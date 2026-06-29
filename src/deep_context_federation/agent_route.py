"""Machine-readable DCF route decisions for global agent wrappers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from deep_context_federation.agent_discover import discover_agent_context
from deep_context_federation.builder import utc_now

AGENT_ROUTE_SCHEMA_VERSION = "deep_context_federation_agent_route_v1"


def _quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def _target_args(targets: Sequence[str]) -> str:
    return "".join(f" --target {_quote(str(target))}" for target in targets if str(target))


def _manifest_args(manifests: Sequence[str]) -> str:
    return "".join(f" --manifest {_quote(str(manifest))}" for manifest in manifests if str(manifest))


def _step(step_id: str, *, action: str, command: str, purpose: str, terminal_model_input: bool = False) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "action": action,
        "command": command,
        "purpose": purpose,
        "terminal_model_input": terminal_model_input,
    }


def _first_list(discovery: Mapping[str, Any], key: str) -> list[str]:
    discovered = discovery.get("discovered") if isinstance(discovery.get("discovered"), Mapping) else {}
    return [str(item) for item in discovered.get(key) or [] if str(item)]


def route_agent_context(
    *,
    root: Path,
    task: str = "",
    targets: Sequence[str] = (),
    handoff_path: Path | None = None,
    output_dir: Path = Path(".dcf"),
) -> dict[str, Any]:
    """Build a read-only route artifact for global wrappers.

    The route intentionally does not execute the recommended command. It only
    normalizes discovery states into stable actions so wrappers do not need to
    hard-code DCF status branching.
    """

    root = root.expanduser().resolve()
    output_dir = output_dir.expanduser()
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    output_arg = output_dir.resolve().as_posix()
    discovery = discover_agent_context(root=root, handoff_path=handoff_path)
    discovery_status = str(discovery.get("status") or "")
    handoffs = _first_list(discovery, "handoffs")
    manifests = _first_list(discovery, "manifests")
    federations = _first_list(discovery, "federations")
    task_text = str(task or "").strip()
    selected_command = str(discovery.get("recommended_next_command") or "")
    route_steps: list[dict[str, Any]] = []
    requires_user_input: list[dict[str, Any]] = []
    status = "needs_bootstrap_agent_route"
    action = "scan_and_build"
    route_ready = True
    model_input_ready = bool(discovery.get("ready_for_model_input"))

    if discovery_status == "ready_model_input":
        status = "ready_agent_route"
        action = "emit_model_input"
        route_steps.append(
            _step(
                "00_emit_model_input",
                action=action,
                command=selected_command,
                purpose="Verify handoff and emit prompt text for the model.",
                terminal_model_input=True,
            )
        )
    elif discovery_status in {"blocked_model_input", "blocked_handoff_unreadable"}:
        status = "blocked_agent_route"
        action = "verify_handoff"
        route_ready = False
        route_steps.append(
            _step(
                "00_verify_handoff",
                action=action,
                command=selected_command,
                purpose="Inspect why the existing handoff is not safe for model input.",
            )
        )
    elif discovery_status == "manifest_available":
        action = "build_agent_handoff"
        if task_text:
            status = "needs_agent_handoff"
            manifest_arg = _manifest_args(manifests[:1])
            selected_command = (
                f"dcf agent-handoff --root {_quote(root.as_posix())} --output-dir {_quote(output_arg)}"
                f"{manifest_arg} --task {_quote(task_text)}{_target_args(targets)}"
            )
            route_steps.append(
                _step(
                    "00_build_agent_handoff",
                    action=action,
                    command=selected_command,
                    purpose="Build gated DCF handoff artifacts for the current task.",
                )
            )
            route_steps.append(
                _step(
                    "01_discover_again",
                    action="rediscover",
                    command=f"dcf agent-discover --root {_quote(root.as_posix())}",
                    purpose="Rediscover after handoff build before emitting model input.",
                )
            )
        else:
            status = "needs_task_agent_route"
            route_ready = False
            requires_user_input.append({"id": "task_required", "description": "agent-handoff requires a task string"})
            selected_command = str(discovery.get("recommended_next_command") or "")
            route_steps.append(
                _step(
                    "00_build_agent_handoff",
                    action=action,
                    command=selected_command,
                    purpose="Provide --task, then build a gated DCF handoff.",
                )
            )
    else:
        action = "scan_and_build"
        selected_command = f"dcf scan --root {_quote(root.as_posix())} --output-dir {_quote(output_arg)} --write --build"
        route_steps.append(
            _step(
                "00_scan_and_build",
                action=action,
                command=selected_command,
                purpose="Create starter DCF artifacts before task scoped handoff.",
            )
        )
        if discovery_status == "federation_available":
            status = "needs_manifest_refresh_agent_route"

    return {
        "schema_version": AGENT_ROUTE_SCHEMA_VERSION,
        "ok": route_ready,
        "status": status,
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": utc_now(),
        "root": root.as_posix(),
        "task": task_text,
        "targets": list(targets),
        "discovery_status": discovery_status,
        "action": action,
        "model_input_ready": model_input_ready,
        "route_ready": route_ready,
        "recommended_next_command": selected_command,
        "route_steps": route_steps,
        "requires_user_input": requires_user_input,
        "discovered": {
            "handoffs": handoffs,
            "manifests": manifests,
            "federations": federations,
        },
        "discovery_summary": {
            "schema_version": discovery.get("schema_version"),
            "status": discovery.get("status"),
            "ok": discovery.get("ok"),
            "ready_for_model_input": discovery.get("ready_for_model_input"),
            "selected_handoff": discovery.get("selected_handoff"),
        },
        "wrapper_contract": {
            "read_status": "status",
            "read_action": "action",
            "execute_only_route_steps": True,
            "execute_terminal_model_input_only_when_model_input_ready": True,
            "rerun_agent_discover_after_nonterminal_steps": True,
            "do_not_infer_authority_from_route": True,
        },
        "safety_boundaries": {
            "authority_effect": "none",
            "no_apply": True,
            "mutation_allowed": False,
            "external_model_calls": False,
            "source_or_authority_mutation": False,
            "route_only": True,
            "executes_commands": False,
        },
    }


def markdown_agent_route(result: Mapping[str, Any]) -> str:
    lines = [
        "# Deep Context Federation Agent Route",
        "",
        f"- Status: `{result.get('status')}`",
        f"- Action: `{result.get('action')}`",
        f"- Route ready: `{result.get('route_ready')}`",
        f"- Model input ready: `{result.get('model_input_ready')}`",
        f"- Recommended next command: `{result.get('recommended_next_command')}`",
        "",
        "## Route Steps",
        "",
    ]
    for row in result.get("route_steps") or []:
        if isinstance(row, Mapping):
            lines.append(f"- `{row.get('step_id')}` `{row.get('action')}`: `{row.get('command')}`")
    if not result.get("route_steps"):
        lines.append("- none")
    lines.extend(["", "## Required Input", ""])
    required = [row for row in result.get("requires_user_input") or [] if isinstance(row, Mapping)]
    if required:
        for row in required:
            lines.append(f"- `{row.get('id')}`: {row.get('description')}")
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"
