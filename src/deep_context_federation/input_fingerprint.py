"""Input freshness fingerprints for DCF agent handoffs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from deep_context_federation.builder import read_json
from deep_context_federation.builder import resolve_path
from deep_context_federation.builder import sha256_file
from deep_context_federation.builder import utc_now

INPUT_FINGERPRINT_SCHEMA_VERSION = "deep_context_federation_input_fingerprint_v1"
INPUT_FINGERPRINT_COMPARE_SCHEMA_VERSION = "deep_context_federation_input_fingerprint_compare_v1"


def _file_fingerprint(path: Path) -> dict[str, Any]:
    exists = path.exists() and path.is_file()
    return {
        "path": path.as_posix(),
        "exists": exists,
        "byte_size": path.stat().st_size if exists else 0,
        "sha256": sha256_file(path) if exists else "",
    }


def _digest(payload: Mapping[str, Any]) -> str:
    text = json.dumps(dict(payload), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_input_fingerprint(*, root: Path, manifests: Sequence[Path]) -> dict[str, Any]:
    """Fingerprint manifests and their explicitly listed JSON sources."""

    root = root.expanduser().resolve()
    manifest_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for manifest_path in manifests:
        resolved_manifest = manifest_path.expanduser()
        if not resolved_manifest.is_absolute():
            resolved_manifest = root / resolved_manifest
        resolved_manifest = resolved_manifest.resolve()
        manifest_fingerprint = _file_fingerprint(resolved_manifest)
        payload = read_json(resolved_manifest) if manifest_fingerprint["exists"] else {}
        manifest_rows.append(
            {
                **manifest_fingerprint,
                "schema_version": payload.get("schema_version") if isinstance(payload, Mapping) else "",
                "source_count": len(payload.get("sources") or []) if isinstance(payload.get("sources"), list) else 0,
            }
        )
        if not manifest_fingerprint["exists"]:
            errors.append({"id": "manifest_missing", "path": resolved_manifest.as_posix()})
            continue
        if not payload:
            errors.append({"id": "manifest_unreadable", "path": resolved_manifest.as_posix()})
            continue
        for index, source in enumerate(payload.get("sources") or []):
            if not isinstance(source, Mapping):
                errors.append({"id": "source_spec_invalid", "manifest_path": resolved_manifest.as_posix(), "index": index})
                continue
            source_path = str(source.get("path") or "")
            source_id = str(source.get("source_id") or f"source_{index}")
            source_resolved = resolve_path(source_path, root, resolved_manifest.parent) if source_path else root / "__missing__"
            source_fingerprint = _file_fingerprint(source_resolved)
            source_rows.append(
                {
                    **source_fingerprint,
                    "source_id": source_id,
                    "role": str(source.get("role") or ""),
                    "required": bool(source.get("required")),
                    "declared_path": source_path,
                    "manifest_path": resolved_manifest.as_posix(),
                }
            )
            if source.get("required") and not source_fingerprint["exists"]:
                errors.append({"id": "required_source_missing", "source_id": source_id, "path": source_resolved.as_posix()})

    digest_payload = {"manifests": manifest_rows, "sources": source_rows}
    return {
        "schema_version": INPUT_FINGERPRINT_SCHEMA_VERSION,
        "ok": not errors,
        "status": "pass_input_fingerprint" if not errors else "fail_input_fingerprint",
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": utc_now(),
        "root": root.as_posix(),
        "digest": _digest(digest_payload),
        "manifest_count": len(manifest_rows),
        "source_count": len(source_rows),
        "manifests": manifest_rows,
        "sources": source_rows,
        "errors": errors,
        "safety_boundaries": {
            "authority_effect": "none",
            "no_apply": True,
            "mutation_allowed": False,
            "reads_manifest_declared_sources_only": True,
            "source_tree_scan": False,
        },
    }


def compare_input_fingerprint(previous: Mapping[str, Any], current: Mapping[str, Any]) -> dict[str, Any]:
    """Compare previous and current input fingerprints."""

    previous_digest = str(previous.get("digest") or "")
    current_digest = str(current.get("digest") or "")
    comparable = bool(previous_digest and current_digest)
    matches = comparable and previous_digest == current_digest
    return {
        "schema_version": INPUT_FINGERPRINT_COMPARE_SCHEMA_VERSION,
        "ok": matches,
        "status": "pass_input_fingerprint_compare" if matches else "fail_input_fingerprint_compare",
        "authority_effect": "none",
        "no_apply": True,
        "comparable": comparable,
        "matches": matches,
        "previous_digest": previous_digest,
        "current_digest": current_digest,
        "previous_status": previous.get("status"),
        "current_status": current.get("status"),
        "current_error_count": len(current.get("errors") or []),
    }
