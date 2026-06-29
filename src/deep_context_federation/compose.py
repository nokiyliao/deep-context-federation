"""Compose multiple federation manifests into one read-only manifest."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from deep_context_federation.builder import read_json
from deep_context_federation.builder import safe_id
from deep_context_federation.builder import utc_now
from deep_context_federation.builder import write_json
from deep_context_federation.manifest import MANIFEST_SCHEMA
from deep_context_federation.manifest import validate_manifest

COMPOSE_SCHEMA_VERSION = "deep_context_federation_manifest_compose_v1"


def _source_rows(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(item) for item in manifest.get("sources") or [] if isinstance(item, Mapping)]


def _resolve_source_path(raw_path: str, manifest_dir: Path) -> Path:
    raw = Path(raw_path).expanduser()
    if raw.is_absolute():
        return raw.resolve()
    return (manifest_dir / raw).resolve()


def _rebase_source_path(raw_path: str, *, manifest_dir: Path, output_dir: Path | None) -> str:
    if not raw_path:
        return raw_path
    resolved = _resolve_source_path(raw_path, manifest_dir)
    if output_dir and resolved.exists():
        return os.path.relpath(resolved, output_dir.resolve())
    return Path(raw_path).as_posix()


def _normalized_source_key(row: Mapping[str, Any], *, manifest_dir: Path) -> str:
    raw_path = str(row.get("path") or "")
    resolved = _resolve_source_path(raw_path, manifest_dir).as_posix() if raw_path else ""
    comparable = {
        "role": str(row.get("role") or ""),
        "required": bool(row.get("required")),
        "path": resolved,
        "verifier": str(row.get("verifier") or ""),
        "authority_effect": str(row.get("authority_effect") or "none"),
        "no_apply": row.get("no_apply", True),
    }
    return json.dumps(comparable, ensure_ascii=True, sort_keys=True)


def _renamed_source_id(source_id: str, manifest_path: Path, used_ids: set[str]) -> str:
    stem = safe_id(manifest_path.stem, 28)
    base = safe_id(f"{source_id}__from_{stem}", 96)
    candidate = base
    index = 2
    while candidate in used_ids:
        candidate = safe_id(f"{base}_{index}", 96)
        index += 1
    return candidate


def compose_manifests(
    manifest_paths: Sequence[Path],
    *,
    output_path: Path | None = None,
    write: bool = False,
) -> dict[str, Any]:
    """Compose many manifests into one buildable manifest.

    Duplicate source ids with identical normalized source specs are collapsed.
    Duplicate source ids with different specs are retained under deterministic
    renamed ids and reported as warning conflicts.
    """

    paths = [path.expanduser().resolve() for path in manifest_paths]
    output_dir = output_path.expanduser().resolve().parent if output_path else None
    manifest_results: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    key_by_source_id: dict[str, str] = {}
    composed_sources: list[dict[str, Any]] = []
    duplicate_collapsed_count = 0

    for manifest_path in paths:
        manifest = read_json(manifest_path)
        validation = validate_manifest(manifest, manifest_path=manifest_path)
        manifest_results.append(
            {
                "path": manifest_path.as_posix(),
                "ok": validation["ok"],
                "status": validation["status"],
                "source_count": validation["source_count"],
                "error_count": validation["error_count"],
            }
        )
        if not validation["ok"]:
            conflicts.append(
                {
                    "conflict_id": f"manifest_invalid:{safe_id(manifest_path.as_posix(), 96)}",
                    "conflict_type": "manifest_invalid",
                    "severity": "error",
                    "manifest_path": manifest_path.as_posix(),
                    "detail": {"errors": validation.get("errors") or []},
                }
            )
            continue
        manifest_dir = manifest_path.parent
        for row in _source_rows(manifest):
            source_id = str(row.get("source_id") or "")
            if not source_id:
                continue
            normalized_key = _normalized_source_key(row, manifest_dir=manifest_dir)
            target_id = source_id
            if source_id in used_ids:
                if key_by_source_id.get(source_id) == normalized_key:
                    duplicate_collapsed_count += 1
                    continue
                target_id = _renamed_source_id(source_id, manifest_path, used_ids)
                conflicts.append(
                    {
                        "conflict_id": f"source_id_renamed:{source_id}:{target_id}",
                        "conflict_type": "source_id_renamed",
                        "severity": "warning",
                        "source_id": source_id,
                        "renamed_source_id": target_id,
                        "manifest_path": manifest_path.as_posix(),
                        "detail": {"reason": "duplicate source_id with different source spec"},
                    }
                )
            output_row = dict(row)
            output_row["source_id"] = target_id
            output_row["path"] = _rebase_source_path(str(row.get("path") or ""), manifest_dir=manifest_dir, output_dir=output_dir)
            output_row["composed_from_manifest"] = manifest_path.as_posix()
            if target_id != source_id:
                output_row["original_source_id"] = source_id
            composed_sources.append(output_row)
            used_ids.add(target_id)
            key_by_source_id[target_id] = normalized_key
            key_by_source_id.setdefault(source_id, normalized_key)

    composed_manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "authority_boundary": {"authority_effect": "none", "no_apply": True},
        "metadata": {
            "generated_by": "dcf merge-context-inputs",
            "generated_at": utc_now(),
            "source_manifest_count": len(paths),
        },
        "sources": sorted(composed_sources, key=lambda item: str(item.get("source_id") or "")),
    }
    validation = validate_manifest(composed_manifest, manifest_path=output_path)
    if not validation["ok"]:
        conflicts.append(
            {
                "conflict_id": "composed_manifest_invalid",
                "conflict_type": "composed_manifest_invalid",
                "severity": "error",
                "detail": {"errors": validation.get("errors") or []},
            }
        )
    errors = [item for item in conflicts if item.get("severity") == "error"]
    warnings = [item for item in conflicts if item.get("severity") == "warning"]
    result = {
        "schema_version": COMPOSE_SCHEMA_VERSION,
        "ok": not errors,
        "status": "pass_manifest_compose" if not errors else "fail_manifest_compose",
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": composed_manifest["metadata"]["generated_at"],
        "output_path": output_path.expanduser().resolve().as_posix() if output_path else "",
        "write": bool(write),
        "manifest_inputs": manifest_results,
        "conflicts": conflicts,
        "composed_manifest": composed_manifest,
        "summary": {
            "input_manifest_count": len(paths),
            "source_count": len(composed_sources),
            "duplicate_collapsed_count": duplicate_collapsed_count,
            "warning_count": len(warnings),
            "error_count": len(errors),
        },
    }
    if write and output_path:
        write_json(output_path.expanduser().resolve(), composed_manifest)
    return result


def markdown_compose(result: Mapping[str, Any]) -> str:
    summary = result.get("summary") if isinstance(result.get("summary"), Mapping) else {}
    lines = [
        "# Deep Context Federation Manifest Compose",
        "",
        f"- Status: `{result.get('status')}`",
        f"- Authority effect: `{result.get('authority_effect')}`",
        f"- No apply: `{result.get('no_apply')}`",
        f"- Inputs: `{summary.get('input_manifest_count')}`",
        f"- Sources: `{summary.get('source_count')}` collapsed=`{summary.get('duplicate_collapsed_count')}`",
        f"- Conflicts: warnings=`{summary.get('warning_count')}` errors=`{summary.get('error_count')}`",
        f"- Output: `{result.get('output_path') or ''}`",
        "",
        "## Inputs",
        "",
    ]
    for row in result.get("manifest_inputs") or []:
        if isinstance(row, Mapping):
            lines.append(f"- `{row.get('path')}` status=`{row.get('status')}` sources=`{row.get('source_count')}`")
    conflicts = [item for item in result.get("conflicts") or [] if isinstance(item, Mapping)]
    if conflicts:
        lines.extend(["", "## Conflicts", ""])
        for item in conflicts:
            lines.append(f"- `{item.get('severity')}` `{item.get('conflict_type')}`: `{item.get('conflict_id')}`")
    return "\n".join(lines).rstrip() + "\n"
