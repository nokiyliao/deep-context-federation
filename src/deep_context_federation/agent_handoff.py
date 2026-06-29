"""One-command gated agent handoff pipeline."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from deep_context_federation.agent_ci import build_agent_ci
from deep_context_federation.agent_context import build_agent_context
from deep_context_federation.agent_context import markdown_agent_context
from deep_context_federation.agent_context_gate import evaluate_agent_context_gate
from deep_context_federation.agent_context_gate import markdown_agent_context_gate
from deep_context_federation.builder import utc_now
from deep_context_federation.builder import write_json
from deep_context_federation.builder import write_markdown
from deep_context_federation.context_pack import estimate_tokens

AGENT_HANDOFF_SCHEMA_VERSION = "deep_context_federation_agent_handoff_v1"
DEFAULT_AGENT_HANDOFF_JSON_NAME = "deep_context_federation_agent_handoff.json"
DEFAULT_AGENT_HANDOFF_MD_NAME = "DEEP_CONTEXT_FEDERATION_AGENT_HANDOFF.md"
DEFAULT_AGENT_CONTEXT_JSON_NAME = "deep_context_federation_agent_context.json"
DEFAULT_AGENT_CONTEXT_MD_NAME = "DEEP_CONTEXT_FEDERATION_AGENT_CONTEXT.md"
DEFAULT_AGENT_CONTEXT_GATE_JSON_NAME = "deep_context_federation_agent_context_gate.json"
DEFAULT_AGENT_CONTEXT_GATE_MD_NAME = "DEEP_CONTEXT_FEDERATION_AGENT_CONTEXT_GATE.md"
DEFAULT_AGENT_MODEL_PROMPT_MD_NAME = "DEEP_CONTEXT_FEDERATION_AGENT_MODEL_PROMPT.md"


def _normalize_output_dir(root: Path, output_dir: Path) -> Path:
    root = root.expanduser().resolve()
    output_dir = output_dir.expanduser()
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    return output_dir.resolve()


def _json_text(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    except Exception:
        return str(value)


def _summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    return {
        "schema_version": payload.get("schema_version"),
        "status": payload.get("status"),
        "ok": payload.get("ok"),
        "summary": dict(summary),
    }


def _failed_check_ids(payload: Mapping[str, Any]) -> list[str]:
    result = []
    for row in payload.get("errors") or []:
        if isinstance(row, Mapping):
            result.append(str(row.get("id") or "unknown_check"))
    return result


def _handoff_decision(agent_ci: Mapping[str, Any], agent_context: Mapping[str, Any], agent_context_gate: Mapping[str, Any]) -> dict[str, Any]:
    stop_reasons: list[dict[str, Any]] = []
    cautions: list[dict[str, Any]] = []
    if agent_ci.get("ok") is not True:
        stop_reasons.append({"id": "agent_ci_failed", "status": agent_ci.get("status")})
    if agent_context.get("ok") is not True:
        stop_reasons.append({"id": "agent_context_failed", "status": agent_context.get("status")})
    if agent_context_gate.get("ok") is not True:
        stop_reasons.append(
            {
                "id": "agent_context_gate_failed",
                "status": agent_context_gate.get("status"),
                "failed_check_ids": _failed_check_ids(agent_context_gate),
            }
        )
    for name, payload in (
        ("agent_ci", agent_ci),
        ("agent_context", agent_context),
        ("agent_context_gate", agent_context_gate),
    ):
        if str(payload.get("status") or "").startswith("warn"):
            cautions.append({"id": f"{name}_warn", "status": payload.get("status")})

    if stop_reasons:
        return {
            "action": "stop",
            "handoff_allowed": False,
            "reason": "required_gate_failed",
            "stop_reasons": stop_reasons,
            "cautions": cautions,
        }
    if cautions:
        return {
            "action": "handoff_with_caution",
            "handoff_allowed": True,
            "reason": "all_required_gates_passed_with_warnings",
            "stop_reasons": [],
            "cautions": cautions,
        }
    return {
        "action": "handoff",
        "handoff_allowed": True,
        "reason": "all_required_gates_passed",
        "stop_reasons": [],
        "cautions": [],
    }


def _render_prompt_text(result: Mapping[str, Any]) -> str:
    decision = result.get("decision") if isinstance(result.get("decision"), Mapping) else {}
    model_handoff = result.get("model_handoff") if isinstance(result.get("model_handoff"), Mapping) else {}
    lines = [
        "# Deep Context Federation Agent Handoff",
        "",
        "Boundary: authority_effect=none; no_apply=true; generated artifacts only.",
        f"Status: {result.get('status')}",
        f"Decision: {decision.get('action')}",
        f"Task: {result.get('task')}",
        f"Model prompt source: {model_handoff.get('model_prompt_source')}",
        "",
        "## Required Reads",
    ]
    for item in model_handoff.get("read_first") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Stop Reasons"])
    for row in decision.get("stop_reasons") or []:
        if isinstance(row, Mapping):
            lines.append(f"- {row.get('id')}: {row.get('status')}")
    if not decision.get("stop_reasons"):
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def build_agent_handoff(
    *,
    root: Path,
    output_dir: Path,
    task: str,
    targets: Sequence[str] = (),
    manifests: Sequence[Path] = (),
    quality_gate_policy: Mapping[str, Any] | None = None,
    target_review_gate_policy: Mapping[str, Any] | None = None,
    efficiency_gate_policy: Mapping[str, Any] | None = None,
    agent_context_gate_policy: Mapping[str, Any] | None = None,
    quality_policy_path: Path | None = None,
    target_review_policy_path: Path | None = None,
    workflow_token_budget: int = 4000,
    context_token_budget: int = 4000,
    context_mode: str = "read-first",
    max_artifact_tokens: int = 1200,
    query_limit: int = 10,
    max_presets: int = 3,
    max_rows: int = 80,
    max_files: int = 5000,
    max_parse_bytes: int = 1_000_000,
    include_hashes: bool = False,
    include_codebase_memory: bool = False,
    codebase_memory_cache_dir: Path | None = None,
    include_content: bool = True,
    include_prompt: bool = True,
    include_details: bool = False,
    extra_baselines: Sequence[Path] = (),
) -> dict[str, Any]:
    """Build agent CI, bounded context, context gate, and one final handoff."""

    started = time.perf_counter()
    root = root.expanduser().resolve()
    out_dir = _normalize_output_dir(root, output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    agent_ci = build_agent_ci(
        root=root,
        output_dir=out_dir,
        manifests=manifests,
        task=task,
        targets=targets,
        quality_gate_policy=quality_gate_policy,
        target_review_gate_policy=target_review_gate_policy,
        efficiency_gate_policy=efficiency_gate_policy,
        quality_policy_path=quality_policy_path,
        target_review_policy_path=target_review_policy_path,
        token_budget=workflow_token_budget,
        query_limit=query_limit,
        max_presets=max_presets,
        max_rows=max_rows,
        max_files=max_files,
        max_parse_bytes=max_parse_bytes,
        include_hashes=include_hashes,
        include_codebase_memory=include_codebase_memory,
        codebase_memory_cache_dir=codebase_memory_cache_dir,
        include_prompt=include_prompt,
        include_details=include_details,
        extra_baselines=extra_baselines,
    )

    agent_ci_path = Path(str(agent_ci.get("outputs", {}).get("agent_ci_json") or ""))
    agent_context = build_agent_context(
        agent_ci,
        agent_ci_path=agent_ci_path,
        mode=context_mode,
        token_budget=context_token_budget,
        max_artifact_tokens=max_artifact_tokens,
        include_content=include_content,
        include_prompt=include_prompt,
    )
    agent_context_json = out_dir / DEFAULT_AGENT_CONTEXT_JSON_NAME
    agent_context_md = out_dir / DEFAULT_AGENT_CONTEXT_MD_NAME
    agent_model_prompt_md = out_dir / DEFAULT_AGENT_MODEL_PROMPT_MD_NAME
    agent_context["outputs"] = {
        "agent_context_json": agent_context_json.as_posix(),
        "agent_context_markdown": agent_context_md.as_posix(),
        "agent_model_prompt_markdown": agent_model_prompt_md.as_posix() if include_prompt else "",
    }
    write_json(agent_context_json, agent_context)
    write_markdown(agent_context_md, markdown_agent_context(agent_context).splitlines())
    prompt_text = str(agent_context.get("prompt_text") or "")
    if include_prompt and prompt_text:
        write_markdown(agent_model_prompt_md, prompt_text.splitlines())

    agent_context_gate = evaluate_agent_context_gate(agent_context, policy=agent_context_gate_policy)
    agent_context_gate_json = out_dir / DEFAULT_AGENT_CONTEXT_GATE_JSON_NAME
    agent_context_gate_md = out_dir / DEFAULT_AGENT_CONTEXT_GATE_MD_NAME
    agent_context_gate["outputs"] = {
        "agent_context_gate_json": agent_context_gate_json.as_posix(),
        "agent_context_gate_markdown": agent_context_gate_md.as_posix(),
    }
    write_json(agent_context_gate_json, agent_context_gate)
    write_markdown(agent_context_gate_md, markdown_agent_context_gate(agent_context_gate).splitlines())

    decision = _handoff_decision(agent_ci, agent_context, agent_context_gate)
    ok = bool(decision.get("handoff_allowed"))
    status = "fail_agent_handoff"
    if ok:
        status = "warn_agent_handoff" if decision.get("action") == "handoff_with_caution" else "pass_agent_handoff"

    handoff_json = out_dir / DEFAULT_AGENT_HANDOFF_JSON_NAME
    handoff_md = out_dir / DEFAULT_AGENT_HANDOFF_MD_NAME
    outputs = {
        "agent_handoff_json": handoff_json.as_posix(),
        "agent_handoff_markdown": handoff_md.as_posix(),
        "agent_ci_json": str(agent_ci.get("outputs", {}).get("agent_ci_json") or ""),
        "agent_context_json": agent_context_json.as_posix(),
        "agent_model_prompt_markdown": agent_model_prompt_md.as_posix() if include_prompt and prompt_text else "",
        "agent_context_gate_json": agent_context_gate_json.as_posix(),
    }
    model_prompt_source = agent_model_prompt_md.as_posix() if ok and include_prompt and prompt_text else ""
    model_handoff = {
        "read_first": [
            item
            for item in (handoff_json.as_posix(), agent_context_gate_json.as_posix(), model_prompt_source)
            if item
        ],
        "model_prompt_source": model_prompt_source,
        "model_prompt_format": "markdown" if model_prompt_source else "",
        "model_prompt_estimated_tokens": agent_context.get("prompt_estimated_tokens") if ok else 0,
        "machine_context_source": agent_context_json.as_posix(),
        "skip_by_default": [
            "full repository tree",
            "full federation artifact",
            "machine context JSON unless debugging or auditing",
            "raw source files without target match",
            "ungated agent context",
        ],
    }
    result: dict[str, Any] = {
        "schema_version": AGENT_HANDOFF_SCHEMA_VERSION,
        "ok": ok,
        "status": status,
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": utc_now(),
        "duration_seconds": round(max(0.0, time.perf_counter() - started), 6),
        "root": root.as_posix(),
        "output_dir": out_dir.as_posix(),
        "task": task,
        "targets": list(dict.fromkeys(str(item).strip() for item in targets if str(item).strip())),
        "decision": decision,
        "agent_ci_summary": _summary(agent_ci),
        "agent_context_summary": _summary(agent_context),
        "agent_context_gate_summary": _summary(agent_context_gate),
        "model_handoff": model_handoff,
        "outputs": outputs,
        "safety_boundaries": {
            "authority_effect": "none",
            "no_apply": True,
            "mutation_allowed": False,
            "writes_only_output_dir": True,
            "external_model_calls": False,
            "source_or_authority_mutation": False,
        },
    }
    prompt_text = _render_prompt_text(result) if include_prompt else ""
    result["prompt_text"] = prompt_text
    result["prompt_estimated_tokens"] = estimate_tokens(prompt_text) if prompt_text else 0
    result["json_estimated_tokens"] = estimate_tokens(_json_text(result))
    write_json(handoff_json, result)
    write_markdown(handoff_md, markdown_agent_handoff(result).splitlines())
    return result


def markdown_agent_handoff(result: Mapping[str, Any]) -> str:
    decision = result.get("decision") if isinstance(result.get("decision"), Mapping) else {}
    model_handoff = result.get("model_handoff") if isinstance(result.get("model_handoff"), Mapping) else {}
    gate_summary = result.get("agent_context_gate_summary") if isinstance(result.get("agent_context_gate_summary"), Mapping) else {}
    lines = [
        "# Deep Context Federation Agent Handoff",
        "",
        f"- Status: `{result.get('status')}`",
        f"- OK: `{result.get('ok')}`",
        f"- Decision: `{decision.get('action')}`",
        f"- Handoff allowed: `{decision.get('handoff_allowed')}`",
        f"- Task: `{result.get('task')}`",
        f"- Context gate status: `{gate_summary.get('status')}`",
        f"- Model prompt source: `{model_handoff.get('model_prompt_source')}`",
        f"- Model prompt tokens: `{model_handoff.get('model_prompt_estimated_tokens')}`",
        "",
        "## Stop Reasons",
        "",
    ]
    stop_reasons = [row for row in decision.get("stop_reasons") or [] if isinstance(row, Mapping)]
    if stop_reasons:
        for row in stop_reasons:
            lines.append(f"- `{row.get('id')}` status=`{row.get('status')}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Read First", ""])
    for item in model_handoff.get("read_first") or []:
        lines.append(f"- `{item}`")
    return "\n".join(lines).rstrip() + "\n"
