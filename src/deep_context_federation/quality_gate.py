"""Machine-readable quality gates for federation and bootstrap artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

QUALITY_GATE_SCHEMA_VERSION = "deep_context_federation_quality_gate_v1"


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


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def evaluate_quality_gate(
    payload: Mapping[str, Any],
    *,
    federation_payload: Mapping[str, Any] | None = None,
    min_sources: int = 1,
    min_entities: int = 1,
    min_edges: int = 1,
    max_errors: int = 0,
    max_warnings: int = 0,
    max_duration_seconds: float | None = None,
    max_scan_duration_seconds: float | None = None,
    require_roles: Sequence[str] = (),
    require_sources: Sequence[str] = (),
    require_query_presets: Sequence[str] = (),
    require_bootstrap_steps: bool = True,
) -> dict[str, Any]:
    """Evaluate CI/agent quality gates without mutating any artifact."""

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
    policy = {
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
    }
    return {
        "schema_version": QUALITY_GATE_SCHEMA_VERSION,
        "ok": not failed,
        "status": "pass_quality_gate" if not failed else "fail_quality_gate",
        "artifact_kind": artifact_kind,
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": _utc_now(),
        "policy": policy,
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
