"""Deep Context Federation public API."""

from deep_context_federation.bootstrap import bootstrap_federation
from deep_context_federation.builder import build_federation
from deep_context_federation.capabilities import build_capabilities
from deep_context_federation.compose import compose_manifests
from deep_context_federation.diff import diff_federations
from deep_context_federation.doctor import doctor_federation
from deep_context_federation.graph import trace_federation
from deep_context_federation.manifest import validate_manifest
from deep_context_federation.quality_gate import evaluate_quality_gate
from deep_context_federation.quality_gate import load_quality_gate_policy
from deep_context_federation.quality_gate import normalize_quality_gate_policy
from deep_context_federation.query import query_federation
from deep_context_federation.rank import rank_entities
from deep_context_federation.rank import rank_sources
from deep_context_federation.scanner import scan_repository
from deep_context_federation.schemas import build_schema_registry
from deep_context_federation.schemas import validate_artifact_contract
from deep_context_federation.sqlite_query import query_sqlite
from deep_context_federation.verifier import verify_federation
from deep_context_federation.version import __version__

__all__ = [
    "bootstrap_federation",
    "build_federation",
    "build_capabilities",
    "build_schema_registry",
    "compose_manifests",
    "diff_federations",
    "doctor_federation",
    "evaluate_quality_gate",
    "load_quality_gate_policy",
    "normalize_quality_gate_policy",
    "query_federation",
    "query_sqlite",
    "rank_entities",
    "rank_sources",
    "scan_repository",
    "trace_federation",
    "validate_artifact_contract",
    "validate_manifest",
    "verify_federation",
]
