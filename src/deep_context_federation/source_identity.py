"""Shared source-identity policies for public DCF artifacts."""

from __future__ import annotations

from typing import Any

PROMPT_PACK_SCHEMA_VERSION = "deep_context_federation_prompt_pack_v1"


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


def public_prompt_pack(
    *,
    prompt_source: str = "",
    prompt_format: str = "",
    prompt_bytes: int = 0,
    prompt_sha256: str = "",
    prompt_estimated_tokens: int = 0,
    prompt_text: str = "",
) -> dict[str, Any]:
    """Return the public model-input section used by boundary audits."""

    return {
        "schema_version": PROMPT_PACK_SCHEMA_VERSION,
        "authority_effect": "none",
        "no_apply": True,
        "prompt_source": str(prompt_source or ""),
        "prompt_format": str(prompt_format or ""),
        "prompt_bytes": max(0, int(prompt_bytes or 0)),
        "prompt_sha256": str(prompt_sha256 or ""),
        "prompt_estimated_tokens": max(0, int(prompt_estimated_tokens or 0)),
        "prompt_text": str(prompt_text or ""),
    }
