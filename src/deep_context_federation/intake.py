"""One-command agent intake pipeline for DCF."""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from deep_context_federation.bootstrap import bootstrap_federation
from deep_context_federation.builder import read_json
from deep_context_federation.builder import utc_now
from deep_context_federation.builder import write_json
from deep_context_federation.builder import write_markdown
from deep_context_federation.quality_gate import evaluate_quality_gate
from deep_context_federation.task_brief import build_task_brief

AGENT_INTAKE_SCHEMA_VERSION = "deep_context_federation_agent_intake_v1"
DEFAULT_AGENT_INTAKE_JSON_NAME = "deep_context_federation_agent_intake.json"
DEFAULT_AGENT_INTAKE_MD_NAME = "DEEP_CONTEXT_FEDERATION_AGENT_INTAKE.md"
DEFAULT_INTAKE_QUALITY_GATE_JSON_NAME = "deep_context_federation_intake_quality_gate.json"
DEFAULT_INTAKE_TASK_BRIEF_JSON_NAME = "deep_context_federation_intake_task_brief.json"


def _status(*, bootstrap_ok: bool, quality_gate_ok: bool, task_brief_status: str) -> tuple[bool, str]:
    ok = bootstrap_ok and quality_gate_ok and task_brief_status != "blocked"
    if not ok:
        return False, "fail_agent_intake"
    if task_brief_status == "warn":
        return True, "warn_agent_intake"
    return True, "pass_agent_intake"


def _next_actions(quality_gate: Mapping[str, Any], task_brief: Mapping[str, Any]) -> list[str]:
    actions: list[str] = []
    if not quality_gate.get("ok"):
        failed_ids = [
            str(row.get("id"))
            for row in quality_gate.get("errors") or []
            if isinstance(row, Mapping) and row.get("id")
        ]
        if failed_ids:
            actions.append("Resolve quality gate failures: " + ", ".join(failed_ids[:8]))
    doctor = task_brief.get("doctor_summary") if isinstance(task_brief.get("doctor_summary"), Mapping) else {}
    for action in doctor.get("recommended_actions") or []:
        if action:
            actions.append(str(action))
    coverage = task_brief.get("coverage") if isinstance(task_brief.get("coverage"), Mapping) else {}
    missing_terms = coverage.get("missing_terms") if isinstance(coverage.get("missing_terms"), list) else []
    if missing_terms:
        actions.append("Review missing task terms before trusting the prompt pack: " + ", ".join(str(term) for term in missing_terms))
    return list(dict.fromkeys(actions))


def build_agent_intake(
    *,
    root: Path,
    output_dir: Path,
    task: str,
    manifests: Sequence[Path] = (),
    quality_gate_policy: Mapping[str, Any] | None = None,
    max_files: int = 5000,
    max_parse_bytes: int = 1_000_000,
    include_hashes: bool = False,
    include_codebase_memory: bool = False,
    codebase_memory_cache_dir: Path | None = None,
    token_budget: int = 4000,
    query_limit: int = 10,
    max_presets: int = 3,
    max_rows: int = 80,
    include_prompt: bool = True,
    write: bool = True,
) -> dict[str, Any]:
    """Run bootstrap, quality gate, and task brief as one read-only intake."""

    started = time.perf_counter()
    root = root.expanduser().resolve()
    output_dir = output_dir.expanduser()
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    bootstrap = bootstrap_federation(
        root=root,
        output_dir=output_dir,
        manifests=manifests,
        max_files=max_files,
        max_parse_bytes=max_parse_bytes,
        include_hashes=include_hashes,
        include_codebase_memory=include_codebase_memory,
        codebase_memory_cache_dir=codebase_memory_cache_dir,
        write=True,
    )
    federation_json = Path(str(bootstrap["outputs"]["federation_json"]))
    federation = read_json(federation_json)
    quality_gate = evaluate_quality_gate(
        bootstrap,
        federation_payload=federation,
        policy=quality_gate_policy,
    )
    task_brief = build_task_brief(
        federation,
        task=task,
        token_budget=token_budget,
        query_limit=query_limit,
        max_presets=max_presets,
        max_rows=max_rows,
        include_prompt=include_prompt,
        input_path=federation_json.as_posix(),
    )
    ok, status = _status(
        bootstrap_ok=bool(bootstrap.get("ok")),
        quality_gate_ok=bool(quality_gate.get("ok")),
        task_brief_status=str(task_brief.get("status") or ""),
    )
    duration_seconds = max(0.0, time.perf_counter() - started)
    outputs = {
        "agent_intake_json": (output_dir / DEFAULT_AGENT_INTAKE_JSON_NAME).as_posix(),
        "agent_intake_markdown": (output_dir / DEFAULT_AGENT_INTAKE_MD_NAME).as_posix(),
        "bootstrap_json": bootstrap["outputs"]["bootstrap_json"],
        "federation_json": bootstrap["outputs"]["federation_json"],
        "federation_sqlite": bootstrap["outputs"]["federation_sqlite"],
        "quality_gate_json": (output_dir / DEFAULT_INTAKE_QUALITY_GATE_JSON_NAME).as_posix(),
        "task_brief_json": (output_dir / DEFAULT_INTAKE_TASK_BRIEF_JSON_NAME).as_posix(),
    }
    result = {
        "schema_version": AGENT_INTAKE_SCHEMA_VERSION,
        "ok": ok,
        "status": status,
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": utc_now(),
        "root": root.as_posix(),
        "output_dir": output_dir.as_posix(),
        "task": task,
        "duration_seconds": round(duration_seconds, 6),
        "bootstrap_summary": {
            "ok": bootstrap.get("ok"),
            "status": bootstrap.get("status"),
            "duration_seconds": bootstrap.get("duration_seconds"),
            "build": bootstrap.get("build"),
            "verify": bootstrap.get("verify"),
            "doctor": bootstrap.get("doctor"),
        },
        "quality_gate_summary": {
            "ok": quality_gate.get("ok"),
            "status": quality_gate.get("status"),
            "error_count": quality_gate.get("error_count"),
            "summary": quality_gate.get("summary"),
        },
        "task_brief_summary": {
            "status": task_brief.get("status"),
            "selected_presets": task_brief.get("selected_presets"),
            "context_budget": task_brief.get("context_budget"),
            "coverage": task_brief.get("coverage"),
        },
        "quality_gate": quality_gate,
        "task_brief": task_brief,
        "next_actions": _next_actions(quality_gate, task_brief),
        "outputs": outputs,
        "safety_boundaries": {
            "authority_effect": "none",
            "no_apply": True,
            "mutation_allowed": False,
            "writes_only_output_dir": True,
            "external_model_calls": False,
            "live_runtime_or_broker_mutation": False,
        },
    }
    if write:
        write_json(output_dir / DEFAULT_INTAKE_QUALITY_GATE_JSON_NAME, quality_gate)
        write_json(output_dir / DEFAULT_INTAKE_TASK_BRIEF_JSON_NAME, task_brief)
        write_json(output_dir / DEFAULT_AGENT_INTAKE_JSON_NAME, result)
        write_markdown(output_dir / DEFAULT_AGENT_INTAKE_MD_NAME, markdown_agent_intake(result).splitlines())
    return result


def markdown_agent_intake(result: Mapping[str, Any]) -> str:
    bootstrap = result.get("bootstrap_summary") if isinstance(result.get("bootstrap_summary"), Mapping) else {}
    gate = result.get("quality_gate_summary") if isinstance(result.get("quality_gate_summary"), Mapping) else {}
    brief = result.get("task_brief_summary") if isinstance(result.get("task_brief_summary"), Mapping) else {}
    budget = brief.get("context_budget") if isinstance(brief.get("context_budget"), Mapping) else {}
    lines = [
        "# Deep Context Federation Agent Intake",
        "",
        f"- Status: `{result.get('status')}`",
        f"- Authority effect: `{result.get('authority_effect')}`",
        f"- No apply: `{result.get('no_apply')}`",
        f"- Task: `{result.get('task')}`",
        f"- Duration: `{result.get('duration_seconds')}`s",
        "",
        "## Gates",
        "",
        f"- Bootstrap: `{bootstrap.get('status')}`",
        f"- Quality gate: `{gate.get('status')}` errors=`{gate.get('error_count')}`",
        f"- Task brief: `{brief.get('status')}`",
        f"- Context tokens: `{budget.get('context_pack_estimated_tokens')}` / `{budget.get('token_budget')}`",
        f"- Compression ratio: `{budget.get('compression_ratio')}`",
        "",
        "## Next Actions",
        "",
    ]
    actions = [str(item) for item in result.get("next_actions") or []]
    if actions:
        for action in actions:
            lines.append(f"- {action}")
    else:
        lines.append("- none")
    lines.extend(["", "## Outputs", ""])
    outputs = result.get("outputs") if isinstance(result.get("outputs"), Mapping) else {}
    for key in sorted(outputs):
        lines.append(f"- `{key}`: `{outputs.get(key)}`")
    return "\n".join(lines).rstrip() + "\n"
