"""Graph intelligence helpers over a federation artifact."""

from __future__ import annotations

import json
from collections import Counter, deque
from collections.abc import Mapping
from typing import Any


def _text(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    except Exception:
        return str(value)


def _rows(payload: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    return [dict(item) for item in payload.get(key) or [] if isinstance(item, Mapping)]


def summarize_graph(payload: Mapping[str, Any], *, top_n: int = 20) -> dict[str, Any]:
    entities = _rows(payload, "entities")
    edges = _rows(payload, "edges")
    degree: Counter[str] = Counter()
    edge_type_counts: Counter[str] = Counter()
    for edge in edges:
        from_entity = str(edge.get("from_entity") or "")
        to_entity = str(edge.get("to_entity") or "")
        if from_entity:
            degree[from_entity] += 1
        if to_entity:
            degree[to_entity] += 1
        edge_type_counts[str(edge.get("edge_type") or "")] += 1
    by_id = {str(entity.get("entity_id") or ""): entity for entity in entities}
    top = []
    for entity_id, count in degree.most_common(top_n):
        entity = by_id.get(entity_id, {})
        top.append(
            {
                "entity_id": entity_id,
                "degree": count,
                "entity_type": entity.get("entity_type"),
                "value": entity.get("value"),
            }
        )
    return {
        "schema_version": "deep_context_federation_graph_summary_v1",
        "entity_count": len(entities),
        "edge_count": len(edges),
        "edge_type_counts": dict(sorted(edge_type_counts.items())),
        "top_degree_entities": top,
    }


def trace_federation(payload: Mapping[str, Any], *, match: str, depth: int = 2, limit: int = 50) -> dict[str, Any]:
    entities = _rows(payload, "entities")
    edges = _rows(payload, "edges")
    by_id = {str(entity.get("entity_id") or ""): entity for entity in entities}
    seeds = [
        entity
        for entity in entities
        if match.lower() in _text(entity).lower()
    ]
    seed_ids = [str(entity.get("entity_id") or "") for entity in seeds if entity.get("entity_id")]
    adjacency: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        from_entity = str(edge.get("from_entity") or "")
        to_entity = str(edge.get("to_entity") or "")
        if not from_entity or not to_entity:
            continue
        adjacency.setdefault(from_entity, []).append(edge)
        adjacency.setdefault(to_entity, []).append(edge)
    visited = set(seed_ids)
    visited_edges: dict[str, dict[str, Any]] = {}
    queue: deque[tuple[str, int]] = deque((seed_id, 0) for seed_id in seed_ids)
    max_depth = max(0, int(depth))
    max_rows = max(1, int(limit))
    while queue:
        entity_id, current_depth = queue.popleft()
        if current_depth >= max_depth:
            continue
        for edge in adjacency.get(entity_id, []):
            edge_id = str(edge.get("edge_id") or "")
            if edge_id:
                visited_edges[edge_id] = edge
            for neighbor in (str(edge.get("from_entity") or ""), str(edge.get("to_entity") or "")):
                if neighbor and neighbor not in visited and len(visited) < max_rows:
                    visited.add(neighbor)
                    queue.append((neighbor, current_depth + 1))
            if len(visited_edges) >= max_rows and len(visited) >= max_rows:
                break
        if len(visited_edges) >= max_rows and len(visited) >= max_rows:
            break
    nodes = [by_id[entity_id] for entity_id in sorted(visited) if entity_id in by_id]
    return {
        "schema_version": "deep_context_federation_trace_v1",
        "match": match,
        "depth": max_depth,
        "limit": max_rows,
        "seed_count": len(seed_ids),
        "node_count": len(nodes),
        "edge_count": len(visited_edges),
        "seeds": seeds[:max_rows],
        "nodes": nodes[:max_rows],
        "edges": list(visited_edges.values())[:max_rows],
    }


def markdown_trace(result: Mapping[str, Any]) -> str:
    lines = [
        f"# Deep Context Federation Trace: {result.get('match')}",
        "",
        f"- Depth: `{result.get('depth')}`",
        f"- Seeds: `{result.get('seed_count')}`",
        f"- Nodes: `{result.get('node_count')}`",
        f"- Edges: `{result.get('edge_count')}`",
        "",
    ]
    for index, node in enumerate(result.get("nodes") or [], start=1):
        if isinstance(node, Mapping):
            lines.append(f"## {index}. `{node.get('entity_id')}`")
            lines.append(f"- `type`: `{node.get('entity_type')}`")
            lines.append(f"- `value`: `{node.get('value')}`")
            lines.append("")
    if not result.get("nodes"):
        lines.append("- no nodes")
    return "\n".join(lines).rstrip() + "\n"
