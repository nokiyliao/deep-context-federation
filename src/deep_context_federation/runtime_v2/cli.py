"""Public CLI for the project-configurable DCF v2 runtime."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from .collectors import CollectionError
from .events import (
    EventReconcileBusy,
    acknowledge_events,
    enqueue_event,
    event_reconcile_lock,
    pending_events,
)
from .graph import traverse
from .jspace import (
    JSpaceCompileError,
    compile_jspace_contract,
    compile_task_context_capsule,
    verify_contract_freshness,
    write_immutable_contract,
)
from .query import FreshnessBlocked, InvalidQuery, UnknownCapability, query_capability
from .runtime import DcfRuntime
from .storage import GenerationTransactionError, GenerationUnavailable

EXIT_OK = 0
EXIT_BLOCKED = 2
EXIT_UNAVAILABLE = 3


def _emit(payload: dict[str, Any], *, pretty: bool) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True))


def _add_runtime_paths(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--runtime-root", type=Path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dcf runtime",
        description="Immutable, read-only DCF v2 project context runtime",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    refresh = subparsers.add_parser("refresh", help="build and atomically publish a generation")
    _add_runtime_paths(refresh)
    refresh.add_argument("--if-needed", action="store_true")
    refresh.add_argument("--reason", default="manual")
    refresh.add_argument("--no-write", action="store_true")
    refresh.add_argument("--json", action="store_true")

    status = subparsers.add_parser("status", help="read current generation status")
    _add_runtime_paths(status)
    status.add_argument(
        "--required-capability",
        dest="required_capabilities",
        action="append",
        help="evaluate task-local admission for one capability (repeatable)",
    )
    status.add_argument("--json", action="store_true")

    query = subparsers.add_parser("query", help="query one capability")
    _add_runtime_paths(query)
    query.add_argument("--capability", required=True)
    query.add_argument("--target")
    query.add_argument("--depth", type=int, default=2)
    query.add_argument("--allow-stale", action="store_true")
    query.add_argument("--json", action="store_true")

    verify = subparsers.add_parser("verify", help="verify immutable generation integrity")
    _add_runtime_paths(verify)
    verify.add_argument("--json", action="store_true")

    event = subparsers.add_parser("event", help="enqueue one cheap refresh event")
    _add_runtime_paths(event)
    event.add_argument("--kind", required=True, choices=("git", "lease", "receipt", "operator"))
    event.add_argument("--reason", default="")
    event.add_argument("--json", action="store_true")

    reconcile = subparsers.add_parser(
        "reconcile-events",
        help="coalesce pending events into at most one immutable generation",
    )
    _add_runtime_paths(reconcile)
    reconcile.add_argument("--json", action="store_true")

    watchdog = subparsers.add_parser(
        "watchdog",
        help="run one bounded event reconciliation for an external scheduler",
    )
    _add_runtime_paths(watchdog)
    watchdog.add_argument("--once", action="store_true", required=True)
    watchdog.add_argument("--json", action="store_true")

    jspace = subparsers.add_parser(
        "compile-jspace",
        help="compile one immutable action contract and optional bounded task capsule",
    )
    _add_runtime_paths(jspace)
    jspace.add_argument("--surface-id", required=True)
    jspace.add_argument("--action-json", type=Path, required=True)
    jspace.add_argument("--output", type=Path, required=True)
    jspace.add_argument("--capsule-output", type=Path)
    jspace.add_argument("--json", action="store_true")
    return parser


def _runtime(args: argparse.Namespace) -> DcfRuntime:
    return DcfRuntime(
        args.repo_root.expanduser().resolve(),
        runtime_root=(
            None if args.runtime_root is None else args.runtime_root.expanduser().resolve()
        ),
    )


def _reconcile_pending_events(
    runtime: DcfRuntime,
    *,
    repo_root: Path,
    runtime_root: Path | None,
) -> dict[str, Any]:
    with event_reconcile_lock(repo_root, runtime_root=runtime_root):
        rows = pending_events(repo_root, runtime_root=runtime_root)
        kinds = sorted({str(payload.get("kind", "unknown")) for _, payload in rows})
        result = runtime.refresh(
            if_needed=True,
            reason=("events:" + ",".join(kinds)) if rows else "event-reconcile",
            write=True,
        )
        receipt = acknowledge_events(rows, generation_id=str(result["generation_id"]))
        result["coalesced_event_count"] = len(rows)
        result["event_receipt"] = None if receipt is None else str(receipt)
        return result


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.repo_root.expanduser().resolve()
    pretty = bool(args.json)
    try:
        runtime = _runtime(args)
        if args.command == "refresh":
            result = runtime.refresh(
                if_needed=args.if_needed,
                reason=args.reason,
                write=not args.no_write,
            )
            _emit(result, pretty=pretty)
            return EXIT_OK
        if args.command == "status":
            response = runtime.status(
                required_capabilities=args.required_capabilities,
            )
            _emit(response.model_dump(mode="json"), pretty=pretty)
            if response.generation_id is None:
                return EXIT_UNAVAILABLE
            if (
                args.required_capabilities
                and response.execution_admission.get("admitted") is not True
            ):
                return EXIT_BLOCKED
            return EXIT_OK
        if args.command == "query":
            response, elapsed_ms = query_capability(
                runtime,
                capability_id=args.capability,
                target=args.target,
                depth=args.depth,
                allow_stale=args.allow_stale,
                graph_traverse=traverse,
            )
            payload = response.model_dump(mode="json")
            payload["elapsed_ms"] = round(elapsed_ms, 3)
            _emit(payload, pretty=pretty)
            return EXIT_BLOCKED if response.projection_status == "blocked" else EXIT_OK
        if args.command == "verify":
            result = runtime.verify_current()
            _emit(result, pretty=pretty)
            return EXIT_OK if result["ok"] else EXIT_BLOCKED
        if args.command == "event":
            result = enqueue_event(
                root,
                kind=args.kind,
                payload={"reason": args.reason},
                runtime_root=args.runtime_root,
            )
            _emit(result, pretty=pretty)
            return EXIT_OK
        if args.command in {"reconcile-events", "watchdog"}:
            result = _reconcile_pending_events(
                runtime,
                repo_root=root,
                runtime_root=args.runtime_root,
            )
            _emit(result, pretty=pretty)
            return EXIT_OK
        if args.command == "compile-jspace":
            action = json.loads(args.action_json.read_text(encoding="utf-8"))
            if not isinstance(action, dict):
                raise JSpaceCompileError(
                    "JSPACE_ACTION_SHAPE_INVALID", "--action-json must contain an object"
                )
            contract = compile_jspace_contract(
                runtime,
                surface_id=args.surface_id,
                action=action,
            )
            verify_contract_freshness(runtime, contract)
            contract_path = write_immutable_contract(args.output, contract)
            capsule = None
            capsule_path = None
            if args.capsule_output is not None:
                capsule = compile_task_context_capsule(contract, action=action)
                capsule_path = write_immutable_contract(args.capsule_output, capsule)
            _emit(
                {
                    "schema_version": "jspace_compile_result_v2",
                    "status": "compiled",
                    "contract_path": contract_path,
                    "authorization_semantic_sha256": contract[
                        "authorization_semantic_sha256"
                    ],
                    "content_sha256": contract["content_sha256"],
                    "task_context_capsule_path": capsule_path,
                    "task_context_capsule_semantic_sha256": (
                        None if capsule is None else capsule["semantic_sha256"]
                    ),
                    "dcf_generation_id": contract["dcf_generation"]["generation_id"],
                    "matched_surface_ids": contract["matched_surface_ids"],
                    "authority_effect": "none",
                    "no_apply": True,
                },
                pretty=pretty,
            )
            return EXIT_OK
    except FreshnessBlocked as exc:
        _emit(
            {
                "schema_version": "dcf_error_v2",
                "status": "blocked",
                "error": str(exc),
                "authority_effect": "none",
                "no_apply": True,
            },
            pretty=True,
        )
        return EXIT_BLOCKED
    except JSpaceCompileError as exc:
        _emit(
            {
                "schema_version": "jspace_error_v1",
                "status": "blocked" if exc.blocked else "invalid",
                "error_code": exc.error_code,
                "error": str(exc),
                "authority_effect": "none",
                "no_apply": True,
            },
            pretty=True,
        )
        return EXIT_BLOCKED if exc.blocked else EXIT_UNAVAILABLE
    except (UnknownCapability, InvalidQuery) as exc:
        _emit(
            {
                "schema_version": "dcf_error_v2",
                "status": "invalid_query",
                "error_code": getattr(exc, "error_code", "INVALID_QUERY"),
                "error": str(exc),
                "authority_effect": "none",
                "no_apply": True,
            },
            pretty=True,
        )
        return EXIT_UNAVAILABLE
    except (
        GenerationUnavailable,
        GenerationTransactionError,
        EventReconcileBusy,
        CollectionError,
        json.JSONDecodeError,
        OSError,
        ValueError,
    ) as exc:
        _emit(
            {
                "schema_version": "dcf_error_v2",
                "status": "unavailable",
                "error": str(exc),
                "authority_effect": "none",
                "no_apply": True,
            },
            pretty=True,
        )
        return EXIT_UNAVAILABLE
    return EXIT_UNAVAILABLE


if __name__ == "__main__":
    raise SystemExit(main())
