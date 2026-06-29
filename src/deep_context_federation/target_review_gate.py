"""Machine-readable gates for DCF target review artifacts."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TARGET_REVIEW_GATE_SCHEMA_VERSION = "deep_context_federation_target_review_gate_v1"
TARGET_REVIEW_GATE_POLICY_SCHEMA_VERSION = "deep_context_federation_target_review_gate_policy_v1"

DEFAULT_TARGET_REVIEW_GATE_POLICY: dict[str, Any] = {
    "schema_version": TARGET_REVIEW_GATE_POLICY_SCHEMA_VERSION,
    "authority_effect": "none",
    "no_apply": True,
    "max_blocked": 0,
    "max_no_match": 0,
    "max_advisory_only": 0,
    "max_warn": None,
    "max_priority_score": 99,
    "min_average_confidence": 0.0,
    "disallow_risk_flags": [],
    "require_targets": [],
}

_OPTIONAL_POLICY_KEYS = {"policy_id", "description"}
_POLICY_KEYS = set(DEFAULT_TARGET_REVIEW_GATE_POLICY) | _OPTIONAL_POLICY_KEYS


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


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


def _optional_int(raw: Mapping[str, Any], key: str, default: int | None, errors: list[str]) -> int | None:
    if key not in raw or raw.get(key) is None:
        return default
    value = raw.get(key)
    if isinstance(value, bool):
        errors.append(f"{key} must be an integer or null, not bool")
        return default
    try:
        result = int(value)
    except Exception:
        errors.append(f"{key} must be an integer or null")
        return default
    if result < 0:
        errors.append(f"{key} must be non-negative")
        return default
    return result


def _optional_float(raw: Mapping[str, Any], key: str, default: float | None, errors: list[str]) -> float | None:
    if key not in raw or raw.get(key) is None:
        return default
    value = raw.get(key)
    if isinstance(value, bool):
        errors.append(f"{key} must be a number or null, not bool")
        return default
    try:
        result = float(value)
    except Exception:
        errors.append(f"{key} must be a number or null")
        return default
    if result < 0:
        errors.append(f"{key} must be non-negative")
        return default
    return result


def _policy_bool(raw: Mapping[str, Any], key: str, default: bool, errors: list[str]) -> bool:
    if key not in raw:
        return default
    value = raw.get(key)
    if isinstance(value, bool):
        return value
    errors.append(f"{key} must be a boolean")
    return default


def _string_list(raw: Mapping[str, Any], key: str, errors: list[str]) -> list[str]:
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


def normalize_target_review_gate_policy(policy: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Normalize target review gate policy-as-code."""

    raw = dict(policy or {})
    provided = policy is not None
    errors: list[str] = []
    unknown_keys = sorted(str(key) for key in raw.keys() - _POLICY_KEYS)
    input_schema = str(raw.get("schema_version") or "")
    schema_supported = (not provided and not input_schema) or input_schema == TARGET_REVIEW_GATE_POLICY_SCHEMA_VERSION
    if provided and not input_schema:
        errors.append("schema_version is required")
    elif input_schema and input_schema != TARGET_REVIEW_GATE_POLICY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {TARGET_REVIEW_GATE_POLICY_SCHEMA_VERSION}")

    normalized = dict(DEFAULT_TARGET_REVIEW_GATE_POLICY)
    normalized.update(
        {
            "source": "provided" if provided else "default",
            "input_schema_version": input_schema or TARGET_REVIEW_GATE_POLICY_SCHEMA_VERSION,
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
    for key in ("max_blocked", "max_no_match", "max_advisory_only", "max_warn", "max_priority_score"):
        normalized[key] = _optional_int(raw, key, normalized.get(key), errors)
    normalized["min_average_confidence"] = _optional_float(
        raw,
        "min_average_confidence",
        float(normalized["min_average_confidence"]),
        errors,
    )
    normalized["disallow_risk_flags"] = _string_list(raw, "disallow_risk_flags", errors)
    normalized["require_targets"] = _string_list(raw, "require_targets", errors)
    return normalized


def load_target_review_gate_policy(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError(f"target review gate policy must be a JSON object: {path}")
    return normalize_target_review_gate_policy(data)


def _pick(policy: Mapping[str, Any], key: str, override: Any) -> Any:
    return policy.get(key) if override is None else override


def evaluate_target_review_gate(
    review: Mapping[str, Any],
    *,
    policy: Mapping[str, Any] | None = None,
    max_blocked: int | None = None,
    max_no_match: int | None = None,
    max_advisory_only: int | None = None,
    max_warn: int | None = None,
    max_priority_score: int | None = None,
    min_average_confidence: float | None = None,
    disallow_risk_flags: Sequence[str] | None = None,
    require_targets: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Evaluate a target review artifact against a policy."""

    normalized_policy = (
        dict(policy)
        if policy and policy.get("schema_version") == TARGET_REVIEW_GATE_POLICY_SCHEMA_VERSION and "schema_supported" in policy
        else normalize_target_review_gate_policy(policy)
    )
    max_blocked = _pick(normalized_policy, "max_blocked", max_blocked)
    max_no_match = _pick(normalized_policy, "max_no_match", max_no_match)
    max_advisory_only = _pick(normalized_policy, "max_advisory_only", max_advisory_only)
    max_warn = _pick(normalized_policy, "max_warn", max_warn)
    max_priority_score = _pick(normalized_policy, "max_priority_score", max_priority_score)
    min_average_confidence = _pick(normalized_policy, "min_average_confidence", min_average_confidence)
    disallow_risk_flags = list(_pick(normalized_policy, "disallow_risk_flags", disallow_risk_flags))
    require_targets = list(_pick(normalized_policy, "require_targets", require_targets))

    summary = review.get("summary") if isinstance(review.get("summary"), Mapping) else {}
    verdict_counts = summary.get("verdict_counts") if isinstance(summary.get("verdict_counts"), Mapping) else {}
    risk_flag_counts = summary.get("risk_flag_counts") if isinstance(summary.get("risk_flag_counts"), Mapping) else {}
    target_set = {str(row.get("target")) for row in review.get("rows") or [] if isinstance(row, Mapping) and row.get("target")}
    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, detail: Any = None) -> None:
        checks.append({"id": check_id, "passed": bool(passed), "severity": "error", "detail": detail})

    add("artifact_schema_supported", review.get("schema_version") == "deep_context_federation_target_review_v1", review.get("schema_version"))
    add("authority_effect_none", review.get("authority_effect") == "none", review.get("authority_effect"))
    add("no_apply_true", review.get("no_apply") is True, review.get("no_apply"))
    add("policy_schema_supported", normalized_policy.get("schema_supported") is True, normalized_policy.get("input_schema_version"))
    add("policy_authority_effect_none", normalized_policy.get("authority_effect") == "none", normalized_policy.get("authority_effect"))
    add("policy_no_apply_true", normalized_policy.get("no_apply") is True, normalized_policy.get("no_apply"))
    add("policy_unknown_keys_absent", not normalized_policy.get("unknown_keys"), normalized_policy.get("unknown_keys"))
    add("policy_validation_errors_absent", not normalized_policy.get("validation_errors"), normalized_policy.get("validation_errors"))
    if max_blocked is not None:
        add("blocked_within_limit", _int(verdict_counts.get("blocked")) <= int(max_blocked), {"actual": verdict_counts.get("blocked", 0), "max": max_blocked})
    if max_no_match is not None:
        add("no_match_within_limit", _int(verdict_counts.get("no_match")) <= int(max_no_match), {"actual": verdict_counts.get("no_match", 0), "max": max_no_match})
    if max_advisory_only is not None:
        add(
            "advisory_only_within_limit",
            _int(verdict_counts.get("advisory_only")) <= int(max_advisory_only),
            {"actual": verdict_counts.get("advisory_only", 0), "max": max_advisory_only},
        )
    if max_warn is not None:
        add("warn_within_limit", _int(verdict_counts.get("warn")) <= int(max_warn), {"actual": verdict_counts.get("warn", 0), "max": max_warn})
    if max_priority_score is not None:
        add(
            "priority_score_within_limit",
            _int(summary.get("max_priority_score")) <= int(max_priority_score),
            {"actual": summary.get("max_priority_score"), "max": max_priority_score},
        )
    if min_average_confidence is not None:
        add(
            "average_confidence_minimum",
            _float(summary.get("average_confidence")) >= float(min_average_confidence),
            {"actual": summary.get("average_confidence"), "min": min_average_confidence},
        )
    for flag in disallow_risk_flags:
        add(
            f"risk_flag_absent:{flag}",
            _int(risk_flag_counts.get(flag)) == 0,
            {"flag": flag, "count": risk_flag_counts.get(flag, 0)},
        )
    for target in require_targets:
        add(f"required_target_reviewed:{target}", target in target_set, {"required": target, "available": sorted(target_set)})

    failed = [item for item in checks if not item["passed"]]
    effective_policy = dict(normalized_policy)
    effective_policy.update(
        {
            "max_blocked": max_blocked,
            "max_no_match": max_no_match,
            "max_advisory_only": max_advisory_only,
            "max_warn": max_warn,
            "max_priority_score": max_priority_score,
            "min_average_confidence": min_average_confidence,
            "disallow_risk_flags": list(disallow_risk_flags),
            "require_targets": list(require_targets),
        }
    )
    return {
        "schema_version": TARGET_REVIEW_GATE_SCHEMA_VERSION,
        "ok": not failed,
        "status": "pass_target_review_gate" if not failed else "fail_target_review_gate",
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
            "review_status": review.get("status"),
            "target_count": _int(review.get("target_count")),
            "reviewed_count": _int(review.get("reviewed_count")),
            "verdict_counts": verdict_counts,
            "risk_flag_counts": risk_flag_counts,
            "max_priority_score": _int(summary.get("max_priority_score")),
            "average_confidence": _float(summary.get("average_confidence")),
        },
    }


def markdown_target_review_gate(result: Mapping[str, Any]) -> str:
    lines = [
        "# Deep Context Federation Target Review Gate",
        "",
        f"- Status: `{result.get('status')}`",
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
