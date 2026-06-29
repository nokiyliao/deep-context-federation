"""Build a read-only deep context federation artifact from JSON sources."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "deep_context_federation_v1"
MANIFEST_SCHEMA = "deep_context_federation_manifest_v1"
DEFAULT_JSON_NAME = "deep_context_federation_latest.json"
DEFAULT_MD_NAME = "DEEP_CONTEXT_FEDERATION_LATEST.md"
DEFAULT_SQLITE_NAME = "deep_context_federation_latest.sqlite"

QUERY_PRESETS = [
    "surface-splits",
    "claim-lineage",
    "stale-sources",
    "code-to-authority",
    "r19-context",
    "operator-projection",
]

FUSION_ROLES = [
    "authority_boundary_reviewer",
    "source_graph_reviewer",
    "evidence_lineage_reviewer",
    "operator_projection_reviewer",
    "external_tool_adoption_reviewer",
]

EDGE_TYPES = {
    "DECLARES",
    "SUPPORTS",
    "ADVISES",
    "OWNS",
    "DERIVES_FROM",
    "REFERENCES_SYMBOL",
    "CONFLICTS_WITH",
    "STALE_FOR",
}

ENTITY_KEYS = {
    "path": "path",
    "source_path": "path",
    "file": "path",
    "artifact_path": "artifact_id",
    "artifact_id": "artifact_id",
    "claim_id": "claim_id",
    "surface_id": "surface_id",
    "id": "surface_id",
    "contract_id": "contract_id",
    "task_id": "task_id",
    "thread_id": "thread_id",
    "commit_sha": "commit_sha",
    "head_commit": "commit_sha",
    "git_commit": "commit_sha",
    "symbol_fqn": "symbol_fqn",
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, lines: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def relpath(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def digest_text(text: str, length: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def safe_id(value: str, max_len: int = 72) -> str:
    safe = "".join(char if char.isalnum() or char in {"_", "-", "."} else "_" for char in value).strip("_")
    return (safe or "item")[:max_len]


def run_git(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return ""


def git_info(root: Path) -> dict[str, Any]:
    status = run_git(root, "status", "--short")
    return {
        "branch": run_git(root, "rev-parse", "--abbrev-ref", "HEAD"),
        "head_commit": run_git(root, "rev-parse", "HEAD"),
        "head_short_commit": run_git(root, "rev-parse", "--short", "HEAD"),
        "dirty": bool(status.strip()),
        "dirty_count": len([line for line in status.splitlines() if line.strip()]),
    }


def resolve_path(path: str | Path, root: Path, manifest_dir: Path | None = None) -> Path:
    raw = Path(path).expanduser()
    if raw.is_absolute():
        return raw.resolve()
    base = manifest_dir if manifest_dir else root
    candidate = (base / raw).resolve()
    if candidate.exists():
        return candidate
    return (root / raw).resolve()


def source_status(payload: Mapping[str, Any]) -> str:
    if payload.get("status"):
        return str(payload["status"])
    if payload.get("verdict"):
        return str(payload["verdict"])
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    return str(summary.get("status") or summary.get("verdict") or "")


def source_head(payload: Mapping[str, Any]) -> str:
    for key in ("head_commit", "git_commit", "commit_sha", "commit"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    git = payload.get("git") if isinstance(payload.get("git"), Mapping) else {}
    for key in ("head_commit", "commit", "sha"):
        value = git.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def entity_id(entity_type: str, value: str) -> str:
    return f"{entity_type}:{safe_id(value)}:{digest_text(entity_type + ':' + value, 12)}"


def edge_id(edge_type: str, source_id: str, target_id: str, source_ref: str) -> str:
    return f"edge:{edge_type.lower()}:{digest_text(source_id + '|' + target_id + '|' + source_ref, 14)}"


def add_entity(
    entities: dict[str, dict[str, Any]],
    *,
    entity_type: str,
    value: str,
    source_id: str,
    label: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    item_id = entity_id(entity_type, value)
    existing = entities.get(item_id)
    if existing:
        refs = set(existing.get("source_ids") or [])
        refs.add(source_id)
        existing["source_ids"] = sorted(refs)
        return item_id
    entities[item_id] = {
        "entity_id": item_id,
        "entity_type": entity_type,
        "value": value,
        "label": label or value,
        "source_ids": [source_id],
        "metadata": dict(metadata or {}),
    }
    return item_id


def add_edge(
    edges: dict[str, dict[str, Any]],
    *,
    edge_type: str,
    from_entity: str,
    to_entity: str,
    source_id: str,
    evidence: str = "",
) -> None:
    if edge_type not in EDGE_TYPES or not from_entity or not to_entity:
        return
    item_id = edge_id(edge_type, from_entity, to_entity, source_id + evidence)
    edges[item_id] = {
        "edge_id": item_id,
        "edge_type": edge_type,
        "from_entity": from_entity,
        "to_entity": to_entity,
        "source_id": source_id,
        "evidence": evidence,
    }


def scalar(value: Any) -> str:
    if isinstance(value, (str, int, float)):
        return str(value)
    return ""


def walk_entities(
    value: Any,
    *,
    source_id: str,
    entities: dict[str, dict[str, Any]],
    edges: dict[str, dict[str, Any]],
    source_entity_id: str,
    path: str = "",
    limit: int = 2000,
) -> None:
    if len(entities) >= limit:
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            item_type = ENTITY_KEYS.get(key_text)
            item_scalar = scalar(item)
            if item_type and item_scalar:
                target = add_entity(
                    entities,
                    entity_type=item_type,
                    value=item_scalar,
                    source_id=source_id,
                    metadata={"json_path": f"{path}.{key_text}".strip(".")},
                )
                add_edge(edges, edge_type="DECLARES", from_entity=source_entity_id, to_entity=target, source_id=source_id)
            elif item_type and isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
                for child in item[:100]:
                    child_scalar = scalar(child)
                    if child_scalar:
                        target = add_entity(
                            entities,
                            entity_type=item_type,
                            value=child_scalar,
                            source_id=source_id,
                            metadata={"json_path": f"{path}.{key_text}".strip(".")},
                        )
                        add_edge(edges, edge_type="DECLARES", from_entity=source_entity_id, to_entity=target, source_id=source_id)
            walk_entities(
                item,
                source_id=source_id,
                entities=entities,
                edges=edges,
                source_entity_id=source_entity_id,
                path=f"{path}.{key_text}".strip("."),
                limit=limit,
            )
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value[:300]):
            walk_entities(
                item,
                source_id=source_id,
                entities=entities,
                edges=edges,
                source_entity_id=source_entity_id,
                path=f"{path}[{index}]",
                limit=limit,
            )


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    if not manifest:
        raise ValueError(f"manifest is missing or invalid: {manifest_path}")
    return manifest


def load_source(root: Path, manifest_dir: Path, spec: Mapping[str, Any], head_commit: str) -> dict[str, Any]:
    source_id = str(spec.get("source_id") or "")
    source_path = str(spec.get("path") or "")
    resolved = resolve_path(source_path, root, manifest_dir) if source_path else root / "__missing__"
    exists = bool(source_path and resolved.exists())
    payload = read_json(resolved) if exists else {}
    found_head = source_head(payload)
    status = "loaded" if exists else "missing"
    stale_for = ""
    if exists and found_head and head_commit and found_head != head_commit:
        status = "stale"
        stale_for = head_commit
    row: dict[str, Any] = {
        "source_id": source_id,
        "role": str(spec.get("role") or ""),
        "required": bool(spec.get("required")),
        "status": status,
        "path": source_path,
        "resolved_path": resolved.as_posix() if source_path else "",
        "exists": exists,
        "authority_effect": str(payload.get("authority_effect") or spec.get("authority_effect") or "none"),
        "no_apply": payload.get("no_apply") if "no_apply" in payload else bool(spec.get("no_apply", True)),
        "schema_version": str(payload.get("schema_version") or payload.get("schema") or ""),
        "source_status": source_status(payload),
        "generated_at": str(payload.get("generated_at") or payload.get("generated_at_utc") or ""),
        "head_commit": found_head,
        "stale_for": stale_for,
        "verifier": str(spec.get("verifier") or ""),
        "payload_keys": sorted(str(key) for key in payload.keys())[:80],
        "summary": payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {},
    }
    if exists:
        row["byte_size"] = resolved.stat().st_size
        row["sha256"] = sha256_file(resolved)
    return row


def tracked_codebase_memory_graph(root: Path) -> list[str]:
    tracked = run_git(root, "ls-files", ".codebase-memory/graph.db.zst")
    return [line for line in tracked.splitlines() if line.strip()]


def is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def codebase_memory_source(
    root: Path,
    *,
    include: bool,
    cache_dir: Path | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    conflicts: list[dict[str, Any]] = []
    source = {
        "source_id": "codebase_memory_mcp",
        "role": "optional_advisory_code_memory",
        "required": False,
        "status": "optional_disabled",
        "path": "",
        "exists": False,
        "authority_effect": "none",
        "no_apply": True,
        "verifier": "safe_adapter_policy_only",
        "payload_keys": [],
        "summary": {
            "enabled": False,
            "installer_ran": False,
            "auto_index_enabled": False,
            "watcher_enabled": False,
            "manage_adr_used": False,
        },
    }
    tracked = tracked_codebase_memory_graph(root)
    if tracked:
        conflicts.append(
            {
                "conflict_id": "codebase_memory_tracked_graph",
                "conflict_type": "codebase_memory_policy_violation",
                "severity": "error",
                "source_id": "codebase_memory_mcp",
                "detail": {"tracked_paths": tracked},
            }
        )
    if not include:
        return source, conflicts
    executable = shutil.which("codebase-memory-mcp")
    source["summary"]["enabled"] = True
    if not executable:
        source.update({"status": "optional_unavailable", "summary": {**source["summary"], "reason": "binary not found"}})
        return source, conflicts
    resolved_cache = cache_dir or Path(os.environ.get("CBM_CACHE_DIR") or "")
    if not str(resolved_cache):
        source.update({"status": "error", "exists": True})
        conflicts.append(
            {
                "conflict_id": "codebase_memory_cache_missing",
                "conflict_type": "codebase_memory_policy_violation",
                "severity": "error",
                "source_id": "codebase_memory_mcp",
                "detail": {"required_env": "CBM_CACHE_DIR"},
            }
        )
        return source, conflicts
    resolved_cache = resolved_cache.expanduser().resolve()
    if is_inside(resolved_cache, root):
        source.update({"status": "error", "exists": True, "path": resolved_cache.as_posix()})
        conflicts.append(
            {
                "conflict_id": "codebase_memory_repo_local_cache",
                "conflict_type": "codebase_memory_policy_violation",
                "severity": "error",
                "source_id": "codebase_memory_mcp",
                "detail": {"cache_dir": resolved_cache.as_posix()},
            }
        )
        return source, conflicts
    source.update(
        {
            "status": "loaded",
            "exists": True,
            "path": resolved_cache.as_posix(),
            "summary": {
                **source["summary"],
                "binary": executable,
                "cache_dir": resolved_cache.as_posix(),
                "safe_mode": True,
                "indexing_invoked": False,
            },
        }
    )
    return source, conflicts


def source_payload(source: Mapping[str, Any]) -> dict[str, Any]:
    resolved = str(source.get("resolved_path") or "")
    if not resolved:
        return {}
    return read_json(Path(resolved))


def claim_lineage(
    payload: Mapping[str, Any],
    *,
    source_id: str,
    entities: dict[str, dict[str, Any]],
    edges: dict[str, dict[str, Any]],
    source_entity_id: str,
) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    claims = payload.get("claims")
    if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes, bytearray)):
        return conflicts
    for claim in claims:
        if not isinstance(claim, Mapping):
            continue
        claim_id = str(claim.get("claim_id") or "")
        if not claim_id:
            continue
        claim_entity = add_entity(
            entities,
            entity_type="claim_id",
            value=claim_id,
            source_id=source_id,
            label=str(claim.get("label") or claim_id),
            metadata={"status": claim.get("status"), "authority_level": claim.get("authority_level")},
        )
        add_edge(edges, edge_type="DECLARES", from_entity=source_entity_id, to_entity=claim_entity, source_id=source_id)
        authority_sources = [str(item) for item in claim.get("authority_sources") or [] if str(item)]
        supporting = [str(item) for item in claim.get("supporting_artifacts") or [] if str(item)]
        advisory = [str(item) for item in claim.get("advisory_sources") or [] if str(item)]
        verifiers = [str(item) for item in claim.get("verifiers") or [] if str(item)]
        if not authority_sources and not supporting and not advisory and not verifiers:
            conflicts.append(
                {
                    "conflict_id": f"claim_without_evidence:{claim_id}",
                    "conflict_type": "claim_without_evidence",
                    "severity": "warning",
                    "source_id": source_id,
                    "entity_id": claim_entity,
                    "detail": {"claim_id": claim_id},
                }
            )
        for item in authority_sources + supporting + verifiers:
            target = add_entity(entities, entity_type="artifact_id", value=item, source_id=source_id)
            add_edge(edges, edge_type="SUPPORTS", from_entity=claim_entity, to_entity=target, source_id=source_id)
        for item in advisory:
            target = add_entity(entities, entity_type="artifact_id", value=item, source_id=source_id)
            add_edge(edges, edge_type="ADVISES", from_entity=claim_entity, to_entity=target, source_id=source_id)
    return conflicts


def surface_owner_conflicts(payload: Mapping[str, Any], *, source_id: str, entities: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    surfaces = payload.get("surfaces")
    if not surfaces and isinstance(payload.get("surface_map"), Mapping):
        surfaces = payload["surface_map"].get("surfaces")
    if isinstance(surfaces, Sequence) and not isinstance(surfaces, (str, bytes, bytearray)):
        rows = [item for item in surfaces if isinstance(item, Mapping)]
    conflicts: list[dict[str, Any]] = []
    for row in rows:
        surface_id = str(row.get("surface_id") or row.get("id") or row.get("name") or "")
        if not surface_id:
            continue
        entity = add_entity(entities, entity_type="surface_id", value=surface_id, source_id=source_id)
        owner = row.get("owner") or row.get("owner_agent") or row.get("owner_board") or row.get("owner_lane")
        if not owner:
            conflicts.append(
                {
                    "conflict_id": f"surface_owner_missing:{surface_id}",
                    "conflict_type": "surface_owner_missing",
                    "severity": "warning",
                    "source_id": source_id,
                    "entity_id": entity,
                    "detail": {"surface_id": surface_id},
                }
            )
    return conflicts


def build_entities_and_edges(sources: Mapping[str, Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    entities: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    conflicts: list[dict[str, Any]] = []
    for source_id, source in sources.items():
        source_entity = add_entity(
            entities,
            entity_type="artifact_id",
            value=source_id,
            source_id=source_id,
            label=source_id,
            metadata={"role": source.get("role"), "status": source.get("status")},
        )
        if source.get("path"):
            target = add_entity(entities, entity_type="path", value=str(source["path"]), source_id=source_id)
            add_edge(edges, edge_type="DERIVES_FROM", from_entity=source_entity, to_entity=target, source_id=source_id)
        payload = source_payload(source)
        if payload:
            walk_entities(payload, source_id=source_id, entities=entities, edges=edges, source_entity_id=source_entity)
            conflicts.extend(claim_lineage(payload, source_id=source_id, entities=entities, edges=edges, source_entity_id=source_entity))
            conflicts.extend(surface_owner_conflicts(payload, source_id=source_id, entities=entities))
    return list(entities.values()), list(edges.values()), conflicts


def source_conflicts(sources: Mapping[str, Mapping[str, Any]], codebase_conflicts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    conflicts = [dict(item) for item in codebase_conflicts]
    for source_id, source in sources.items():
        status = str(source.get("status") or "")
        if source.get("required") and status not in {"loaded", "stale"}:
            conflicts.append(
                {
                    "conflict_id": f"source_missing:{source_id}",
                    "conflict_type": "source_missing",
                    "severity": "error",
                    "source_id": source_id,
                    "detail": {"status": status, "path": source.get("path")},
                }
            )
        if status == "stale":
            conflicts.append(
                {
                    "conflict_id": f"source_stale:{source_id}",
                    "conflict_type": "source_stale",
                    "severity": "warning",
                    "source_id": source_id,
                    "detail": {"source_head": source.get("head_commit"), "current_head": source.get("stale_for")},
                }
            )
        if str(source.get("authority_effect") or "none") != "none" or source.get("no_apply") is False:
            conflicts.append(
                {
                    "conflict_id": f"authority_advisory_mixed:{source_id}",
                    "conflict_type": "authority_advisory_mixed",
                    "severity": "error",
                    "source_id": source_id,
                    "detail": {"authority_effect": source.get("authority_effect"), "no_apply": source.get("no_apply")},
                }
            )
    return conflicts


def fusion_synthesis(sources: Mapping[str, Mapping[str, Any]], conflicts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    error_types = {str(item.get("conflict_type") or "") for item in conflicts if str(item.get("severity") or "") == "error"}
    warning_types = {str(item.get("conflict_type") or "") for item in conflicts if str(item.get("severity") or "") == "warning"}
    missing_required = [source_id for source_id, row in sources.items() if row.get("required") and row.get("status") not in {"loaded", "stale"}]
    return [
        {
            "role": "authority_boundary_reviewer",
            "verdict": "blocked" if "authority_advisory_mixed" in error_types else "pass",
            "input_sources": sorted(sources),
            "findings": ["Federation is read-only and advisory; explicit authority drift is a hard error."],
        },
        {
            "role": "source_graph_reviewer",
            "verdict": "warn" if sources.get("codebase_memory_mcp", {}).get("status") in {"optional_disabled", "optional_unavailable"} else "pass",
            "input_sources": ["codebase_memory_mcp"],
            "findings": ["External source graphs remain advisory adapters."],
        },
        {
            "role": "evidence_lineage_reviewer",
            "verdict": "blocked" if missing_required else ("warn" if "claim_without_evidence" in warning_types else "pass"),
            "input_sources": [source_id for source_id, row in sources.items() if "evidence" in str(row.get("role") or "") or "claim" in str(row.get("role") or "")],
            "findings": ["Claims are linked to authority, evidence, advisory, and verifier artifacts when present."],
        },
        {
            "role": "operator_projection_reviewer",
            "verdict": "warn" if "source_stale" in warning_types else "pass",
            "input_sources": [source_id for source_id, row in sources.items() if "operator" in str(row.get("role") or "") or "surface" in str(row.get("role") or "")],
            "findings": ["Operator projections do not replace lower-level evidence."],
        },
        {
            "role": "external_tool_adoption_reviewer",
            "verdict": "blocked" if "codebase_memory_policy_violation" in error_types else "pass",
            "input_sources": ["codebase_memory_mcp"],
            "findings": ["codebase-memory-mcp is disabled by default and never installed or auto-indexed by this tool."],
        },
    ]


def query_preset_summary(sources: Mapping[str, Mapping[str, Any]], entities: Sequence[Mapping[str, Any]], conflicts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    values = [str(item.get("value") or "") for item in entities]
    return {
        "surface-splits": {
            "description": "Surface ownership, advisory splits, and surface-related conflicts.",
            "result_count_hint": sum(1 for item in conflicts if "surface" in str(item.get("conflict_type") or "")),
        },
        "claim-lineage": {
            "description": "Claim to authority/evidence/verifier lineage.",
            "result_count_hint": sum(1 for item in entities if item.get("entity_type") == "claim_id"),
        },
        "stale-sources": {
            "description": "Missing, stale, or errored sources.",
            "result_count_hint": sum(1 for row in sources.values() if row.get("status") in {"stale", "missing", "error", "optional_unavailable"}),
        },
        "code-to-authority": {
            "description": "Path or symbol entities joined into the federation.",
            "result_count_hint": sum(1 for item in entities if item.get("entity_type") in {"path", "symbol_fqn"}),
        },
        "r19-context": {
            "description": "Rows matching r19/R19 text for projects that use R19 research lanes.",
            "result_count_hint": sum(1 for value in values if "r19" in value.lower()),
        },
        "operator-projection": {
            "description": "Operator/dashboard/governance projection context.",
            "result_count_hint": sum(1 for value in values if "operator" in value.lower() or "dashboard" in value.lower() or "governance" in value.lower()),
        },
    }


def markdown(payload: Mapping[str, Any]) -> list[str]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    lines = [
        "# Deep Context Federation Latest",
        "",
        f"- Generated: `{payload.get('generated_at')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Authority effect: `{payload.get('authority_effect')}`",
        f"- No apply: `{payload.get('no_apply')}`",
        f"- Sources: `{summary.get('source_count')}` loaded=`{summary.get('loaded_source_count')}` stale=`{summary.get('stale_source_count')}` missing=`{summary.get('missing_source_count')}`",
        f"- Entities: `{summary.get('entity_count')}`",
        f"- Edges: `{summary.get('edge_count')}`",
        f"- Conflicts: `{summary.get('conflict_count')}` errors=`{summary.get('error_count')}` warnings=`{summary.get('warning_count')}`",
        "",
        "## Sources",
        "",
        "| source_id | role | status | required | path |",
        "|---|---|---:|---:|---|",
    ]
    for source in payload.get("sources") or []:
        if isinstance(source, Mapping):
            lines.append(f"| `{source.get('source_id')}` | `{source.get('role')}` | `{source.get('status')}` | `{source.get('required')}` | `{source.get('path') or ''}` |")
    lines.extend(["", "## Codex Fusion Synthesis", ""])
    for row in payload.get("codex_fusion_synthesis") or []:
        if isinstance(row, Mapping):
            lines.append(f"- `{row.get('role')}`: `{row.get('verdict')}`")
    lines.extend(["", "## Conflicts", ""])
    conflicts = [item for item in payload.get("conflicts") or [] if isinstance(item, Mapping)]
    if not conflicts:
        lines.append("- none")
    for item in conflicts[:80]:
        lines.append(f"- `{item.get('severity')}` `{item.get('conflict_type')}` source=`{item.get('source_id')}` id=`{item.get('conflict_id')}`")
    return lines


def write_sqlite(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        conn.execute("create table sources (source_id text primary key, role text, required integer, status text, path text, summary_json text)")
        conn.execute("create table entities (entity_id text primary key, entity_type text, value text, label text, source_ids_json text, metadata_json text)")
        conn.execute("create table edges (edge_id text primary key, edge_type text, from_entity text, to_entity text, source_id text)")
        conn.execute("create table conflicts (conflict_id text, conflict_type text, severity text, source_id text, detail_json text)")
        for source in payload.get("sources") or []:
            if isinstance(source, Mapping):
                conn.execute(
                    "insert into sources values (?, ?, ?, ?, ?, ?)",
                    (source.get("source_id"), source.get("role"), 1 if source.get("required") else 0, source.get("status"), source.get("path"), json.dumps(source.get("summary") or {}, sort_keys=True)),
                )
        for entity in payload.get("entities") or []:
            if isinstance(entity, Mapping):
                conn.execute(
                    "insert into entities values (?, ?, ?, ?, ?, ?)",
                    (entity.get("entity_id"), entity.get("entity_type"), entity.get("value"), entity.get("label"), json.dumps(entity.get("source_ids") or [], sort_keys=True), json.dumps(entity.get("metadata") or {}, sort_keys=True)),
                )
        for edge in payload.get("edges") or []:
            if isinstance(edge, Mapping):
                conn.execute("insert into edges values (?, ?, ?, ?, ?)", (edge.get("edge_id"), edge.get("edge_type"), edge.get("from_entity"), edge.get("to_entity"), edge.get("source_id")))
        for conflict in payload.get("conflicts") or []:
            if isinstance(conflict, Mapping):
                conn.execute("insert into conflicts values (?, ?, ?, ?, ?)", (conflict.get("conflict_id"), conflict.get("conflict_type"), conflict.get("severity"), conflict.get("source_id"), json.dumps(conflict.get("detail") or {}, sort_keys=True)))
        conn.commit()
    finally:
        conn.close()


def build_federation(
    *,
    manifest_path: Path,
    root: Path,
    output_dir: Path,
    include_codebase_memory: bool = False,
    codebase_memory_cache_dir: Path | None = None,
    write: bool = False,
) -> dict[str, Any]:
    root = root.expanduser().resolve()
    manifest_path = manifest_path.expanduser().resolve()
    manifest_dir = manifest_path.parent
    output_dir = output_dir.expanduser().resolve()
    manifest = load_manifest(manifest_path)
    git = git_info(root)
    source_specs = [dict(item) for item in manifest.get("sources") or [] if isinstance(item, Mapping)]
    sources = {
        str(spec.get("source_id")): load_source(root, manifest_dir, spec, str(git.get("head_commit") or ""))
        for spec in source_specs
        if spec.get("source_id")
    }
    codebase, codebase_conflicts = codebase_memory_source(root, include=include_codebase_memory, cache_dir=codebase_memory_cache_dir)
    sources["codebase_memory_mcp"] = codebase
    entities, edges, entity_conflicts = build_entities_and_edges(sources)
    conflicts = source_conflicts(sources, codebase_conflicts)
    conflicts.extend(entity_conflicts)
    errors = [item for item in conflicts if item.get("severity") == "error"]
    warnings = [item for item in conflicts if item.get("severity") == "warning"]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "status": "pass_deep_context_federation" if not errors else "fail_deep_context_federation",
        "ok": not errors,
        "root": root.as_posix(),
        "branch": git.get("branch"),
        "head_commit": git.get("head_commit"),
        "authority_effect": "none",
        "no_apply": True,
        "mutation_guard": {
            "live_authority_mutation_allowed": False,
            "runtime_registry_mutation_allowed": False,
            "broker_order_mutation_allowed": False,
            "promotion_mutation_allowed": False,
            "task_ledger_replacement_allowed": False,
            "external_model_calls_allowed": False,
        },
        "manifest": {"path": manifest_path.as_posix(), "schema_version": manifest.get("schema_version")},
        "sources": [sources[key] for key in sorted(sources)],
        "entities": sorted(entities, key=lambda item: (str(item.get("entity_type")), str(item.get("value")))),
        "edges": sorted(edges, key=lambda item: (str(item.get("edge_type")), str(item.get("edge_id")))),
        "conflicts": sorted(conflicts, key=lambda item: (str(item.get("severity")), str(item.get("conflict_type")), str(item.get("conflict_id")))),
        "codex_fusion_synthesis": fusion_synthesis(sources, conflicts),
        "query_presets": query_preset_summary(sources, entities, conflicts),
        "summary": {
            "source_count": len(sources),
            "required_source_count": sum(1 for source in sources.values() if source.get("required")),
            "loaded_source_count": sum(1 for source in sources.values() if source.get("status") == "loaded"),
            "stale_source_count": sum(1 for source in sources.values() if source.get("status") == "stale"),
            "missing_source_count": sum(1 for source in sources.values() if source.get("status") == "missing"),
            "entity_count": len(entities),
            "edge_count": len(edges),
            "conflict_count": len(conflicts),
            "error_count": len(errors),
            "warning_count": len(warnings),
            "query_preset_count": len(QUERY_PRESETS),
            "codex_fusion_role_count": len(FUSION_ROLES),
        },
        "outputs": {
            "json": (output_dir / DEFAULT_JSON_NAME).as_posix(),
            "markdown": (output_dir / DEFAULT_MD_NAME).as_posix(),
            "sqlite": (output_dir / DEFAULT_SQLITE_NAME).as_posix(),
        },
    }
    if write:
        write_json(output_dir / DEFAULT_JSON_NAME, payload)
        write_markdown(output_dir / DEFAULT_MD_NAME, markdown(payload))
        write_sqlite(output_dir / DEFAULT_SQLITE_NAME, payload)
    return payload
