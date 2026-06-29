"""Manifest validation for Deep Context Federation."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

MANIFEST_SCHEMA = "deep_context_federation_manifest_v1"


def validate_manifest(manifest: Mapping[str, Any], *, manifest_path: Path | None = None) -> dict[str, Any]:
    """Validate the public manifest shape without touching source files."""

    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, detail: Any = None) -> None:
        checks.append({"id": check_id, "passed": bool(passed), "detail": detail})

    add("schema_version", manifest.get("schema_version") == MANIFEST_SCHEMA, manifest.get("schema_version"))
    sources = manifest.get("sources")
    add("sources_present", isinstance(sources, list) and bool(sources), {"type": type(sources).__name__})
    rows = [dict(item) for item in sources or [] if isinstance(item, Mapping)]
    add("sources_all_objects", len(rows) == len(sources or []), {"count": len(rows), "raw_count": len(sources or [])})

    seen: set[str] = set()
    duplicates: list[str] = []
    required_count = 0
    for index, row in enumerate(rows):
        source_id = str(row.get("source_id") or "")
        if source_id in seen:
            duplicates.append(source_id)
        seen.add(source_id)
        if row.get("required"):
            required_count += 1
        add(f"sources[{index}].source_id", bool(source_id), row)
        add(f"sources[{index}].role", bool(str(row.get("role") or "")), row)
        add(f"sources[{index}].path", bool(str(row.get("path") or "")), row)
    add("source_ids_unique", not duplicates, duplicates)
    add("required_source_present", required_count > 0, {"required_count": required_count})

    boundary = manifest.get("authority_boundary") if isinstance(manifest.get("authority_boundary"), Mapping) else {}
    if boundary:
        add("authority_boundary_effect_none", boundary.get("authority_effect") in {None, "none"}, boundary)
        add("authority_boundary_no_apply_not_false", boundary.get("no_apply") is not False, boundary)

    failed = [item for item in checks if not item["passed"]]
    return {
        "schema_version": "deep_context_federation_manifest_verify_v1",
        "ok": not failed,
        "status": "pass_manifest" if not failed else "fail_manifest",
        "manifest_path": manifest_path.as_posix() if manifest_path else "",
        "source_count": len(rows),
        "required_source_count": required_count,
        "error_count": len(failed),
        "checks": checks,
        "errors": failed,
    }
