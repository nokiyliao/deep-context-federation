"""Verification for gated DCF agent handoff artifacts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from deep_context_federation.agent_handoff import AGENT_HANDOFF_SCHEMA_VERSION
from deep_context_federation.builder import utc_now
from deep_context_federation.context_pack import estimate_tokens

AGENT_HANDOFF_VERIFICATION_SCHEMA_VERSION = "deep_context_federation_agent_handoff_verification_v1"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, Mapping) else {}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""


def _resolve(path: str, *, base_dir: Path | None) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute() and base_dir is not None:
        candidate = base_dir / candidate
    return candidate.resolve()


def _fingerprint(path: Path) -> dict[str, Any]:
    text = _read_text(path)
    exists = path.exists() and path.is_file()
    return {
        "exists": exists,
        "bytes": path.stat().st_size if exists else 0,
        "sha256": _sha256(text),
        "estimated_tokens": estimate_tokens(text) if text else 0,
    }


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(float(numerator) / float(denominator), 6)


def _savings_percent(before: int, after: int) -> float:
    if before <= 0:
        return 0.0
    return round(max(0.0, (float(before - after) / float(before)) * 100.0), 3)


def _int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def verify_agent_handoff(payload: Mapping[str, Any], *, handoff_path: Path | None = None) -> dict[str, Any]:
    """Verify a handoff artifact's boundaries, fingerprints, and token economics."""

    base_dir = handoff_path.expanduser().resolve().parent if handoff_path else None
    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, detail: Any = None, severity: str = "error") -> None:
        checks.append({"id": check_id, "passed": bool(passed), "severity": severity, "detail": detail})

    add("schema_version_supported", payload.get("schema_version") == AGENT_HANDOFF_SCHEMA_VERSION, payload.get("schema_version"))
    add("authority_effect_none", payload.get("authority_effect") == "none", payload.get("authority_effect"))
    add("no_apply_true", payload.get("no_apply") is True, payload.get("no_apply"))

    safety = payload.get("safety_boundaries") if isinstance(payload.get("safety_boundaries"), Mapping) else {}
    add("safety_authority_effect_none", safety.get("authority_effect") == "none", safety.get("authority_effect"))
    add("safety_no_apply_true", safety.get("no_apply") is True, safety.get("no_apply"))
    add("safety_mutation_disallowed", safety.get("mutation_allowed") is False, safety.get("mutation_allowed"))
    add("safety_external_model_calls_false", safety.get("external_model_calls") is False, safety.get("external_model_calls"))
    add("safety_source_or_authority_mutation_false", safety.get("source_or_authority_mutation") is False, safety.get("source_or_authority_mutation"))

    decision = payload.get("decision") if isinstance(payload.get("decision"), Mapping) else {}
    handoff_allowed = decision.get("handoff_allowed") is True
    add("ok_matches_decision", payload.get("ok") is handoff_allowed, {"ok": payload.get("ok"), "handoff_allowed": decision.get("handoff_allowed")})
    if payload.get("ok") is True:
        add("ok_status_is_pass_or_warn", payload.get("status") in {"pass_agent_handoff", "warn_agent_handoff"}, payload.get("status"))
    else:
        add("fail_status_is_fail_agent_handoff", payload.get("status") == "fail_agent_handoff", payload.get("status"))

    model_handoff = payload.get("model_handoff") if isinstance(payload.get("model_handoff"), Mapping) else {}
    add("model_handoff_present", bool(model_handoff), None)
    read_first = [str(item) for item in model_handoff.get("read_first") or [] if str(item)]
    read_first_artifacts = [dict(row) for row in model_handoff.get("read_first_artifacts") or [] if isinstance(row, Mapping)]
    audit_artifacts = [dict(row) for row in model_handoff.get("audit_artifacts") or [] if isinstance(row, Mapping)]
    all_artifacts = read_first_artifacts + audit_artifacts

    recomputed_by_role: dict[str, dict[str, Any]] = {}
    for row in all_artifacts:
        role = str(row.get("role") or "unknown")
        path_text = str(row.get("path") or "")
        add(f"artifact_path_present:{role}", bool(path_text), row)
        if not path_text:
            continue
        path = _resolve(path_text, base_dir=base_dir)
        actual = _fingerprint(path)
        recomputed_by_role[role] = {**actual, "path": path.as_posix(), "role": role}
        add(f"artifact_exists:{role}", actual["exists"] is True, {"path": path.as_posix()})
        add(f"artifact_bytes_match:{role}", _int(row.get("bytes")) == actual["bytes"], {"expected": row.get("bytes"), "actual": actual["bytes"]})
        add(f"artifact_sha256_match:{role}", str(row.get("sha256") or "") == actual["sha256"], {"expected": row.get("sha256"), "actual": actual["sha256"]})
        add(
            f"artifact_estimated_tokens_match:{role}",
            _int(row.get("estimated_tokens")) == actual["estimated_tokens"],
            {"expected": row.get("estimated_tokens"), "actual": actual["estimated_tokens"]},
        )

    prompt_source = str(model_handoff.get("model_prompt_source") or "")
    machine_context_source = str(model_handoff.get("machine_context_source") or "")
    context_advantage_source = str(model_handoff.get("context_advantage_source") or "")
    public_boundary_source = str(model_handoff.get("public_boundary_audit_source") or "")
    prompt_row = next((row for row in read_first_artifacts if row.get("role") == "model_prompt"), {})
    context_row = next((row for row in audit_artifacts if row.get("role") == "machine_context"), {})
    gate_row = next((row for row in read_first_artifacts if row.get("role") == "context_gate"), {})
    advantage_row = next((row for row in read_first_artifacts if row.get("role") == "context_advantage"), {})
    public_boundary_row = next((row for row in read_first_artifacts if row.get("role") == "public_boundary_audit"), {})

    add("context_gate_artifact_listed", bool(gate_row), None)
    add("context_advantage_artifact_listed", bool(advantage_row), None)
    add("public_boundary_audit_artifact_listed", bool(public_boundary_row), None)
    add("context_advantage_source_present", bool(context_advantage_source), None)
    add("public_boundary_audit_source_present", bool(public_boundary_source), None)
    add(
        "context_advantage_source_matches_read_first_artifact",
        context_advantage_source == str(advantage_row.get("path") or ""),
        {"source": context_advantage_source, "artifact": advantage_row.get("path")},
    )
    add("context_advantage_source_in_read_first", context_advantage_source in read_first, {"source": context_advantage_source, "read_first": read_first})
    add(
        "public_boundary_audit_source_matches_read_first_artifact",
        public_boundary_source == str(public_boundary_row.get("path") or ""),
        {"source": public_boundary_source, "artifact": public_boundary_row.get("path")},
    )
    add("public_boundary_audit_source_in_read_first", public_boundary_source in read_first, {"source": public_boundary_source, "read_first": read_first})
    if public_boundary_source:
        boundary_path = _resolve(public_boundary_source, base_dir=base_dir)
        boundary_payload = _read_json(boundary_path)
        add("public_boundary_audit_schema", boundary_payload.get("schema_version") == "deep_context_federation_public_boundary_audit_v1", boundary_payload.get("schema_version"))
        add("public_boundary_audit_ok", boundary_payload.get("ok") is True, {"status": boundary_payload.get("status"), "ok": boundary_payload.get("ok")})
        add("public_boundary_audit_no_errors", _int(boundary_payload.get("summary", {}).get("error_count") if isinstance(boundary_payload.get("summary"), Mapping) else 0) == 0, boundary_payload.get("summary"))
    add("machine_context_artifact_listed", bool(context_row), None)
    add("machine_context_source_matches_audit_artifact", machine_context_source == str(context_row.get("path") or ""), {"source": machine_context_source, "artifact": context_row.get("path")})
    if payload.get("ok") is True:
        add("model_prompt_source_present_when_allowed", bool(prompt_source), None)
        add("model_prompt_format_markdown", model_handoff.get("model_prompt_format") == "markdown", model_handoff.get("model_prompt_format"))
        add("model_prompt_source_in_read_first", prompt_source in read_first, {"source": prompt_source, "read_first": read_first})
        add("model_prompt_source_matches_prompt_artifact", prompt_source == str(prompt_row.get("path") or ""), {"source": prompt_source, "artifact": prompt_row.get("path")})
        add("model_prompt_artifact_default_input", prompt_row.get("default_model_input") is True, prompt_row.get("default_model_input"))
    else:
        add("model_prompt_source_empty_when_blocked", prompt_source == "", prompt_source)

    economics = model_handoff.get("token_economics") if isinstance(model_handoff.get("token_economics"), Mapping) else {}
    machine_tokens = _int(context_row.get("estimated_tokens"))
    prompt_tokens = _int(prompt_row.get("estimated_tokens")) if prompt_source else 0
    add("machine_context_tokens_match", _int(model_handoff.get("machine_context_estimated_tokens")) == machine_tokens, {"handoff": model_handoff.get("machine_context_estimated_tokens"), "artifact": machine_tokens})
    if prompt_source:
        add("model_prompt_tokens_match", _int(model_handoff.get("model_prompt_estimated_tokens")) == prompt_tokens, {"handoff": model_handoff.get("model_prompt_estimated_tokens"), "artifact": prompt_tokens})
        add("token_economics_status_measured", economics.get("status") == "measured", economics.get("status"))
        add("token_economics_prompt_tokens_match", _int(economics.get("model_prompt_estimated_tokens")) == prompt_tokens, economics.get("model_prompt_estimated_tokens"))
        add("token_economics_machine_tokens_match", _int(economics.get("machine_context_estimated_tokens")) == machine_tokens, economics.get("machine_context_estimated_tokens"))
        add("token_economics_ratio_match", _float(economics.get("model_prompt_to_machine_context_ratio")) == _ratio(prompt_tokens, machine_tokens), economics.get("model_prompt_to_machine_context_ratio"))
        add("token_economics_savings_match", _int(economics.get("estimated_token_savings")) == max(0, machine_tokens - prompt_tokens), economics.get("estimated_token_savings"))
        add("token_economics_savings_percent_match", _float(economics.get("estimated_token_savings_percent")) == _savings_percent(machine_tokens, prompt_tokens), economics.get("estimated_token_savings_percent"))
    else:
        add("model_prompt_tokens_zero_when_blocked", _int(model_handoff.get("model_prompt_estimated_tokens")) == 0, model_handoff.get("model_prompt_estimated_tokens"))
        add("token_economics_status_not_applicable", economics.get("status") == "not_applicable", economics.get("status"))
        add("token_economics_savings_zero_when_blocked", _int(economics.get("estimated_token_savings")) == 0, economics.get("estimated_token_savings"))

    failed = [row for row in checks if not row["passed"]]
    return {
        "schema_version": AGENT_HANDOFF_VERIFICATION_SCHEMA_VERSION,
        "ok": not failed,
        "status": "pass_agent_handoff_verification" if not failed else "fail_agent_handoff_verification",
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": utc_now(),
        "input_ref": handoff_path.expanduser().resolve().as_posix() if handoff_path else "",
        "check_count": len(checks),
        "error_count": len(failed),
        "checks": checks,
        "errors": failed,
        "summary": {
            "handoff_status": payload.get("status"),
            "handoff_ok": payload.get("ok"),
            "default_model_input": economics.get("default_model_input") if isinstance(economics, Mapping) else "",
            "token_economics_status": economics.get("status") if isinstance(economics, Mapping) else "",
            "estimated_token_savings_percent": economics.get("estimated_token_savings_percent") if isinstance(economics, Mapping) else 0.0,
            "verified_artifact_count": len(all_artifacts),
        },
    }


def markdown_agent_handoff_verification(result: Mapping[str, Any]) -> str:
    lines = [
        "# Deep Context Federation Agent Handoff Verification",
        "",
        f"- Status: `{result.get('status')}`",
        f"- OK: `{result.get('ok')}`",
        f"- Input: `{result.get('input_ref')}`",
        f"- Checks: `{result.get('check_count')}`",
        f"- Errors: `{result.get('error_count')}`",
        "",
        "## Errors",
        "",
    ]
    errors = [row for row in result.get("errors") or [] if isinstance(row, Mapping)]
    if errors:
        for row in errors:
            lines.append(f"- `{row.get('id')}` detail=`{row.get('detail')}`")
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"
