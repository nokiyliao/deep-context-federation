"""Repository-local DCF agent discovery for global wrappers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from deep_context_federation.agent_model_input import build_agent_model_input
from deep_context_federation.builder import read_json
from deep_context_federation.builder import utc_now

AGENT_DISCOVERY_SCHEMA_VERSION = "deep_context_federation_agent_discovery_v1"

DEFAULT_HANDOFF_CANDIDATES = (
    ".dcf/deep_context_federation_agent_handoff.json",
    "deep_context_federation_agent_handoff.json",
)
DEFAULT_MANIFEST_CANDIDATES = (
    "deep_context_federation.json",
    ".dcf/deep_context_federation.json",
)
DEFAULT_FEDERATION_CANDIDATES = (
    ".dcf/deep_context_federation_latest.json",
    "deep_context_federation_latest.json",
)


def _resolve(root: Path, path: Path | str) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


def _existing(root: Path, candidates: Sequence[str]) -> list[str]:
    result = []
    for item in candidates:
        path = _resolve(root, item)
        if path.exists() and path.is_file():
            result.append(path.as_posix())
    return result


def _summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    return {
        "schema_version": payload.get("schema_version"),
        "status": payload.get("status"),
        "ok": payload.get("ok"),
        "summary": dict(summary),
    }


def _quote(path: str) -> str:
    return "'" + path.replace("'", "'\\''") + "'"


def discover_agent_context(*, root: Path, handoff_path: Path | None = None) -> dict[str, Any]:
    """Discover the safest next DCF agent step for a repository."""

    root = root.expanduser().resolve()
    explicit_handoff = handoff_path.expanduser().resolve() if handoff_path else None
    handoff_candidates = [explicit_handoff.as_posix()] if explicit_handoff else list(DEFAULT_HANDOFF_CANDIDATES)
    handoffs = [explicit_handoff.as_posix()] if explicit_handoff and explicit_handoff.exists() else _existing(root, handoff_candidates)
    manifests = _existing(root, DEFAULT_MANIFEST_CANDIDATES)
    federations = _existing(root, DEFAULT_FEDERATION_CANDIDATES)
    status = "not_configured"
    ready_for_model_input = False
    selected_handoff = handoffs[0] if handoffs else ""
    model_input_summary: dict[str, Any] = {}
    diagnostics: list[dict[str, Any]] = []

    if explicit_handoff and not explicit_handoff.exists():
        selected_handoff = explicit_handoff.as_posix()
        status = "blocked_handoff_unreadable"
        diagnostics.append({"id": "handoff_unreadable", "path": selected_handoff})
    elif selected_handoff:
        payload = read_json(Path(selected_handoff))
        if payload:
            model_input = build_agent_model_input(payload, handoff_path=Path(selected_handoff), include_prompt=False)
            model_input_summary = _summary(model_input)
            ready_for_model_input = model_input.get("ok") is True
            status = "ready_model_input" if ready_for_model_input else "blocked_model_input"
            if not ready_for_model_input:
                diagnostics.extend(model_input.get("errors") or [])
        else:
            status = "blocked_handoff_unreadable"
            diagnostics.append({"id": "handoff_unreadable", "path": selected_handoff})
    elif manifests:
        status = "manifest_available"
    elif federations:
        status = "federation_available"

    if ready_for_model_input:
        recommended_next_command = f"dcf agent-model-input --input {_quote(selected_handoff)} --format prompt"
    elif selected_handoff:
        recommended_next_command = f"dcf verify-handoff --input {_quote(selected_handoff)}"
    elif manifests:
        recommended_next_command = f"dcf agent-handoff --root {_quote(root.as_posix())} --manifest {_quote(manifests[0])} --task '<task>'"
    else:
        recommended_next_command = f"dcf scan --root {_quote(root.as_posix())} --output-dir .dcf --write --build"

    return {
        "schema_version": AGENT_DISCOVERY_SCHEMA_VERSION,
        "ok": True,
        "status": status,
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": utc_now(),
        "root": root.as_posix(),
        "ready_for_model_input": ready_for_model_input,
        "selected_handoff": selected_handoff,
        "model_input_summary": model_input_summary,
        "discovered": {
            "handoffs": handoffs,
            "manifests": manifests,
            "federations": federations,
        },
        "recommended_next_command": recommended_next_command,
        "diagnostics": diagnostics,
        "safety_boundaries": {
            "authority_effect": "none",
            "no_apply": True,
            "mutation_allowed": False,
            "reads_dcf_artifacts_only": True,
            "source_tree_scan": False,
            "external_model_calls": False,
            "source_or_authority_mutation": False,
        },
    }


def markdown_agent_discovery(result: Mapping[str, Any]) -> str:
    discovered = result.get("discovered") if isinstance(result.get("discovered"), Mapping) else {}
    lines = [
        "# Deep Context Federation Agent Discovery",
        "",
        f"- Status: `{result.get('status')}`",
        f"- Ready for model input: `{result.get('ready_for_model_input')}`",
        f"- Selected handoff: `{result.get('selected_handoff')}`",
        f"- Recommended next command: `{result.get('recommended_next_command')}`",
        "",
        "## Discovered",
        "",
        f"- Handoffs: `{len(discovered.get('handoffs') or [])}`",
        f"- Manifests: `{len(discovered.get('manifests') or [])}`",
        f"- Federations: `{len(discovered.get('federations') or [])}`",
        "",
        "## Diagnostics",
        "",
    ]
    diagnostics = [row for row in result.get("diagnostics") or [] if isinstance(row, Mapping)]
    if diagnostics:
        for row in diagnostics:
            lines.append(f"- `{row.get('id')}` detail=`{row}`")
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"
