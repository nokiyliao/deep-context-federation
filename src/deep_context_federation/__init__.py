"""Deep Context Federation public API."""

from deep_context_federation.builder import build_federation
from deep_context_federation.query import query_federation
from deep_context_federation.verifier import verify_federation

__all__ = ["build_federation", "query_federation", "verify_federation"]

__version__ = "0.1.0"
