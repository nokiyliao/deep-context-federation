"""Fail-closed model input reader for DCF agent handoffs."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from deep_context_federation.agent_handoff_verify import verify_agent_handoff
from deep_context_federation.builder import utc_now
from deep_context_federation.context_pack import estimate_tokens
from deep_context_federation.source_identity import public_prompt_pack
from deep_context_federation.source_identity import public_source_identity_policy

AGENT_MODEL_INPUT_SCHEMA_VERSION = "deep_context_federation_agent_model_input_v1"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""


def _resolve(path: str, *, base_dir: Path | None) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute() and base_dir is not None:
        candidate = base_dir / candidate
    return candidate.resolve()


def _summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    return {
        "schema_version": payload.get("schema_version"),
        "status": payload.get("status"),
        "ok": payload.get("ok"),
        "summary": dict(summary),
    }


def build_agent_model_input(
    payload: Mapping[str, Any],
    *,
    handoff_path: Path,
    include_prompt: bool = True,
) -> dict[str, Any]:
    """Verify a handoff and release prompt text only when it is safe to model-read."""

    base_dir = handoff_path.expanduser().resolve().parent
    verification = verify_agent_handoff(payload, handoff_path=handoff_path)
    model_handoff = payload.get("model_handoff") if isinstance(payload.get("model_handoff"), Mapping) else {}
    economics = model_handoff.get("token_economics") if isinstance(model_handoff.get("token_economics"), Mapping) else {}
    prompt_source = str(model_handoff.get("model_prompt_source") or "")
    prompt_path = _resolve(prompt_source, base_dir=base_dir) if prompt_source else None

    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, detail: Any = None) -> None:
        checks.append({"id": check_id, "passed": bool(passed), "severity": "error", "detail": detail})

    add("handoff_verification_ok", verification.get("ok") is True, verification.get("status"))
    add("handoff_ok", payload.get("ok") is True, payload.get("ok"))
    add("handoff_status_allows_model_input", payload.get("status") in {"pass_agent_handoff", "warn_agent_handoff"}, payload.get("status"))
    add("model_prompt_source_present", bool(prompt_source), prompt_source)
    add("model_prompt_format_markdown", model_handoff.get("model_prompt_format") == "markdown", model_handoff.get("model_prompt_format"))
    if prompt_path is not None:
        add("model_prompt_file_exists", prompt_path.exists() and prompt_path.is_file(), prompt_path.as_posix())
    else:
        add("model_prompt_file_exists", False, "")

    failed = [row for row in checks if not row["passed"]]
    prompt_text = ""
    prompt_bytes = 0
    prompt_sha256 = ""
    prompt_estimated_tokens = 0
    if not failed and prompt_path is not None:
        prompt_text = _read_text(prompt_path)
        prompt_bytes = prompt_path.stat().st_size if prompt_path.exists() else 0
        prompt_sha256 = _sha256(prompt_text)
        prompt_estimated_tokens = estimate_tokens(prompt_text) if prompt_text else 0
        if not prompt_text:
            failed.append({"id": "model_prompt_text_nonempty", "passed": False, "severity": "error", "detail": prompt_path.as_posix()})

    ok = not failed
    if not include_prompt:
        prompt_text = ""
    prompt_pack = public_prompt_pack(
        prompt_source=prompt_path.as_posix() if prompt_path is not None and ok else "",
        prompt_format="markdown" if ok else "",
        prompt_bytes=prompt_bytes if ok else 0,
        prompt_sha256=prompt_sha256 if ok else "",
        prompt_estimated_tokens=prompt_estimated_tokens if ok else 0,
        prompt_text=prompt_text if ok else "",
    )

    return {
        "schema_version": AGENT_MODEL_INPUT_SCHEMA_VERSION,
        "ok": ok,
        "status": "pass_agent_model_input" if ok else "fail_agent_model_input",
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": utc_now(),
        "source_identity_policy": public_source_identity_policy(audit_provenance_location="verified_handoff_and_prompt_file"),
        "input_ref": handoff_path.expanduser().resolve().as_posix(),
        "prompt_source": prompt_path.as_posix() if prompt_path is not None else "",
        "prompt_format": "markdown" if ok else "",
        "prompt_bytes": prompt_bytes if ok else 0,
        "prompt_sha256": prompt_sha256 if ok else "",
        "prompt_estimated_tokens": prompt_estimated_tokens if ok else 0,
        "prompt_text": prompt_text if ok else "",
        "prompt_pack": prompt_pack,
        "handoff_summary": {
            "schema_version": payload.get("schema_version"),
            "status": payload.get("status"),
            "ok": payload.get("ok"),
            "decision": payload.get("decision") if isinstance(payload.get("decision"), Mapping) else {},
        },
        "verification_summary": _summary(verification),
        "token_economics": dict(economics),
        "checks": checks,
        "errors": failed,
        "safety_boundaries": {
            "authority_effect": "none",
            "no_apply": True,
            "mutation_allowed": False,
            "reads_generated_artifacts_only": True,
            "external_model_calls": False,
            "source_or_authority_mutation": False,
            "prompt_emitted_only_after_verification": True,
            "source_ids_exposed": False,
            "source_identity_collapsed": True,
        },
    }


def markdown_agent_model_input(result: Mapping[str, Any]) -> str:
    lines = [
        "# Deep Context Federation Agent Model Input",
        "",
        f"- Status: `{result.get('status')}`",
        f"- OK: `{result.get('ok')}`",
        f"- Input: `{result.get('input_ref')}`",
        f"- Prompt source: `{result.get('prompt_source')}`",
        f"- Prompt tokens: `{result.get('prompt_estimated_tokens')}`",
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
