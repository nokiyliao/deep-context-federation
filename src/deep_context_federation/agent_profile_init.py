"""Generate agent-ready profiles for global DCF wrappers."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from deep_context_federation.agent_profile import AGENT_PROFILE_SCHEMA_VERSION
from deep_context_federation.agent_profile import load_agent_profile
from deep_context_federation.builder import utc_now
from deep_context_federation.builder import write_json

AGENT_PROFILE_INIT_SCHEMA_VERSION = "deep_context_federation_agent_profile_init_v1"


def _resolve_from_root(root: Path, value: Path | None) -> Path | None:
    if value is None:
        return None
    path = value.expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _relpath(path: Path, *, base_dir: Path) -> str:
    try:
        return os.path.relpath(path, base_dir)
    except ValueError:
        return path.as_posix()


def _default_manifests(root: Path) -> list[Path]:
    candidates = [
        root / "deep_context_federation.json",
        root / ".dcf" / "deep_context_federation.composed.json",
    ]
    return [path.resolve() for path in candidates if path.exists()]


def _path_list(root: Path, values: Sequence[Path]) -> list[Path]:
    return [resolved for value in values if (resolved := _resolve_from_root(root, value)) is not None]


def _summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": payload.get("schema_version"),
        "ok": payload.get("ok"),
        "status": payload.get("status"),
        "summary": dict(payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}),
    }


def build_agent_profile_init(
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
    model_entrypoint_preference: str = "prompt-file",
    allow_caution_model_entrypoint: bool = False,
    extra_baselines: Sequence[Path] = (),
    write: bool = True,
) -> dict[str, Any]:
    """Create a strict agent-ready profile and optionally write it to disk."""

    root = root.expanduser().resolve()
    resolved_profile_path = _resolve_from_root(root, profile_path)
    assert resolved_profile_path is not None
    profile_dir = resolved_profile_path.parent
    resolved_output_dir = _resolve_from_root(root, output_dir) if output_dir else profile_dir
    assert resolved_output_dir is not None
    resolved_handoff = _resolve_from_root(root, handoff_path)
    selected_manifests = _path_list(root, manifests) if manifests else _default_manifests(root)
    selected_baselines = _path_list(root, extra_baselines)
    policy_paths = {
        "quality_policy": _resolve_from_root(root, quality_policy_path),
        "target_review_policy": _resolve_from_root(root, target_review_policy_path),
        "efficiency_policy": _resolve_from_root(root, efficiency_policy_path),
        "context_gate_policy": _resolve_from_root(root, context_gate_policy_path),
        "memory_import_cache_dir": _resolve_from_root(root, codebase_memory_cache_dir),
    }
    checks: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, detail: Any = None) -> None:
        checks.append({"id": check_id, "passed": bool(passed), "detail": detail})

    def warn(warning_id: str, detail: Any = None) -> None:
        warnings.append({"id": warning_id, "detail": detail})

    task_text = str(task or "").strip()
    normalized_targets = list(dict.fromkeys(str(item).strip() for item in targets if str(item).strip()))
    entrypoint_preference = str(model_entrypoint_preference or "prompt-file")
    add("root_exists", root.exists() and root.is_dir(), root.as_posix())
    add("task_present", bool(task_text), task_text)
    add("model_entrypoint_preference_valid", entrypoint_preference in {"prompt-file", "prompt-pack", "audit-json"}, entrypoint_preference)
    if not normalized_targets:
        warn("no_targets", "profile can still run, but request binding will be weaker")
    add("manifest_or_handoff_present", bool(selected_manifests or resolved_handoff), {"manifest_count": len(selected_manifests), "handoff": resolved_handoff.as_posix() if resolved_handoff else ""})
    for path in selected_manifests:
        add("manifest_exists", path.exists() and path.is_file(), path.as_posix())
    if resolved_handoff:
        add("handoff_exists", resolved_handoff.exists() and resolved_handoff.is_file(), resolved_handoff.as_posix())
    for key, path in policy_paths.items():
        if path and key != "memory_import_cache_dir":
            add(f"{key}_exists", path.exists() and path.is_file(), path.as_posix())
        if path and key == "memory_import_cache_dir":
            add("memory_import_cache_dir_exists", path.exists() and path.is_dir(), path.as_posix())
    for path in selected_baselines:
        add("baseline_exists", path.exists() and path.is_file(), path.as_posix())

    profile: dict[str, Any] = {
        "schema_version": AGENT_PROFILE_SCHEMA_VERSION,
        "profile_id": str(profile_id or f"{root.name}_agent_ready_profile"),
        "description": str(description or "Generated agent-ready profile for global wrappers."),
        "authority_effect": "none",
        "no_apply": True,
        "root": _relpath(root, base_dir=profile_dir),
        "output_dir": _relpath(resolved_output_dir, base_dir=profile_dir),
        "task": task_text,
        "targets": normalized_targets,
        "workflow_token_budget": int(workflow_token_budget),
        "context_token_budget": int(context_token_budget),
        "context_mode": str(context_mode or "read-first"),
        "max_artifact_tokens": int(max_artifact_tokens),
        "query_limit": int(query_limit),
        "max_presets": int(max_presets),
        "max_rows": int(max_rows),
        "max_files": int(max_files),
        "max_parse_bytes": int(max_parse_bytes),
        "hash_files": bool(include_hashes),
        "include_memory_import": bool(include_codebase_memory),
        "include_details": bool(include_details),
        "include_content": bool(include_content),
        "include_prompt": bool(include_prompt),
        "model_entrypoint_preference": entrypoint_preference,
        "allow_caution_model_entrypoint": bool(allow_caution_model_entrypoint),
    }
    if selected_manifests:
        profile["manifests"] = [_relpath(path, base_dir=profile_dir) for path in selected_manifests]
    if resolved_handoff:
        profile["handoff"] = _relpath(resolved_handoff, base_dir=profile_dir)
    if selected_baselines:
        profile["baselines"] = [_relpath(path, base_dir=profile_dir) for path in selected_baselines]
    for key, path in policy_paths.items():
        if path:
            profile[key] = _relpath(path, base_dir=profile_dir)

    validation: dict[str, Any] = {}
    failed = [row for row in checks if row.get("passed") is not True]
    wrote_profile = False
    if write and not failed:
        write_json(resolved_profile_path, profile)
        validation = load_agent_profile(resolved_profile_path)
        wrote_profile = True
    if validation and validation.get("ok") is not True:
        failed.append({"id": "written_profile_validation_failed", "passed": False, "detail": validation.get("errors")})
    ok = not failed
    return {
        "schema_version": AGENT_PROFILE_INIT_SCHEMA_VERSION,
        "ok": ok,
        "status": "pass_agent_profile_init" if ok else "fail_agent_profile_init",
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": utc_now(),
        "root": root.as_posix(),
        "profile_path": resolved_profile_path.as_posix(),
        "profile": profile,
        "profile_validation_summary": _summary(validation) if validation else {},
        "checks": checks,
        "warnings": warnings,
        "errors": failed,
        "outputs": {"agent_profile_json": resolved_profile_path.as_posix()} if wrote_profile else {},
        "summary": {
            "manifest_count": len(selected_manifests),
            "target_count": len(normalized_targets),
            "warning_count": len(warnings),
            "write": bool(write),
        },
        "safety_boundaries": {
            "authority_effect": "none",
            "no_apply": True,
            "mutation_allowed": False,
            "writes_profile_only": bool(wrote_profile),
            "external_model_calls": False,
            "source_or_authority_mutation": False,
        },
    }


def markdown_agent_profile_init(result: Mapping[str, Any]) -> str:
    lines = [
        "# Deep Context Federation Agent Profile Init",
        "",
        f"- Status: `{result.get('status')}`",
        f"- OK: `{result.get('ok')}`",
        f"- Profile: `{result.get('profile_path')}`",
        f"- Validation: `{(result.get('profile_validation_summary') or {}).get('status')}`",
        "",
        "## Warnings",
        "",
    ]
    warnings = [row for row in result.get("warnings") or [] if isinstance(row, Mapping)]
    if warnings:
        for row in warnings:
            lines.append(f"- `{row.get('id')}` detail=`{row.get('detail')}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Errors", ""])
    errors = [row for row in result.get("errors") or [] if isinstance(row, Mapping)]
    if errors:
        for row in errors:
            lines.append(f"- `{row.get('id')}` detail=`{row}`")
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"
