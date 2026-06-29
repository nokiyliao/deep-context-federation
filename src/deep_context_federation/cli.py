"""Command-line interface for Deep Context Federation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from deep_context_federation.adjudicate import adjudicate_target
from deep_context_federation.adjudicate import markdown_adjudication
from deep_context_federation.agent_context import build_agent_context
from deep_context_federation.agent_context import markdown_agent_context
from deep_context_federation.agent_context_gate import evaluate_agent_context_gate
from deep_context_federation.agent_context_gate import load_agent_context_gate_policy
from deep_context_federation.agent_context_gate import markdown_agent_context_gate
from deep_context_federation.agent_ci import build_agent_ci
from deep_context_federation.agent_ci import markdown_agent_ci
from deep_context_federation.agent_discover import discover_agent_context
from deep_context_federation.agent_discover import markdown_agent_discovery
from deep_context_federation.agent_handoff import build_agent_handoff
from deep_context_federation.agent_handoff import markdown_agent_handoff
from deep_context_federation.agent_handoff_verify import markdown_agent_handoff_verification
from deep_context_federation.agent_handoff_verify import verify_agent_handoff
from deep_context_federation.agent_model_input import build_agent_model_input
from deep_context_federation.agent_model_input import markdown_agent_model_input
from deep_context_federation.agent_onboard import build_agent_onboard
from deep_context_federation.agent_onboard import markdown_agent_onboard
from deep_context_federation.agent_profile import load_agent_profile
from deep_context_federation.agent_profile import markdown_agent_profile
from deep_context_federation.agent_profile_init import build_agent_profile_init
from deep_context_federation.agent_profile_init import markdown_agent_profile_init
from deep_context_federation.agent_ready import AGENT_READY_SCHEMA_VERSION
from deep_context_federation.agent_ready import build_agent_ready
from deep_context_federation.agent_ready import markdown_agent_ready
from deep_context_federation.agent_route import markdown_agent_route
from deep_context_federation.agent_route import route_agent_context
from deep_context_federation.bench import benchmark_build
from deep_context_federation.bootstrap import bootstrap_federation
from deep_context_federation.bootstrap import markdown_bootstrap
from deep_context_federation.builder import DEFAULT_JSON_NAME, build_federation, read_json, write_json, write_markdown
from deep_context_federation.capabilities import build_capabilities
from deep_context_federation.capabilities import markdown_capabilities
from deep_context_federation.compose import compose_manifests
from deep_context_federation.compose import markdown_compose
from deep_context_federation.context_pack import markdown_context_pack
from deep_context_federation.context_pack import pack_context
from deep_context_federation.diff import diff_federations
from deep_context_federation.diff import markdown_diff
from deep_context_federation.doctor import doctor_federation
from deep_context_federation.doctor import markdown_doctor
from deep_context_federation.efficiency_gate import evaluate_efficiency_gate
from deep_context_federation.efficiency_gate import load_efficiency_gate_policy
from deep_context_federation.efficiency_gate import markdown_efficiency_gate
from deep_context_federation.efficiency_report import build_efficiency_report
from deep_context_federation.efficiency_report import markdown_efficiency_report
from deep_context_federation.graph import markdown_trace
from deep_context_federation.graph import trace_federation
from deep_context_federation.intake import build_agent_intake
from deep_context_federation.intake import markdown_agent_intake
from deep_context_federation.manifest import validate_manifest
from deep_context_federation.memory_ledger import build_memory_ledger
from deep_context_federation.memory_ledger import markdown_memory_ledger
from deep_context_federation.native_integration import build_native_integration_plan
from deep_context_federation.native_integration import markdown_native_integration_plan
from deep_context_federation.quality_gate import evaluate_quality_gate
from deep_context_federation.quality_gate import load_quality_gate_policy
from deep_context_federation.quality_gate import markdown_quality_gate
from deep_context_federation.query import markdown as query_markdown
from deep_context_federation.query import query_federation
from deep_context_federation.rank import markdown_rank
from deep_context_federation.rank import rank_entities
from deep_context_federation.rank import rank_sources
from deep_context_federation.resolve import markdown_resolve
from deep_context_federation.resolve import resolve_target
from deep_context_federation.scanner import markdown_scan
from deep_context_federation.scanner import scan_repository
from deep_context_federation.schemas import artifact_kinds
from deep_context_federation.schemas import build_schema_registry
from deep_context_federation.schemas import markdown_contract_validation
from deep_context_federation.schemas import markdown_json_schema
from deep_context_federation.schemas import markdown_schema_registry
from deep_context_federation.schemas import schema_for_artifact
from deep_context_federation.schemas import validate_artifact_contract
from deep_context_federation.sqlite_query import SQL_PRESETS
from deep_context_federation.sqlite_query import markdown as sql_markdown
from deep_context_federation.sqlite_query import query_sqlite
from deep_context_federation.target_review import markdown_target_review
from deep_context_federation.target_review import review_targets
from deep_context_federation.target_review_gate import evaluate_target_review_gate
from deep_context_federation.target_review_gate import load_target_review_gate_policy
from deep_context_federation.target_review_gate import markdown_target_review_gate
from deep_context_federation.task_brief import build_task_brief
from deep_context_federation.task_brief import markdown_task_brief
from deep_context_federation.unified_index import build_unified_index
from deep_context_federation.unified_index import build_unified_working_set
from deep_context_federation.unified_index import markdown_unified_index
from deep_context_federation.unified_index import markdown_unified_working_set
from deep_context_federation.verifier import read_json as read_required_json
from deep_context_federation.verifier import verify_federation
from deep_context_federation.workflow_plan import build_workflow_plan
from deep_context_federation.workflow_plan import markdown_workflow_plan
from deep_context_federation.workflow_run import build_workflow_run
from deep_context_federation.workflow_run import markdown_workflow_run


COMMAND_ALIASES = {
    "native-integration-plan": "plan-native-ownership",
    "memory-ledger": "index-context-memory",
    "agent-ci": "decide-continuation",
    "agent-context": "pack-model-context",
    "agent-context-gate": "gate-model-context",
    "agent-handoff": "prepare-model-handoff",
    "verify-handoff": "verify-model-handoff",
    "agent-model-input": "emit-model-input",
    "agent-profile": "validate-run-profile",
    "agent-profile-init": "init-run-profile",
    "agent-onboard": "onboard-runner",
    "agent-discover": "discover-model-readiness",
    "agent-route": "route-model-readiness",
    "agent-ready": "prepare-model-input",
}


def _normalize_command_argv(argv: Sequence[str] | None) -> list[str]:
    normalized = list(sys.argv[1:] if argv is None else argv)
    if normalized:
        normalized[0] = COMMAND_ALIASES.get(normalized[0], normalized[0])
    return normalized


def add_common_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", type=Path, default=Path("deep_context_federation.json"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=Path(".dcf"))


def add_memory_import_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--include-memory-import", dest="include_codebase_memory", action="store_true")
    parser.add_argument("--memory-import-cache-dir", dest="codebase_memory_cache_dir", metavar="MEMORY_IMPORT_CACHE_DIR", type=Path)
    parser.add_argument("--include-codebase-memory", dest="include_codebase_memory", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--codebase-memory-cache-dir", dest="codebase_memory_cache_dir", type=Path, help=argparse.SUPPRESS)


def read_targets_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except Exception:
        data = None
    if isinstance(data, list):
        return [str(item) for item in data if str(item).strip()]
    return [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]


AGENT_READY_DEFAULTS = {
    "output_dir": Path(".dcf"),
    "workflow_token_budget": 4000,
    "context_token_budget": 4000,
    "context_mode": "read-first",
    "max_artifact_tokens": 1200,
    "query_limit": 10,
    "max_presets": 3,
    "max_rows": 80,
    "max_files": 5000,
    "max_parse_bytes": 1_000_000,
}


def _profile_summary(profile: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": profile.get("schema_version"),
        "ok": profile.get("ok"),
        "status": profile.get("status"),
        "profile_path": profile.get("profile_path"),
        "profile_id": profile.get("profile_id"),
        "summary": dict(profile.get("summary") if isinstance(profile.get("summary"), Mapping) else {}),
    }


def _profile_path(normalized: Mapping[str, Any], key: str) -> Path | None:
    if key not in normalized:
        return None
    value = str(normalized.get(key) or "").strip()
    return Path(value) if value else None


def _profile_path_list(normalized: Mapping[str, Any], key: str) -> list[Path]:
    values = normalized.get(key)
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return []
    return [Path(str(value)) for value in values if str(value).strip()]


def _profile_int(args: argparse.Namespace, normalized: Mapping[str, Any], field: str) -> int:
    value = getattr(args, field)
    default = AGENT_READY_DEFAULTS[field]
    if value == default and field in normalized:
        return int(normalized[field])
    return int(value)


def _profile_string(args: argparse.Namespace, normalized: Mapping[str, Any], field: str) -> str:
    value = str(getattr(args, field) or "")
    default = str(AGENT_READY_DEFAULTS[field])
    if value == default and field in normalized:
        return str(normalized[field] or "")
    return value


def _agent_ready_profile_failure(*, args: argparse.Namespace, profile: Mapping[str, Any]) -> dict[str, Any]:
    root = Path.cwd()
    normalized = profile.get("normalized") if isinstance(profile.get("normalized"), Mapping) else {}
    profile_root = _profile_path(normalized, "root")
    if profile_root:
        root = profile_root.expanduser().resolve()
    elif getattr(args, "root", None):
        root = args.root.expanduser().resolve()
    return {
        "schema_version": AGENT_READY_SCHEMA_VERSION,
        "ok": False,
        "status": "fail_agent_ready",
        "authority_effect": "none",
        "no_apply": True,
        "root": root.as_posix(),
        "task": str(normalized.get("task") or getattr(args, "task", "") or ""),
        "targets": list(normalized.get("targets") or getattr(args, "target", []) or []),
        "action_taken": "blocked_by_profile",
        "agent_profile_summary": _profile_summary(profile),
        "route_summary": {},
        "handoff_summary": {},
        "input_freshness": {},
        "request_binding": {},
        "model_input_summary": {},
        "prompt_source": "",
        "prompt_format": "",
        "prompt_estimated_tokens": 0,
        "prompt_text": "",
        "token_economics": {},
        "errors": [{"id": "agent_profile_invalid", "status": profile.get("status"), "profile_errors": list(profile.get("errors") or [])}],
        "outputs": {},
        "safety_boundaries": {
            "authority_effect": "none",
            "no_apply": True,
            "mutation_allowed": False,
            "writes_only_output_dir": True,
            "external_model_calls": False,
            "source_or_authority_mutation": False,
            "prompt_emitted_only_after_model_input_pass": True,
        },
    }


def _resolve_agent_ready_args(args: argparse.Namespace, normalized: Mapping[str, Any]) -> dict[str, Any]:
    root = args.root
    if args.root == Path.cwd():
        root = _profile_path(normalized, "root") or args.root
    output_dir = args.output_dir
    if args.output_dir == AGENT_READY_DEFAULTS["output_dir"]:
        output_dir = _profile_path(normalized, "output_dir") or args.output_dir
    manifests = list(args.manifest or []) or _profile_path_list(normalized, "manifests")
    targets = list(args.target or []) or list(normalized.get("targets") or [])
    if args.targets_file:
        targets.extend(read_targets_file(args.targets_file))
    handoff = args.handoff or _profile_path(normalized, "handoff")
    quality_policy = args.quality_policy or _profile_path(normalized, "quality_policy")
    target_review_policy = args.target_review_policy or _profile_path(normalized, "target_review_policy")
    efficiency_policy = args.efficiency_policy or _profile_path(normalized, "efficiency_policy")
    context_gate_policy = args.context_gate_policy or _profile_path(normalized, "context_gate_policy")
    codebase_memory_cache_dir = args.codebase_memory_cache_dir or _profile_path(normalized, "memory_import_cache_dir") or _profile_path(normalized, "codebase_memory_cache_dir")
    baselines = list(args.baseline or []) or _profile_path_list(normalized, "baselines")
    task = str(args.task or normalized.get("task") or "")
    include_content = bool(normalized.get("include_content")) if "include_content" in normalized else not args.no_content
    if args.no_content:
        include_content = False
    include_prompt = bool(normalized.get("include_prompt")) if "include_prompt" in normalized else not args.no_prompt
    if args.no_prompt:
        include_prompt = False
    return {
        "root": root,
        "output_dir": output_dir,
        "manifests": manifests,
        "task": task,
        "targets": targets,
        "handoff_path": handoff,
        "quality_policy_path": quality_policy,
        "target_review_policy_path": target_review_policy,
        "efficiency_policy_path": efficiency_policy,
        "context_gate_policy_path": context_gate_policy,
        "workflow_token_budget": _profile_int(args, normalized, "workflow_token_budget"),
        "context_token_budget": _profile_int(args, normalized, "context_token_budget"),
        "context_mode": _profile_string(args, normalized, "context_mode"),
        "max_artifact_tokens": _profile_int(args, normalized, "max_artifact_tokens"),
        "query_limit": _profile_int(args, normalized, "query_limit"),
        "max_presets": _profile_int(args, normalized, "max_presets"),
        "max_rows": _profile_int(args, normalized, "max_rows"),
        "max_files": _profile_int(args, normalized, "max_files"),
        "max_parse_bytes": _profile_int(args, normalized, "max_parse_bytes"),
        "include_hashes": bool(args.hash_files or normalized.get("hash_files")),
        "include_codebase_memory": bool(args.include_codebase_memory or normalized.get("include_memory_import") or normalized.get("include_codebase_memory")),
        "codebase_memory_cache_dir": codebase_memory_cache_dir,
        "include_content": include_content,
        "include_prompt": include_prompt,
        "include_details": bool(args.include_details or normalized.get("include_details")),
        "extra_baselines": baselines,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dcf", description="Read-only deep context federation CLI.")
    sub = parser.add_subparsers(dest="command", required=True)
    capabilities = sub.add_parser("capabilities", help="Describe DCF machine-readable contracts, commands, presets, and safety boundaries.")
    capabilities.add_argument("--output", type=Path)
    capabilities.add_argument("--format", choices=["json", "markdown"], default="json")
    schema = sub.add_parser("schema", help="Emit the DCF JSON Schema registry or one artifact schema.")
    schema.add_argument("--artifact", choices=artifact_kinds())
    schema.add_argument("--output", type=Path)
    schema.add_argument("--format", choices=["json", "markdown"], default="json")
    validate_artifact = sub.add_parser("validate-artifact", help="Validate an artifact against DCF top-level JSON Schema contracts.")
    validate_artifact.add_argument("--input", type=Path, required=True)
    validate_artifact.add_argument("--artifact", choices=artifact_kinds())
    validate_artifact.add_argument("--output", type=Path)
    validate_artifact.add_argument("--format", choices=["json", "markdown"], default="json")
    native_integration = sub.add_parser("plan-native-ownership", help="Plan DCF-native ownership of overlapping context-tool functions.")
    native_integration.set_defaults(capability=[])
    native_integration.add_argument("--function", dest="capability", metavar="FUNCTION", action="append", help="DCF function name to inspect, such as symbol-call-graph or long-term-context-memory.")
    native_integration.add_argument("--capability", dest="capability", action="append", help=argparse.SUPPRESS)
    native_integration.add_argument("--output", type=Path)
    native_integration.add_argument("--format", choices=["json", "markdown"], default="json")
    memory_ledger = sub.add_parser("index-context-memory", help="Materialize generated DCF artifacts into a native reusable context memory ledger.")
    memory_ledger.add_argument("--root", type=Path, default=Path.cwd())
    memory_ledger.add_argument("--input-dir", type=Path, action="append", default=[])
    memory_ledger.add_argument("--input-file", type=Path, action="append", default=[])
    memory_ledger.add_argument("--max-files", type=int, default=500)
    memory_ledger.add_argument("--output", type=Path)
    memory_ledger.add_argument("--format", choices=["json", "markdown"], default="json")
    unified_index = sub.add_parser("unify-context", help="Build a DCF-native source-collapsed unified context index.")
    unified_index.add_argument("--input", type=Path, default=Path(".dcf") / DEFAULT_JSON_NAME, help="Federation JSON artifact.")
    unified_index.add_argument("--memory-ledger", type=Path)
    unified_index.add_argument("--capabilities", type=Path)
    unified_index.add_argument("--native-plan", type=Path)
    unified_index.add_argument("--query", default="")
    unified_index.add_argument("--limit", type=int, default=200)
    unified_index.add_argument("--output", type=Path)
    unified_index.add_argument("--format", choices=["json", "markdown"], default="json")
    selected_context = sub.add_parser("select-context", help="Select a compact task-scoped DCF working set from a unified context index.")
    selected_context.add_argument("--input", type=Path, default=Path(".dcf") / "deep_context_federation_unified_index.json", help="Unified context index JSON artifact.")
    selected_context.add_argument("--query", default="")
    selected_context.add_argument("--limit", type=int, default=24)
    selected_context.add_argument("--label-chars", type=int, default=96)
    selected_context.add_argument("--value-chars", type=int, default=160)
    selected_context.add_argument("--max-tokens", type=int)
    selected_context.add_argument("--facet-mode", choices=["balanced", "ranked"], default="balanced")
    selected_context.add_argument("--min-facets", type=int, default=4)
    selected_context.add_argument("--output", type=Path)
    selected_context.add_argument("--format", choices=["json", "markdown"], default="json")
    build = sub.add_parser("build", help="Build a federation artifact from a manifest.")
    add_common_source_args(build)
    add_memory_import_args(build)
    build.add_argument("--write", action="store_true")
    build.add_argument("--json", action="store_true")
    scan = sub.add_parser("scan", help="Read-only scan of a repo into starter federation sources.")
    scan.add_argument("--root", type=Path, default=Path.cwd())
    scan.add_argument("--output-dir", type=Path, default=Path(".dcf"))
    scan.add_argument("--write", action="store_true")
    scan.add_argument("--build", action="store_true", help="Build a federation immediately from the generated manifest.")
    scan.add_argument("--max-files", type=int, default=5000)
    scan.add_argument("--max-parse-bytes", type=int, default=1_000_000)
    scan.add_argument("--hash-files", action="store_true")
    scan.add_argument("--format", choices=["json", "markdown"], default="json")
    bootstrap = sub.add_parser("bootstrap", help="Run scan, optional compose, build, verify, and doctor in one pipeline.")
    bootstrap.add_argument("--root", type=Path, default=Path.cwd())
    bootstrap.add_argument("--output-dir", type=Path, default=Path(".dcf"))
    bootstrap.add_argument("--manifest", type=Path, action="append", default=[])
    bootstrap.add_argument("--max-files", type=int, default=5000)
    bootstrap.add_argument("--max-parse-bytes", type=int, default=1_000_000)
    bootstrap.add_argument("--hash-files", action="store_true")
    add_memory_import_args(bootstrap)
    bootstrap.add_argument("--format", choices=["json", "markdown"], default="json")
    intake = sub.add_parser("intake", help="Run bootstrap, quality gate, and task brief as one agent intake packet.")
    intake.add_argument("--root", type=Path, default=Path.cwd())
    intake.add_argument("--output-dir", type=Path, default=Path(".dcf"))
    intake.add_argument("--manifest", type=Path, action="append", default=[])
    intake.add_argument("--task", required=True)
    intake.add_argument("--policy", type=Path, help="Optional quality gate policy JSON.")
    intake.add_argument("--max-files", type=int, default=5000)
    intake.add_argument("--max-parse-bytes", type=int, default=1_000_000)
    intake.add_argument("--hash-files", action="store_true")
    add_memory_import_args(intake)
    intake.add_argument("--token-budget", type=int, default=4000)
    intake.add_argument("--query-limit", type=int, default=10)
    intake.add_argument("--max-presets", type=int, default=3)
    intake.add_argument("--max-rows", type=int, default=80)
    intake.add_argument("--no-prompt", action="store_true", help="Skip rendered prompt_text inside the embedded task brief.")
    intake.add_argument("--format", choices=["json", "markdown"], default="json")
    workflow_plan = sub.add_parser("workflow-plan", help="Emit a read-only run plan that orders DCF commands, gates, and bounded context reads.")
    workflow_plan.add_argument("--root", type=Path, default=Path.cwd())
    workflow_plan.add_argument("--output-dir", type=Path, default=Path(".dcf"))
    workflow_plan.add_argument("--task", required=True)
    workflow_plan.add_argument("--target", action="append", default=[])
    workflow_plan.add_argument("--targets-file", type=Path)
    workflow_plan.add_argument("--quality-policy", type=Path)
    workflow_plan.add_argument("--target-review-policy", type=Path)
    workflow_plan.add_argument("--token-budget", type=int, default=4000)
    workflow_plan.add_argument("--query-limit", type=int, default=10)
    workflow_plan.add_argument("--max-presets", type=int, default=3)
    workflow_plan.add_argument("--max-rows", type=int, default=80)
    workflow_plan.add_argument("--max-files", type=int, default=5000)
    workflow_plan.add_argument("--max-parse-bytes", type=int, default=1_000_000)
    workflow_plan.add_argument("--hash-files", action="store_true")
    add_memory_import_args(workflow_plan)
    workflow_plan.add_argument("--no-prompt", action="store_true", help="Skip rendered prompt_text.")
    workflow_plan.add_argument("--output", type=Path)
    workflow_plan.add_argument("--format", choices=["json", "markdown"], default="json")
    workflow_run = sub.add_parser("workflow-run", help="Execute the read-only DCF workflow into one compact run capsule.")
    workflow_run.add_argument("--root", type=Path, default=Path.cwd())
    workflow_run.add_argument("--output-dir", type=Path, default=Path(".dcf"))
    workflow_run.add_argument("--manifest", type=Path, action="append", default=[])
    workflow_run.add_argument("--task", required=True)
    workflow_run.add_argument("--target", action="append", default=[])
    workflow_run.add_argument("--targets-file", type=Path)
    workflow_run.add_argument("--quality-policy", type=Path)
    workflow_run.add_argument("--target-review-policy", type=Path)
    workflow_run.add_argument("--token-budget", type=int, default=4000)
    workflow_run.add_argument("--query-limit", type=int, default=10)
    workflow_run.add_argument("--max-presets", type=int, default=3)
    workflow_run.add_argument("--max-rows", type=int, default=80)
    workflow_run.add_argument("--max-files", type=int, default=5000)
    workflow_run.add_argument("--max-parse-bytes", type=int, default=1_000_000)
    workflow_run.add_argument("--hash-files", action="store_true")
    add_memory_import_args(workflow_run)
    workflow_run.add_argument("--include-details", action="store_true", help="Include full target adjudication details inside target review.")
    workflow_run.add_argument("--no-prompt", action="store_true", help="Skip rendered prompt_text.")
    workflow_run.add_argument("--output", type=Path)
    workflow_run.add_argument("--format", choices=["json", "markdown"], default="json")
    efficiency = sub.add_parser("efficiency-report", help="Measure workflow-run token savings against available context baselines.")
    efficiency.add_argument("--input", type=Path, required=True)
    efficiency.add_argument("--baseline", type=Path, action="append", default=[])
    efficiency.add_argument("--output", type=Path)
    efficiency.add_argument("--format", choices=["json", "markdown"], default="json")
    efficiency_gate = sub.add_parser("efficiency-gate", help="Evaluate an efficiency report against token-budget policy thresholds.")
    efficiency_gate.add_argument("--input", type=Path, required=True)
    efficiency_gate.add_argument("--policy", type=Path)
    efficiency_gate.add_argument("--max-read-first-tokens", type=int)
    efficiency_gate.add_argument("--max-gate-pass-tokens", type=int)
    efficiency_gate.add_argument("--max-read-first-ratio", type=float)
    efficiency_gate.add_argument("--max-gate-pass-ratio", type=float)
    efficiency_gate.add_argument("--min-read-first-savings-percent", type=float)
    efficiency_gate.add_argument("--min-gate-pass-savings-percent", type=float)
    efficiency_gate.add_argument("--require-artifact-role", action="append")
    efficiency_gate.add_argument("--output", type=Path)
    efficiency_gate.add_argument("--format", choices=["json", "markdown"], default="json")
    agent_ci = sub.add_parser("decide-continuation", help="Run workflow, efficiency report, and efficiency gate into one continuation decision.")
    agent_ci.add_argument("--root", type=Path, default=Path.cwd())
    agent_ci.add_argument("--output-dir", type=Path, default=Path(".dcf"))
    agent_ci.add_argument("--manifest", type=Path, action="append", default=[])
    agent_ci.add_argument("--task", required=True)
    agent_ci.add_argument("--target", action="append", default=[])
    agent_ci.add_argument("--targets-file", type=Path)
    agent_ci.add_argument("--quality-policy", type=Path)
    agent_ci.add_argument("--target-review-policy", type=Path)
    agent_ci.add_argument("--efficiency-policy", type=Path)
    agent_ci.add_argument("--baseline", type=Path, action="append", default=[])
    agent_ci.add_argument("--token-budget", type=int, default=4000)
    agent_ci.add_argument("--query-limit", type=int, default=10)
    agent_ci.add_argument("--max-presets", type=int, default=3)
    agent_ci.add_argument("--max-rows", type=int, default=80)
    agent_ci.add_argument("--max-files", type=int, default=5000)
    agent_ci.add_argument("--max-parse-bytes", type=int, default=1_000_000)
    agent_ci.add_argument("--hash-files", action="store_true")
    add_memory_import_args(agent_ci)
    agent_ci.add_argument("--include-details", action="store_true", help="Include full target adjudication details inside target review.")
    agent_ci.add_argument("--no-prompt", action="store_true", help="Skip rendered prompt_text.")
    agent_ci.add_argument("--output", type=Path)
    agent_ci.add_argument("--format", choices=["json", "markdown"], default="json")
    agent_context = sub.add_parser("pack-model-context", help="Bundle selected continuation read-plan artifacts into one bounded model context.")
    agent_context.add_argument("--input", type=Path, required=True)
    agent_context.add_argument("--mode", choices=["read-first", "decision-allowed", "all"], default="read-first")
    agent_context.add_argument("--token-budget", type=int, default=4000)
    agent_context.add_argument("--max-artifact-tokens", type=int, default=1200)
    agent_context.add_argument("--no-content", action="store_true", help="Emit metadata-only sections without embedding artifact content.")
    agent_context.add_argument("--no-prompt", action="store_true", help="Skip rendered prompt_text.")
    agent_context.add_argument("--output", type=Path)
    agent_context.add_argument("--format", choices=["json", "markdown"], default="json")
    agent_context_gate = sub.add_parser("gate-model-context", help="Evaluate a model-context bundle against token and artifact policy thresholds.")
    agent_context_gate.add_argument("--input", type=Path, required=True)
    agent_context_gate.add_argument("--policy", type=Path)
    agent_context_gate.add_argument("--max-missing-artifacts", type=int)
    agent_context_gate.add_argument("--max-skipped-artifacts", type=int)
    agent_context_gate.add_argument("--max-truncated-artifacts", type=int)
    agent_context_gate.add_argument("--max-selected-tokens", type=int)
    agent_context_gate.add_argument("--max-prompt-tokens", type=int)
    agent_context_gate.add_argument("--require-schema-version", action="append")
    agent_context_gate.add_argument("--output", type=Path)
    agent_context_gate.add_argument("--format", choices=["json", "markdown"], default="json")
    agent_handoff = sub.add_parser("prepare-model-handoff", help="Run continuation, context packing, and context gate checks into one gated model handoff.")
    agent_handoff.add_argument("--root", type=Path, default=Path.cwd())
    agent_handoff.add_argument("--output-dir", type=Path, default=Path(".dcf"))
    agent_handoff.add_argument("--manifest", type=Path, action="append", default=[])
    agent_handoff.add_argument("--task", required=True)
    agent_handoff.add_argument("--target", action="append", default=[])
    agent_handoff.add_argument("--targets-file", type=Path)
    agent_handoff.add_argument("--quality-policy", type=Path)
    agent_handoff.add_argument("--target-review-policy", type=Path)
    agent_handoff.add_argument("--efficiency-policy", type=Path)
    agent_handoff.add_argument("--context-gate-policy", type=Path)
    agent_handoff.add_argument("--baseline", type=Path, action="append", default=[])
    agent_handoff.add_argument("--workflow-token-budget", type=int, default=4000)
    agent_handoff.add_argument("--context-token-budget", type=int, default=4000)
    agent_handoff.add_argument("--context-mode", choices=["read-first", "decision-allowed", "all"], default="read-first")
    agent_handoff.add_argument("--max-artifact-tokens", type=int, default=1200)
    agent_handoff.add_argument("--query-limit", type=int, default=10)
    agent_handoff.add_argument("--max-presets", type=int, default=3)
    agent_handoff.add_argument("--max-rows", type=int, default=80)
    agent_handoff.add_argument("--max-files", type=int, default=5000)
    agent_handoff.add_argument("--max-parse-bytes", type=int, default=1_000_000)
    agent_handoff.add_argument("--hash-files", action="store_true")
    add_memory_import_args(agent_handoff)
    agent_handoff.add_argument("--include-details", action="store_true", help="Include full target adjudication details inside target review.")
    agent_handoff.add_argument("--no-content", action="store_true", help="Emit metadata-only context sections.")
    agent_handoff.add_argument("--no-prompt", action="store_true", help="Skip rendered prompt_text fields.")
    agent_handoff.add_argument("--output", type=Path)
    agent_handoff.add_argument("--format", choices=["json", "markdown"], default="json")
    verify_handoff = sub.add_parser("verify-model-handoff", help="Verify a generated model-handoff artifact before model use.")
    verify_handoff.add_argument("--input", type=Path, required=True)
    verify_handoff.add_argument("--output", type=Path)
    verify_handoff.add_argument("--format", choices=["json", "markdown"], default="json")
    agent_model_input = sub.add_parser("emit-model-input", help="Fail-closed reader that emits model prompt text only after handoff verification passes.")
    agent_model_input.add_argument("--input", type=Path, required=True)
    agent_model_input.add_argument("--output", type=Path)
    agent_model_input.add_argument("--no-prompt", action="store_true", help="Verify and emit metadata without embedding prompt_text.")
    agent_model_input.add_argument("--format", choices=["json", "markdown", "prompt"], default="json")
    agent_profile = sub.add_parser("validate-run-profile", help="Validate and normalize a model-input run profile for global wrappers.")
    agent_profile.add_argument("--profile", type=Path, required=True)
    agent_profile.add_argument("--output", type=Path)
    agent_profile.add_argument("--format", choices=["json", "markdown"], default="json")
    agent_profile_init = sub.add_parser("init-run-profile", help="Generate a validated model-input run profile for global wrappers.")
    agent_profile_init.add_argument("--root", type=Path, default=Path.cwd())
    agent_profile_init.add_argument("--output", type=Path, default=Path(".dcf") / "agent_ready_profile.json", help="Profile JSON path to write.")
    agent_profile_init.add_argument("--profile-id", default="")
    agent_profile_init.add_argument("--description", default="")
    agent_profile_init.add_argument("--task", required=True)
    agent_profile_init.add_argument("--target", action="append", default=[])
    agent_profile_init.add_argument("--targets-file", type=Path)
    agent_profile_init.add_argument("--manifest", type=Path, action="append", default=[])
    agent_profile_init.add_argument("--handoff", type=Path)
    agent_profile_init.add_argument("--output-dir", type=Path)
    agent_profile_init.add_argument("--quality-policy", type=Path)
    agent_profile_init.add_argument("--target-review-policy", type=Path)
    agent_profile_init.add_argument("--efficiency-policy", type=Path)
    agent_profile_init.add_argument("--context-gate-policy", type=Path)
    agent_profile_init.add_argument("--baseline", type=Path, action="append", default=[])
    agent_profile_init.add_argument("--workflow-token-budget", type=int, default=4000)
    agent_profile_init.add_argument("--context-token-budget", type=int, default=4000)
    agent_profile_init.add_argument("--context-mode", choices=["read-first", "decision-allowed", "all"], default="read-first")
    agent_profile_init.add_argument("--max-artifact-tokens", type=int, default=1200)
    agent_profile_init.add_argument("--query-limit", type=int, default=10)
    agent_profile_init.add_argument("--max-presets", type=int, default=3)
    agent_profile_init.add_argument("--max-rows", type=int, default=80)
    agent_profile_init.add_argument("--max-files", type=int, default=5000)
    agent_profile_init.add_argument("--max-parse-bytes", type=int, default=1_000_000)
    agent_profile_init.add_argument("--hash-files", action="store_true")
    add_memory_import_args(agent_profile_init)
    agent_profile_init.add_argument("--include-details", action="store_true")
    agent_profile_init.add_argument("--no-content", action="store_true")
    agent_profile_init.add_argument("--no-prompt", action="store_true")
    agent_profile_init.add_argument("--format", choices=["json", "markdown"], default="json")
    agent_onboard = sub.add_parser("onboard-runner", help="Generate a run profile and run the fail-closed model-input path in one wrapper command.")
    agent_onboard.add_argument("--root", type=Path, default=Path.cwd())
    agent_onboard.add_argument("--profile-output", type=Path, default=Path(".dcf") / "agent_ready_profile.json")
    agent_onboard.add_argument("--output", type=Path, help="Optional runner onboarding capsule JSON path.")
    agent_onboard.add_argument("--profile-id", default="")
    agent_onboard.add_argument("--description", default="")
    agent_onboard.add_argument("--task", required=True)
    agent_onboard.add_argument("--target", action="append", default=[])
    agent_onboard.add_argument("--targets-file", type=Path)
    agent_onboard.add_argument("--manifest", type=Path, action="append", default=[])
    agent_onboard.add_argument("--handoff", type=Path)
    agent_onboard.add_argument("--output-dir", type=Path)
    agent_onboard.add_argument("--quality-policy", type=Path)
    agent_onboard.add_argument("--target-review-policy", type=Path)
    agent_onboard.add_argument("--efficiency-policy", type=Path)
    agent_onboard.add_argument("--context-gate-policy", type=Path)
    agent_onboard.add_argument("--baseline", type=Path, action="append", default=[])
    agent_onboard.add_argument("--workflow-token-budget", type=int, default=4000)
    agent_onboard.add_argument("--context-token-budget", type=int, default=4000)
    agent_onboard.add_argument("--context-mode", choices=["read-first", "decision-allowed", "all"], default="read-first")
    agent_onboard.add_argument("--max-artifact-tokens", type=int, default=1200)
    agent_onboard.add_argument("--query-limit", type=int, default=10)
    agent_onboard.add_argument("--max-presets", type=int, default=3)
    agent_onboard.add_argument("--max-rows", type=int, default=80)
    agent_onboard.add_argument("--max-files", type=int, default=5000)
    agent_onboard.add_argument("--max-parse-bytes", type=int, default=1_000_000)
    agent_onboard.add_argument("--hash-files", action="store_true")
    add_memory_import_args(agent_onboard)
    agent_onboard.add_argument("--include-details", action="store_true")
    agent_onboard.add_argument("--no-content", action="store_true")
    agent_onboard.add_argument("--no-prompt", action="store_true")
    agent_onboard.add_argument("--format", choices=["json", "markdown"], default="json")
    agent_discover = sub.add_parser("discover-model-readiness", help="Discover repo-local DCF handoff readiness for global wrappers.")
    agent_discover.add_argument("--root", type=Path, default=Path.cwd())
    agent_discover.add_argument("--handoff", type=Path)
    agent_discover.add_argument("--output", type=Path)
    agent_discover.add_argument("--format", choices=["json", "markdown"], default="json")
    agent_route = sub.add_parser("route-model-readiness", help="Normalize DCF discovery into a global-wrapper route decision.")
    agent_route.add_argument("--root", type=Path, default=Path.cwd())
    agent_route.add_argument("--task", default="")
    agent_route.add_argument("--target", action="append", default=[])
    agent_route.add_argument("--handoff", type=Path)
    agent_route.add_argument("--output-dir", type=Path, default=Path(".dcf"))
    agent_route.add_argument("--output", type=Path)
    agent_route.add_argument("--format", choices=["json", "markdown"], default="json")
    agent_ready = sub.add_parser("prepare-model-input", help="Fail-closed DCF pipeline that emits model prompt text only when gates pass.")
    agent_ready.add_argument("--profile", type=Path, help="Optional machine-readable defaults for global wrappers.")
    agent_ready.add_argument("--root", type=Path, default=Path.cwd())
    agent_ready.add_argument("--output-dir", type=Path, default=Path(".dcf"))
    agent_ready.add_argument("--manifest", type=Path, action="append", default=[])
    agent_ready.add_argument("--task", default="")
    agent_ready.add_argument("--target", action="append", default=[])
    agent_ready.add_argument("--targets-file", type=Path)
    agent_ready.add_argument("--handoff", type=Path)
    agent_ready.add_argument("--quality-policy", type=Path)
    agent_ready.add_argument("--target-review-policy", type=Path)
    agent_ready.add_argument("--efficiency-policy", type=Path)
    agent_ready.add_argument("--context-gate-policy", type=Path)
    agent_ready.add_argument("--baseline", type=Path, action="append", default=[])
    agent_ready.add_argument("--workflow-token-budget", type=int, default=4000)
    agent_ready.add_argument("--context-token-budget", type=int, default=4000)
    agent_ready.add_argument("--context-mode", choices=["read-first", "decision-allowed", "all"], default="read-first")
    agent_ready.add_argument("--max-artifact-tokens", type=int, default=1200)
    agent_ready.add_argument("--query-limit", type=int, default=10)
    agent_ready.add_argument("--max-presets", type=int, default=3)
    agent_ready.add_argument("--max-rows", type=int, default=80)
    agent_ready.add_argument("--max-files", type=int, default=5000)
    agent_ready.add_argument("--max-parse-bytes", type=int, default=1_000_000)
    agent_ready.add_argument("--hash-files", action="store_true")
    add_memory_import_args(agent_ready)
    agent_ready.add_argument("--include-details", action="store_true", help="Include full target adjudication details inside target review.")
    agent_ready.add_argument("--no-content", action="store_true", help="Emit metadata-only context sections.")
    agent_ready.add_argument("--no-prompt", action="store_true", help="Verify and emit metadata without embedding prompt_text.")
    agent_ready.add_argument("--output", type=Path)
    agent_ready.add_argument("--format", choices=["json", "markdown", "prompt"], default="json")
    validate = sub.add_parser("validate-manifest", help="Validate manifest shape before reading sources.")
    validate.add_argument("--manifest", type=Path, default=Path("deep_context_federation.json"))
    validate.add_argument("--json", action="store_true")
    compose = sub.add_parser("compose-manifest", help="Compose multiple federation manifests into one manifest.")
    compose.add_argument("--manifest", type=Path, action="append", required=True)
    compose.add_argument("--output", type=Path, default=Path(".dcf") / "deep_context_federation.composed.json")
    compose.add_argument("--write", action="store_true")
    compose.add_argument("--format", choices=["json", "markdown"], default="json")
    verify = sub.add_parser("verify", help="Verify a federation artifact.")
    verify.add_argument("--input", type=Path, default=Path(".dcf") / DEFAULT_JSON_NAME)
    verify.add_argument("--manifest", type=Path, default=Path("deep_context_federation.json"))
    verify.add_argument("--root", type=Path, default=Path.cwd())
    verify.add_argument("--json", action="store_true")
    query = sub.add_parser("query", help="Query a federation artifact with a named preset.")
    query.add_argument("--input", type=Path, default=Path(".dcf") / DEFAULT_JSON_NAME)
    query.add_argument("--preset", required=True)
    query.add_argument("--limit", type=int, default=50)
    query.add_argument("--format", choices=["json", "markdown"], default="json")
    pack = sub.add_parser("pack", help="Build a token-aware bounded context pack for a task.")
    pack.add_argument("--input", type=Path, default=Path(".dcf") / DEFAULT_JSON_NAME)
    pack.add_argument("--task", required=True)
    pack.add_argument("--token-budget", type=int, default=4000)
    pack.add_argument("--min-score", type=int, default=0)
    pack.add_argument("--max-rows", type=int, default=80)
    pack.add_argument("--no-prompt", action="store_true", help="Emit scored JSON rows without the rendered prompt_text field.")
    pack.add_argument("--output", type=Path)
    pack.add_argument("--format", choices=["json", "markdown"], default="json")
    brief = sub.add_parser("brief", help="Build a one-shot task routing brief with queries, doctor summary, and prompt pack.")
    brief.add_argument("--input", type=Path, default=Path(".dcf") / DEFAULT_JSON_NAME)
    brief.add_argument("--task", required=True)
    brief.add_argument("--token-budget", type=int, default=4000)
    brief.add_argument("--query-limit", type=int, default=10)
    brief.add_argument("--max-presets", type=int, default=3)
    brief.add_argument("--max-rows", type=int, default=80)
    brief.add_argument("--no-prompt", action="store_true", help="Skip rendered prompt_text inside the embedded context_pack.")
    brief.add_argument("--output", type=Path)
    brief.add_argument("--format", choices=["json", "markdown"], default="json")
    trace = sub.add_parser("trace", help="Trace neighboring federation entities by text match.")
    trace.add_argument("--input", type=Path, default=Path(".dcf") / DEFAULT_JSON_NAME)
    trace.add_argument("--match", required=True)
    trace.add_argument("--depth", type=int, default=2)
    trace.add_argument("--limit", type=int, default=50)
    trace.add_argument("--format", choices=["json", "markdown"], default="json")
    resolve = sub.add_parser("resolve", help="Resolve a claim/path/surface/symbol target into an evidence card.")
    resolve.add_argument("--input", type=Path, default=Path(".dcf") / DEFAULT_JSON_NAME)
    resolve.add_argument("--target", required=True)
    resolve.add_argument("--limit", type=int, default=20)
    resolve.add_argument("--token-budget", type=int, default=2500)
    resolve.add_argument("--no-prompt", action="store_true", help="Skip rendered prompt_text and embedded context prompt.")
    resolve.add_argument("--output", type=Path)
    resolve.add_argument("--format", choices=["json", "markdown"], default="json")
    adjudicate = sub.add_parser("adjudicate", help="Adjudicate a target into authority/evidence/advisory support and a deterministic verdict.")
    adjudicate.add_argument("--input", type=Path, default=Path(".dcf") / DEFAULT_JSON_NAME)
    adjudicate.add_argument("--target", required=True)
    adjudicate.add_argument("--limit", type=int, default=20)
    adjudicate.add_argument("--token-budget", type=int, default=2500)
    adjudicate.add_argument("--no-prompt", action="store_true", help="Skip rendered prompt_text.")
    adjudicate.add_argument("--output", type=Path)
    adjudicate.add_argument("--format", choices=["json", "markdown"], default="json")
    review_targets_parser = sub.add_parser("review-targets", help="Batch adjudicate targets and rank governance/context risk.")
    review_targets_parser.add_argument("--input", type=Path, default=Path(".dcf") / DEFAULT_JSON_NAME)
    review_targets_parser.add_argument("--target", action="append", default=[])
    review_targets_parser.add_argument("--targets-file", type=Path)
    review_targets_parser.add_argument("--limit", type=int, default=20)
    review_targets_parser.add_argument("--token-budget", type=int, default=3000)
    review_targets_parser.add_argument("--include-details", action="store_true", help="Include full per-target adjudication payloads.")
    review_targets_parser.add_argument("--no-prompt", action="store_true", help="Skip rendered prompt_text.")
    review_targets_parser.add_argument("--output", type=Path)
    review_targets_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    review_gate = sub.add_parser("review-gate", help="Evaluate a target review artifact against CI/agent policy.")
    review_gate.add_argument("--input", type=Path, required=True)
    review_gate.add_argument("--policy", type=Path)
    review_gate.add_argument("--max-blocked", type=int)
    review_gate.add_argument("--max-no-match", type=int)
    review_gate.add_argument("--max-advisory-only", type=int)
    review_gate.add_argument("--max-warn", type=int)
    review_gate.add_argument("--max-priority-score", type=int)
    review_gate.add_argument("--min-average-confidence", type=float)
    review_gate.add_argument("--disallow-risk", action="append", dest="disallow_risk_flag")
    review_gate.add_argument("--require-target", action="append")
    review_gate.add_argument("--output", type=Path)
    review_gate.add_argument("--format", choices=["json", "markdown"], default="json")
    doctor = sub.add_parser("doctor", help="Diagnose federation health and recommend next actions.")
    doctor.add_argument("--input", type=Path, default=Path(".dcf") / DEFAULT_JSON_NAME)
    doctor.add_argument("--format", choices=["json", "markdown"], default="json")
    gate = sub.add_parser("quality-gate", help="Evaluate CI/agent quality gates on a bootstrap or federation artifact.")
    gate.add_argument("--input", type=Path, default=Path(".dcf") / "deep_context_federation_bootstrap.json")
    gate.add_argument("--federation-input", type=Path)
    gate.add_argument("--policy", type=Path, help="JSON policy-as-code file for repeatable quality gates.")
    gate.add_argument("--min-sources", type=int)
    gate.add_argument("--min-entities", type=int)
    gate.add_argument("--min-edges", type=int)
    gate.add_argument("--max-errors", type=int)
    gate.add_argument("--max-warnings", type=int)
    gate.add_argument("--max-duration-seconds", type=float)
    gate.add_argument("--max-scan-duration-seconds", type=float)
    gate.add_argument("--require-role", action="append")
    gate.add_argument("--require-source", action="append")
    gate.add_argument("--require-query-preset", action="append")
    gate.add_argument("--no-bootstrap-step-check", action="store_true")
    gate.add_argument("--output", type=Path)
    gate.add_argument("--format", choices=["json", "markdown"], default="json")
    rank = sub.add_parser("rank", help="Rank important entities or risky sources.")
    rank.add_argument("--input", type=Path, default=Path(".dcf") / DEFAULT_JSON_NAME)
    rank.add_argument("--kind", choices=["entities", "sources"], default="entities")
    rank.add_argument("--limit", type=int, default=20)
    rank.add_argument("--format", choices=["json", "markdown"], default="json")
    diff = sub.add_parser("diff", help="Diff two federation artifacts.")
    diff.add_argument("--before", type=Path, required=True)
    diff.add_argument("--after", type=Path, required=True)
    diff.add_argument("--format", choices=["json", "markdown"], default="json")
    sql = sub.add_parser("sql", help="Query the generated SQLite read model.")
    sql.add_argument("--sqlite", type=Path, default=Path(".dcf") / "deep_context_federation_latest.sqlite")
    sql.add_argument("--preset", choices=sorted(SQL_PRESETS), required=True)
    sql.add_argument("--limit", type=int, default=50)
    sql.add_argument("--search", default="")
    sql.add_argument("--format", choices=["json", "markdown"], default="json")
    bench = sub.add_parser("bench", help="Benchmark in-memory federation build time.")
    add_common_source_args(bench)
    bench.add_argument("--iterations", type=int, default=5)
    bench.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(_normalize_command_argv(argv))
    if args.command == "capabilities":
        result = build_capabilities()
        if args.output:
            result["outputs"] = {"capabilities_json": args.output.expanduser().resolve().as_posix()}
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_capabilities(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0
    if args.command == "schema":
        if args.artifact:
            result = schema_for_artifact(args.artifact)
            if args.output:
                write_json(args.output, result)
            if args.format == "markdown":
                print(markdown_json_schema(result, artifact_kind=args.artifact))
            else:
                print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        else:
            result = build_schema_registry()
            if args.output:
                result["outputs"] = {"schema_registry_json": args.output.expanduser().resolve().as_posix()}
                write_json(args.output, result)
            if args.format == "markdown":
                print(markdown_schema_registry(result))
            else:
                print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0
    if args.command == "validate-artifact":
        payload = read_required_json(args.input)
        result = validate_artifact_contract(payload, artifact_kind=args.artifact)
        if args.output:
            result["outputs"] = {"contract_validation_json": args.output.expanduser().resolve().as_posix()}
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_contract_validation(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "plan-native-ownership":
        result = build_native_integration_plan(capabilities=args.capability)
        if args.output:
            result["outputs"] = {"native_integration_plan_json": args.output.expanduser().resolve().as_posix()}
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_native_integration_plan(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "index-context-memory":
        result = build_memory_ledger(
            root=args.root,
            input_dirs=args.input_dir,
            input_files=args.input_file,
            max_files=args.max_files,
        )
        if args.output:
            result["outputs"] = {"memory_ledger_json": args.output.expanduser().resolve().as_posix()}
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_memory_ledger(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "unify-context":
        federation = read_required_json(args.input)
        memory = read_required_json(args.memory_ledger) if args.memory_ledger else {}
        capabilities = read_required_json(args.capabilities) if args.capabilities else {}
        native_plan = read_required_json(args.native_plan) if args.native_plan else {}
        result = build_unified_index(
            federation=federation,
            federation_path=args.input.expanduser().resolve().as_posix(),
            memory_ledger=memory,
            memory_ledger_path=args.memory_ledger.expanduser().resolve().as_posix() if args.memory_ledger else "",
            capabilities=capabilities,
            capabilities_path=args.capabilities.expanduser().resolve().as_posix() if args.capabilities else "",
            native_plan=native_plan,
            native_plan_path=args.native_plan.expanduser().resolve().as_posix() if args.native_plan else "",
            limit=args.limit,
            query=args.query,
        )
        if args.output:
            result["outputs"] = {"unified_index_json": args.output.expanduser().resolve().as_posix()}
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_unified_index(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "select-context":
        unified_index = read_required_json(args.input)
        result = build_unified_working_set(
            unified_index=unified_index,
            unified_index_path=args.input.expanduser().resolve().as_posix(),
            query=args.query,
            limit=args.limit,
            label_chars=args.label_chars,
            value_chars=args.value_chars,
            max_tokens=args.max_tokens,
            facet_mode=args.facet_mode,
            min_facets=args.min_facets,
        )
        if args.output:
            result["outputs"] = {"selected_context_json": args.output.expanduser().resolve().as_posix()}
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_unified_working_set(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "validate-manifest":
        manifest = read_json(args.manifest)
        result = validate_manifest(manifest, manifest_path=args.manifest)
        if args.json:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        else:
            print(f"{result['status']} errors={result['error_count']} sources={result['source_count']}")
        return 0 if result["ok"] else 2
    if args.command == "compose-manifest":
        result = compose_manifests(args.manifest, output_path=args.output, write=args.write)
        if args.format == "markdown":
            print(markdown_compose(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "build":
        payload = build_federation(
            manifest_path=args.manifest,
            root=args.root,
            output_dir=args.output_dir,
            include_codebase_memory=args.include_codebase_memory,
            codebase_memory_cache_dir=args.codebase_memory_cache_dir,
            write=args.write,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        else:
            summary = payload["summary"]
            print(
                "{} errors={} warnings={} sources={} entities={} edges={}".format(
                    payload["status"],
                    summary["error_count"],
                    summary["warning_count"],
                    summary["source_count"],
                    summary["entity_count"],
                    summary["edge_count"],
                )
            )
        return 0 if payload["ok"] else 2
    if args.command == "bootstrap":
        result = bootstrap_federation(
            root=args.root,
            output_dir=args.output_dir,
            manifests=args.manifest,
            max_files=args.max_files,
            max_parse_bytes=args.max_parse_bytes,
            include_hashes=args.hash_files,
            include_codebase_memory=args.include_codebase_memory,
            codebase_memory_cache_dir=args.codebase_memory_cache_dir,
            write=True,
        )
        if args.format == "markdown":
            print(markdown_bootstrap(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "intake":
        policy = load_quality_gate_policy(args.policy) if args.policy else None
        result = build_agent_intake(
            root=args.root,
            output_dir=args.output_dir,
            manifests=args.manifest,
            task=args.task,
            quality_gate_policy=policy,
            max_files=args.max_files,
            max_parse_bytes=args.max_parse_bytes,
            include_hashes=args.hash_files,
            include_codebase_memory=args.include_codebase_memory,
            codebase_memory_cache_dir=args.codebase_memory_cache_dir,
            token_budget=args.token_budget,
            query_limit=args.query_limit,
            max_presets=args.max_presets,
            max_rows=args.max_rows,
            include_prompt=not args.no_prompt,
            write=True,
        )
        if args.format == "markdown":
            print(markdown_agent_intake(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "workflow-plan":
        targets = list(args.target or [])
        if args.targets_file:
            targets.extend(read_targets_file(args.targets_file))
        result = build_workflow_plan(
            task=args.task,
            root=args.root,
            output_dir=args.output_dir,
            targets=targets,
            quality_policy=args.quality_policy,
            target_review_policy=args.target_review_policy,
            token_budget=args.token_budget,
            query_limit=args.query_limit,
            max_presets=args.max_presets,
            max_rows=args.max_rows,
            max_files=args.max_files,
            max_parse_bytes=args.max_parse_bytes,
            include_hashes=args.hash_files,
            include_codebase_memory=args.include_codebase_memory,
            codebase_memory_cache_dir=args.codebase_memory_cache_dir,
            include_prompt=not args.no_prompt,
        )
        if args.output:
            result["outputs"]["workflow_plan_json"] = args.output.expanduser().resolve().as_posix()
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_workflow_plan(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0
    if args.command == "workflow-run":
        targets = list(args.target or [])
        if args.targets_file:
            targets.extend(read_targets_file(args.targets_file))
        quality_policy = load_quality_gate_policy(args.quality_policy) if args.quality_policy else None
        target_policy = load_target_review_gate_policy(args.target_review_policy) if args.target_review_policy else None
        result = build_workflow_run(
            root=args.root,
            output_dir=args.output_dir,
            manifests=args.manifest,
            task=args.task,
            targets=targets,
            quality_gate_policy=quality_policy,
            target_review_gate_policy=target_policy,
            quality_policy_path=args.quality_policy,
            target_review_policy_path=args.target_review_policy,
            token_budget=args.token_budget,
            query_limit=args.query_limit,
            max_presets=args.max_presets,
            max_rows=args.max_rows,
            max_files=args.max_files,
            max_parse_bytes=args.max_parse_bytes,
            include_hashes=args.hash_files,
            include_codebase_memory=args.include_codebase_memory,
            codebase_memory_cache_dir=args.codebase_memory_cache_dir,
            include_details=args.include_details,
            include_prompt=not args.no_prompt,
        )
        if args.output:
            original_output = str(result["outputs"].get("workflow_run_json") or "")
            resolved_output = args.output.expanduser().resolve().as_posix()
            result["outputs"]["workflow_run_json"] = resolved_output
            handoff = result.get("model_handoff") if isinstance(result.get("model_handoff"), dict) else {}
            if isinstance(handoff.get("read_first"), list):
                handoff["read_first"] = [resolved_output if item == original_output else item for item in handoff["read_first"]]
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_workflow_run(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "efficiency-report":
        payload = read_required_json(args.input)
        result = build_efficiency_report(
            payload,
            workflow_run_path=args.input,
            extra_baselines=args.baseline,
        )
        if args.output:
            result["outputs"] = {"efficiency_report_json": args.output.expanduser().resolve().as_posix()}
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_efficiency_report(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "efficiency-gate":
        payload = read_required_json(args.input)
        policy = load_efficiency_gate_policy(args.policy) if args.policy else None
        result = evaluate_efficiency_gate(
            payload,
            policy=policy,
            max_read_first_tokens=args.max_read_first_tokens,
            max_gate_pass_tokens=args.max_gate_pass_tokens,
            max_read_first_ratio=args.max_read_first_ratio,
            max_gate_pass_ratio=args.max_gate_pass_ratio,
            min_read_first_savings_percent=args.min_read_first_savings_percent,
            min_gate_pass_savings_percent=args.min_gate_pass_savings_percent,
            require_artifact_roles=args.require_artifact_role,
        )
        if args.output:
            result["outputs"] = {"efficiency_gate_json": args.output.expanduser().resolve().as_posix()}
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_efficiency_gate(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "decide-continuation":
        targets = list(args.target or [])
        if args.targets_file:
            targets.extend(read_targets_file(args.targets_file))
        quality_policy = load_quality_gate_policy(args.quality_policy) if args.quality_policy else None
        target_policy = load_target_review_gate_policy(args.target_review_policy) if args.target_review_policy else None
        efficiency_policy = load_efficiency_gate_policy(args.efficiency_policy) if args.efficiency_policy else None
        result = build_agent_ci(
            root=args.root,
            output_dir=args.output_dir,
            manifests=args.manifest,
            task=args.task,
            targets=targets,
            quality_gate_policy=quality_policy,
            target_review_gate_policy=target_policy,
            efficiency_gate_policy=efficiency_policy,
            quality_policy_path=args.quality_policy,
            target_review_policy_path=args.target_review_policy,
            token_budget=args.token_budget,
            query_limit=args.query_limit,
            max_presets=args.max_presets,
            max_rows=args.max_rows,
            max_files=args.max_files,
            max_parse_bytes=args.max_parse_bytes,
            include_hashes=args.hash_files,
            include_codebase_memory=args.include_codebase_memory,
            codebase_memory_cache_dir=args.codebase_memory_cache_dir,
            include_details=args.include_details,
            include_prompt=not args.no_prompt,
            extra_baselines=args.baseline,
        )
        if args.output:
            original_output = str(result["outputs"].get("agent_ci_json") or "")
            resolved_output = args.output.expanduser().resolve().as_posix()
            result["outputs"]["agent_ci_json"] = resolved_output
            next_reads = result.get("next_reads") if isinstance(result.get("next_reads"), dict) else {}
            if isinstance(next_reads.get("read_first"), list):
                next_reads["read_first"] = [resolved_output if item == original_output else item for item in next_reads["read_first"]]
            read_plan = result.get("artifact_read_plan") if isinstance(result.get("artifact_read_plan"), dict) else {}
            for row in read_plan.get("rows") or []:
                if isinstance(row, dict):
                    if row.get("artifact_ref") == original_output:
                        row["artifact_ref"] = resolved_output
                    if row.get("path") == original_output:
                        row["path"] = resolved_output
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_agent_ci(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "pack-model-context":
        payload = read_required_json(args.input)
        result = build_agent_context(
            payload,
            agent_ci_path=args.input,
            mode=args.mode,
            token_budget=args.token_budget,
            max_artifact_tokens=args.max_artifact_tokens,
            include_content=not args.no_content,
            include_prompt=not args.no_prompt,
        )
        if args.output:
            result["outputs"] = {"agent_context_json": args.output.expanduser().resolve().as_posix()}
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_agent_context(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "gate-model-context":
        payload = read_required_json(args.input)
        policy = load_agent_context_gate_policy(args.policy) if args.policy else None
        result = evaluate_agent_context_gate(
            payload,
            policy=policy,
            max_missing_artifacts=args.max_missing_artifacts,
            max_skipped_artifacts=args.max_skipped_artifacts,
            max_truncated_artifacts=args.max_truncated_artifacts,
            max_selected_tokens=args.max_selected_tokens,
            max_prompt_tokens=args.max_prompt_tokens,
            require_schema_versions=args.require_schema_version,
        )
        if args.output:
            result["outputs"] = {"agent_context_gate_json": args.output.expanduser().resolve().as_posix()}
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_agent_context_gate(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "prepare-model-handoff":
        targets = list(args.target or [])
        if args.targets_file:
            targets.extend(read_targets_file(args.targets_file))
        quality_policy = load_quality_gate_policy(args.quality_policy) if args.quality_policy else None
        target_policy = load_target_review_gate_policy(args.target_review_policy) if args.target_review_policy else None
        efficiency_policy = load_efficiency_gate_policy(args.efficiency_policy) if args.efficiency_policy else None
        context_gate_policy = load_agent_context_gate_policy(args.context_gate_policy) if args.context_gate_policy else None
        result = build_agent_handoff(
            root=args.root,
            output_dir=args.output_dir,
            manifests=args.manifest,
            task=args.task,
            targets=targets,
            quality_gate_policy=quality_policy,
            target_review_gate_policy=target_policy,
            efficiency_gate_policy=efficiency_policy,
            agent_context_gate_policy=context_gate_policy,
            quality_policy_path=args.quality_policy,
            target_review_policy_path=args.target_review_policy,
            workflow_token_budget=args.workflow_token_budget,
            context_token_budget=args.context_token_budget,
            context_mode=args.context_mode,
            max_artifact_tokens=args.max_artifact_tokens,
            query_limit=args.query_limit,
            max_presets=args.max_presets,
            max_rows=args.max_rows,
            max_files=args.max_files,
            max_parse_bytes=args.max_parse_bytes,
            include_hashes=args.hash_files,
            include_codebase_memory=args.include_codebase_memory,
            codebase_memory_cache_dir=args.codebase_memory_cache_dir,
            include_content=not args.no_content,
            include_prompt=not args.no_prompt,
            include_details=args.include_details,
            extra_baselines=args.baseline,
        )
        if args.output:
            original_output = str(result["outputs"].get("agent_handoff_json") or "")
            resolved_output = args.output.expanduser().resolve().as_posix()
            result["outputs"]["agent_handoff_json"] = resolved_output
            model_handoff = result.get("model_handoff") if isinstance(result.get("model_handoff"), dict) else {}
            if isinstance(model_handoff.get("read_first"), list):
                model_handoff["read_first"] = [resolved_output if item == original_output else item for item in model_handoff["read_first"]]
            write_json(args.output, result)
            verification = verify_agent_handoff(result, handoff_path=args.output)
            verification_json = Path(str(result["outputs"].get("agent_handoff_verification_json") or "")).expanduser()
            verification_markdown = Path(str(result["outputs"].get("agent_handoff_verification_markdown") or "")).expanduser()
            if verification_json:
                write_json(verification_json, verification)
            if verification_markdown:
                write_markdown(verification_markdown, markdown_agent_handoff_verification(verification).splitlines())
            result["agent_handoff_verification_summary"] = {
                "schema_version": verification.get("schema_version"),
                "status": verification.get("status"),
                "ok": verification.get("ok"),
                "summary": dict(verification.get("summary") if isinstance(verification.get("summary"), dict) else {}),
            }
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_agent_handoff(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "verify-model-handoff":
        payload = read_required_json(args.input)
        result = verify_agent_handoff(payload, handoff_path=args.input)
        if args.output:
            result["outputs"] = {"agent_handoff_verification_json": args.output.expanduser().resolve().as_posix()}
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_agent_handoff_verification(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "emit-model-input":
        payload = read_required_json(args.input)
        result = build_agent_model_input(payload, handoff_path=args.input, include_prompt=not args.no_prompt)
        if args.output:
            result["outputs"] = {"agent_model_input_json": args.output.expanduser().resolve().as_posix()}
            write_json(args.output, result)
        if args.format == "prompt":
            if result["ok"]:
                print(result.get("prompt_text") or "", end="" if str(result.get("prompt_text") or "").endswith("\n") else "\n")
        elif args.format == "markdown":
            print(markdown_agent_model_input(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "validate-run-profile":
        result = load_agent_profile(args.profile)
        if args.output:
            result["outputs"] = {"agent_profile_json": args.output.expanduser().resolve().as_posix()}
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_agent_profile(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "init-run-profile":
        targets = list(args.target or [])
        if args.targets_file:
            targets.extend(read_targets_file(args.targets_file))
        result = build_agent_profile_init(
            root=args.root,
            profile_path=args.output,
            profile_id=args.profile_id,
            description=args.description,
            task=args.task,
            targets=targets,
            manifests=args.manifest,
            handoff_path=args.handoff,
            output_dir=args.output_dir,
            quality_policy_path=args.quality_policy,
            target_review_policy_path=args.target_review_policy,
            efficiency_policy_path=args.efficiency_policy,
            context_gate_policy_path=args.context_gate_policy,
            workflow_token_budget=args.workflow_token_budget,
            context_token_budget=args.context_token_budget,
            context_mode=args.context_mode,
            max_artifact_tokens=args.max_artifact_tokens,
            query_limit=args.query_limit,
            max_presets=args.max_presets,
            max_rows=args.max_rows,
            max_files=args.max_files,
            max_parse_bytes=args.max_parse_bytes,
            include_hashes=args.hash_files,
            include_codebase_memory=args.include_codebase_memory,
            codebase_memory_cache_dir=args.codebase_memory_cache_dir,
            include_details=args.include_details,
            include_content=not args.no_content,
            include_prompt=not args.no_prompt,
            extra_baselines=args.baseline,
            write=True,
        )
        if args.format == "markdown":
            print(markdown_agent_profile_init(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "onboard-runner":
        targets = list(args.target or [])
        if args.targets_file:
            targets.extend(read_targets_file(args.targets_file))
        result = build_agent_onboard(
            root=args.root,
            profile_path=args.profile_output,
            profile_id=args.profile_id,
            description=args.description,
            task=args.task,
            targets=targets,
            manifests=args.manifest,
            handoff_path=args.handoff,
            output_dir=args.output_dir,
            quality_policy_path=args.quality_policy,
            target_review_policy_path=args.target_review_policy,
            efficiency_policy_path=args.efficiency_policy,
            context_gate_policy_path=args.context_gate_policy,
            workflow_token_budget=args.workflow_token_budget,
            context_token_budget=args.context_token_budget,
            context_mode=args.context_mode,
            max_artifact_tokens=args.max_artifact_tokens,
            query_limit=args.query_limit,
            max_presets=args.max_presets,
            max_rows=args.max_rows,
            max_files=args.max_files,
            max_parse_bytes=args.max_parse_bytes,
            include_hashes=args.hash_files,
            include_codebase_memory=args.include_codebase_memory,
            codebase_memory_cache_dir=args.codebase_memory_cache_dir,
            include_details=args.include_details,
            include_content=not args.no_content,
            include_prompt=not args.no_prompt,
            extra_baselines=args.baseline,
        )
        if args.output:
            result["outputs"] = dict(result.get("outputs") if isinstance(result.get("outputs"), dict) else {})
            result["outputs"]["agent_onboard_json"] = args.output.expanduser().resolve().as_posix()
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_agent_onboard(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "discover-model-readiness":
        result = discover_agent_context(root=args.root, handoff_path=args.handoff)
        if args.output:
            result["outputs"] = {"agent_discovery_json": args.output.expanduser().resolve().as_posix()}
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_agent_discovery(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0
    if args.command == "route-model-readiness":
        result = route_agent_context(
            root=args.root,
            task=args.task,
            targets=args.target,
            handoff_path=args.handoff,
            output_dir=args.output_dir,
        )
        if args.output:
            result["outputs"] = {"agent_route_json": args.output.expanduser().resolve().as_posix()}
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_agent_route(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0
    if args.command == "prepare-model-input":
        profile = load_agent_profile(args.profile) if args.profile else {}
        if profile and profile.get("ok") is not True:
            result = _agent_ready_profile_failure(args=args, profile=profile)
            if args.output:
                result["outputs"] = {"agent_ready_json": args.output.expanduser().resolve().as_posix()}
                write_json(args.output, result)
            if args.format == "prompt":
                pass
            elif args.format == "markdown":
                print(markdown_agent_ready(result))
            else:
                print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
            return 2
        normalized = profile.get("normalized") if isinstance(profile.get("normalized"), Mapping) else {}
        ready_args = _resolve_agent_ready_args(args, normalized)
        quality_policy = load_quality_gate_policy(ready_args["quality_policy_path"]) if ready_args["quality_policy_path"] else None
        target_policy = load_target_review_gate_policy(ready_args["target_review_policy_path"]) if ready_args["target_review_policy_path"] else None
        efficiency_policy = load_efficiency_gate_policy(ready_args["efficiency_policy_path"]) if ready_args["efficiency_policy_path"] else None
        context_gate_policy = load_agent_context_gate_policy(ready_args["context_gate_policy_path"]) if ready_args["context_gate_policy_path"] else None
        result = build_agent_ready(
            root=ready_args["root"],
            output_dir=ready_args["output_dir"],
            manifests=ready_args["manifests"],
            task=ready_args["task"],
            targets=ready_args["targets"],
            handoff_path=ready_args["handoff_path"],
            quality_gate_policy=quality_policy,
            target_review_gate_policy=target_policy,
            efficiency_gate_policy=efficiency_policy,
            agent_context_gate_policy=context_gate_policy,
            quality_policy_path=ready_args["quality_policy_path"],
            target_review_policy_path=ready_args["target_review_policy_path"],
            workflow_token_budget=ready_args["workflow_token_budget"],
            context_token_budget=ready_args["context_token_budget"],
            context_mode=ready_args["context_mode"],
            max_artifact_tokens=ready_args["max_artifact_tokens"],
            query_limit=ready_args["query_limit"],
            max_presets=ready_args["max_presets"],
            max_rows=ready_args["max_rows"],
            max_files=ready_args["max_files"],
            max_parse_bytes=ready_args["max_parse_bytes"],
            include_hashes=ready_args["include_hashes"],
            include_codebase_memory=ready_args["include_codebase_memory"],
            codebase_memory_cache_dir=ready_args["codebase_memory_cache_dir"],
            include_content=ready_args["include_content"],
            include_prompt=ready_args["include_prompt"],
            include_details=ready_args["include_details"],
            extra_baselines=ready_args["extra_baselines"],
        )
        if profile:
            result["agent_profile_summary"] = _profile_summary(profile)
        if args.output:
            result["outputs"] = dict(result.get("outputs") if isinstance(result.get("outputs"), dict) else {})
            result["outputs"]["agent_ready_json"] = args.output.expanduser().resolve().as_posix()
            write_json(args.output, result)
        if args.format == "prompt":
            if result["ok"]:
                print(result.get("prompt_text") or "", end="" if str(result.get("prompt_text") or "").endswith("\n") else "\n")
        elif args.format == "markdown":
            print(markdown_agent_ready(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "scan":
        if args.build and not args.write:
            print("scan --build requires --write so the generated manifest exists", flush=True)
            return 2
        result = scan_repository(
            root=args.root,
            output_dir=args.output_dir,
            write=args.write,
            max_files=args.max_files,
            max_parse_bytes=args.max_parse_bytes,
            include_hashes=args.hash_files,
        )
        if args.build:
            federation = build_federation(
                manifest_path=Path(str(result["outputs"]["manifest"])),
                root=args.root,
                output_dir=Path(str(result["output_dir"])),
                write=True,
            )
            result["federation"] = {
                "ok": federation["ok"],
                "status": federation["status"],
                "summary": federation["summary"],
                "outputs": federation["outputs"],
            }
            result["ok"] = result["ok"] and federation["ok"]
            result["status"] = "pass_scan_and_build" if federation["ok"] else "fail_scan_and_build"
        if args.format == "markdown":
            print(markdown_scan(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "verify":
        payload = read_required_json(args.input)
        manifest = read_json(args.manifest)
        result = verify_federation(payload, manifest=manifest, root=args.root)
        if args.json:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        else:
            print(f"{result['status']} errors={result['error_count']}")
        return 0 if result["ok"] else 2
    if args.command == "query":
        payload = read_required_json(args.input)
        result = query_federation(payload, preset=args.preset, limit=args.limit)
        if args.format == "markdown":
            print(query_markdown(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0
    if args.command == "pack":
        payload = read_required_json(args.input)
        result = pack_context(
            payload,
            task=args.task,
            token_budget=args.token_budget,
            min_score=args.min_score,
            max_rows=args.max_rows,
            include_prompt=not args.no_prompt,
        )
        if args.output:
            result["outputs"] = {"context_pack_json": args.output.expanduser().resolve().as_posix()}
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_context_pack(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0
    if args.command == "brief":
        payload = read_required_json(args.input)
        result = build_task_brief(
            payload,
            task=args.task,
            token_budget=args.token_budget,
            query_limit=args.query_limit,
            max_presets=args.max_presets,
            max_rows=args.max_rows,
            include_prompt=not args.no_prompt,
            input_path=args.input.as_posix(),
        )
        if args.output:
            result["outputs"] = {"task_brief_json": args.output.expanduser().resolve().as_posix()}
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_task_brief(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0
    if args.command == "trace":
        payload = read_required_json(args.input)
        result = trace_federation(payload, match=args.match, depth=args.depth, limit=args.limit)
        if args.format == "markdown":
            print(markdown_trace(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0
    if args.command == "resolve":
        payload = read_required_json(args.input)
        result = resolve_target(
            payload,
            target=args.target,
            limit=args.limit,
            token_budget=args.token_budget,
            include_prompt=not args.no_prompt,
        )
        if args.output:
            result["outputs"] = {"resolve_json": args.output.expanduser().resolve().as_posix()}
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_resolve(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0
    if args.command == "adjudicate":
        payload = read_required_json(args.input)
        result = adjudicate_target(
            payload,
            target=args.target,
            limit=args.limit,
            token_budget=args.token_budget,
            include_prompt=not args.no_prompt,
        )
        if args.output:
            result["outputs"] = {"adjudication_json": args.output.expanduser().resolve().as_posix()}
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_adjudication(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0
    if args.command == "review-targets":
        payload = read_required_json(args.input)
        targets = list(args.target or [])
        if args.targets_file:
            targets.extend(read_targets_file(args.targets_file))
        result = review_targets(
            payload,
            targets=targets,
            limit=args.limit,
            token_budget=args.token_budget,
            include_details=args.include_details,
            include_prompt=not args.no_prompt,
        )
        if args.output:
            result["outputs"] = {"target_review_json": args.output.expanduser().resolve().as_posix()}
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_target_review(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0
    if args.command == "review-gate":
        payload = read_required_json(args.input)
        policy = load_target_review_gate_policy(args.policy) if args.policy else None
        result = evaluate_target_review_gate(
            payload,
            policy=policy,
            max_blocked=args.max_blocked,
            max_no_match=args.max_no_match,
            max_advisory_only=args.max_advisory_only,
            max_warn=args.max_warn,
            max_priority_score=args.max_priority_score,
            min_average_confidence=args.min_average_confidence,
            disallow_risk_flags=args.disallow_risk_flag,
            require_targets=args.require_target,
        )
        if args.output:
            result["outputs"] = {"target_review_gate_json": args.output.expanduser().resolve().as_posix()}
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_target_review_gate(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "doctor":
        payload = read_required_json(args.input)
        result = doctor_federation(payload)
        if args.format == "markdown":
            print(markdown_doctor(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "quality-gate":
        payload = read_required_json(args.input)
        policy = load_quality_gate_policy(args.policy) if args.policy else None
        federation_payload = read_required_json(args.federation_input) if args.federation_input else None
        if federation_payload is None and payload.get("schema_version") == "deep_context_federation_bootstrap_v1":
            outputs = payload.get("outputs") if isinstance(payload.get("outputs"), dict) else {}
            federation_path = outputs.get("federation_json")
            if federation_path:
                candidate = Path(str(federation_path))
                if candidate.exists():
                    federation_payload = read_required_json(candidate)
        result = evaluate_quality_gate(
            payload,
            federation_payload=federation_payload,
            policy=policy,
            min_sources=args.min_sources,
            min_entities=args.min_entities,
            min_edges=args.min_edges,
            max_errors=args.max_errors,
            max_warnings=args.max_warnings,
            max_duration_seconds=args.max_duration_seconds,
            max_scan_duration_seconds=args.max_scan_duration_seconds,
            require_roles=args.require_role,
            require_sources=args.require_source,
            require_query_presets=args.require_query_preset,
            require_bootstrap_steps=False if args.no_bootstrap_step_check else None,
        )
        if args.output:
            result["outputs"] = {"quality_gate_json": args.output.expanduser().resolve().as_posix()}
            write_json(args.output, result)
        if args.format == "markdown":
            print(markdown_quality_gate(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "rank":
        payload = read_required_json(args.input)
        result = rank_sources(payload, limit=args.limit) if args.kind == "sources" else rank_entities(payload, limit=args.limit)
        if args.format == "markdown":
            print(markdown_rank(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0
    if args.command == "diff":
        before = read_required_json(args.before)
        after = read_required_json(args.after)
        result = diff_federations(before, after)
        if args.format == "markdown":
            print(markdown_diff(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0
    if args.command == "sql":
        result = query_sqlite(args.sqlite, preset=args.preset, limit=args.limit, search=args.search)
        if args.format == "markdown":
            print(sql_markdown(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0
    if args.command == "bench":
        result = benchmark_build(
            manifest_path=args.manifest,
            root=args.root,
            output_dir=args.output_dir,
            iterations=args.iterations,
        )
        if args.json:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        else:
            print(
                "bench iterations={} mean={:.6f}s median={:.6f}s min={:.6f}s max={:.6f}s".format(
                    result["iterations"],
                    result["seconds_mean"],
                    result["seconds_median"],
                    result["seconds_min"],
                    result["seconds_max"],
                )
            )
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
