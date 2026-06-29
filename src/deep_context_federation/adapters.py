"""Typed semantic adapters for common context-tool exports."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

ENTITY_REF = dict[str, Any]


def _text(value: Any) -> str:
    if isinstance(value, (str, int, float)):
        return str(value)
    return ""


def _surface_rows(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    surfaces = payload.get("surfaces")
    if not surfaces and isinstance(payload.get("surface_map"), Mapping):
        surfaces = payload["surface_map"].get("surfaces")
    if isinstance(surfaces, Mapping):
        return [dict(value, id=str(key)) for key, value in surfaces.items() if isinstance(value, Mapping)]
    if isinstance(surfaces, Sequence) and not isinstance(surfaces, (str, bytes, bytearray)):
        return [item for item in surfaces if isinstance(item, Mapping)]
    return []


def _symbol_rows(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    symbols = payload.get("symbols")
    if not symbols and isinstance(payload.get("code_map"), Mapping):
        symbols = payload["code_map"].get("symbols")
    if isinstance(symbols, Sequence) and not isinstance(symbols, (str, bytes, bytearray)):
        return [item for item in symbols if isinstance(item, Mapping)]
    return []


def _graph_nodes(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    nodes = payload.get("nodes")
    if not nodes and isinstance(payload.get("graph"), Mapping):
        nodes = payload["graph"].get("nodes")
    if isinstance(nodes, Sequence) and not isinstance(nodes, (str, bytes, bytearray)):
        return [item for item in nodes if isinstance(item, Mapping)]
    return []


def _graph_edges(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    edges = payload.get("edges")
    if not edges and isinstance(payload.get("graph"), Mapping):
        edges = payload["graph"].get("edges")
    if isinstance(edges, Sequence) and not isinstance(edges, (str, bytes, bytearray)):
        return [item for item in edges if isinstance(item, Mapping)]
    return []


def _entity_ref(entity_type: str, value: str, **metadata: Any) -> ENTITY_REF:
    return {
        "entity_type": entity_type,
        "value": value,
        "label": str(metadata.pop("label", "") or value),
        "metadata": metadata,
    }


def _node_ref(row: Mapping[str, Any]) -> ENTITY_REF | None:
    for key, entity_type in [
        ("symbol_fqn", "symbol_fqn"),
        ("path", "path"),
        ("surface_id", "surface_id"),
        ("claim_id", "claim_id"),
        ("artifact_id", "artifact_id"),
        ("task_id", "task_id"),
        ("thread_id", "thread_id"),
        ("owner", "owner_id"),
    ]:
        value = _text(row.get(key))
        if value:
            return _entity_ref(entity_type, value, label=_text(row.get("label")) or value, adapter="graph_node")
    value = _text(row.get("id") or row.get("name"))
    if value:
        kind = _text(row.get("kind") or row.get("type") or "artifact")
        entity_type = "symbol_fqn" if kind == "symbol" else ("path" if kind == "path" else ("surface_id" if kind == "surface" else "artifact_id"))
        return _entity_ref(entity_type, value, label=_text(row.get("label")) or value, adapter="graph_node", graph_kind=kind)
    return None


def _edge_type(raw: str) -> str:
    normalized = raw.strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "DECLARES": "DECLARES",
        "SUPPORTS": "SUPPORTS",
        "ADVISES": "ADVISES",
        "OWNS": "OWNS",
        "OWNER_OF": "OWNS",
        "DERIVES_FROM": "DERIVES_FROM",
        "REFERENCES_SYMBOL": "REFERENCES_SYMBOL",
        "REFERENCES": "REFERENCES_SYMBOL",
        "CALLS": "REFERENCES_SYMBOL",
        "CONFLICTS_WITH": "CONFLICTS_WITH",
        "STALE_FOR": "STALE_FOR",
    }
    return aliases.get(normalized, "DERIVES_FROM")


def _fallback_endpoint_ref(value: str) -> ENTITY_REF:
    if "/" in value or "\\" in value or value.endswith((".py", ".ts", ".tsx", ".js", ".json", ".md", ".yaml", ".yml")):
        return _entity_ref("path", value, adapter="graph_edge_endpoint")
    if "." in value and " " not in value:
        return _entity_ref("symbol_fqn", value, adapter="graph_edge_endpoint")
    return _entity_ref("artifact_id", value, adapter="graph_edge_endpoint")


def _append_entity(entities: list[ENTITY_REF], seen: set[tuple[str, str]], ref: ENTITY_REF | None) -> None:
    if not ref:
        return
    key = (str(ref["entity_type"]), str(ref["value"]))
    if key in seen:
        return
    seen.add(key)
    entities.append(ref)


def extract_adapter_items(payload: Mapping[str, Any], *, source_id: str, role: str) -> dict[str, Any]:
    """Return semantic entity/edge specs from common graph-like JSON shapes."""

    entities: list[ENTITY_REF] = []
    edges: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    surface_count = 0
    owner_edge_count = 0
    for row in _surface_rows(payload):
        surface_id = _text(row.get("surface_id") or row.get("id") or row.get("name"))
        if not surface_id:
            continue
        surface_count += 1
        surface = _entity_ref("surface_id", surface_id, label=_text(row.get("display") or row.get("label")) or surface_id, adapter="surface")
        _append_entity(entities, seen, surface)
        owner = _text(row.get("owner") or row.get("owner_agent") or row.get("owner_board") or row.get("owner_lane"))
        if owner:
            owner_ref = _entity_ref("owner_id", owner, adapter="surface_owner")
            _append_entity(entities, seen, owner_ref)
            edges.append({"edge_type": "OWNS", "from": owner_ref, "to": surface, "evidence": source_id})
            owner_edge_count += 1
        path = _text(row.get("path"))
        if path:
            path_ref = _entity_ref("path", path, adapter="surface_path")
            _append_entity(entities, seen, path_ref)
            edges.append({"edge_type": "DERIVES_FROM", "from": surface, "to": path_ref, "evidence": source_id})

    symbol_count = 0
    for row in _symbol_rows(payload):
        symbol = _text(row.get("symbol_fqn") or row.get("fqn") or row.get("name"))
        path = _text(row.get("path") or row.get("file"))
        surface_id = _text(row.get("surface_id"))
        if symbol:
            symbol_count += 1
            symbol_ref = _entity_ref("symbol_fqn", symbol, adapter="symbol")
            _append_entity(entities, seen, symbol_ref)
            if path:
                path_ref = _entity_ref("path", path, adapter="symbol_path")
                _append_entity(entities, seen, path_ref)
                edges.append({"edge_type": "REFERENCES_SYMBOL", "from": path_ref, "to": symbol_ref, "evidence": source_id})
            if surface_id:
                surface_ref = _entity_ref("surface_id", surface_id, adapter="symbol_surface")
                _append_entity(entities, seen, surface_ref)
                edges.append({"edge_type": "DERIVES_FROM", "from": symbol_ref, "to": surface_ref, "evidence": source_id})

    node_refs: dict[str, ENTITY_REF] = {}
    for row in _graph_nodes(payload):
        ref = _node_ref(row)
        node_id = _text(row.get("id") or row.get("name") or row.get("symbol_fqn") or row.get("path") or row.get("surface_id"))
        if ref and node_id:
            node_refs[node_id] = ref
            _append_entity(entities, seen, ref)
    graph_edge_count = 0
    for row in _graph_edges(payload):
        raw_from = _text(row.get("from") or row.get("source") or row.get("from_id") or row.get("source_id"))
        raw_to = _text(row.get("to") or row.get("target") or row.get("to_id") or row.get("target_id"))
        if not raw_from or not raw_to:
            continue
        from_ref = node_refs.get(raw_from) or _fallback_endpoint_ref(raw_from)
        to_ref = node_refs.get(raw_to) or _fallback_endpoint_ref(raw_to)
        _append_entity(entities, seen, from_ref)
        _append_entity(entities, seen, to_ref)
        edges.append(
            {
                "edge_type": _edge_type(_text(row.get("edge_type") or row.get("relation") or row.get("type"))),
                "from": from_ref,
                "to": to_ref,
                "evidence": _text(row.get("evidence")) or source_id,
            }
        )
        graph_edge_count += 1

    return {
        "entities": entities,
        "edges": edges,
        "conflicts": conflicts,
        "stats": {
            "role": role,
            "surface_count": surface_count,
            "owner_edge_count": owner_edge_count,
            "symbol_count": symbol_count,
            "graph_node_count": len(node_refs),
            "graph_edge_count": graph_edge_count,
            "semantic_entity_count": len(entities),
            "semantic_edge_count": len(edges),
        },
    }
