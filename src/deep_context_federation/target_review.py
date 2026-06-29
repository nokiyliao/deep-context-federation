"""Batch target review for DCF adjudication portfolios."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from deep_context_federation.adjudicate import adjudicate_target
from deep_context_federation.context_pack import estimate_tokens

TARGET_REVIEW_SCHEMA_VERSION = "deep_context_federation_target_review_v1"

_VERDICT_PRIORITY = {
    "blocked": 100,
    "no_match": 90,
    "advisory_only": 80,
    "warn": 60,
    "supported": 10,
}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _dedupe_targets(targets: Sequence[str]) -> list[str]:
    result = []
    seen = set()
    for target in targets:
        clean = str(target).strip()
        if not clean or clean in seen:
            continue
        result.append(clean)
        seen.add(clean)
    return result


def _support_counts(adjudication: Mapping[str, Any]) -> dict[str, int]:
    support = adjudication.get("support") if isinstance(adjudication.get("support"), Mapping) else {}
    return {
        "authority": len(support.get("authority_sources") or []),
        "evidence": len(support.get("evidence_sources") or []),
        "advisory": len(support.get("advisory_sources") or []),
        "context": len(support.get("context_sources") or []),
        "unavailable": len(support.get("unavailable_sources") or []),
    }


def _priority_score(adjudication: Mapping[str, Any]) -> int:
    verdict = str(adjudication.get("verdict") or "")
    confidence = int(adjudication.get("confidence_score") or 0)
    risk_flags = adjudication.get("risk_flags") if isinstance(adjudication.get("risk_flags"), list) else []
    conflicts = adjudication.get("conflict_summary") if isinstance(adjudication.get("conflict_summary"), Mapping) else {}
    score = _VERDICT_PRIORITY.get(verdict, 50)
    score += min(20, len(risk_flags) * 5)
    score += min(20, int(conflicts.get("error") or 0) * 10 + int(conflicts.get("warning") or 0) * 5)
    score += max(0, 50 - confidence) // 5
    return max(0, min(150, score))


def _row_from_adjudication(adjudication: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "target": adjudication.get("target"),
        "verdict": adjudication.get("verdict"),
        "confidence_score": adjudication.get("confidence_score"),
        "priority_score": _priority_score(adjudication),
        "risk_flags": adjudication.get("risk_flags") or [],
        "support_counts": _support_counts(adjudication),
        "conflict_summary": adjudication.get("conflict_summary"),
        "recommended_use": adjudication.get("recommended_use"),
    }


def _render_prompt_text(result: Mapping[str, Any]) -> str:
    lines = [
        "# Deep Context Federation Target Review",
        "",
        "Boundary: authority_effect=none; no_apply=true; this ranks context risk only.",
        f"Status: {result.get('status')}",
        "",
        "## Priority Targets",
    ]
    for row in result.get("priority_order") or []:
        if isinstance(row, Mapping):
            lines.append(
                "- {target} verdict={verdict} priority={priority} confidence={confidence} risks={risks}".format(
                    target=row.get("target"),
                    verdict=row.get("verdict"),
                    priority=row.get("priority_score"),
                    confidence=row.get("confidence_score"),
                    risks=",".join(row.get("risk_flags") or []) or "none",
                )
            )
    if not result.get("priority_order"):
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def _bounded_prompt_text(result: Mapping[str, Any], token_budget: int) -> tuple[str, int]:
    prompt_view = dict(result)
    rows = list(result.get("priority_order") or [])
    prompt_view["priority_order"] = rows
    prompt_text = _render_prompt_text(prompt_view)
    prompt_tokens = estimate_tokens(prompt_text)
    while rows and prompt_tokens > token_budget:
        rows = rows[:-1]
        prompt_view["priority_order"] = rows
        prompt_text = _render_prompt_text(prompt_view)
        prompt_tokens = estimate_tokens(prompt_text)
    return prompt_text, prompt_tokens


def review_targets(
    payload: Mapping[str, Any],
    *,
    targets: Sequence[str],
    limit: int = 20,
    token_budget: int = 3000,
    include_details: bool = False,
    include_prompt: bool = True,
) -> dict[str, Any]:
    """Review many targets and rank adjudication risk."""

    clean_targets = _dedupe_targets(targets)
    token_budget = max(500, int(token_budget))
    rows: list[dict[str, Any]] = []
    adjudications: list[dict[str, Any]] = []
    for target in clean_targets:
        adjudication = adjudicate_target(
            payload,
            target=target,
            limit=limit,
            token_budget=token_budget,
            include_prompt=False,
        )
        row = _row_from_adjudication(adjudication)
        rows.append(row)
        if include_details:
            adjudications.append(adjudication)
    priority_order = sorted(rows, key=lambda row: (-int(row["priority_score"]), str(row["target"])))
    verdict_counts = Counter(str(row.get("verdict") or "") for row in rows)
    risk_flag_counts = Counter(flag for row in rows for flag in row.get("risk_flags") or [])
    confidence_values = [int(row.get("confidence_score") or 0) for row in rows]
    status = "pass"
    if any(row.get("verdict") == "blocked" for row in rows):
        status = "blocked"
    elif any(row.get("verdict") in {"warn", "advisory_only", "no_match"} for row in rows):
        status = "warn"
    result: dict[str, Any] = {
        "schema_version": TARGET_REVIEW_SCHEMA_VERSION,
        "status": status,
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": _utc_now(),
        "target_count": len(clean_targets),
        "reviewed_count": len(rows),
        "summary": {
            "verdict_counts": dict(sorted(verdict_counts.items())),
            "risk_flag_counts": dict(sorted(risk_flag_counts.items())),
            "average_confidence": round(sum(confidence_values) / len(confidence_values), 3) if confidence_values else 0.0,
            "max_priority_score": max((int(row["priority_score"]) for row in rows), default=0),
        },
        "rows": rows,
        "priority_order": priority_order,
        "adjudications": adjudications,
        "recommended_next_targets": [row["target"] for row in priority_order[: min(10, len(priority_order))]],
    }
    prompt_text, prompt_tokens = _bounded_prompt_text(result, token_budget) if include_prompt else ("", 0)
    result["prompt_text"] = prompt_text
    result["prompt_estimated_tokens"] = prompt_tokens
    return result


def markdown_target_review(result: Mapping[str, Any]) -> str:
    summary = result.get("summary") if isinstance(result.get("summary"), Mapping) else {}
    lines = [
        "# Deep Context Federation Target Review",
        "",
        f"- Status: `{result.get('status')}`",
        f"- Targets: `{result.get('target_count')}`",
        f"- Reviewed: `{result.get('reviewed_count')}`",
        f"- Average confidence: `{summary.get('average_confidence')}`",
        f"- Max priority score: `{summary.get('max_priority_score')}`",
        "",
        "## Priority Order",
        "",
    ]
    for row in result.get("priority_order") or []:
        if isinstance(row, Mapping):
            lines.append(
                f"- `{row.get('target')}` verdict=`{row.get('verdict')}` priority=`{row.get('priority_score')}` confidence=`{row.get('confidence_score')}`"
            )
    if not result.get("priority_order"):
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"
