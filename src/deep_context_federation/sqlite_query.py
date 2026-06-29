"""SQLite read-model queries for Deep Context Federation."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from deep_context_federation.query import SOURCE_IDENTITY_KEYS
from deep_context_federation.query import source_identity_policy
from deep_context_federation.query import strip_source_identity

SQL_QUERY_SCHEMA_VERSION = "deep_context_federation_sql_query_v1"

SQL_PRESETS: dict[str, dict[str, str]] = {
    "source-health": {
        "description": "Source status, required flag, and summary JSON.",
        "sql": """
            select source_id, role, required, status, path, quality_score, quality_reasons_json, summary_json
            from sources
            order by quality_score asc, required desc, source_id asc
            limit :limit
        """,
    },
    "stale-sources": {
        "description": "Sources and conflicts with stale or missing status.",
        "sql": """
            select 'source' as kind, source_id as id, status, role as detail
            from sources
            where status in ('stale', 'missing', 'error', 'optional_unavailable')
            union all
            select 'conflict' as kind, conflict_id as id, severity as status, detail_json as detail
            from conflicts
            where conflict_type in ('source_stale', 'source_missing')
            limit :limit
        """,
    },
    "claim-lineage": {
        "description": "Claim entities and their support/advisory edges.",
        "sql": """
            select 'entity' as kind, entity_id as id, entity_type as type, value as detail
            from entities
            where entity_type = 'claim_id'
            union all
            select 'edge' as kind, edge_id as id, edge_type as type, source_id as detail
            from edges
            where from_entity in (select entity_id from entities where entity_type = 'claim_id')
            limit :limit
        """,
    },
    "surface-splits": {
        "description": "Surface entities and surface-related conflicts.",
        "sql": """
            select 'entity' as kind, entity_id as id, entity_type as type, value as detail
            from entities
            where entity_type = 'surface_id' or value like '%surface%'
            union all
            select 'conflict' as kind, conflict_id as id, conflict_type as type, detail_json as detail
            from conflicts
            where conflict_type like '%surface%'
            limit :limit
        """,
    },
    "code-to-authority": {
        "description": "Path and symbol entities for source-to-authority navigation.",
        "sql": """
            select entity_id, entity_type, value, source_ids_json
            from entities
            where entity_type in ('path', 'symbol_fqn')
            order by entity_type asc, value asc
            limit :limit
        """,
    },
    "operator-projection": {
        "description": "Rows mentioning operator, dashboard, or governance.",
        "sql": """
            select kind, row_id as id, text
            from search_index
            where text like '%operator%' or text like '%dashboard%' or text like '%governance%'
            order by kind asc, row_id asc
            limit :limit
        """,
    },
    "search": {
        "description": "Text search over sources, entities, conflicts, and fusion roles.",
        "sql": """
            select kind, row_id as id, text
            from search_index
            where text like :needle
            order by kind asc, row_id asc
            limit :limit
        """,
    },
}


def connect_readonly(sqlite_path: Path) -> sqlite3.Connection:
    if not sqlite_path.exists():
        raise FileNotFoundError(f"federation SQLite projection missing: {sqlite_path}")
    uri = f"file:{sqlite_path.resolve().as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def rows_from_cursor(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
    columns = [str(item[0]) for item in cursor.description or []]
    return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]


def _strip_json_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped or stripped[0] not in "[{":
        return value
    try:
        parsed = json.loads(stripped)
    except Exception:
        return value
    return json.dumps(strip_source_identity(parsed), ensure_ascii=True, sort_keys=True)


def _public_sql_row(row: dict[str, Any]) -> dict[str, Any]:
    public = {}
    kind = str(row.get("kind") or "")
    for key, value in row.items():
        if key in SOURCE_IDENTITY_KEYS or key == "source_ids_json":
            continue
        if key == "id" and kind == "source":
            continue
        if key == "detail" and kind == "edge":
            continue
        public[key] = _strip_json_text(value)
    return public


def query_sqlite(
    sqlite_path: Path,
    *,
    preset: str,
    limit: int = 50,
    search: str = "",
    include_source_identity: bool = False,
) -> dict[str, Any]:
    if preset not in SQL_PRESETS:
        raise ValueError(f"unknown SQL preset {preset!r}")
    limit = max(1, int(limit))
    spec = SQL_PRESETS[preset]
    params: dict[str, Any] = {"limit": limit, "needle": f"%{search}%"}
    with connect_readonly(sqlite_path) as conn:
        tables = {
            str(row[0])
            for row in conn.execute("select name from sqlite_master where type = 'table'").fetchall()
        }
        required = {"sources", "entities", "edges", "conflicts"}
        if preset in {"operator-projection", "search"}:
            required.add("search_index")
        missing = sorted(required - tables)
        if missing:
            raise RuntimeError(
                f"SQLite projection is missing tables {missing}; rebuild with `dcf assemble-context --write`."
            )
        cursor = conn.execute(spec["sql"], params)
        rows = rows_from_cursor(cursor)
    public_rows = rows if include_source_identity else [_public_sql_row(row) for row in rows]
    return {
        "schema_version": SQL_QUERY_SCHEMA_VERSION,
        "preset": preset,
        "description": spec["description"],
        "authority_effect": "none",
        "no_apply": True,
        "sqlite_path": sqlite_path.as_posix(),
        "limit": limit,
        "search": search,
        "row_count": len(public_rows),
        "rows": public_rows,
        "source_identity_policy": source_identity_policy(include_source_identity=include_source_identity),
    }


def markdown(result: dict[str, Any]) -> str:
    lines = [
        f"# Deep Context Federation SQL Query: {result.get('preset')}",
        "",
        f"- Rows: `{result.get('row_count')}`",
        f"- Source ids exposed: `{(result.get('source_identity_policy') or {}).get('source_ids_exposed')}`",
    ]
    if result.get("search"):
        lines.append(f"- Search: `{result.get('search')}`")
    lines.append("")
    for index, row in enumerate(result.get("rows") or [], start=1):
        title = row.get("id") or row.get("entity_id") or row.get("path") or row.get("role") or f"row-{index}"
        lines.append(f"## {index}. `{title}`")
        for key, value in row.items():
            if key == "id":
                continue
            rendered = json.dumps(value, ensure_ascii=True, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
            lines.append(f"- `{key}`: `{rendered}`")
        lines.append("")
    if not result.get("rows"):
        lines.append("- no rows")
    return "\n".join(lines).rstrip() + "\n"
