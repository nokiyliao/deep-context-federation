"""Ranking helpers for federation entities and sources."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any


EDGE_WEIGHTS = {
    "SUPPORTS": 4,
    "OWNS": 3,
    "REFERENCES_SYMBOL": 3,
    "DERIVES_FROM": 2,
    "DECLARES": 1,
    "ADVISES": 1,
    "CONFLICTS_WITH": -3,
    "STALE_FOR": -2,
}


def _rows(payload: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    return [dict(item) for item in payload.get(key) or [] if isinstance(item, Mapping)]


def _source_quality_by_id(payload: Mapping[str, Any]) -> dict[str, int]:
    rows: dict[str, int] = {}
    for source in _rows(payload, "sources"):
        quality = source.get("quality") if isinstance(source.get("quality"), Mapping) else {}
        rows[str(source.get("source_id") or "")] = int(quality.get("score") or 100)
    return rows


def rank_entities(payload: Mapping[str, Any], *, limit: int = 20) -> dict[str, Any]:
    entities = _rows(payload, "entities")
    edges = _rows(payload, "edges")
    quality_by_source = _source_quality_by_id(payload)
    degree: Counter[str] = Counter()
    weighted_degree: Counter[str] = Counter()
    for edge in edges:
        edge_type = str(edge.get("edge_type") or "")
        weight = EDGE_WEIGHTS.get(edge_type, 1)
        for key in ("from_entity", "to_entity"):
            entity_id = str(edge.get(key) or "")
            if entity_id:
                degree[entity_id] += 1
                weighted_degree[entity_id] += weight
    ranked: list[dict[str, Any]] = []
    for entity in entities:
        entity_id = str(entity.get("entity_id") or "")
        source_ids = [str(item) for item in entity.get("source_ids") or []]
        source_score = 0
        if source_ids:
            source_score = round(sum(quality_by_source.get(source_id, 100) for source_id in source_ids) / len(source_ids))
        score = int(weighted_degree[entity_id]) * 10 + int(degree[entity_id]) * 3 + source_score
        if entity.get("entity_type") in {"claim_id", "surface_id", "symbol_fqn"}:
            score += 10
        ranked.append(
            {
                "entity_id": entity_id,
                "entity_type": entity.get("entity_type"),
                "value": entity.get("value"),
                "score": score,
                "degree": int(degree[entity_id]),
                "weighted_degree": int(weighted_degree[entity_id]),
                "source_score": source_score,
                "source_ids": source_ids,
            }
        )
    ranked.sort(key=lambda row: (-int(row["score"]), str(row["entity_type"]), str(row["value"])))
    return {
        "schema_version": "deep_context_federation_entity_rank_v1",
        "limit": max(1, int(limit)),
        "row_count": min(max(1, int(limit)), len(ranked)),
        "rows": ranked[: max(1, int(limit))],
    }


def rank_sources(payload: Mapping[str, Any], *, limit: int = 20) -> dict[str, Any]:
    sources = _rows(payload, "sources")
    conflicts = _rows(payload, "conflicts")
    conflict_counts: Counter[str] = Counter(str(item.get("source_id") or "") for item in conflicts)
    error_counts: Counter[str] = Counter(
        str(item.get("source_id") or "")
        for item in conflicts
        if str(item.get("severity") or "") == "error"
    )
    warning_counts: Counter[str] = Counter(
        str(item.get("source_id") or "")
        for item in conflicts
        if str(item.get("severity") or "") == "warning"
    )
    rows: list[dict[str, Any]] = []
    for source in sources:
        source_id = str(source.get("source_id") or "")
        quality = source.get("quality") if isinstance(source.get("quality"), Mapping) else {}
        quality_score = int(quality.get("score") or 100)
        risk = (100 - quality_score) + error_counts[source_id] * 50 + warning_counts[source_id] * 10
        if source.get("required"):
            risk += 5
        rows.append(
            {
                "source_id": source_id,
                "role": source.get("role"),
                "required": bool(source.get("required")),
                "status": source.get("status"),
                "quality_score": quality_score,
                "quality_reasons": list(quality.get("reasons") or []),
                "conflict_count": int(conflict_counts[source_id]),
                "error_count": int(error_counts[source_id]),
                "warning_count": int(warning_counts[source_id]),
                "risk_score": risk,
            }
        )
    rows.sort(key=lambda row: (-int(row["risk_score"]), str(row["source_id"])))
    return {
        "schema_version": "deep_context_federation_source_rank_v1",
        "limit": max(1, int(limit)),
        "row_count": min(max(1, int(limit)), len(rows)),
        "rows": rows[: max(1, int(limit))],
    }


def markdown_rank(result: Mapping[str, Any]) -> str:
    lines = [
        f"# Deep Context Federation Rank: `{result.get('schema_version')}`",
        "",
        f"- Rows: `{result.get('row_count')}`",
        "",
    ]
    for index, row in enumerate(result.get("rows") or [], start=1):
        if not isinstance(row, Mapping):
            continue
        title = row.get("entity_id") or row.get("source_id") or f"row-{index}"
        lines.append(f"## {index}. `{title}`")
        for key, value in row.items():
            if key in {"entity_id", "source_id"}:
                continue
            lines.append(f"- `{key}`: `{value}`")
        lines.append("")
    if not result.get("rows"):
        lines.append("- no rows")
    return "\n".join(lines).rstrip() + "\n"
