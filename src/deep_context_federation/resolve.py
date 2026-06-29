"""Target-level evidence resolver for DCF artifacts."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from deep_context_federation.context_pack import estimate_tokens
from deep_context_federation.context_pack import pack_context

RESOLVE_SCHEMA_VERSION = "deep_context_federation_resolve_v1"

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _json_text(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    except Exception:
        return str(value)


def _rows(payload: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    return [dict(item) for item in payload.get(key) or [] if isinstance(item, Mapping)]


def _terms(target: str) -> list[str]:
    terms = []
    for raw in re.findall(r"[A-Za-z0-9_./:-]+|[\u4e00-\u9fff]+", target.lower()):
        if len(raw) < 2 or raw in _STOPWORDS:
            continue
        terms.append(raw)
    return sorted(set(terms), key=lambda item: (-len(item), item))


def _match_score(row: Mapping[str, Any], target: str, terms: Sequence[str], *, base: int = 0) -> tuple[int, list[str]]:
    text = _json_text(row).lower()
    target_text = target.lower()
    matched = [term for term in terms if term in text]
    score = base + len(matched) * 20
    if target_text and target_text in text:
        score += 100
    if matched:
        score += 10
    return score, matched


def _row_id(row: Mapping[str, Any], fallback: str) -> str:
    return str(
        row.get("entity_id")
        or row.get("source_id")
        or row.get("edge_id")
        or row.get("conflict_id")
        or fallback
    )


def _entity_source_ids(entity: Mapping[str, Any]) -> set[str]:
    raw = entity.get("source_ids")
    if isinstance(raw, list):
        return {str(item) for item in raw if item}
    return set()


def _ranked_matches(rows: Sequence[Mapping[str, Any]], *, target: str, terms: Sequence[str], kind: str, limit: int, base: int = 0) -> list[dict[str, Any]]:
    matches = []
    for index, row in enumerate(rows):
        score, matched = _match_score(row, target, terms, base=base)
        if score <= base and not matched:
            continue
        matches.append(
            {
                "kind": kind,
                "id": _row_id(row, f"{kind}:{index}"),
                "score": score,
                "matched_terms": matched,
                "row": dict(row),
            }
        )
    matches.sort(key=lambda item: (-int(item["score"]), str(item["kind"]), str(item["id"])))
    return matches[: max(1, int(limit))]


def _related_edges(edges: Sequence[Mapping[str, Any]], entity_ids: set[str], *, target: str, terms: Sequence[str], limit: int) -> list[dict[str, Any]]:
    matches = []
    for index, edge in enumerate(edges):
        touches_entity = str(edge.get("from_entity") or "") in entity_ids or str(edge.get("to_entity") or "") in entity_ids
        score, matched = _match_score(edge, target, terms, base=50 if touches_entity else 0)
        if not touches_entity and score <= 0 and not matched:
            continue
        matches.append(
            {
                "kind": "edge",
                "id": _row_id(edge, f"edge:{index}"),
                "score": score,
                "matched_terms": matched,
                "row": dict(edge),
            }
        )
    matches.sort(key=lambda item: (-int(item["score"]), str(item["id"])))
    return matches[: max(1, int(limit))]


def _related_sources(
    sources: Sequence[Mapping[str, Any]],
    source_ids: set[str],
    *,
    target: str,
    terms: Sequence[str],
    limit: int,
) -> list[dict[str, Any]]:
    matches = []
    for index, source in enumerate(sources):
        source_id = str(source.get("source_id") or "")
        is_referenced = source_id in source_ids
        score, matched = _match_score(source, target, terms, base=70 if is_referenced else 0)
        if not is_referenced and score <= 0 and not matched:
            continue
        matches.append(
            {
                "kind": "source",
                "id": _row_id(source, f"source:{index}"),
                "score": score,
                "matched_terms": matched,
                "row": dict(source),
            }
        )
    matches.sort(key=lambda item: (-int(item["score"]), str(item["id"])))
    return matches[: max(1, int(limit))]


def _related_conflicts(
    conflicts: Sequence[Mapping[str, Any]],
    source_ids: set[str],
    *,
    target: str,
    terms: Sequence[str],
    limit: int,
) -> list[dict[str, Any]]:
    severity_base = {"error": 90, "warning": 60, "info": 20}
    matches = []
    for index, conflict in enumerate(conflicts):
        source_id = str(conflict.get("source_id") or "")
        referenced = source_id in source_ids
        base = severity_base.get(str(conflict.get("severity") or ""), 0) if referenced else 0
        score, matched = _match_score(conflict, target, terms, base=base)
        if not referenced and score <= 0 and not matched:
            continue
        matches.append(
            {
                "kind": "conflict",
                "id": _row_id(conflict, f"conflict:{index}"),
                "score": score,
                "matched_terms": matched,
                "row": dict(conflict),
            }
        )
    matches.sort(key=lambda item: (-int(item["score"]), str(item["id"])))
    return matches[: max(1, int(limit))]


def _highest_conflict_severity(conflicts: Sequence[Mapping[str, Any]]) -> str:
    order = {"error": 3, "warning": 2, "info": 1}
    highest = ""
    highest_score = 0
    for item in conflicts:
        row = item.get("row") if isinstance(item.get("row"), Mapping) else {}
        severity = str(row.get("severity") or "")
        score = order.get(severity, 0)
        if score > highest_score:
            highest = severity
            highest_score = score
    return highest or "none"


def _render_prompt_text(result: Mapping[str, Any]) -> str:
    lines = [
        "# Deep Context Federation Target Resolution",
        "",
        f"Target: {result.get('target')}",
        "Boundary: authority_effect=none; no_apply=true; this is evidence context, not mutation authority.",
        f"Status: {result.get('status')}",
        "",
        "## Matched Entities",
    ]
    for item in result.get("matched_entities") or []:
        if isinstance(item, Mapping):
            lines.append(f"- {item.get('id')} score={item.get('score')} row={_json_text(item.get('row'))}")
    if not result.get("matched_entities"):
        lines.append("- none")
    lines.extend(["", "## Related Sources"])
    for item in result.get("related_sources") or []:
        if isinstance(item, Mapping):
            row = item.get("row") if isinstance(item.get("row"), Mapping) else {}
            lines.append(f"- {item.get('id')} role={row.get('role')} status={row.get('status')} path={row.get('path')}")
    if not result.get("related_sources"):
        lines.append("- none")
    lines.extend(["", "## Related Edges"])
    for item in result.get("related_edges") or []:
        if isinstance(item, Mapping):
            row = item.get("row") if isinstance(item.get("row"), Mapping) else {}
            lines.append(f"- {item.get('id')} type={row.get('edge_type')} from={row.get('from_entity')} to={row.get('to_entity')}")
    if not result.get("related_edges"):
        lines.append("- none")
    lines.extend(["", "## Related Conflicts"])
    for item in result.get("related_conflicts") or []:
        if isinstance(item, Mapping):
            row = item.get("row") if isinstance(item.get("row"), Mapping) else {}
            lines.append(f"- {item.get('id')} severity={row.get('severity')} type={row.get('conflict_type')} detail={row.get('detail')}")
    if not result.get("related_conflicts"):
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def _bounded_prompt_text(result: Mapping[str, Any], token_budget: int) -> tuple[str, int, dict[str, int]]:
    prompt_view = dict(result)
    for key in ("matched_entities", "related_sources", "related_edges", "related_conflicts"):
        prompt_view[key] = list(result.get(key) or [])
    minimums = {
        "matched_entities": 1 if prompt_view["matched_entities"] else 0,
        "related_sources": 1 if prompt_view["related_sources"] else 0,
        "related_edges": 0,
        "related_conflicts": 0,
    }
    trim_order = ("related_edges", "related_conflicts", "related_sources", "matched_entities")
    prompt_text = _render_prompt_text(prompt_view)
    prompt_tokens = estimate_tokens(prompt_text)
    while prompt_tokens > token_budget:
        changed = False
        for key in trim_order:
            rows = list(prompt_view.get(key) or [])
            if len(rows) > minimums[key]:
                prompt_view[key] = rows[:-1]
                changed = True
                break
        if not changed:
            break
        prompt_text = _render_prompt_text(prompt_view)
        prompt_tokens = estimate_tokens(prompt_text)
    rendered_counts = {
        key: len(prompt_view.get(key) or [])
        for key in ("matched_entities", "related_sources", "related_edges", "related_conflicts")
    }
    return prompt_text, prompt_tokens, rendered_counts


def resolve_target(
    payload: Mapping[str, Any],
    *,
    target: str,
    limit: int = 20,
    token_budget: int = 2500,
    include_prompt: bool = True,
) -> dict[str, Any]:
    """Resolve a claim/path/surface/symbol target into a compact evidence card."""

    limit = max(1, int(limit))
    token_budget = max(500, int(token_budget))
    terms = _terms(target)
    sources = _rows(payload, "sources")
    entities = _rows(payload, "entities")
    edges = _rows(payload, "edges")
    conflicts = _rows(payload, "conflicts")
    matched_entities = _ranked_matches(entities, target=target, terms=terms, kind="entity", limit=limit, base=0)
    entity_ids = {str(item["id"]) for item in matched_entities}
    source_ids: set[str] = set()
    for item in matched_entities:
        row = item.get("row") if isinstance(item.get("row"), Mapping) else {}
        source_ids.update(_entity_source_ids(row))
    related_edges = _related_edges(edges, entity_ids, target=target, terms=terms, limit=limit * 2)
    for item in related_edges:
        row = item.get("row") if isinstance(item.get("row"), Mapping) else {}
        if row.get("source_id"):
            source_ids.add(str(row.get("source_id")))
    related_sources = _related_sources(sources, source_ids, target=target, terms=terms, limit=limit)
    source_ids.update(str(item.get("id")) for item in related_sources if item.get("id"))
    related_conflicts = _related_conflicts(conflicts, source_ids, target=target, terms=terms, limit=limit)
    context_pack = pack_context(
        payload,
        task=f"resolve target {target}",
        token_budget=token_budget,
        max_rows=limit * 2,
        include_prompt=include_prompt,
    )
    severity = _highest_conflict_severity(related_conflicts)
    status = "no_match" if not matched_entities and not related_sources and not related_edges else "matched"
    if status == "matched" and severity in {"error", "warning"}:
        status = "warn"
    result: dict[str, Any] = {
        "schema_version": RESOLVE_SCHEMA_VERSION,
        "status": status,
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": _utc_now(),
        "target": target,
        "terms": terms,
        "source_snapshot": {
            "schema_version": payload.get("schema_version"),
            "generated_at": payload.get("generated_at"),
            "head_commit": payload.get("head_commit"),
            "authority_effect": payload.get("authority_effect"),
            "no_apply": payload.get("no_apply"),
        },
        "summary": {
            "matched_entity_count": len(matched_entities),
            "related_source_count": len(related_sources),
            "related_edge_count": len(related_edges),
            "related_conflict_count": len(related_conflicts),
            "highest_conflict_severity": severity,
        },
        "matched_entities": matched_entities,
        "related_sources": related_sources,
        "related_edges": related_edges,
        "related_conflicts": related_conflicts,
        "context_pack": context_pack,
        "recommended_commands": [
            {"purpose": "trace_target_neighborhood", "command": f"dcf trace --match {json.dumps(target, ensure_ascii=True)} --format markdown"},
            {"purpose": "build_target_context_pack", "command": f"dcf pack --task {json.dumps('resolve target ' + target, ensure_ascii=True)} --token-budget {token_budget}"},
        ],
    }
    prompt_text, prompt_tokens, rendered_counts = _bounded_prompt_text(result, token_budget) if include_prompt else ("", 0, {})
    result["prompt_text"] = prompt_text
    result["prompt_estimated_tokens"] = prompt_tokens
    result["prompt_rendered_counts"] = rendered_counts
    return result


def markdown_resolve(result: Mapping[str, Any]) -> str:
    summary = result.get("summary") if isinstance(result.get("summary"), Mapping) else {}
    lines = [
        "# Deep Context Federation Resolve",
        "",
        f"- Status: `{result.get('status')}`",
        f"- Target: `{result.get('target')}`",
        f"- Matched entities: `{summary.get('matched_entity_count')}`",
        f"- Related sources: `{summary.get('related_source_count')}`",
        f"- Related edges: `{summary.get('related_edge_count')}`",
        f"- Related conflicts: `{summary.get('related_conflict_count')}`",
        f"- Highest conflict severity: `{summary.get('highest_conflict_severity')}`",
        "",
        "## Matched Entities",
        "",
    ]
    for item in result.get("matched_entities") or []:
        if isinstance(item, Mapping):
            row = item.get("row") if isinstance(item.get("row"), Mapping) else {}
            lines.append(f"- `{item.get('id')}` type=`{row.get('entity_type')}` value=`{row.get('value')}` score=`{item.get('score')}`")
    if not result.get("matched_entities"):
        lines.append("- none")
    lines.extend(["", "## Related Sources", ""])
    for item in result.get("related_sources") or []:
        if isinstance(item, Mapping):
            row = item.get("row") if isinstance(item.get("row"), Mapping) else {}
            lines.append(f"- `{item.get('id')}` role=`{row.get('role')}` status=`{row.get('status')}`")
    if not result.get("related_sources"):
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"
