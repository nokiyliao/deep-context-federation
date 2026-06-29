"""Source fingerprint cache for incremental federation runs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

CACHE_SCHEMA_VERSION = "deep_context_federation_source_cache_v1"
DEFAULT_CACHE_NAME = "source_fingerprints.json"


def load_cache(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def source_fingerprints(sources: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for source_id, source in sources.items():
        rows[source_id] = {
            "source_id": source_id,
            "status": source.get("status"),
            "path": source.get("path"),
            "sha256": source.get("sha256"),
            "byte_size": source.get("byte_size"),
            "head_commit": source.get("head_commit"),
        }
    return rows


def compare_cache(sources: Mapping[str, Mapping[str, Any]], previous_cache: Mapping[str, Any]) -> dict[str, Any]:
    current = source_fingerprints(sources)
    previous = previous_cache.get("sources") if isinstance(previous_cache.get("sources"), Mapping) else {}
    changed: list[str] = []
    unchanged: list[str] = []
    new: list[str] = []
    for source_id, fingerprint in current.items():
        old = previous.get(source_id) if isinstance(previous, Mapping) else None
        if not old:
            new.append(source_id)
        elif dict(old) == fingerprint:
            unchanged.append(source_id)
        else:
            changed.append(source_id)
    removed = sorted(set(previous) - set(current)) if isinstance(previous, Mapping) else []
    return {
        "schema_version": "deep_context_federation_cache_compare_v1",
        "previous_cache_available": bool(previous),
        "current_source_count": len(current),
        "unchanged_source_count": len(unchanged),
        "changed_source_count": len(changed),
        "new_source_count": len(new),
        "removed_source_count": len(removed),
        "unchanged_sources": sorted(unchanged),
        "changed_sources": sorted(changed),
        "new_sources": sorted(new),
        "removed_sources": sorted(removed),
        "sources": current,
    }


def write_cache(path: Path, cache_state: Mapping[str, Any]) -> None:
    payload = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "sources": dict(cache_state.get("sources") or {}),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
