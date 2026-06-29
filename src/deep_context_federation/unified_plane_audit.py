"""Machine-readable audit for the DCF unified capability plane."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

UNIFIED_PLANE_AUDIT_SCHEMA_VERSION = "deep_context_federation_unified_plane_audit_v1"

HIDDEN_COMMAND_ALIASES = {
    "agent-ci",
    "agent-context",
    "agent-context-gate",
    "agent-discover",
    "agent-handoff",
    "agent-model-input",
    "agent-onboard",
    "agent-profile",
    "agent-profile-init",
    "agent-ready",
    "agent-route",
    "audit-unified-plane",
    "bench",
    "bootstrap",
    "build",
    "build-context-index",
    "build-reuse-index",
    "capabilities",
    "compose-manifest",
    "diff",
    "doctor",
    "efficiency-gate",
    "efficiency-report",
    "index-context-memory",
    "intake",
    "memory-ledger",
    "native-integration-plan",
    "pack",
    "pack-working-set",
    "plan-native-ownership",
    "quality-gate",
    "query",
    "query-read-model",
    "rank",
    "resolve",
    "review-gate",
    "schema",
    "scan",
    "sql",
    "trace",
    "validate-artifact",
    "validate-manifest",
    "verify",
    "verify-handoff",
    "workflow-plan",
    "workflow-run",
}

REQUIRED_FUNCTION_COMMANDS = {
    "brief-task",
    "reuse-context",
    "select-context",
    "unify-context",
    "plan-capability-ownership",
    "query-context-store",
}

SOURCE_IDENTITY_KEYS = {"source_id", "source_ids", "sources", "input_sources", "related_sources"}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _strings(value: object) -> set[str]:
    return {str(item) for item in value or [] if str(item)}


def _has_source_identity_key(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key) in SOURCE_IDENTITY_KEYS:
                return True
            if _has_source_identity_key(child):
                return True
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return any(_has_source_identity_key(child) for child in value)
    return False


def _check(checks: list[dict[str, Any]], *, check_id: str, ok: bool, severity: str, detail: str, observed: object = None, expected: object = None) -> None:
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
        detail=f"{name} must remain read-only and authority-neutral.",
        observed={"authority_effect": payload.get("authority_effect"), "no_apply": payload.get("no_apply")},
        expected={"authority_effect": "none", "no_apply": True},
    )


def audit_unified_plane(
    *,
    capabilities: Mapping[str, Any],
    ownership_plan: Mapping[str, Any],
    context_index: Mapping[str, Any] | None = None,
    working_set: Mapping[str, Any] | None = None,
    require_all_owned: bool = False,
    min_facets: int = 4,
) -> dict[str, Any]:
    """Audit whether public DCF surfaces are collapsed into one functional plane."""

    checks: list[dict[str, Any]] = []
    capabilities = _mapping(capabilities)
    ownership_plan = _mapping(ownership_plan)
    context_index = _mapping(context_index)
    working_set = _mapping(working_set)

    _boundary_check(checks, "capabilities", capabilities)
    _boundary_check(checks, "ownership_plan", ownership_plan)

    command_names = {str(row.get("command") or "") for row in _rows(capabilities.get("commands"))}
    leaked_aliases = sorted(command_names & HIDDEN_COMMAND_ALIASES)
    _check(
        checks,
        check_id="command_surface_uses_function_names",
        ok=not leaked_aliases,
        severity="error",
        detail="Public command manifest must use DCF function names, not source or legacy surface names.",
        observed=leaked_aliases,
        expected=[],
    )
    missing_function_commands = sorted(REQUIRED_FUNCTION_COMMANDS - command_names)
    _check(
        checks,
        check_id="required_function_commands_present",
        ok=not missing_function_commands,
        severity="error",
        detail="The core DCF function commands must be present in the machine-readable command manifest.",
        observed=missing_function_commands,
        expected=sorted(REQUIRED_FUNCTION_COMMANDS),
    )

    contract_rows = _rows(_mapping(capabilities.get("contracts")).get("artifact_contracts"))
    task_brief_contract = next((row for row in contract_rows if row.get("artifact_kind") == "task_brief"), {})
    task_brief_required = _strings(task_brief_contract.get("top_level_required"))
    _check(
        checks,
        check_id="task_brief_has_machine_query_plan",
        ok="query_plan" in task_brief_required,
        severity="error",
        detail="Task brief must expose a machine-readable query_plan so runners do not infer behavior from prose.",
        observed=sorted(task_brief_required),
        expected="query_plan",
    )

    policy = _mapping(ownership_plan.get("integration_policy"))
    _check(
        checks,
        check_id="ownership_policy_collapses_public_identity",
        ok=policy.get("public_identity") == "deep_context_federation" and policy.get("hide_upstream_tool_identity") is True,
        severity="error",
        detail="Ownership plan must collapse upstream tool identity into the DCF public identity.",
        observed={"public_identity": policy.get("public_identity"), "hide_upstream_tool_identity": policy.get("hide_upstream_tool_identity")},
        expected={"public_identity": "deep_context_federation", "hide_upstream_tool_identity": True},
    )

    capability_rows = _rows(ownership_plan.get("capabilities"))
    unknown = sorted(str(row.get("capability_id") or "") for row in capability_rows if row.get("known") is False)
    _check(
        checks,
        check_id="no_unknown_requested_functions",
        ok=not unknown,
        severity="error",
        detail="Unknown requested functions are not yet DCF-native capabilities.",
        observed=unknown,
        expected=[],
    )
    partial = sorted(str(row.get("capability_id") or "") for row in capability_rows if row.get("integration_status") == "native_partial")
    _check(
        checks,
        check_id="all_capabilities_fully_owned",
        ok=not partial,
        severity="error" if require_all_owned else "warn",
        detail="Native-partial capabilities remain integration work; use --require-all-owned to fail on them.",
        observed=partial,
        expected=[],
    )

    context_rows = _rows(context_index.get("rows"))
    context_policy = _mapping(context_index.get("source_identity_policy"))
    if context_index:
        _boundary_check(checks, "context_index", context_index)
        _check(
            checks,
            check_id="context_index_hides_source_identity",
            ok=context_policy.get("public_identity") == "deep_context_federation"
            and context_policy.get("source_ids_exposed") is False
            and context_policy.get("source_table_exposed") is False
            and not _has_source_identity_key(context_rows),
            severity="error",
            detail="Context index must expose DCF rows without public source identity keys.",
            observed={
                "public_identity": context_policy.get("public_identity"),
                "source_ids_exposed": context_policy.get("source_ids_exposed"),
                "source_table_exposed": context_policy.get("source_table_exposed"),
                "row_source_identity_keys_found": _has_source_identity_key(context_rows),
            },
            expected={"public_identity": "deep_context_federation", "source_ids_exposed": False, "source_table_exposed": False},
        )
        facets = sorted({str(row.get("facet") or "") for row in context_rows if row.get("facet")})
        missing_core_facets = sorted({"command", "capability"} - set(facets))
        _check(
            checks,
            check_id="context_index_has_function_facets",
            ok=len(facets) >= max(1, min_facets) and not missing_core_facets,
            severity="error",
            detail="Context index must include enough DCF facets plus command/capability rows to serve as a unified plane.",
            observed={"facets": facets, "missing_core_facets": missing_core_facets},
            expected={"min_facets": min_facets, "required_facets": ["command", "capability"]},
        )
    else:
        _check(
            checks,
            check_id="context_index_available",
            ok=False,
            severity="warn",
            detail="No context index was provided, so the audit cannot prove row-level unification.",
            observed="missing",
            expected="deep_context_federation_unified_index_v1",
        )

    working_rows = _rows(working_set.get("rows"))
    if working_set:
        _boundary_check(checks, "working_set", working_set)
        working_policy = _mapping(working_set.get("source_identity_policy"))
        _check(
            checks,
            check_id="working_set_hides_source_identity",
            ok=working_policy.get("public_identity") == "deep_context_federation"
            and working_policy.get("source_ids_exposed") is False
            and not _has_source_identity_key(working_rows),
            severity="error",
            detail="Working set must preserve DCF-only public identity for model read-first use.",
            observed={
                "public_identity": working_policy.get("public_identity"),
                "source_ids_exposed": working_policy.get("source_ids_exposed"),
                "row_source_identity_keys_found": _has_source_identity_key(working_rows),
            },
            expected={"public_identity": "deep_context_federation", "source_ids_exposed": False},
        )

    errors = [row for row in checks if not row["ok"] and row["severity"] == "error"]
    warnings = [row for row in checks if not row["ok"] and row["severity"] == "warn"]
    score = max(0, min(100, 100 - len(errors) * 25 - len(warnings) * 8))
    status = "fail_unified_plane_audit" if errors else "warn_unified_plane_audit" if warnings else "pass_unified_plane_audit"
    return {
        "schema_version": UNIFIED_PLANE_AUDIT_SCHEMA_VERSION,
        "ok": not errors,
        "status": status,
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": _utc_now(),
        "strict": {"require_all_owned": bool(require_all_owned), "min_facets": int(min_facets)},
        "summary": {
            "score": score,
            "check_count": len(checks),
            "error_count": len(errors),
            "warning_count": len(warnings),
            "capability_count": len(capability_rows),
            "native_partial_count": len(partial),
            "context_index_row_count": len(context_rows),
            "working_set_row_count": len(working_rows),
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
        },
    }


def _next_actions(*, errors: Sequence[Mapping[str, Any]], warnings: Sequence[Mapping[str, Any]]) -> list[str]:
    ids = {str(row.get("id") or "") for row in [*errors, *warnings]}
    actions: list[str] = []
    if "command_surface_uses_function_names" in ids:
        actions.append("rename_public_commands_to_function_names_and_keep_legacy_as_hidden_aliases")
    if "task_brief_has_machine_query_plan" in ids:
        actions.append("add_task_brief_query_plan_to_contract_and_builder")
    if "all_capabilities_fully_owned" in ids:
        actions.append("finish_native_partial_capabilities_or_run_without_require_all_owned")
    if "context_index_available" in ids:
        actions.append("run_build_context_index_and_reaudit_with_context_index")
    if "context_index_has_function_facets" in ids:
        actions.append("include_ability_registry_and_ownership_plan_when_building_context_index")
    if not actions:
        actions.append("continue_using_dcf_as_the_unified_read_only_context_plane")
    return actions


def markdown_unified_plane_audit(payload: Mapping[str, Any]) -> str:
    summary = _mapping(payload.get("summary"))
    lines = [
        "# Deep Context Federation Unified Plane Audit",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- OK: `{payload.get('ok')}`",
        f"- Score: `{summary.get('score')}`",
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
