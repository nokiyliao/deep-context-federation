"""Read-only DCF workflow runner."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from deep_context_federation.builder import read_json
from deep_context_federation.builder import utc_now
from deep_context_federation.builder import write_json
from deep_context_federation.builder import write_markdown
from deep_context_federation.context_pack import estimate_tokens
from deep_context_federation.intake import build_agent_intake
from deep_context_federation.resolve import resolve_target
from deep_context_federation.target_review import review_targets
from deep_context_federation.target_review_gate import evaluate_target_review_gate
from deep_context_federation.workflow_plan import DEFAULT_TARGET_REVIEW_GATE_JSON_NAME
from deep_context_federation.workflow_plan import DEFAULT_TARGET_REVIEW_JSON_NAME
from deep_context_federation.workflow_plan import DEFAULT_WORKFLOW_PLAN_JSON_NAME
from deep_context_federation.workflow_plan import build_workflow_plan

WORKFLOW_RUN_SCHEMA_VERSION = "deep_context_federation_workflow_run_v1"
DEFAULT_WORKFLOW_RUN_JSON_NAME = "deep_context_federation_workflow_run.json"
DEFAULT_WORKFLOW_RUN_MD_NAME = "DEEP_CONTEXT_FEDERATION_WORKFLOW_RUN.md"
DEFAULT_AGENT_INTAKE_CONTRACT_JSON_NAME = "deep_context_federation_agent_intake_contract_validation.json"
DEFAULT_PRIORITY_RESOLVE_JSON_NAME = "deep_context_federation_priority_resolve.json"


def _normalize_output_dir(root: Path, output_dir: Path) -> Path:
    root = root.expanduser().resolve()
    output_dir = output_dir.expanduser()
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    return output_dir.resolve()


def _row(
    *,
    step_id: str,
    status: str,
    ok: bool | None,
    artifact_ref: str = "",
    summary: Mapping[str, Any] | None = None,
    skipped_reason: str = "",
) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "status": status,
        "ok": ok,
        "artifact_ref": artifact_ref,
        "summary": dict(summary or {}),
        "skipped_reason": skipped_reason,
        "authority_effect": "none",
        "no_apply": True,
    }


def _plan_summary(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": plan.get("status"),
        "target_count": plan.get("target_count"),
        "step_count": len(plan.get("steps") or []),
        "gate_count": len(plan.get("gates") or []),
        "json_estimated_tokens": plan.get("json_estimated_tokens"),
        "prompt_estimated_tokens": plan.get("prompt_estimated_tokens"),
    }


def _intake_summary(intake: Mapping[str, Any]) -> dict[str, Any]:
    quality = intake.get("quality_gate_summary") if isinstance(intake.get("quality_gate_summary"), Mapping) else {}
    brief = intake.get("task_brief_summary") if isinstance(intake.get("task_brief_summary"), Mapping) else {}
    budget = brief.get("context_budget") if isinstance(brief.get("context_budget"), Mapping) else {}
    return {
        "status": intake.get("status"),
        "quality_gate_status": quality.get("status"),
        "quality_gate_error_count": quality.get("error_count"),
        "task_brief_status": brief.get("status"),
        "context_pack_estimated_tokens": budget.get("context_pack_estimated_tokens"),
        "estimated_token_savings": budget.get("estimated_token_savings"),
    }


def _contract_summary(validation: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": validation.get("status"),
        "artifact_kind": validation.get("artifact_kind"),
        "error_count": validation.get("error_count"),
    }


def _target_review_summary(review: Mapping[str, Any]) -> dict[str, Any]:
    summary = review.get("summary") if isinstance(review.get("summary"), Mapping) else {}
    return {
        "status": review.get("status"),
        "target_count": review.get("target_count"),
        "reviewed_count": review.get("reviewed_count"),
        "verdict_counts": summary.get("verdict_counts"),
        "max_priority_score": summary.get("max_priority_score"),
        "average_confidence": summary.get("average_confidence"),
    }


def _gate_summary(gate: Mapping[str, Any]) -> dict[str, Any]:
    summary = gate.get("summary") if isinstance(gate.get("summary"), Mapping) else {}
    return {
        "status": gate.get("status"),
        "error_count": gate.get("error_count"),
        "failed_check_count": summary.get("failed_check_count"),
        "passed_check_count": summary.get("passed_check_count"),
    }


def _priority_target(review: Mapping[str, Any]) -> str:
    priority = review.get("priority_order") if isinstance(review.get("priority_order"), list) else []
    for row in priority:
        if isinstance(row, Mapping) and row.get("target"):
            return str(row["target"])
    return ""


def _resolve_summary(resolve: Mapping[str, Any]) -> dict[str, Any]:
    summary = resolve.get("summary") if isinstance(resolve.get("summary"), Mapping) else {}
    return {
        "status": resolve.get("status"),
        "target": resolve.get("target"),
        "matched_entity_count": summary.get("matched_entity_count"),
        "related_source_count": summary.get("related_source_count"),
        "related_conflict_count": summary.get("related_conflict_count"),
        "prompt_estimated_tokens": resolve.get("prompt_estimated_tokens"),
    }


def _run_status(step_results: Sequence[Mapping[str, Any]], *, has_targets: bool) -> tuple[bool, str]:
    failed = [row for row in step_results if row.get("ok") is False]
    if failed:
        return False, "fail_workflow_run"
    if not has_targets:
        return True, "warn_workflow_run"
    return True, "pass_workflow_run"


def _render_prompt_text(result: Mapping[str, Any]) -> str:
    lines = [
        "# Deep Context Federation Workflow Run",
        "",
        "Boundary: authority_effect=none; no_apply=true; generated artifacts only.",
        f"Status: {result.get('status')}",
        f"Task: {result.get('task')}",
        "",
        "## Step Results",
    ]
    for row in result.get("step_results") or []:
        if isinstance(row, Mapping):
            lines.append(
                "- {step_id}: status={status} ok={ok} artifact={artifact}".format(
                    step_id=row.get("step_id"),
                    status=row.get("status"),
                    ok=row.get("ok"),
                    artifact=row.get("artifact_ref") or "none",
                )
            )
    compact = result.get("model_handoff") if isinstance(result.get("model_handoff"), Mapping) else {}
    lines.extend(["", "## Model Handoff"])
    for key in ("read_first", "read_next_if_gate_passes", "skip_by_default"):
        values = compact.get(key) if isinstance(compact.get(key), list) else []
        lines.append(f"- {key}: {', '.join(str(item) for item in values) if values else 'none'}")
    return "\n".join(lines).rstrip() + "\n"


def build_workflow_run(
    *,
    root: Path,
    output_dir: Path,
    task: str,
    targets: Sequence[str] = (),
    manifests: Sequence[Path] = (),
    quality_gate_policy: Mapping[str, Any] | None = None,
    target_review_gate_policy: Mapping[str, Any] | None = None,
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
) -> dict[str, Any]:
    """Execute the DCF read-only workflow and return one compact run capsule."""

    started = time.perf_counter()
    root = root.expanduser().resolve()
    out_dir = _normalize_output_dir(root, output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    clean_targets = list(dict.fromkeys(str(item).strip() for item in targets if str(item).strip()))

    plan = build_workflow_plan(
        task=task,
        root=root,
        output_dir=out_dir,
        targets=clean_targets,
        quality_policy=quality_policy_path,
        target_review_policy=target_review_policy_path,
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
    )
    plan_json = out_dir / DEFAULT_WORKFLOW_PLAN_JSON_NAME
    write_json(plan_json, plan)

    step_results: list[dict[str, Any]] = [
        _row(
            step_id="00_workflow_plan",
            status=str(plan.get("status") or ""),
            ok=True,
            artifact_ref=plan_json.as_posix(),
            summary=_plan_summary(plan),
        )
    ]

    intake = build_agent_intake(
        root=root,
        output_dir=out_dir,
        manifests=manifests,
        task=task,
        quality_gate_policy=quality_gate_policy,
        max_files=max_files,
        max_parse_bytes=max_parse_bytes,
        include_hashes=include_hashes,
        include_codebase_memory=include_codebase_memory,
        codebase_memory_cache_dir=codebase_memory_cache_dir,
        token_budget=token_budget,
        query_limit=query_limit,
        max_presets=max_presets,
        max_rows=max_rows,
        include_prompt=include_prompt,
        write=True,
    )
    intake_path = str((intake.get("outputs") or {}).get("agent_intake_json") or "")
    step_results.append(
        _row(
            step_id="01_agent_intake",
            status=str(intake.get("status") or ""),
            ok=bool(intake.get("ok")),
            artifact_ref=intake_path,
            summary=_intake_summary(intake),
        )
    )

    from deep_context_federation.schemas import validate_artifact_contract

    intake_contract = validate_artifact_contract(intake, artifact_kind="agent_intake")
    intake_contract_path = out_dir / DEFAULT_AGENT_INTAKE_CONTRACT_JSON_NAME
    write_json(intake_contract_path, intake_contract)
    step_results.append(
        _row(
            step_id="02_validate_intake_contract",
            status=str(intake_contract.get("status") or ""),
            ok=bool(intake_contract.get("ok")),
            artifact_ref=intake_contract_path.as_posix(),
            summary=_contract_summary(intake_contract),
        )
    )

    review: dict[str, Any] | None = None
    review_gate: dict[str, Any] | None = None
    priority_resolve: dict[str, Any] | None = None
    target_review_path = out_dir / DEFAULT_TARGET_REVIEW_JSON_NAME
    target_review_gate_path = out_dir / DEFAULT_TARGET_REVIEW_GATE_JSON_NAME
    priority_resolve_path = out_dir / DEFAULT_PRIORITY_RESOLVE_JSON_NAME

    if clean_targets and intake.get("ok") and intake_contract.get("ok"):
        outputs = intake.get("outputs") if isinstance(intake.get("outputs"), Mapping) else {}
        federation_path = Path(str(outputs.get("federation_json") or ""))
        federation = read_json(federation_path)
        review = review_targets(
            federation,
            targets=clean_targets,
            token_budget=token_budget,
            include_details=include_details,
            include_prompt=include_prompt,
        )
        write_json(target_review_path, review)
        step_results.append(
            _row(
                step_id="03_review_targets",
                status=str(review.get("status") or ""),
                ok=True,
                artifact_ref=target_review_path.as_posix(),
                summary=_target_review_summary(review),
            )
        )

        review_gate = evaluate_target_review_gate(review, policy=target_review_gate_policy)
        write_json(target_review_gate_path, review_gate)
        step_results.append(
            _row(
                step_id="04_review_gate",
                status=str(review_gate.get("status") or ""),
                ok=bool(review_gate.get("ok")),
                artifact_ref=target_review_gate_path.as_posix(),
                summary=_gate_summary(review_gate),
            )
        )

        priority = _priority_target(review)
        if review_gate.get("ok") and priority:
            priority_resolve = resolve_target(
                federation,
                target=priority,
                token_budget=max(500, int(token_budget) // 2),
                include_prompt=include_prompt,
            )
            write_json(priority_resolve_path, priority_resolve)
            step_results.append(
                _row(
                    step_id="05_priority_resolve",
                    status=str(priority_resolve.get("status") or ""),
                    ok=priority_resolve.get("status") in {"matched", "warn"},
                    artifact_ref=priority_resolve_path.as_posix(),
                    summary=_resolve_summary(priority_resolve),
                )
            )
        else:
            step_results.append(
                _row(
                    step_id="05_priority_resolve",
                    status="skipped",
                    ok=None,
                    artifact_ref="",
                    skipped_reason="review gate did not pass or no priority target",
                )
            )
    else:
        step_results.append(
            _row(
                step_id="03_review_targets",
                status="skipped",
                ok=None,
                skipped_reason="no targets or earlier required gate failed",
            )
        )

    ok, status = _run_status(step_results, has_targets=bool(clean_targets))
    duration_seconds = round(max(0.0, time.perf_counter() - started), 6)
    outputs = {
        "workflow_run_json": (out_dir / DEFAULT_WORKFLOW_RUN_JSON_NAME).as_posix(),
        "workflow_run_markdown": (out_dir / DEFAULT_WORKFLOW_RUN_MD_NAME).as_posix(),
        "workflow_plan_json": plan_json.as_posix(),
        "agent_intake_json": intake_path,
        "agent_intake_contract_json": intake_contract_path.as_posix(),
        "target_review_json": target_review_path.as_posix() if review else "",
        "target_review_gate_json": target_review_gate_path.as_posix() if review_gate else "",
        "priority_resolve_json": priority_resolve_path.as_posix() if priority_resolve else "",
    }
    model_handoff = {
        "read_first": [
            outputs["workflow_run_json"],
            outputs["workflow_plan_json"],
            outputs["agent_intake_contract_json"],
        ],
        "read_next_if_gate_passes": [
            outputs["target_review_gate_json"],
            outputs["priority_resolve_json"],
        ],
        "skip_by_default": [
            "full repository tree",
            "full federation artifact",
            "full per target adjudication details",
            "raw source files without target match",
        ],
    }
    model_handoff["read_next_if_gate_passes"] = [item for item in model_handoff["read_next_if_gate_passes"] if item]
    result: dict[str, Any] = {
        "schema_version": WORKFLOW_RUN_SCHEMA_VERSION,
        "ok": ok,
        "status": status,
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": utc_now(),
        "duration_seconds": duration_seconds,
        "root": root.as_posix(),
        "output_dir": out_dir.as_posix(),
        "task": task,
        "targets": clean_targets,
        "target_count": len(clean_targets),
        "workflow_plan_summary": _plan_summary(plan),
        "step_results": step_results,
        "model_handoff": model_handoff,
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
    prompt_text = _render_prompt_text(result) if include_prompt else ""
    result["prompt_text"] = prompt_text
    result["prompt_estimated_tokens"] = 0
    if prompt_text:
        result["prompt_estimated_tokens"] = estimate_tokens(prompt_text)
    result["json_estimated_tokens"] = 0
    result["json_estimated_tokens"] = estimate_tokens(json.dumps(result, ensure_ascii=True, sort_keys=True))
    write_json(out_dir / DEFAULT_WORKFLOW_RUN_JSON_NAME, result)
    write_markdown(out_dir / DEFAULT_WORKFLOW_RUN_MD_NAME, markdown_workflow_run(result).splitlines())
    return result


def markdown_workflow_run(result: Mapping[str, Any]) -> str:
    lines = [
        "# Deep Context Federation Workflow Run",
        "",
        f"- Status: `{result.get('status')}`",
        f"- OK: `{result.get('ok')}`",
        f"- Task: `{result.get('task')}`",
        f"- Target count: `{result.get('target_count')}`",
        f"- Duration: `{result.get('duration_seconds')}`s",
        f"- Authority effect: `{result.get('authority_effect')}`",
        f"- No apply: `{result.get('no_apply')}`",
        "",
        "## Step Results",
        "",
    ]
    for row in result.get("step_results") or []:
        if isinstance(row, Mapping):
            lines.append(f"- `{row.get('step_id')}` status=`{row.get('status')}` ok=`{row.get('ok')}`")
            if row.get("artifact_ref"):
                lines.append(f"  - artifact: `{row.get('artifact_ref')}`")
            if row.get("skipped_reason"):
                lines.append(f"  - skipped: {row.get('skipped_reason')}")
    handoff = result.get("model_handoff") if isinstance(result.get("model_handoff"), Mapping) else {}
    lines.extend(["", "## Model Handoff", ""])
    for key in ("read_first", "read_next_if_gate_passes", "skip_by_default"):
        lines.append(f"### {key}")
        values = handoff.get(key) if isinstance(handoff.get(key), list) else []
        if values:
            for item in values:
                lines.append(f"- `{item}`")
        else:
            lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"
