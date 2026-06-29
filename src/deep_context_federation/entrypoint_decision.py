"""Final machine-readable DCF entrypoint adoption decision."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

ENTRYPOINT_DECISION_SCHEMA_VERSION = "deep_context_federation_entrypoint_decision_v1"


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _summary_value(summary: Mapping[str, Any], key: str, default: Any = None) -> Any:
    inner = _mapping(summary.get("summary"))
    return inner.get(key, default)


def _float(value: object) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _check(checks: list[dict[str, Any]], check_id: str, passed: bool, *, severity: str = "error", detail: Any = None) -> None:
    checks.append({"id": check_id, "passed": bool(passed), "severity": "info" if passed else severity, "detail": detail})


def build_entrypoint_decision(
    *,
    ok: bool,
    prompt_source: str,
    prompt_format: str,
    source_identity_policy: Mapping[str, Any],
    verification_summary: Mapping[str, Any],
    context_advantage_summary: Mapping[str, Any],
    token_economics: Mapping[str, Any],
    prompt_pack: Mapping[str, Any],
    errors: Sequence[Mapping[str, Any]] = (),
    blocked_reason: str = "",
) -> dict[str, Any]:
    """Return one final recommendation for wrappers choosing a model entrypoint."""

    advantage_status = str(context_advantage_summary.get("status") or "")
    verification_status = str(verification_summary.get("status") or "")
    token_status = str(token_economics.get("status") or "")
    source_ids_exposed = source_identity_policy.get("source_ids_exposed")
    checks: list[dict[str, Any]] = []
    _check(checks, "model_input_passed", bool(ok), detail={"status": "pass" if ok else "fail"})
    _check(checks, "verification_passed", verification_summary.get("ok") is True and verification_status.startswith("pass"), detail=verification_status)
    _check(checks, "context_advantage_available", bool(context_advantage_summary), detail=advantage_status)
    _check(checks, "context_advantage_not_failed", advantage_status.startswith(("pass", "warn")), detail=advantage_status)
    _check(checks, "source_identity_hidden", source_ids_exposed is False, detail={"source_ids_exposed": source_ids_exposed})
    _check(checks, "prompt_source_present", bool(prompt_source), detail=prompt_source)
    _check(checks, "prompt_format_markdown", str(prompt_format or "") == "markdown", detail=prompt_format)
    _check(checks, "prompt_pack_public", prompt_pack.get("authority_effect") == "none" and prompt_pack.get("no_apply") is True, detail=prompt_pack.get("schema_version"))
    _check(checks, "token_economics_measured", token_status == "measured", severity="warn", detail=token_status)

    hard_errors = [row for row in checks if not row["passed"] and row["severity"] == "error"]
    warnings = [row for row in checks if not row["passed"] and row["severity"] == "warn"]
    warnings.extend({"id": str(row.get("id") or "model_input_error"), "detail": dict(row), "severity": "warn"} for row in errors if ok and isinstance(row, Mapping))
    if hard_errors:
        decision = "do_not_use_dcf_model_input"
        status = "fail_entrypoint_decision"
        recommended_action = "repair_handoff_before_model_use"
        reason = blocked_reason or "required_entrypoint_gate_failed"
    elif advantage_status.startswith("warn") or warnings:
        decision = "use_dcf_model_input_with_caution"
        status = "warn_entrypoint_decision"
        recommended_action = "use_prompt_pack_and_record_context_warnings"
        reason = "required_gates_passed_with_warnings"
    else:
        decision = "use_dcf_model_input"
        status = "pass_entrypoint_decision"
        recommended_action = "use_prompt_pack_or_prompt_source_as_model_input"
        reason = "verified_dcf_entrypoint_is_integrated_token_efficient_and_public_boundary_safe"

    evidence = {
        "verification_status": verification_status,
        "context_advantage_status": advantage_status,
        "advantage_score": _summary_value(context_advantage_summary, "advantage_score", 0),
        "read_first_savings_percent": _summary_value(context_advantage_summary, "read_first_savings_percent", 0.0),
        "token_economics_status": token_status,
        "estimated_token_savings_percent": _float(token_economics.get("estimated_token_savings_percent")),
        "prompt_source_present": bool(prompt_source),
        "prompt_format": str(prompt_format or ""),
        "source_ids_exposed": source_ids_exposed,
        "prompt_pack_schema_version": str(prompt_pack.get("schema_version") or ""),
    }
    return {
        "schema_version": ENTRYPOINT_DECISION_SCHEMA_VERSION,
        "ok": decision in {"use_dcf_model_input", "use_dcf_model_input_with_caution"},
        "status": status,
        "authority_effect": "none",
        "no_apply": True,
        "decision": decision,
        "recommended_action": recommended_action,
        "reason": reason,
        "evidence": evidence,
        "checks": checks,
        "errors": hard_errors,
        "warnings": warnings,
    }
