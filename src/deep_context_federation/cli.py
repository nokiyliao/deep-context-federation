"""Command-line interface for Deep Context Federation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from deep_context_federation.bench import benchmark_build
from deep_context_federation.builder import DEFAULT_JSON_NAME, build_federation, read_json
from deep_context_federation.graph import markdown_trace
from deep_context_federation.graph import trace_federation
from deep_context_federation.manifest import validate_manifest
from deep_context_federation.query import markdown as query_markdown
from deep_context_federation.query import query_federation
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
    validate = sub.add_parser("validate-manifest", help="Validate manifest shape before reading sources.")
    validate.add_argument("--manifest", type=Path, default=Path("deep_context_federation.json"))
    validate.add_argument("--json", action="store_true")
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
