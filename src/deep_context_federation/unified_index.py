"""DCF-native source-collapsed unified context index."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from deep_context_federation.builder import utc_now
from deep_context_federation.context_pack import estimate_tokens

UNIFIED_INDEX_SCHEMA_VERSION = "deep_context_federation_unified_index_v1"
UNIFIED_WORKING_SET_SCHEMA_VERSION = "deep_context_federation_unified_working_set_v1"

EDGE_WEIGHTS = {
    "SUPPORTS": 5,
    "OWNS": 4,
    "REFERENCES_SYMBOL": 4,
    "DERIVES_FROM": 3,
    "DECLARES": 2,
    "ADVISES": 1,
    "CONFLICTS_WITH": -4,
    "STALE_FOR": -3,
}

ENTITY_FACETS = {
    "surface_id": "surface",
    "symbol_fqn": "symbol",
    "claim_id": "claim",
    "path": "path",
    "artifact_id": "artifact",
    "contract_id": "contract",
    "task_id": "task",
    "thread_id": "thread",
    "commit_sha": "commit",
}


def _rows(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, Mapping)]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _strings(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [str(item) for item in value if str(item)]


def _stable_id(prefix: str, parts: Sequence[Any]) -> str:
    text = json.dumps([str(item) for item in parts], ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return f"{prefix}:{hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]}"


def _json_text(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    except Exception:
        return str(value)


def _pretty_json_text(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), ensure_ascii=True, indent=2, sort_keys=True) + "\n"


def _count_terms(row: Mapping[str, Any], terms: Sequence[str]) -> int:
    text = _json_text(row).lower()
    return sum(1 for term in terms if term and term.lower() in text)


def _terms(query: str) -> list[str]:
    return [term.lower() for term in str(query or "").replace("/", " ").replace("_", " ").split() if len(term) >= 2]


def _truncate(value: Any, limit: int) -> str:
    text = str(value or "")
    limit = max(8, int(limit))
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _strip_identity(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return a controlled public metadata dict without source identity keys."""

    hidden = {"source_id", "source_ids", "sources", "input_sources", "related_sources"}
    result: dict[str, Any] = {}
    for key, value in row.items():
        if key in hidden:
            continue
        if isinstance(value, Mapping):
            result[key] = _strip_identity(value)
        elif isinstance(value, list):
            result[key] = [_strip_identity(item) if isinstance(item, Mapping) else item for item in value]
        else:
            result[key] = value
    return result


def _entity_rows(federation: Mapping[str, Any], *, limit: int) -> list[dict[str, Any]]:
    entities = _rows(federation.get("entities"))
    edges = _rows(federation.get("edges"))
    conflicts = _rows(federation.get("conflicts"))
    degree: Counter[str] = Counter()
    weighted: Counter[str] = Counter()
    conflict_count: Counter[str] = Counter()
    conflict_severity: dict[str, str] = {}
    severity_rank = {"error": 3, "warning": 2, "info": 1}

    for edge in edges:
        edge_type = str(edge.get("edge_type") or "")
        weight = EDGE_WEIGHTS.get(edge_type, 1)
        for key in ("from_entity", "to_entity"):
            entity_id = str(edge.get(key) or "")
            if entity_id:
                degree[entity_id] += 1
                weighted[entity_id] += weight

    for conflict in conflicts:
        severity = str(conflict.get("severity") or "info")
        for value in _strip_identity(conflict).values():
            if not isinstance(value, str):
                continue
            for entity in entities:
                entity_id = str(entity.get("entity_id") or "")
                entity_value = str(entity.get("value") or "")
                if entity_id and (entity_id in value or (entity_value and entity_value in value)):
                    conflict_count[entity_id] += 1
                    current = conflict_severity.get(entity_id, "")
                    if severity_rank.get(severity, 0) > severity_rank.get(current, 0):
                        conflict_severity[entity_id] = severity

    rows: list[dict[str, Any]] = []
    for entity in entities:
        entity_id = str(entity.get("entity_id") or "")
        entity_type = str(entity.get("entity_type") or "entity")
        facet = ENTITY_FACETS.get(entity_type, "entity")
        evidence_count = len(_strings(entity.get("source_ids")))
        score = int(weighted[entity_id]) * 12 + int(degree[entity_id]) * 4 + evidence_count * 8
        if facet in {"surface", "claim", "symbol"}:
            score += 30
        score -= int(conflict_count[entity_id]) * 15
        rows.append(
            {
                "row_id": _stable_id("urow", [facet, entity_type, entity.get("value"), entity_id]),
                "facet": facet,
                "label": str(entity.get("label") or entity.get("value") or entity_id),
                "value": str(entity.get("value") or ""),
                "entity_type": entity_type,
                "entity_ref": entity_id,
                "score": score,
                "edge_count": int(degree[entity_id]),
                "weighted_edge_score": int(weighted[entity_id]),
                "evidence_count": evidence_count,
                "conflict_count": int(conflict_count[entity_id]),
                "highest_conflict_severity": conflict_severity.get(entity_id, "none"),
                "metadata": _strip_identity(_mapping(entity.get("metadata"))),
            }
        )
    rows.sort(key=lambda item: (-int(item["score"]), str(item["facet"]), str(item["label"])))
    return rows[: max(1, int(limit))]


def _conflict_rows(federation: Mapping[str, Any], *, limit: int) -> list[dict[str, Any]]:
    rows = []
    rank = {"error": 300, "warning": 200, "info": 100}
    for index, conflict in enumerate(_rows(federation.get("conflicts"))):
        public = _strip_identity(conflict)
        conflict_type = str(public.get("conflict_type") or "conflict")
        severity = str(public.get("severity") or "info")
        detail = _mapping(public.get("detail"))
        rows.append(
            {
                "row_id": _stable_id("urow", ["conflict", index, conflict_type, severity, detail]),
                "facet": "conflict",
                "label": conflict_type,
                "value": severity,
                "score": rank.get(severity, 100),
                "severity": severity,
                "conflict_type": conflict_type,
                "detail": _strip_identity(detail),
            }
        )
    rows.sort(key=lambda item: (-int(item["score"]), str(item["label"])))
    return rows[: max(1, int(limit))]


def _memory_rows(memory_ledger: Mapping[str, Any], *, limit: int) -> list[dict[str, Any]]:
    rows = []
    for row in _rows(memory_ledger.get("rows")):
        task = str(row.get("task") or "")
        prompt = str(row.get("model_prompt_source") or "")
        reusable = row.get("reusable") is True
        savings = float(row.get("estimated_token_savings_percent") or 0.0)
        rows.append(
            {
                "row_id": _stable_id("urow", ["memory", row.get("artifact_kind"), row.get("path"), task, prompt]),
                "facet": "memory",
                "label": task or str(row.get("artifact_kind") or "memory"),
                "value": str(row.get("path") or ""),
                "score": int(140 if reusable else 60) + round(savings),
                "artifact_kind": str(row.get("artifact_kind") or ""),
                "memory_role": str(row.get("memory_role") or ""),
                "status": str(row.get("status") or ""),
                "reusable": reusable,
                "task": task,
                "targets": _strings(row.get("targets")),
                "fingerprint_digest": str(row.get("input_fingerprint_digest") or ""),
                "model_prompt_source": prompt,
                "estimated_token_savings_percent": savings,
            }
        )
    rows.sort(key=lambda item: (-int(item["score"]), str(item["artifact_kind"]), str(item["label"])))
    return rows[: max(1, int(limit))]


def _command_rows(capabilities: Mapping[str, Any], *, limit: int) -> list[dict[str, Any]]:
    rows = []
    for row in _rows(capabilities.get("commands")):
        command = str(row.get("command") or "")
        rows.append(
            {
                "row_id": _stable_id("urow", ["command", command]),
                "facet": "command",
                "label": command,
                "value": str(row.get("intent") or ""),
                "score": 120 if command in {"unify-context", "prepare-model-input", "decide-continuation"} else 85,
                "command": command,
                "intent": str(row.get("intent") or ""),
                "writes": _strings(row.get("writes")),
                "output_schemas": _strings(row.get("output_schemas")),
                "authority_effect": str(row.get("authority_effect") or ""),
                "no_apply": row.get("no_apply") is True,
            }
        )
    rows.sort(key=lambda item: (-int(item["score"]), str(item["command"])))
    return rows[: max(1, int(limit))]


def _capability_rows(native_plan: Mapping[str, Any], *, limit: int) -> list[dict[str, Any]]:
    rows = []
    for row in _rows(native_plan.get("capabilities")):
        status = str(row.get("integration_status") or "")
        rows.append(
            {
                "row_id": _stable_id("urow", ["capability", row.get("capability_id")]),
                "facet": "capability",
                "label": str(row.get("capability_name") or row.get("capability_id") or ""),
                "value": str(row.get("capability_id") or ""),
                "score": 130 if status == "native_available" else 90,
                "capability_id": str(row.get("capability_id") or ""),
                "integration_status": status,
                "integration_mode": str(row.get("integration_mode") or ""),
                "native_owner": str(row.get("dcf_native_owner") or ""),
                "commands": _strings(row.get("dcf_commands")),
                "native_surfaces": _strings(row.get("native_surfaces")),
            }
        )
    rows.sort(key=lambda item: (-int(item["score"]), str(item["capability_id"])))
    return rows[: max(1, int(limit))]


def build_unified_index(
    *,
    federation: Mapping[str, Any],
    federation_path: str = "",
    memory_ledger: Mapping[str, Any] | None = None,
    memory_ledger_path: str = "",
    capabilities: Mapping[str, Any] | None = None,
    capabilities_path: str = "",
    native_plan: Mapping[str, Any] | None = None,
    native_plan_path: str = "",
    limit: int = 200,
    query: str = "",
) -> dict[str, Any]:
    """Build a source-collapsed DCF working set.

    The generated rows intentionally avoid exposing source identity fields.
    Source-like provenance remains inside the original input artifacts; this
    artifact is the public DCF-native query plane.
    """

    limit = max(1, int(limit))
    memory_ledger = dict(memory_ledger or {})
    capabilities = dict(capabilities or {})
    native_plan = dict(native_plan or {})
    terms = _terms(query)
    rows = [
        *_entity_rows(federation, limit=limit),
        *_conflict_rows(federation, limit=limit),
        *_memory_rows(memory_ledger, limit=limit),
        *_command_rows(capabilities, limit=limit),
        *_capability_rows(native_plan, limit=limit),
    ]
    if terms:
        for row in rows:
            row["query_match_score"] = _count_terms(row, terms)
        rows = [row for row in rows if int(row.get("query_match_score") or 0) > 0]
    rows.sort(key=lambda item: (-int(item["score"]), -int(item.get("query_match_score") or 0), str(item["facet"]), str(item["label"])))
    rows = rows[:limit]
    facet_counts = Counter(str(row.get("facet") or "") for row in rows)
    observed_artifact_count = len(_rows(federation.get("sources"))) + int(bool(memory_ledger)) + int(bool(capabilities)) + int(bool(native_plan))
    warnings = []
    if not rows:
        warnings.append({"id": "no_unified_rows", "detail": "No rows matched the selected unified context inputs."})
    return {
        "schema_version": UNIFIED_INDEX_SCHEMA_VERSION,
        "ok": True,
        "status": "pass_unified_index" if rows else "warn_unified_index",
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": utc_now(),
        "query": str(query or ""),
        "limit": limit,
        "inputs": {
            "federation": {
                "path": federation_path,
                "schema_version": federation.get("schema_version"),
                "entity_count": len(_rows(federation.get("entities"))),
                "edge_count": len(_rows(federation.get("edges"))),
                "conflict_count": len(_rows(federation.get("conflicts"))),
            },
            "memory_ledger": {"path": memory_ledger_path, "schema_version": memory_ledger.get("schema_version") if memory_ledger else ""},
            "capabilities": {"path": capabilities_path, "schema_version": capabilities.get("schema_version") if capabilities else ""},
            "native_plan": {"path": native_plan_path, "schema_version": native_plan.get("schema_version") if native_plan else ""},
        },
        "summary": {
            "row_count": len(rows),
            "facet_counts": dict(sorted(facet_counts.items())),
            "observed_artifact_count": observed_artifact_count,
            "query_filtered": bool(terms),
            "warning_count": len(warnings),
        },
        "source_identity_policy": {
            "public_identity": "deep_context_federation",
            "user_facing_source_identity_collapsed": True,
            "source_ids_exposed": False,
            "source_table_exposed": False,
            "upstream_identity_fields_stripped": True,
            "audit_provenance_location": "original_input_artifacts",
        },
        "rows": rows,
        "warnings": warnings,
        "safety_boundaries": {
            "authority_effect": "none",
            "no_apply": True,
            "mutation_allowed": False,
            "external_model_calls": False,
            "source_or_authority_mutation": False,
            "user_facing_source_identity_collapsed_to_dcf": True,
        },
    }


def _compact_working_row(row: Mapping[str, Any], *, label_chars: int, value_chars: int) -> dict[str, Any]:
    compact = {
        "row_id": str(row.get("row_id") or ""),
        "facet": str(row.get("facet") or ""),
        "label": _truncate(row.get("label"), label_chars),
        "value": _truncate(row.get("value"), value_chars),
        "score": int(row.get("score") or 0),
    }
    for key in (
        "entity_type",
        "conflict_count",
        "highest_conflict_severity",
        "severity",
        "status",
        "reusable",
        "task",
        "command",
        "capability_id",
        "integration_status",
        "query_match_score",
    ):
        if key in row:
            compact[key] = row[key]
    if row.get("facet") == "conflict":
        compact["attention"] = "inspect_before_use"
    elif int(row.get("conflict_count") or 0) > 0:
        compact["attention"] = "has_conflict"
    else:
        compact["attention"] = "normal"
    return _strip_identity(compact)


def build_unified_working_set(
    *,
    unified_index: Mapping[str, Any],
    unified_index_path: str = "",
    query: str = "",
    limit: int = 24,
    label_chars: int = 96,
    value_chars: int = 160,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """Build a compact, task-scoped machine working set from a unified index."""

    limit = max(1, int(limit))
    token_budget = int(max_tokens) if max_tokens is not None else None
    if token_budget is not None:
        token_budget = max(1, token_budget)
    terms = _terms(query)
    source_rows = _rows(unified_index.get("rows"))
    rows: list[dict[str, Any]] = []
    for row in source_rows:
        candidate = dict(row)
        if terms:
            candidate["query_match_score"] = int(candidate.get("query_match_score") or _count_terms(candidate, terms))
        rows.append(candidate)
    if terms:
        matched = [row for row in rows if int(row.get("query_match_score") or 0) > 0]
        if matched:
            rows = matched
    rows.sort(key=lambda item: (-int(item.get("query_match_score") or 0), -int(item.get("score") or 0), str(item.get("facet") or ""), str(item.get("label") or "")))
    candidates = [_compact_working_row(row, label_chars=label_chars, value_chars=value_chars) for row in rows[:limit]]
    warnings = []

    def build_payload(selected_rows: Sequence[Mapping[str, Any]], selected_warnings: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        facet_counts = Counter(str(row.get("facet") or "") for row in selected_rows)
        payload = {
            "schema_version": UNIFIED_WORKING_SET_SCHEMA_VERSION,
            "ok": True,
            "status": "pass_unified_working_set" if selected_rows else "warn_unified_working_set",
            "authority_effect": "none",
            "no_apply": True,
            "generated_at": utc_now(),
            "query": str(query or ""),
            "limit": limit,
            "inputs": {
                "unified_index": {
                    "path": unified_index_path,
                    "schema_version": unified_index.get("schema_version"),
                    "row_count": len(source_rows),
                }
            },
            "summary": {
                "selected_row_count": len(selected_rows),
                "source_row_count": len(source_rows),
                "candidate_row_count": len(candidates),
                "omitted_row_count": max(0, len(source_rows) - len(selected_rows)),
                "omitted_by_token_budget_count": max(0, len(candidates) - len(selected_rows)) if token_budget is not None else 0,
                "facet_counts": dict(sorted(facet_counts.items())),
                "query_filtered": bool(terms),
                "estimated_tokens": 0,
                "max_tokens": token_budget,
                "token_budget_limited": token_budget is not None and len(selected_rows) < len(candidates),
                "warning_count": len(selected_warnings),
            },
            "optimization_policy": {
                "purpose": "task_scoped_machine_read_first",
                "full_index_role": "audit_only",
                "label_chars": max(8, int(label_chars)),
                "value_chars": max(8, int(value_chars)),
                "max_tokens": token_budget,
                "source_identity_collapsed": True,
            },
            "source_identity_policy": {
                "public_identity": "deep_context_federation",
                "user_facing_source_identity_collapsed": True,
                "source_ids_exposed": False,
                "source_table_exposed": False,
                "upstream_identity_fields_stripped": True,
                "audit_provenance_location": "unified_index_source",
            },
            "rows": list(selected_rows),
            "warnings": [dict(row) for row in selected_warnings],
            "safety_boundaries": {
                "authority_effect": "none",
                "no_apply": True,
                "mutation_allowed": False,
                "external_model_calls": False,
                "source_or_authority_mutation": False,
                "user_facing_source_identity_collapsed_to_dcf": True,
            },
        }
        payload["summary"]["estimated_tokens"] = estimate_tokens(_pretty_json_text(payload))
        return payload

    if token_budget is None:
        selected = candidates
    else:
        selected = []
        for row in candidates:
            trial = [*selected, row]
            if estimate_tokens(_pretty_json_text(build_payload(trial, warnings))) <= token_budget or not selected:
                selected = trial
        if len(selected) < len(candidates):
            warnings.append(
                {
                    "id": "selected_context_token_budget_applied",
                    "detail": {
                        "max_tokens": token_budget,
                        "candidate_row_count": len(candidates),
                        "selected_row_count": len(selected),
                    },
                }
            )
    if not selected:
        warnings.append({"id": "no_selected_context_rows", "detail": "No rows were available for the compact working set."})
    payload = build_payload(selected, warnings)
    while token_budget is not None and int(payload["summary"]["estimated_tokens"]) > token_budget and len(selected) > 1:
        selected = selected[:-1]
        payload = build_payload(selected, warnings)
    if token_budget is not None and int(payload["summary"]["estimated_tokens"]) > token_budget:
        payload["warnings"].append(
            {
                "id": "selected_context_minimum_exceeds_token_budget",
                "detail": {"max_tokens": token_budget, "estimated_tokens": payload["summary"]["estimated_tokens"]},
            }
        )
        payload["summary"]["warning_count"] = len(payload["warnings"])
    return payload


def markdown_unified_index(payload: Mapping[str, Any]) -> str:
    summary = _mapping(payload.get("summary"))
    policy = _mapping(payload.get("source_identity_policy"))
    lines = [
        "# DCF Unified Context Index",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Rows: `{summary.get('row_count', 0)}`",
        f"- Public identity: `{policy.get('public_identity')}`",
        f"- Source ids exposed: `{policy.get('source_ids_exposed')}`",
        "",
        "## Facets",
        "",
    ]
    facets = _mapping(summary.get("facet_counts"))
    if facets:
        for facet, count in sorted(facets.items()):
            lines.append(f"- `{facet}`: `{count}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Top Rows", ""])
    for row in _rows(payload.get("rows"))[:25]:
        lines.append(
            "- `{facet}` `{label}` score=`{score}` value=`{value}`".format(
                facet=row.get("facet"),
                label=row.get("label"),
                score=row.get("score"),
                value=row.get("value"),
            )
        )
    if not payload.get("rows"):
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def markdown_unified_working_set(payload: Mapping[str, Any]) -> str:
    summary = _mapping(payload.get("summary"))
    policy = _mapping(payload.get("source_identity_policy"))
    lines = [
        "# DCF Selected Context",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Selected rows: `{summary.get('selected_row_count', 0)}` / `{summary.get('source_row_count', 0)}`",
        f"- Public identity: `{policy.get('public_identity')}`",
        f"- Source ids exposed: `{policy.get('source_ids_exposed')}`",
        "",
        "## Rows",
        "",
    ]
    for row in _rows(payload.get("rows"))[:25]:
        lines.append(
            "- `{facet}` `{label}` score=`{score}` attention=`{attention}` value=`{value}`".format(
                facet=row.get("facet"),
                label=row.get("label"),
                score=row.get("score"),
                attention=row.get("attention"),
                value=row.get("value"),
            )
        )
    if not payload.get("rows"):
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"
