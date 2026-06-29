"""Machine-readable workflow plans for DCF agent runs."""

from __future__ import annotations

import json
import shlex
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from deep_context_federation.builder import DEFAULT_JSON_NAME
from deep_context_federation.builder import utc_now
from deep_context_federation.context_pack import estimate_tokens
from deep_context_federation.intake import DEFAULT_AGENT_INTAKE_JSON_NAME
from deep_context_federation.intake import DEFAULT_INTAKE_TASK_BRIEF_JSON_NAME
from deep_context_federation.target_review import TARGET_REVIEW_SCHEMA_VERSION
from deep_context_federation.target_review_gate import TARGET_REVIEW_GATE_SCHEMA_VERSION

WORKFLOW_PLAN_SCHEMA_VERSION = "deep_context_federation_workflow_plan_v1"
DEFAULT_WORKFLOW_PLAN_JSON_NAME = "deep_context_federation_workflow_plan.json"
DEFAULT_WORKFLOW_PLAN_MD_NAME = "DEEP_CONTEXT_FEDERATION_WORKFLOW_PLAN.md"
DEFAULT_TARGET_REVIEW_JSON_NAME = "deep_context_federation_target_review.json"
DEFAULT_TARGET_REVIEW_GATE_JSON_NAME = "deep_context_federation_target_review_gate.json"


def _quote(value: str | Path) -> str:
    return shlex.quote(str(value))


def _dedupe_targets(targets: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for target in targets:
        clean = str(target).strip()
        if not clean or clean in seen:
            continue
        result.append(clean)
        seen.add(clean)
    return result


def _normalize_output_dir(root: Path, output_dir: Path) -> Path:
    root = root.expanduser().resolve()
    output_dir = output_dir.expanduser()
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    return output_dir.resolve()


def _step(
    *,
    step_id: str,
    purpose: str,
    command: str,
    input_refs: Sequence[str],
    output_refs: Sequence[str],
    produces_schema: Sequence[str],
    stop_on_failure: bool,
    reads_context: str,
    token_role: str,
) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "purpose": purpose,
        "command": command,
        "input_refs": list(input_refs),
        "output_refs": list(output_refs),
        "produces_schema": list(produces_schema),
        "stop_on_failure": bool(stop_on_failure),
        "reads_context": reads_context,
        "token_role": token_role,
        "authority_effect": "none",
        "no_apply": True,
    }


def _render_prompt_text(result: Mapping[str, Any]) -> str:
    lines = [
        "# Deep Context Federation Workflow Plan",
        "",
        "Boundary: authority_effect=none; no_apply=true; this is a read-only execution plan.",
        f"Task: {result.get('task')}",
        f"Status: {result.get('status')}",
        "",
        "## Run Order",
    ]
    for step in result.get("steps") or []:
        if isinstance(step, Mapping):
            lines.append(
                "- {step_id}: {purpose}; stop_on_failure={stop}; token_role={token_role}".format(
                    step_id=step.get("step_id"),
                    purpose=step.get("purpose"),
                    stop=step.get("stop_on_failure"),
                    token_role=step.get("token_role"),
                )
            )
    warnings = [str(item) for item in result.get("warnings") or []]
    if warnings:
        lines.extend(["", "## Warnings"])
        for warning in warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines).rstrip() + "\n"


def build_workflow_plan(
    *,
    task: str,
    root: Path = Path.cwd(),
    output_dir: Path = Path(".dcf"),
    targets: Sequence[str] = (),
    quality_policy: Path | None = None,
    target_review_policy: Path | None = None,
    token_budget: int = 4000,
    query_limit: int = 10,
    max_presets: int = 3,
    max_rows: int = 80,
    max_files: int = 5000,
    max_parse_bytes: int = 1_000_000,
    include_hashes: bool = False,
    include_codebase_memory: bool = False,
    codebase_memory_cache_dir: Path | None = None,
    include_prompt: bool = True,
) -> dict[str, Any]:
    """Build a deterministic read-only run plan for agents."""

    task = str(task).strip()
    root = root.expanduser().resolve()
    out_dir = _normalize_output_dir(root, output_dir)
    target_rows = _dedupe_targets(targets)
    token_budget = max(500, int(token_budget))
    query_limit = max(1, int(query_limit))
    max_presets = max(1, int(max_presets))
    max_rows = max(1, int(max_rows))
    max_files = max(1, int(max_files))
    max_parse_bytes = max(1, int(max_parse_bytes))

    federation_json = out_dir / DEFAULT_JSON_NAME
    agent_intake_json = out_dir / DEFAULT_AGENT_INTAKE_JSON_NAME
    task_brief_json = out_dir / DEFAULT_INTAKE_TASK_BRIEF_JSON_NAME
    target_review_json = out_dir / DEFAULT_TARGET_REVIEW_JSON_NAME
    target_review_gate_json = out_dir / DEFAULT_TARGET_REVIEW_GATE_JSON_NAME
    plan_json = out_dir / DEFAULT_WORKFLOW_PLAN_JSON_NAME

    intake_parts = [
        "dcf",
        "intake",
        "--root",
        _quote(root),
        "--output-dir",
        _quote(out_dir),
        "--task",
        _quote(task),
        "--token-budget",
        str(token_budget),
        "--query-limit",
        str(query_limit),
        "--max-presets",
        str(max_presets),
        "--max-rows",
        str(max_rows),
        "--max-files",
        str(max_files),
        "--max-parse-bytes",
        str(max_parse_bytes),
    ]
    if quality_policy:
        intake_parts.extend(["--policy", _quote(quality_policy.expanduser())])
    if include_hashes:
        intake_parts.append("--hash-files")
    if include_codebase_memory:
        intake_parts.append("--include-memory-import")
    if codebase_memory_cache_dir:
        intake_parts.extend(["--memory-import-cache-dir", _quote(codebase_memory_cache_dir.expanduser())])
    if not include_prompt:
        intake_parts.append("--no-prompt")

    steps = [
        _step(
            step_id="01_agent_intake",
            purpose="Build the bounded context surface, health gate, and task brief before model reasoning.",
            command=" ".join(intake_parts),
            input_refs=[root.as_posix()],
            output_refs=[agent_intake_json.as_posix(), federation_json.as_posix(), task_brief_json.as_posix()],
            produces_schema=["deep_context_federation_agent_intake_v1"],
            stop_on_failure=True,
            reads_context="repo_scan_and_manifest_sources",
            token_role="produce_bounded_context_pack",
        ),
        _step(
            step_id="02_validate_intake_contract",
            purpose="Fail early if the intake packet does not match the machine-readable contract.",
            command=(
                "dcf validate-artifact --input {input} --artifact agent_intake "
                "--output {output}"
            ).format(
                input=_quote(agent_intake_json),
                output=_quote(out_dir / "deep_context_federation_agent_intake_contract_validation.json"),
            ),
            input_refs=[agent_intake_json.as_posix()],
            output_refs=[(out_dir / "deep_context_federation_agent_intake_contract_validation.json").as_posix()],
            produces_schema=["deep_context_federation_contract_validation_v1"],
            stop_on_failure=True,
            reads_context="agent_intake_contract_only",
            token_role="avoid_large_invalid_artifacts",
        ),
    ]

    if target_rows:
        target_args = " ".join(f"--target {_quote(target)}" for target in target_rows)
        steps.extend(
            [
                _step(
                    step_id="03_review_targets",
                    purpose="Batch review requested targets before deep model reading.",
                    command=(
                        "dcf review-targets --input {input} {targets} --token-budget {budget} "
                        "--output {output}"
                    ).format(
                        input=_quote(federation_json),
                        targets=target_args,
                        budget=token_budget,
                        output=_quote(target_review_json),
                    ),
                    input_refs=[federation_json.as_posix(), *target_rows],
                    output_refs=[target_review_json.as_posix()],
                    produces_schema=[TARGET_REVIEW_SCHEMA_VERSION],
                    stop_on_failure=False,
                    reads_context="target_matched_evidence_only",
                    token_role="rank_targets_before_prompt_expansion",
                ),
                _step(
                    step_id="04_review_gate",
                    purpose="Apply deterministic continuation thresholds to the target portfolio.",
                    command=" ".join(
                        [
                            "dcf",
                            "review-gate",
                            "--input",
                            _quote(target_review_json),
                            *(["--policy", _quote(target_review_policy.expanduser())] if target_review_policy else []),
                            "--output",
                            _quote(target_review_gate_json),
                        ]
                    ),
                    input_refs=[target_review_json.as_posix()],
                    output_refs=[target_review_gate_json.as_posix()],
                    produces_schema=[TARGET_REVIEW_GATE_SCHEMA_VERSION],
                    stop_on_failure=True,
                    reads_context="target_review_summary_only",
                    token_role="stop_before_wasting_model_context",
                ),
                _step(
                    step_id="05_inspect_priority_target",
                    purpose="Resolve only the highest priority target from the review result, not the whole federation.",
                    command=(
                        "dcf resolve --input {input} --target '<target_from_priority_order>' "
                        "--token-budget {budget} --output {output}"
                    ).format(
                        input=_quote(federation_json),
                        budget=max(500, token_budget // 2),
                        output=_quote(out_dir / "deep_context_federation_priority_resolve.json"),
                    ),
                    input_refs=[federation_json.as_posix(), target_review_json.as_posix()],
                    output_refs=[(out_dir / "deep_context_federation_priority_resolve.json").as_posix()],
                    produces_schema=["deep_context_federation_resolve_v1"],
                    stop_on_failure=False,
                    reads_context="one_target_evidence_card",
                    token_role="defer_expensive_context_until_gate_passes",
                ),
            ]
        )
    else:
        steps.append(
            _step(
                step_id="03_task_brief_only",
                purpose="Use the generated task brief and bounded context pack because no target portfolio was supplied.",
                command="dcf brief --input {input} --task {task} --token-budget {budget} --output {output}".format(
                    input=_quote(federation_json),
                    task=_quote(task),
                    budget=token_budget,
                    output=_quote(out_dir / "deep_context_federation_task_brief.json"),
                ),
                input_refs=[federation_json.as_posix()],
                output_refs=[(out_dir / "deep_context_federation_task_brief.json").as_posix()],
                produces_schema=["deep_context_federation_task_brief_v1"],
                stop_on_failure=False,
                reads_context="bounded_prompt_pack_only",
                token_role="single_packet_model_context",
            )
        )

    warnings: list[str] = []
    if not task:
        warnings.append("Task is empty; downstream routing quality will be low.")
    if not target_rows:
        warnings.append("No targets supplied; target review and review gate are skipped.")
    if include_codebase_memory and codebase_memory_cache_dir is None:
        warnings.append("memory import requested without explicit cache dir; keep cache outside the repo.")

    gates = [
        {
            "gate_id": "intake_quality_gate",
            "source_step": "01_agent_intake",
            "required": True,
            "artifact_ref": agent_intake_json.as_posix(),
            "failure_action": "stop_and_repair_context_surface",
        },
        {
            "gate_id": "agent_intake_contract",
            "source_step": "02_validate_intake_contract",
            "required": True,
            "artifact_ref": (out_dir / "deep_context_federation_agent_intake_contract_validation.json").as_posix(),
            "failure_action": "stop_before_model_prompt",
        },
    ]
    if target_rows:
        gates.append(
            {
                "gate_id": "target_review_gate",
                "source_step": "04_review_gate",
                "required": True,
                "artifact_ref": target_review_gate_json.as_posix(),
                "failure_action": "stop_or_request_human_review",
            }
        )

    token_efficiency = {
        "model_first_reads": [
            plan_json.as_posix(),
            task_brief_json.as_posix(),
            target_review_gate_json.as_posix() if target_rows else "",
        ],
        "skip_by_default": [
            "full repository tree",
            "full federation artifact",
            "full per target adjudication details",
            "raw source files without target match",
        ],
        "mechanisms": [
            "contract validation before context expansion",
            "task brief preset selection",
            "bounded context pack token budget",
            "target review summary before target resolution",
            "review gate stop condition before deeper prompts",
        ],
    }
    token_efficiency["model_first_reads"] = [item for item in token_efficiency["model_first_reads"] if item]

    result: dict[str, Any] = {
        "schema_version": WORKFLOW_PLAN_SCHEMA_VERSION,
        "status": "ready_with_targets" if target_rows else "ready_no_targets",
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": utc_now(),
        "task": task,
        "root": root.as_posix(),
        "output_dir": out_dir.as_posix(),
        "targets": target_rows,
        "target_count": len(target_rows),
        "steps": steps,
        "gates": gates,
        "warnings": warnings,
        "token_efficiency": token_efficiency,
        "outputs": {
            "workflow_plan_json": plan_json.as_posix(),
            "workflow_plan_markdown": (out_dir / DEFAULT_WORKFLOW_PLAN_MD_NAME).as_posix(),
            "agent_intake_json": agent_intake_json.as_posix(),
            "federation_json": federation_json.as_posix(),
            "task_brief_json": task_brief_json.as_posix(),
            "target_review_json": target_review_json.as_posix() if target_rows else "",
            "target_review_gate_json": target_review_gate_json.as_posix() if target_rows else "",
        },
        "safety_boundaries": {
            "authority_effect": "none",
            "no_apply": True,
            "mutation_allowed": False,
            "external_model_calls": False,
            "executes_commands": False,
            "live_runtime_or_broker_mutation": False,
            "plan_only": True,
        },
    }
    prompt_text = _render_prompt_text(result) if include_prompt else ""
    result["prompt_text"] = prompt_text
    result["prompt_estimated_tokens"] = estimate_tokens(prompt_text) if prompt_text else 0
    result["json_estimated_tokens"] = estimate_tokens(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return result


def markdown_workflow_plan(result: Mapping[str, Any]) -> str:
    token_efficiency = result.get("token_efficiency") if isinstance(result.get("token_efficiency"), Mapping) else {}
    lines = [
        "# Deep Context Federation Workflow Plan",
        "",
        f"- Status: `{result.get('status')}`",
        f"- Task: `{result.get('task')}`",
        f"- Target count: `{result.get('target_count')}`",
        f"- Authority effect: `{result.get('authority_effect')}`",
        f"- No apply: `{result.get('no_apply')}`",
        f"- Prompt tokens: `{result.get('prompt_estimated_tokens')}`",
        "",
        "## Steps",
        "",
    ]
    for step in result.get("steps") or []:
        if isinstance(step, Mapping):
            lines.append(f"- `{step.get('step_id')}` {step.get('purpose')}")
            lines.append(f"  - command: `{step.get('command')}`")
    lines.extend(["", "## Gates", ""])
    for gate in result.get("gates") or []:
        if isinstance(gate, Mapping):
            lines.append(f"- `{gate.get('gate_id')}` required=`{gate.get('required')}` action=`{gate.get('failure_action')}`")
    lines.extend(["", "## Token Efficiency", ""])
    for item in token_efficiency.get("mechanisms") or []:
        lines.append(f"- {item}")
    warnings = [str(item) for item in result.get("warnings") or []]
    if warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines).rstrip() + "\n"
