"""Native capability integration planning for overlapping context tools."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

NATIVE_INTEGRATION_PLAN_SCHEMA_VERSION = "deep_context_federation_native_integration_plan_v1"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _norm(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


NATIVE_CAPABILITY_ROWS: dict[str, dict[str, Any]] = {
    "symbol_call_graph": {
        "capability_id": "symbol_call_graph",
        "capability_name": "Symbol and call graph intelligence",
        "absorbed_function_classes": ["symbol_indexing", "call_graph_navigation", "impact_navigation"],
        "dcf_native_owner": "repo_scan_symbol_dependency_graph",
        "dcf_commands": ["map-repo", "bootstrap-context", "assemble-context", "trace-context", "resolve-evidence", "rank-context", "query-context-store"],
        "native_surfaces": [
            "repo_code_symbols",
            "repo_dependency_graph",
            "edges.REFERENCES_SYMBOL",
            "sqlite.entities",
            "sqlite.edges",
        ],
        "integration_mode": "native_owned_capability",
        "integration_status": "native_available",
        "adapter_only": False,
        "source_of_record_boundary": "DCF owns the unified symbol/entity graph and query plane. Upstream observations are collapsed into DCF graph semantics.",
        "remaining_gap": "Deep language-specific call resolution can still be improved, but DCF already owns the symbol graph projection and query contract.",
        "exit_criteria": [
            "agent workflows call DCF trace-context/resolve-evidence/rank-context/query-context-store first",
            "symbol graph inputs are normalized into DCF entities and edges",
            "no wrapper reads a private symbol graph without DCF contract validation",
        ],
    },
    "surface_map": {
        "capability_id": "surface_map",
        "capability_name": "Project surface and split detection",
        "absorbed_function_classes": ["surface_mapping", "split_detection", "ownership_gap_detection"],
        "dcf_native_owner": "repo_scan_surface_map",
        "dcf_commands": ["map-repo", "bootstrap-context", "query-context", "diagnose-context", "gate-quality"],
        "native_surfaces": [
            "repo_surface_map",
            "query_presets.surface-splits",
            "conflicts.surface_owner_missing",
            "doctor.recommended_actions",
        ],
        "integration_mode": "native_owned_capability",
        "integration_status": "native_available",
        "adapter_only": False,
        "source_of_record_boundary": "DCF owns the canonical machine-readable surface map projection. Surface observations are collapsed into one DCF-facing truth plane.",
        "remaining_gap": "Project-specific owners can be made stricter by feeding repo-local policy files into DCF quality gates.",
        "exit_criteria": [
            "surface-split reviews use DCF query-context/diagnose-context output",
            "surface-map inputs are imported only as normalized DCF rows",
            "surface ownership gaps are reported by DCF conflicts",
        ],
    },
    "long_term_context_memory": {
        "capability_id": "long_term_context_memory",
        "capability_name": "Long-term context memory and reuse",
        "absorbed_function_classes": ["long_term_context_recall", "session_memory", "context_reuse"],
        "dcf_native_owner": "memory_ledger_fingerprint_agent_handoff",
        "dcf_commands": ["reuse-context", "assemble-context", "diff-context", "prepare-model-handoff", "prepare-model-input", "onboard-runner", "measure-token-efficiency"],
        "native_surfaces": [
            "memory_ledger",
            "reuse_index",
            "source_fingerprints",
            "sqlite read model",
            "architecture diff",
            "agent_handoff read plan",
            "agent_ready freshness gates",
        ],
        "integration_mode": "native_owned_capability",
        "integration_status": "native_available",
        "adapter_only": False,
        "source_of_record_boundary": "DCF owns the memory retrieval contract, reuse index, and freshness gates. Existing memory databases can be one-time import material, not a separate identity, live watcher, or authority.",
        "remaining_gap": "Retention and compaction policy can be tuned, but DCF now owns the native memory ledger contract.",
        "exit_criteria": [
            "accepted handoffs and fingerprints materialize into reuse-context rows",
            "fresh agents read DCF handoff/profile/onboard artifacts before private memory stores",
            "memory recall is bounded by DCF freshness and request-binding checks",
            "memory imports are one-shot, watcher-free, and collapsed into DCF-native records",
        ],
    },
    "evidence_lineage": {
        "capability_id": "evidence_lineage",
        "capability_name": "Evidence lineage and claim adjudication",
        "absorbed_function_classes": ["evidence_receipts", "current_truth_snapshot", "claim_lineage"],
        "dcf_native_owner": "resolve_adjudicate_review_gate",
        "dcf_commands": ["resolve-evidence", "adjudicate-evidence", "review-targets", "gate-target-review", "describe-contracts", "check-artifact"],
        "native_surfaces": [
            "entities.claim_id",
            "entities.artifact_id",
            "edges.SUPPORTS",
            "edges.DERIVES_FROM",
            "adjudication.support",
            "target_review.priority_order",
        ],
        "integration_mode": "native_owned_capability",
        "integration_status": "native_available",
        "adapter_only": False,
        "source_of_record_boundary": "DCF owns cross-artifact lineage queries and deterministic adjudication. Original evidence artifacts remain immutable audit inputs but are not exposed as competing DCF identities.",
        "remaining_gap": "More project-specific claim extractors can raise coverage, but DCF already owns the lineage query and gate semantics.",
        "exit_criteria": [
            "claim-lineage questions use DCF resolve-evidence/adjudicate-evidence",
            "all imported evidence artifacts pass DCF contract validation",
            "authority/advisory conflicts are surfaced as DCF conflicts",
        ],
    },
    "operator_projection": {
        "capability_id": "operator_projection",
        "capability_name": "Operator projection and current truth cockpit",
        "absorbed_function_classes": ["governance_projection", "current_truth_projection", "blocker_cockpit"],
        "dcf_native_owner": "agent_ready_capabilities_query_gate",
        "dcf_commands": ["describe-abilities", "query-context", "diagnose-context", "prepare-model-input", "onboard-runner", "gate-quality"],
        "native_surfaces": [
            "capabilities manifest",
            "query_presets.operator-projection",
            "doctor health",
            "agent_ready model input gate",
            "quality_gate policy",
        ],
        "integration_mode": "native_owned_capability",
        "integration_status": "native_partial",
        "adapter_only": False,
        "source_of_record_boundary": "DCF owns the agent/operator read model and gating view. Project dashboards may render DCF output but should not maintain a divergent projection contract or identity.",
        "remaining_gap": "Add first-class DCF cockpit summary rows for active blockers, dirty lanes, and current truth drift.",
        "exit_criteria": [
            "operators and agents start from DCF describe-abilities/prepare-model-input output",
            "dashboard claims are checked against DCF query and quality gates",
            "current truth snapshots are normalized into DCF rows instead of queried separately by agents",
        ],
    },
    "workflow_orchestration": {
        "capability_id": "workflow_orchestration",
        "capability_name": "Agent workflow orchestration and handoff",
        "absorbed_function_classes": ["agent_launch", "prompt_packaging", "session_handoff"],
        "dcf_native_owner": "agent_profile_onboard_ready_handoff",
        "dcf_commands": ["init-run-profile", "validate-run-profile", "onboard-runner", "prepare-model-input", "prepare-model-handoff", "emit-model-input"],
        "native_surfaces": [
            "agent_profile",
            "agent_onboard",
            "agent_ready",
            "agent_handoff",
            "agent_model_input",
            "request_binding",
            "input_fingerprint",
        ],
        "integration_mode": "native_owned_capability",
        "integration_status": "native_available",
        "adapter_only": False,
        "source_of_record_boundary": "DCF owns the launch contract, freshness checks, token budget, and model prompt emission. Shell wrappers should call DCF rather than reimplement readiness logic.",
        "remaining_gap": "Global wrappers should be simplified until they only invoke DCF and display its pass/fail result.",
        "exit_criteria": [
            "new agent sessions use onboard-runner or prepare-model-input",
            "manual prompt packs are replaced by prepare-model-handoff model_prompt_source",
            "wrappers emit no model prompt when DCF gates fail",
        ],
    },
}

ALIASES = {
    "symbol_graph": "symbol_call_graph",
    "call_graph": "symbol_call_graph",
    "impact_navigation": "symbol_call_graph",
    "surface_split_detection": "surface_map",
    "context_memory": "long_term_context_memory",
    "memory_import": "long_term_context_memory",
    "claim_lineage": "evidence_lineage",
    "evidence_receipts": "evidence_lineage",
    "current_truth_projection": "operator_projection",
    "governance_projection": "operator_projection",
    "agent_handoff": "workflow_orchestration",
    "agent_launch": "workflow_orchestration",
}


def _row_for_request(requested: str) -> dict[str, Any]:
    key = _norm(requested)
    capability_id = ALIASES.get(key, key)
    if capability_id in NATIVE_CAPABILITY_ROWS:
        row = dict(NATIVE_CAPABILITY_ROWS[capability_id])
        row["known"] = True
        row["input_identity_collapsed"] = True
        return row
    return {
        "capability_id": capability_id,
        "capability_name": capability_id,
        "known": False,
        "input_identity_collapsed": True,
        "absorbed_function_classes": ["unclassified_context_tool"],
        "dcf_native_owner": "manual_review_required",
        "dcf_commands": [],
        "native_surfaces": [],
        "integration_mode": "manual_native_design_required",
        "integration_status": "manual_review",
        "adapter_only": False,
        "source_of_record_boundary": "Unknown capability. DCF should collapse it into a native capability only after a native design review.",
        "remaining_gap": "Define the DCF-owned query/index/governance function before adopting or retiring this tool.",
        "exit_criteria": [
            "native owner command is named",
            "machine-readable artifact contract is registered",
            "safety boundary and validation path are documented",
        ],
    }


def build_native_integration_plan(*, capabilities: Iterable[str] | None = None) -> dict[str, Any]:
    requested = [item for item in (capabilities or []) if str(item).strip()]
    if requested:
        rows = [_row_for_request(item) for item in requested]
    else:
        rows = [dict(row, known=True, input_identity_collapsed=True) for row in NATIVE_CAPABILITY_ROWS.values()]
    status_counts = Counter(str(row["integration_status"]) for row in rows)
    partial_rows = [row for row in rows if row["integration_status"] in {"native_partial", "manual_review"}]
    adapter_only_rows = [row for row in rows if row.get("adapter_only")]
    ok = not adapter_only_rows
    return {
        "schema_version": NATIVE_INTEGRATION_PLAN_SCHEMA_VERSION,
        "ok": ok,
        "status": "warn_native_integration_plan" if partial_rows else "pass_native_integration_plan",
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": _utc_now(),
        "integration_policy": {
            "public_identity": "deep_context_federation",
            "hide_upstream_tool_identity": True,
            "upstream_provenance_retained_for_audit_only": True,
            "default_mode": "native_owned_capability",
            "adapter_only_allowed": False,
            "consume_only_allowed": False,
            "upstream_inputs_may_contribute_observations": True,
            "dcf_owns_query_index_governance_and_model_handoff": True,
            "original_evidence_records_are_not_overwritten": True,
        },
        "summary": {
            "capability_count": len(rows),
            "native_available_count": status_counts.get("native_available", 0),
            "native_partial_count": status_counts.get("native_partial", 0),
            "manual_review_count": status_counts.get("manual_review", 0),
            "adapter_only_count": len(adapter_only_rows),
            "status_counts": dict(sorted(status_counts.items())),
        },
        "capabilities": rows,
        "nativeization_sequence": [
            {
                "step": "orchestration_entrypoint",
                "goal": "All agents start through DCF onboard-runner or prepare-model-input.",
                "owner_capability": "workflow_orchestration",
                "exit_gate": "agent_onboard and agent_ready artifacts validate and emit prompt only after gates pass",
            },
            {
                "step": "surface_and_symbol_unification",
                "goal": "Surface and symbol questions resolve through DCF query/trace/resolve, not private tool outputs.",
                "owner_capability": "surface_map + symbol_call_graph",
                "exit_gate": "map-repo/bootstrap-context/assemble-context/verify-context pass with repo_surface_map and repo_code_symbols present",
            },
            {
                "step": "claim_evidence_lineage",
                "goal": "Claims, current truth, and evidence receipts are joined through DCF resolve/adjudicate.",
                "owner_capability": "evidence_lineage",
                "exit_gate": "target review and review gate pass for selected claims",
            },
            {
                "step": "native_memory_ledger",
                "goal": "Accepted handoffs and context fingerprints become DCF-native reusable memory.",
                "owner_capability": "long_term_context_memory",
                "exit_gate": "reuse-context emits reusable rows with fingerprint-bound prompt sources",
            },
            {
                "step": "operator_projection_convergence",
                "goal": "Dashboards and agents render the same DCF current context contract.",
                "owner_capability": "operator_projection",
                "exit_gate": "operator-projection query and quality gate cover blockers, dirty lanes, and current truth drift",
            },
        ],
        "safety_boundaries": {
            "user_facing_source_identity_collapsed_to_dcf": True,
            "does_not_install_external_tools": True,
            "does_not_start_watchers": True,
            "does_not_mutate_source_authority": True,
            "does_not_replace_broker_order_or_live_runtime_authority": True,
            "does_not_overwrite_original_evidence_records": True,
            "upstream_inputs_require_dcf_normalization": True,
        },
    }


def markdown_native_integration_plan(payload: Mapping[str, Any]) -> str:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    lines = [
        "# DCF Native Integration Plan",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- OK: `{payload.get('ok')}`",
        f"- Capabilities: `{summary.get('capability_count', 0)}`",
        f"- Native available: `{summary.get('native_available_count', 0)}`",
        f"- Native partial: `{summary.get('native_partial_count', 0)}`",
        f"- Adapter-only: `{summary.get('adapter_only_count', 0)}`",
        "",
        "## Capabilities",
    ]
    for row in payload.get("capabilities") or []:
        if not isinstance(row, Mapping):
            continue
        lines.extend(
            [
                f"- `{row.get('capability_id')}` status=`{row.get('integration_status')}` mode=`{row.get('integration_mode')}` owner=`{row.get('dcf_native_owner')}`",
                f"  - absorbed function classes: `{', '.join(str(item) for item in row.get('absorbed_function_classes') or [])}`",
                f"  - gap: {row.get('remaining_gap')}",
            ]
        )
    lines.append("")
    lines.append("## Nativeization Sequence")
    for step in payload.get("nativeization_sequence") or []:
        if not isinstance(step, Mapping):
            continue
        lines.append(f"- `{step.get('step')}`: {step.get('goal')} gate=`{step.get('exit_gate')}`")
    return "\n".join(lines) + "\n"
