"""Diff two Deep Context Federation artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _rows(payload: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    return [dict(item) for item in payload.get(key) or [] if isinstance(item, Mapping)]


def _by_id(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row.get(key) or ""): row for row in rows if row.get(key)}


def _changed(before: Mapping[str, Mapping[str, Any]], after: Mapping[str, Mapping[str, Any]], fields: list[str]) -> list[dict[str, Any]]:
    changed = []
    for item_id in sorted(set(before) & set(after)):
        before_row = before[item_id]
        after_row = after[item_id]
        deltas = {
            field: {"before": before_row.get(field), "after": after_row.get(field)}
            for field in fields
            if before_row.get(field) != after_row.get(field)
        }
        if deltas:
            changed.append({"id": item_id, "fields": deltas})
    return changed


def diff_federations(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    before_sources = _by_id(_rows(before, "sources"), "source_id")
    after_sources = _by_id(_rows(after, "sources"), "source_id")
    before_entities = _by_id(_rows(before, "entities"), "entity_id")
    after_entities = _by_id(_rows(after, "entities"), "entity_id")
    before_edges = _by_id(_rows(before, "edges"), "edge_id")
    after_edges = _by_id(_rows(after, "edges"), "edge_id")
    before_conflicts = _by_id(_rows(before, "conflicts"), "conflict_id")
    after_conflicts = _by_id(_rows(after, "conflicts"), "conflict_id")
    summary_before = before.get("summary") if isinstance(before.get("summary"), Mapping) else {}
    summary_after = after.get("summary") if isinstance(after.get("summary"), Mapping) else {}
    summary_delta = {
        key: {"before": summary_before.get(key), "after": summary_after.get(key)}
        for key in sorted(set(summary_before) | set(summary_after))
        if summary_before.get(key) != summary_after.get(key)
    }
    return {
        "schema_version": "deep_context_federation_diff_v1",
        "before_generated_at": before.get("generated_at"),
        "after_generated_at": after.get("generated_at"),
        "summary_delta": summary_delta,
        "sources": {
            "added": sorted(set(after_sources) - set(before_sources)),
            "removed": sorted(set(before_sources) - set(after_sources)),
            "changed": _changed(before_sources, after_sources, ["status", "sha256", "head_commit", "quality"]),
        },
        "entities": {
            "added_count": len(set(after_entities) - set(before_entities)),
            "removed_count": len(set(before_entities) - set(after_entities)),
            "added": sorted(set(after_entities) - set(before_entities))[:50],
            "removed": sorted(set(before_entities) - set(after_entities))[:50],
        },
        "edges": {
            "added_count": len(set(after_edges) - set(before_edges)),
            "removed_count": len(set(before_edges) - set(after_edges)),
            "added": sorted(set(after_edges) - set(before_edges))[:50],
            "removed": sorted(set(before_edges) - set(after_edges))[:50],
        },
        "conflicts": {
            "added": sorted(set(after_conflicts) - set(before_conflicts)),
            "removed": sorted(set(before_conflicts) - set(after_conflicts)),
            "changed": _changed(before_conflicts, after_conflicts, ["severity", "detail"]),
        },
    }


def markdown_diff(result: Mapping[str, Any]) -> str:
    lines = [
        "# Deep Context Federation Diff",
        "",
        "## Sources",
        "",
    ]
    sources = result.get("sources") if isinstance(result.get("sources"), Mapping) else {}
    for key in ("added", "removed", "changed"):
        lines.append(f"- `{key}`: `{len(sources.get(key) or [])}`")
    entities = result.get("entities") if isinstance(result.get("entities"), Mapping) else {}
    edges = result.get("edges") if isinstance(result.get("edges"), Mapping) else {}
    conflicts = result.get("conflicts") if isinstance(result.get("conflicts"), Mapping) else {}
    lines.extend(
        [
            "",
            "## Graph",
            "",
            f"- `entities_added`: `{entities.get('added_count')}`",
            f"- `entities_removed`: `{entities.get('removed_count')}`",
            f"- `edges_added`: `{edges.get('added_count')}`",
            f"- `edges_removed`: `{edges.get('removed_count')}`",
            "",
            "## Conflicts",
            "",
            f"- `added`: `{len(conflicts.get('added') or [])}`",
            f"- `removed`: `{len(conflicts.get('removed') or [])}`",
            f"- `changed`: `{len(conflicts.get('changed') or [])}`",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
