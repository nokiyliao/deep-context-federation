"""JSON Schema registry and lightweight contract validation for DCF artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from deep_context_federation.adjudicate import ADJUDICATE_SCHEMA_VERSION
from deep_context_federation.agent_context import AGENT_CONTEXT_SCHEMA_VERSION
from deep_context_federation.agent_context_gate import AGENT_CONTEXT_GATE_POLICY_SCHEMA_VERSION
from deep_context_federation.agent_context_gate import AGENT_CONTEXT_GATE_SCHEMA_VERSION
from deep_context_federation.agent_ci import AGENT_CI_SCHEMA_VERSION
from deep_context_federation.agent_discover import AGENT_DISCOVERY_SCHEMA_VERSION
from deep_context_federation.agent_handoff import AGENT_HANDOFF_SCHEMA_VERSION
from deep_context_federation.agent_handoff_verify import AGENT_HANDOFF_VERIFICATION_SCHEMA_VERSION
from deep_context_federation.agent_model_input import AGENT_MODEL_INPUT_SCHEMA_VERSION
from deep_context_federation.agent_onboard import AGENT_ONBOARD_SCHEMA_VERSION
from deep_context_federation.agent_profile import AGENT_PROFILE_SCHEMA_VERSION
from deep_context_federation.agent_profile import AGENT_PROFILE_VALIDATION_SCHEMA_VERSION
from deep_context_federation.agent_profile_init import AGENT_PROFILE_INIT_SCHEMA_VERSION
from deep_context_federation.agent_ready import AGENT_READY_SCHEMA_VERSION
from deep_context_federation.agent_route import AGENT_ROUTE_SCHEMA_VERSION
from deep_context_federation.bootstrap import BOOTSTRAP_SCHEMA_VERSION
from deep_context_federation.builder import MANIFEST_SCHEMA
from deep_context_federation.builder import SCHEMA_VERSION
from deep_context_federation.capabilities import CAPABILITIES_SCHEMA_VERSION
from deep_context_federation.compose import COMPOSE_SCHEMA_VERSION
from deep_context_federation.context_pack import CONTEXT_PACK_SCHEMA_VERSION
from deep_context_federation.efficiency_gate import EFFICIENCY_GATE_POLICY_SCHEMA_VERSION
from deep_context_federation.efficiency_gate import EFFICIENCY_GATE_SCHEMA_VERSION
from deep_context_federation.efficiency_report import EFFICIENCY_REPORT_SCHEMA_VERSION
from deep_context_federation.intake import AGENT_INTAKE_SCHEMA_VERSION
from deep_context_federation.input_fingerprint import INPUT_FINGERPRINT_COMPARE_SCHEMA_VERSION
from deep_context_federation.input_fingerprint import INPUT_FINGERPRINT_SCHEMA_VERSION
from deep_context_federation.memory_ledger import MEMORY_LEDGER_SCHEMA_VERSION
from deep_context_federation.native_integration import NATIVE_INTEGRATION_PLAN_SCHEMA_VERSION
from deep_context_federation.quality_gate import QUALITY_GATE_POLICY_SCHEMA_VERSION
from deep_context_federation.quality_gate import QUALITY_GATE_SCHEMA_VERSION
from deep_context_federation.query import QUERY_SCHEMA_VERSION
from deep_context_federation.resolve import RESOLVE_SCHEMA_VERSION
from deep_context_federation.scanner import SCAN_SCHEMA_VERSION
from deep_context_federation.target_review import TARGET_REVIEW_SCHEMA_VERSION
from deep_context_federation.target_review_gate import TARGET_REVIEW_GATE_POLICY_SCHEMA_VERSION
from deep_context_federation.target_review_gate import TARGET_REVIEW_GATE_SCHEMA_VERSION
from deep_context_federation.task_brief import TASK_BRIEF_SCHEMA_VERSION
from deep_context_federation.unified_plane_audit import UNIFIED_PLANE_AUDIT_SCHEMA_VERSION
from deep_context_federation.unified_index import UNIFIED_INDEX_SCHEMA_VERSION
from deep_context_federation.unified_index import UNIFIED_WORKING_SET_SCHEMA_VERSION
from deep_context_federation.verifier import VERIFY_SCHEMA_VERSION
from deep_context_federation.workflow_plan import WORKFLOW_PLAN_SCHEMA_VERSION
from deep_context_federation.workflow_run import WORKFLOW_RUN_SCHEMA_VERSION

SCHEMA_REGISTRY_SCHEMA_VERSION = "deep_context_federation_schema_registry_v1"
CONTRACT_VALIDATION_SCHEMA_VERSION = "deep_context_federation_contract_validation_v1"
JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _schema(schema_version: str, title: str, required: list[str], properties: dict[str, Any]) -> dict[str, Any]:
    props = {
        "schema_version": {"type": "string", "const": schema_version},
        **properties,
    }
    return {
        "$schema": JSON_SCHEMA_DIALECT,
        "$id": f"https://deep-context-federation.local/schemas/{schema_version}.json",
        "title": title,
        "type": "object",
        "required": required,
        "additionalProperties": True,
        "properties": props,
    }


def _boundary_props() -> dict[str, Any]:
    return {
        "authority_effect": {"type": "string", "const": "none"},
        "no_apply": {"type": "boolean", "const": True},
    }


def _artifact_schemas() -> dict[str, dict[str, Any]]:
    object_type = {"type": "object"}
    array_type = {"type": "array"}
    return {
        "schema_registry": _schema(
            SCHEMA_REGISTRY_SCHEMA_VERSION,
            "Deep Context Federation schema registry",
            ["schema_version", "status", "authority_effect", "no_apply", "artifact_schemas", "summary"],
            {
                "status": {"type": "string", "const": "ok"},
                **_boundary_props(),
                "artifact_schemas": array_type,
                "summary": object_type,
            },
        ),
        "contract_validation": _schema(
            CONTRACT_VALIDATION_SCHEMA_VERSION,
            "Deep Context Federation contract validation result",
            ["schema_version", "ok", "status", "authority_effect", "no_apply", "checks", "errors"],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string"},
                **_boundary_props(),
                "artifact_kind": {"type": "string"},
                "checks": array_type,
                "errors": array_type,
            },
        ),
        "capabilities": _schema(
            CAPABILITIES_SCHEMA_VERSION,
            "Deep Context Federation capabilities manifest",
            ["schema_version", "status", "authority_effect", "no_apply", "package", "contracts", "commands"],
            {
                "status": {"type": "string", "const": "ok"},
                **_boundary_props(),
                "package": object_type,
                "contracts": object_type,
                "commands": array_type,
                "query_presets": array_type,
                "sql_presets": array_type,
                "safety_boundaries": object_type,
            },
        ),
        "native_integration_plan": _schema(
            NATIVE_INTEGRATION_PLAN_SCHEMA_VERSION,
            "Deep Context Federation native capability integration plan",
            [
                "schema_version",
                "ok",
                "status",
                "authority_effect",
                "no_apply",
                "integration_policy",
                "summary",
                "capabilities",
                "nativeization_sequence",
                "safety_boundaries",
            ],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string", "enum": ["pass_native_integration_plan", "warn_native_integration_plan"]},
                **_boundary_props(),
                "generated_at": {"type": "string"},
                "integration_policy": object_type,
                "summary": object_type,
                "capabilities": array_type,
                "nativeization_sequence": array_type,
                "safety_boundaries": object_type,
            },
        ),
        "unified_plane_audit": _schema(
            UNIFIED_PLANE_AUDIT_SCHEMA_VERSION,
            "Deep Context Federation unified plane audit",
            [
                "schema_version",
                "ok",
                "status",
                "authority_effect",
                "no_apply",
                "summary",
                "checks",
                "errors",
                "warnings",
                "safety_boundaries",
            ],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string", "enum": ["pass_unified_plane_audit", "warn_unified_plane_audit", "fail_unified_plane_audit"]},
                **_boundary_props(),
                "generated_at": {"type": "string"},
                "strict": object_type,
                "summary": object_type,
                "checks": array_type,
                "errors": array_type,
                "warnings": array_type,
                "next_actions": array_type,
                "safety_boundaries": object_type,
            },
        ),
        "memory_ledger": _schema(
            MEMORY_LEDGER_SCHEMA_VERSION,
            "Deep Context Federation native memory ledger",
            [
                "schema_version",
                "ok",
                "status",
                "authority_effect",
                "no_apply",
                "summary",
                "rows",
                "reuse_index",
                "safety_boundaries",
            ],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string", "enum": ["pass_memory_ledger", "warn_memory_ledger"]},
                **_boundary_props(),
                "generated_at": {"type": "string"},
                "root": {"type": "string"},
                "inputs": object_type,
                "summary": object_type,
                "rows": array_type,
                "reuse_index": array_type,
                "input_fingerprint_digests": array_type,
                "warnings": array_type,
                "errors": array_type,
                "safety_boundaries": object_type,
            },
        ),
        "unified_index": _schema(
            UNIFIED_INDEX_SCHEMA_VERSION,
            "Deep Context Federation source-collapsed unified context index",
            [
                "schema_version",
                "ok",
                "status",
                "authority_effect",
                "no_apply",
                "source_identity_policy",
                "summary",
                "rows",
                "safety_boundaries",
            ],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string", "enum": ["pass_unified_index", "warn_unified_index"]},
                **_boundary_props(),
                "generated_at": {"type": "string"},
                "query": {"type": "string"},
                "limit": {"type": "integer"},
                "inputs": object_type,
                "summary": object_type,
                "source_identity_policy": object_type,
                "rows": array_type,
                "warnings": array_type,
                "safety_boundaries": object_type,
            },
        ),
        "unified_working_set": _schema(
            UNIFIED_WORKING_SET_SCHEMA_VERSION,
            "Deep Context Federation selected compact working set",
            [
                "schema_version",
                "ok",
                "status",
                "authority_effect",
                "no_apply",
                "optimization_policy",
                "source_identity_policy",
                "summary",
                "rows",
                "expansion_plan",
                "safety_boundaries",
            ],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string", "enum": ["pass_unified_working_set", "warn_unified_working_set"]},
                **_boundary_props(),
                "generated_at": {"type": "string"},
                "query": {"type": "string"},
                "limit": {"type": "integer"},
                "inputs": object_type,
                "summary": object_type,
                "optimization_policy": object_type,
                "source_identity_policy": object_type,
                "rows": array_type,
                "expansion_plan": object_type,
                "warnings": array_type,
                "safety_boundaries": object_type,
            },
        ),
        "manifest": _schema(
            MANIFEST_SCHEMA,
            "Deep Context Federation input manifest",
            ["schema_version", "authority_boundary", "sources"],
            {
                "authority_boundary": object_type,
                "sources": array_type,
                "metadata": object_type,
            },
        ),
        "federation": _schema(
            SCHEMA_VERSION,
            "Deep Context Federation artifact",
            [
                "schema_version",
                "status",
                "ok",
                "authority_effect",
                "no_apply",
                "sources",
                "entities",
                "edges",
                "conflicts",
                "query_presets",
                "summary",
            ],
            {
                "status": {"type": "string"},
                "ok": {"type": "boolean"},
                **_boundary_props(),
                "mutation_guard": object_type,
                "sources": array_type,
                "entities": array_type,
                "edges": array_type,
                "conflicts": array_type,
                "query_presets": object_type,
                "summary": object_type,
                "outputs": object_type,
            },
        ),
        "repo_scan": _schema(
            SCAN_SCHEMA_VERSION,
            "Deep Context Federation repository scan result",
            ["schema_version", "ok", "status", "authority_effect", "no_apply", "summary", "outputs"],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string"},
                **_boundary_props(),
                "summary": object_type,
                "outputs": object_type,
            },
        ),
        "bootstrap": _schema(
            BOOTSTRAP_SCHEMA_VERSION,
            "Deep Context Federation bootstrap result",
            ["schema_version", "ok", "status", "authority_effect", "no_apply", "scan", "build", "verify", "doctor", "outputs"],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string"},
                **_boundary_props(),
                "scan": object_type,
                "compose": {"type": ["object", "null"]},
                "build": object_type,
                "verify": object_type,
                "doctor": object_type,
                "outputs": object_type,
            },
        ),
        "quality_gate_policy": _schema(
            QUALITY_GATE_POLICY_SCHEMA_VERSION,
            "Deep Context Federation quality gate policy",
            ["schema_version", "authority_effect", "no_apply"],
            {
                **_boundary_props(),
                "policy_id": {"type": "string"},
                "description": {"type": "string"},
                "min_sources": {"type": "integer"},
                "min_entities": {"type": "integer"},
                "min_edges": {"type": "integer"},
                "max_errors": {"type": "integer"},
                "max_warnings": {"type": "integer"},
                "max_duration_seconds": {"type": ["number", "null"]},
                "max_scan_duration_seconds": {"type": ["number", "null"]},
                "require_roles": array_type,
                "require_sources": array_type,
                "require_query_presets": array_type,
                "require_bootstrap_steps": {"type": "boolean"},
            },
        ),
        "quality_gate": _schema(
            QUALITY_GATE_SCHEMA_VERSION,
            "Deep Context Federation quality gate result",
            ["schema_version", "ok", "status", "authority_effect", "no_apply", "policy", "checks", "errors", "summary"],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string"},
                **_boundary_props(),
                "policy": object_type,
                "checks": array_type,
                "errors": array_type,
                "summary": object_type,
            },
        ),
        "manifest_compose": _schema(
            COMPOSE_SCHEMA_VERSION,
            "Deep Context Federation manifest compose result",
            ["schema_version", "ok", "status", "authority_effect", "no_apply", "summary"],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string"},
                **_boundary_props(),
                "summary": object_type,
                "conflicts": array_type,
                "composed_manifest": object_type,
            },
        ),
        "verify": _schema(
            VERIFY_SCHEMA_VERSION,
            "Deep Context Federation verification result",
            ["schema_version", "ok", "status", "checks", "errors"],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string"},
                "checks": array_type,
                "errors": array_type,
            },
        ),
        "query": _schema(
            QUERY_SCHEMA_VERSION,
            "Deep Context Federation query result",
            ["schema_version", "preset", "status", "row_count", "rows"],
            {
                "preset": {"type": "string"},
                "status": {"type": "string"},
                "row_count": {"type": "integer"},
                "rows": array_type,
                "source_snapshot": object_type,
            },
        ),
        "resolve": _schema(
            RESOLVE_SCHEMA_VERSION,
            "Deep Context Federation target evidence resolver",
            [
                "schema_version",
                "status",
                "authority_effect",
                "no_apply",
                "target",
                "summary",
                "matched_entities",
                "related_sources",
                "related_edges",
                "related_conflicts",
            ],
            {
                "status": {"type": "string", "enum": ["matched", "warn", "no_match"]},
                **_boundary_props(),
                "target": {"type": "string"},
                "terms": array_type,
                "source_snapshot": object_type,
                "summary": object_type,
                "matched_entities": array_type,
                "related_sources": array_type,
                "related_edges": array_type,
                "related_conflicts": array_type,
                "context_pack": object_type,
                "prompt_text": {"type": "string"},
                "prompt_estimated_tokens": {"type": "integer"},
                "prompt_rendered_counts": object_type,
                "recommended_commands": array_type,
            },
        ),
        "adjudication": _schema(
            ADJUDICATE_SCHEMA_VERSION,
            "Deep Context Federation deterministic target adjudication",
            [
                "schema_version",
                "status",
                "authority_effect",
                "no_apply",
                "target",
                "verdict",
                "confidence_score",
                "support",
                "conflict_summary",
                "recommended_use",
            ],
            {
                "status": {"type": "string", "const": "ok"},
                **_boundary_props(),
                "target": {"type": "string"},
                "verdict": {"type": "string", "enum": ["supported", "warn", "blocked", "advisory_only", "no_match"]},
                "confidence_score": {"type": "integer"},
                "risk_flags": array_type,
                "support": object_type,
                "conflict_summary": object_type,
                "resolve_summary": object_type,
                "resolve": object_type,
                "recommended_use": object_type,
                "prompt_text": {"type": "string"},
                "prompt_estimated_tokens": {"type": "integer"},
            },
        ),
        "target_review": _schema(
            TARGET_REVIEW_SCHEMA_VERSION,
            "Deep Context Federation batch target review",
            [
                "schema_version",
                "status",
                "authority_effect",
                "no_apply",
                "target_count",
                "reviewed_count",
                "summary",
                "rows",
                "priority_order",
            ],
            {
                "status": {"type": "string", "enum": ["pass", "warn", "blocked"]},
                **_boundary_props(),
                "target_count": {"type": "integer"},
                "reviewed_count": {"type": "integer"},
                "summary": object_type,
                "rows": array_type,
                "priority_order": array_type,
                "adjudications": array_type,
                "recommended_next_targets": array_type,
                "prompt_text": {"type": "string"},
                "prompt_estimated_tokens": {"type": "integer"},
            },
        ),
        "target_review_gate_policy": _schema(
            TARGET_REVIEW_GATE_POLICY_SCHEMA_VERSION,
            "Deep Context Federation target review gate policy",
            ["schema_version", "authority_effect", "no_apply"],
            {
                **_boundary_props(),
                "policy_id": {"type": "string"},
                "description": {"type": "string"},
                "max_blocked": {"type": ["integer", "null"]},
                "max_no_match": {"type": ["integer", "null"]},
                "max_advisory_only": {"type": ["integer", "null"]},
                "max_warn": {"type": ["integer", "null"]},
                "max_priority_score": {"type": ["integer", "null"]},
                "min_average_confidence": {"type": ["number", "null"]},
                "disallow_risk_flags": array_type,
                "require_targets": array_type,
            },
        ),
        "target_review_gate": _schema(
            TARGET_REVIEW_GATE_SCHEMA_VERSION,
            "Deep Context Federation target review gate",
            ["schema_version", "ok", "status", "authority_effect", "no_apply", "policy", "checks", "errors", "summary"],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string", "enum": ["pass_target_review_gate", "fail_target_review_gate"]},
                **_boundary_props(),
                "policy": object_type,
                "error_count": {"type": "integer"},
                "checks": array_type,
                "errors": array_type,
                "summary": object_type,
            },
        ),
        "context_pack": _schema(
            CONTEXT_PACK_SCHEMA_VERSION,
            "Deep Context Federation token-aware context pack",
            [
                "schema_version",
                "status",
                "authority_effect",
                "no_apply",
                "task",
                "token_budget",
                "estimated_tokens",
                "prompt_estimated_tokens",
                "prompt_text",
                "coverage",
                "rows",
                "summary",
            ],
            {
                "status": {"type": "string", "const": "ok"},
                **_boundary_props(),
                "task": {"type": "string"},
                "token_budget": {"type": "integer"},
                "estimated_tokens": {"type": "integer"},
                "prompt_estimated_tokens": {"type": "integer"},
                "prompt_text": {"type": "string"},
                "json_estimated_tokens": {"type": "integer"},
                "original_estimated_tokens": {"type": "integer"},
                "estimated_token_savings": {"type": "integer"},
                "compression_ratio": {"type": "number"},
                "budget_utilization": {"type": "number"},
                "coverage": object_type,
                "rows": array_type,
                "dropped": array_type,
                "summary": object_type,
            },
        ),
        "task_brief": _schema(
            TASK_BRIEF_SCHEMA_VERSION,
            "Deep Context Federation task routing brief",
            [
                "schema_version",
                "status",
                "authority_effect",
                "no_apply",
                "task",
                "selected_presets",
                "doctor_summary",
                "context_budget",
                "coverage",
                "context_pack",
                "query_plan",
                "recommended_commands",
                "safety_boundaries",
            ],
            {
                "status": {"type": "string", "enum": ["ready", "warn", "blocked"]},
                **_boundary_props(),
                "task": {"type": "string"},
                "terms": array_type,
                "source_snapshot": object_type,
                "selected_presets": array_type,
                "routed_queries": array_type,
                "doctor_summary": object_type,
                "context_budget": object_type,
                "coverage": object_type,
                "context_pack": object_type,
                "query_plan": object_type,
                "recommended_commands": array_type,
                "safety_boundaries": object_type,
            },
        ),
        "agent_intake": _schema(
            AGENT_INTAKE_SCHEMA_VERSION,
            "Deep Context Federation agent intake packet",
            [
                "schema_version",
                "ok",
                "status",
                "authority_effect",
                "no_apply",
                "task",
                "bootstrap_summary",
                "quality_gate_summary",
                "task_brief_summary",
                "quality_gate",
                "task_brief",
                "outputs",
                "safety_boundaries",
            ],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string", "enum": ["pass_agent_intake", "warn_agent_intake", "fail_agent_intake"]},
                **_boundary_props(),
                "task": {"type": "string"},
                "root": {"type": "string"},
                "output_dir": {"type": "string"},
                "duration_seconds": {"type": "number"},
                "bootstrap_summary": object_type,
                "quality_gate_summary": object_type,
                "task_brief_summary": object_type,
                "quality_gate": object_type,
                "task_brief": object_type,
                "next_actions": array_type,
                "outputs": object_type,
                "safety_boundaries": object_type,
            },
        ),
        "workflow_plan": _schema(
            WORKFLOW_PLAN_SCHEMA_VERSION,
            "Deep Context Federation workflow plan",
            [
                "schema_version",
                "status",
                "authority_effect",
                "no_apply",
                "task",
                "steps",
                "gates",
                "token_efficiency",
                "safety_boundaries",
            ],
            {
                "status": {"type": "string", "enum": ["ready_with_targets", "ready_no_targets"]},
                **_boundary_props(),
                "task": {"type": "string"},
                "root": {"type": "string"},
                "output_dir": {"type": "string"},
                "targets": array_type,
                "target_count": {"type": "integer"},
                "steps": array_type,
                "gates": array_type,
                "warnings": array_type,
                "token_efficiency": object_type,
                "outputs": object_type,
                "safety_boundaries": object_type,
                "prompt_text": {"type": "string"},
                "prompt_estimated_tokens": {"type": "integer"},
                "json_estimated_tokens": {"type": "integer"},
            },
        ),
        "workflow_run": _schema(
            WORKFLOW_RUN_SCHEMA_VERSION,
            "Deep Context Federation workflow run",
            [
                "schema_version",
                "ok",
                "status",
                "authority_effect",
                "no_apply",
                "task",
                "step_results",
                "model_handoff",
                "outputs",
                "safety_boundaries",
            ],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string", "enum": ["pass_workflow_run", "warn_workflow_run", "fail_workflow_run"]},
                **_boundary_props(),
                "task": {"type": "string"},
                "root": {"type": "string"},
                "output_dir": {"type": "string"},
                "duration_seconds": {"type": "number"},
                "targets": array_type,
                "target_count": {"type": "integer"},
                "workflow_plan_summary": object_type,
                "step_results": array_type,
                "model_handoff": object_type,
                "outputs": object_type,
                "safety_boundaries": object_type,
                "prompt_text": {"type": "string"},
                "prompt_estimated_tokens": {"type": "integer"},
                "json_estimated_tokens": {"type": "integer"},
            },
        ),
        "efficiency_report": _schema(
            EFFICIENCY_REPORT_SCHEMA_VERSION,
            "Deep Context Federation efficiency report",
            [
                "schema_version",
                "ok",
                "status",
                "authority_effect",
                "no_apply",
                "workflow_run_ref",
                "artifacts",
                "model_context_budget",
                "safety_boundaries",
            ],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string", "enum": ["pass_efficiency_report", "warn_efficiency_report", "fail_efficiency_report"]},
                **_boundary_props(),
                "workflow_run_ref": {"type": "string"},
                "workflow_run_status": {"type": "string"},
                "task": {"type": "string"},
                "artifact_count": {"type": "integer"},
                "artifacts": array_type,
                "model_context_budget": object_type,
                "missing_required_artifacts": array_type,
                "warnings": array_type,
                "recommendations": array_type,
                "safety_boundaries": object_type,
                "json_estimated_tokens": {"type": "integer"},
            },
        ),
        "efficiency_gate_policy": _schema(
            EFFICIENCY_GATE_POLICY_SCHEMA_VERSION,
            "Deep Context Federation efficiency gate policy",
            ["schema_version", "authority_effect", "no_apply"],
            {
                **_boundary_props(),
                "policy_id": {"type": "string"},
                "description": {"type": "string"},
                "require_report_ok": {"type": "boolean"},
                "max_missing_required": {"type": ["integer", "null"]},
                "max_warnings": {"type": ["integer", "null"]},
                "min_baseline_tokens": {"type": ["integer", "null"]},
                "max_read_first_tokens": {"type": ["integer", "null"]},
                "max_gate_pass_tokens": {"type": ["integer", "null"]},
                "max_read_first_ratio": {"type": ["number", "null"]},
                "max_gate_pass_ratio": {"type": ["number", "null"]},
                "min_read_first_savings_percent": {"type": ["number", "null"]},
                "min_gate_pass_savings_percent": {"type": ["number", "null"]},
                "require_artifact_roles": array_type,
            },
        ),
        "efficiency_gate": _schema(
            EFFICIENCY_GATE_SCHEMA_VERSION,
            "Deep Context Federation efficiency gate",
            ["schema_version", "ok", "status", "authority_effect", "no_apply", "policy", "checks", "errors", "summary"],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string", "enum": ["pass_efficiency_gate", "fail_efficiency_gate"]},
                **_boundary_props(),
                "policy": object_type,
                "check_count": {"type": "integer"},
                "error_count": {"type": "integer"},
                "checks": array_type,
                "errors": array_type,
                "summary": object_type,
            },
        ),
        "agent_ci": _schema(
            AGENT_CI_SCHEMA_VERSION,
            "Deep Context Federation agent continuation decision",
            [
                "schema_version",
                "ok",
                "status",
                "authority_effect",
                "no_apply",
                "decision",
                "workflow_run_summary",
                "efficiency_report_summary",
                "efficiency_gate_summary",
                "contract_validation_summary",
                "contract_validations",
                "next_reads",
                "artifact_read_plan",
                "outputs",
                "safety_boundaries",
            ],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string", "enum": ["pass_agent_ci", "warn_agent_ci", "fail_agent_ci"]},
                **_boundary_props(),
                "task": {"type": "string"},
                "root": {"type": "string"},
                "output_dir": {"type": "string"},
                "duration_seconds": {"type": "number"},
                "targets": array_type,
                "decision": object_type,
                "workflow_run_summary": object_type,
                "efficiency_report_summary": object_type,
                "efficiency_gate_summary": object_type,
                "contract_validation_summary": object_type,
                "contract_validations": object_type,
                "next_reads": object_type,
                "artifact_read_plan": object_type,
                "outputs": object_type,
                "safety_boundaries": object_type,
                "prompt_text": {"type": "string"},
                "prompt_estimated_tokens": {"type": "integer"},
                "json_estimated_tokens": {"type": "integer"},
            },
        ),
        "agent_context": _schema(
            AGENT_CONTEXT_SCHEMA_VERSION,
            "Deep Context Federation agent context bundle",
            [
                "schema_version",
                "ok",
                "status",
                "authority_effect",
                "no_apply",
                "input_ref",
                "mode",
                "summary",
                "sections",
                "skipped",
                "safety_boundaries",
            ],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string", "enum": ["pass_agent_context", "warn_agent_context", "fail_agent_context"]},
                **_boundary_props(),
                "input_ref": {"type": "string"},
                "mode": {"type": "string", "enum": ["read-first", "decision-allowed", "all"]},
                "task": {"type": "string"},
                "decision": object_type,
                "token_budget": {"type": "integer"},
                "max_artifact_tokens": {"type": "integer"},
                "include_content": {"type": "boolean"},
                "source_contract_validation": object_type,
                "summary": object_type,
                "sections": array_type,
                "skipped": array_type,
                "safety_boundaries": object_type,
                "prompt_text": {"type": "string"},
                "prompt_estimated_tokens": {"type": "integer"},
                "json_estimated_tokens": {"type": "integer"},
            },
        ),
        "agent_context_gate_policy": _schema(
            AGENT_CONTEXT_GATE_POLICY_SCHEMA_VERSION,
            "Deep Context Federation agent context gate policy",
            ["schema_version", "authority_effect", "no_apply"],
            {
                **_boundary_props(),
                "policy_id": {"type": "string"},
                "description": {"type": "string"},
                "require_context_ok": {"type": "boolean"},
                "require_source_contract_ok": {"type": "boolean"},
                "max_missing_artifacts": {"type": ["integer", "null"]},
                "max_skipped_artifacts": {"type": ["integer", "null"]},
                "max_truncated_artifacts": {"type": ["integer", "null"]},
                "max_selected_tokens": {"type": ["integer", "null"]},
                "max_prompt_tokens": {"type": ["integer", "null"]},
                "enforce_prompt_within_token_budget": {"type": "boolean"},
                "enforce_selected_within_content_budget": {"type": "boolean"},
                "require_schema_versions": array_type,
            },
        ),
        "agent_context_gate": _schema(
            AGENT_CONTEXT_GATE_SCHEMA_VERSION,
            "Deep Context Federation agent context gate",
            ["schema_version", "ok", "status", "authority_effect", "no_apply", "policy", "checks", "errors", "summary"],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string", "enum": ["pass_agent_context_gate", "fail_agent_context_gate"]},
                **_boundary_props(),
                "policy": object_type,
                "check_count": {"type": "integer"},
                "error_count": {"type": "integer"},
                "checks": array_type,
                "errors": array_type,
                "summary": object_type,
            },
        ),
        "agent_handoff": _schema(
            AGENT_HANDOFF_SCHEMA_VERSION,
            "Deep Context Federation gated agent handoff",
            [
                "schema_version",
                "ok",
                "status",
                "authority_effect",
                "no_apply",
                "decision",
                "agent_ci_summary",
                "agent_context_summary",
                "agent_context_gate_summary",
                "agent_handoff_verification_summary",
                "model_handoff",
                "outputs",
                "safety_boundaries",
            ],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string", "enum": ["pass_agent_handoff", "warn_agent_handoff", "fail_agent_handoff"]},
                **_boundary_props(),
                "task": {"type": "string"},
                "root": {"type": "string"},
                "output_dir": {"type": "string"},
                "duration_seconds": {"type": "number"},
                "targets": array_type,
                "decision": object_type,
                "agent_ci_summary": object_type,
                "agent_context_summary": object_type,
                "agent_context_gate_summary": object_type,
                "agent_handoff_verification_summary": object_type,
                "input_fingerprint_summary": object_type,
                "input_fingerprint": object_type,
                "model_handoff": object_type,
                "outputs": object_type,
                "safety_boundaries": object_type,
                "prompt_text": {"type": "string"},
                "prompt_estimated_tokens": {"type": "integer"},
                "json_estimated_tokens": {"type": "integer"},
            },
        ),
        "agent_handoff_verification": _schema(
            AGENT_HANDOFF_VERIFICATION_SCHEMA_VERSION,
            "Deep Context Federation agent handoff verification",
            ["schema_version", "ok", "status", "authority_effect", "no_apply", "checks", "errors", "summary"],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string", "enum": ["pass_agent_handoff_verification", "fail_agent_handoff_verification"]},
                **_boundary_props(),
                "input_ref": {"type": "string"},
                "check_count": {"type": "integer"},
                "error_count": {"type": "integer"},
                "checks": array_type,
                "errors": array_type,
                "summary": object_type,
            },
        ),
        "agent_model_input": _schema(
            AGENT_MODEL_INPUT_SCHEMA_VERSION,
            "Deep Context Federation fail-closed agent model input",
            ["schema_version", "ok", "status", "authority_effect", "no_apply", "verification_summary", "checks", "errors", "safety_boundaries"],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string", "enum": ["pass_agent_model_input", "fail_agent_model_input"]},
                **_boundary_props(),
                "input_ref": {"type": "string"},
                "prompt_source": {"type": "string"},
                "prompt_format": {"type": "string"},
                "prompt_bytes": {"type": "integer"},
                "prompt_sha256": {"type": "string"},
                "prompt_estimated_tokens": {"type": "integer"},
                "prompt_text": {"type": "string"},
                "handoff_summary": object_type,
                "verification_summary": object_type,
                "token_economics": object_type,
                "checks": array_type,
                "errors": array_type,
                "safety_boundaries": object_type,
            },
        ),
        "agent_discovery": _schema(
            AGENT_DISCOVERY_SCHEMA_VERSION,
            "Deep Context Federation agent discovery",
            ["schema_version", "ok", "status", "authority_effect", "no_apply", "root", "ready_for_model_input", "discovered", "recommended_next_command", "safety_boundaries"],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string", "enum": ["ready_model_input", "blocked_model_input", "blocked_handoff_unreadable", "manifest_available", "federation_available", "not_configured"]},
                **_boundary_props(),
                "root": {"type": "string"},
                "ready_for_model_input": {"type": "boolean"},
                "selected_handoff": {"type": "string"},
                "model_input_summary": object_type,
                "discovered": object_type,
                "recommended_next_command": {"type": "string"},
                "diagnostics": array_type,
                "safety_boundaries": object_type,
            },
        ),
        "agent_route": _schema(
            AGENT_ROUTE_SCHEMA_VERSION,
            "Deep Context Federation agent route",
            [
                "schema_version",
                "ok",
                "status",
                "authority_effect",
                "no_apply",
                "root",
                "discovery_status",
                "action",
                "recommended_next_command",
                "route_steps",
                "wrapper_contract",
                "safety_boundaries",
            ],
            {
                "ok": {"type": "boolean"},
                "status": {
                    "type": "string",
                    "enum": [
                        "ready_agent_route",
                        "needs_agent_handoff",
                        "needs_task_agent_route",
                        "needs_bootstrap_agent_route",
                        "needs_manifest_refresh_agent_route",
                        "blocked_agent_route",
                    ],
                },
                **_boundary_props(),
                "root": {"type": "string"},
                "task": {"type": "string"},
                "targets": array_type,
                "discovery_status": {"type": "string"},
                "action": {"type": "string"},
                "model_input_ready": {"type": "boolean"},
                "route_ready": {"type": "boolean"},
                "recommended_next_command": {"type": "string"},
                "route_steps": array_type,
                "requires_user_input": array_type,
                "discovered": object_type,
                "discovery_summary": object_type,
                "wrapper_contract": object_type,
                "safety_boundaries": object_type,
            },
        ),
        "agent_ready": _schema(
            AGENT_READY_SCHEMA_VERSION,
            "Deep Context Federation agent ready",
            [
                "schema_version",
                "ok",
                "status",
                "authority_effect",
                "no_apply",
                "root",
                "action_taken",
                "route_summary",
                "handoff_summary",
                "input_freshness",
                "request_binding",
                "model_input_summary",
                "prompt_source",
                "prompt_estimated_tokens",
                "safety_boundaries",
            ],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string", "enum": ["pass_agent_ready", "fail_agent_ready"]},
                **_boundary_props(),
                "root": {"type": "string"},
                "task": {"type": "string"},
                "targets": array_type,
                "action_taken": {"type": "string"},
                "route_summary": object_type,
                "handoff_summary": object_type,
                "input_freshness": object_type,
                "request_binding": object_type,
                "agent_profile_summary": object_type,
                "model_input_summary": object_type,
                "prompt_source": {"type": "string"},
                "prompt_format": {"type": "string"},
                "prompt_estimated_tokens": {"type": "integer"},
                "prompt_text": {"type": "string"},
                "token_economics": object_type,
                "errors": array_type,
                "outputs": object_type,
                "safety_boundaries": object_type,
            },
        ),
        "agent_profile": _schema(
            AGENT_PROFILE_SCHEMA_VERSION,
            "Deep Context Federation agent profile",
            [
                "schema_version",
                "authority_effect",
                "no_apply",
            ],
            {
                **_boundary_props(),
                "profile_id": {"type": "string"},
                "description": {"type": "string"},
                "root": {"type": "string"},
                "output_dir": {"type": "string"},
                "manifests": array_type,
                "handoff": {"type": "string"},
                "task": {"type": "string"},
                "targets": array_type,
                "quality_policy": {"type": "string"},
                "target_review_policy": {"type": "string"},
                "efficiency_policy": {"type": "string"},
                "context_gate_policy": {"type": "string"},
                "baselines": array_type,
            },
        ),
        "agent_profile_validation": _schema(
            AGENT_PROFILE_VALIDATION_SCHEMA_VERSION,
            "Deep Context Federation agent profile validation",
            [
                "schema_version",
                "ok",
                "status",
                "authority_effect",
                "no_apply",
                "profile_path",
                "normalized",
                "checks",
                "errors",
            ],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string", "enum": ["pass_agent_profile", "fail_agent_profile"]},
                **_boundary_props(),
                "profile_path": {"type": "string"},
                "profile_id": {"type": "string"},
                "description": {"type": "string"},
                "normalized": object_type,
                "checks": array_type,
                "errors": array_type,
                "summary": object_type,
            },
        ),
        "agent_profile_init": _schema(
            AGENT_PROFILE_INIT_SCHEMA_VERSION,
            "Deep Context Federation agent profile init",
            [
                "schema_version",
                "ok",
                "status",
                "authority_effect",
                "no_apply",
                "profile_path",
                "profile",
                "profile_validation_summary",
                "checks",
                "errors",
                "safety_boundaries",
            ],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string", "enum": ["pass_agent_profile_init", "fail_agent_profile_init"]},
                **_boundary_props(),
                "root": {"type": "string"},
                "profile_path": {"type": "string"},
                "profile": object_type,
                "profile_validation_summary": object_type,
                "checks": array_type,
                "warnings": array_type,
                "errors": array_type,
                "outputs": object_type,
                "summary": object_type,
                "safety_boundaries": object_type,
            },
        ),
        "agent_onboard": _schema(
            AGENT_ONBOARD_SCHEMA_VERSION,
            "Deep Context Federation agent onboard",
            [
                "schema_version",
                "ok",
                "status",
                "authority_effect",
                "no_apply",
                "profile_path",
                "profile_init_summary",
                "profile_validation_summary",
                "agent_ready_summary",
                "model_input_ready",
                "safety_boundaries",
            ],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string", "enum": ["pass_agent_onboard", "fail_agent_onboard"]},
                **_boundary_props(),
                "root": {"type": "string"},
                "profile_path": {"type": "string"},
                "profile_init_summary": object_type,
                "profile_validation_summary": object_type,
                "agent_ready_summary": object_type,
                "model_input_ready": {"type": "boolean"},
                "prompt_source": {"type": "string"},
                "prompt_estimated_tokens": {"type": "integer"},
                "recommended_next_command": {"type": "string"},
                "agent_ready": object_type,
                "errors": array_type,
                "outputs": object_type,
                "safety_boundaries": object_type,
            },
        ),
        "input_fingerprint": _schema(
            INPUT_FINGERPRINT_SCHEMA_VERSION,
            "Deep Context Federation input fingerprint",
            [
                "schema_version",
                "ok",
                "status",
                "authority_effect",
                "no_apply",
                "root",
                "digest",
                "manifests",
                "sources",
            ],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string", "enum": ["pass_input_fingerprint", "fail_input_fingerprint"]},
                **_boundary_props(),
                "root": {"type": "string"},
                "digest": {"type": "string"},
                "manifest_count": {"type": "integer"},
                "source_count": {"type": "integer"},
                "manifests": array_type,
                "sources": array_type,
                "errors": array_type,
                "safety_boundaries": object_type,
            },
        ),
        "input_fingerprint_compare": _schema(
            INPUT_FINGERPRINT_COMPARE_SCHEMA_VERSION,
            "Deep Context Federation input fingerprint compare",
            ["schema_version", "status", "authority_effect", "no_apply", "comparable", "matches"],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string"},
                **_boundary_props(),
                "comparable": {"type": "boolean"},
                "matches": {},
                "previous_digest": {"type": "string"},
                "current_digest": {"type": "string"},
                "reason": {"type": "string"},
                "current_fingerprint": object_type,
            },
        ),
        "request_binding": _schema(
            "deep_context_federation_request_binding_v1",
            "Deep Context Federation request binding",
            ["schema_version", "ok", "status", "authority_effect", "no_apply", "requested_task", "handoff_task", "requested_targets", "handoff_targets"],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string"},
                **_boundary_props(),
                "requested_task": {"type": "string"},
                "handoff_task": {"type": "string"},
                "requested_targets": array_type,
                "handoff_targets": array_type,
                "checks": array_type,
                "errors": array_type,
            },
        ),
    }


def build_schema_registry() -> dict[str, Any]:
    schemas = _artifact_schemas()
    rows = [
        {
            "artifact_kind": artifact_kind,
            "schema_version": schema["properties"]["schema_version"]["const"],
            "json_schema": schema,
        }
        for artifact_kind, schema in sorted(schemas.items())
    ]
    return {
        "schema_version": SCHEMA_REGISTRY_SCHEMA_VERSION,
        "status": "ok",
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": _utc_now(),
        "json_schema_dialect": JSON_SCHEMA_DIALECT,
        "artifact_schemas": rows,
        "summary": {
            "artifact_schema_count": len(rows),
            "artifact_kinds": [row["artifact_kind"] for row in rows],
        },
    }


def schema_for_artifact(artifact_kind: str) -> dict[str, Any]:
    schemas = _artifact_schemas()
    if artifact_kind not in schemas:
        raise ValueError(f"unknown artifact kind {artifact_kind!r}; available={sorted(schemas)}")
    return schemas[artifact_kind]


def artifact_kinds() -> list[str]:
    return sorted(_artifact_schemas())


def infer_artifact_kind(payload: Mapping[str, Any]) -> str | None:
    schema_version = str(payload.get("schema_version") or "")
    for artifact_kind, schema in _artifact_schemas().items():
        expected = str(schema.get("properties", {}).get("schema_version", {}).get("const") or "")
        if schema_version == expected:
            return artifact_kind
    return None


def _matches_type(value: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        return any(_matches_type(value, item) for item in expected)
    if expected == "object":
        return isinstance(value, Mapping)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _check(checks: list[dict[str, Any]], check_id: str, passed: bool, detail: Any = None) -> None:
    checks.append({"id": check_id, "passed": bool(passed), "severity": "error", "detail": detail})


def _validate_subset(schema: Mapping[str, Any], value: Any, path: str, checks: list[dict[str, Any]]) -> None:
    expected_type = schema.get("type")
    if expected_type is not None:
        _check(checks, f"{path}:type", _matches_type(value, expected_type), {"expected": expected_type, "actual": type(value).__name__})
        if not _matches_type(value, expected_type):
            return
    if "const" in schema:
        _check(checks, f"{path}:const", value == schema.get("const"), {"expected": schema.get("const"), "actual": value})
    if "enum" in schema:
        allowed = list(schema.get("enum") or [])
        _check(checks, f"{path}:enum", value in allowed, {"allowed": allowed, "actual": value})
    if not isinstance(value, Mapping):
        return
    required = [str(item) for item in schema.get("required") or []]
    for key in required:
        _check(checks, f"{path}.{key}:required", key in value, {"required": key})
    properties = schema.get("properties") if isinstance(schema.get("properties"), Mapping) else {}
    for key, subschema in properties.items():
        if key in value and isinstance(subschema, Mapping):
            _validate_subset(subschema, value[key], f"{path}.{key}", checks)
    if schema.get("additionalProperties") is False:
        extra = sorted(set(value) - set(properties))
        _check(checks, f"{path}:additionalProperties", not extra, {"extra": extra})


def validate_artifact_contract(payload: Mapping[str, Any], *, artifact_kind: str | None = None) -> dict[str, Any]:
    selected_artifact = artifact_kind or infer_artifact_kind(payload)
    checks: list[dict[str, Any]] = []
    _check(checks, "payload_is_object", isinstance(payload, Mapping), {"actual": type(payload).__name__})
    if not selected_artifact:
        _check(checks, "artifact_kind_inferred", False, {"schema_version": payload.get("schema_version")})
        schema = None
    else:
        _check(checks, "artifact_kind_selected", True, {"artifact_kind": selected_artifact})
        schema = schema_for_artifact(selected_artifact)
    if schema is not None:
        _validate_subset(schema, payload, "$", checks)
    failed = [check for check in checks if not check["passed"]]
    return {
        "schema_version": CONTRACT_VALIDATION_SCHEMA_VERSION,
        "ok": not failed,
        "status": "pass_contract_validation" if not failed else "fail_contract_validation",
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": _utc_now(),
        "artifact_kind": selected_artifact or "",
        "input_schema_version": payload.get("schema_version"),
        "check_count": len(checks),
        "error_count": len(failed),
        "checks": checks,
        "errors": failed,
    }


def markdown_schema_registry(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Deep Context Federation Schema Registry",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Dialect: `{payload.get('json_schema_dialect')}`",
        "",
        "## Artifact Schemas",
        "",
    ]
    for row in payload.get("artifact_schemas") or []:
        if isinstance(row, Mapping):
            lines.append(f"- `{row.get('artifact_kind')}` -> `{row.get('schema_version')}`")
    return "\n".join(lines).rstrip() + "\n"


def markdown_json_schema(schema: Mapping[str, Any], *, artifact_kind: str) -> str:
    lines = [
        "# Deep Context Federation JSON Schema",
        "",
        f"- Artifact: `{artifact_kind}`",
        f"- Schema: `{schema.get('$id')}`",
        f"- Title: `{schema.get('title')}`",
        "",
        "## Required",
        "",
    ]
    for item in schema.get("required") or []:
        lines.append(f"- `{item}`")
    return "\n".join(lines).rstrip() + "\n"


def markdown_contract_validation(result: Mapping[str, Any]) -> str:
    lines = [
        "# Deep Context Federation Contract Validation",
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
