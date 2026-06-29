"""Self-describing machine-readable capabilities for DCF."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from deep_context_federation.adjudicate import ADJUDICATE_SCHEMA_VERSION
from deep_context_federation.bootstrap import BOOTSTRAP_SCHEMA_VERSION
from deep_context_federation.builder import DEFAULT_JSON_NAME
from deep_context_federation.builder import DEFAULT_MD_NAME
from deep_context_federation.builder import DEFAULT_SQLITE_NAME
from deep_context_federation.builder import EDGE_TYPES
from deep_context_federation.builder import FUSION_ROLES
from deep_context_federation.builder import MANIFEST_SCHEMA
from deep_context_federation.builder import QUERY_PRESETS
from deep_context_federation.builder import SCHEMA_VERSION
from deep_context_federation.compose import COMPOSE_SCHEMA_VERSION
from deep_context_federation.context_pack import CONTEXT_PACK_SCHEMA_VERSION
from deep_context_federation.efficiency_gate import EFFICIENCY_GATE_POLICY_SCHEMA_VERSION
from deep_context_federation.efficiency_gate import EFFICIENCY_GATE_SCHEMA_VERSION
from deep_context_federation.efficiency_report import EFFICIENCY_REPORT_SCHEMA_VERSION
from deep_context_federation.intake import AGENT_INTAKE_SCHEMA_VERSION
from deep_context_federation.manifest import MANIFEST_SCHEMA as MANIFEST_VERIFY_INPUT_SCHEMA
from deep_context_federation.quality_gate import QUALITY_GATE_POLICY_SCHEMA_VERSION
from deep_context_federation.quality_gate import QUALITY_GATE_SCHEMA_VERSION
from deep_context_federation.query import QUERY_SCHEMA_VERSION
from deep_context_federation.resolve import RESOLVE_SCHEMA_VERSION
from deep_context_federation.scanner import DEPENDENCY_GRAPH_SCHEMA_VERSION
from deep_context_federation.scanner import FILE_INVENTORY_SCHEMA_VERSION
from deep_context_federation.scanner import SCAN_SCHEMA_VERSION
from deep_context_federation.scanner import SURFACE_MAP_SCHEMA_VERSION
from deep_context_federation.scanner import SYMBOL_MAP_SCHEMA_VERSION
from deep_context_federation.sqlite_query import SQL_PRESETS
from deep_context_federation.target_review import TARGET_REVIEW_SCHEMA_VERSION
from deep_context_federation.target_review_gate import TARGET_REVIEW_GATE_POLICY_SCHEMA_VERSION
from deep_context_federation.target_review_gate import TARGET_REVIEW_GATE_SCHEMA_VERSION
from deep_context_federation.task_brief import TASK_BRIEF_SCHEMA_VERSION
from deep_context_federation.verifier import VERIFY_SCHEMA_VERSION
from deep_context_federation.version import __version__
from deep_context_federation.workflow_plan import WORKFLOW_PLAN_SCHEMA_VERSION
from deep_context_federation.workflow_run import WORKFLOW_RUN_SCHEMA_VERSION

CAPABILITIES_SCHEMA_VERSION = "deep_context_federation_capabilities_v1"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _artifact_contracts() -> list[dict[str, Any]]:
    return [
        {
            "artifact_kind": "manifest",
            "schema_version": MANIFEST_SCHEMA,
            "producer": "human_or_tool",
            "consumer_commands": ["build", "validate-manifest", "compose-manifest", "bootstrap"],
            "top_level_required": ["schema_version", "authority_boundary", "sources"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "artifact_kind": "federation",
            "schema_version": SCHEMA_VERSION,
            "producer": "build",
            "default_outputs": [DEFAULT_JSON_NAME, DEFAULT_MD_NAME, DEFAULT_SQLITE_NAME],
            "consumer_commands": ["verify", "query", "trace", "resolve", "adjudicate", "review-targets", "doctor", "rank", "diff", "quality-gate", "brief"],
            "top_level_required": ["schema_version", "sources", "entities", "edges", "conflicts", "query_presets"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "artifact_kind": "repo_scan",
            "schema_version": SCAN_SCHEMA_VERSION,
            "producer": "scan",
            "consumer_commands": ["bootstrap"],
            "top_level_required": ["schema_version", "outputs", "summary"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "artifact_kind": "bootstrap",
            "schema_version": BOOTSTRAP_SCHEMA_VERSION,
            "producer": "bootstrap",
            "consumer_commands": ["quality-gate", "intake"],
            "top_level_required": ["schema_version", "scan", "build", "verify", "doctor", "outputs"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "artifact_kind": "quality_gate_policy",
            "schema_version": QUALITY_GATE_POLICY_SCHEMA_VERSION,
            "producer": "human_or_ci",
            "consumer_commands": ["quality-gate"],
            "top_level_required": ["schema_version", "authority_effect", "no_apply"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "artifact_kind": "quality_gate",
            "schema_version": QUALITY_GATE_SCHEMA_VERSION,
            "producer": "quality-gate",
            "consumer_commands": ["ci", "agent_router"],
            "top_level_required": ["schema_version", "ok", "status", "policy", "checks", "errors", "summary"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "artifact_kind": "manifest_compose",
            "schema_version": COMPOSE_SCHEMA_VERSION,
            "producer": "compose-manifest",
            "consumer_commands": ["build", "bootstrap"],
            "top_level_required": ["schema_version", "ok", "status", "outputs", "summary"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "artifact_kind": "verify",
            "schema_version": VERIFY_SCHEMA_VERSION,
            "producer": "verify",
            "consumer_commands": ["bootstrap", "ci"],
            "top_level_required": ["schema_version", "ok", "status", "checks", "errors"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "artifact_kind": "query",
            "schema_version": QUERY_SCHEMA_VERSION,
            "producer": "query",
            "consumer_commands": ["agent_router", "operator_context"],
            "top_level_required": ["schema_version", "preset", "status", "rows"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "artifact_kind": "resolve",
            "schema_version": RESOLVE_SCHEMA_VERSION,
            "producer": "resolve",
            "consumer_commands": ["adjudicate", "agent_router", "agent_prompt", "operator_context"],
            "top_level_required": ["schema_version", "status", "target", "summary", "matched_entities", "related_sources"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "artifact_kind": "adjudication",
            "schema_version": ADJUDICATE_SCHEMA_VERSION,
            "producer": "adjudicate",
            "consumer_commands": ["review-targets", "agent_router", "agent_prompt", "operator_context"],
            "top_level_required": ["schema_version", "status", "target", "verdict", "confidence_score", "support", "recommended_use"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "artifact_kind": "target_review",
            "schema_version": TARGET_REVIEW_SCHEMA_VERSION,
            "producer": "review-targets",
            "consumer_commands": ["review-gate", "agent_router", "ci", "operator_context"],
            "top_level_required": ["schema_version", "status", "target_count", "summary", "rows", "priority_order"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "artifact_kind": "target_review_gate_policy",
            "schema_version": TARGET_REVIEW_GATE_POLICY_SCHEMA_VERSION,
            "producer": "human_or_ci",
            "consumer_commands": ["review-gate"],
            "top_level_required": ["schema_version", "authority_effect", "no_apply"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "artifact_kind": "target_review_gate",
            "schema_version": TARGET_REVIEW_GATE_SCHEMA_VERSION,
            "producer": "review-gate",
            "consumer_commands": ["agent_router", "ci"],
            "top_level_required": ["schema_version", "ok", "status", "policy", "checks", "errors", "summary"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "artifact_kind": "context_pack",
            "schema_version": CONTEXT_PACK_SCHEMA_VERSION,
            "producer": "pack",
            "consumer_commands": ["brief", "agent_prompt", "model_context_router"],
            "top_level_required": ["schema_version", "token_budget", "estimated_tokens", "prompt_text", "coverage", "rows", "summary"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "artifact_kind": "task_brief",
            "schema_version": TASK_BRIEF_SCHEMA_VERSION,
            "producer": "brief",
            "consumer_commands": ["agent_router", "agent_prompt", "operator_context"],
            "top_level_required": [
                "schema_version",
                "status",
                "task",
                "selected_presets",
                "doctor_summary",
                "context_pack",
                "recommended_commands",
            ],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "artifact_kind": "agent_intake",
            "schema_version": AGENT_INTAKE_SCHEMA_VERSION,
            "producer": "intake",
            "consumer_commands": ["workflow-plan", "agent_router", "ci", "operator_context"],
            "top_level_required": [
                "schema_version",
                "ok",
                "status",
                "task",
                "bootstrap_summary",
                "quality_gate_summary",
                "task_brief_summary",
                "outputs",
            ],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "artifact_kind": "workflow_plan",
            "schema_version": WORKFLOW_PLAN_SCHEMA_VERSION,
            "producer": "workflow-plan",
            "consumer_commands": ["workflow-run", "agent_router", "ci", "operator_context"],
            "top_level_required": [
                "schema_version",
                "status",
                "task",
                "steps",
                "gates",
                "token_efficiency",
                "safety_boundaries",
            ],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "artifact_kind": "workflow_run",
            "schema_version": WORKFLOW_RUN_SCHEMA_VERSION,
            "producer": "workflow-run",
            "consumer_commands": ["efficiency-report", "agent_router", "ci", "operator_context"],
            "top_level_required": [
                "schema_version",
                "ok",
                "status",
                "task",
                "step_results",
                "model_handoff",
                "outputs",
                "safety_boundaries",
            ],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "artifact_kind": "efficiency_report",
            "schema_version": EFFICIENCY_REPORT_SCHEMA_VERSION,
            "producer": "efficiency-report",
            "consumer_commands": ["efficiency-gate", "agent_router", "ci", "operator_context"],
            "top_level_required": [
                "schema_version",
                "ok",
                "status",
                "workflow_run_ref",
                "artifacts",
                "model_context_budget",
                "safety_boundaries",
            ],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "artifact_kind": "efficiency_gate_policy",
            "schema_version": EFFICIENCY_GATE_POLICY_SCHEMA_VERSION,
            "producer": "human_or_ci",
            "consumer_commands": ["efficiency-gate"],
            "top_level_required": ["schema_version", "authority_effect", "no_apply"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "artifact_kind": "efficiency_gate",
            "schema_version": EFFICIENCY_GATE_SCHEMA_VERSION,
            "producer": "efficiency-gate",
            "consumer_commands": ["agent_router", "ci", "operator_context"],
            "top_level_required": [
                "schema_version",
                "ok",
                "status",
                "policy",
                "checks",
                "errors",
                "summary",
            ],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "artifact_kind": "schema_registry",
            "schema_version": "deep_context_federation_schema_registry_v1",
            "producer": "schema",
            "consumer_commands": ["schema", "validate-artifact", "agent_router"],
            "top_level_required": ["schema_version", "artifact_schemas", "summary"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "artifact_kind": "contract_validation",
            "schema_version": "deep_context_federation_contract_validation_v1",
            "producer": "validate-artifact",
            "consumer_commands": ["ci", "agent_router"],
            "top_level_required": ["schema_version", "ok", "status", "checks", "errors"],
            "authority_effect": "none",
            "no_apply": True,
        },
    ]


def _generated_source_contracts() -> list[dict[str, Any]]:
    return [
        {
            "source_id": "repo_file_inventory",
            "schema_version": FILE_INVENTORY_SCHEMA_VERSION,
            "role": "evidence_index",
            "producer": "scan",
        },
        {
            "source_id": "repo_code_symbols",
            "schema_version": SYMBOL_MAP_SCHEMA_VERSION,
            "role": "advisory_source_symbol_graph",
            "producer": "scan",
        },
        {
            "source_id": "repo_dependency_graph",
            "schema_version": DEPENDENCY_GRAPH_SCHEMA_VERSION,
            "role": "advisory_dependency_graph",
            "producer": "scan",
        },
        {
            "source_id": "repo_surface_map",
            "schema_version": SURFACE_MAP_SCHEMA_VERSION,
            "role": "project_surface",
            "producer": "scan",
        },
    ]


def _commands() -> list[dict[str, Any]]:
    return [
        {
            "command": "capabilities",
            "intent": "Describe available machine-readable contracts, commands, presets, and safety boundaries.",
            "writes": ["optional --output JSON"],
            "output_schemas": [CAPABILITIES_SCHEMA_VERSION],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "schema",
            "intent": "Emit the JSON Schema registry or one artifact schema.",
            "writes": ["optional --output JSON"],
            "output_schemas": ["deep_context_federation_schema_registry_v1", "json_schema"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "validate-artifact",
            "intent": "Validate an artifact against the built-in top-level JSON Schema contract subset.",
            "writes": ["optional --output JSON"],
            "output_schemas": ["deep_context_federation_contract_validation_v1"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "scan",
            "intent": "Read-only repository scan into starter source artifacts and manifest.",
            "writes": ["output_dir generated artifacts only when --write is set"],
            "output_schemas": [SCAN_SCHEMA_VERSION, MANIFEST_SCHEMA],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "bootstrap",
            "intent": "Run scan, optional compose, build, verify, and doctor as one local pipeline.",
            "writes": ["output_dir generated artifacts"],
            "output_schemas": [BOOTSTRAP_SCHEMA_VERSION, SCHEMA_VERSION, VERIFY_SCHEMA_VERSION],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "intake",
            "intent": "Run bootstrap, quality gate, and task brief as one agent intake packet.",
            "writes": ["output_dir generated artifacts"],
            "output_schemas": [AGENT_INTAKE_SCHEMA_VERSION, BOOTSTRAP_SCHEMA_VERSION, QUALITY_GATE_SCHEMA_VERSION, TASK_BRIEF_SCHEMA_VERSION],
            "options": ["--task", "--policy", "--token-budget", "--query-limit", "--max-presets", "--max-rows", "--no-prompt"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "workflow-plan",
            "intent": "Emit a read-only execution plan that sequences intake, validation, target review, gates, and bounded context reads.",
            "writes": ["optional workflow plan JSON when --output is set"],
            "output_schemas": [WORKFLOW_PLAN_SCHEMA_VERSION],
            "options": [
                "--task",
                "--target",
                "--targets-file",
                "--quality-policy",
                "--target-review-policy",
                "--token-budget",
                "--query-limit",
                "--max-presets",
                "--max-rows",
                "--no-prompt",
            ],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "workflow-run",
            "intent": "Execute the DCF read-only workflow and emit one compact run capsule for agents.",
            "writes": ["output_dir generated artifacts", "optional workflow run JSON when --output is set"],
            "output_schemas": [WORKFLOW_RUN_SCHEMA_VERSION],
            "input_schemas": [
                WORKFLOW_PLAN_SCHEMA_VERSION,
                AGENT_INTAKE_SCHEMA_VERSION,
                TARGET_REVIEW_SCHEMA_VERSION,
                TARGET_REVIEW_GATE_SCHEMA_VERSION,
            ],
            "options": [
                "--task",
                "--target",
                "--targets-file",
                "--quality-policy",
                "--target-review-policy",
                "--token-budget",
                "--query-limit",
                "--max-presets",
                "--max-rows",
                "--include-details",
                "--no-prompt",
            ],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "efficiency-report",
            "intent": "Measure workflow-run token savings against full-federation and generated-output baselines.",
            "writes": ["optional efficiency report JSON when --output is set"],
            "output_schemas": [EFFICIENCY_REPORT_SCHEMA_VERSION],
            "input_schemas": [WORKFLOW_RUN_SCHEMA_VERSION],
            "options": ["--input", "--baseline", "--output"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "efficiency-gate",
            "intent": "Evaluate an efficiency report against policy thresholds for agent or CI continuation.",
            "writes": ["optional efficiency gate JSON when --output is set"],
            "output_schemas": [EFFICIENCY_GATE_SCHEMA_VERSION],
            "input_schemas": [EFFICIENCY_REPORT_SCHEMA_VERSION, EFFICIENCY_GATE_POLICY_SCHEMA_VERSION],
            "options": [
                "--policy",
                "--max-read-first-tokens",
                "--max-gate-pass-tokens",
                "--max-read-first-ratio",
                "--max-gate-pass-ratio",
                "--min-read-first-savings-percent",
                "--min-gate-pass-savings-percent",
                "--require-artifact-role",
            ],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "build",
            "intent": "Build federation JSON, Markdown, SQLite, and cache from a manifest.",
            "writes": ["output_dir generated artifacts when --write is set"],
            "output_schemas": [SCHEMA_VERSION],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "validate-manifest",
            "intent": "Validate manifest shape before reading sources.",
            "writes": [],
            "output_schemas": ["deep_context_federation_manifest_verify_v1"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "compose-manifest",
            "intent": "Merge multiple manifests into one buildable manifest.",
            "writes": ["optional composed manifest when --write is set"],
            "output_schemas": [COMPOSE_SCHEMA_VERSION, MANIFEST_VERIFY_INPUT_SCHEMA],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "verify",
            "intent": "Verify a federation artifact and boundary invariants.",
            "writes": [],
            "output_schemas": [VERIFY_SCHEMA_VERSION],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "quality-gate",
            "intent": "Evaluate a bootstrap or federation artifact against thresholds or a JSON policy.",
            "writes": ["optional quality gate JSON when --output is set"],
            "output_schemas": [QUALITY_GATE_SCHEMA_VERSION],
            "input_schemas": [BOOTSTRAP_SCHEMA_VERSION, SCHEMA_VERSION, QUALITY_GATE_POLICY_SCHEMA_VERSION],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "query",
            "intent": "Run named JSON artifact query presets.",
            "writes": [],
            "output_schemas": [QUERY_SCHEMA_VERSION],
            "presets": list(QUERY_PRESETS),
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "resolve",
            "intent": "Resolve a claim, path, surface, or symbol target into an evidence card.",
            "writes": ["optional resolve JSON when --output is set"],
            "output_schemas": [RESOLVE_SCHEMA_VERSION],
            "options": ["--target", "--limit", "--token-budget", "--no-prompt"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "adjudicate",
            "intent": "Classify target support into authority/evidence/advisory tiers and emit a deterministic verdict.",
            "writes": ["optional adjudication JSON when --output is set"],
            "output_schemas": [ADJUDICATE_SCHEMA_VERSION],
            "options": ["--target", "--limit", "--token-budget", "--no-prompt"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "review-targets",
            "intent": "Batch adjudicate targets and rank governance/context risk.",
            "writes": ["optional target review JSON when --output is set"],
            "output_schemas": [TARGET_REVIEW_SCHEMA_VERSION],
            "options": ["--target", "--targets-file", "--limit", "--token-budget", "--include-details", "--no-prompt"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "review-gate",
            "intent": "Evaluate target review against CI/agent policy thresholds.",
            "writes": ["optional target review gate JSON when --output is set"],
            "output_schemas": [TARGET_REVIEW_GATE_SCHEMA_VERSION],
            "input_schemas": [TARGET_REVIEW_SCHEMA_VERSION, TARGET_REVIEW_GATE_POLICY_SCHEMA_VERSION],
            "options": [
                "--policy",
                "--max-blocked",
                "--max-no-match",
                "--max-advisory-only",
                "--max-warn",
                "--max-priority-score",
                "--min-average-confidence",
                "--disallow-risk",
                "--require-target",
            ],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "pack",
            "intent": "Build a token-aware bounded context pack and prompt_text for a task.",
            "writes": ["optional context pack JSON when --output is set"],
            "output_schemas": [CONTEXT_PACK_SCHEMA_VERSION],
            "options": ["--task", "--token-budget", "--max-rows", "--min-score", "--no-prompt"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "brief",
            "intent": "Build a task routing brief with selected query presets, doctor summary, recommended commands, and prompt pack.",
            "writes": ["optional task brief JSON when --output is set"],
            "output_schemas": [TASK_BRIEF_SCHEMA_VERSION],
            "options": ["--task", "--token-budget", "--query-limit", "--max-presets", "--max-rows", "--no-prompt"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "sql",
            "intent": "Run named read-only SQLite query presets.",
            "writes": [],
            "output_schemas": ["deep_context_federation_sql_query_v1"],
            "presets": sorted(SQL_PRESETS),
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "trace",
            "intent": "Trace neighboring federation entities by text match.",
            "writes": [],
            "output_schemas": ["deep_context_federation_trace_v1"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "doctor",
            "intent": "Diagnose federation health and next actions.",
            "writes": [],
            "output_schemas": ["deep_context_federation_doctor_v1"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "rank",
            "intent": "Rank important entities or risky sources.",
            "writes": [],
            "output_schemas": ["deep_context_federation_entity_rank_v1", "deep_context_federation_source_rank_v1"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "diff",
            "intent": "Diff two federation artifacts.",
            "writes": [],
            "output_schemas": ["deep_context_federation_diff_v1"],
            "authority_effect": "none",
            "no_apply": True,
        },
        {
            "command": "bench",
            "intent": "Benchmark in-memory federation build time.",
            "writes": [],
            "output_schemas": ["deep_context_federation_benchmark_v1"],
            "authority_effect": "none",
            "no_apply": True,
        },
    ]


def build_capabilities() -> dict[str, Any]:
    """Return the stable machine-readable capability registry."""

    return {
        "schema_version": CAPABILITIES_SCHEMA_VERSION,
        "status": "ok",
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": _utc_now(),
        "package": {
            "name": "deep-context-federation",
            "cli": "dcf",
            "version": __version__,
        },
        "contracts": {
            "artifact_contracts": _artifact_contracts(),
            "generated_source_contracts": _generated_source_contracts(),
            "edge_types": sorted(EDGE_TYPES),
            "fusion_roles": list(FUSION_ROLES),
        },
        "commands": _commands(),
        "query_presets": [{"preset": preset, "mode": "json_artifact"} for preset in QUERY_PRESETS],
        "sql_presets": [
            {"preset": preset, "mode": "sqlite_readonly", "description": spec["description"]}
            for preset, spec in sorted(SQL_PRESETS.items())
        ],
        "exit_codes": {
            "0": "pass_or_success",
            "2": "validation_or_quality_gate_failure",
            "other": "runtime_error",
        },
        "safety_boundaries": {
            "authority_effect": "none",
            "no_apply": True,
            "does_not_replace": [
                "project_authority",
                "runtime_registry",
                "task_ledger",
                "promotion_gate",
                "broker_or_order_path",
            ],
            "writes_only_generated_outputs": True,
            "external_tool_install": "never",
            "codebase_memory_mcp": "optional_advisory_adapter_only",
        },
    }


def markdown_capabilities(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Deep Context Federation Capabilities",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Authority effect: `{payload.get('authority_effect')}`",
        f"- No apply: `{payload.get('no_apply')}`",
        "",
        "## Commands",
        "",
    ]
    for command in payload.get("commands") or []:
        if isinstance(command, Mapping):
            lines.append(f"- `{command.get('command')}`: {command.get('intent')}")
    lines.extend(["", "## Query Presets", ""])
    for preset in payload.get("query_presets") or []:
        if isinstance(preset, Mapping):
            lines.append(f"- `{preset.get('preset')}`")
    lines.extend(["", "## Artifact Contracts", ""])
    contracts = payload.get("contracts") if isinstance(payload.get("contracts"), Mapping) else {}
    for contract in contracts.get("artifact_contracts") or []:
        if isinstance(contract, Mapping):
            lines.append(f"- `{contract.get('artifact_kind')}` -> `{contract.get('schema_version')}`")
    return "\n".join(lines).rstrip() + "\n"
