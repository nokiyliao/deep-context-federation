"""Shared source-identity policies for public DCF artifacts."""

from __future__ import annotations

from typing import Any


def public_source_identity_policy(*, audit_provenance_location: str = "original_input_artifacts") -> dict[str, Any]:
    """Return the standard public DCF identity-collapse policy."""

    return {
        "public_identity": "deep_context_federation",
        "user_facing_source_identity_collapsed": True,
        "source_ids_exposed": False,
        "source_table_exposed": False,
        "upstream_identity_fields_stripped": True,
        "audit_provenance_location": str(audit_provenance_location),
    }
