"""Machine-readable gates for DCF agent context bundles."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from deep_context_federation.agent_context import AGENT_CONTEXT_SCHEMA_VERSION

AGENT_CONTEXT_GATE_SCHEMA_VERSION = "deep_context_federation_agent_context_gate_v1"
AGENT_CONTEXT_GATE_POLICY_SCHEMA_VERSION = "deep_context_federation_agent_context_gate_policy_v1"

DEFAULT_AGENT_CONTEXT_GATE_POLICY: dict[str, Any] = {
    "schema_version": AGENT_CONTEXT_GATE_POLICY_SCHEMA_VERSION,
    "authority_effect": "none",
    "no_apply": True,
    "require_context_ok": True,
    "require_source_contract_ok": True,
    "max_missing_artifacts": 0,
    "max_skipped_artifacts": None,
    "max_truncated_artifacts": None,
    "max_selected_tokens": None,
    "max_prompt_tokens": None,
    "enforce_prompt_within_token_budget": True,
    "enforce_selected_within_content_budget": True,
    "require_schema_versions": [],
}

_OPTIONAL_POLICY_KEYS = {"policy_id", "description"}
_POLICY_KEYS = set(DEFAULT_AGENT_CONTEXT_GATE_POLICY) | _OPTIONAL_POLICY_KEYS


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _policy_bool(raw: Mapping[str, Any], key: str, default: bool, errors: list[str]) -> bool:
    if key not in raw:
        return default
    value = raw.get(key)
    if isinstance(value, bool):
        return value
    errors.append(f"{key} must be a boolean")
    return default


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


def normalize_agent_context_gate_policy(policy: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Normalize agent context gate policy-as-code."""

    raw = dict(policy or {})
    provided = policy is not None
    errors: list[str] = []
    unknown_keys = sorted(str(key) for key in raw.keys() - _POLICY_KEYS)
    input_schema = str(raw.get("schema_version") or "")
    schema_supported = (not provided and not input_schema) or input_schema == AGENT_CONTEXT_GATE_POLICY_SCHEMA_VERSION
    if provided and not input_schema:
        errors.append("schema_version is required")
    elif input_schema and input_schema != AGENT_CONTEXT_GATE_POLICY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {AGENT_CONTEXT_GATE_POLICY_SCHEMA_VERSION}")

    normalized = dict(DEFAULT_AGENT_CONTEXT_GATE_POLICY)
    normalized.update(
        {
            "source": "provided" if provided else "default",
            "input_schema_version": input_schema or AGENT_CONTEXT_GATE_POLICY_SCHEMA_VERSION,
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
    for key in (
        "no_apply",
        "require_context_ok",
        "require_source_contract_ok",
        "enforce_prompt_within_token_budget",
        "enforce_selected_within_content_budget",
    ):
        normalized[key] = _policy_bool(raw, key, bool(normalized[key]), errors)
    for key in ("max_missing_artifacts", "max_skipped_artifacts", "max_truncated_artifacts", "max_selected_tokens", "max_prompt_tokens"):
        normalized[key] = _optional_int(raw, key, normalized.get(key), errors)
    normalized["require_schema_versions"] = _string_list(raw, "require_schema_versions", normalized.get("require_schema_versions") or [], errors)
    return normalized


def load_agent_context_gate_policy(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError(f"agent context gate policy must be a JSON object: {path}")
    return normalize_agent_context_gate_policy(data)


def _schema_versions(context: Mapping[str, Any]) -> set[str]:
    summary = context.get("summary") if isinstance(context.get("summary"), Mapping) else {}
    raw = summary.get("schema_versions") if isinstance(summary.get("schema_versions"), list) else []
    return {str(item) for item in raw if item}


def evaluate_agent_context_gate(
    context: Mapping[str, Any],
    *,
    policy: Mapping[str, Any] | None = None,
    max_missing_artifacts: int | None = None,
    max_skipped_artifacts: int | None = None,
    max_truncated_artifacts: int | None = None,
    max_selected_tokens: int | None = None,
    max_prompt_tokens: int | None = None,
    require_schema_versions: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Evaluate an agent context bundle against a policy."""

    normalized_policy = (
        dict(policy)
        if policy and policy.get("schema_version") == AGENT_CONTEXT_GATE_POLICY_SCHEMA_VERSION and "schema_supported" in policy
        else normalize_agent_context_gate_policy(policy)
    )
    if max_missing_artifacts is not None:
        normalized_policy["max_missing_artifacts"] = max_missing_artifacts
    if max_skipped_artifacts is not None:
        normalized_policy["max_skipped_artifacts"] = max_skipped_artifacts
    if max_truncated_artifacts is not None:
        normalized_policy["max_truncated_artifacts"] = max_truncated_artifacts
    if max_selected_tokens is not None:
        normalized_policy["max_selected_tokens"] = max_selected_tokens
    if max_prompt_tokens is not None:
        normalized_policy["max_prompt_tokens"] = max_prompt_tokens
    if require_schema_versions is not None:
        normalized_policy["require_schema_versions"] = [str(item) for item in require_schema_versions]

    summary = context.get("summary") if isinstance(context.get("summary"), Mapping) else {}
    source_contract = context.get("source_contract_validation") if isinstance(context.get("source_contract_validation"), Mapping) else {}
    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, detail: Any = None) -> None:
        checks.append({"id": check_id, "passed": bool(passed), "severity": "error", "detail": detail})

    add("artifact_schema_supported", context.get("schema_version") == AGENT_CONTEXT_SCHEMA_VERSION, context.get("schema_version"))
    add("authority_effect_none", context.get("authority_effect") == "none", context.get("authority_effect"))
    add("no_apply_true", context.get("no_apply") is True, context.get("no_apply"))
    add("policy_schema_supported", normalized_policy.get("schema_supported") is True, normalized_policy.get("input_schema_version"))
    add("policy_authority_effect_none", normalized_policy.get("authority_effect") == "none", normalized_policy.get("authority_effect"))
    add("policy_no_apply_true", normalized_policy.get("no_apply") is True, normalized_policy.get("no_apply"))
    add("policy_unknown_keys_absent", not normalized_policy.get("unknown_keys"), normalized_policy.get("unknown_keys"))
    add("policy_validation_errors_absent", not normalized_policy.get("validation_errors"), normalized_policy.get("validation_errors"))
    if normalized_policy.get("require_context_ok"):
        add("context_ok", context.get("ok") is True, context.get("ok"))
    if normalized_policy.get("require_source_contract_ok"):
        add("source_contract_ok", source_contract.get("ok") is True, source_contract.get("ok"))

    for key, check_id in (
        ("max_missing_artifacts", "missing_artifacts_within_limit"),
        ("max_skipped_artifacts", "skipped_artifacts_within_limit"),
        ("max_truncated_artifacts", "truncated_artifacts_within_limit"),
        ("max_selected_tokens", "selected_tokens_within_limit"),
        ("max_prompt_tokens", "prompt_tokens_within_limit"),
    ):
        limit = normalized_policy.get(key)
        if limit is None:
            continue
        actual_key = {
            "max_missing_artifacts": "missing_artifact_count",
            "max_skipped_artifacts": "skipped_artifact_count",
            "max_truncated_artifacts": "truncated_artifact_count",
            "max_selected_tokens": "selected_estimated_tokens",
            "max_prompt_tokens": "prompt_estimated_tokens",
        }[key]
        actual = context.get(actual_key) if actual_key == "prompt_estimated_tokens" else summary.get(actual_key)
        add(check_id, _int(actual) <= int(limit), {"actual": actual, "max": limit})

    if normalized_policy.get("enforce_prompt_within_token_budget"):
        add(
            "prompt_within_token_budget",
            _int(context.get("prompt_estimated_tokens")) <= _int(context.get("token_budget")),
            {"actual": context.get("prompt_estimated_tokens"), "max": context.get("token_budget")},
        )
    if normalized_policy.get("enforce_selected_within_content_budget"):
        content_budget = int(max(1, _int(context.get("token_budget")) * 0.65))
        add(
            "selected_within_content_budget",
            _int(summary.get("selected_estimated_tokens")) <= content_budget,
            {"actual": summary.get("selected_estimated_tokens"), "max": content_budget},
        )
    available_versions = _schema_versions(context)
    for schema_version in normalized_policy.get("require_schema_versions") or []:
        add(
            f"required_schema_version_present:{schema_version}",
            str(schema_version) in available_versions,
            {"required": schema_version, "available": sorted(available_versions)},
        )

    failed = [item for item in checks if not item["passed"]]
    return {
        "schema_version": AGENT_CONTEXT_GATE_SCHEMA_VERSION,
        "ok": not failed,
        "status": "pass_agent_context_gate" if not failed else "fail_agent_context_gate",
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": _utc_now(),
        "policy": normalized_policy,
        "check_count": len(checks),
        "error_count": len(failed),
        "checks": checks,
        "errors": failed,
        "summary": {
            "failed_check_count": len(failed),
            "passed_check_count": len(checks) - len(failed),
            "context_status": context.get("status"),
            "selected_estimated_tokens": summary.get("selected_estimated_tokens"),
            "prompt_estimated_tokens": context.get("prompt_estimated_tokens"),
            "token_budget": context.get("token_budget"),
            "missing_artifact_count": summary.get("missing_artifact_count"),
            "skipped_artifact_count": summary.get("skipped_artifact_count"),
            "truncated_artifact_count": summary.get("truncated_artifact_count"),
        },
    }


def markdown_agent_context_gate(result: Mapping[str, Any]) -> str:
    summary = result.get("summary") if isinstance(result.get("summary"), Mapping) else {}
    lines = [
        "# Deep Context Federation Agent Context Gate",
        "",
        f"- Status: `{result.get('status')}`",
        f"- OK: `{result.get('ok')}`",
        f"- Errors: `{result.get('error_count')}`",
        f"- Context status: `{summary.get('context_status')}`",
        f"- Selected tokens: `{summary.get('selected_estimated_tokens')}`",
        f"- Prompt tokens: `{summary.get('prompt_estimated_tokens')}`",
        f"- Token budget: `{summary.get('token_budget')}`",
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
