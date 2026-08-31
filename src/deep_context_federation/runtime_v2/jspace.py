"""Action-scoped J-Space contract compilation for DCF v2.

This module consumes one immutable DCF generation and emits one immutable
contract. It deliberately does not call the diagnostic status path or refresh
the generation while compiling an action.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import tempfile
from pathlib import Path
from typing import Any

JSPACE_SCHEMA_VERSION = "jspace_contract_v2"
JSPACE_AUTHORIZATION_SCHEMA_VERSION = "jspace_authorization_v1"
JSPACE_EXPANSION_ERROR = "JSPACE_EXPANSION_REQUIRED"
TASK_CONTEXT_CAPSULE_SCHEMA_VERSION = "task_context_capsule_v1"
_BASE_REQUIRED_CAPABILITIES = ("surface-map", "verifier-gates")
_DEFAULT_DENIED_OPERATIONS = ("network", "install", "system_mutation")
_PATH_OPERATIONS = frozenset({"read", "create", "modify", "delete"})
_COMMAND_EFFECTS = frozenset({*_PATH_OPERATIONS, *_DEFAULT_DENIED_OPERATIONS})
_MAX_CONTEXT_SUMMARY_CHARS = 32_000
_MAX_EVIDENCE_REFS = 64


class JSpaceCompileError(ValueError):
    """The first deterministic predicate that prevents contract compilation."""

    def __init__(self, error_code: str, message: str, *, blocked: bool = False) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.blocked = blocked


def _value(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _strings(value: Any, *, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise JSpaceCompileError(
            "JSPACE_ACTION_SHAPE_INVALID", f"{field} must be a list of strings"
        )
    return [item.strip() for item in value if item.strip()]


def _capability(capability_rows: dict[str, Any], capability_id: str) -> Any:
    row = capability_rows.get(capability_id)
    if row is None:
        raise JSpaceCompileError(
            "JSPACE_REQUIRED_CAPABILITY_MISSING",
            f"required capability is missing: {capability_id}",
            blocked=True,
        )
    for key in ("projection_status", "domain_verdict", "freshness_status"):
        value = str(_value(row, key, ""))
        expected = "current" if key == "freshness_status" else "pass"
        if value != expected:
            raise JSpaceCompileError(
                "JSPACE_REQUIRED_CAPABILITY_NOT_CURRENT",
                f"required capability {capability_id} has {key}={value!r}, expected {expected!r}",
                blocked=True,
            )
    return _value(row, "data", {})


def _required_domain_bindings(
    snapshot: Any,
    capability_rows: dict[str, Any],
    required_capabilities: list[str],
) -> dict[str, dict[str, Any]]:
    source_fingerprints = _value(snapshot, "source_fingerprints", {})
    if not isinstance(source_fingerprints, dict):
        raise JSpaceCompileError(
            "JSPACE_SOURCE_FINGERPRINTS_INVALID",
            "DCF generation source_fingerprints must be an object",
            blocked=True,
        )
    bindings: dict[str, dict[str, Any]] = {}
    for capability_id in required_capabilities:
        row = capability_rows.get(capability_id)
        required_domains = _value(row, "required_domains", None)
        if not isinstance(required_domains, list) or any(
            not isinstance(domain, str) or not domain.strip() for domain in required_domains
        ):
            raise JSpaceCompileError(
                "JSPACE_REQUIRED_DOMAINS_INVALID",
                f"required capability {capability_id} has invalid required_domains",
                blocked=True,
            )
        normalized_domains = sorted(set(required_domains))
        domain_fingerprints: dict[str, str] = {}
        for domain in normalized_domains:
            fingerprint = source_fingerprints.get(domain)
            if not isinstance(fingerprint, str) or not fingerprint:
                raise JSpaceCompileError(
                    "JSPACE_REQUIRED_DOMAIN_FINGERPRINT_MISSING",
                    f"required capability {capability_id} has no fingerprint for domain {domain}",
                    blocked=True,
                )
            domain_fingerprints[domain] = fingerprint
        bindings[capability_id] = {
            "required_domains": normalized_domains,
            "source_fingerprints": domain_fingerprints,
        }
    return bindings


def _surface(surface_data: dict[str, Any], surface_id: str) -> dict[str, Any]:
    rows = surface_data.get("surfaces")
    if not isinstance(rows, list):
        raise JSpaceCompileError(
            "JSPACE_SURFACE_DATA_INVALID", "surface-map surfaces must be a list"
        )
    for row in rows:
        if isinstance(row, dict) and str(row.get("surface_id", "")) == surface_id:
            return row
    raise JSpaceCompileError(
        "JSPACE_SURFACE_NOT_FOUND", f"surface is not present in surface-map: {surface_id}"
    )


def _scope_is_within_surface(requested: str, allowed: str) -> bool:
    if requested == allowed:
        return True
    if allowed.endswith("/**"):
        root = allowed[:-3].rstrip("/")
        return bool(root) and requested.startswith(f"{root}/")
    return False


def _validate_write_scopes(surface: dict[str, Any], write_scopes: list[str]) -> None:
    allowed_scopes = _strings(
        surface.get("allowed_write_scopes", []), field="surface.allowed_write_scopes"
    )
    for requested in write_scopes:
        if requested.startswith("/") or ".." in Path(requested).parts:
            raise JSpaceCompileError(
                "JSPACE_WRITE_SCOPE_OUTSIDE_SURFACE",
                f"write scope must be repo-relative and traversal-free: {requested}",
                blocked=True,
            )
        if not any(_scope_is_within_surface(requested, allowed) for allowed in allowed_scopes):
            raise JSpaceCompileError(
                "JSPACE_WRITE_SCOPE_OUTSIDE_SURFACE",
                f"write scope is not contained by surface {surface['surface_id']}: {requested}",
                blocked=True,
            )


def _validate_read_scopes(surface: dict[str, Any], read_scopes: list[str]) -> None:
    allowed_scopes = _strings(surface.get("logical_ref", []), field="surface.logical_ref")
    for requested in read_scopes:
        if requested.startswith("/") or ".." in Path(requested).parts:
            raise JSpaceCompileError(
                "JSPACE_READ_SCOPE_OUTSIDE_SURFACE",
                f"read scope must be repo-relative and traversal-free: {requested}",
                blocked=True,
            )
        if not any(_scope_is_within_surface(requested, allowed) for allowed in allowed_scopes):
            raise JSpaceCompileError(
                "JSPACE_READ_SCOPE_OUTSIDE_SURFACE",
                f"read scope is not contained by surface {surface['surface_id']}: {requested}",
                blocked=True,
            )


def _validate_relative_path(value: str, *, field: str) -> str:
    normalized = value.strip().replace("\\", "/")
    if not normalized or normalized.startswith("/") or ".." in Path(normalized).parts:
        raise JSpaceCompileError(
            "JSPACE_TARGET_INVALID",
            f"{field} must be repo-relative and traversal-free: {value}",
            blocked=True,
        )
    return normalized


def _path_is_within_scope(path: str, scope: str) -> bool:
    if path == scope:
        return True
    if scope.endswith("/**"):
        root = scope[:-3].rstrip("/")
        return bool(root) and (path == root or path.startswith(f"{root}/"))
    return False


def _declared_targets(action: dict[str, Any], write_scopes: list[str]) -> list[str]:
    targets = sorted(
        {
            _validate_relative_path(target, field="target_paths")
            for target in _strings(action.get("target_paths", []), field="target_paths")
        }
    )
    for target in targets:
        if any(character in target for character in "*?[]"):
            raise JSpaceCompileError(
                "JSPACE_TARGET_INVALID",
                f"declared targets must be exact paths without wildcards: {target}",
                blocked=True,
            )
        if write_scopes and not any(_path_is_within_scope(target, scope) for scope in write_scopes):
            raise JSpaceCompileError(
                "JSPACE_TARGET_OUTSIDE_WRITE_SCOPE",
                f"declared target is not contained by a write scope: {target}",
                blocked=True,
            )
    return targets


def _exact_argv(command: str, *, field: str) -> list[str]:
    if not command.strip() or any(character in command for character in "\x00\r\n"):
        raise JSpaceCompileError(
            "JSPACE_COMMAND_TEMPLATE_INVALID", f"{field} must be one bounded command"
        )
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>()")
        lexer.whitespace_split = True
        lexer.commenters = ""
        argv = list(lexer)
    except ValueError as exc:
        raise JSpaceCompileError(
            "JSPACE_COMMAND_TEMPLATE_INVALID", f"{field} is not valid shell syntax: {exc}"
        ) from exc
    shell_operators = set(";&|<>()")
    if not argv or any(
        (token and set(token) <= shell_operators) or "$" in token or "`" in token
        for token in argv
    ):
        raise JSpaceCompileError(
            "JSPACE_COMMAND_TEMPLATE_UNSAFE",
            f"{field} may not contain shell control, expansion, redirection, or substitution",
            blocked=True,
        )
    return argv


def _command_templates(
    action: dict[str, Any],
    *,
    surface: dict[str, Any],
    allowed_operations: list[str],
    denied_operations: list[str],
    declared_targets: list[str],
) -> list[dict[str, Any]]:
    raw = action.get("command_templates")
    if raw is None:
        # Input compatibility only: legacy prefixes are lowered to exact argv templates.
        raw = action.get("command_prefixes")
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise JSpaceCompileError(
            "JSPACE_ACTION_SHAPE_INVALID", "command_templates must be a list"
        )

    templates: list[dict[str, Any]] = []
    declared_commands = [
        *_strings(
            surface.get("allowed_command_templates", []),
            field="surface.allowed_command_templates",
        ),
        *_strings(surface.get("required_verifiers", []), field="surface.required_verifiers"),
    ]
    declared_argv = {
        tuple(_exact_argv(command, field="surface.command_allowlist"))
        for command in declared_commands
    }
    seen_argv: set[tuple[str, ...]] = set()
    for index, item in enumerate(raw):
        field = f"command_templates[{index}]"
        if isinstance(item, str):
            argv = _exact_argv(item, field=field)
            effects = ["read"]
            raw_targets: list[Any] = []
        elif isinstance(item, dict):
            raw_argv = item.get("argv")
            if raw_argv is not None:
                argv = _strings(raw_argv, field=f"{field}.argv")
                if not argv:
                    raise JSpaceCompileError(
                        "JSPACE_COMMAND_TEMPLATE_INVALID", f"{field}.argv must not be empty"
                    )
                if any(any(character in token for character in "\x00\r\n") for token in argv):
                    raise JSpaceCompileError(
                        "JSPACE_COMMAND_TEMPLATE_INVALID", f"{field}.argv contains control bytes"
                    )
            else:
                command = item.get("command")
                if not isinstance(command, str):
                    raise JSpaceCompileError(
                        "JSPACE_COMMAND_TEMPLATE_INVALID",
                        f"{field} requires command or argv",
                    )
                argv = _exact_argv(command, field=f"{field}.command")
            effects = sorted(set(_strings(item.get("effects", ["read"]), field=f"{field}.effects")))
            raw_targets = item.get("targets", [])
            if not isinstance(raw_targets, list):
                raise JSpaceCompileError(
                    "JSPACE_COMMAND_TEMPLATE_INVALID", f"{field}.targets must be a list"
                )
        else:
            raise JSpaceCompileError(
                "JSPACE_COMMAND_TEMPLATE_INVALID", f"{field} must be a string or object"
            )

        argv_key = tuple(argv)
        if argv_key not in declared_argv:
            raise JSpaceCompileError(
                "JSPACE_COMMAND_NOT_DECLARED",
                f"command is not declared by surface {surface['surface_id']}: {' '.join(argv)}",
                blocked=True,
            )
        if argv_key in seen_argv:
            raise JSpaceCompileError(
                "JSPACE_COMMAND_TEMPLATE_DUPLICATE",
                f"duplicate exact argv template: {' '.join(argv)}",
            )
        seen_argv.add(argv_key)
        if not effects or any(effect not in _COMMAND_EFFECTS for effect in effects):
            raise JSpaceCompileError(
                "JSPACE_COMMAND_EFFECT_INVALID", f"{field}.effects contains an unknown effect"
            )
        for effect in effects:
            if effect in denied_operations or (
                effect in _PATH_OPERATIONS and effect not in allowed_operations
            ):
                raise JSpaceCompileError(
                    "JSPACE_COMMAND_EFFECT_DENIED",
                    f"command effect {effect} is not admitted: {' '.join(argv)}",
                    blocked=True,
                )

        targets: list[dict[str, Any]] = []
        for target_index, target in enumerate(raw_targets):
            if not isinstance(target, dict):
                raise JSpaceCompileError(
                    "JSPACE_COMMAND_TEMPLATE_INVALID",
                    f"{field}.targets[{target_index}] must be an object",
                )
            operation = str(target.get("operation", "")).strip()
            path = target.get("path")
            argv_index = target.get("argv_index")
            if (
                operation not in _PATH_OPERATIONS
                or not isinstance(path, str)
                or not isinstance(argv_index, int)
                or isinstance(argv_index, bool)
                or argv_index < 0
                or argv_index >= len(argv)
            ):
                raise JSpaceCompileError(
                    "JSPACE_COMMAND_TEMPLATE_INVALID",
                    f"{field}.targets[{target_index}] requires operation, path, and valid argv_index",
                )
            normalized_path = _validate_relative_path(
                path, field=f"{field}.targets[{target_index}].path"
            )
            if operation not in effects:
                raise JSpaceCompileError(
                    "JSPACE_COMMAND_TARGET_EFFECT_MISMATCH",
                    f"command target operation {operation} is absent from effects",
                )
            if argv[argv_index] != normalized_path:
                raise JSpaceCompileError(
                    "JSPACE_COMMAND_TARGET_ARGV_MISMATCH",
                    f"command target path must equal argv[{argv_index}]",
                    blocked=True,
                )
            if operation != "read" and normalized_path not in declared_targets:
                raise JSpaceCompileError(
                    "JSPACE_COMMAND_TARGET_UNDECLARED",
                    f"command mutation target is not declared: {normalized_path}",
                    blocked=True,
                )
            targets.append(
                {"operation": operation, "path": normalized_path, "argv_index": argv_index}
            )

        mutation_effects = set(effects).intersection({"create", "modify", "delete"})
        targeted_mutation_effects = {
            target["operation"] for target in targets if target["operation"] != "read"
        }
        if mutation_effects != targeted_mutation_effects:
            raise JSpaceCompileError(
                "JSPACE_COMMAND_MUTATION_TARGET_MISSING",
                f"every command mutation effect requires an exact target: {' '.join(argv)}",
                blocked=True,
            )
        templates.append({"argv": argv, "effects": effects, "targets": targets})

    return sorted(templates, key=_canonical_bytes)


def _focused_verifiers(
    authority_data: dict[str, Any],
    verifier_data: dict[str, Any],
    surface: dict[str, Any],
    requested: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sources = [
        authority_data.get("verifier_gates", []),
        verifier_data.get("verifier_gates", []),
    ]
    for command in requested:
        match = next(
            (
                row
                for source in sources
                for row in source
                if isinstance(row, dict)
                and str(row.get("surface_id", "")) == str(surface["surface_id"])
                and str(row.get("command", "")) == command
            ),
            None,
        )
        if match is None:
            raise JSpaceCompileError(
                "JSPACE_FOCUSED_VERIFIER_MISSING",
                f"focused verifier is not evidenced for surface {surface['surface_id']}: {command}",
                blocked=True,
            )
        rows.append(
            {
                "verifier_id": str(match.get("verifier_id", "")),
                "surface_id": str(match.get("surface_id", "")),
                "command": command,
                "declared": bool(match.get("declared", False)),
                "result_status": str(match.get("result_status", "unverified")),
                "result_artifact_ids": [str(item) for item in match.get("result_artifact_ids", [])],
            }
        )
    return rows


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _semantic_digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _authorization_payload(payload: dict[str, Any]) -> dict[str, Any]:
    generation = payload.get("dcf_generation", {})
    if not isinstance(generation, dict):
        generation = {}
    return {
        "schema_version": JSPACE_AUTHORIZATION_SCHEMA_VERSION,
        "repo_root": payload.get("repo_root"),
        "required_domain_bindings": generation.get("required_domain_bindings"),
        "matched_surface_ids": payload.get("matched_surface_ids"),
        "read_scopes": payload.get("read_scopes"),
        "write_scopes": payload.get("write_scopes"),
        "allowed_operations": payload.get("allowed_operations"),
        "denied_operations": payload.get("denied_operations"),
        "command_templates": payload.get("command_templates"),
        "declared_targets": payload.get("declared_targets"),
        "expansion": payload.get("expansion"),
    }


def _authorization_digest(payload: dict[str, Any]) -> str:
    return _semantic_digest(_authorization_payload(payload))


def _required_fingerprint_map(
    bindings: dict[str, dict[str, Any]],
) -> dict[str, str]:
    required: dict[str, str] = {}
    for capability_id, binding in bindings.items():
        fingerprints = binding.get("source_fingerprints")
        if not isinstance(fingerprints, dict):
            raise JSpaceCompileError(
                "JSPACE_REQUIRED_DOMAIN_FINGERPRINT_MISSING",
                f"required capability {capability_id} has invalid source_fingerprints",
                blocked=True,
            )
        for domain, fingerprint in fingerprints.items():
            previous = required.setdefault(str(domain), str(fingerprint))
            if previous != fingerprint:
                raise JSpaceCompileError(
                    "JSPACE_REQUIRED_DOMAIN_FINGERPRINT_CONFLICT",
                    f"required domain {domain} has conflicting fingerprints",
                    blocked=True,
                )
    return dict(sorted(required.items()))


def _current_required_fingerprints(runtime: Any, expected: dict[str, str]) -> dict[str, str]:
    reader = getattr(runtime, "current_domain_fingerprints", None)
    if not callable(reader):
        raise JSpaceCompileError(
            "JSPACE_FRESHNESS_READER_MISSING",
            "DCF runtime cannot produce an action-scoped freshness token",
            blocked=True,
        )
    current = reader(sorted(expected))
    if not isinstance(current, dict):
        raise JSpaceCompileError(
            "JSPACE_FRESHNESS_TOKEN_INVALID",
            "DCF action-scoped freshness token must be an object",
            blocked=True,
        )
    normalized = {str(domain): str(value) for domain, value in current.items()}
    if normalized != expected:
        changed = sorted(
            domain for domain in set(expected).union(normalized) if expected.get(domain) != normalized.get(domain)
        )
        raise JSpaceCompileError(
            "JSPACE_REQUIRED_DOMAIN_CHANGED",
            f"required DCF domains changed during compilation: {','.join(changed)}",
            blocked=True,
        )
    return normalized


def compile_jspace_contract(
    runtime: Any, *, surface_id: str, action: dict[str, Any]
) -> dict[str, Any]:
    """Compile one action from the current immutable generation.

    The immutable snapshot supplies provenance while the read-only capability
    overlay supplies current action-scoped freshness. No global readiness
    calculation or generation refresh is part of this path.
    """

    if not isinstance(action, dict):
        raise JSpaceCompileError("JSPACE_ACTION_SHAPE_INVALID", "action evidence must be an object")
    snapshot, _, _ = runtime.store.load_current(verify_file_hashes=True)
    _, capability_rows, _ = runtime.capability_views(
        include_data=True,
        snapshot=snapshot,
    )
    requires_authority_lineage = action.get("requires_authority_lineage", False)
    if not isinstance(requires_authority_lineage, bool):
        raise JSpaceCompileError(
            "JSPACE_ACTION_SHAPE_INVALID",
            "requires_authority_lineage must be a boolean",
        )
    surface_data = _capability(capability_rows, "surface-map")
    verifier_data = _capability(capability_rows, "verifier-gates")
    authority_data: dict[str, Any] = {}
    required_capabilities = list(_BASE_REQUIRED_CAPABILITIES)
    if requires_authority_lineage:
        authority_data = _capability(capability_rows, "authority-lineage")
        required_capabilities.append("authority-lineage")
    surface = _surface(surface_data, surface_id)

    operations = _strings(action.get("operations", ["read"]), field="operations")
    if not operations:
        raise JSpaceCompileError(
            "JSPACE_OPERATION_MISSING", "action must declare at least one operation"
        )
    additional_allowed = _strings(action.get("allowed_operations"), field="allowed_operations")
    allowed = sorted(set(operations + additional_allowed))
    known_operations = {"read", "create", "modify", "delete", "command"}
    unknown = [operation for operation in allowed if operation not in known_operations]
    if unknown:
        raise JSpaceCompileError(
            "JSPACE_UNKNOWN_OPERATION",
            f"action declares unknown operations: {','.join(unknown)}",
        )
    if bool(surface.get("read_only", False)) and any(operation != "read" for operation in allowed):
        raise JSpaceCompileError(
            "JSPACE_READ_ONLY_SURFACE",
            f"surface {surface_id} is read-only but action requests mutation",
            blocked=True,
        )

    read_scopes = sorted(
        {
            _validate_relative_path(scope, field="read_scopes")
            for scope in _strings(action.get("read_scopes"), field="read_scopes")
        }
    )
    write_scopes = sorted(
        {
            _validate_relative_path(scope, field="write_scopes")
            for scope in _strings(action.get("write_scopes"), field="write_scopes")
        }
    )
    if "read" in allowed and not read_scopes:
        raise JSpaceCompileError(
            "JSPACE_READ_SCOPE_MISSING", "read action must declare read_scopes"
        )
    if "read" in allowed:
        _validate_read_scopes(surface, read_scopes)
    if (
        any(operation in {"create", "modify", "delete"} for operation in allowed)
        and not write_scopes
    ):
        raise JSpaceCompileError(
            "JSPACE_WRITE_SCOPE_MISSING", "mutation action has no write_scopes"
        )
    if any(operation in {"create", "modify", "delete"} for operation in allowed):
        _validate_write_scopes(surface, write_scopes)
    declared_targets = _declared_targets(action, write_scopes)
    if any(operation in {"create", "modify", "delete"} for operation in allowed) and not declared_targets:
        raise JSpaceCompileError(
            "JSPACE_DECLARED_TARGET_MISSING",
            "mutation actions require at least one exact declared target",
            blocked=True,
        )

    denied = sorted(
        {
            *_DEFAULT_DENIED_OPERATIONS,
            *_strings(action.get("denied_operations"), field="denied_operations"),
        }
    )
    command_templates = _command_templates(
        action,
        surface=surface,
        allowed_operations=allowed,
        denied_operations=denied,
        declared_targets=declared_targets,
    )
    if "command" in allowed and not command_templates:
        raise JSpaceCompileError(
            "JSPACE_COMMAND_TEMPLATE_MISSING", "command action must declare command_templates"
        )
    if command_templates and "command" not in allowed:
        raise JSpaceCompileError(
            "JSPACE_COMMAND_OPERATION_MISSING",
            "command_templates require an explicit command operation grant",
        )
    requested_verifiers = _strings(
        action.get("focused_verifiers", surface.get("required_verifiers", [])),
        field="focused_verifiers",
    )
    focused_verifiers = _focused_verifiers(
        authority_data, verifier_data, surface, requested_verifiers
    )

    repo = snapshot.repo
    snapshot_root = Path(str(repo.get("root") or "")).resolve()
    runtime_root = Path(runtime.repo_root).resolve()
    requested_root = Path(str(action.get("repo_root") or snapshot_root)).resolve()
    if snapshot_root != runtime_root or requested_root != snapshot_root:
        raise JSpaceCompileError(
            "JSPACE_ROOT_EVIDENCE_MISMATCH",
            "action, DCF snapshot, and runtime roots must identify the same repository",
            blocked=True,
        )
    repo_root = str(snapshot_root)
    required_domain_bindings = _required_domain_bindings(
        snapshot,
        capability_rows,
        required_capabilities,
    )
    expected_fingerprints = _required_fingerprint_map(required_domain_bindings)
    current_fingerprints = _current_required_fingerprints(runtime, expected_fingerprints)
    dcf_generation = {
        "repo_root": repo_root,
        "generation_id": snapshot.generation_id,
        "generated_at": snapshot.generated_at,
        "input_fingerprint": snapshot.input_fingerprint,
        "repo_head": str(repo.get("head_commit", "")),
        "worktree_fingerprint": str(repo.get("worktree_fingerprint", "")),
        "required_capabilities": required_capabilities,
        "required_domain_bindings": required_domain_bindings,
        "action_freshness": {
            "required_domains": sorted(expected_fingerprints),
            "source_fingerprints": current_fingerprints,
            "token_sha256": _semantic_digest(current_fingerprints),
        },
    }
    payload: dict[str, Any] = {
        "schema_version": JSPACE_SCHEMA_VERSION,
        "repo_root": repo_root,
        "dcf_generation": dcf_generation,
        "provenance": {
            "surface_contract": str(surface_data.get("contract_path", "")),
            "matched_surface_ids": [surface_id],
            "authority_contract": str(
                authority_data.get("authority_contract") or surface.get("source_contract", "")
            ),
        },
        "matched_surface_ids": [surface_id],
        "read_scopes": read_scopes,
        "write_scopes": write_scopes,
        "allowed_operations": allowed,
        "denied_operations": denied,
        "command_templates": command_templates,
        "focused_verifiers": focused_verifiers,
        "declared_targets": declared_targets,
        "expansion": {
            "mode": "exact_target_only",
            "error_code": JSPACE_EXPANSION_ERROR,
            "mutation_on_expansion": False,
        },
    }
    payload["authorization_semantic_sha256"] = _authorization_digest(payload)
    payload["content_sha256"] = _semantic_digest(payload)
    return payload


def compile_task_context_capsule(
    jspace_contract: dict[str, Any], *, action: dict[str, Any]
) -> dict[str, Any]:
    """Bind one bounded mission context to one already-compiled J-Space contract.

    The capsule is provider-independent. It contains only the task facts needed
    by Tura reasoning and verification; path/command authority remains in the
    separately hashed J-Space contract.
    """

    canonical_contract_bytes(jspace_contract)
    mission = action.get("mission")
    if not isinstance(mission, dict):
        raise JSpaceCompileError("TASK_CONTEXT_MISSION_MISSING", "action.mission must be an object")
    required_mission_fields = ("mission_id", "mode", "current_predicate", "objective")
    normalized_mission: dict[str, str] = {}
    for field in required_mission_fields:
        value = mission.get(field)
        if not isinstance(value, str) or not value.strip():
            raise JSpaceCompileError(
                "TASK_CONTEXT_MISSION_INVALID", f"action.mission.{field} must be non-empty"
            )
        normalized_mission[field] = value.strip()
    task_id = mission.get("task_id")
    if task_id is not None:
        if not isinstance(task_id, str) or not task_id.strip():
            raise JSpaceCompileError(
                "TASK_CONTEXT_MISSION_INVALID", "action.mission.task_id must be non-empty"
            )
        normalized_mission["task_id"] = task_id.strip()

    context_summary = action.get("context_summary")
    if not isinstance(context_summary, str) or not context_summary.strip():
        raise JSpaceCompileError(
            "TASK_CONTEXT_SUMMARY_MISSING", "action.context_summary must be non-empty"
        )
    context_summary = context_summary.strip()
    if len(context_summary) > _MAX_CONTEXT_SUMMARY_CHARS:
        raise JSpaceCompileError(
            "TASK_CONTEXT_SUMMARY_TOO_LARGE",
            f"action.context_summary exceeds {_MAX_CONTEXT_SUMMARY_CHARS} characters",
        )

    evidence_refs = action.get("evidence_refs", [])
    if not isinstance(evidence_refs, list) or len(evidence_refs) > _MAX_EVIDENCE_REFS:
        raise JSpaceCompileError(
            "TASK_CONTEXT_EVIDENCE_INVALID",
            f"action.evidence_refs must be a list with at most {_MAX_EVIDENCE_REFS} entries",
        )
    normalized_evidence: list[dict[str, str]] = []
    for index, evidence in enumerate(evidence_refs):
        if not isinstance(evidence, dict):
            raise JSpaceCompileError(
                "TASK_CONTEXT_EVIDENCE_INVALID", f"evidence_refs[{index}] must be an object"
            )
        evidence_id = evidence.get("id")
        kind = evidence.get("kind")
        if not isinstance(evidence_id, str) or not evidence_id.strip():
            raise JSpaceCompileError(
                "TASK_CONTEXT_EVIDENCE_INVALID", f"evidence_refs[{index}].id must be non-empty"
            )
        if not isinstance(kind, str) or not kind.strip():
            raise JSpaceCompileError(
                "TASK_CONTEXT_EVIDENCE_INVALID", f"evidence_refs[{index}].kind must be non-empty"
            )
        row = {"id": evidence_id.strip(), "kind": kind.strip()}
        sha256 = evidence.get("sha256")
        if sha256 is not None:
            if (
                not isinstance(sha256, str)
                or len(sha256) != 64
                or any(character not in "0123456789abcdef" for character in sha256)
            ):
                raise JSpaceCompileError(
                    "TASK_CONTEXT_EVIDENCE_INVALID",
                    f"evidence_refs[{index}].sha256 must be lowercase SHA-256",
                )
            row["sha256"] = sha256
        normalized_evidence.append(row)

    forbidden_effects = _strings(action.get("forbidden_effects"), field="forbidden_effects")
    payload: dict[str, Any] = {
        "schema_version": TASK_CONTEXT_CAPSULE_SCHEMA_VERSION,
        "mission": normalized_mission,
        "context_summary": context_summary,
        "dcf_generation": jspace_contract["dcf_generation"],
        "surface": {
            "repo_root": jspace_contract["repo_root"],
            "matched_surface_ids": jspace_contract["matched_surface_ids"],
            "declared_targets": jspace_contract["declared_targets"],
        },
        "authority": {
            "forbidden_effects": forbidden_effects,
            "denied_operations": jspace_contract["denied_operations"],
        },
        "evidence_refs": normalized_evidence,
        "focused_verifiers": jspace_contract["focused_verifiers"],
        "jspace_semantic_sha256": jspace_contract["authorization_semantic_sha256"],
    }
    payload["semantic_sha256"] = _semantic_digest(payload)
    return payload


def canonical_contract_bytes(contract: dict[str, Any]) -> bytes:
    """Return the immutable on-disk representation of a compiled contract."""

    if contract.get("schema_version") == JSPACE_SCHEMA_VERSION:
        claimed_authorization = contract.get("authorization_semantic_sha256")
        expected_authorization = _authorization_digest(contract)
        if claimed_authorization != expected_authorization:
            raise JSpaceCompileError(
                "JSPACE_AUTHORIZATION_DIGEST_MISMATCH",
                "contract authorization_semantic_sha256 does not match authorization fields",
            )
        without_content = {key: value for key, value in contract.items() if key != "content_sha256"}
        expected_content = _semantic_digest(without_content)
        if contract.get("content_sha256") != expected_content:
            raise JSpaceCompileError(
                "JSPACE_CONTENT_DIGEST_MISMATCH",
                "contract content_sha256 does not match payload",
            )
        return _canonical_bytes(contract)

    without_digest = {key: value for key, value in contract.items() if key != "semantic_sha256"}
    expected = _semantic_digest(without_digest)
    if contract.get("semantic_sha256") != expected:
        raise JSpaceCompileError(
            "JSPACE_SEMANTIC_DIGEST_MISMATCH", "contract semantic_sha256 does not match payload"
        )
    return _canonical_bytes(contract)


def verify_contract_freshness(runtime: Any, contract: dict[str, Any]) -> None:
    """Recheck the exact required-domain token immediately before publication."""

    canonical_contract_bytes(contract)
    if contract.get("schema_version") != JSPACE_SCHEMA_VERSION:
        return
    generation = contract.get("dcf_generation")
    if not isinstance(generation, dict):
        raise JSpaceCompileError(
            "JSPACE_FRESHNESS_TOKEN_INVALID", "dcf_generation must be an object", blocked=True
        )
    freshness = generation.get("action_freshness")
    if not isinstance(freshness, dict):
        raise JSpaceCompileError(
            "JSPACE_FRESHNESS_TOKEN_INVALID", "action_freshness must be an object", blocked=True
        )
    expected = freshness.get("source_fingerprints")
    if not isinstance(expected, dict):
        raise JSpaceCompileError(
            "JSPACE_FRESHNESS_TOKEN_INVALID",
            "action_freshness.source_fingerprints must be an object",
            blocked=True,
        )
    normalized = {str(domain): str(value) for domain, value in expected.items()}
    if freshness.get("token_sha256") != _semantic_digest(normalized):
        raise JSpaceCompileError(
            "JSPACE_FRESHNESS_TOKEN_INVALID", "action freshness token digest is invalid", blocked=True
        )
    _current_required_fingerprints(runtime, normalized)


def write_immutable_contract(path: Path, contract: dict[str, Any]) -> str:
    """Atomically create a contract once; never expose partial final bytes."""

    encoded = canonical_contract_bytes(contract)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, 0o644)
        try:
            os.link(temporary_path, path)
        except FileExistsError as exc:
            if path.is_file() and not path.is_symlink() and path.read_bytes() == encoded:
                return str(path)
            raise JSpaceCompileError(
                "JSPACE_IMMUTABLE_CONTRACT_EXISTS",
                f"immutable contract path already contains different bytes: {path}",
                blocked=True,
            ) from exc
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        if descriptor != -1:
            os.close(descriptor)
        temporary_path.unlink(missing_ok=True)
    return str(path)
