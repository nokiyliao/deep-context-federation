"""Public-facing DCF boundary audit for generated artifacts."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from deep_context_federation.builder import utc_now
from deep_context_federation.query import SOURCE_IDENTITY_KEYS

PUBLIC_BOUNDARY_AUDIT_SCHEMA_VERSION = "deep_context_federation_public_boundary_audit_v1"

PUBLIC_SECTION_KEYS = (
    "rows",
    "operator_rows",
    "expansion_plan",
    "recommended_commands",
    "model_handoff",
    "next_reads",
    "artifact_read_plan",
    "read_first",
    "prompt_pack",
    "context_advantage_summary",
)


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _rows(value: object) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, Mapping)]


def _schema(value: Mapping[str, Any]) -> str:
    return str(value.get("schema_version") or "")


def _policy(payload: Mapping[str, Any]) -> dict[str, Any]:
    policy = dict(_mapping(payload.get("source_identity_policy")))
    if policy:
        return policy
    safety = _mapping(payload.get("safety_boundaries"))
    if "source_ids_exposed" in safety or "source_identity_collapsed" in safety:
        return {
            "public_identity": "deep_context_federation",
            "source_ids_exposed": bool(safety.get("source_ids_exposed")),
            "source_identity_collapsed": bool(safety.get("source_identity_collapsed")),
            "policy_source": "safety_boundaries",
        }
    return {}


def _public_sections(payload: Mapping[str, Any]) -> dict[str, Any]:
    sections = {key: payload.get(key) for key in PUBLIC_SECTION_KEYS if key in payload}
    if sections:
        return sections
    return {}


def _identity_paths(value: object, *, path: str = "$", limit: int = 50) -> list[str]:
    found: list[str] = []

    def walk(item: object, current_path: str) -> None:
        if len(found) >= limit:
            return
        if isinstance(item, Mapping):
            for key, child in item.items():
                key_text = str(key)
                next_path = f"{current_path}.{key_text}"
                if key_text in SOURCE_IDENTITY_KEYS:
                    found.append(next_path)
                    if len(found) >= limit:
                        return
                walk(child, next_path)
        elif isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, f"{current_path}[{index}]")
                if len(found) >= limit:
                    return

    walk(value, path)
    return found


def _check(checks: list[dict[str, Any]], check_id: str, ok: bool, detail: Mapping[str, Any] | None = None) -> None:
    checks.append({"id": check_id, "ok": bool(ok), "detail": dict(detail or {})})


def build_public_boundary_audit(
    artifacts: Sequence[tuple[str, Mapping[str, Any]]],
    *,
    require_public_policy: bool = False,
) -> dict[str, Any]:
    """Audit generated outputs for public source-identity leakage."""

    rows: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    public_count = 0
    raw_count = 0

    for label, payload in artifacts:
        policy = _policy(payload)
        source_ids_exposed = policy.get("source_ids_exposed")
        public_declared = source_ids_exposed is False
        raw_declared = source_ids_exposed is True
        sections = _public_sections(payload)
        scan_target = sections if sections else payload
        identity_paths = _identity_paths(scan_target)
        authority_effect = str(payload.get("authority_effect") or "none")
        no_apply = payload.get("no_apply") is not False
        row = {
            "artifact_ref": label,
            "schema_version": _schema(payload),
            "status": str(payload.get("status") or ""),
            "public_boundary_declared": public_declared,
            "raw_source_identity_declared": raw_declared,
            "authority_effect": authority_effect,
            "no_apply": no_apply,
            "source_identity_policy": policy,
            "scanned_section_keys": sorted(sections) if sections else ["<entire_artifact>"],
            "source_identity_path_count": len(identity_paths),
            "source_identity_paths": identity_paths,
        }
        rows.append(row)

        _check(
            checks,
            f"{label}:authority_effect_none",
            authority_effect == "none",
            {"authority_effect": authority_effect},
        )
        _check(
            checks,
            f"{label}:no_apply_not_false",
            no_apply,
            {"no_apply": payload.get("no_apply")},
        )

        if public_declared:
            public_count += 1
            ok = not identity_paths
            _check(checks, f"{label}:public_sections_hide_source_identity", ok, {"source_identity_paths": identity_paths})
            if not ok:
                errors.append(
                    {
                        "id": "public_source_identity_leak",
                        "artifact_ref": label,
                        "schema_version": _schema(payload),
                        "source_identity_paths": identity_paths,
                    }
                )
        elif raw_declared:
            raw_count += 1
            warnings.append(
                {
                    "id": "raw_source_identity_exposed",
                    "artifact_ref": label,
                    "schema_version": _schema(payload),
                    "detail": "Artifact explicitly exposes raw source identity and should be used as audit input, not public model context.",
                }
            )
        else:
            raw_count += 1
            warning = {
                "id": "public_policy_missing",
                "artifact_ref": label,
                "schema_version": _schema(payload),
                "detail": "Artifact does not declare source_identity_policy or safety_boundaries.source_ids_exposed.",
            }
            if require_public_policy:
                errors.append(warning)
            else:
                warnings.append(warning)

    check_errors = [row for row in checks if not row.get("ok")]
    errors.extend(
        {"id": "boundary_check_failed", "check_id": row.get("id"), "detail": row.get("detail") or {}}
        for row in check_errors
    )
    status = "fail_public_boundary_audit" if errors else "warn_public_boundary_audit" if warnings else "pass_public_boundary_audit"
    return {
        "schema_version": PUBLIC_BOUNDARY_AUDIT_SCHEMA_VERSION,
        "ok": not errors,
        "status": status,
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": utc_now(),
        "summary": {
            "artifact_count": len(rows),
            "public_artifact_count": public_count,
            "raw_or_unclassified_artifact_count": raw_count,
            "check_count": len(checks),
            "error_count": len(errors),
            "warning_count": len(warnings),
        },
        "rows": rows,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "safety_boundaries": {
            "authority_effect": "none",
            "no_apply": True,
            "mutation_allowed": False,
            "external_model_calls": False,
            "source_or_authority_mutation": False,
        },
    }


def load_artifacts(paths: Sequence[Path]) -> list[tuple[str, Mapping[str, Any]]]:
    artifacts: list[tuple[str, Mapping[str, Any]]] = []
    for path in paths:
        payload = json.loads(path.expanduser().read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError(f"artifact is not a JSON object: {path}")
        artifacts.append((path.expanduser().resolve().as_posix(), payload))
    return artifacts


def markdown_public_boundary_audit(payload: Mapping[str, Any]) -> str:
    summary = _mapping(payload.get("summary"))
    lines = [
        "# Deep Context Federation Public Boundary Audit",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- OK: `{payload.get('ok')}`",
        f"- Artifacts: `{summary.get('artifact_count')}`",
        f"- Public artifacts: `{summary.get('public_artifact_count')}`",
        f"- Raw/unclassified artifacts: `{summary.get('raw_or_unclassified_artifact_count')}`",
        f"- Errors: `{summary.get('error_count')}`",
        f"- Warnings: `{summary.get('warning_count')}`",
        "",
        "## Rows",
        "",
    ]
    rows = _rows(payload.get("rows"))
    if not rows:
        lines.append("- none")
    for row in rows:
        paths = row.get("source_identity_paths") or []
        lines.append(
            "- `{schema}` public=`{public}` raw=`{raw}` leaks=`{leaks}` ref=`{ref}`".format(
                schema=row.get("schema_version") or "unknown",
                public=row.get("public_boundary_declared"),
                raw=row.get("raw_source_identity_declared"),
                leaks=len(paths) if isinstance(paths, list) else 0,
                ref=row.get("artifact_ref"),
            )
        )
    return "\n".join(lines).rstrip() + "\n"
