"""Select the final model input surface from verified DCF artifacts."""

from __future__ import annotations

import shlex
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from deep_context_federation.agent_model_input import build_agent_model_input
from deep_context_federation.builder import utc_now
from deep_context_federation.source_identity import public_source_identity_policy

AGENT_HANDOFF_SCHEMA_VERSION = "deep_context_federation_agent_handoff_v1"
AGENT_MODEL_INPUT_SCHEMA_VERSION = "deep_context_federation_agent_model_input_v1"
AGENT_READY_SCHEMA_VERSION = "deep_context_federation_agent_ready_v1"
AGENT_ONBOARD_SCHEMA_VERSION = "deep_context_federation_agent_onboard_v1"
MODEL_ENTRYPOINT_SELECTION_SCHEMA_VERSION = "deep_context_federation_model_entrypoint_selection_v1"

SUPPORTED_INPUT_SCHEMAS = {
    AGENT_HANDOFF_SCHEMA_VERSION: "agent_handoff",
    AGENT_MODEL_INPUT_SCHEMA_VERSION: "agent_model_input",
    AGENT_READY_SCHEMA_VERSION: "agent_ready",
    AGENT_ONBOARD_SCHEMA_VERSION: "agent_onboard",
}
PREFERENCES = ("prompt-file", "prompt-pack", "audit-json")


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": payload.get("schema_version"),
        "ok": payload.get("ok"),
        "status": payload.get("status"),
    }


def _quote(value: str) -> str:
    return shlex.quote(value)


def _input_path_text(input_path: Path | None) -> str:
    return input_path.expanduser().resolve().as_posix() if input_path is not None else ""


def _check(checks: list[dict[str, Any]], check_id: str, passed: bool, *, severity: str = "error", detail: Any = None) -> None:
    checks.append({"id": check_id, "passed": bool(passed), "severity": "info" if passed else severity, "detail": detail})


def _surface_from_payload(payload: Mapping[str, Any], *, input_path: Path | None) -> tuple[str, dict[str, Any], dict[str, Any]]:
    schema_version = str(payload.get("schema_version") or "")
    input_artifact_kind = SUPPORTED_INPUT_SCHEMAS.get(schema_version, "unsupported")
    if schema_version == AGENT_HANDOFF_SCHEMA_VERSION and input_path is not None:
        model_input = build_agent_model_input(payload, handoff_path=input_path, include_prompt=False)
        return input_artifact_kind, model_input, model_input
    if schema_version == AGENT_ONBOARD_SCHEMA_VERSION:
        ready = dict(_mapping(payload.get("agent_ready")))
        return input_artifact_kind, dict(payload), ready or dict(payload)
    return input_artifact_kind, dict(payload), dict(payload)


def _entrypoint_decision(root: Mapping[str, Any], surface: Mapping[str, Any]) -> Mapping[str, Any]:
    decision = _mapping(root.get("entrypoint_decision"))
    if decision:
        return decision
    return _mapping(surface.get("entrypoint_decision"))


def _prompt_pack(root: Mapping[str, Any], surface: Mapping[str, Any]) -> Mapping[str, Any]:
    pack = _mapping(surface.get("prompt_pack"))
    if pack:
        return pack
    return _mapping(root.get("prompt_pack"))


def _prompt_source(root: Mapping[str, Any], surface: Mapping[str, Any], prompt_pack: Mapping[str, Any]) -> str:
    return str(root.get("prompt_source") or surface.get("prompt_source") or prompt_pack.get("prompt_source") or "")


def _prompt_format(root: Mapping[str, Any], surface: Mapping[str, Any], prompt_pack: Mapping[str, Any]) -> str:
    return str(root.get("prompt_format") or surface.get("prompt_format") or prompt_pack.get("prompt_format") or "")


def _prompt_tokens(root: Mapping[str, Any], surface: Mapping[str, Any], prompt_pack: Mapping[str, Any]) -> int:
    value = root.get("prompt_estimated_tokens") or surface.get("prompt_estimated_tokens") or prompt_pack.get("prompt_estimated_tokens") or 0
    try:
        return max(0, int(value))
    except Exception:
        return 0


def build_model_entrypoint_selection(
    payload: Mapping[str, Any],
    *,
    input_path: Path | None = None,
    prefer: str = "prompt-file",
    allow_caution: bool = False,
) -> dict[str, Any]:
    """Return a final machine-readable model input selection for wrappers."""

    preference = prefer if prefer in PREFERENCES else "prompt-file"
    input_ref = _input_path_text(input_path)
    input_schema_version = str(payload.get("schema_version") or "")
    input_artifact_kind, root, surface = _surface_from_payload(payload, input_path=input_path)
    decision = _entrypoint_decision(root, surface)
    decision_name = str(decision.get("decision") or "")
    decision_status = str(decision.get("status") or "")
    decision_ok = decision_name == "use_dcf_model_input" or (allow_caution and decision_name == "use_dcf_model_input_with_caution")
    prompt_pack = _prompt_pack(root, surface)
    prompt_source = _prompt_source(root, surface, prompt_pack)
    prompt_format = _prompt_format(root, surface, prompt_pack)
    prompt_tokens = _prompt_tokens(root, surface, prompt_pack)
    prompt_text_available = bool(str(prompt_pack.get("prompt_text") or ""))

    checks: list[dict[str, Any]] = []
    _check(checks, "supported_input_schema", input_artifact_kind != "unsupported", detail=input_schema_version)
    _check(checks, "entrypoint_decision_present", bool(decision), detail=decision_status)
    _check(checks, "entrypoint_decision_allows_model_use", decision_ok, detail={"decision": decision_name, "allow_caution": allow_caution})
    _check(checks, "authority_effect_none", str(root.get("authority_effect") or "none") == "none", detail=root.get("authority_effect"))
    _check(checks, "no_apply_true", root.get("no_apply") is True, detail=root.get("no_apply"))

    warnings: list[dict[str, Any]] = []
    if decision_name == "use_dcf_model_input_with_caution" and allow_caution:
        warnings.append({"id": "entrypoint_decision_caution_allowed", "detail": decision_status})

    if input_artifact_kind == "unsupported" or not decision_ok:
        mode = "blocked"
        consume_as = "none"
        model_input_ref = ""
        token_policy = "entrypoint_decision_blocks_model_input"
    elif preference == "audit-json":
        mode = "audit_json"
        consume_as = "json_audit_context"
        model_input_ref = input_ref
        token_policy = "audit_json_selected_by_preference"
    elif preference == "prompt-pack" and prompt_text_available:
        mode = "prompt_pack"
        consume_as = "embedded_markdown_prompt"
        model_input_ref = input_ref
        token_policy = "use_embedded_prompt_pack_text"
    elif prompt_source:
        mode = "prompt_file"
        consume_as = "markdown_prompt_file"
        model_input_ref = prompt_source
        token_policy = "read_prompt_file_only_by_default"
    elif prompt_text_available:
        mode = "prompt_pack"
        consume_as = "embedded_markdown_prompt"
        model_input_ref = input_ref
        token_policy = "fallback_to_embedded_prompt_pack_text"
        warnings.append({"id": "prompt_file_missing_using_prompt_pack", "detail": preference})
    else:
        mode = "blocked"
        consume_as = "none"
        model_input_ref = ""
        token_policy = "no_model_input_selected"

    _check(checks, "model_input_ref_selected", bool(model_input_ref) and mode != "blocked", detail={"mode": mode, "model_input_ref": model_input_ref})
    if mode == "prompt_file":
        _check(checks, "prompt_format_markdown", prompt_format == "markdown", detail=prompt_format)

    hard_errors = [row for row in checks if not row["passed"] and row["severity"] == "error"]
    if hard_errors:
        status = "fail_model_entrypoint_selection"
        action = "repair_before_model_use"
        ok = False
    elif warnings:
        status = "warn_model_entrypoint_selection"
        action = "use_selected_model_input_with_caution"
        ok = True
    else:
        status = "pass_model_entrypoint_selection"
        action = "use_selected_model_input"
        ok = True

    if input_artifact_kind == "agent_handoff" and mode == "prompt_file" and input_ref:
        recommended_command = f"dcf release-model-input --input {_quote(input_ref)} --format prompt"
    elif mode == "audit_json" and input_ref:
        recommended_command = f"cat {_quote(input_ref)}"
    elif mode == "prompt_file" and prompt_source:
        recommended_command = f"cat {_quote(prompt_source)}"
    else:
        recommended_command = ""

    return {
        "schema_version": MODEL_ENTRYPOINT_SELECTION_SCHEMA_VERSION,
        "ok": ok,
        "status": status,
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": utc_now(),
        "input_ref": input_ref,
        "input_schema_version": input_schema_version,
        "input_artifact_kind": input_artifact_kind,
        "evaluated_artifact_summary": _summary(surface),
        "source_identity_policy": public_source_identity_policy(audit_provenance_location="selected_entrypoint_input_artifact"),
        "entrypoint_decision": dict(decision),
        "selected_model_input": {
            "mode": mode,
            "consume_as": consume_as,
            "model_input_ref": model_input_ref,
            "prompt_source": prompt_source,
            "prompt_format": prompt_format,
            "prompt_estimated_tokens": prompt_tokens,
            "prompt_text_available": prompt_text_available,
            "audit_ref": input_ref,
            "preference": preference,
            "token_policy": token_policy,
        },
        "recommended_reader": {
            "action": action,
            "command": recommended_command,
            "read_path": model_input_ref if mode in {"prompt_file", "audit_json"} else "",
            "read_json_path": "prompt_pack.prompt_text" if mode == "prompt_pack" else "",
        },
        "checks": checks,
        "warnings": warnings,
        "errors": hard_errors,
        "safety_boundaries": {
            "authority_effect": "none",
            "no_apply": True,
            "mutation_allowed": False,
            "external_model_calls": False,
            "source_or_authority_mutation": False,
            "prompt_emitted_by_selection": False,
        },
    }


def markdown_model_entrypoint_selection(result: Mapping[str, Any]) -> str:
    selected = _mapping(result.get("selected_model_input"))
    reader = _mapping(result.get("recommended_reader"))
    lines = [
        "# Deep Context Federation Model Entrypoint Selection",
        "",
        f"- Status: `{result.get('status')}`",
        f"- OK: `{result.get('ok')}`",
        f"- Input kind: `{result.get('input_artifact_kind')}`",
        f"- Mode: `{selected.get('mode')}`",
        f"- Model input ref: `{selected.get('model_input_ref')}`",
        f"- Recommended action: `{reader.get('action')}`",
        f"- Recommended command: `{reader.get('command')}`",
        "",
        "## Errors",
        "",
    ]
    errors = [row for row in result.get("errors") or [] if isinstance(row, Mapping)]
    if errors:
        lines.extend(f"- `{row.get('id')}` detail=`{row}`" for row in errors)
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"
