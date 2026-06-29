"""Command-line interface for Deep Context Federation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from deep_context_federation.bench import benchmark_build
from deep_context_federation.bootstrap import bootstrap_federation
from deep_context_federation.bootstrap import markdown_bootstrap
from deep_context_federation.builder import DEFAULT_JSON_NAME, build_federation, read_json, write_json
from deep_context_federation.compose import compose_manifests
from deep_context_federation.compose import markdown_compose
from deep_context_federation.diff import diff_federations
from deep_context_federation.diff import markdown_diff
from deep_context_federation.doctor import doctor_federation
from deep_context_federation.doctor import markdown_doctor
from deep_context_federation.graph import markdown_trace
from deep_context_federation.graph import trace_federation
from deep_context_federation.manifest import validate_manifest
from deep_context_federation.quality_gate import evaluate_quality_gate
from deep_context_federation.quality_gate import markdown_quality_gate
from deep_context_federation.query import markdown as query_markdown
from deep_context_federation.query import query_federation
from deep_context_federation.rank import markdown_rank
from deep_context_federation.rank import rank_entities
from deep_context_federation.rank import rank_sources
from deep_context_federation.scanner import markdown_scan
from deep_context_federation.scanner import scan_repository
from deep_context_federation.sqlite_query import SQL_PRESETS
from deep_context_federation.sqlite_query import markdown as sql_markdown
from deep_context_federation.sqlite_query import query_sqlite
from deep_context_federation.verifier import read_json as read_required_json
from deep_context_federation.verifier import verify_federation


def add_common_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", type=Path, default=Path("deep_context_federation.json"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=Path(".dcf"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dcf", description="Read-only deep context federation CLI.")
    sub = parser.add_subparsers(dest="command", required=True)
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
    trace = sub.add_parser("trace", help="Trace neighboring federation entities by text match.")
    trace.add_argument("--input", type=Path, default=Path(".dcf") / DEFAULT_JSON_NAME)
    trace.add_argument("--match", required=True)
    trace.add_argument("--depth", type=int, default=2)
    trace.add_argument("--limit", type=int, default=50)
    trace.add_argument("--format", choices=["json", "markdown"], default="json")
    doctor = sub.add_parser("doctor", help="Diagnose federation health and recommend next actions.")
    doctor.add_argument("--input", type=Path, default=Path(".dcf") / DEFAULT_JSON_NAME)
    doctor.add_argument("--format", choices=["json", "markdown"], default="json")
    gate = sub.add_parser("quality-gate", help="Evaluate CI/agent quality gates on a bootstrap or federation artifact.")
    gate.add_argument("--input", type=Path, default=Path(".dcf") / "deep_context_federation_bootstrap.json")
    gate.add_argument("--federation-input", type=Path)
    gate.add_argument("--min-sources", type=int, default=1)
    gate.add_argument("--min-entities", type=int, default=1)
    gate.add_argument("--min-edges", type=int, default=1)
    gate.add_argument("--max-errors", type=int, default=0)
    gate.add_argument("--max-warnings", type=int, default=0)
    gate.add_argument("--max-duration-seconds", type=float)
    gate.add_argument("--max-scan-duration-seconds", type=float)
    gate.add_argument("--require-role", action="append", default=[])
    gate.add_argument("--require-source", action="append", default=[])
    gate.add_argument("--require-query-preset", action="append", default=[])
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
    if args.command == "trace":
        payload = read_required_json(args.input)
        result = trace_federation(payload, match=args.match, depth=args.depth, limit=args.limit)
        if args.format == "markdown":
            print(markdown_trace(result))
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
        return 0
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
            require_bootstrap_steps=not args.no_bootstrap_step_check,
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
