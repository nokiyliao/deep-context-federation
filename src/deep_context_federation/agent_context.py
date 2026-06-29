"""Bounded context bundles from DCF agent CI read plans."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from deep_context_federation.builder import utc_now
from deep_context_federation.context_pack import estimate_tokens

AGENT_CONTEXT_SCHEMA_VERSION = "deep_context_federation_agent_context_v1"


def _json_text(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    except Exception:
        return str(value)


def _resolve(path: str | Path, *, base_dir: Path) -> Path:
    candidate = Path(str(path)).expanduser()
    if not candidate.is_absolute():
        candidate = base_dir / candidate
    return candidate.resolve()


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""


def _truncate_text(text: str, max_tokens: int) -> tuple[str, bool]:
    if not text or max_tokens <= 0:
        return "", bool(text)
    if estimate_tokens(text) <= max_tokens:
        return text, False
    suffix = "\n...<truncated by dcf agent-context>...\n"

    best = ""
    low = 0
    high = len(text)
    while low <= high:
        mid = (low + high) // 2
        candidate = text[:mid].rstrip() + suffix
        if estimate_tokens(candidate) <= max_tokens:
            best = candidate
            low = mid + 1
        else:
            high = mid - 1
    if best:
        return best, True

    # Extremely small budgets may not fit the full marker. Keep the invariant
    # stronger than the marker readability in that degenerate case.
    return suffix[: max(0, max_tokens * 4)], True


def _source_contract(agent_ci: Mapping[str, Any]) -> dict[str, Any]:
    from deep_context_federation.schemas import validate_artifact_contract

    return validate_artifact_contract(agent_ci, artifact_kind="agent_ci")


def _rows_for_mode(agent_ci: Mapping[str, Any], mode: str) -> list[dict[str, Any]]:
    read_plan = agent_ci.get("artifact_read_plan") if isinstance(agent_ci.get("artifact_read_plan"), Mapping) else {}
    rows = [dict(row) for row in read_plan.get("rows") or [] if isinstance(row, Mapping)]
    if mode == "read-first":
        allowed_roles = {"read_first"}
    elif mode == "decision-allowed":
        allowed_roles = {"read_first", "read_next_if_decision_allows"}
    else:
        allowed_roles = {"read_first", "read_next_if_decision_allows"}
    return [row for row in sorted(rows, key=lambda item: int(item.get("order") or 0)) if row.get("role") in allowed_roles]


def _render_prompt(result: Mapping[str, Any]) -> str:
    lines = [
        "# Deep Context Federation Agent Context",
        "",
        "Boundary: authority_effect=none; no_apply=true; context is advisory and read-only.",
        f"Status: {result.get('status')}",
        f"Mode: {result.get('mode')}",
        f"Task: {result.get('task')}",
        f"Decision: {result.get('decision', {}).get('action') if isinstance(result.get('decision'), Mapping) else ''}",
        "",
        "Use only the selected sections below as model context. Follow missing/skipped/truncated caveats.",
        "",
        "## Selected Sections",
    ]
    sections = result.get("sections") if isinstance(result.get("sections"), list) else []
    if not sections:
        lines.append("- no sections selected")
    for section in sections:
        if not isinstance(section, Mapping):
            continue
        lines.extend(
            [
                "",
                "### {order}. {role} {schema}".format(
                    order=section.get("order"),
                    role=section.get("role"),
                    schema=section.get("schema_version") or "unknown_schema",
                ),
                f"- path: `{section.get('path')}`",
                f"- tokens: `{section.get('selected_estimated_tokens')}` truncated=`{section.get('truncated')}`",
            ]
        )
        content = str(section.get("content") or "")
        if content:
            lines.extend(["", "```json", content, "```"])
    skipped = result.get("skipped") if isinstance(result.get("skipped"), list) else []
    if skipped:
        lines.extend(["", "## Skipped"])
        for row in skipped:
            if isinstance(row, Mapping):
                lines.append(f"- `{row.get('path')}` reason=`{row.get('reason')}`")
    return "\n".join(lines).rstrip() + "\n"


def build_agent_context(
    agent_ci: Mapping[str, Any],
    *,
    agent_ci_path: Path,
    mode: str = "read-first",
    token_budget: int = 4000,
    max_artifact_tokens: int = 1200,
    include_content: bool = True,
    include_prompt: bool = True,
) -> dict[str, Any]:
    """Build one bounded model context bundle from an agent CI read plan."""

    agent_ci_path = agent_ci_path.expanduser().resolve()
    base_dir = agent_ci_path.parent
    token_budget = max(1, int(token_budget))
    max_artifact_tokens = max(1, int(max_artifact_tokens))
    contract = _source_contract(agent_ci)
    candidate_rows = _rows_for_mode(agent_ci, mode)
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    content_budget = max(1, int(token_budget * 0.65))
    used_tokens = 0
    missing_count = 0

    for row in candidate_rows:
        path = _resolve(str(row.get("path") or row.get("artifact_ref") or ""), base_dir=base_dir)
        exists = path.exists() and path.is_file()
        if not exists:
            missing_count += 1
            skipped.append({**row, "path": path.as_posix(), "reason": "missing_artifact"})
            continue
        raw = _read_text(path)
        raw_tokens = estimate_tokens(raw) if raw else 0
        remaining = content_budget - used_tokens
        if include_content and remaining <= 0:
            skipped.append({**row, "path": path.as_posix(), "reason": "token_budget_exhausted"})
            continue
        content = ""
        truncated = False
        selected_tokens = 0
        if include_content:
            content, truncated = _truncate_text(raw, min(max_artifact_tokens, remaining))
            selected_tokens = estimate_tokens(content) if content else 0
        section = {
            "order": len(selected) + 1,
            "source_order": row.get("order"),
            "role": row.get("role"),
            "artifact_ref": row.get("artifact_ref"),
            "path": path.as_posix(),
            "exists": exists,
            "bytes": path.stat().st_size,
            "schema_version": row.get("schema_version") or "",
            "source_estimated_tokens": row.get("estimated_tokens"),
            "selected_estimated_tokens": selected_tokens,
            "truncated": truncated,
            "sha256": _sha256(raw),
            "content": content,
        }
        selected.append(section)
        used_tokens += selected_tokens

    status = "pass_agent_context"
    ok = True
    if contract.get("ok") is not True or missing_count:
        status = "fail_agent_context"
        ok = False
    elif skipped or any(section.get("truncated") for section in selected):
        status = "warn_agent_context"

    decision = agent_ci.get("decision") if isinstance(agent_ci.get("decision"), Mapping) else {}
    result: dict[str, Any] = {
        "schema_version": AGENT_CONTEXT_SCHEMA_VERSION,
        "ok": ok,
        "status": status,
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": utc_now(),
        "input_ref": agent_ci_path.as_posix(),
        "mode": mode,
        "task": agent_ci.get("task"),
        "decision": {
            "action": decision.get("action"),
            "continue_agent": decision.get("continue_agent"),
            "reason": decision.get("reason"),
        },
        "token_budget": token_budget,
        "max_artifact_tokens": max_artifact_tokens,
        "include_content": include_content,
        "source_contract_validation": contract,
        "summary": {
            "candidate_artifact_count": len(candidate_rows),
            "selected_artifact_count": len(selected),
            "skipped_artifact_count": len(skipped),
            "missing_artifact_count": missing_count,
            "truncated_artifact_count": sum(1 for section in selected if section.get("truncated")),
            "selected_estimated_tokens": used_tokens,
            "schema_versions": sorted({str(section.get("schema_version")) for section in selected if section.get("schema_version")}),
        },
        "sections": selected,
        "skipped": skipped,
        "safety_boundaries": {
            "authority_effect": "none",
            "no_apply": True,
            "mutation_allowed": False,
            "reads_generated_artifacts_only": True,
            "external_model_calls": False,
            "source_or_authority_mutation": False,
        },
    }
    prompt_text = _render_prompt(result) if include_prompt else ""
    result["prompt_text"] = prompt_text
    result["prompt_estimated_tokens"] = estimate_tokens(prompt_text) if prompt_text else 0
    result["json_estimated_tokens"] = estimate_tokens(_json_text(result))
    return result


def markdown_agent_context(result: Mapping[str, Any]) -> str:
    summary = result.get("summary") if isinstance(result.get("summary"), Mapping) else {}
    lines = [
        "# Deep Context Federation Agent Context",
        "",
        f"- Status: `{result.get('status')}`",
        f"- OK: `{result.get('ok')}`",
        f"- Mode: `{result.get('mode')}`",
        f"- Input: `{result.get('input_ref')}`",
        f"- Selected artifacts: `{summary.get('selected_artifact_count')}`",
        f"- Skipped artifacts: `{summary.get('skipped_artifact_count')}`",
        f"- Missing artifacts: `{summary.get('missing_artifact_count')}`",
        f"- Selected tokens: `{summary.get('selected_estimated_tokens')}`",
        f"- Prompt tokens: `{result.get('prompt_estimated_tokens')}`",
        "",
        "## Sections",
        "",
    ]
    for section in result.get("sections") or []:
        if isinstance(section, Mapping):
            lines.append(
                "- `{path}` role=`{role}` schema=`{schema}` tokens=`{tokens}` truncated=`{truncated}`".format(
                    path=section.get("path"),
                    role=section.get("role"),
                    schema=section.get("schema_version"),
                    tokens=section.get("selected_estimated_tokens"),
                    truncated=section.get("truncated"),
                )
            )
    if not result.get("sections"):
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"
