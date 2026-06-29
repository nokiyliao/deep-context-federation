"""Machine-readable proof that DCF is a better default than scattered context reads."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from deep_context_federation.source_identity import public_source_identity_policy

CONTEXT_ADVANTAGE_SCHEMA_VERSION = "deep_context_federation_context_advantage_v1"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _rows(value: object) -> list[Mapping[str, Any]]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [row for row in value if isinstance(row, Mapping)]
    return []


def _float(value: object) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _int(value: object) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _check(
    checks: list[dict[str, Any]],
    *,
    check_id: str,
    ok: bool,
    severity: str,
    detail: str,
    observed: object = None,
    expected: object = None,
) -> None:
    checks.append(
        {
            "id": check_id,
            "ok": bool(ok),
            "severity": "info" if ok else severity,
            "detail": detail,
            "observed": observed,
            "expected": expected,
        }
    )


def _boundary_check(checks: list[dict[str, Any]], name: str, payload: Mapping[str, Any]) -> None:
    _check(
        checks,
        check_id=f"{name}_boundary",
        ok=payload.get("authority_effect") == "none" and payload.get("no_apply") is True,
        severity="error",
        detail=f"{name} must be read-only and authority-neutral.",
        observed={"authority_effect": payload.get("authority_effect"), "no_apply": payload.get("no_apply")},
        expected={"authority_effect": "none", "no_apply": True},
    )


def _artifact_roles(report: Mapping[str, Any]) -> set[str]:
    roles: set[str] = set()
    for row in _rows(report.get("artifacts")):
        for role in row.get("roles") or []:
            if role:
                roles.add(str(role))
    return roles


def prove_context_advantage(
    *,
    unified_plane_audit: Mapping[str, Any],
    efficiency_report: Mapping[str, Any],
    efficiency_gate: Mapping[str, Any] | None = None,
    min_read_first_savings_percent: float = 50.0,
    max_read_first_ratio: float = 0.5,
    require_unified_plane_pass: bool = True,
    require_efficiency_gate: bool = False,
) -> dict[str, Any]:
    """Combine integration and efficiency evidence into one advantage proof."""

    checks: list[dict[str, Any]] = []
    unified_plane_audit = _mapping(unified_plane_audit)
    efficiency_report = _mapping(efficiency_report)
    efficiency_gate = _mapping(efficiency_gate)

    _boundary_check(checks, "unified_plane_audit", unified_plane_audit)
    _boundary_check(checks, "efficiency_report", efficiency_report)
    if efficiency_gate:
        _boundary_check(checks, "efficiency_gate", efficiency_gate)

    unified_status = str(unified_plane_audit.get("status") or "")
    unified_ok = unified_plane_audit.get("ok") is True
    if require_unified_plane_pass:
        plane_ok = unified_ok and unified_status == "pass_unified_plane_audit"
        expected_plane = "pass_unified_plane_audit"
    else:
        plane_ok = unified_ok
        expected_plane = "ok=true"
    _check(
        checks,
        check_id="unified_plane_ready",
        ok=plane_ok,
        severity="error",
        detail="DCF must prove it is one collapsed function-named plane before claiming context advantage.",
        observed={"ok": unified_plane_audit.get("ok"), "status": unified_status},
        expected=expected_plane,
    )

    _check(
        checks,
        check_id="efficiency_report_ready",
        ok=efficiency_report.get("ok") is True and str(efficiency_report.get("status") or "").startswith("pass_"),
        severity="error",
        detail="Efficiency report must be a passing measurement artifact.",
        observed={"ok": efficiency_report.get("ok"), "status": efficiency_report.get("status")},
        expected="pass_efficiency_report",
    )

    if require_efficiency_gate or efficiency_gate:
        _check(
            checks,
            check_id="efficiency_gate_ready",
            ok=efficiency_gate.get("ok") is True and efficiency_gate.get("status") == "pass_efficiency_gate",
            severity="error" if require_efficiency_gate else "warn",
            detail="Efficiency gate should pass when supplied or required.",
            observed={"ok": efficiency_gate.get("ok"), "status": efficiency_gate.get("status")},
            expected="pass_efficiency_gate",
        )

    budget = _mapping(efficiency_report.get("model_context_budget"))
    read_first_tokens = _int(budget.get("read_first_estimated_tokens"))
    baseline_tokens = _int(budget.get("effective_baseline_estimated_tokens"))
    read_first_ratio = _float(budget.get("read_first_ratio_vs_baseline"))
    read_first_savings = _float(budget.get("read_first_savings_percent"))
    _check(
        checks,
        check_id="baseline_available",
        ok=baseline_tokens > 0,
        severity="error",
        detail="A baseline is required to compare DCF read-first context against scattered/default reads.",
        observed=baseline_tokens,
        expected="> 0",
    )
    _check(
        checks,
        check_id="read_first_smaller_than_baseline",
        ok=read_first_tokens > 0 and baseline_tokens > 0 and read_first_tokens < baseline_tokens,
        severity="error",
        detail="DCF read-first input must be smaller than the measured baseline.",
        observed={"read_first_tokens": read_first_tokens, "baseline_tokens": baseline_tokens},
        expected="0 < read_first < baseline",
    )
    _check(
        checks,
        check_id="read_first_ratio_within_advantage_limit",
        ok=baseline_tokens > 0 and read_first_ratio <= float(max_read_first_ratio),
        severity="error",
        detail="DCF read-first ratio must stay below the configured advantage limit.",
        observed=read_first_ratio,
        expected=f"<= {float(max_read_first_ratio)}",
    )
    _check(
        checks,
        check_id="read_first_savings_meets_advantage_threshold",
        ok=read_first_savings >= float(min_read_first_savings_percent),
        severity="error",
        detail="DCF read-first token savings must meet the configured advantage threshold.",
        observed=read_first_savings,
        expected=f">= {float(min_read_first_savings_percent)}",
    )
    roles = _artifact_roles(efficiency_report)
    missing_roles = sorted({"read_first", "baseline"} - roles)
    _check(
        checks,
        check_id="required_comparison_roles_present",
        ok=not missing_roles,
        severity="error",
        detail="Efficiency report must include read_first and baseline roles.",
        observed={"available_roles": sorted(roles), "missing_roles": missing_roles},
        expected=["baseline", "read_first"],
    )

    errors = [row for row in checks if not row["ok"] and row["severity"] == "error"]
    warnings = [row for row in checks if not row["ok"] and row["severity"] == "warn"]
    integration_score = _int(_mapping(unified_plane_audit.get("summary")).get("score"))
    advantage_score = max(0, min(100, int(round((integration_score * 0.4) + (min(100.0, read_first_savings) * 0.6))) - len(errors) * 25 - len(warnings) * 8))
    status = "fail_context_advantage" if errors else "warn_context_advantage" if warnings else "pass_context_advantage"
    return {
        "schema_version": CONTEXT_ADVANTAGE_SCHEMA_VERSION,
        "ok": not errors,
        "status": status,
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": _utc_now(),
        "source_identity_policy": public_source_identity_policy(audit_provenance_location="referenced_evidence_artifacts"),
        "policy": {
            "min_read_first_savings_percent": float(min_read_first_savings_percent),
            "max_read_first_ratio": float(max_read_first_ratio),
            "require_unified_plane_pass": bool(require_unified_plane_pass),
            "require_efficiency_gate": bool(require_efficiency_gate),
        },
        "summary": {
            "advantage_score": advantage_score,
            "integration_score": integration_score,
            "read_first_estimated_tokens": read_first_tokens,
            "baseline_estimated_tokens": baseline_tokens,
            "read_first_ratio_vs_baseline": read_first_ratio,
            "read_first_savings_percent": read_first_savings,
            "check_count": len(checks),
            "error_count": len(errors),
            "warning_count": len(warnings),
        },
        "evidence_refs": {
            "unified_plane_status": unified_status,
            "efficiency_report_status": efficiency_report.get("status"),
            "efficiency_gate_status": efficiency_gate.get("status") if efficiency_gate else "",
        },
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "next_actions": _next_actions(errors=errors, warnings=warnings),
        "safety_boundaries": {
            "authority_effect": "none",
            "no_apply": True,
            "mutates_repo": False,
            "executes_commands": False,
            "external_model_calls": False,
            "proof_uses_existing_artifacts_only": True,
            "source_ids_exposed": False,
            "source_identity_collapsed": True,
        },
    }


def _next_actions(*, errors: Sequence[Mapping[str, Any]], warnings: Sequence[Mapping[str, Any]]) -> list[str]:
    ids = {str(row.get("id") or "") for row in [*errors, *warnings]}
    actions: list[str] = []
    if "unified_plane_ready" in ids:
        actions.append("run_audit_unified_plane_and_fix_integration_errors_before_claiming_advantage")
    if "efficiency_report_ready" in ids or "baseline_available" in ids:
        actions.append("run_workflow_run_then_efficiency_report_with_a_full_baseline")
    if "efficiency_gate_ready" in ids:
        actions.append("run_or_relax_efficiency_gate_before_using_this_as_ci_proof")
    if "read_first_savings_meets_advantage_threshold" in ids or "read_first_ratio_within_advantage_limit" in ids:
        actions.append("tighten_read_first_context_or_lower_the_configured_advantage_threshold")
    if not actions:
        actions.append("use_dcf_read_first_artifacts_as_the_default_model_entrypoint")
    return actions


def markdown_context_advantage(payload: Mapping[str, Any]) -> str:
    summary = _mapping(payload.get("summary"))
    lines = [
        "# Deep Context Federation Context Advantage Proof",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- OK: `{payload.get('ok')}`",
        f"- Advantage score: `{summary.get('advantage_score')}`",
        f"- Read-first tokens: `{summary.get('read_first_estimated_tokens')}`",
        f"- Baseline tokens: `{summary.get('baseline_estimated_tokens')}`",
        f"- Read-first savings: `{summary.get('read_first_savings_percent')}`%",
        f"- Errors: `{summary.get('error_count')}`",
        f"- Warnings: `{summary.get('warning_count')}`",
        "",
        "## Checks",
        "",
    ]
    for check in _rows(payload.get("checks")):
        lines.append(f"- `{check.get('id')}` ok=`{check.get('ok')}` severity=`{check.get('severity')}`")
    lines.extend(["", "## Next Actions", ""])
    for action in payload.get("next_actions") or []:
        lines.append(f"- `{action}`")
    return "\n".join(lines).rstrip() + "\n"
