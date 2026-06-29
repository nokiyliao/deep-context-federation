"""Machine-readable operator context projection for DCF artifacts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from deep_context_federation.builder import utc_now
from deep_context_federation.doctor import doctor_federation
from deep_context_federation.query import query_federation

OPERATOR_CONTEXT_SCHEMA_VERSION = "deep_context_federation_operator_context_v1"


def _rows(payload: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    return [dict(item) for item in payload.get(key) or [] if isinstance(item, Mapping)]


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _strings(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [str(item) for item in value if str(item)]


def _json_text(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    except Exception:
        return str(value)


def _stable_id(kind: str, label: str) -> str:
    digest = hashlib.sha256(f"{kind}:{label}".encode("utf-8")).hexdigest()[:16]
    safe = "".join(char if char.isalnum() or char in {"_", "-", "."} else "_" for char in label).strip("_")
    return f"operator:{kind}:{(safe or 'item')[:48]}:{digest}"


def _append_row(
    rows: list[dict[str, Any]],
    *,
    kind: str,
    label: str,
    status: str,
    severity: str,
    detail: Mapping[str, Any] | None = None,
    recommended_action: str = "",
) -> None:
    rows.append(
        {
            "row_id": _stable_id(kind, label),
            "kind": kind,
            "label": label,
            "status": status,
            "severity": severity,
            "detail": dict(detail or {}),
            "recommended_action": recommended_action,
        }
    )


def _text_match(row: Mapping[str, Any], *needles: str) -> bool:
    text = _json_text(row).lower()
    return any(needle.lower() in text for needle in needles)


def _source_label(row: Mapping[str, Any]) -> str:
    role = str(row.get("role") or "source")
    status = str(row.get("status") or row.get("source_status") or "unknown")
    required = "required" if row.get("required") else "optional"
    schema = str(row.get("schema_version") or "")
    return " ".join(item for item in [role, required, status, schema] if item)


def _status_counts(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "")
        if value:
            counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def build_operator_context(federation: Mapping[str, Any], *, limit: int = 50) -> dict[str, Any]:
    """Summarize operator-relevant blockers, warnings, and projection drift."""

    limit = max(1, int(limit))
    sources = _rows(federation, "sources")
    entities = _rows(federation, "entities")
    edges = _rows(federation, "edges")
    conflicts = _rows(federation, "conflicts")
    summary = _mapping(federation.get("summary"))
    graph_summary = _mapping(federation.get("graph_summary"))
    doctor = doctor_federation(federation)
    operator_query = query_federation(federation, preset="operator-projection", limit=limit)
    stale_query = query_federation(federation, preset="stale-sources", limit=limit)
    rows: list[dict[str, Any]] = []

    for conflict in conflicts:
        severity = str(conflict.get("severity") or "warning")
        label = str(conflict.get("conflict_type") or "conflict")
        _append_row(
            rows,
            kind="conflict",
            label=label,
            status="blocked" if severity == "error" else "warn",
            severity=severity,
            detail={
                "conflict_type": conflict.get("conflict_type"),
                "message": conflict.get("message") or conflict.get("detail"),
            },
            recommended_action="resolve_conflict_before_operator_handoff" if severity == "error" else "review_conflict_before_broad_context_use",
        )

    for source in sources:
        quality = _mapping(source.get("quality"))
        reasons = _strings(quality.get("reasons"))
        status = str(source.get("status") or "")
        role = str(source.get("role") or "")
        label = _source_label(source)
        if source.get("required") and status not in {"loaded", "stale"}:
            _append_row(
                rows,
                kind="required_input",
                label=label,
                status="blocked",
                severity="error",
                detail={"role": role, "status": status, "required": True},
                recommended_action="refresh_or_restore_required_input",
            )
        if status == "stale":
            _append_row(
                rows,
                kind="stale_input",
                label=label,
                status="warn",
                severity="warning",
                detail={"role": role, "status": status, "stale_for": source.get("stale_for")},
                recommended_action="refresh_stale_input_or_accept_advisory_use",
            )
        if int(quality.get("score") or 100) < 80:
            _append_row(
                rows,
                kind="low_quality_input",
                label=label,
                status="warn",
                severity="warning",
                detail={"role": role, "quality_score": quality.get("score"), "quality_reasons": reasons},
                recommended_action="inspect_low_quality_input_before_model_handoff",
            )
        if "dirty" in reasons or "dirty" in status:
            _append_row(
                rows,
                kind="dirty_lane",
                label=label,
                status="warn",
                severity="warning",
                detail={"role": role, "status": status, "quality_reasons": reasons},
                recommended_action="settle_dirty_lane_before_trusting_operator_projection",
            )

    federation_head = str(federation.get("head_commit") or "")
    for source in sources:
        role = str(source.get("role") or "")
        if "current_truth" not in role and "truth" not in _json_text(source).lower():
            continue
        source_head = str(source.get("head_commit") or "")
        drift = bool(federation_head and source_head and federation_head != source_head)
        _append_row(
            rows,
            kind="current_truth",
            label=_source_label(source),
            status="warn" if drift else "ok",
            severity="warning" if drift else "info",
            detail={
                "role": role,
                "status": source.get("status"),
                "head_commit_matches_federation": not drift,
                "has_source_head": bool(source_head),
                "has_federation_head": bool(federation_head),
            },
            recommended_action="refresh_current_truth_snapshot_to_federation_head" if drift else "continue_using_current_truth_projection",
        )

    for entity in entities:
        if str(entity.get("entity_type") or "") == "surface_id":
            _append_row(
                rows,
                kind="surface",
                label=str(entity.get("label") or entity.get("value") or "surface"),
                status="observed",
                severity="info",
                detail={"entity_type": "surface_id"},
                recommended_action="use_resolve_evidence_for_surface_details",
            )

    operator_projection_count = int(operator_query.get("row_count") or 0)
    stale_projection_count = int(stale_query.get("row_count") or 0)
    error_count = len([row for row in rows if row.get("severity") == "error"])
    warning_count = len([row for row in rows if row.get("severity") == "warning"])
    status = "fail_operator_context" if error_count else "warn_operator_context" if warning_count else "pass_operator_context"
    rows = rows[:limit]
    recommended_commands = [
        {
            "id": "inspect_operator_projection_rows",
            "command": "query-context",
            "argv": ["query-context", "--preset", "operator-projection", "--limit", str(limit), "--format", "json"],
            "when": "operator_projection_details_needed",
        },
        {
            "id": "diagnose_context_health",
            "command": "diagnose-context",
            "argv": ["diagnose-context", "--format", "json"],
            "when": "operator_context_status_not_pass",
        },
        {
            "id": "gate_context_quality",
            "command": "gate-quality",
            "argv": ["gate-quality", "--format", "json"],
            "when": "ci_or_wrapper_needs_pass_fail_gate",
        },
    ]
    return {
        "schema_version": OPERATOR_CONTEXT_SCHEMA_VERSION,
        "ok": error_count == 0,
        "status": status,
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": utc_now(),
        "summary": {
            "source_count": len(sources),
            "entity_count": len(entities),
            "edge_count": len(edges),
            "conflict_count": len(conflicts),
            "operator_projection_row_count": operator_projection_count,
            "stale_projection_row_count": stale_projection_count,
            "row_count": len(rows),
            "error_count": error_count,
            "warning_count": warning_count,
            "status_counts": _status_counts(rows, "status"),
            "severity_counts": _status_counts(rows, "severity"),
            "doctor_status": doctor.get("status"),
            "federation_status": federation.get("status"),
            "graph_edge_count": graph_summary.get("edge_count") or summary.get("edge_count"),
        },
        "operator_rows": rows,
        "doctor_summary": {
            "status": doctor.get("status"),
            "ok": doctor.get("ok"),
            "error_count": doctor.get("error_count"),
            "warning_count": doctor.get("warning_count"),
            "recommended_actions": list(doctor.get("recommended_actions") or []),
        },
        "query_summaries": {
            "operator_projection": {
                "status": operator_query.get("status"),
                "row_count": operator_projection_count,
                "limit": operator_query.get("limit"),
            },
            "stale_sources": {
                "status": stale_query.get("status"),
                "row_count": stale_projection_count,
                "limit": stale_query.get("limit"),
            },
        },
        "recommended_commands": recommended_commands,
        "safety_boundaries": {
            "authority_effect": "none",
            "no_apply": True,
            "mutates_repo": False,
            "executes_commands": False,
            "external_model_calls": False,
            "source_identity_collapsed": True,
            "source_ids_exposed": False,
        },
    }


def markdown_operator_context(payload: Mapping[str, Any]) -> str:
    summary = _mapping(payload.get("summary"))
    lines = [
        "# Deep Context Federation Operator Context",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- OK: `{payload.get('ok')}`",
        f"- Rows: `{summary.get('row_count')}`",
        f"- Errors: `{summary.get('error_count')}`",
        f"- Warnings: `{summary.get('warning_count')}`",
        f"- Doctor: `{summary.get('doctor_status')}`",
        "",
        "## Operator Rows",
        "",
    ]
    rows = [row for row in payload.get("operator_rows") or [] if isinstance(row, Mapping)]
    if not rows:
        lines.append("- none")
    for row in rows:
        lines.append(f"- `{row.get('kind')}` status=`{row.get('status')}` severity=`{row.get('severity')}` label=`{row.get('label')}`")
        action = str(row.get("recommended_action") or "")
        if action:
            lines.append(f"  - action: `{action}`")
    lines.extend(["", "## Recommended Commands", ""])
    for command in payload.get("recommended_commands") or []:
        if isinstance(command, Mapping):
            lines.append(f"- `{command.get('command')}` when=`{command.get('when')}`")
    return "\n".join(lines).rstrip() + "\n"
