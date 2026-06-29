"""Deterministic target adjudication over DCF evidence cards."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from deep_context_federation.context_pack import estimate_tokens
from deep_context_federation.resolve import resolve_target

ADJUDICATE_SCHEMA_VERSION = "deep_context_federation_adjudicate_v1"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _source_row(item: Mapping[str, Any]) -> Mapping[str, Any]:
    row = item.get("row")
    return row if isinstance(row, Mapping) else {}


def _tier_for_role(role: str) -> str:
    role_text = role.lower()
    if role_text.startswith("advisory") or "advisory" in role_text:
        return "advisory"
    if any(term in role_text for term in ("truth", "authority", "claim", "surface", "policy", "contract")):
        return "authority"
    if any(term in role_text for term in ("evidence", "receipt", "inventory")):
        return "evidence"
    return "context"


def _classify_sources(resolve: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    buckets = {"authority": [], "evidence": [], "advisory": [], "context": [], "unavailable": []}
    for item in resolve.get("related_sources") or []:
        if not isinstance(item, Mapping):
            continue
        row = _source_row(item)
        status = str(row.get("status") or "")
        tier = _tier_for_role(str(row.get("role") or ""))
        entry = {
            "source_id": item.get("id"),
            "role": row.get("role"),
            "status": status,
            "required": bool(row.get("required")),
            "path": row.get("path"),
            "quality": row.get("quality") if isinstance(row.get("quality"), Mapping) else {},
            "score": item.get("score"),
        }
        buckets[tier].append(entry)
        if status not in {"loaded", "stale"}:
            buckets["unavailable"].append(entry)
    return buckets


def _conflict_counts(resolve: Mapping[str, Any]) -> dict[str, int]:
    counts = {"error": 0, "warning": 0, "info": 0, "unknown": 0}
    for item in resolve.get("related_conflicts") or []:
        if not isinstance(item, Mapping):
            continue
        row = item.get("row") if isinstance(item.get("row"), Mapping) else {}
        severity = str(row.get("severity") or "unknown")
        counts[severity if severity in counts else "unknown"] += 1
    return counts


def _risk_flags(resolve: Mapping[str, Any], sources: Mapping[str, list[Mapping[str, Any]]], conflicts: Mapping[str, int]) -> list[str]:
    flags: list[str] = []
    if resolve.get("status") == "no_match":
        flags.append("target_not_found")
    if conflicts.get("error", 0) > 0:
        flags.append("error_conflict_present")
    if conflicts.get("warning", 0) > 0:
        flags.append("warning_conflict_present")
    if not sources.get("authority") and not sources.get("evidence"):
        flags.append("no_authority_or_evidence_source")
    if sources.get("advisory") and not sources.get("authority"):
        flags.append("advisory_without_authority")
    if sources.get("unavailable"):
        flags.append("unavailable_source_present")
    for tier in ("authority", "evidence", "advisory", "context"):
        if any(str(row.get("status") or "") == "stale" for row in sources.get(tier, [])):
            flags.append("stale_source_present")
            break
    return list(dict.fromkeys(flags))


def _confidence_score(resolve: Mapping[str, Any], sources: Mapping[str, list[Mapping[str, Any]]], conflicts: Mapping[str, int], risk_flags: list[str]) -> int:
    summary = resolve.get("summary") if isinstance(resolve.get("summary"), Mapping) else {}
    score = 0
    if int(summary.get("matched_entity_count") or 0) > 0:
        score += 25
    if int(summary.get("related_edge_count") or 0) > 0:
        score += 15
    score += min(25, len(sources.get("authority", [])) * 15)
    score += min(20, len(sources.get("evidence", [])) * 10)
    score += min(10, len(sources.get("advisory", [])) * 5)
    score -= min(40, int(conflicts.get("error", 0)) * 40)
    score -= min(25, int(conflicts.get("warning", 0)) * 15)
    if "no_authority_or_evidence_source" in risk_flags:
        score -= 25
    if "stale_source_present" in risk_flags:
        score -= 10
    if "unavailable_source_present" in risk_flags:
        score -= 15
    return max(0, min(100, score))


def _verdict(resolve: Mapping[str, Any], confidence_score: int, conflicts: Mapping[str, int], risk_flags: list[str]) -> str:
    if resolve.get("status") == "no_match":
        return "no_match"
    if int(conflicts.get("error", 0)) > 0:
        return "blocked"
    if "no_authority_or_evidence_source" in risk_flags:
        return "advisory_only"
    if confidence_score >= 70 and not risk_flags:
        return "supported"
    return "warn"


def _render_prompt_text(result: Mapping[str, Any]) -> str:
    support = result.get("support") if isinstance(result.get("support"), Mapping) else {}
    lines = [
        "# Deep Context Federation Adjudication",
        "",
        f"Target: {result.get('target')}",
        "Boundary: authority_effect=none; no_apply=true; this verdict gates context use only.",
        f"Verdict: {result.get('verdict')}",
        f"Confidence: {result.get('confidence_score')}",
        f"Risk flags: {', '.join(result.get('risk_flags') or []) or 'none'}",
        "",
        "## Authority Sources",
    ]
    for row in support.get("authority_sources") or []:
        lines.append(f"- {row.get('source_id')} role={row.get('role')} status={row.get('status')} path={row.get('path')}")
    if not support.get("authority_sources"):
        lines.append("- none")
    lines.extend(["", "## Evidence Sources"])
    for row in support.get("evidence_sources") or []:
        lines.append(f"- {row.get('source_id')} role={row.get('role')} status={row.get('status')} path={row.get('path')}")
    if not support.get("evidence_sources"):
        lines.append("- none")
    lines.extend(["", "## Advisory Sources"])
    for row in support.get("advisory_sources") or []:
        lines.append(f"- {row.get('source_id')} role={row.get('role')} status={row.get('status')} path={row.get('path')}")
    if not support.get("advisory_sources"):
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def _bounded_prompt_text(result: Mapping[str, Any], token_budget: int) -> tuple[str, int]:
    prompt_text = _render_prompt_text(result)
    prompt_tokens = estimate_tokens(prompt_text)
    if prompt_tokens <= token_budget:
        return prompt_text, prompt_tokens
    compact = dict(result)
    support = dict(result.get("support") or {})
    for key in ("authority_sources", "evidence_sources", "advisory_sources"):
        support[key] = list(support.get(key) or [])[:3]
    compact["support"] = support
    prompt_text = _render_prompt_text(compact)
    return prompt_text, estimate_tokens(prompt_text)


def adjudicate_target(
    payload: Mapping[str, Any],
    *,
    target: str,
    limit: int = 20,
    token_budget: int = 2500,
    include_prompt: bool = True,
) -> dict[str, Any]:
    """Adjudicate whether a target is supported by authority/evidence context."""

    token_budget = max(500, int(token_budget))
    resolve = resolve_target(payload, target=target, limit=limit, token_budget=token_budget, include_prompt=include_prompt)
    sources = _classify_sources(resolve)
    conflicts = _conflict_counts(resolve)
    risk_flags = _risk_flags(resolve, sources, conflicts)
    confidence = _confidence_score(resolve, sources, conflicts, risk_flags)
    verdict = _verdict(resolve, confidence, conflicts, risk_flags)
    result: dict[str, Any] = {
        "schema_version": ADJUDICATE_SCHEMA_VERSION,
        "status": "ok",
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": _utc_now(),
        "target": target,
        "verdict": verdict,
        "confidence_score": confidence,
        "risk_flags": risk_flags,
        "support": {
            "authority_sources": sources["authority"],
            "evidence_sources": sources["evidence"],
            "advisory_sources": sources["advisory"],
            "context_sources": sources["context"],
            "unavailable_sources": sources["unavailable"],
        },
        "conflict_summary": conflicts,
        "resolve_summary": resolve.get("summary"),
        "resolve": resolve,
        "recommended_use": {
            "model_context_allowed": verdict in {"supported", "warn", "advisory_only"},
            "requires_human_review": verdict in {"warn", "blocked", "advisory_only", "no_match"},
            "safe_for_mutation": False,
        },
    }
    prompt_text, prompt_tokens = _bounded_prompt_text(result, token_budget) if include_prompt else ("", 0)
    result["prompt_text"] = prompt_text
    result["prompt_estimated_tokens"] = prompt_tokens
    return result


def markdown_adjudication(result: Mapping[str, Any]) -> str:
    support = result.get("support") if isinstance(result.get("support"), Mapping) else {}
    lines = [
        "# Deep Context Federation Adjudication",
        "",
        f"- Target: `{result.get('target')}`",
        f"- Verdict: `{result.get('verdict')}`",
        f"- Confidence: `{result.get('confidence_score')}`",
        f"- Risk flags: `{', '.join(result.get('risk_flags') or []) or 'none'}`",
        "",
        "## Support",
        "",
        f"- Authority sources: `{len(support.get('authority_sources') or [])}`",
        f"- Evidence sources: `{len(support.get('evidence_sources') or [])}`",
        f"- Advisory sources: `{len(support.get('advisory_sources') or [])}`",
        f"- Context sources: `{len(support.get('context_sources') or [])}`",
        "",
        "## Recommended Use",
        "",
    ]
    recommended = result.get("recommended_use") if isinstance(result.get("recommended_use"), Mapping) else {}
    for key in ("model_context_allowed", "requires_human_review", "safe_for_mutation"):
        lines.append(f"- `{key}`: `{recommended.get(key)}`")
    return "\n".join(lines).rstrip() + "\n"
