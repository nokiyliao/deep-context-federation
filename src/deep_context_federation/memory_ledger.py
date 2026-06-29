"""DCF-native reusable context memory ledger."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from deep_context_federation.agent_context import AGENT_CONTEXT_SCHEMA_VERSION
from deep_context_federation.agent_context_gate import AGENT_CONTEXT_GATE_SCHEMA_VERSION
from deep_context_federation.agent_ci import AGENT_CI_SCHEMA_VERSION
from deep_context_federation.agent_handoff import AGENT_HANDOFF_SCHEMA_VERSION
from deep_context_federation.agent_handoff_verify import AGENT_HANDOFF_VERIFICATION_SCHEMA_VERSION
from deep_context_federation.agent_onboard import AGENT_ONBOARD_SCHEMA_VERSION
from deep_context_federation.agent_ready import AGENT_READY_SCHEMA_VERSION
from deep_context_federation.builder import read_json
from deep_context_federation.builder import utc_now
from deep_context_federation.input_fingerprint import INPUT_FINGERPRINT_SCHEMA_VERSION
from deep_context_federation.workflow_run import WORKFLOW_RUN_SCHEMA_VERSION

MEMORY_LEDGER_SCHEMA_VERSION = "deep_context_federation_memory_ledger_v1"

SCHEMA_KIND = {
    AGENT_CI_SCHEMA_VERSION: "agent_ci",
    AGENT_CONTEXT_SCHEMA_VERSION: "agent_context",
    AGENT_CONTEXT_GATE_SCHEMA_VERSION: "agent_context_gate",
    AGENT_HANDOFF_SCHEMA_VERSION: "agent_handoff",
    AGENT_HANDOFF_VERIFICATION_SCHEMA_VERSION: "agent_handoff_verification",
    AGENT_ONBOARD_SCHEMA_VERSION: "agent_onboard",
    AGENT_READY_SCHEMA_VERSION: "agent_ready",
    INPUT_FINGERPRINT_SCHEMA_VERSION: "input_fingerprint",
    WORKFLOW_RUN_SCHEMA_VERSION: "workflow_run",
}


def _resolve(root: Path, path: Path) -> Path:
    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json_digest(payload: Mapping[str, Any]) -> str:
    text = json.dumps(dict(payload), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return _sha256_text(text)


def _rows(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, Mapping)]


def _strings(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [str(item) for item in value if str(item)]


def _artifact_candidates(*, root: Path, input_dirs: Sequence[Path], input_files: Sequence[Path], max_files: int) -> tuple[list[Path], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    paths: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        resolved = _resolve(root, path)
        key = resolved.as_posix()
        if key in seen:
            return
        seen.add(key)
        paths.append(resolved)

    for path in input_files:
        resolved = _resolve(root, path)
        if resolved.exists() and resolved.is_file():
            add(resolved)
        else:
            warnings.append({"id": "input_file_missing", "path": resolved.as_posix()})

    for path in input_dirs:
        resolved = _resolve(root, path)
        if not resolved.exists() or not resolved.is_dir():
            warnings.append({"id": "input_dir_missing", "path": resolved.as_posix()})
            continue
        for item in sorted(resolved.rglob("*.json")):
            if len(paths) >= max_files:
                warnings.append({"id": "max_files_reached", "max_files": max_files})
                break
            if item.is_file():
                add(item)

    return paths[:max_files], warnings


def _file_ref(path: Path) -> dict[str, Any]:
    exists = path.exists() and path.is_file()
    text = ""
    if exists:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            text = ""
    return {
        "path": path.as_posix(),
        "exists": exists,
        "bytes": path.stat().st_size if exists else 0,
        "sha256": _sha256_text(text) if text else "",
    }


def _summary_ref(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": payload.get("schema_version"),
        "ok": payload.get("ok"),
        "status": payload.get("status"),
    }


def _handoff_row(payload: Mapping[str, Any], *, path: Path) -> dict[str, Any]:
    decision = payload.get("decision") if isinstance(payload.get("decision"), Mapping) else {}
    model = payload.get("model_handoff") if isinstance(payload.get("model_handoff"), Mapping) else {}
    fingerprint = payload.get("input_fingerprint") if isinstance(payload.get("input_fingerprint"), Mapping) else {}
    economics = model.get("token_economics") if isinstance(model.get("token_economics"), Mapping) else {}
    reusable = payload.get("ok") is True and decision.get("handoff_allowed") is True and bool(model.get("model_prompt_source"))
    return {
        "artifact_kind": "agent_handoff",
        "memory_role": "model_handoff",
        "path": path.as_posix(),
        "schema_version": payload.get("schema_version"),
        "status": payload.get("status"),
        "ok": payload.get("ok"),
        "reusable": reusable,
        "task": str(payload.get("task") or ""),
        "targets": _strings(payload.get("targets")),
        "input_fingerprint_digest": str(fingerprint.get("digest") or ""),
        "model_prompt_source": str(model.get("model_prompt_source") or ""),
        "machine_context_source": str(model.get("machine_context_source") or ""),
        "model_prompt_estimated_tokens": int(model.get("model_prompt_estimated_tokens") or 0),
        "machine_context_estimated_tokens": int(model.get("machine_context_estimated_tokens") or 0),
        "estimated_token_savings_percent": float(economics.get("estimated_token_savings_percent") or 0.0),
        "decision_action": str(decision.get("action") or ""),
        "summary_ref": _summary_ref(payload),
        "file_ref": _file_ref(path),
    }


def _ready_row(payload: Mapping[str, Any], *, path: Path) -> dict[str, Any]:
    request_binding = payload.get("request_binding") if isinstance(payload.get("request_binding"), Mapping) else {}
    return {
        "artifact_kind": "agent_ready",
        "memory_role": "agent_launch_gate",
        "path": path.as_posix(),
        "schema_version": payload.get("schema_version"),
        "status": payload.get("status"),
        "ok": payload.get("ok"),
        "reusable": payload.get("ok") is True and bool(payload.get("prompt_source")),
        "task": str(payload.get("task") or ""),
        "targets": _strings(payload.get("targets")),
        "input_fingerprint_digest": str((payload.get("input_freshness") if isinstance(payload.get("input_freshness"), Mapping) else {}).get("current_digest") or ""),
        "model_prompt_source": str(payload.get("prompt_source") or ""),
        "machine_context_source": "",
        "model_prompt_estimated_tokens": int(payload.get("prompt_estimated_tokens") or 0),
        "machine_context_estimated_tokens": 0,
        "estimated_token_savings_percent": 0.0,
        "decision_action": str(payload.get("action_taken") or ""),
        "request_binding_status": request_binding.get("status"),
        "summary_ref": _summary_ref(payload),
        "file_ref": _file_ref(path),
    }


def _onboard_row(payload: Mapping[str, Any], *, path: Path) -> dict[str, Any]:
    return {
        "artifact_kind": "agent_onboard",
        "memory_role": "agent_onboard_capsule",
        "path": path.as_posix(),
        "schema_version": payload.get("schema_version"),
        "status": payload.get("status"),
        "ok": payload.get("ok"),
        "reusable": payload.get("model_input_ready") is True and bool(payload.get("prompt_source")),
        "task": "",
        "targets": [],
        "input_fingerprint_digest": "",
        "model_prompt_source": str(payload.get("prompt_source") or ""),
        "machine_context_source": "",
        "model_prompt_estimated_tokens": int(payload.get("prompt_estimated_tokens") or 0),
        "machine_context_estimated_tokens": 0,
        "estimated_token_savings_percent": 0.0,
        "decision_action": "agent_onboard",
        "summary_ref": _summary_ref(payload),
        "file_ref": _file_ref(path),
    }


def _fingerprint_row(payload: Mapping[str, Any], *, path: Path) -> dict[str, Any]:
    return {
        "artifact_kind": "input_fingerprint",
        "memory_role": "input_freshness_fingerprint",
        "path": path.as_posix(),
        "schema_version": payload.get("schema_version"),
        "status": payload.get("status"),
        "ok": payload.get("ok"),
        "reusable": payload.get("ok") is True and bool(payload.get("digest")),
        "task": "",
        "targets": [],
        "input_fingerprint_digest": str(payload.get("digest") or ""),
        "model_prompt_source": "",
        "machine_context_source": "",
        "model_prompt_estimated_tokens": 0,
        "machine_context_estimated_tokens": 0,
        "estimated_token_savings_percent": 0.0,
        "decision_action": "fingerprint",
        "manifest_count": int(payload.get("manifest_count") or 0),
        "source_count": int(payload.get("source_count") or 0),
        "summary_ref": _summary_ref(payload),
        "file_ref": _file_ref(path),
    }


def _workflow_row(payload: Mapping[str, Any], *, path: Path) -> dict[str, Any]:
    handoff = payload.get("model_handoff") if isinstance(payload.get("model_handoff"), Mapping) else {}
    return {
        "artifact_kind": "workflow_run",
        "memory_role": "workflow_context_capsule",
        "path": path.as_posix(),
        "schema_version": payload.get("schema_version"),
        "status": payload.get("status"),
        "ok": payload.get("ok"),
        "reusable": payload.get("ok") is True,
        "task": str(payload.get("task") or ""),
        "targets": _strings(payload.get("targets")),
        "input_fingerprint_digest": "",
        "model_prompt_source": "",
        "machine_context_source": "",
        "model_prompt_estimated_tokens": int(payload.get("prompt_estimated_tokens") or 0),
        "machine_context_estimated_tokens": 0,
        "estimated_token_savings_percent": 0.0,
        "decision_action": str(handoff.get("decision") or ""),
        "summary_ref": _summary_ref(payload),
        "file_ref": _file_ref(path),
    }


def _generated_context_row(payload: Mapping[str, Any], *, path: Path, artifact_kind: str, memory_role: str) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    return {
        "artifact_kind": artifact_kind,
        "memory_role": memory_role,
        "path": path.as_posix(),
        "schema_version": payload.get("schema_version"),
        "status": payload.get("status"),
        "ok": payload.get("ok"),
        "reusable": payload.get("ok") is True,
        "task": str(payload.get("task") or ""),
        "targets": _strings(payload.get("targets")),
        "input_fingerprint_digest": "",
        "model_prompt_source": str((payload.get("model_handoff") if isinstance(payload.get("model_handoff"), Mapping) else {}).get("model_prompt_source") or ""),
        "machine_context_source": str(payload.get("input_ref") or ""),
        "model_prompt_estimated_tokens": int(payload.get("prompt_estimated_tokens") or summary.get("prompt_estimated_tokens") or 0),
        "machine_context_estimated_tokens": int(summary.get("selected_estimated_tokens") or 0),
        "estimated_token_savings_percent": 0.0,
        "decision_action": str(payload.get("decision") or payload.get("action") or ""),
        "summary_ref": _summary_ref(payload),
        "file_ref": _file_ref(path),
    }


def _row_from_payload(payload: Mapping[str, Any], *, path: Path) -> dict[str, Any] | None:
    schema = str(payload.get("schema_version") or "")
    if schema == AGENT_CI_SCHEMA_VERSION:
        return _generated_context_row(payload, path=path, artifact_kind="agent_ci", memory_role="agent_continuation_decision")
    if schema == AGENT_CONTEXT_SCHEMA_VERSION:
        return _generated_context_row(payload, path=path, artifact_kind="agent_context", memory_role="machine_context_bundle")
    if schema == AGENT_CONTEXT_GATE_SCHEMA_VERSION:
        return _generated_context_row(payload, path=path, artifact_kind="agent_context_gate", memory_role="context_gate_evidence")
    if schema == AGENT_HANDOFF_SCHEMA_VERSION:
        return _handoff_row(payload, path=path)
    if schema == AGENT_HANDOFF_VERIFICATION_SCHEMA_VERSION:
        return _generated_context_row(payload, path=path, artifact_kind="agent_handoff_verification", memory_role="handoff_verification_evidence")
    if schema == AGENT_READY_SCHEMA_VERSION:
        return _ready_row(payload, path=path)
    if schema == AGENT_ONBOARD_SCHEMA_VERSION:
        return _onboard_row(payload, path=path)
    if schema == INPUT_FINGERPRINT_SCHEMA_VERSION:
        return _fingerprint_row(payload, path=path)
    if schema == WORKFLOW_RUN_SCHEMA_VERSION:
        return _workflow_row(payload, path=path)
    return None


def build_memory_ledger(
    *,
    root: Path,
    input_dirs: Sequence[Path] = (),
    input_files: Sequence[Path] = (),
    max_files: int = 500,
) -> dict[str, Any]:
    """Materialize reusable DCF context artifacts into one native memory ledger."""

    root = root.expanduser().resolve()
    dirs = list(input_dirs) if input_dirs else [Path(".dcf")]
    paths, warnings = _artifact_candidates(root=root, input_dirs=dirs, input_files=input_files, max_files=max_files)
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    ignored_count = 0
    for path in paths:
        payload = read_json(path)
        if not isinstance(payload, Mapping) or not payload:
            ignored_count += 1
            continue
        row = _row_from_payload(payload, path=path)
        if row is None:
            ignored_count += 1
            continue
        rows.append(row)

    rows.sort(key=lambda item: (str(item.get("artifact_kind") or ""), str(item.get("path") or "")))
    reusable_rows = [row for row in rows if row.get("reusable") is True]
    by_kind = Counter(str(row.get("artifact_kind") or "") for row in rows)
    by_task = Counter(str(row.get("task") or "") for row in rows if row.get("task"))
    fingerprint_digests = sorted({str(row.get("input_fingerprint_digest") or "") for row in rows if row.get("input_fingerprint_digest")})
    reuse_index = [
        {
            "key": _json_digest(
                {
                    "task": row.get("task"),
                    "targets": row.get("targets"),
                    "fingerprint": row.get("input_fingerprint_digest"),
                    "prompt": row.get("model_prompt_source"),
                }
            ),
            "artifact_kind": row.get("artifact_kind"),
            "memory_role": row.get("memory_role"),
            "path": row.get("path"),
            "task": row.get("task"),
            "targets": row.get("targets"),
            "input_fingerprint_digest": row.get("input_fingerprint_digest"),
            "model_prompt_source": row.get("model_prompt_source"),
            "estimated_token_savings_percent": row.get("estimated_token_savings_percent"),
        }
        for row in reusable_rows
    ]
    status = "pass_memory_ledger" if rows else "warn_memory_ledger"
    if not rows:
        warnings.append({"id": "no_memory_rows", "detail": "No reusable DCF memory artifacts found in selected inputs."})
    return {
        "schema_version": MEMORY_LEDGER_SCHEMA_VERSION,
        "ok": not errors,
        "status": status,
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": utc_now(),
        "root": root.as_posix(),
        "inputs": {
            "input_dirs": [_resolve(root, path).as_posix() for path in dirs],
            "input_files": [_resolve(root, path).as_posix() for path in input_files],
            "max_files": int(max_files),
        },
        "summary": {
            "scanned_json_count": len(paths),
            "ignored_json_count": ignored_count,
            "memory_row_count": len(rows),
            "reusable_row_count": len(reusable_rows),
            "artifact_kind_counts": dict(sorted(by_kind.items())),
            "task_count": len(by_task),
            "input_fingerprint_digest_count": len(fingerprint_digests),
            "warning_count": len(warnings),
            "error_count": len(errors),
        },
        "rows": rows,
        "reuse_index": reuse_index,
        "input_fingerprint_digests": fingerprint_digests,
        "warnings": warnings,
        "errors": errors,
        "safety_boundaries": {
            "authority_effect": "none",
            "no_apply": True,
            "mutation_allowed": False,
            "reads_generated_dcf_artifacts_only": True,
            "source_or_authority_mutation": False,
            "external_tool_identity_required": False,
            "external_model_calls": False,
        },
    }


def markdown_memory_ledger(payload: Mapping[str, Any]) -> str:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    lines = [
        "# DCF Memory Ledger",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- OK: `{payload.get('ok')}`",
        f"- Memory rows: `{summary.get('memory_row_count', 0)}`",
        f"- Reusable rows: `{summary.get('reusable_row_count', 0)}`",
        f"- Fingerprints: `{summary.get('input_fingerprint_digest_count', 0)}`",
        "",
        "## Reuse Index",
    ]
    for row in payload.get("reuse_index") or []:
        if isinstance(row, Mapping):
            lines.append(
                "- `{key}` kind=`{kind}` task=`{task}` prompt=`{prompt}`".format(
                    key=row.get("key"),
                    kind=row.get("artifact_kind"),
                    task=row.get("task"),
                    prompt=row.get("model_prompt_source"),
                )
            )
    if not payload.get("reuse_index"):
        lines.append("- none")
    lines.extend(["", "## Warnings"])
    warnings = _rows(payload.get("warnings"))
    if warnings:
        for row in warnings:
            lines.append(f"- `{row.get('id')}` detail=`{row}`")
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"
