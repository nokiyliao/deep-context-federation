"""Deep Context Federation public API."""

from deep_context_federation.adjudicate import adjudicate_target
from deep_context_federation.agent_context import build_agent_context
from deep_context_federation.agent_context_gate import evaluate_agent_context_gate
from deep_context_federation.agent_context_gate import load_agent_context_gate_policy
from deep_context_federation.agent_context_gate import normalize_agent_context_gate_policy
from deep_context_federation.agent_ci import build_agent_ci
from deep_context_federation.agent_handoff import build_agent_handoff
from deep_context_federation.agent_handoff_verify import verify_agent_handoff
from deep_context_federation.agent_model_input import build_agent_model_input
from deep_context_federation.bootstrap import bootstrap_federation
from deep_context_federation.builder import build_federation
from deep_context_federation.capabilities import build_capabilities
from deep_context_federation.compose import compose_manifests
from deep_context_federation.context_pack import pack_context
from deep_context_federation.diff import diff_federations
from deep_context_federation.doctor import doctor_federation
from deep_context_federation.efficiency_gate import evaluate_efficiency_gate
from deep_context_federation.efficiency_gate import load_efficiency_gate_policy
from deep_context_federation.efficiency_gate import normalize_efficiency_gate_policy
from deep_context_federation.efficiency_report import build_efficiency_report
from deep_context_federation.graph import trace_federation
from deep_context_federation.intake import build_agent_intake
from deep_context_federation.manifest import validate_manifest
from deep_context_federation.quality_gate import evaluate_quality_gate
from deep_context_federation.quality_gate import load_quality_gate_policy
from deep_context_federation.quality_gate import normalize_quality_gate_policy
from deep_context_federation.query import query_federation
from deep_context_federation.rank import rank_entities
from deep_context_federation.rank import rank_sources
from deep_context_federation.resolve import resolve_target
from deep_context_federation.scanner import scan_repository
from deep_context_federation.schemas import build_schema_registry
from deep_context_federation.schemas import validate_artifact_contract
from deep_context_federation.sqlite_query import query_sqlite
from deep_context_federation.target_review import review_targets
from deep_context_federation.target_review_gate import evaluate_target_review_gate
from deep_context_federation.target_review_gate import load_target_review_gate_policy
from deep_context_federation.target_review_gate import normalize_target_review_gate_policy
from deep_context_federation.task_brief import build_task_brief
from deep_context_federation.verifier import verify_federation
from deep_context_federation.version import __version__
from deep_context_federation.workflow_plan import build_workflow_plan
from deep_context_federation.workflow_run import build_workflow_run

__all__ = [
    "adjudicate_target",
    "bootstrap_federation",
    "build_federation",
    "build_agent_context",
    "build_agent_ci",
    "build_agent_handoff",
    "build_agent_model_input",
    "verify_agent_handoff",
    "build_workflow_plan",
    "build_workflow_run",
    "build_capabilities",
    "build_agent_intake",
    "build_efficiency_report",
    "build_task_brief",
    "build_schema_registry",
    "compose_manifests",
    "diff_federations",
    "doctor_federation",
    "evaluate_agent_context_gate",
    "evaluate_efficiency_gate",
    "evaluate_quality_gate",
    "evaluate_target_review_gate",
    "load_efficiency_gate_policy",
    "load_agent_context_gate_policy",
    "load_quality_gate_policy",
    "load_target_review_gate_policy",
    "normalize_efficiency_gate_policy",
    "normalize_agent_context_gate_policy",
    "normalize_quality_gate_policy",
    "normalize_target_review_gate_policy",
    "pack_context",
    "query_federation",
    "query_sqlite",
    "rank_entities",
    "rank_sources",
    "resolve_target",
    "review_targets",
    "scan_repository",
    "trace_federation",
    "validate_artifact_contract",
    "validate_manifest",
    "verify_federation",
]
