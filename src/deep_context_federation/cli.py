"""Command-line interface for Deep Context Federation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from deep_context_federation.adjudicate import adjudicate_target
from deep_context_federation.adjudicate import markdown_adjudication
from deep_context_federation.bench import benchmark_build
from deep_context_federation.bootstrap import bootstrap_federation
from deep_context_federation.bootstrap import markdown_bootstrap
from deep_context_federation.builder import DEFAULT_JSON_NAME, build_federation, read_json, write_json
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
from deep_context_federation.verifier import read_json as read_required_json
from deep_context_federation.verifier import verify_federation
from deep_context_federation.workflow_plan import build_workflow_plan
from deep_context_federation.workflow_plan import markdown_workflow_plan
from deep_context_federation.workflow_run import build_workflow_run
from deep_context_federation.workflow_run import markdown_workflow_run


def add_common_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", type=Path, default=Path("deep_context_federation.json"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=Path(".dcf"))


def read_targets_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except Exception:
        data = None
    if isinstance(data, list):
        return [str(item) for item in data if str(item).strip()]
    return [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]


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
    build = sub.add_parser("build", help="Build a federation artifact from a manifest.")
    add_common_source_args(build)
    build.add_argument("--include-codebase-memory", action="store_true")
    build.add_argument("--codebase-memory-cache-dir", type=Path)
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
    bootstrap.add_argument("--include-codebase-memory", action="store_true")
    bootstrap.add_argument("--codebase-memory-cache-dir", type=Path)
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
    intake.add_argument("--include-codebase-memory", action="store_true")
    intake.add_argument("--codebase-memory-cache-dir", type=Path)
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
    workflow_plan.add_argument("--include-codebase-memory", action="store_true")
    workflow_plan.add_argument("--codebase-memory-cache-dir", type=Path)
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
    workflow_run.add_argument("--include-codebase-memory", action="store_true")
    workflow_run.add_argument("--codebase-memory-cache-dir", type=Path)
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
    args = build_parser().parse_args(argv)
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
