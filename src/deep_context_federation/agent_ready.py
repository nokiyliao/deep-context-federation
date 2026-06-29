"""Fail-closed DCF prompt readiness pipeline for global agent wrappers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from deep_context_federation.agent_handoff import build_agent_handoff
from deep_context_federation.agent_model_input import build_agent_model_input
from deep_context_federation.agent_route import route_agent_context
from deep_context_federation.builder import read_json
from deep_context_federation.builder import utc_now
from deep_context_federation.input_fingerprint import build_input_fingerprint
from deep_context_federation.input_fingerprint import compare_input_fingerprint

AGENT_READY_SCHEMA_VERSION = "deep_context_federation_agent_ready_v1"


def _summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    return {
        "schema_version": payload.get("schema_version"),
        "status": payload.get("status"),
        "ok": payload.get("ok"),
        "summary": dict(summary),
    }


def _route_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": payload.get("schema_version"),
        "status": payload.get("status"),
        "ok": payload.get("ok"),
        "action": payload.get("action"),
        "discovery_status": payload.get("discovery_status"),
        "model_input_ready": payload.get("model_input_ready"),
        "route_ready": payload.get("route_ready"),
        "recommended_next_command": payload.get("recommended_next_command"),
    }


def _selected_handoff(route: Mapping[str, Any], handoff_path: Path | None) -> str:
    if handoff_path:
        return handoff_path.expanduser().resolve().as_posix()
    discovery_summary = route.get("discovery_summary") if isinstance(route.get("discovery_summary"), Mapping) else {}
    selected = str(discovery_summary.get("selected_handoff") or "")
    if selected:
        return selected
    discovered = route.get("discovered") if isinstance(route.get("discovered"), Mapping) else {}
    handoffs = [str(item) for item in discovered.get("handoffs") or [] if str(item)]
    return handoffs[0] if handoffs else ""


def _manifest_paths(route: Mapping[str, Any], manifests: Sequence[Path]) -> list[Path]:
    if manifests:
        return [path.expanduser().resolve() for path in manifests]
    discovered = route.get("discovered") if isinstance(route.get("discovered"), Mapping) else {}
    return [Path(str(item)).expanduser().resolve() for item in discovered.get("manifests") or [] if str(item)]


def _normalize_targets(targets: Sequence[Any]) -> list[str]:
    return list(dict.fromkeys(str(item).strip() for item in targets if str(item).strip()))


def _request_binding(handoff: Mapping[str, Any], *, task: str, targets: Sequence[str]) -> dict[str, Any]:
    requested_task = str(task or "").strip()
    handoff_task = str(handoff.get("task") or "").strip()
    requested_targets = _normalize_targets(targets)
    handoff_targets_raw = handoff.get("targets") if isinstance(handoff.get("targets"), Sequence) and not isinstance(handoff.get("targets"), (str, bytes)) else []
    handoff_targets = _normalize_targets(handoff_targets_raw)
    checks: list[dict[str, Any]] = []
    if requested_task:
        checks.append(
            {
                "id": "task_matches",
                "passed": requested_task == handoff_task,
                "requested_task": requested_task,
                "handoff_task": handoff_task,
            }
        )
    if requested_targets:
        checks.append(
            {
                "id": "targets_match",
                "passed": requested_targets == handoff_targets,
                "requested_targets": requested_targets,
                "handoff_targets": handoff_targets,
            }
        )
    failed = [row for row in checks if row.get("passed") is not True]
    if not checks:
        status = "not_checked_no_request_binding"
    elif failed:
        status = "fail_request_binding"
    else:
        status = "pass_request_binding"
    return {
        "schema_version": "deep_context_federation_request_binding_v1",
        "ok": not failed,
        "status": status,
        "authority_effect": "none",
        "no_apply": True,
        "requested_task": requested_task,
        "handoff_task": handoff_task,
        "requested_targets": requested_targets,
        "handoff_targets": handoff_targets,
        "checks": checks,
        "errors": failed,
    }


def _failure(
    *,
    root: Path,
    task: str,
    targets: Sequence[str],
    route: Mapping[str, Any],
    action_taken: str,
    errors: Sequence[Mapping[str, Any]],
    input_freshness: Mapping[str, Any] | None = None,
    request_binding: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": AGENT_READY_SCHEMA_VERSION,
        "ok": False,
        "status": "fail_agent_ready",
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": utc_now(),
        "root": root.as_posix(),
        "task": task,
        "targets": list(targets),
        "action_taken": action_taken,
        "route_summary": _route_summary(route),
        "handoff_summary": {},
        "model_input_summary": {},
        "input_freshness": dict(input_freshness or {}),
        "request_binding": dict(request_binding or {}),
        "prompt_source": "",
        "prompt_format": "",
        "prompt_estimated_tokens": 0,
        "prompt_text": "",
        "errors": [dict(row) for row in errors],
        "outputs": {},
        "safety_boundaries": {
            "authority_effect": "none",
            "no_apply": True,
            "mutation_allowed": False,
            "writes_only_output_dir": True,
            "external_model_calls": False,
            "source_or_authority_mutation": False,
            "prompt_emitted_only_after_model_input_pass": True,
        },
    }


def build_agent_ready(
    *,
    root: Path,
    output_dir: Path,
    task: str = "",
    targets: Sequence[str] = (),
    handoff_path: Path | None = None,
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
    """Return a model-ready prompt artifact when existing gates permit it."""

    root = root.expanduser().resolve()
    task_text = str(task or "").strip()
    out_dir = output_dir.expanduser()
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    out_dir = out_dir.resolve()
    route = route_agent_context(root=root, task=task_text, targets=targets, handoff_path=handoff_path, output_dir=out_dir)
    route_status = str(route.get("status") or "")
    handoff: dict[str, Any] = {}
    action_taken = "none"
    input_freshness: dict[str, Any] = {}
    request_binding: dict[str, Any] = {}

    if route_status == "ready_agent_route":
        action_taken = "read_existing_handoff"
        selected = _selected_handoff(route, handoff_path)
        handoff = read_json(Path(selected)) if selected else {}
        handoff_ref = Path(selected) if selected else None
        if not handoff or handoff_ref is None:
            return _failure(
                root=root,
                task=task_text,
                targets=targets,
                route=route,
                action_taken=action_taken,
                errors=[{"id": "handoff_unreadable", "path": selected}],
            )
        current_manifests = _manifest_paths(route, manifests)
        previous_fingerprint = handoff.get("input_fingerprint") if isinstance(handoff.get("input_fingerprint"), Mapping) else {}
        if current_manifests and previous_fingerprint:
            current_fingerprint = build_input_fingerprint(root=root, manifests=current_manifests)
            input_freshness = compare_input_fingerprint(previous_fingerprint, current_fingerprint)
            input_freshness["current_fingerprint"] = current_fingerprint
            if input_freshness.get("matches") is not True:
                return _failure(
                    root=root,
                    task=task_text,
                    targets=targets,
                    route=route,
                    action_taken=action_taken,
                    input_freshness=input_freshness,
                    errors=[{"id": "input_fingerprint_mismatch", "status": input_freshness.get("status")}],
                )
        elif current_manifests and not previous_fingerprint:
            current_fingerprint = build_input_fingerprint(root=root, manifests=current_manifests)
            input_freshness = {
                "schema_version": "deep_context_federation_input_fingerprint_compare_v1",
                "ok": False,
                "status": "fail_input_fingerprint_compare",
                "authority_effect": "none",
                "no_apply": True,
                "comparable": False,
                "matches": False,
                "reason": "previous_input_fingerprint_missing",
                "current_fingerprint": current_fingerprint,
            }
            return _failure(
                root=root,
                task=task_text,
                targets=targets,
                route=route,
                action_taken=action_taken,
                input_freshness=input_freshness,
                errors=[{"id": "input_fingerprint_missing"}],
            )
        else:
            input_freshness = {
                "schema_version": "deep_context_federation_input_fingerprint_compare_v1",
                "ok": True,
                "status": "not_checked_no_current_manifest",
                "authority_effect": "none",
                "no_apply": True,
                "comparable": False,
                "matches": None,
            }
        request_binding = _request_binding(handoff, task=task_text, targets=targets)
        if request_binding.get("ok") is not True:
            return _failure(
                root=root,
                task=task_text,
                targets=targets,
                route=route,
                action_taken=action_taken,
                input_freshness=input_freshness,
                request_binding=request_binding,
                errors=[{"id": "request_binding_mismatch", "status": request_binding.get("status")}],
            )
    elif route_status == "needs_agent_handoff" or manifests:
        action_taken = "build_agent_handoff"
        manifest_paths = _manifest_paths(route, manifests)
        if not task_text:
            return _failure(
                root=root,
                task=task_text,
                targets=targets,
                route=route,
                action_taken=action_taken,
                errors=[{"id": "task_required"}],
            )
        if not manifest_paths:
            return _failure(
                root=root,
                task=task_text,
                targets=targets,
                route=route,
                action_taken=action_taken,
                errors=[{"id": "manifest_required"}],
            )
        handoff = build_agent_handoff(
            root=root,
            output_dir=out_dir,
            manifests=manifest_paths,
            task=task_text,
            targets=targets,
            quality_gate_policy=quality_gate_policy,
            target_review_gate_policy=target_review_gate_policy,
            efficiency_gate_policy=efficiency_gate_policy,
            agent_context_gate_policy=agent_context_gate_policy,
            quality_policy_path=quality_policy_path,
            target_review_policy_path=target_review_policy_path,
            workflow_token_budget=workflow_token_budget,
            context_token_budget=context_token_budget,
            context_mode=context_mode,
            max_artifact_tokens=max_artifact_tokens,
            query_limit=query_limit,
            max_presets=max_presets,
            max_rows=max_rows,
            max_files=max_files,
            max_parse_bytes=max_parse_bytes,
            include_hashes=include_hashes,
            include_codebase_memory=include_codebase_memory,
            codebase_memory_cache_dir=codebase_memory_cache_dir,
            include_content=include_content,
            include_prompt=True,
            include_details=include_details,
            extra_baselines=extra_baselines,
        )
        handoff_ref = Path(str(handoff.get("outputs", {}).get("agent_handoff_json") or ""))
        input_freshness = {
            "schema_version": "deep_context_federation_input_fingerprint_compare_v1",
            "ok": True,
            "status": "freshly_built",
            "authority_effect": "none",
            "no_apply": True,
            "comparable": True,
            "matches": True,
            "current_digest": handoff.get("input_fingerprint", {}).get("digest") if isinstance(handoff.get("input_fingerprint"), Mapping) else "",
        }
        request_binding = {
            "schema_version": "deep_context_federation_request_binding_v1",
            "ok": True,
            "status": "freshly_built",
            "authority_effect": "none",
            "no_apply": True,
            "requested_task": task_text,
            "handoff_task": handoff.get("task"),
            "requested_targets": _normalize_targets(targets),
            "handoff_targets": _normalize_targets(handoff.get("targets") if isinstance(handoff.get("targets"), Sequence) and not isinstance(handoff.get("targets"), (str, bytes)) else []),
            "checks": [],
            "errors": [],
        }
    elif route_status == "needs_task_agent_route":
        return _failure(
            root=root,
            task=task_text,
            targets=targets,
            route=route,
            action_taken="blocked_by_route",
            errors=[{"id": "task_required"}],
        )
    else:
        return _failure(
            root=root,
            task=task_text,
            targets=targets,
            route=route,
            action_taken="blocked_by_route",
            errors=[{"id": "route_not_ready", "status": route_status, "action": route.get("action")}],
        )

    model_input = build_agent_model_input(handoff, handoff_path=handoff_ref, include_prompt=include_prompt)
    ok = model_input.get("ok") is True
    return {
        "schema_version": AGENT_READY_SCHEMA_VERSION,
        "ok": ok,
        "status": "pass_agent_ready" if ok else "fail_agent_ready",
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": utc_now(),
        "root": root.as_posix(),
        "task": task_text,
        "targets": list(targets),
        "action_taken": action_taken,
        "route_summary": _route_summary(route),
        "handoff_summary": {
            "schema_version": handoff.get("schema_version"),
            "status": handoff.get("status"),
            "ok": handoff.get("ok"),
            "decision": handoff.get("decision") if isinstance(handoff.get("decision"), Mapping) else {},
        },
        "input_freshness": input_freshness,
        "request_binding": request_binding,
        "model_input_summary": _summary(model_input),
        "prompt_source": model_input.get("prompt_source") if ok else "",
        "prompt_format": model_input.get("prompt_format") if ok else "",
        "prompt_estimated_tokens": model_input.get("prompt_estimated_tokens") if ok else 0,
        "prompt_text": model_input.get("prompt_text") if ok else "",
        "token_economics": model_input.get("token_economics") if isinstance(model_input.get("token_economics"), Mapping) else {},
        "errors": list(model_input.get("errors") or []),
        "outputs": dict(handoff.get("outputs") if isinstance(handoff.get("outputs"), Mapping) else {}),
        "safety_boundaries": {
            "authority_effect": "none",
            "no_apply": True,
            "mutation_allowed": False,
            "writes_only_output_dir": True,
            "external_model_calls": False,
            "source_or_authority_mutation": False,
            "prompt_emitted_only_after_model_input_pass": True,
        },
    }


def markdown_agent_ready(result: Mapping[str, Any]) -> str:
    route = result.get("route_summary") if isinstance(result.get("route_summary"), Mapping) else {}
    binding = result.get("request_binding") if isinstance(result.get("request_binding"), Mapping) else {}
    lines = [
        "# Deep Context Federation Agent Ready",
        "",
        f"- Status: `{result.get('status')}`",
        f"- OK: `{result.get('ok')}`",
        f"- Action taken: `{result.get('action_taken')}`",
        f"- Route status: `{route.get('status')}`",
        f"- Request binding: `{binding.get('status')}`",
        f"- Prompt source: `{result.get('prompt_source')}`",
        f"- Prompt tokens: `{result.get('prompt_estimated_tokens')}`",
        "",
        "## Errors",
        "",
    ]
    errors = [row for row in result.get("errors") or [] if isinstance(row, Mapping)]
    if errors:
        for row in errors:
            lines.append(f"- `{row.get('id')}` detail=`{row}`")
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"
