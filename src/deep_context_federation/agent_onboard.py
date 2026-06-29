"""One-command DCF onboarding capsule for global agent wrappers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from deep_context_federation.agent_profile import load_agent_profile
from deep_context_federation.agent_profile_init import build_agent_profile_init
from deep_context_federation.agent_ready import build_agent_ready
from deep_context_federation.agent_ready import markdown_agent_ready
from deep_context_federation.builder import utc_now
from deep_context_federation.efficiency_gate import load_efficiency_gate_policy
from deep_context_federation.quality_gate import load_quality_gate_policy
from deep_context_federation.target_review_gate import load_target_review_gate_policy
from deep_context_federation.agent_context_gate import load_agent_context_gate_policy

AGENT_ONBOARD_SCHEMA_VERSION = "deep_context_federation_agent_onboard_v1"


def _profile_path(normalized: Mapping[str, Any], key: str) -> Path | None:
    value = str(normalized.get(key) or "").strip()
    return Path(value) if value else None


def _profile_path_list(normalized: Mapping[str, Any], key: str) -> list[Path]:
    values = normalized.get(key)
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return []
    return [Path(str(value)) for value in values if str(value).strip()]


def _summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": payload.get("schema_version"),
        "ok": payload.get("ok"),
        "status": payload.get("status"),
        "summary": dict(payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}),
    }


def _ready_args_from_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    normalized = profile.get("normalized") if isinstance(profile.get("normalized"), Mapping) else {}
    return {
        "root": _profile_path(normalized, "root") or Path.cwd(),
        "output_dir": _profile_path(normalized, "output_dir") or Path(".dcf"),
        "manifests": _profile_path_list(normalized, "manifests"),
        "task": str(normalized.get("task") or ""),
        "targets": list(normalized.get("targets") or []),
        "handoff_path": _profile_path(normalized, "handoff"),
        "quality_policy_path": _profile_path(normalized, "quality_policy"),
        "target_review_policy_path": _profile_path(normalized, "target_review_policy"),
        "efficiency_policy_path": _profile_path(normalized, "efficiency_policy"),
        "context_gate_policy_path": _profile_path(normalized, "context_gate_policy"),
        "workflow_token_budget": int(normalized.get("workflow_token_budget") or 4000),
        "context_token_budget": int(normalized.get("context_token_budget") or 4000),
        "context_mode": str(normalized.get("context_mode") or "read-first"),
        "max_artifact_tokens": int(normalized.get("max_artifact_tokens") or 1200),
        "query_limit": int(normalized.get("query_limit") or 10),
        "max_presets": int(normalized.get("max_presets") or 3),
        "max_rows": int(normalized.get("max_rows") or 80),
        "max_files": int(normalized.get("max_files") or 5000),
        "max_parse_bytes": int(normalized.get("max_parse_bytes") or 1_000_000),
        "include_hashes": bool(normalized.get("hash_files")),
        "include_codebase_memory": bool(normalized.get("include_memory_import") or normalized.get("include_codebase_memory")),
        "codebase_memory_cache_dir": _profile_path(normalized, "memory_import_cache_dir") or _profile_path(normalized, "codebase_memory_cache_dir"),
        "include_content": bool(normalized.get("include_content")) if "include_content" in normalized else True,
        "include_prompt": bool(normalized.get("include_prompt")) if "include_prompt" in normalized else True,
        "include_details": bool(normalized.get("include_details")),
        "extra_baselines": _profile_path_list(normalized, "baselines"),
    }


def _failure(
    *,
    root: Path,
    profile_path: Path,
    profile_init: Mapping[str, Any],
    profile: Mapping[str, Any],
    errors: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": AGENT_ONBOARD_SCHEMA_VERSION,
        "ok": False,
        "status": "fail_agent_onboard",
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": utc_now(),
        "root": root.expanduser().resolve().as_posix(),
        "profile_path": profile_path.expanduser().resolve().as_posix(),
        "profile_init_summary": _summary(profile_init),
        "profile_validation_summary": _summary(profile),
        "agent_ready_summary": {},
        "model_input_ready": False,
        "prompt_source": "",
        "prompt_estimated_tokens": 0,
        "recommended_next_command": "",
        "errors": [dict(row) for row in errors],
        "outputs": {},
        "safety_boundaries": {
            "authority_effect": "none",
            "no_apply": True,
            "mutation_allowed": False,
            "writes_generated_outputs_only": True,
            "external_model_calls": False,
            "source_or_authority_mutation": False,
            "prompt_emitted_only_after_model_input_pass": True,
        },
    }


def build_agent_onboard(
    *,
    root: Path,
    profile_path: Path,
    task: str,
    targets: Sequence[str] = (),
    manifests: Sequence[Path] = (),
    handoff_path: Path | None = None,
    quality_policy_path: Path | None = None,
    target_review_policy_path: Path | None = None,
    efficiency_policy_path: Path | None = None,
    context_gate_policy_path: Path | None = None,
    profile_id: str = "",
    description: str = "",
    output_dir: Path | None = None,
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
    """Generate a profile and immediately run the fail-closed agent-ready path."""

    profile_init = build_agent_profile_init(
        root=root,
        profile_path=profile_path,
        profile_id=profile_id,
        description=description,
        task=task,
        targets=targets,
        manifests=manifests,
        handoff_path=handoff_path,
        output_dir=output_dir,
        quality_policy_path=quality_policy_path,
        target_review_policy_path=target_review_policy_path,
        efficiency_policy_path=efficiency_policy_path,
        context_gate_policy_path=context_gate_policy_path,
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
        include_details=include_details,
        include_content=include_content,
        include_prompt=include_prompt,
        extra_baselines=extra_baselines,
        write=True,
    )
    resolved_root = root.expanduser().resolve()
    resolved_profile_path = profile_path.expanduser()
    if not resolved_profile_path.is_absolute():
        resolved_profile_path = resolved_root / resolved_profile_path
    resolved_profile_path = resolved_profile_path.resolve()
    if profile_init.get("ok") is not True:
        return _failure(
            root=resolved_root,
            profile_path=resolved_profile_path,
            profile_init=profile_init,
            profile={},
            errors=[{"id": "profile_init_failed", "status": profile_init.get("status"), "errors": list(profile_init.get("errors") or [])}],
        )
    profile = load_agent_profile(resolved_profile_path)
    if profile.get("ok") is not True:
        return _failure(
            root=resolved_root,
            profile_path=resolved_profile_path,
            profile_init=profile_init,
            profile=profile,
            errors=[{"id": "profile_validation_failed", "status": profile.get("status"), "errors": list(profile.get("errors") or [])}],
        )
    ready_args = _ready_args_from_profile(profile)
    quality_policy = load_quality_gate_policy(ready_args["quality_policy_path"]) if ready_args["quality_policy_path"] else None
    target_policy = load_target_review_gate_policy(ready_args["target_review_policy_path"]) if ready_args["target_review_policy_path"] else None
    efficiency_policy = load_efficiency_gate_policy(ready_args["efficiency_policy_path"]) if ready_args["efficiency_policy_path"] else None
    context_gate_policy = load_agent_context_gate_policy(ready_args["context_gate_policy_path"]) if ready_args["context_gate_policy_path"] else None
    agent_ready = build_agent_ready(
        root=ready_args["root"],
        output_dir=ready_args["output_dir"],
        manifests=ready_args["manifests"],
        task=ready_args["task"],
        targets=ready_args["targets"],
        handoff_path=ready_args["handoff_path"],
        quality_gate_policy=quality_policy,
        target_review_gate_policy=target_policy,
        efficiency_gate_policy=efficiency_policy,
        agent_context_gate_policy=context_gate_policy,
        quality_policy_path=ready_args["quality_policy_path"],
        target_review_policy_path=ready_args["target_review_policy_path"],
        workflow_token_budget=ready_args["workflow_token_budget"],
        context_token_budget=ready_args["context_token_budget"],
        context_mode=ready_args["context_mode"],
        max_artifact_tokens=ready_args["max_artifact_tokens"],
        query_limit=ready_args["query_limit"],
        max_presets=ready_args["max_presets"],
        max_rows=ready_args["max_rows"],
        max_files=ready_args["max_files"],
        max_parse_bytes=ready_args["max_parse_bytes"],
        include_hashes=ready_args["include_hashes"],
        include_codebase_memory=ready_args["include_codebase_memory"],
        codebase_memory_cache_dir=ready_args["codebase_memory_cache_dir"],
        include_content=ready_args["include_content"],
        include_prompt=ready_args["include_prompt"],
        include_details=ready_args["include_details"],
        extra_baselines=ready_args["extra_baselines"],
    )
    agent_ready["agent_profile_summary"] = {
        "schema_version": profile.get("schema_version"),
        "ok": profile.get("ok"),
        "status": profile.get("status"),
        "profile_path": profile.get("profile_path"),
        "profile_id": profile.get("profile_id"),
        "summary": dict(profile.get("summary") if isinstance(profile.get("summary"), Mapping) else {}),
    }
    ready_outputs = dict(agent_ready.get("outputs") if isinstance(agent_ready.get("outputs"), Mapping) else {})
    outputs = {"agent_profile_json": resolved_profile_path.as_posix(), **ready_outputs}
    ok = agent_ready.get("ok") is True
    return {
        "schema_version": AGENT_ONBOARD_SCHEMA_VERSION,
        "ok": ok,
        "status": "pass_agent_onboard" if ok else "fail_agent_onboard",
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": utc_now(),
        "root": ready_args["root"].expanduser().resolve().as_posix(),
        "profile_path": resolved_profile_path.as_posix(),
        "profile_init_summary": _summary(profile_init),
        "profile_validation_summary": _summary(profile),
        "agent_ready_summary": _summary(agent_ready),
        "model_input_ready": ok,
        "prompt_source": agent_ready.get("prompt_source") if ok else "",
        "prompt_estimated_tokens": agent_ready.get("prompt_estimated_tokens") if ok else 0,
        "recommended_next_command": f"dcf agent-ready --profile '{resolved_profile_path.as_posix()}' --format prompt",
        "agent_ready": agent_ready,
        "errors": list(agent_ready.get("errors") or []),
        "outputs": outputs,
        "safety_boundaries": {
            "authority_effect": "none",
            "no_apply": True,
            "mutation_allowed": False,
            "writes_generated_outputs_only": True,
            "external_model_calls": False,
            "source_or_authority_mutation": False,
            "prompt_emitted_only_after_model_input_pass": True,
        },
    }


def markdown_agent_onboard(result: Mapping[str, Any]) -> str:
    ready = result.get("agent_ready") if isinstance(result.get("agent_ready"), Mapping) else {}
    lines = [
        "# Deep Context Federation Agent Onboard",
        "",
        f"- Status: `{result.get('status')}`",
        f"- OK: `{result.get('ok')}`",
        f"- Profile: `{result.get('profile_path')}`",
        f"- Prompt source: `{result.get('prompt_source')}`",
        f"- Prompt tokens: `{result.get('prompt_estimated_tokens')}`",
        f"- Recommended next command: `{result.get('recommended_next_command')}`",
        "",
    ]
    if ready:
        lines.extend(["## Agent Ready", "", markdown_agent_ready(ready).rstrip(), ""])
    lines.extend(["## Errors", ""])
    errors = [row for row in result.get("errors") or [] if isinstance(row, Mapping)]
    if errors:
        for row in errors:
            lines.append(f"- `{row.get('id')}` detail=`{row}`")
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"
