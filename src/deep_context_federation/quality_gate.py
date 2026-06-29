"""Machine-readable quality gates for federation and bootstrap artifacts."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

QUALITY_GATE_SCHEMA_VERSION = "deep_context_federation_quality_gate_v1"
QUALITY_GATE_POLICY_SCHEMA_VERSION = "deep_context_federation_quality_gate_policy_v1"

DEFAULT_QUALITY_GATE_POLICY: dict[str, Any] = {
    "schema_version": QUALITY_GATE_POLICY_SCHEMA_VERSION,
    "authority_effect": "none",
    "no_apply": True,
    "min_sources": 1,
    "min_entities": 1,
    "min_edges": 1,
    "max_errors": 0,
    "max_warnings": 0,
    "max_duration_seconds": None,
    "max_scan_duration_seconds": None,
    "require_roles": [],
    "require_sources": [],
    "require_query_presets": [],
    "require_bootstrap_steps": True,
}

_OPTIONAL_POLICY_KEYS = {"policy_id", "description"}
_POLICY_KEYS = set(DEFAULT_QUALITY_GATE_POLICY) | _OPTIONAL_POLICY_KEYS


def _rows(payload: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    return [dict(item) for item in payload.get(key) or [] if isinstance(item, Mapping)]


def _summary(payload: Mapping[str, Any], federation_payload: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if str(payload.get("schema_version") or "") == "deep_context_federation_bootstrap_v1":
        build = payload.get("build") if isinstance(payload.get("build"), Mapping) else {}
        return build.get("summary") if isinstance(build.get("summary"), Mapping) else {}
    source = federation_payload if federation_payload is not None else payload
    return source.get("summary") if isinstance(source.get("summary"), Mapping) else {}


def _sources(payload: Mapping[str, Any], federation_payload: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    source = federation_payload if federation_payload is not None else payload
    return _rows(source, "sources")


def _query_presets(payload: Mapping[str, Any], federation_payload: Mapping[str, Any] | None) -> set[str]:
    source = federation_payload if federation_payload is not None else payload
    presets = source.get("query_presets") if isinstance(source.get("query_presets"), Mapping) else {}
    return {str(key) for key in presets.keys()}


def _int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _policy_int(raw: Mapping[str, Any], key: str, default: int, errors: list[str]) -> int:
    if key not in raw:
        return default
    value = raw.get(key)
    if isinstance(value, bool):
        errors.append(f"{key} must be an integer, not bool")
        return default
    try:
        result = int(value)
    except Exception:
        errors.append(f"{key} must be an integer")
        return default
    if result < 0:
        errors.append(f"{key} must be non-negative")
        return default
    return result


def _policy_optional_float(raw: Mapping[str, Any], key: str, errors: list[str]) -> float | None:
    if key not in raw or raw.get(key) is None:
        return None
    value = raw.get(key)
    if isinstance(value, bool):
        errors.append(f"{key} must be a number, not bool")
        return None
    try:
        result = float(value)
    except Exception:
        errors.append(f"{key} must be a number or null")
        return None
    if result < 0:
        errors.append(f"{key} must be non-negative")
        return None
    return result


def _policy_bool(raw: Mapping[str, Any], key: str, default: bool, errors: list[str]) -> bool:
    if key not in raw:
        return default
    value = raw.get(key)
    if isinstance(value, bool):
        return value
    errors.append(f"{key} must be a boolean")
    return default


def _policy_string_list(raw: Mapping[str, Any], key: str, errors: list[str]) -> list[str]:
    if key not in raw or raw.get(key) is None:
        return []
    value = raw.get(key)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        errors.append(f"{key} must be a list of strings")
        return []
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            errors.append(f"{key}[{index}] must be a string")
            continue
        if item:
            result.append(item)
    return result


def normalize_quality_gate_policy(policy: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Normalize a policy-as-code document into the exact gate inputs."""

    raw = dict(policy or {})
    provided = policy is not None
    errors: list[str] = []
    unknown_keys = sorted(str(key) for key in raw.keys() - _POLICY_KEYS)
    input_schema = str(raw.get("schema_version") or "")
    schema_supported = (not provided and not input_schema) or input_schema == QUALITY_GATE_POLICY_SCHEMA_VERSION
    if provided and not input_schema:
        errors.append("schema_version is required")
    elif input_schema and input_schema != QUALITY_GATE_POLICY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {QUALITY_GATE_POLICY_SCHEMA_VERSION}")

    normalized = dict(DEFAULT_QUALITY_GATE_POLICY)
    normalized.update(
        {
            "source": "provided" if provided else "default",
            "input_schema_version": input_schema or QUALITY_GATE_POLICY_SCHEMA_VERSION,
            "schema_supported": schema_supported,
            "unknown_keys": unknown_keys,
            "validation_errors": errors,
        }
    )
    if "policy_id" in raw:
        normalized["policy_id"] = str(raw.get("policy_id") or "")
    if "description" in raw:
        normalized["description"] = str(raw.get("description") or "")

    normalized["authority_effect"] = str(raw.get("authority_effect") or normalized["authority_effect"])
    normalized["no_apply"] = _policy_bool(raw, "no_apply", bool(normalized["no_apply"]), errors)
    normalized["min_sources"] = _policy_int(raw, "min_sources", int(normalized["min_sources"]), errors)
    normalized["min_entities"] = _policy_int(raw, "min_entities", int(normalized["min_entities"]), errors)
    normalized["min_edges"] = _policy_int(raw, "min_edges", int(normalized["min_edges"]), errors)
    normalized["max_errors"] = _policy_int(raw, "max_errors", int(normalized["max_errors"]), errors)
    normalized["max_warnings"] = _policy_int(raw, "max_warnings", int(normalized["max_warnings"]), errors)
    normalized["max_duration_seconds"] = _policy_optional_float(raw, "max_duration_seconds", errors)
    normalized["max_scan_duration_seconds"] = _policy_optional_float(raw, "max_scan_duration_seconds", errors)
    normalized["require_roles"] = _policy_string_list(raw, "require_roles", errors)
    normalized["require_sources"] = _policy_string_list(raw, "require_sources", errors)
    normalized["require_query_presets"] = _policy_string_list(raw, "require_query_presets", errors)
    normalized["require_bootstrap_steps"] = _policy_bool(
        raw,
        "require_bootstrap_steps",
        bool(normalized["require_bootstrap_steps"]),
        errors,
    )
    return normalized


def load_quality_gate_policy(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError(f"quality gate policy must be a JSON object: {path}")
    return normalize_quality_gate_policy(data)


def _pick(policy: Mapping[str, Any], key: str, override: Any) -> Any:
    return policy.get(key) if override is None else override


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def evaluate_quality_gate(
    payload: Mapping[str, Any],
    *,
    federation_payload: Mapping[str, Any] | None = None,
    policy: Mapping[str, Any] | None = None,
    min_sources: int | None = None,
    min_entities: int | None = None,
    min_edges: int | None = None,
    max_errors: int | None = None,
    max_warnings: int | None = None,
    max_duration_seconds: float | None = None,
    max_scan_duration_seconds: float | None = None,
    require_roles: Sequence[str] | None = None,
    require_sources: Sequence[str] | None = None,
    require_query_presets: Sequence[str] | None = None,
    require_bootstrap_steps: bool | None = None,
) -> dict[str, Any]:
    """Evaluate CI/agent quality gates without mutating any artifact."""

    normalized_policy = dict(policy) if policy and policy.get("schema_version") == QUALITY_GATE_POLICY_SCHEMA_VERSION and "schema_supported" in policy else normalize_quality_gate_policy(policy)
    min_sources = _pick(normalized_policy, "min_sources", min_sources)
    min_entities = _pick(normalized_policy, "min_entities", min_entities)
    min_edges = _pick(normalized_policy, "min_edges", min_edges)
    max_errors = _pick(normalized_policy, "max_errors", max_errors)
    max_warnings = _pick(normalized_policy, "max_warnings", max_warnings)
    max_duration_seconds = _pick(normalized_policy, "max_duration_seconds", max_duration_seconds)
    max_scan_duration_seconds = _pick(normalized_policy, "max_scan_duration_seconds", max_scan_duration_seconds)
    require_roles = list(_pick(normalized_policy, "require_roles", require_roles))
    require_sources = list(_pick(normalized_policy, "require_sources", require_sources))
    require_query_presets = list(_pick(normalized_policy, "require_query_presets", require_query_presets))
    require_bootstrap_steps = bool(_pick(normalized_policy, "require_bootstrap_steps", require_bootstrap_steps))

    schema = str(payload.get("schema_version") or "")
    artifact_kind = "bootstrap" if schema == "deep_context_federation_bootstrap_v1" else "federation"
    summary = _summary(payload, federation_payload)
    sources = _sources(payload, federation_payload)
    source_ids = {str(item.get("source_id") or "") for item in sources}
    roles = {str(item.get("role") or "") for item in sources}
    query_presets = _query_presets(payload, federation_payload)
    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, detail: Any = None) -> None:
        checks.append({"id": check_id, "passed": bool(passed), "severity": "error", "detail": detail})

    add("artifact_schema_supported", schema in {"deep_context_federation_bootstrap_v1", "deep_context_federation_v1"}, schema)
    add("authority_effect_none", payload.get("authority_effect") == "none", payload.get("authority_effect"))
    add("no_apply_true", payload.get("no_apply") is True, payload.get("no_apply"))
    add("policy_schema_supported", normalized_policy.get("schema_supported") is True, normalized_policy.get("input_schema_version"))
    add("policy_authority_effect_none", normalized_policy.get("authority_effect") == "none", normalized_policy.get("authority_effect"))
    add("policy_no_apply_true", normalized_policy.get("no_apply") is True, normalized_policy.get("no_apply"))
    add("policy_unknown_keys_absent", not normalized_policy.get("unknown_keys"), normalized_policy.get("unknown_keys"))
    add("policy_validation_errors_absent", not normalized_policy.get("validation_errors"), normalized_policy.get("validation_errors"))
    if federation_payload is not None:
        add("federation_authority_effect_none", federation_payload.get("authority_effect") == "none", federation_payload.get("authority_effect"))
        add("federation_no_apply_true", federation_payload.get("no_apply") is True, federation_payload.get("no_apply"))
    add("summary_error_count_within_limit", _int(summary.get("error_count")) <= max_errors, {"actual": summary.get("error_count"), "max": max_errors})
    add("summary_warning_count_within_limit", _int(summary.get("warning_count")) <= max_warnings, {"actual": summary.get("warning_count"), "max": max_warnings})
    add("source_count_minimum", _int(summary.get("source_count")) >= min_sources, {"actual": summary.get("source_count"), "min": min_sources})
    add("entity_count_minimum", _int(summary.get("entity_count")) >= min_entities, {"actual": summary.get("entity_count"), "min": min_entities})
    add("edge_count_minimum", _int(summary.get("edge_count")) >= min_edges, {"actual": summary.get("edge_count"), "min": min_edges})
    for role in require_roles:
        add(f"required_role_present:{role}", role in roles, {"required": role, "available": sorted(roles)})
    for source_id in require_sources:
        add(f"required_source_present:{source_id}", source_id in source_ids, {"required": source_id, "available": sorted(source_ids)})
    for preset in require_query_presets:
        add(f"required_query_preset_present:{preset}", preset in query_presets, {"required": preset, "available": sorted(query_presets)})

    if max_duration_seconds is not None:
        add(
            "duration_within_limit",
            _float(payload.get("duration_seconds")) <= max_duration_seconds,
            {"actual": payload.get("duration_seconds"), "max": max_duration_seconds},
        )
    if artifact_kind == "bootstrap":
        scan = payload.get("scan") if isinstance(payload.get("scan"), Mapping) else {}
        scan_summary = scan.get("summary") if isinstance(scan.get("summary"), Mapping) else {}
        if max_scan_duration_seconds is not None:
            add(
                "scan_duration_within_limit",
                _float(scan_summary.get("duration_seconds")) <= max_scan_duration_seconds,
                {"actual": scan_summary.get("duration_seconds"), "max": max_scan_duration_seconds},
            )
        if require_bootstrap_steps:
            for key in ("scan", "build", "verify", "doctor"):
                row = payload.get(key) if isinstance(payload.get(key), Mapping) else {}
                add(f"bootstrap_step_{key}_ok", row.get("ok") is True, row)
            compose = payload.get("compose")
            if isinstance(compose, Mapping):
                add("bootstrap_step_compose_ok", compose.get("ok") is True, compose)
    elif require_bootstrap_steps:
        add("bootstrap_steps_not_required_for_federation", True, {"artifact_kind": artifact_kind})

    failed = [item for item in checks if not item["passed"]]
    effective_policy = dict(normalized_policy)
    effective_policy.update({
        "min_sources": min_sources,
        "min_entities": min_entities,
        "min_edges": min_edges,
        "max_errors": max_errors,
        "max_warnings": max_warnings,
        "max_duration_seconds": max_duration_seconds,
        "max_scan_duration_seconds": max_scan_duration_seconds,
        "require_roles": list(require_roles),
        "require_sources": list(require_sources),
        "require_query_presets": list(require_query_presets),
        "require_bootstrap_steps": require_bootstrap_steps,
    })
    return {
        "schema_version": QUALITY_GATE_SCHEMA_VERSION,
        "ok": not failed,
        "status": "pass_quality_gate" if not failed else "fail_quality_gate",
        "artifact_kind": artifact_kind,
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": _utc_now(),
        "policy": effective_policy,
        "error_count": len(failed),
        "checks": checks,
        "errors": failed,
        "summary": {
            "check_count": len(checks),
            "passed_check_count": len(checks) - len(failed),
            "failed_check_count": len(failed),
            "source_count": _int(summary.get("source_count")),
            "entity_count": _int(summary.get("entity_count")),
            "edge_count": _int(summary.get("edge_count")),
            "warning_count": _int(summary.get("warning_count")),
            "error_count": _int(summary.get("error_count")),
            "required_role_count": len(require_roles),
            "required_source_count": len(require_sources),
            "required_query_preset_count": len(require_query_presets),
        },
    }


def markdown_quality_gate(result: Mapping[str, Any]) -> str:
    lines = [
        "# Deep Context Federation Quality Gate",
        "",
        f"- Status: `{result.get('status')}`",
        f"- Artifact: `{result.get('artifact_kind')}`",
        f"- Errors: `{result.get('error_count')}`",
        "",
        "## Checks",
        "",
    ]
    for check in result.get("checks") or []:
        if isinstance(check, Mapping):
            state = "pass" if check.get("passed") else "fail"
            lines.append(f"- `{state}` `{check.get('id')}`")
    return "\n".join(lines).rstrip() + "\n"
