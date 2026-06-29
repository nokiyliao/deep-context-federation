"""JSON Schema registry and lightweight contract validation for DCF artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from deep_context_federation.bootstrap import BOOTSTRAP_SCHEMA_VERSION
from deep_context_federation.builder import MANIFEST_SCHEMA
from deep_context_federation.builder import SCHEMA_VERSION
from deep_context_federation.capabilities import CAPABILITIES_SCHEMA_VERSION
from deep_context_federation.compose import COMPOSE_SCHEMA_VERSION
from deep_context_federation.context_pack import CONTEXT_PACK_SCHEMA_VERSION
from deep_context_federation.quality_gate import QUALITY_GATE_POLICY_SCHEMA_VERSION
from deep_context_federation.quality_gate import QUALITY_GATE_SCHEMA_VERSION
from deep_context_federation.query import QUERY_SCHEMA_VERSION
from deep_context_federation.scanner import SCAN_SCHEMA_VERSION
from deep_context_federation.verifier import VERIFY_SCHEMA_VERSION

SCHEMA_REGISTRY_SCHEMA_VERSION = "deep_context_federation_schema_registry_v1"
CONTRACT_VALIDATION_SCHEMA_VERSION = "deep_context_federation_contract_validation_v1"
JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _schema(schema_version: str, title: str, required: list[str], properties: dict[str, Any]) -> dict[str, Any]:
    props = {
        "schema_version": {"type": "string", "const": schema_version},
        **properties,
    }
    return {
        "$schema": JSON_SCHEMA_DIALECT,
        "$id": f"https://deep-context-federation.local/schemas/{schema_version}.json",
        "title": title,
        "type": "object",
        "required": required,
        "additionalProperties": True,
        "properties": props,
    }


def _boundary_props() -> dict[str, Any]:
    return {
        "authority_effect": {"type": "string", "const": "none"},
        "no_apply": {"type": "boolean", "const": True},
    }


def _artifact_schemas() -> dict[str, dict[str, Any]]:
    object_type = {"type": "object"}
    array_type = {"type": "array"}
    return {
        "schema_registry": _schema(
            SCHEMA_REGISTRY_SCHEMA_VERSION,
            "Deep Context Federation schema registry",
            ["schema_version", "status", "authority_effect", "no_apply", "artifact_schemas", "summary"],
            {
                "status": {"type": "string", "const": "ok"},
                **_boundary_props(),
                "artifact_schemas": array_type,
                "summary": object_type,
            },
        ),
        "contract_validation": _schema(
            CONTRACT_VALIDATION_SCHEMA_VERSION,
            "Deep Context Federation contract validation result",
            ["schema_version", "ok", "status", "authority_effect", "no_apply", "checks", "errors"],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string"},
                **_boundary_props(),
                "artifact_kind": {"type": "string"},
                "checks": array_type,
                "errors": array_type,
            },
        ),
        "capabilities": _schema(
            CAPABILITIES_SCHEMA_VERSION,
            "Deep Context Federation capabilities manifest",
            ["schema_version", "status", "authority_effect", "no_apply", "package", "contracts", "commands"],
            {
                "status": {"type": "string", "const": "ok"},
                **_boundary_props(),
                "package": object_type,
                "contracts": object_type,
                "commands": array_type,
                "query_presets": array_type,
                "sql_presets": array_type,
                "safety_boundaries": object_type,
            },
        ),
        "manifest": _schema(
            MANIFEST_SCHEMA,
            "Deep Context Federation input manifest",
            ["schema_version", "authority_boundary", "sources"],
            {
                "authority_boundary": object_type,
                "sources": array_type,
                "metadata": object_type,
            },
        ),
        "federation": _schema(
            SCHEMA_VERSION,
            "Deep Context Federation artifact",
            [
                "schema_version",
                "status",
                "ok",
                "authority_effect",
                "no_apply",
                "sources",
                "entities",
                "edges",
                "conflicts",
                "query_presets",
                "summary",
            ],
            {
                "status": {"type": "string"},
                "ok": {"type": "boolean"},
                **_boundary_props(),
                "mutation_guard": object_type,
                "sources": array_type,
                "entities": array_type,
                "edges": array_type,
                "conflicts": array_type,
                "query_presets": object_type,
                "summary": object_type,
                "outputs": object_type,
            },
        ),
        "repo_scan": _schema(
            SCAN_SCHEMA_VERSION,
            "Deep Context Federation repository scan result",
            ["schema_version", "ok", "status", "authority_effect", "no_apply", "summary", "outputs"],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string"},
                **_boundary_props(),
                "summary": object_type,
                "outputs": object_type,
            },
        ),
        "bootstrap": _schema(
            BOOTSTRAP_SCHEMA_VERSION,
            "Deep Context Federation bootstrap result",
            ["schema_version", "ok", "status", "authority_effect", "no_apply", "scan", "build", "verify", "doctor", "outputs"],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string"},
                **_boundary_props(),
                "scan": object_type,
                "compose": {"type": ["object", "null"]},
                "build": object_type,
                "verify": object_type,
                "doctor": object_type,
                "outputs": object_type,
            },
        ),
        "quality_gate_policy": _schema(
            QUALITY_GATE_POLICY_SCHEMA_VERSION,
            "Deep Context Federation quality gate policy",
            ["schema_version", "authority_effect", "no_apply"],
            {
                **_boundary_props(),
                "policy_id": {"type": "string"},
                "description": {"type": "string"},
                "min_sources": {"type": "integer"},
                "min_entities": {"type": "integer"},
                "min_edges": {"type": "integer"},
                "max_errors": {"type": "integer"},
                "max_warnings": {"type": "integer"},
                "max_duration_seconds": {"type": ["number", "null"]},
                "max_scan_duration_seconds": {"type": ["number", "null"]},
                "require_roles": array_type,
                "require_sources": array_type,
                "require_query_presets": array_type,
                "require_bootstrap_steps": {"type": "boolean"},
            },
        ),
        "quality_gate": _schema(
            QUALITY_GATE_SCHEMA_VERSION,
            "Deep Context Federation quality gate result",
            ["schema_version", "ok", "status", "authority_effect", "no_apply", "policy", "checks", "errors", "summary"],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string"},
                **_boundary_props(),
                "policy": object_type,
                "checks": array_type,
                "errors": array_type,
                "summary": object_type,
            },
        ),
        "manifest_compose": _schema(
            COMPOSE_SCHEMA_VERSION,
            "Deep Context Federation manifest compose result",
            ["schema_version", "ok", "status", "authority_effect", "no_apply", "summary"],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string"},
                **_boundary_props(),
                "summary": object_type,
                "conflicts": array_type,
                "composed_manifest": object_type,
            },
        ),
        "verify": _schema(
            VERIFY_SCHEMA_VERSION,
            "Deep Context Federation verification result",
            ["schema_version", "ok", "status", "checks", "errors"],
            {
                "ok": {"type": "boolean"},
                "status": {"type": "string"},
                "checks": array_type,
                "errors": array_type,
            },
        ),
        "query": _schema(
            QUERY_SCHEMA_VERSION,
            "Deep Context Federation query result",
            ["schema_version", "preset", "status", "row_count", "rows"],
            {
                "preset": {"type": "string"},
                "status": {"type": "string"},
                "row_count": {"type": "integer"},
                "rows": array_type,
                "source_snapshot": object_type,
            },
        ),
        "context_pack": _schema(
            CONTEXT_PACK_SCHEMA_VERSION,
            "Deep Context Federation token-aware context pack",
            [
                "schema_version",
                "status",
                "authority_effect",
                "no_apply",
                "task",
                "token_budget",
                "estimated_tokens",
                "rows",
                "summary",
            ],
            {
                "status": {"type": "string", "const": "ok"},
                **_boundary_props(),
                "task": {"type": "string"},
                "token_budget": {"type": "integer"},
                "estimated_tokens": {"type": "integer"},
                "original_estimated_tokens": {"type": "integer"},
                "estimated_token_savings": {"type": "integer"},
                "compression_ratio": {"type": "number"},
                "rows": array_type,
                "dropped": array_type,
                "summary": object_type,
            },
        ),
    }


def build_schema_registry() -> dict[str, Any]:
    schemas = _artifact_schemas()
    rows = [
        {
            "artifact_kind": artifact_kind,
            "schema_version": schema["properties"]["schema_version"]["const"],
            "json_schema": schema,
        }
        for artifact_kind, schema in sorted(schemas.items())
    ]
    return {
        "schema_version": SCHEMA_REGISTRY_SCHEMA_VERSION,
        "status": "ok",
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": _utc_now(),
        "json_schema_dialect": JSON_SCHEMA_DIALECT,
        "artifact_schemas": rows,
        "summary": {
            "artifact_schema_count": len(rows),
            "artifact_kinds": [row["artifact_kind"] for row in rows],
        },
    }


def schema_for_artifact(artifact_kind: str) -> dict[str, Any]:
    schemas = _artifact_schemas()
    if artifact_kind not in schemas:
        raise ValueError(f"unknown artifact kind {artifact_kind!r}; available={sorted(schemas)}")
    return schemas[artifact_kind]


def artifact_kinds() -> list[str]:
    return sorted(_artifact_schemas())


def infer_artifact_kind(payload: Mapping[str, Any]) -> str | None:
    schema_version = str(payload.get("schema_version") or "")
    for artifact_kind, schema in _artifact_schemas().items():
        expected = str(schema.get("properties", {}).get("schema_version", {}).get("const") or "")
        if schema_version == expected:
            return artifact_kind
    return None


def _matches_type(value: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        return any(_matches_type(value, item) for item in expected)
    if expected == "object":
        return isinstance(value, Mapping)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _check(checks: list[dict[str, Any]], check_id: str, passed: bool, detail: Any = None) -> None:
    checks.append({"id": check_id, "passed": bool(passed), "severity": "error", "detail": detail})


def _validate_subset(schema: Mapping[str, Any], value: Any, path: str, checks: list[dict[str, Any]]) -> None:
    expected_type = schema.get("type")
    if expected_type is not None:
        _check(checks, f"{path}:type", _matches_type(value, expected_type), {"expected": expected_type, "actual": type(value).__name__})
        if not _matches_type(value, expected_type):
            return
    if "const" in schema:
        _check(checks, f"{path}:const", value == schema.get("const"), {"expected": schema.get("const"), "actual": value})
    if "enum" in schema:
        allowed = list(schema.get("enum") or [])
        _check(checks, f"{path}:enum", value in allowed, {"allowed": allowed, "actual": value})
    if not isinstance(value, Mapping):
        return
    required = [str(item) for item in schema.get("required") or []]
    for key in required:
        _check(checks, f"{path}.{key}:required", key in value, {"required": key})
    properties = schema.get("properties") if isinstance(schema.get("properties"), Mapping) else {}
    for key, subschema in properties.items():
        if key in value and isinstance(subschema, Mapping):
            _validate_subset(subschema, value[key], f"{path}.{key}", checks)
    if schema.get("additionalProperties") is False:
        extra = sorted(set(value) - set(properties))
        _check(checks, f"{path}:additionalProperties", not extra, {"extra": extra})


def validate_artifact_contract(payload: Mapping[str, Any], *, artifact_kind: str | None = None) -> dict[str, Any]:
    selected_artifact = artifact_kind or infer_artifact_kind(payload)
    checks: list[dict[str, Any]] = []
    _check(checks, "payload_is_object", isinstance(payload, Mapping), {"actual": type(payload).__name__})
    if not selected_artifact:
        _check(checks, "artifact_kind_inferred", False, {"schema_version": payload.get("schema_version")})
        schema = None
    else:
        _check(checks, "artifact_kind_selected", True, {"artifact_kind": selected_artifact})
        schema = schema_for_artifact(selected_artifact)
    if schema is not None:
        _validate_subset(schema, payload, "$", checks)
    failed = [check for check in checks if not check["passed"]]
    return {
        "schema_version": CONTRACT_VALIDATION_SCHEMA_VERSION,
        "ok": not failed,
        "status": "pass_contract_validation" if not failed else "fail_contract_validation",
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": _utc_now(),
        "artifact_kind": selected_artifact or "",
        "input_schema_version": payload.get("schema_version"),
        "check_count": len(checks),
        "error_count": len(failed),
        "checks": checks,
        "errors": failed,
    }


def markdown_schema_registry(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Deep Context Federation Schema Registry",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Dialect: `{payload.get('json_schema_dialect')}`",
        "",
        "## Artifact Schemas",
        "",
    ]
    for row in payload.get("artifact_schemas") or []:
        if isinstance(row, Mapping):
            lines.append(f"- `{row.get('artifact_kind')}` -> `{row.get('schema_version')}`")
    return "\n".join(lines).rstrip() + "\n"


def markdown_json_schema(schema: Mapping[str, Any], *, artifact_kind: str) -> str:
    lines = [
        "# Deep Context Federation JSON Schema",
        "",
        f"- Artifact: `{artifact_kind}`",
        f"- Schema: `{schema.get('$id')}`",
        f"- Title: `{schema.get('title')}`",
        "",
        "## Required",
        "",
    ]
    for item in schema.get("required") or []:
        lines.append(f"- `{item}`")
    return "\n".join(lines).rstrip() + "\n"


def markdown_contract_validation(result: Mapping[str, Any]) -> str:
    lines = [
        "# Deep Context Federation Contract Validation",
        "",
        f"- Status: `{result.get('status')}`",
        f"- Artifact: `{result.get('artifact_kind')}`",
        f"- Errors: `{result.get('error_count')}`",
        "",
        "## Checks",
        "",
    ]
    for check in result.get("checks") or []:
        if isinstance(check, Mapping):
            state = "pass" if check.get("passed") else "fail"
            lines.append(f"- `{state}` `{check.get('id')}`")
    return "\n".join(lines).rstrip() + "\n"
