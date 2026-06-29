"""Named preset queries over a Deep Context Federation JSON artifact."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from deep_context_federation.builder import QUERY_PRESETS

QUERY_SCHEMA_VERSION = "deep_context_federation_query_v1"


def as_text(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    except Exception:
        return str(value)


def contains(value: Any, needle: str) -> bool:
    return needle.lower() in as_text(value).lower()


def rows(payload: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    return [dict(item) for item in payload.get(key) or [] if isinstance(item, Mapping)]


def query_federation(payload: Mapping[str, Any], *, preset: str, limit: int = 50) -> dict[str, Any]:
    if preset not in QUERY_PRESETS:
        raise ValueError(f"unknown preset {preset!r}")
    limit = max(1, int(limit))
    sources = rows(payload, "sources")
    entities = rows(payload, "entities")
    edges = rows(payload, "edges")
    conflicts = rows(payload, "conflicts")
    result_rows: list[dict[str, Any]] = []
    if preset == "surface-splits":
        result_rows = [item for item in [*conflicts, *entities] if contains(item, "surface")][:limit]
    elif preset == "claim-lineage":
        claim_entities = [item for item in entities if item.get("entity_type") == "claim_id"]
        claim_ids = {str(item.get("entity_id") or "") for item in claim_entities}
        lineage_edges = [item for item in edges if item.get("from_entity") in claim_ids or item.get("to_entity") in claim_ids]
        result_rows = [*claim_entities, *lineage_edges][:limit]
    elif preset == "stale-sources":
        result_rows = [item for item in [*sources, *conflicts] if contains(item, "stale") or contains(item, "missing") or contains(item, "optional_unavailable")][:limit]
    elif preset == "code-to-authority":
        result_rows = [item for item in entities if item.get("entity_type") in {"path", "symbol_fqn"}][:limit]
    elif preset == "r19-context":
        result_rows = [item for item in [*sources, *entities, *edges, *conflicts] if contains(item, "r19")][:limit]
    elif preset == "operator-projection":
        result_rows = [item for item in [*sources, *entities, *edges, *conflicts] if contains(item, "operator") or contains(item, "dashboard") or contains(item, "governance")][:limit]
    return {
        "schema_version": QUERY_SCHEMA_VERSION,
        "preset": preset,
        "status": "ok",
        "row_count": len(result_rows),
        "limit": limit,
        "rows": result_rows,
        "source_snapshot": {
            "federation_schema": payload.get("schema_version"),
            "generated_at": payload.get("generated_at"),
            "head_commit": payload.get("head_commit"),
            "authority_effect": payload.get("authority_effect"),
            "no_apply": payload.get("no_apply"),
        },
    }


def markdown(result: Mapping[str, Any]) -> str:
    lines = [
        f"# Deep Context Federation Query: {result.get('preset')}",
        "",
        f"- Status: `{result.get('status')}`",
        f"- Rows: `{result.get('row_count')}`",
        "",
    ]
    items = [dict(item) for item in result.get("rows") or [] if isinstance(item, Mapping)]
    if not items:
        lines.append("- no rows")
        return "\n".join(lines) + "\n"
    for index, item in enumerate(items, start=1):
        title = item.get("source_id") or item.get("entity_id") or item.get("edge_id") or item.get("conflict_id") or f"row-{index}"
        lines.append(f"## {index}. `{title}`")
        for key in ("role", "status", "required", "path", "entity_type", "value", "edge_type", "severity", "conflict_type", "source_id"):
            if key in item:
                lines.append(f"- `{key}`: `{item.get(key)}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
