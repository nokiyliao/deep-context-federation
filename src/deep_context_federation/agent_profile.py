"""Agent-ready profile loading for DCF global wrappers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from deep_context_federation.builder import read_json
from deep_context_federation.builder import utc_now

AGENT_PROFILE_SCHEMA_VERSION = "deep_context_federation_agent_profile_v1"


PATH_FIELDS = {
    "root",
    "output_dir",
    "handoff",
    "quality_policy",
    "target_review_policy",
    "efficiency_policy",
    "context_gate_policy",
    "codebase_memory_cache_dir",
}
PATH_LIST_FIELDS = {"manifests", "baselines"}
STRING_LIST_FIELDS = {"targets"}
BOOL_FIELDS = {"hash_files", "include_codebase_memory", "include_details", "include_content", "include_prompt"}
INT_FIELDS = {"workflow_token_budget", "context_token_budget", "max_artifact_tokens", "query_limit", "max_presets", "max_rows", "max_files", "max_parse_bytes"}
STRING_FIELDS = {"task", "context_mode"}


def _resolve_path(value: Any, *, base_dir: Path) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve().as_posix()


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _is_json_list(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes))


def load_agent_profile(path: Path) -> dict[str, Any]:
    """Load and normalize an agent-ready profile without executing it."""

    profile_path = path.expanduser().resolve()
    base_dir = profile_path.parent
    raw = read_json(profile_path)
    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, detail: Any = None) -> None:
        checks.append({"id": check_id, "passed": bool(passed), "detail": detail})

    add("profile_exists", profile_path.exists() and profile_path.is_file(), profile_path.as_posix())
    add("profile_json_object", bool(raw), type(raw).__name__)
    add("schema_version", raw.get("schema_version") == AGENT_PROFILE_SCHEMA_VERSION, raw.get("schema_version"))
    add("authority_effect_none", raw.get("authority_effect") in {None, "none"}, raw.get("authority_effect"))
    add("no_apply_not_false", raw.get("no_apply") is not False, raw.get("no_apply"))

    normalized: dict[str, Any] = {}
    unknown_keys = sorted(
        str(key)
        for key in raw
        if key
        not in {
            "schema_version",
            "authority_effect",
            "no_apply",
            "profile_id",
            "description",
            *PATH_FIELDS,
            *PATH_LIST_FIELDS,
            *STRING_LIST_FIELDS,
            *BOOL_FIELDS,
            *INT_FIELDS,
            *STRING_FIELDS,
        }
    )
    add("unknown_keys_absent", not unknown_keys, unknown_keys)

    for field in PATH_FIELDS:
        if field in raw and raw.get(field) is not None:
            add(f"{field}_string", isinstance(raw.get(field), str), raw.get(field))
            if isinstance(raw.get(field), str):
                normalized[field] = _resolve_path(raw.get(field), base_dir=base_dir)
    for field in PATH_LIST_FIELDS:
        if field in raw and raw.get(field) is not None:
            add(f"{field}_list", _is_json_list(raw.get(field)), raw.get(field))
            if _is_json_list(raw.get(field)):
                values = _string_list(raw.get(field))
                normalized[field] = [_resolve_path(value, base_dir=base_dir) for value in values]
    for field in STRING_LIST_FIELDS:
        if field in raw and raw.get(field) is not None:
            add(f"{field}_list", _is_json_list(raw.get(field)), raw.get(field))
            if _is_json_list(raw.get(field)):
                normalized[field] = _string_list(raw.get(field))
    for field in BOOL_FIELDS:
        if field in raw and raw.get(field) is not None:
            add(f"{field}_boolean", isinstance(raw.get(field), bool), raw.get(field))
            if isinstance(raw.get(field), bool):
                normalized[field] = bool(raw.get(field))
    for field in INT_FIELDS:
        if field in raw and raw.get(field) is not None:
            is_integer = isinstance(raw.get(field), int) and not isinstance(raw.get(field), bool)
            add(f"{field}_integer", is_integer, raw.get(field))
            if is_integer:
                normalized[field] = int(raw.get(field))
    for field in STRING_FIELDS:
        if field in raw and raw.get(field) is not None:
            add(f"{field}_string", isinstance(raw.get(field), str), raw.get(field))
            if isinstance(raw.get(field), str):
                normalized[field] = str(raw.get(field) or "")

    failed = [row for row in checks if row.get("passed") is not True]
    return {
        "schema_version": AGENT_PROFILE_SCHEMA_VERSION,
        "ok": not failed,
        "status": "pass_agent_profile" if not failed else "fail_agent_profile",
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": utc_now(),
        "profile_path": profile_path.as_posix(),
        "profile_id": str(raw.get("profile_id") or profile_path.stem),
        "description": str(raw.get("description") or ""),
        "normalized": normalized,
        "checks": checks,
        "errors": failed,
        "summary": {
            "field_count": len(normalized),
            "unknown_key_count": len(unknown_keys),
        },
    }


def markdown_agent_profile(result: Mapping[str, Any]) -> str:
    """Render an agent-ready profile validation result for humans."""

    normalized = result.get("normalized") if isinstance(result.get("normalized"), Mapping) else {}
    lines = [
        "# Deep Context Federation Agent Profile",
        "",
        f"- Status: `{result.get('status')}`",
        f"- OK: `{result.get('ok')}`",
        f"- Profile: `{result.get('profile_path')}`",
        f"- Profile ID: `{result.get('profile_id')}`",
        f"- Normalized fields: `{len(normalized)}`",
        "",
        "## Fields",
        "",
    ]
    if normalized:
        for key in sorted(normalized):
            value = normalized[key]
            lines.append(f"- `{key}`: `{value}`")
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
