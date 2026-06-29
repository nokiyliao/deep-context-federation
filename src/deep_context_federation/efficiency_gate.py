"""Machine-readable gates for DCF efficiency reports."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from deep_context_federation.efficiency_report import EFFICIENCY_REPORT_SCHEMA_VERSION

EFFICIENCY_GATE_SCHEMA_VERSION = "deep_context_federation_efficiency_gate_v1"
EFFICIENCY_GATE_POLICY_SCHEMA_VERSION = "deep_context_federation_efficiency_gate_policy_v1"
DEFAULT_EFFICIENCY_GATE_JSON_NAME = "deep_context_federation_efficiency_gate.json"
DEFAULT_EFFICIENCY_GATE_MD_NAME = "DEEP_CONTEXT_FEDERATION_EFFICIENCY_GATE.md"

DEFAULT_EFFICIENCY_GATE_POLICY: dict[str, Any] = {
    "schema_version": EFFICIENCY_GATE_POLICY_SCHEMA_VERSION,
    "authority_effect": "none",
    "no_apply": True,
    "require_report_ok": True,
    "max_missing_required": 0,
    "max_warnings": 0,
    "min_baseline_tokens": 1,
    "max_read_first_tokens": None,
    "max_gate_pass_tokens": None,
    "max_read_first_ratio": 0.5,
    "max_gate_pass_ratio": 1.0,
    "min_read_first_savings_percent": 50.0,
    "min_gate_pass_savings_percent": None,
    "require_artifact_roles": ["read_first", "baseline"],
}

_OPTIONAL_POLICY_KEYS = {"policy_id", "description"}
_POLICY_KEYS = set(DEFAULT_EFFICIENCY_GATE_POLICY) | _OPTIONAL_POLICY_KEYS


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


def _string_list(raw: Mapping[str, Any], key: str, default: Sequence[str], errors: list[str]) -> list[str]:
    if key not in raw or raw.get(key) is None:
        return [str(item) for item in default]
    value = raw.get(key)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        errors.append(f"{key} must be a list of strings")
        return [str(item) for item in default]
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            errors.append(f"{key}[{index}] must be a string")
            continue
        if item:
            result.append(item)
    return result


def normalize_efficiency_gate_policy(policy: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Normalize efficiency gate policy-as-code."""

    raw = dict(policy or {})
    provided = policy is not None
    errors: list[str] = []
    unknown_keys = sorted(str(key) for key in raw.keys() - _POLICY_KEYS)
    input_schema = str(raw.get("schema_version") or "")
    schema_supported = (not provided and not input_schema) or input_schema == EFFICIENCY_GATE_POLICY_SCHEMA_VERSION
    if provided and not input_schema:
        errors.append("schema_version is required")
    elif input_schema and input_schema != EFFICIENCY_GATE_POLICY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {EFFICIENCY_GATE_POLICY_SCHEMA_VERSION}")

    normalized = dict(DEFAULT_EFFICIENCY_GATE_POLICY)
    normalized.update(
        {
            "source": "provided" if provided else "default",
            "input_schema_version": input_schema or EFFICIENCY_GATE_POLICY_SCHEMA_VERSION,
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
    normalized["require_report_ok"] = _policy_bool(raw, "require_report_ok", bool(normalized["require_report_ok"]), errors)
    for key in ("max_missing_required", "max_warnings", "min_baseline_tokens", "max_read_first_tokens", "max_gate_pass_tokens"):
        normalized[key] = _optional_int(raw, key, normalized.get(key), errors)
    for key in ("max_read_first_ratio", "max_gate_pass_ratio", "min_read_first_savings_percent", "min_gate_pass_savings_percent"):
        normalized[key] = _optional_float(raw, key, normalized.get(key), errors)
    normalized["require_artifact_roles"] = _string_list(
        raw,
        "require_artifact_roles",
        normalized.get("require_artifact_roles") or [],
        errors,
    )
    return normalized


def load_efficiency_gate_policy(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError(f"efficiency gate policy must be a JSON object: {path}")
    return normalize_efficiency_gate_policy(data)


def _pick(policy: Mapping[str, Any], key: str, override: Any) -> Any:
    return policy.get(key) if override is None else override


def _artifact_roles(report: Mapping[str, Any]) -> set[str]:
    roles: set[str] = set()
    for row in report.get("artifacts") or []:
        if isinstance(row, Mapping):
            for role in row.get("roles") or []:
                if role:
                    roles.add(str(role))
    return roles


def evaluate_efficiency_gate(
    report: Mapping[str, Any],
    *,
    policy: Mapping[str, Any] | None = None,
    max_read_first_tokens: int | None = None,
    max_gate_pass_tokens: int | None = None,
    max_read_first_ratio: float | None = None,
    max_gate_pass_ratio: float | None = None,
    min_read_first_savings_percent: float | None = None,
    min_gate_pass_savings_percent: float | None = None,
    require_artifact_roles: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Evaluate an efficiency report against a policy."""

    normalized_policy = (
        dict(policy)
        if policy and policy.get("schema_version") == EFFICIENCY_GATE_POLICY_SCHEMA_VERSION and "schema_supported" in policy
        else normalize_efficiency_gate_policy(policy)
    )
    max_read_first_tokens = _pick(normalized_policy, "max_read_first_tokens", max_read_first_tokens)
    max_gate_pass_tokens = _pick(normalized_policy, "max_gate_pass_tokens", max_gate_pass_tokens)
    max_read_first_ratio = _pick(normalized_policy, "max_read_first_ratio", max_read_first_ratio)
    max_gate_pass_ratio = _pick(normalized_policy, "max_gate_pass_ratio", max_gate_pass_ratio)
    min_read_first_savings_percent = _pick(normalized_policy, "min_read_first_savings_percent", min_read_first_savings_percent)
    min_gate_pass_savings_percent = _pick(normalized_policy, "min_gate_pass_savings_percent", min_gate_pass_savings_percent)
    required_roles = list(_pick(normalized_policy, "require_artifact_roles", require_artifact_roles))
    budget = report.get("model_context_budget") if isinstance(report.get("model_context_budget"), Mapping) else {}
    missing_required = report.get("missing_required_artifacts") if isinstance(report.get("missing_required_artifacts"), list) else []
    warnings = report.get("warnings") if isinstance(report.get("warnings"), list) else []
    available_roles = _artifact_roles(report)
    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, detail: Any = None) -> None:
        checks.append({"id": check_id, "passed": bool(passed), "severity": "error", "detail": detail})

    add("artifact_schema_supported", report.get("schema_version") == EFFICIENCY_REPORT_SCHEMA_VERSION, report.get("schema_version"))
    add("authority_effect_none", report.get("authority_effect") == "none", report.get("authority_effect"))
    add("no_apply_true", report.get("no_apply") is True, report.get("no_apply"))
    if normalized_policy.get("require_report_ok"):
        add("report_ok", report.get("ok") is True, report.get("ok"))
    add("policy_schema_supported", normalized_policy.get("schema_supported") is True, normalized_policy.get("input_schema_version"))
    add("policy_authority_effect_none", normalized_policy.get("authority_effect") == "none", normalized_policy.get("authority_effect"))
    add("policy_no_apply_true", normalized_policy.get("no_apply") is True, normalized_policy.get("no_apply"))
    add("policy_unknown_keys_absent", not normalized_policy.get("unknown_keys"), normalized_policy.get("unknown_keys"))
    add("policy_validation_errors_absent", not normalized_policy.get("validation_errors"), normalized_policy.get("validation_errors"))
    max_missing = normalized_policy.get("max_missing_required")
    if max_missing is not None:
        add("missing_required_within_limit", len(missing_required) <= int(max_missing), {"actual": len(missing_required), "max": max_missing})
    max_warnings = normalized_policy.get("max_warnings")
    if max_warnings is not None:
        add("warnings_within_limit", len(warnings) <= int(max_warnings), {"actual": len(warnings), "max": max_warnings})
    min_baseline = normalized_policy.get("min_baseline_tokens")
    if min_baseline is not None:
        add(
            "baseline_tokens_minimum",
            _int(budget.get("effective_baseline_estimated_tokens")) >= int(min_baseline),
            {"actual": budget.get("effective_baseline_estimated_tokens"), "min": min_baseline},
        )
    if max_read_first_tokens is not None:
        add(
            "read_first_tokens_within_limit",
            _int(budget.get("read_first_estimated_tokens")) <= int(max_read_first_tokens),
            {"actual": budget.get("read_first_estimated_tokens"), "max": max_read_first_tokens},
        )
    if max_gate_pass_tokens is not None:
        add(
            "gate_pass_tokens_within_limit",
            _int(budget.get("gate_pass_estimated_tokens")) <= int(max_gate_pass_tokens),
            {"actual": budget.get("gate_pass_estimated_tokens"), "max": max_gate_pass_tokens},
        )
    if max_read_first_ratio is not None:
        add(
            "read_first_ratio_within_limit",
            _float(budget.get("read_first_ratio_vs_baseline")) <= float(max_read_first_ratio),
            {"actual": budget.get("read_first_ratio_vs_baseline"), "max": max_read_first_ratio},
        )
    if max_gate_pass_ratio is not None:
        add(
            "gate_pass_ratio_within_limit",
            _float(budget.get("gate_pass_ratio_vs_baseline")) <= float(max_gate_pass_ratio),
            {"actual": budget.get("gate_pass_ratio_vs_baseline"), "max": max_gate_pass_ratio},
        )
    if min_read_first_savings_percent is not None:
        add(
            "read_first_savings_minimum",
            _float(budget.get("read_first_savings_percent")) >= float(min_read_first_savings_percent),
            {"actual": budget.get("read_first_savings_percent"), "min": min_read_first_savings_percent},
        )
    if min_gate_pass_savings_percent is not None:
        add(
            "gate_pass_savings_minimum",
            _float(budget.get("gate_pass_savings_percent")) >= float(min_gate_pass_savings_percent),
            {"actual": budget.get("gate_pass_savings_percent"), "min": min_gate_pass_savings_percent},
        )
    for role in required_roles:
        add(f"required_artifact_role_present:{role}", str(role) in available_roles, {"required": role, "available": sorted(available_roles)})

    failed = [item for item in checks if not item["passed"]]
    effective_policy = dict(normalized_policy)
    effective_policy.update(
        {
            "max_read_first_tokens": max_read_first_tokens,
            "max_gate_pass_tokens": max_gate_pass_tokens,
            "max_read_first_ratio": max_read_first_ratio,
            "max_gate_pass_ratio": max_gate_pass_ratio,
            "min_read_first_savings_percent": min_read_first_savings_percent,
            "min_gate_pass_savings_percent": min_gate_pass_savings_percent,
            "require_artifact_roles": required_roles,
        }
    )
    return {
        "schema_version": EFFICIENCY_GATE_SCHEMA_VERSION,
        "ok": not failed,
        "status": "pass_efficiency_gate" if not failed else "fail_efficiency_gate",
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": _utc_now(),
        "policy": effective_policy,
        "check_count": len(checks),
        "error_count": len(failed),
        "checks": checks,
        "errors": failed,
        "summary": {
            "failed_check_count": len(failed),
            "passed_check_count": len(checks) - len(failed),
            "read_first_estimated_tokens": budget.get("read_first_estimated_tokens"),
            "gate_pass_estimated_tokens": budget.get("gate_pass_estimated_tokens"),
            "effective_baseline_estimated_tokens": budget.get("effective_baseline_estimated_tokens"),
            "read_first_savings_percent": budget.get("read_first_savings_percent"),
            "gate_pass_savings_percent": budget.get("gate_pass_savings_percent"),
        },
    }


def markdown_efficiency_gate(result: Mapping[str, Any]) -> str:
    summary = result.get("summary") if isinstance(result.get("summary"), Mapping) else {}
    lines = [
        "# Deep Context Federation Efficiency Gate",
        "",
        f"- Status: `{result.get('status')}`",
        f"- OK: `{result.get('ok')}`",
        f"- Errors: `{result.get('error_count')}`",
        f"- Read-first tokens: `{summary.get('read_first_estimated_tokens')}`",
        f"- Baseline tokens: `{summary.get('effective_baseline_estimated_tokens')}`",
        f"- Read-first savings: `{summary.get('read_first_savings_percent')}`%",
        "",
        "## Failed Checks",
        "",
    ]
    failed = [row for row in result.get("errors") or [] if isinstance(row, Mapping)]
    if failed:
        for row in failed:
            lines.append(f"- `{row.get('id')}` detail=`{row.get('detail')}`")
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"
