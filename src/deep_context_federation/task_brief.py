"""Task routing brief for agents consuming DCF artifacts."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from deep_context_federation.context_pack import estimate_tokens
from deep_context_federation.context_pack import pack_context
from deep_context_federation.doctor import doctor_federation
from deep_context_federation.query import query_federation

TASK_BRIEF_SCHEMA_VERSION = "deep_context_federation_task_brief_v1"

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "this",
    "to",
    "what",
    "with",
}

_PRESET_RULES = {
    "surface-splits": {"surface", "split", "fragment", "fragmentation", "entrypoint", "入口", "表面", "分裂"},
    "claim-lineage": {"claim", "lineage", "evidence", "authority", "verifier", "readiness", "權威", "證據"},
    "stale-sources": {"stale", "missing", "drift", "outdated", "freshness", "過期", "漂移", "缺失"},
    "code-to-authority": {"code", "symbol", "path", "file", "module", "source", "程式", "檔案", "符號"},
    "r19-context": {"r19", "alpha", "research", "candidate", "mining"},
    "operator-projection": {"operator", "dashboard", "governance", "cockpit", "runtime", "ops", "治理", "儀表板"},
}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _terms(task: str) -> list[str]:
    terms = []
    for raw in re.findall(r"[A-Za-z0-9_./:-]+|[\u4e00-\u9fff]+", task.lower()):
        if len(raw) < 2 or raw in _STOPWORDS:
            continue
        terms.append(raw)
    return sorted(set(terms), key=lambda item: (-len(item), item))


def _json_text(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    except Exception:
        return str(value)


def _select_presets(task: str, terms: Sequence[str], *, max_presets: int) -> list[dict[str, Any]]:
    task_text = task.lower()
    scored: list[dict[str, Any]] = []
    for preset, keywords in _PRESET_RULES.items():
        matched = sorted(keyword for keyword in keywords if keyword in task_text or keyword in terms)
        score = len(matched) * 10
        if preset == "claim-lineage" and not scored:
            score += 1
        if matched or preset == "claim-lineage":
            scored.append({"preset": preset, "score": score, "matched_terms": matched})
    scored.sort(key=lambda item: (-int(item["score"]), str(item["preset"])))
    return scored[: max(1, int(max_presets))]


def _query_summaries(payload: Mapping[str, Any], presets: Sequence[Mapping[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    summaries = []
    for preset in presets:
        preset_name = str(preset.get("preset") or "")
        result = query_federation(payload, preset=preset_name, limit=limit)
        rows = result.get("rows") if isinstance(result.get("rows"), list) else []
        summaries.append(
            {
                "preset": preset_name,
                "status": result.get("status"),
                "row_count": result.get("row_count"),
                "matched_terms": preset.get("matched_terms") or [],
                "sample_rows": rows[: min(3, len(rows))],
            }
        )
    return summaries


def _recommended_commands(
    *,
    input_path: str,
    task: str,
    token_budget: int,
    selected_presets: Sequence[Mapping[str, Any]],
    query_limit: int,
) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = [
        {
            "purpose": "refresh_health_before_action",
            "command": f"dcf doctor --input {input_path} --format markdown",
        },
        {
            "purpose": "generate_bounded_model_context",
            "command": (
                "dcf pack --input {input_path} --task {task_json} --token-budget {budget} "
                "--output .dcf/deep_context_federation_context_pack.json"
            ).format(input_path=input_path, task_json=json.dumps(task, ensure_ascii=True), budget=token_budget),
        },
    ]
    for preset in selected_presets:
        commands.append(
            {
                "purpose": f"inspect_{preset.get('preset')}",
                "command": "dcf query --input {input_path} --preset {preset} --limit {limit} --format markdown".format(
                    input_path=input_path,
                    preset=preset.get("preset"),
                    limit=query_limit,
                ),
            }
        )
    return commands


def _default_read_model_path(input_path: str) -> str:
    text = str(input_path or "").strip()
    if text.endswith(".json"):
        return text[:-5] + ".sqlite"
    return ".dcf/deep_context_federation_latest.sqlite"


def _query_plan(
    *,
    input_path: str,
    read_model_path: str,
    task: str,
    terms: Sequence[str],
    token_budget: int,
    selected_presets: Sequence[Mapping[str, Any]],
    query_limit: int,
    max_rows: int,
    include_prompt: bool,
) -> dict[str, Any]:
    steps: list[dict[str, Any]] = [
        {
            "step_id": "00_health_gate",
            "command": "doctor",
            "argv": ["doctor", "--input", input_path, "--format", "json"],
            "read_role": "gate_first",
            "artifact_role": "health_gate",
            "stop_on_failure": True,
        },
        {
            "step_id": "01_pack_bounded_context",
            "command": "pack",
            "argv": [
                "pack",
                "--input",
                input_path,
                "--task",
                task,
                "--token-budget",
                str(token_budget),
                "--max-rows",
                str(max_rows),
                "--format",
                "json",
            ]
            + ([] if include_prompt else ["--no-prompt"]),
            "read_role": "read_first",
            "artifact_role": "bounded_context",
            "stop_on_failure": False,
        },
    ]
    for index, preset in enumerate(selected_presets, start=1):
        preset_name = str(preset.get("preset") or "")
        steps.append(
            {
                "step_id": f"1{index}_query_json_{preset_name.replace('-', '_')}",
                "command": "query",
                "argv": ["query", "--input", input_path, "--preset", preset_name, "--limit", str(query_limit), "--format", "json"],
                "read_role": "expand_if_needed",
                "artifact_role": "json_artifact_query",
                "preset": preset_name,
                "stop_on_failure": False,
            }
        )
        steps.append(
            {
                "step_id": f"2{index}_query_read_model_{preset_name.replace('-', '_')}",
                "command": "query-read-model",
                "argv": ["query-read-model", "--read-model", read_model_path, "--preset", preset_name, "--limit", str(query_limit), "--format", "json"],
                "read_role": "expand_if_read_model_available",
                "artifact_role": "read_model_query",
                "preset": preset_name,
                "stop_on_failure": False,
                "optional": True,
            }
        )
    return {
        "schema_version": "deep_context_federation_task_query_plan_v1",
        "authority_effect": "none",
        "no_apply": True,
        "task": task,
        "terms": list(terms),
        "input_ref": input_path,
        "read_model_ref": read_model_path,
        "selected_presets": [dict(row) for row in selected_presets],
        "steps": steps,
        "expansion_policy": {
            "default_read_roles": ["gate_first", "read_first"],
            "expand_read_roles": ["expand_if_needed", "expand_if_read_model_available"],
            "audit_only": ["full_federation_json", "full_read_model"],
            "prefer_argv_over_command_string": True,
            "read_model_queries_are_optional": True,
        },
    }


def build_task_brief(
    payload: Mapping[str, Any],
    *,
    task: str,
    token_budget: int = 4000,
    query_limit: int = 10,
    max_presets: int = 3,
    max_rows: int = 80,
    include_prompt: bool = True,
    input_path: str = ".dcf/deep_context_federation_latest.json",
    read_model_path: str | None = None,
) -> dict[str, Any]:
    """Build a one-shot machine-readable routing brief for an agent task."""

    token_budget = max(300, int(token_budget))
    query_limit = max(1, int(query_limit))
    terms = _terms(task)
    read_model_ref = str(read_model_path or _default_read_model_path(input_path))
    selected_presets = _select_presets(task, terms, max_presets=max_presets)
    routed_queries = _query_summaries(payload, selected_presets, limit=query_limit)
    context_pack = pack_context(
        payload,
        task=task,
        token_budget=token_budget,
        max_rows=max_rows,
        include_prompt=include_prompt,
    )
    doctor = doctor_federation(payload)
    context_budget = {
        "token_budget": token_budget,
        "original_estimated_tokens": context_pack.get("original_estimated_tokens"),
        "brief_estimated_tokens": 0,
        "context_pack_estimated_tokens": context_pack.get("estimated_tokens"),
        "estimated_token_savings": context_pack.get("estimated_token_savings"),
        "compression_ratio": context_pack.get("compression_ratio"),
        "budget_utilization": context_pack.get("budget_utilization"),
    }
    status = "ready"
    if doctor.get("status") == "fail":
        status = "blocked"
    elif doctor.get("status") == "warn" or context_pack.get("coverage", {}).get("missing_terms"):
        status = "warn"
    result: dict[str, Any] = {
        "schema_version": TASK_BRIEF_SCHEMA_VERSION,
        "status": status,
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": _utc_now(),
        "task": task,
        "terms": terms,
        "source_snapshot": {
            "schema_version": payload.get("schema_version"),
            "generated_at": payload.get("generated_at"),
            "head_commit": payload.get("head_commit"),
            "authority_effect": payload.get("authority_effect"),
            "no_apply": payload.get("no_apply"),
        },
        "selected_presets": selected_presets,
        "routed_queries": routed_queries,
        "query_plan": _query_plan(
            input_path=input_path,
            read_model_path=read_model_ref,
            task=task,
            terms=terms,
            token_budget=token_budget,
            selected_presets=selected_presets,
            query_limit=query_limit,
            max_rows=max_rows,
            include_prompt=include_prompt,
        ),
        "doctor_summary": {
            "status": doctor.get("status"),
            "ok": doctor.get("ok"),
            "error_count": doctor.get("error_count"),
            "warning_count": doctor.get("warning_count"),
            "recommended_actions": doctor.get("recommended_actions") or [],
        },
        "context_budget": context_budget,
        "coverage": context_pack.get("coverage") or {},
        "context_pack": context_pack,
        "recommended_commands": _recommended_commands(
            input_path=input_path,
            task=task,
            token_budget=token_budget,
            selected_presets=selected_presets,
            query_limit=query_limit,
        ),
        "safety_boundaries": {
            "authority_effect": "none",
            "no_apply": True,
            "mutation_allowed": False,
            "external_model_calls": False,
            "use_prompt_text_as_context_only": True,
            "query_plan_executes_commands": False,
        },
    }
    result["context_budget"]["brief_estimated_tokens"] = estimate_tokens(
        {
            "schema_version": result["schema_version"],
            "task": result["task"],
            "selected_presets": result["selected_presets"],
            "doctor_summary": result["doctor_summary"],
            "coverage": result["coverage"],
            "context_pack_prompt_text": result["context_pack"].get("prompt_text"),
        }
    )
    return result


def markdown_task_brief(result: Mapping[str, Any]) -> str:
    budget = result.get("context_budget") if isinstance(result.get("context_budget"), Mapping) else {}
    doctor = result.get("doctor_summary") if isinstance(result.get("doctor_summary"), Mapping) else {}
    lines = [
        "# Deep Context Federation Task Brief",
        "",
        f"- Status: `{result.get('status')}`",
        f"- Task: `{result.get('task')}`",
        f"- Doctor: `{doctor.get('status')}` errors=`{doctor.get('error_count')}` warnings=`{doctor.get('warning_count')}`",
        f"- Context tokens: `{budget.get('context_pack_estimated_tokens')}` / `{budget.get('token_budget')}`",
        f"- Compression ratio: `{budget.get('compression_ratio')}`",
        "",
        "## Selected Presets",
        "",
    ]
    for preset in result.get("selected_presets") or []:
        if isinstance(preset, Mapping):
            lines.append(f"- `{preset.get('preset')}` score=`{preset.get('score')}` matched=`{','.join(preset.get('matched_terms') or [])}`")
    if not result.get("selected_presets"):
        lines.append("- none")
    lines.extend(["", "## Query Plan", ""])
    query_plan = result.get("query_plan") if isinstance(result.get("query_plan"), Mapping) else {}
    for step in query_plan.get("steps") or []:
        if isinstance(step, Mapping):
            optional = " optional=true" if step.get("optional") else ""
            lines.append(
                f"- `{step.get('step_id')}` command=`{step.get('command')}` read_role=`{step.get('read_role')}`{optional}"
            )
    if not query_plan.get("steps"):
        lines.append("- none")
    lines.extend(["", "## Recommended Commands", ""])
    for command in result.get("recommended_commands") or []:
        if isinstance(command, Mapping):
            lines.append(f"- `{command.get('purpose')}`: `{command.get('command')}`")
    lines.extend(["", "## Prompt Text", ""])
    context_pack = result.get("context_pack") if isinstance(result.get("context_pack"), Mapping) else {}
    prompt_text = str(context_pack.get("prompt_text") or "").rstrip()
    lines.append("```text")
    lines.append(prompt_text or "prompt_text disabled")
    lines.append("```")
    return "\n".join(lines).rstrip() + "\n"
