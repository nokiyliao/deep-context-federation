"""Integrated agent continuation gate for DCF workflows."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from deep_context_federation.builder import utc_now
from deep_context_federation.builder import write_json
from deep_context_federation.builder import write_markdown
from deep_context_federation.context_pack import estimate_tokens
from deep_context_federation.efficiency_gate import DEFAULT_EFFICIENCY_GATE_JSON_NAME
from deep_context_federation.efficiency_gate import DEFAULT_EFFICIENCY_GATE_MD_NAME
from deep_context_federation.efficiency_gate import evaluate_efficiency_gate
from deep_context_federation.efficiency_gate import markdown_efficiency_gate
from deep_context_federation.efficiency_report import DEFAULT_EFFICIENCY_REPORT_JSON_NAME
from deep_context_federation.efficiency_report import DEFAULT_EFFICIENCY_REPORT_MD_NAME
from deep_context_federation.efficiency_report import build_efficiency_report
from deep_context_federation.efficiency_report import markdown_efficiency_report
from deep_context_federation.workflow_run import build_workflow_run

AGENT_CI_SCHEMA_VERSION = "deep_context_federation_agent_ci_v1"
DEFAULT_AGENT_CI_JSON_NAME = "deep_context_federation_agent_ci.json"
DEFAULT_AGENT_CI_MD_NAME = "DEEP_CONTEXT_FEDERATION_AGENT_CI.md"


def _normalize_output_dir(root: Path, output_dir: Path) -> Path:
    root = root.expanduser().resolve()
    output_dir = output_dir.expanduser()
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    return output_dir.resolve()


def _failed_step_ids(workflow_run: Mapping[str, Any]) -> list[str]:
    result: list[str] = []
    for row in workflow_run.get("step_results") or []:
        if isinstance(row, Mapping) and row.get("ok") is False:
            result.append(str(row.get("step_id") or "unknown_step"))
    return result


def _failed_check_ids(gate: Mapping[str, Any]) -> list[str]:
    result: list[str] = []
    for row in gate.get("errors") or []:
        if isinstance(row, Mapping):
            result.append(str(row.get("id") or "unknown_check"))
    return result


def _status_is_warn(payload: Mapping[str, Any]) -> bool:
    return str(payload.get("status") or "").startswith("warn")


def _workflow_summary(workflow_run: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": workflow_run.get("status"),
        "ok": workflow_run.get("ok"),
        "target_count": workflow_run.get("target_count"),
        "duration_seconds": workflow_run.get("duration_seconds"),
        "failed_step_ids": _failed_step_ids(workflow_run),
    }


def _report_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    budget = report.get("model_context_budget") if isinstance(report.get("model_context_budget"), Mapping) else {}
    return {
        "status": report.get("status"),
        "ok": report.get("ok"),
        "artifact_count": report.get("artifact_count"),
        "warning_count": len(report.get("warnings") or []),
        "missing_required_count": len(report.get("missing_required_artifacts") or []),
        "read_first_estimated_tokens": budget.get("read_first_estimated_tokens"),
        "gate_pass_estimated_tokens": budget.get("gate_pass_estimated_tokens"),
        "effective_baseline_estimated_tokens": budget.get("effective_baseline_estimated_tokens"),
        "read_first_savings_percent": budget.get("read_first_savings_percent"),
        "gate_pass_savings_percent": budget.get("gate_pass_savings_percent"),
    }


def _gate_summary(gate: Mapping[str, Any]) -> dict[str, Any]:
    summary = gate.get("summary") if isinstance(gate.get("summary"), Mapping) else {}
    return {
        "status": gate.get("status"),
        "ok": gate.get("ok"),
        "check_count": gate.get("check_count"),
        "error_count": gate.get("error_count"),
        "failed_check_ids": _failed_check_ids(gate),
        "read_first_estimated_tokens": summary.get("read_first_estimated_tokens"),
        "effective_baseline_estimated_tokens": summary.get("effective_baseline_estimated_tokens"),
        "read_first_savings_percent": summary.get("read_first_savings_percent"),
    }


def _decision(
    *,
    workflow_run: Mapping[str, Any],
    efficiency_report: Mapping[str, Any],
    efficiency_gate: Mapping[str, Any],
) -> dict[str, Any]:
    stop_reasons: list[dict[str, Any]] = []
    if workflow_run.get("ok") is not True:
        stop_reasons.append(
            {
                "id": "workflow_run_failed",
                "status": workflow_run.get("status"),
                "failed_step_ids": _failed_step_ids(workflow_run),
            }
        )
    if efficiency_report.get("ok") is not True:
        stop_reasons.append(
            {
                "id": "efficiency_report_failed",
                "status": efficiency_report.get("status"),
                "missing_required_artifacts": list(efficiency_report.get("missing_required_artifacts") or []),
            }
        )
    if efficiency_gate.get("ok") is not True:
        stop_reasons.append(
            {
                "id": "efficiency_gate_failed",
                "status": efficiency_gate.get("status"),
                "failed_check_ids": _failed_check_ids(efficiency_gate),
            }
        )

    cautions: list[dict[str, Any]] = []
    for label, payload in (
        ("workflow_run", workflow_run),
        ("efficiency_report", efficiency_report),
        ("efficiency_gate", efficiency_gate),
    ):
        if _status_is_warn(payload):
            cautions.append({"id": f"{label}_warn", "status": payload.get("status")})
    warnings = efficiency_report.get("warnings") if isinstance(efficiency_report.get("warnings"), list) else []
    for warning in warnings:
        cautions.append({"id": "efficiency_report_warning", "detail": str(warning)})

    if stop_reasons:
        return {
            "action": "stop",
            "continue_agent": False,
            "reason": "required_gate_failed",
            "stop_reasons": stop_reasons,
            "cautions": cautions,
        }
    if cautions:
        return {
            "action": "continue_with_caution",
            "continue_agent": True,
            "reason": "all_required_gates_passed_with_warnings",
            "stop_reasons": [],
            "cautions": cautions,
        }
    return {
        "action": "continue",
        "continue_agent": True,
        "reason": "all_required_gates_passed",
        "stop_reasons": [],
        "cautions": [],
    }


def _next_reads(
    *,
    agent_ci_json: str,
    efficiency_report_json: str,
    efficiency_gate_json: str,
    workflow_run: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> dict[str, Any]:
    handoff = workflow_run.get("model_handoff") if isinstance(workflow_run.get("model_handoff"), Mapping) else {}
    read_first = [agent_ci_json, efficiency_gate_json, efficiency_report_json]
    read_first.extend(str(item) for item in handoff.get("read_first") or [] if item)
    read_next = list(str(item) for item in handoff.get("read_next_if_gate_passes") or [] if item)
    if decision.get("action") == "stop":
        read_next = []
    return {
        "read_first": list(dict.fromkeys(read_first)),
        "read_next_if_decision_allows": list(dict.fromkeys(read_next)),
        "skip_by_default": list(handoff.get("skip_by_default") or []),
    }


def _render_prompt_text(result: Mapping[str, Any]) -> str:
    decision = result.get("decision") if isinstance(result.get("decision"), Mapping) else {}
    reads = result.get("next_reads") if isinstance(result.get("next_reads"), Mapping) else {}
    summary = result.get("efficiency_report_summary") if isinstance(result.get("efficiency_report_summary"), Mapping) else {}
    lines = [
        "# Deep Context Federation Agent CI",
        "",
        "Boundary: authority_effect=none; no_apply=true; generated artifacts only.",
        f"Status: {result.get('status')}",
        f"Decision: {decision.get('action')}",
        f"Task: {result.get('task')}",
        f"Read-first savings: {summary.get('read_first_savings_percent')}%",
        "",
        "## Read First",
    ]
    for item in reads.get("read_first") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Stop Reasons"])
    for row in decision.get("stop_reasons") or []:
        if isinstance(row, Mapping):
            lines.append(f"- {row.get('id')}: {row.get('status')}")
    if not decision.get("stop_reasons"):
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def build_agent_ci(
    *,
    root: Path,
    output_dir: Path,
    task: str,
    targets: Sequence[str] = (),
    manifests: Sequence[Path] = (),
    quality_gate_policy: Mapping[str, Any] | None = None,
    target_review_gate_policy: Mapping[str, Any] | None = None,
    efficiency_gate_policy: Mapping[str, Any] | None = None,
    quality_policy_path: Path | None = None,
    target_review_policy_path: Path | None = None,
    token_budget: int = 4000,
    query_limit: int = 10,
    max_presets: int = 3,
    max_rows: int = 80,
    max_files: int = 5000,
    max_parse_bytes: int = 1_000_000,
    include_hashes: bool = False,
    include_codebase_memory: bool = False,
    codebase_memory_cache_dir: Path | None = None,
    include_prompt: bool = True,
    include_details: bool = False,
    extra_baselines: Sequence[Path] = (),
) -> dict[str, Any]:
    """Run workflow, efficiency report, and efficiency gate into one CI decision."""

    started = time.perf_counter()
    root = root.expanduser().resolve()
    out_dir = _normalize_output_dir(root, output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    workflow_run = build_workflow_run(
        root=root,
        output_dir=out_dir,
        manifests=manifests,
        task=task,
        targets=targets,
        quality_gate_policy=quality_gate_policy,
        target_review_gate_policy=target_review_gate_policy,
        quality_policy_path=quality_policy_path,
        target_review_policy_path=target_review_policy_path,
        token_budget=token_budget,
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
    )
    workflow_run_path = Path(str(workflow_run.get("outputs", {}).get("workflow_run_json") or ""))

    efficiency_report = build_efficiency_report(
        workflow_run,
        workflow_run_path=workflow_run_path,
        extra_baselines=extra_baselines,
    )
    efficiency_report_json = out_dir / DEFAULT_EFFICIENCY_REPORT_JSON_NAME
    efficiency_report_md = out_dir / DEFAULT_EFFICIENCY_REPORT_MD_NAME
    efficiency_report["outputs"] = {
        "efficiency_report_json": efficiency_report_json.as_posix(),
        "efficiency_report_markdown": efficiency_report_md.as_posix(),
    }
    write_json(efficiency_report_json, efficiency_report)
    write_markdown(efficiency_report_md, markdown_efficiency_report(efficiency_report).splitlines())

    efficiency_gate = evaluate_efficiency_gate(efficiency_report, policy=efficiency_gate_policy)
    efficiency_gate_json = out_dir / DEFAULT_EFFICIENCY_GATE_JSON_NAME
    efficiency_gate_md = out_dir / DEFAULT_EFFICIENCY_GATE_MD_NAME
    efficiency_gate["outputs"] = {
        "efficiency_gate_json": efficiency_gate_json.as_posix(),
        "efficiency_gate_markdown": efficiency_gate_md.as_posix(),
    }
    write_json(efficiency_gate_json, efficiency_gate)
    write_markdown(efficiency_gate_md, markdown_efficiency_gate(efficiency_gate).splitlines())

    decision = _decision(
        workflow_run=workflow_run,
        efficiency_report=efficiency_report,
        efficiency_gate=efficiency_gate,
    )
    ok = bool(decision.get("continue_agent"))
    status = "fail_agent_ci"
    if ok:
        status = "warn_agent_ci" if decision.get("action") == "continue_with_caution" else "pass_agent_ci"

    agent_ci_json = out_dir / DEFAULT_AGENT_CI_JSON_NAME
    agent_ci_md = out_dir / DEFAULT_AGENT_CI_MD_NAME
    outputs = {
        "agent_ci_json": agent_ci_json.as_posix(),
        "agent_ci_markdown": agent_ci_md.as_posix(),
        "workflow_run_json": str(workflow_run.get("outputs", {}).get("workflow_run_json") or ""),
        "workflow_run_markdown": str(workflow_run.get("outputs", {}).get("workflow_run_markdown") or ""),
        "efficiency_report_json": efficiency_report_json.as_posix(),
        "efficiency_report_markdown": efficiency_report_md.as_posix(),
        "efficiency_gate_json": efficiency_gate_json.as_posix(),
        "efficiency_gate_markdown": efficiency_gate_md.as_posix(),
    }
    result: dict[str, Any] = {
        "schema_version": AGENT_CI_SCHEMA_VERSION,
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
        "workflow_run_summary": _workflow_summary(workflow_run),
        "efficiency_report_summary": _report_summary(efficiency_report),
        "efficiency_gate_summary": _gate_summary(efficiency_gate),
        "next_reads": _next_reads(
            agent_ci_json=agent_ci_json.as_posix(),
            efficiency_report_json=efficiency_report_json.as_posix(),
            efficiency_gate_json=efficiency_gate_json.as_posix(),
            workflow_run=workflow_run,
            decision=decision,
        ),
        "outputs": outputs,
        "safety_boundaries": {
            "authority_effect": "none",
            "no_apply": True,
            "mutation_allowed": False,
            "writes_only_output_dir": True,
            "external_model_calls": False,
            "live_runtime_or_broker_mutation": False,
            "source_or_authority_mutation": False,
        },
    }
    prompt_text = _render_prompt_text(result) if include_prompt else ""
    result["prompt_text"] = prompt_text
    result["prompt_estimated_tokens"] = estimate_tokens(prompt_text) if prompt_text else 0
    result["json_estimated_tokens"] = estimate_tokens(json.dumps(result, ensure_ascii=True, sort_keys=True))
    write_json(agent_ci_json, result)
    write_markdown(agent_ci_md, markdown_agent_ci(result).splitlines())
    return result


def markdown_agent_ci(result: Mapping[str, Any]) -> str:
    decision = result.get("decision") if isinstance(result.get("decision"), Mapping) else {}
    report = result.get("efficiency_report_summary") if isinstance(result.get("efficiency_report_summary"), Mapping) else {}
    gate = result.get("efficiency_gate_summary") if isinstance(result.get("efficiency_gate_summary"), Mapping) else {}
    lines = [
        "# Deep Context Federation Agent CI",
        "",
        f"- Status: `{result.get('status')}`",
        f"- OK: `{result.get('ok')}`",
        f"- Decision: `{decision.get('action')}`",
        f"- Continue agent: `{decision.get('continue_agent')}`",
        f"- Task: `{result.get('task')}`",
        f"- Read-first tokens: `{report.get('read_first_estimated_tokens')}`",
        f"- Baseline tokens: `{report.get('effective_baseline_estimated_tokens')}`",
        f"- Read-first savings: `{report.get('read_first_savings_percent')}`%",
        f"- Efficiency gate errors: `{gate.get('error_count')}`",
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
    lines.extend(["", "## Next Reads", ""])
    reads = result.get("next_reads") if isinstance(result.get("next_reads"), Mapping) else {}
    for key in ("read_first", "read_next_if_decision_allows", "skip_by_default"):
        lines.append(f"### {key}")
        values = reads.get(key) if isinstance(reads.get(key), list) else []
        if values:
            for item in values:
                lines.append(f"- `{item}`")
        else:
            lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"
