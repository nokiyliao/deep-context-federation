"""Deep Context Federation public API."""

from deep_context_federation.builder import build_federation
from deep_context_federation.diff import diff_federations
from deep_context_federation.doctor import doctor_federation
from deep_context_federation.graph import trace_federation
from deep_context_federation.manifest import validate_manifest
from deep_context_federation.query import query_federation
from deep_context_federation.rank import rank_entities
from deep_context_federation.rank import rank_sources
from deep_context_federation.scanner import scan_repository
from deep_context_federation.sqlite_query import query_sqlite
from deep_context_federation.verifier import verify_federation

__all__ = [
    "build_federation",
    "diff_federations",
    "doctor_federation",
    "query_federation",
    "query_sqlite",
    "rank_entities",
    "rank_sources",
    "scan_repository",
    "trace_federation",
    "validate_manifest",
    "verify_federation",
]

__version__ = "0.5.0"
