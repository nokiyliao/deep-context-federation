"""Verifier for Deep Context Federation artifacts."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from deep_context_federation.builder import EDGE_TYPES, FUSION_ROLES, QUERY_PRESETS, SCHEMA_VERSION

VERIFY_SCHEMA_VERSION = "deep_context_federation_verify_v1"
ALLOWED_VERDICTS = {"pass", "warn", "blocked", "not_applicable"}


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"{path} JSON root must be an object")
    return dict(payload)


def tracked_codebase_memory_graph(root: Path) -> list[str]:
    try:
        output = subprocess.check_output(["git", "ls-files", ".codebase-memory/graph.db.zst"], cwd=root, stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return []
    return [line for line in output.splitlines() if line.strip()]


def check(checks: list[dict[str, Any]], check_id: str, passed: bool, detail: Any = None, severity: str = "error") -> None:
    checks.append({"id": check_id, "passed": bool(passed), "severity": severity, "detail": detail})


def verify_federation(payload: Mapping[str, Any], *, manifest: Mapping[str, Any] | None = None, root: Path | None = None) -> dict[str, Any]:
    root = (root or Path.cwd()).expanduser().resolve()
    manifest = manifest or {}
    required_sources = [str(item.get("source_id")) for item in manifest.get("sources") or [] if isinstance(item, Mapping) and item.get("required")]
    checks: list[dict[str, Any]] = []
    check(checks, "schema_version", payload.get("schema_version") == SCHEMA_VERSION, payload.get("schema_version"))
    check(checks, "authority_effect_none", payload.get("authority_effect") == "none", payload.get("authority_effect"))
    check(checks, "no_apply_true", payload.get("no_apply") is True, payload.get("no_apply"))
    mutation_guard = payload.get("mutation_guard") if isinstance(payload.get("mutation_guard"), Mapping) else {}
    check(checks, "mutation_guard_present", bool(mutation_guard), mutation_guard)
    for key, value in mutation_guard.items():
        check(checks, f"mutation_guard_{key}_false", value is False, {key: value})
    sources = [dict(item) for item in payload.get("sources") or [] if isinstance(item, Mapping)]
    by_id = {str(item.get("source_id") or ""): item for item in sources}
    for source_id in required_sources:
        source = by_id.get(source_id, {})
        check(checks, f"required_source_{source_id}_present", bool(source), source)
        check(checks, f"required_source_{source_id}_loaded_or_stale", str(source.get("status") or "") in {"loaded", "stale"}, source)
        check(checks, f"required_source_{source_id}_authority_none", str(source.get("authority_effect") or "none") == "none", source)
        check(checks, f"required_source_{source_id}_no_apply_not_false", source.get("no_apply") is not False, source)
    codebase = by_id.get("codebase_memory_mcp", {})
    check(checks, "codebase_memory_status_safe", str(codebase.get("status") or "") in {"optional_disabled", "optional_unavailable", "loaded", "error"}, codebase)
    check(checks, "codebase_memory_graph_not_tracked", not tracked_codebase_memory_graph(root), tracked_codebase_memory_graph(root))
    query_presets = payload.get("query_presets") if isinstance(payload.get("query_presets"), Mapping) else {}
    for preset in QUERY_PRESETS:
        check(checks, f"query_preset_{preset}_present", preset in query_presets, sorted(query_presets))
    fusion = [dict(item) for item in payload.get("codex_fusion_synthesis") or [] if isinstance(item, Mapping)]
    by_role = {str(item.get("role") or ""): item for item in fusion}
    for role in FUSION_ROLES:
        row = by_role.get(role, {})
        check(checks, f"fusion_role_{role}_present", bool(row), row)
        check(checks, f"fusion_role_{role}_allowed_verdict", str(row.get("verdict") or "") in ALLOWED_VERDICTS, row)
        check(checks, f"fusion_role_{role}_has_input_sources", bool(list(row.get("input_sources") or [])), row)
    entities = [dict(item) for item in payload.get("entities") or [] if isinstance(item, Mapping)]
    check(checks, "entities_present", bool(entities), {"count": len(entities)})
    edges = [dict(item) for item in payload.get("edges") or [] if isinstance(item, Mapping)]
    bad_edges = [edge for edge in edges if str(edge.get("edge_type") or "") not in EDGE_TYPES]
    check(checks, "edge_types_allowed", not bad_edges, bad_edges[:10])
    conflicts = [dict(item) for item in payload.get("conflicts") or [] if isinstance(item, Mapping)]
    error_conflicts = [item for item in conflicts if str(item.get("severity") or "") == "error"]
    check(checks, "no_error_conflicts", not error_conflicts, error_conflicts[:20])
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    check(checks, "summary_error_count_matches", int(summary.get("error_count") or 0) == len(error_conflicts), {"summary": summary.get("error_count"), "actual": len(error_conflicts)})
    failed = [item for item in checks if not item["passed"] and item["severity"] == "error"]
    return {
        "schema_version": VERIFY_SCHEMA_VERSION,
        "ok": not failed,
        "status": "pass_deep_context_federation" if not failed else "fail_deep_context_federation",
        "error_count": len(failed),
        "checks": checks,
        "errors": failed,
    }
