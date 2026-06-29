"""End-to-end bootstrap pipeline for Deep Context Federation."""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from deep_context_federation.builder import DEFAULT_JSON_NAME
from deep_context_federation.builder import DEFAULT_MD_NAME
from deep_context_federation.builder import DEFAULT_SQLITE_NAME
from deep_context_federation.builder import build_federation
from deep_context_federation.builder import read_json
from deep_context_federation.builder import utc_now
from deep_context_federation.builder import write_json
from deep_context_federation.builder import write_markdown
from deep_context_federation.compose import compose_manifests
from deep_context_federation.doctor import doctor_federation
from deep_context_federation.scanner import scan_repository
from deep_context_federation.verifier import verify_federation

BOOTSTRAP_SCHEMA_VERSION = "deep_context_federation_bootstrap_v1"
DEFAULT_BOOTSTRAP_JSON_NAME = "deep_context_federation_bootstrap.json"
DEFAULT_BOOTSTRAP_MD_NAME = "DEEP_CONTEXT_FEDERATION_BOOTSTRAP.md"
DEFAULT_BOOTSTRAP_COMPOSED_MANIFEST_NAME = "deep_context_federation.bootstrap.composed.json"


def bootstrap_federation(
    *,
    root: Path,
    output_dir: Path,
    manifests: Sequence[Path] = (),
    max_files: int = 5000,
    max_parse_bytes: int = 1_000_000,
    include_hashes: bool = False,
    include_codebase_memory: bool = False,
    codebase_memory_cache_dir: Path | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Run scan -> optional compose -> build -> verify -> doctor.

    The bootstrap command is intentionally read-only with respect to project
    authority. It writes only generated DCF artifacts into ``output_dir``.
    """

    started = time.perf_counter()
    root = root.expanduser().resolve()
    output_dir = output_dir.expanduser()
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    scan = scan_repository(
        root=root,
        output_dir=output_dir,
        write=True,
        max_files=max_files,
        max_parse_bytes=max_parse_bytes,
        include_hashes=include_hashes,
    )
    manifest_inputs = [Path(str(scan["outputs"]["manifest"]))]
    manifest_inputs.extend(path.expanduser().resolve() for path in manifests)

    compose: dict[str, Any] | None = None
    build_manifest_path = manifest_inputs[0]
    if len(manifest_inputs) > 1:
        build_manifest_path = output_dir / DEFAULT_BOOTSTRAP_COMPOSED_MANIFEST_NAME
        compose = compose_manifests(manifest_inputs, output_path=build_manifest_path, write=True)
    federation = build_federation(
        manifest_path=build_manifest_path,
        root=root,
        output_dir=output_dir,
        include_codebase_memory=include_codebase_memory,
        codebase_memory_cache_dir=codebase_memory_cache_dir,
        write=True,
    )
    manifest = read_json(build_manifest_path)
    verification = verify_federation(federation, manifest=manifest, root=root)
    doctor = doctor_federation(federation)
    duration_seconds = max(0.0, time.perf_counter() - started)
    errors = []
    if not scan.get("ok"):
        errors.append("scan_failed")
    if compose is not None and not compose.get("ok"):
        errors.append("compose_failed")
    if not federation.get("ok"):
        errors.append("build_failed")
    if not verification.get("ok"):
        errors.append("verify_failed")
    if not doctor.get("ok"):
        errors.append("doctor_failed")
    summary = federation.get("summary") if isinstance(federation.get("summary"), Mapping) else {}
    result = {
        "schema_version": BOOTSTRAP_SCHEMA_VERSION,
        "ok": not errors,
        "status": "pass_bootstrap" if not errors else "fail_bootstrap",
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": utc_now(),
        "root": root.as_posix(),
        "output_dir": output_dir.as_posix(),
        "duration_seconds": round(duration_seconds, 6),
        "errors": errors,
        "scan": {
            "ok": scan.get("ok"),
            "status": scan.get("status"),
            "summary": scan.get("summary"),
            "outputs": scan.get("outputs"),
        },
        "compose": {
            "ok": compose.get("ok"),
            "status": compose.get("status"),
            "summary": compose.get("summary"),
            "output_path": compose.get("output_path"),
        }
        if compose is not None
        else None,
        "build": {
            "ok": federation.get("ok"),
            "status": federation.get("status"),
            "summary": summary,
            "manifest_path": build_manifest_path.as_posix(),
            "outputs": federation.get("outputs"),
        },
        "verify": {
            "ok": verification.get("ok"),
            "status": verification.get("status"),
            "error_count": verification.get("error_count"),
        },
        "doctor": {
            "ok": doctor.get("ok"),
            "status": doctor.get("status"),
            "error_count": doctor.get("error_count"),
            "warning_count": doctor.get("warning_count"),
            "recommended_actions": doctor.get("recommended_actions"),
        },
        "outputs": {
            "bootstrap_json": (output_dir / DEFAULT_BOOTSTRAP_JSON_NAME).as_posix(),
            "bootstrap_markdown": (output_dir / DEFAULT_BOOTSTRAP_MD_NAME).as_posix(),
            "federation_json": (output_dir / DEFAULT_JSON_NAME).as_posix(),
            "federation_markdown": (output_dir / DEFAULT_MD_NAME).as_posix(),
            "federation_sqlite": (output_dir / DEFAULT_SQLITE_NAME).as_posix(),
            "manifest": build_manifest_path.as_posix(),
        },
    }
    if write:
        write_json(output_dir / DEFAULT_BOOTSTRAP_JSON_NAME, result)
        write_markdown(output_dir / DEFAULT_BOOTSTRAP_MD_NAME, markdown_bootstrap(result).splitlines())
    return result


def markdown_bootstrap(result: Mapping[str, Any]) -> str:
    build = result.get("build") if isinstance(result.get("build"), Mapping) else {}
    build_summary = build.get("summary") if isinstance(build.get("summary"), Mapping) else {}
    scan = result.get("scan") if isinstance(result.get("scan"), Mapping) else {}
    scan_summary = scan.get("summary") if isinstance(scan.get("summary"), Mapping) else {}
    compose = result.get("compose") if isinstance(result.get("compose"), Mapping) else None
    verify = result.get("verify") if isinstance(result.get("verify"), Mapping) else {}
    doctor = result.get("doctor") if isinstance(result.get("doctor"), Mapping) else {}
    lines = [
        "# Deep Context Federation Bootstrap",
        "",
        f"- Status: `{result.get('status')}`",
        f"- Authority effect: `{result.get('authority_effect')}`",
        f"- No apply: `{result.get('no_apply')}`",
        f"- Root: `{result.get('root')}`",
        f"- Duration: `{result.get('duration_seconds')}`s",
        "",
        "## Scan",
        "",
        f"- Status: `{scan.get('status')}`",
        f"- Files: `{scan_summary.get('file_count')}` symbols=`{scan_summary.get('symbol_count')}` dependencies=`{scan_summary.get('dependency_edge_count')}`",
        f"- Scan time: `{scan_summary.get('duration_seconds')}`s files/sec=`{scan_summary.get('files_per_second')}`",
        "",
        "## Compose",
        "",
    ]
    if compose:
        compose_summary = compose.get("summary") if isinstance(compose.get("summary"), Mapping) else {}
        lines.extend(
            [
                f"- Status: `{compose.get('status')}`",
                f"- Sources: `{compose_summary.get('source_count')}` warnings=`{compose_summary.get('warning_count')}` errors=`{compose_summary.get('error_count')}`",
            ]
        )
    else:
        lines.append("- skipped")
    lines.extend(
        [
            "",
            "## Build",
            "",
            f"- Status: `{build.get('status')}`",
            f"- Sources: `{build_summary.get('source_count')}` entities=`{build_summary.get('entity_count')}` edges=`{build_summary.get('edge_count')}`",
            f"- Conflicts: `{build_summary.get('conflict_count')}` errors=`{build_summary.get('error_count')}` warnings=`{build_summary.get('warning_count')}`",
            "",
            "## Gates",
            "",
            f"- Verify: `{verify.get('status')}` errors=`{verify.get('error_count')}`",
            f"- Doctor: `{doctor.get('status')}` errors=`{doctor.get('error_count')}` warnings=`{doctor.get('warning_count')}`",
        ]
    )
    actions = [str(item) for item in doctor.get("recommended_actions") or []] if isinstance(doctor, Mapping) else []
    if actions:
        lines.extend(["", "## Recommended Actions", ""])
        for action in actions:
            lines.append(f"- {action}")
    return "\n".join(lines).rstrip() + "\n"
