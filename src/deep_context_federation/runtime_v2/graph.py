"""SQLite read model for generic DCF v2 generation snapshots."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import deque
from pathlib import Path
from typing import Any

from .collectors import path_matches_surface


SCHEMA = """
PRAGMA journal_mode=OFF;
PRAGMA synchronous=OFF;
PRAGMA temp_store=MEMORY;
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE entities (
    entity_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    label TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE edges (
    source_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (source_id, edge_type, target_id)
);
CREATE INDEX edges_source_idx ON edges(source_id);
CREATE INDEX edges_target_idx ON edges(target_id);
CREATE INDEX entities_type_idx ON entities(entity_type);
CREATE VIRTUAL TABLE entity_fts USING fts5(
    entity_id UNINDEXED, label, content, tokenize='unicode61'
);
"""


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}:{hashlib.sha256(value.encode('utf-8')).hexdigest()[:20]}"


class GraphWriter:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.entities: dict[str, tuple[str, str, str, str]] = {}
        self.edges: dict[tuple[str, str, str], tuple[str, str, str, str]] = {}

    def entity(self, entity_id: str, entity_type: str, label: str, payload: dict[str, Any]) -> None:
        self.entities.setdefault(entity_id, (entity_id, entity_type, label, _json(payload)))

    def edge(self, source_id: str, edge_type: str, target_id: str, payload: dict[str, Any] | None = None) -> None:
        key = (source_id, edge_type, target_id)
        self.edges.setdefault(key, (source_id, edge_type, target_id, _json(payload or {})))

    def flush(self) -> None:
        rows = list(self.entities.values())
        self.connection.executemany(
            "INSERT INTO entities(entity_id, entity_type, label, payload_json) VALUES (?, ?, ?, ?)",
            rows,
        )
        self.connection.executemany(
            "INSERT INTO entity_fts(entity_id, label, content) VALUES (?, ?, ?)",
            ((entity_id, label, payload[:2048]) for entity_id, _, label, payload in rows),
        )
        self.connection.executemany(
            "INSERT INTO edges(source_id, edge_type, target_id, payload_json) VALUES (?, ?, ?, ?)",
            self.edges.values(),
        )


def build_index(path: Path, *, snapshot: dict[str, Any], native: dict[str, Any]) -> dict[str, Any]:
    """Build one immutable generation-local graph."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.executescript(SCHEMA)
        writer = GraphWriter(connection)
        generation_id = str(snapshot["generation_id"])
        connection.execute("INSERT INTO metadata(key, value) VALUES ('generation_id', ?)", (generation_id,))
        connection.execute("INSERT INTO metadata(key, value) VALUES ('schema_version', 'dcf_graph_v2')")
        connection.execute("INSERT INTO metadata(key, value) VALUES ('authority_effect', 'none')")
        connection.execute("INSERT INTO metadata(key, value) VALUES ('no_apply', 'true')")

        authority = native.get("authority", {})
        authority_contract = str(authority.get("authority_contract") or "")
        if authority_contract:
            contract_id = f"contract:{authority_contract}"
            writer.entity(contract_id, "authority_contract", authority_contract, {"path": authority_contract, "authority_effect": "none", "no_apply": True})
        else:
            contract_id = "contract:unavailable"
            writer.entity(contract_id, "typed_absence", "authority contract unavailable", {"code": "source_unavailable", "authority_effect": "none", "no_apply": True})

        surfaces = native.get("surfaces", {}).get("surfaces", [])
        for surface in surfaces:
            surface_id = f"surface:{surface['surface_id']}"
            writer.entity(surface_id, "surface", str(surface.get("display") or surface["surface_id"]), surface)
            writer.edge(surface_id, "DECLARES", contract_id)
            owner = str(surface.get("owner_lane") or "unowned")
            owner_id = f"owner:{owner}"
            writer.entity(owner_id, "owner", owner, {"owner_board": surface.get("owner_board", "")})
            writer.edge(surface_id, "OWNED_BY", owner_id)
            for reference in surface.get("logical_ref", []):
                path_id = f"path:{reference}"
                writer.entity(path_id, "path", str(reference), {"path": reference, "declared": True})
                writer.edge(surface_id, "OWNS", path_id)
                writer.edge(path_id, "BELONGS_TO", surface_id)
            for command in surface.get("required_verifiers", []):
                verifier_id = _stable_id("verifier", str(command))
                writer.entity(verifier_id, "verifier", str(command), {"command": command, "authority_effect": "none"})
                writer.edge(surface_id, "REQUIRES", verifier_id)

        for artifact in authority.get("artifacts", []):
            artifact_id = str(artifact.get("artifact_id") or _stable_id("evidence", str(artifact.get("path"))))
            writer.entity(artifact_id, "evidence", str(artifact.get("path") or artifact_id), artifact)
            for surface_id in artifact.get("surface_ids", []):
                writer.edge(f"surface:{surface_id}", "ADVISES", artifact_id, {"advisory_only": True})

        for claim in authority.get("claims", []):
            claim_id = f"claim:{claim['claim_id']}"
            writer.entity(claim_id, "claim", str(claim.get("statement") or claim["claim_id"]), claim)
            writer.edge(claim_id, "DECLARES", contract_id)
            writer.edge(claim_id, "ABOUT", f"surface:{claim.get('surface_id', '')}")
            for evidence in claim.get("evidence", []):
                evidence_id = f"path:{evidence}"
                writer.entity(evidence_id, "evidence", str(evidence), {"path": evidence, "declared": True})
                writer.edge(claim_id, "SUPPORTED_BY", evidence_id)
            for artifact_id in claim.get("evidence_artifact_ids", []):
                writer.edge(claim_id, "SUPPORTED_BY", str(artifact_id), {"advisory_only": True})
            for command in claim.get("verifiers", []):
                writer.edge(claim_id, "VERIFIED_BY", _stable_id("verifier", str(command)))

        name_to_symbols: dict[str, list[str]] = {}
        for symbol in native.get("symbols", {}).get("symbols", []):
            symbol_id = str(symbol["entity_id"])
            name_to_symbols.setdefault(str(symbol["name"]), []).append(symbol_id)
            writer.entity(symbol_id, "symbol", str(symbol["fqn"]), symbol)
            path_id = f"path:{symbol['path']}"
            writer.entity(path_id, "path", str(symbol["path"]), {"path": symbol["path"], "tracked": True})
            writer.edge(symbol_id, "DEFINED_IN", path_id, {"line": symbol.get("line")})
            for surface in surfaces:
                if path_matches_surface(str(symbol["path"]), surface):
                    writer.edge(path_id, "BELONGS_TO", f"surface:{surface['surface_id']}")
                    break
            for reference in symbol.get("references", []):
                reference_id = f"reference:{reference}"
                writer.entity(reference_id, "symbol_reference", str(reference), {"name": reference})
                writer.edge(symbol_id, "REFERENCES_SYMBOL", reference_id)
        for name, symbol_ids in name_to_symbols.items():
            for symbol_id in symbol_ids:
                writer.edge(f"reference:{name}", "MAY_RESOLVE_TO", symbol_id)

        working_state = native.get("working_state", {})
        for lease in working_state.get("active_leases", []):
            identity = str(lease.get("task_id") or lease.get("id") or lease.get("source_sha256") or "unknown")
            task_id = f"task:{identity}"
            writer.entity(task_id, "task", identity, lease)
            writer.edge(task_id, "PROJECTED_FROM", f"path:{lease.get('source_path', '')}", {"advisory_only": True})
        for receipt in working_state.get("completed_receipts", []):
            identity = str(receipt.get("task_id") or receipt.get("id") or receipt.get("source_sha256") or "unknown")
            receipt_id = f"receipt:{identity}"
            writer.entity(receipt_id, "task_receipt", identity, receipt)

        for event in native.get("timeline", {}).get("events", []):
            commit_id = f"commit:{event['commit']}"
            writer.entity(commit_id, "commit", str(event.get("subject") or event["commit"]), event)

        for source, finding in native.get("source_errors", {}).items():
            finding_id = f"absence:{source}"
            writer.entity(finding_id, "typed_absence", str(finding.get("code") or source), finding)

        writer.flush()
        connection.commit()
        counts = {
            "entity_count": connection.execute("SELECT COUNT(*) FROM entities").fetchone()[0],
            "edge_count": connection.execute("SELECT COUNT(*) FROM edges").fetchone()[0],
            "fts_row_count": connection.execute("SELECT COUNT(*) FROM entity_fts").fetchone()[0],
            "graph_generation_id": generation_id,
            "authority_effect": "none",
            "no_apply": True,
        }
        connection.execute("PRAGMA optimize")
        connection.commit()
        return counts
    finally:
        connection.close()


def _entity(connection: sqlite3.Connection, entity_id: str) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT entity_id, entity_type, label, payload_json FROM entities WHERE entity_id = ?",
        (entity_id,),
    ).fetchone()
    if row is None:
        return None
    return {"entity_id": row[0], "entity_type": row[1], "label": row[2], "payload": json.loads(row[3])}


def resolve_entities(
    index: Path | sqlite3.Connection,
    target: str,
    *,
    base_connection: sqlite3.Connection | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Resolve an exact id first, then FTS and bounded substring matches."""

    owns_connection = not isinstance(index, sqlite3.Connection)
    connection = sqlite3.connect(index) if owns_connection else index
    try:
        exact = _entity(connection, target)
        if exact is not None:
            return [exact]
        query = " ".join(part for part in target.replace(".", " ").replace("/", " ").split() if part)
        rows: list[tuple[Any, ...]] = []
        if query:
            try:
                rows = connection.execute(
                    "SELECT e.entity_id, e.entity_type, e.label, e.payload_json FROM entity_fts f JOIN entities e USING(entity_id) WHERE entity_fts MATCH ? LIMIT ?",
                    (query, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []
        if not rows:
            rows = connection.execute(
                "SELECT entity_id, entity_type, label, payload_json FROM entities WHERE label LIKE ? OR entity_id LIKE ? ORDER BY entity_id LIMIT ?",
                (f"%{target}%", f"%{target}%", limit),
            ).fetchall()
        resolved = [{"entity_id": row[0], "entity_type": row[1], "label": row[2], "payload": json.loads(row[3])} for row in rows]
        if base_connection is not None and len(resolved) < limit:
            seen = {row["entity_id"] for row in resolved}
            for row in resolve_entities(base_connection, target, limit=limit):
                if row["entity_id"] not in seen:
                    resolved.append(row)
                if len(resolved) >= limit:
                    break
        return resolved
    finally:
        if owns_connection:
            connection.close()


def traverse(
    index_path: Path,
    start_ids: list[str] | None = None,
    *,
    base_index_path: Path | None = None,
    target: str | None = None,
    depth: int = 2,
    terminal_types: set[str] | None = None,
    edge_types: set[str] | None = None,
    direction: str = "both",
    max_paths: int = 200,
    limit: int | None = None,
) -> dict[str, Any]:
    if not 1 <= depth <= 4:
        raise ValueError("depth must be between 1 and 4")
    connection = sqlite3.connect(f"file:{index_path}?mode=ro", uri=True)
    base_connection = sqlite3.connect(f"file:{base_index_path}?mode=ro", uri=True) if base_index_path else None
    path_limit = limit or max_paths
    try:
        starts = resolve_entities(connection, target, base_connection=base_connection) if target else [row for entity_id in (start_ids or []) if (row := _entity(connection, entity_id)) is not None]
        queue: deque[tuple[str, list[dict[str, Any]], int]] = deque((row["entity_id"], [{"entity": row}], 0) for row in starts)
        visited: set[tuple[str, int]] = set()
        paths: list[list[dict[str, Any]]] = []
        while queue and len(paths) < path_limit:
            entity_id, path, level = queue.popleft()
            marker = (entity_id, level)
            if marker in visited:
                continue
            visited.add(marker)
            entity = path[-1]["entity"]
            if level > 0 and (not terminal_types or entity["entity_type"] in terminal_types):
                paths.append(path)
            if level >= depth:
                if path not in paths:
                    paths.append(path)
                continue
            clauses: list[str] = []
            parameters: list[str] = []
            if direction in {"outgoing", "both"}:
                clauses.append("SELECT source_id, edge_type, target_id, payload_json, 'outgoing' FROM edges WHERE source_id = ?")
                parameters.append(entity_id)
            if direction in {"incoming", "both"}:
                clauses.append("SELECT source_id, edge_type, target_id, payload_json, 'incoming' FROM edges WHERE target_id = ?")
                parameters.append(entity_id)
            if not clauses:
                continue
            edge_rows = connection.execute(" UNION ALL ".join(clauses), parameters).fetchall()
            if base_connection is not None:
                edge_rows.extend(base_connection.execute(" UNION ALL ".join(clauses), parameters).fetchall())
            for source_id, edge_type, target_id, payload_json, row_direction in edge_rows:
                if edge_types and edge_type not in edge_types:
                    continue
                next_id = target_id if row_direction == "outgoing" else source_id
                next_entity = _entity(connection, next_id) or (_entity(base_connection, next_id) if base_connection else None)
                if next_entity is None:
                    continue
                step = {"edge": {"source_id": source_id, "edge_type": edge_type, "target_id": target_id, "direction": row_direction, "payload": json.loads(payload_json)}, "entity": next_entity}
                queue.append((next_id, [*path, step], level + 1))
        return {"resolved": starts, "paths": paths, "path_count": len(paths), "truncated": bool(queue), "authority_effect": "none", "no_apply": True}
    finally:
        connection.close()
        if base_connection is not None:
            base_connection.close()


def graph_summary(index_path: Path) -> dict[str, Any]:
    with sqlite3.connect(index_path) as connection:
        metadata = dict(connection.execute("SELECT key, value FROM metadata"))
        return {
            "entity_count": connection.execute("SELECT COUNT(*) FROM entities").fetchone()[0],
            "edge_count": connection.execute("SELECT COUNT(*) FROM edges").fetchone()[0],
            "fts_row_count": connection.execute("SELECT COUNT(*) FROM entity_fts").fetchone()[0],
            "graph_generation_id": metadata.get("generation_id"),
            "schema_version": metadata.get("schema_version"),
            "authority_effect": "none",
            "no_apply": True,
        }
