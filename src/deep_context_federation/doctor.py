"""Doctor-style health diagnostics for federation artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from deep_context_federation.rank import rank_sources


def _rows(payload: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    return [dict(item) for item in payload.get(key) or [] if isinstance(item, Mapping)]


def doctor_federation(payload: Mapping[str, Any]) -> dict[str, Any]:
    sources = _rows(payload, "sources")
    conflicts = _rows(payload, "conflicts")
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    graph_summary = payload.get("graph_summary") if isinstance(payload.get("graph_summary"), Mapping) else {}
    ranked_sources = rank_sources(payload, limit=10)["rows"]
    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, severity: str, detail: Any = None, action: str = "") -> None:
        checks.append(
            {
                "id": check_id,
                "passed": bool(passed),
                "severity": severity,
                "detail": detail,
                "action": action,
            }
        )

    error_conflicts = [item for item in conflicts if str(item.get("severity") or "") == "error"]
    warning_conflicts = [item for item in conflicts if str(item.get("severity") or "") == "warning"]
    stale_sources = [item for item in sources if str(item.get("status") or "") == "stale"]
    missing_required = [
        item
        for item in sources
        if item.get("required") and str(item.get("status") or "") not in {"loaded", "stale"}
    ]
    low_quality = [
        item
        for item in sources
        if int((item.get("quality") if isinstance(item.get("quality"), Mapping) else {}).get("score") or 100) < 80
    ]

    add("payload_ok", payload.get("ok") is True, "error", payload.get("status"), "Fix hard verifier failures before trusting this artifact.")
    add("no_error_conflicts", not error_conflicts, "error", {"count": len(error_conflicts)}, "Resolve error conflicts first.")
    add("required_sources_available", not missing_required, "error", [item.get("source_id") for item in missing_required], "Refresh or remove missing required sources.")
    add("stale_sources_reviewed", not stale_sources, "warning", [item.get("source_id") for item in stale_sources], "Refresh stale sources or accept their advisory status.")
    add("low_quality_sources_reviewed", not low_quality, "warning", [item.get("source_id") for item in low_quality], "Inspect low-quality source rankings.")
    add("graph_has_edges", int(graph_summary.get("edge_count") or summary.get("edge_count") or 0) > 0, "warning", graph_summary, "Add native ingestion rows or graph exports to connect entities.")
    add("warning_conflicts_reviewed", not warning_conflicts, "warning", {"count": len(warning_conflicts)}, "Review warnings before agent automation.")

    failed_errors = [item for item in checks if not item["passed"] and item["severity"] == "error"]
    failed_warnings = [item for item in checks if not item["passed"] and item["severity"] == "warning"]
    status = "pass"
    if failed_errors:
        status = "fail"
    elif failed_warnings:
        status = "warn"
    actions = [item["action"] for item in [*failed_errors, *failed_warnings] if item.get("action")]
    return {
        "schema_version": "deep_context_federation_doctor_v1",
        "ok": not failed_errors,
        "status": status,
        "error_count": len(failed_errors),
        "warning_count": len(failed_warnings),
        "checks": checks,
        "top_risky_sources": ranked_sources[:5],
        "recommended_actions": actions,
    }


def markdown_doctor(result: Mapping[str, Any]) -> str:
    lines = [
        "# Deep Context Federation Doctor",
        "",
        f"- Status: `{result.get('status')}`",
        f"- Errors: `{result.get('error_count')}`",
        f"- Warnings: `{result.get('warning_count')}`",
        "",
        "## Checks",
        "",
    ]
    for check in result.get("checks") or []:
        if isinstance(check, Mapping):
            state = "pass" if check.get("passed") else "fail"
            lines.append(f"- `{state}` `{check.get('severity')}` `{check.get('id')}`")
    lines.extend(["", "## Recommended Actions", ""])
    actions = [str(item) for item in result.get("recommended_actions") or []]
    if actions:
        for action in actions:
            lines.append(f"- {action}")
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"
