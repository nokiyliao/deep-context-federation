"""Token-aware context packing for model and agent prompts."""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

CONTEXT_PACK_SCHEMA_VERSION = "deep_context_federation_context_pack_v1"

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "this",
    "to",
    "what",
    "with",
}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _json_text(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    except Exception:
        return str(value)


def estimate_tokens(value: Any) -> int:
    """Cheap deterministic token estimate for local budgeting."""

    text = value if isinstance(value, str) else _json_text(value)
    return max(1, (len(text) + 3) // 4)


def _render_prompt_row(item: Mapping[str, Any]) -> str:
    row = item.get("row") if isinstance(item.get("row"), Mapping) else {}
    matched_terms = item.get("matched_terms") if isinstance(item.get("matched_terms"), list) else []
    return "- {kind} id={id} score={score} matched={matched} row={row}".format(
        kind=item.get("kind"),
        id=item.get("id"),
        score=item.get("score"),
        matched=",".join(str(term) for term in matched_terms) or "none",
        row=_json_text(row),
    )


def _render_prompt_text(result: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> str:
    source_snapshot = result.get("source_snapshot") if isinstance(result.get("source_snapshot"), Mapping) else {}
    coverage = result.get("coverage") if isinstance(result.get("coverage"), Mapping) else {}
    lines = [
        "# Deep Context Federation Prompt Pack",
        "",
        "Task: {task}".format(task=result.get("task") or ""),
        "Boundary: authority_effect=none; no_apply=true; do not mutate repo/runtime/authority from this context alone.",
        "Source: schema={schema} generated_at={generated_at} head_commit={head_commit}".format(
            schema=source_snapshot.get("schema_version") or "unknown",
            generated_at=source_snapshot.get("generated_at") or "unknown",
            head_commit=source_snapshot.get("head_commit") or "unknown",
        ),
        "Budget: token_budget={budget} selected_rows={selected} dropped_rows={dropped} source_coverage={coverage}".format(
            budget=result.get("token_budget"),
            selected=result.get("summary", {}).get("selected_count") if isinstance(result.get("summary"), Mapping) else len(rows),
            dropped=result.get("summary", {}).get("dropped_count") if isinstance(result.get("summary"), Mapping) else 0,
            coverage=coverage.get("source_coverage_ratio", 0),
        ),
        "",
        "Use the selected rows as the only task context. Treat conflicts and missing coverage as blockers or caveats.",
        "",
        "## Selected Rows",
    ]
    if not rows:
        lines.append("- no rows selected")
    else:
        lines.extend(_render_prompt_row(item) for item in rows)
    missing_terms = coverage.get("missing_terms") if isinstance(coverage.get("missing_terms"), list) else []
    if missing_terms:
        lines.extend(["", "## Missing Task Terms", "- " + ", ".join(str(term) for term in missing_terms)])
    return "\n".join(lines).rstrip() + "\n"


def _terms(task: str) -> list[str]:
    terms = []
    for raw in re.findall(r"[A-Za-z0-9_./:-]+", task.lower()):
        if len(raw) < 2 or raw in _STOPWORDS:
            continue
        terms.append(raw)
    return sorted(set(terms), key=lambda item: (-len(item), item))


def _rows(payload: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    return [dict(item) for item in payload.get(key) or [] if isinstance(item, Mapping)]


def _compact_row(kind: str, row: Mapping[str, Any]) -> dict[str, Any]:
    if kind == "source":
        keys = [
            "source_id",
            "role",
            "required",
            "status",
            "path",
            "schema_version",
            "authority_effect",
            "no_apply",
            "head_commit",
            "quality",
            "summary",
        ]
    elif kind == "entity":
        keys = ["entity_id", "entity_type", "value", "source_ids"]
    elif kind == "edge":
        keys = ["edge_id", "edge_type", "from_entity", "to_entity", "source_id"]
    else:
        keys = ["conflict_id", "conflict_type", "severity", "source_id", "detail"]
    return {key: row.get(key) for key in keys if key in row}


def _row_id(kind: str, row: Mapping[str, Any], index: int) -> str:
    return str(
        row.get("source_id")
        or row.get("entity_id")
        or row.get("edge_id")
        or row.get("conflict_id")
        or f"{kind}:{index}"
    )


def _base_score(kind: str, row: Mapping[str, Any]) -> int:
    if kind == "conflict":
        severity = str(row.get("severity") or "")
        return 90 if severity == "error" else 60 if severity == "warning" else 30
    if kind == "source":
        quality = row.get("quality") if isinstance(row.get("quality"), Mapping) else {}
        score = int(quality.get("score") or 50)
        if row.get("required"):
            score += 15
        if str(row.get("status") or "") in {"missing", "error", "stale", "optional_unavailable"}:
            score += 25
        return score
    if kind == "entity":
        entity_type = str(row.get("entity_type") or "")
        return 80 if entity_type in {"claim_id", "surface_id"} else 70 if entity_type in {"symbol_fqn", "path"} else 45
    edge_type = str(row.get("edge_type") or "")
    return {
        "SUPPORTS": 75,
        "OWNS": 70,
        "REFERENCES_SYMBOL": 65,
        "DERIVES_FROM": 55,
        "CONFLICTS_WITH": 60,
        "STALE_FOR": 55,
    }.get(edge_type, 40)


def _score_row(kind: str, row: Mapping[str, Any], terms: Sequence[str]) -> tuple[int, list[str]]:
    text = _json_text(row).lower()
    matched = [term for term in terms if term in text]
    score = _base_score(kind, row)
    score += len(matched) * 50
    if matched:
        score += 30
    return score, matched


def _candidate_rows(payload: Mapping[str, Any], terms: Sequence[str]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for kind, key in (("conflict", "conflicts"), ("source", "sources"), ("entity", "entities"), ("edge", "edges")):
        for index, row in enumerate(_rows(payload, key)):
            compact = _compact_row(kind, row)
            score, matched = _score_row(kind, compact, terms)
            candidate = {
                "kind": kind,
                "id": _row_id(kind, row, index),
                "score": score,
                "matched_terms": matched,
                "row": compact,
            }
            candidate["json_estimated_tokens"] = estimate_tokens(candidate)
            candidate["estimated_tokens"] = estimate_tokens(_render_prompt_row(candidate))
            candidates.append(candidate)
    candidates.sort(key=lambda item: (-int(item["score"]), int(item["estimated_tokens"]), str(item["kind"]), str(item["id"])))
    return candidates


def _selected_entity_ids(selected: Sequence[Mapping[str, Any]]) -> set[str]:
    ids = set()
    for item in selected:
        row = item.get("row") if isinstance(item.get("row"), Mapping) else {}
        if item.get("kind") == "entity" and row.get("entity_id"):
            ids.add(str(row.get("entity_id")))
    return ids


def _relationship_boost(candidates: list[dict[str, Any]], selected: Sequence[Mapping[str, Any]]) -> None:
    entity_ids = _selected_entity_ids(selected)
    if not entity_ids:
        return
    for item in candidates:
        if item.get("kind") != "edge":
            continue
        row = item.get("row") if isinstance(item.get("row"), Mapping) else {}
        if str(row.get("from_entity") or "") in entity_ids or str(row.get("to_entity") or "") in entity_ids:
            item["score"] = int(item.get("score") or 0) + 25
    candidates.sort(key=lambda item: (-int(item["score"]), int(item["estimated_tokens"]), str(item["kind"]), str(item["id"])))


def _source_ids_from_item(item: Mapping[str, Any]) -> set[str]:
    row = item.get("row") if isinstance(item.get("row"), Mapping) else {}
    source_ids: set[str] = set()
    if item.get("kind") == "source" and row.get("source_id"):
        source_ids.add(str(row.get("source_id")))
    if row.get("source_id"):
        source_ids.add(str(row.get("source_id")))
    raw_source_ids = row.get("source_ids")
    if isinstance(raw_source_ids, list):
        source_ids.update(str(source_id) for source_id in raw_source_ids if source_id)
    return source_ids


def _coverage(payload: Mapping[str, Any], selected: Sequence[Mapping[str, Any]], terms: Sequence[str]) -> dict[str, Any]:
    all_source_ids = {str(row.get("source_id")) for row in _rows(payload, "sources") if row.get("source_id")}
    selected_source_ids: set[str] = set()
    entity_types: Counter[str] = Counter()
    conflict_severities: Counter[str] = Counter()
    matched_terms: set[str] = set()

    for item in selected:
        selected_source_ids.update(_source_ids_from_item(item))
        matched_terms.update(str(term) for term in item.get("matched_terms") or [])
        row = item.get("row") if isinstance(item.get("row"), Mapping) else {}
        if item.get("kind") == "entity":
            entity_types[str(row.get("entity_type") or "unknown")] += 1
        if item.get("kind") == "conflict":
            conflict_severities[str(row.get("severity") or "unknown")] += 1

    matched = sorted(term for term in terms if term in matched_terms)
    missing = sorted(term for term in terms if term not in matched_terms)
    source_total = len(all_source_ids)
    selected_source_count = len(selected_source_ids)
    return {
        "selected_source_ids": sorted(selected_source_ids),
        "selected_source_count": selected_source_count,
        "source_count": source_total,
        "source_coverage_ratio": round(selected_source_count / source_total, 6) if source_total else 0.0,
        "matched_terms": matched,
        "missing_terms": missing,
        "matched_term_ratio": round(len(matched) / len(terms), 6) if terms else 1.0,
        "selected_entity_type_counts": dict(sorted(entity_types.items())),
        "selected_conflict_severity_counts": dict(sorted(conflict_severities.items())),
    }


def _selected_by_kind(selected: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {kind: sum(1 for item in selected if item["kind"] == kind) for kind in ("source", "entity", "edge", "conflict")}


def _finalize_prompt_budget(
    result: dict[str, Any],
    selected: list[dict[str, Any]],
    dropped: list[dict[str, Any]],
    dropped_keys: set[tuple[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str, int]:
    prompt_text = _render_prompt_text(result, selected)
    prompt_tokens = estimate_tokens(prompt_text)
    token_budget = int(result.get("token_budget") or 0)
    while selected and prompt_tokens > token_budget:
        removed = selected.pop()
        key = (str(removed["kind"]), str(removed["id"]))
        if key not in dropped_keys:
            dropped.append(
                {
                    "kind": removed["kind"],
                    "id": removed["id"],
                    "reason": "prompt_budget_rebalance",
                    "score": removed["score"],
                    "estimated_tokens": removed["estimated_tokens"],
                }
            )
            dropped_keys.add(key)
        result["summary"]["selected_count"] = len(selected)
        result["summary"]["dropped_count"] = len(dropped)
        result["summary"]["selected_by_kind"] = _selected_by_kind(selected)
        result["coverage"] = _coverage(result.get("_source_payload", {}), selected, result.get("terms") or [])
        prompt_text = _render_prompt_text(result, selected)
        prompt_tokens = estimate_tokens(prompt_text)
    return selected, dropped, prompt_text, prompt_tokens


def pack_context(
    payload: Mapping[str, Any],
    *,
    task: str,
    token_budget: int = 4000,
    min_score: int = 0,
    max_rows: int = 80,
    include_prompt: bool = True,
) -> dict[str, Any]:
    """Build a bounded context bundle from a federation artifact."""

    token_budget = max(200, int(token_budget))
    max_rows = max(1, int(max_rows))
    terms = _terms(task)
    candidates = _candidate_rows(payload, terms)
    original_estimated_tokens = estimate_tokens(payload)
    selected: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    selected_keys: set[tuple[str, str]] = set()
    dropped_keys: set[tuple[str, str]] = set()
    used_tokens = estimate_tokens(
        {
            "task": task,
            "schema_version": CONTEXT_PACK_SCHEMA_VERSION,
            "authority_effect": "none",
            "no_apply": True,
        }
    )

    for pass_index in range(2):
        if pass_index == 1:
            _relationship_boost(candidates, selected)
        for item in candidates:
            key = (str(item["kind"]), str(item["id"]))
            if key in selected_keys:
                continue
            if int(item["score"]) < int(min_score):
                continue
            if len(selected) >= max_rows:
                break
            item_tokens = int(item["estimated_tokens"])
            if used_tokens + item_tokens > token_budget:
                if key not in dropped_keys:
                    dropped.append(
                        {
                            "kind": item["kind"],
                            "id": item["id"],
                            "reason": "budget_exceeded",
                            "score": item["score"],
                            "estimated_tokens": item_tokens,
                        }
                    )
                    dropped_keys.add(key)
                continue
            selected.append(item)
            selected_keys.add(key)
            used_tokens += item_tokens

    for item in candidates:
        key = (str(item["kind"]), str(item["id"]))
        if key in selected_keys:
            continue
        if key in dropped_keys:
            continue
        dropped.append(
            {
                "kind": item["kind"],
                "id": item["id"],
                "reason": "lower_rank_or_row_limit",
                "score": item["score"],
                "estimated_tokens": item["estimated_tokens"],
            }
        )
        dropped_keys.add(key)

    compression_ratio = round(used_tokens / original_estimated_tokens, 6) if original_estimated_tokens else 0.0
    result: dict[str, Any] = {
        "schema_version": CONTEXT_PACK_SCHEMA_VERSION,
        "status": "ok",
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": _utc_now(),
        "task": task,
        "terms": terms,
        "token_budget": token_budget,
        "estimated_tokens": used_tokens,
        "original_estimated_tokens": original_estimated_tokens,
        "estimated_token_savings": max(0, original_estimated_tokens - used_tokens),
        "compression_ratio": compression_ratio,
        "json_estimated_tokens": estimate_tokens({"rows": selected, "dropped": dropped[:100]}),
        "budget_utilization": round(used_tokens / token_budget, 6),
        "selection_policy": {
            "min_score": int(min_score),
            "max_rows": max_rows,
            "token_estimator": "ceil(json_chars/4)",
            "budgeted_surface": "prompt_text",
            "relationship_boost": "selected entity adjacency",
        },
        "source_snapshot": {
            "schema_version": payload.get("schema_version"),
            "generated_at": payload.get("generated_at"),
            "head_commit": payload.get("head_commit"),
            "authority_effect": payload.get("authority_effect"),
            "no_apply": payload.get("no_apply"),
        },
        "summary": {
            "candidate_count": len(candidates),
            "selected_count": len(selected),
            "dropped_count": len(dropped),
            "selected_by_kind": _selected_by_kind(selected),
        },
        "coverage": _coverage(payload, selected, terms),
        "rows": selected,
        "dropped": dropped[:100],
    }
    result["_source_payload"] = payload

    if include_prompt:
        selected, dropped, prompt_text, prompt_tokens = _finalize_prompt_budget(result, selected, dropped, dropped_keys)
        result["rows"] = selected
        result["dropped"] = dropped[:100]
        result["estimated_tokens"] = prompt_tokens
        result["prompt_estimated_tokens"] = prompt_tokens
        result["prompt_text"] = prompt_text
        result["estimated_token_savings"] = max(0, original_estimated_tokens - prompt_tokens)
        result["compression_ratio"] = round(prompt_tokens / original_estimated_tokens, 6) if original_estimated_tokens else 0.0
        result["budget_utilization"] = round(prompt_tokens / token_budget, 6)
        result["coverage"] = _coverage(payload, selected, terms)
        result["summary"]["selected_count"] = len(selected)
        result["summary"]["dropped_count"] = len(dropped)
        result["summary"]["selected_by_kind"] = _selected_by_kind(selected)
    else:
        result["prompt_estimated_tokens"] = 0
        result["prompt_text"] = ""

    result.pop("_source_payload", None)
    return result


def markdown_context_pack(result: Mapping[str, Any]) -> str:
    lines = [
        "# Deep Context Federation Context Pack",
        "",
        f"- Status: `{result.get('status')}`",
        f"- Budget: `{result.get('token_budget')}`",
        f"- Estimated tokens: `{result.get('estimated_tokens')}`",
        f"- Original estimated tokens: `{result.get('original_estimated_tokens')}`",
        f"- Estimated token savings: `{result.get('estimated_token_savings')}`",
        f"- Compression ratio: `{result.get('compression_ratio')}`",
        "",
        "## Selected Rows",
        "",
    ]
    for index, item in enumerate(result.get("rows") or [], start=1):
        if not isinstance(item, Mapping):
            continue
        lines.append(
            f"### {index}. `{item.get('kind')}` `{item.get('id')}` score=`{item.get('score')}` tokens=`{item.get('estimated_tokens')}`"
        )
        row = item.get("row") if isinstance(item.get("row"), Mapping) else {}
        for key, value in row.items():
            rendered = json.dumps(value, ensure_ascii=True, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
            lines.append(f"- `{key}`: `{rendered}`")
        lines.append("")
    if not result.get("rows"):
        lines.append("- no rows selected")
    return "\n".join(lines).rstrip() + "\n"
