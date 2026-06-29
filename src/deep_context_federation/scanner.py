"""Read-only repository scanner for self-bootstrapping a federation manifest."""

from __future__ import annotations

import ast
import os
import re
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from deep_context_federation.builder import git_info
from deep_context_federation.builder import sha256_file
from deep_context_federation.builder import utc_now
from deep_context_federation.builder import write_json
from deep_context_federation.manifest import MANIFEST_SCHEMA

SCAN_SCHEMA_VERSION = "deep_context_federation_repo_scan_v1"
FILE_INVENTORY_SCHEMA_VERSION = "deep_context_federation_repo_file_inventory_v1"
SYMBOL_MAP_SCHEMA_VERSION = "deep_context_federation_repo_code_symbols_v1"
SURFACE_MAP_SCHEMA_VERSION = "deep_context_federation_repo_surface_map_v1"
DEPENDENCY_GRAPH_SCHEMA_VERSION = "deep_context_federation_repo_dependency_graph_v1"

DEFAULT_MANIFEST_NAME = "deep_context_federation.generated.json"
DEFAULT_INVENTORY_NAME = "repo_file_inventory.json"
DEFAULT_SYMBOLS_NAME = "repo_code_symbols.json"
DEFAULT_LEGACY_SYMBOLS_NAME = "repo_python_symbols.json"
DEFAULT_SURFACES_NAME = "repo_surface_map.json"
DEFAULT_DEPENDENCIES_NAME = "repo_dependency_graph.json"

DEFAULT_EXCLUDE_DIRS = {
    ".codebase-memory",
    ".dcf",
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".venv",
    "__pycache__",
    "build",
    "data",
    "dist",
    "logs",
    "node_modules",
    "output",
    "venv",
}

TEXT_SUFFIXES = {
    ".cfg",
    ".css",
    ".html",
    ".ini",
    ".js",
    ".jsx",
    ".json",
    ".mjs",
    ".md",
    ".py",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}

CODE_SUFFIXES = {".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}
JS_TS_SUFFIXES = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}

JS_CLASS_RE = re.compile(r"^\s*(?:export\s+default\s+|export\s+)?class\s+([A-Za-z_$][\w$]*)\b", re.MULTILINE)
JS_FUNCTION_RE = re.compile(r"^\s*(?:export\s+default\s+|export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", re.MULTILINE)
JS_ARROW_RE = re.compile(
    r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>",
    re.MULTILINE,
)
JS_IMPORT_FROM_RE = re.compile(r"\bimport\s+(?:type\s+)?[\s\S]{0,300}?\s+from\s+['\"]([^'\"]+)['\"]", re.MULTILINE)
JS_IMPORT_SIDE_EFFECT_RE = re.compile(r"^\s*import\s+['\"]([^'\"]+)['\"]", re.MULTILINE)
JS_REQUIRE_RE = re.compile(r"\brequire\(\s*['\"]([^'\"]+)['\"]\s*\)")


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _is_excluded_dir(name: str, excludes: set[str]) -> bool:
    return name in excludes or name.startswith(".dcf")


def _surface_for(rel_path: str) -> tuple[str, str]:
    first = rel_path.split("/", 1)[0]
    if first in {"src", "lib"}:
        return "source_code", "source_owner"
    if first in {"tests", "test"}:
        return "test_suite", "test_owner"
    if first in {"docs", "doc"} or rel_path.upper().startswith("README"):
        return "documentation", "docs_owner"
    if first in {"config", "configs"}:
        return "configuration", "config_owner"
    if first in {"scripts", "bin"}:
        return "operations_scripts", "ops_owner"
    if first in {"examples", "example"}:
        return "examples", "example_owner"
    if first == ".github":
        return "github_automation", "automation_owner"
    if rel_path.endswith((".toml", ".cfg", ".ini", ".yaml", ".yml")):
        return "configuration", "config_owner"
    return "repo_root", "repo_owner"


def _module_name(rel_path: str) -> str:
    path = Path(rel_path)
    parts = list(path.with_suffix("").parts)
    if parts and parts[0] == "src":
        parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(part for part in parts if part) or path.stem


def _line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, max(0, offset)) + 1


def _read_text_for_parse(path: Path, *, max_parse_bytes: int) -> tuple[str, str]:
    try:
        if path.stat().st_size > max_parse_bytes:
            return "", "too_large"
        return path.read_text(encoding="utf-8"), ""
    except UnicodeDecodeError:
        return "", "decode_error"
    except OSError:
        return "", "read_error"


def _python_symbols(path: Path, rel_path: str, *, max_parse_bytes: int) -> tuple[list[dict[str, Any]], str]:
    text, failure = _read_text_for_parse(path, max_parse_bytes=max_parse_bytes)
    if failure:
        return [], failure
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [], "syntax_error"

    module = _module_name(rel_path)
    surface_id, _owner = _surface_for(rel_path)
    rows: list[dict[str, Any]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"
            rows.append(
                {
                    "symbol_fqn": f"{module}.{node.name}",
                    "path": rel_path,
                    "kind": kind,
                    "line": node.lineno,
                    "surface_id": surface_id,
                }
            )
        elif isinstance(node, ast.ClassDef):
            class_fqn = f"{module}.{node.name}"
            rows.append(
                {
                    "symbol_fqn": class_fqn,
                    "path": rel_path,
                    "kind": "class",
                    "line": node.lineno,
                    "surface_id": surface_id,
                }
            )
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    kind = "async_method" if isinstance(child, ast.AsyncFunctionDef) else "method"
                    rows.append(
                        {
                            "symbol_fqn": f"{class_fqn}.{child.name}",
                            "path": rel_path,
                            "kind": kind,
                            "line": child.lineno,
                            "surface_id": surface_id,
                        }
                    )
    return rows, ""


def _js_ts_symbols(path: Path, rel_path: str, *, max_parse_bytes: int) -> tuple[list[dict[str, Any]], str]:
    text, failure = _read_text_for_parse(path, max_parse_bytes=max_parse_bytes)
    if failure:
        return [], failure
    module = _module_name(rel_path)
    surface_id, _owner = _surface_for(rel_path)
    rows: list[dict[str, Any]] = []
    for regex, kind in [
        (JS_CLASS_RE, "class"),
        (JS_FUNCTION_RE, "function"),
        (JS_ARROW_RE, "arrow_function"),
    ]:
        for match in regex.finditer(text):
            rows.append(
                {
                    "symbol_fqn": f"{module}.{match.group(1)}",
                    "path": rel_path,
                    "kind": kind,
                    "language": "typescript" if Path(rel_path).suffix.lower() in {".ts", ".tsx"} else "javascript",
                    "line": _line_for_offset(text, match.start()),
                    "surface_id": surface_id,
                }
            )
    return rows, ""


def _resolve_relative_import(root: Path, rel_path: str, raw_target: str) -> str:
    if not raw_target.startswith("."):
        return raw_target
    base = (root / rel_path).parent
    if raw_target.startswith(("./", "../")):
        raw = (base / raw_target).resolve()
    else:
        level = len(raw_target) - len(raw_target.lstrip("."))
        remainder = raw_target[level:]
        for _ in range(max(0, level - 1)):
            base = base.parent
        raw = base.joinpath(*[part for part in remainder.split(".") if part]).resolve()
    candidates: list[Path] = []
    if raw.suffix:
        candidates.append(raw)
    else:
        for suffix in [".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]:
            candidates.append(raw.with_suffix(suffix))
        for suffix in [".py", ".ts", ".tsx", ".js", ".jsx"]:
            candidates.append(raw / f"index{suffix}")
        candidates.append(raw / "__init__.py")
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return _relative(candidate, root)
    return raw_target


def _resolve_python_module(root: Path, module: str) -> str:
    if not module or module.startswith("."):
        return module
    parts = [part for part in module.split(".") if part]
    if not parts:
        return module
    candidates = [
        root.joinpath(*parts).with_suffix(".py"),
        root.joinpath(*parts, "__init__.py"),
        root.joinpath("src", *parts).with_suffix(".py"),
        root.joinpath("src", *parts, "__init__.py"),
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return _relative(candidate, root)
    return module


def _python_import_edges(root: Path, path: Path, rel_path: str, *, max_parse_bytes: int) -> tuple[list[dict[str, Any]], str]:
    text, failure = _read_text_for_parse(path, max_parse_bytes=max_parse_bytes)
    if failure:
        return [], failure
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [], "syntax_error"
    edges: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name:
                    target = _resolve_python_module(root, alias.name)
                    edges.append(
                        {
                            "from": rel_path,
                            "to": target,
                            "relation": "REFERENCES",
                            "language": "python",
                            "line": node.lineno,
                            "evidence": rel_path,
                        }
                    )
        elif isinstance(node, ast.ImportFrom):
            module = "." * int(node.level or 0) + str(node.module or "")
            target = _resolve_relative_import(root, rel_path, module) if module.startswith(".") else _resolve_python_module(root, module)
            if target:
                edges.append(
                    {
                        "from": rel_path,
                        "to": target,
                        "relation": "REFERENCES",
                        "language": "python",
                        "line": node.lineno,
                        "evidence": rel_path,
                    }
                )
    return edges, ""


def _js_ts_import_edges(root: Path, path: Path, rel_path: str, *, max_parse_bytes: int) -> tuple[list[dict[str, Any]], str]:
    text, failure = _read_text_for_parse(path, max_parse_bytes=max_parse_bytes)
    if failure:
        return [], failure
    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    language = "typescript" if Path(rel_path).suffix.lower() in {".ts", ".tsx"} else "javascript"
    for regex in [JS_IMPORT_FROM_RE, JS_IMPORT_SIDE_EFFECT_RE, JS_REQUIRE_RE]:
        for match in regex.finditer(text):
            raw_target = match.group(1)
            line = _line_for_offset(text, match.start())
            key = (raw_target, line)
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                {
                    "from": rel_path,
                    "to": _resolve_relative_import(root, rel_path, raw_target),
                    "relation": "REFERENCES",
                    "language": language,
                    "line": line,
                    "evidence": rel_path,
                }
            )
    return edges, ""


def iter_repo_files(root: Path, *, exclude_dirs: set[str], max_files: int) -> tuple[list[Path], dict[str, Any]]:
    files: list[Path] = []
    skipped_dirs: Counter[str] = Counter()
    truncated = False
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            dirname for dirname in dirnames if not _is_excluded_dir(dirname, exclude_dirs)
        )
        for dirname in set(os.listdir(current_root)) - set(dirnames) if Path(current_root).exists() else set():
            if (Path(current_root) / dirname).is_dir() and _is_excluded_dir(dirname, exclude_dirs):
                skipped_dirs[dirname] += 1
        for filename in sorted(filenames):
            path = Path(current_root) / filename
            if not path.is_file():
                continue
            files.append(path)
            if len(files) >= max_files:
                truncated = True
                return files, {"truncated": truncated, "skipped_dirs": dict(sorted(skipped_dirs.items()))}
    return files, {"truncated": truncated, "skipped_dirs": dict(sorted(skipped_dirs.items()))}


def _file_inventory_payload(
    *,
    root: Path,
    files: Sequence[Path],
    generated_at: str,
    head_commit: str,
    include_hashes: bool,
    max_hash_bytes: int,
    truncated: bool,
) -> tuple[dict[str, Any], Counter[str], Counter[str]]:
    rows: list[dict[str, Any]] = []
    by_surface: Counter[str] = Counter()
    by_suffix: Counter[str] = Counter()
    total_bytes = 0
    for path in files:
        rel_path = _relative(path, root)
        try:
            stat = path.stat()
        except OSError:
            continue
        suffix = path.suffix.lower()
        surface_id, _owner = _surface_for(rel_path)
        by_surface[surface_id] += 1
        by_suffix[suffix or "<none>"] += 1
        total_bytes += stat.st_size
        row: dict[str, Any] = {
            "artifact_id": rel_path,
            "path": rel_path,
            "surface_id": surface_id,
            "suffix": suffix,
            "byte_size": stat.st_size,
            "text_like": suffix in TEXT_SUFFIXES,
        }
        if include_hashes and stat.st_size <= max_hash_bytes:
            row["sha256"] = sha256_file(path)
        rows.append(row)

    payload = {
        "schema_version": FILE_INVENTORY_SCHEMA_VERSION,
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": generated_at,
        "head_commit": head_commit,
        "summary": {
            "status": "pass",
            "file_count": len(rows),
            "total_bytes": total_bytes,
            "truncated": truncated,
            "by_surface": dict(sorted(by_surface.items())),
            "by_suffix": dict(sorted(by_suffix.items())),
        },
        "claims": [
            {
                "claim_id": "repo_scan_inventory_present",
                "label": "Read-only repository inventory was generated.",
                "status": "advisory",
                "authority_level": "advisory",
                "supporting_artifacts": [DEFAULT_INVENTORY_NAME, DEFAULT_SYMBOLS_NAME, DEFAULT_SURFACES_NAME, DEFAULT_DEPENDENCIES_NAME],
                "verifiers": ["dcf discover-project-context", "dcf check-context-inputs", "dcf verify-context"],
            }
        ],
        "artifacts": rows,
    }
    return payload, by_surface, by_suffix


def _symbol_map_payload(
    *,
    root: Path,
    files: Sequence[Path],
    generated_at: str,
    head_commit: str,
    max_parse_bytes: int,
) -> tuple[dict[str, Any], Counter[str]]:
    rows: list[dict[str, Any]] = []
    parse_failures: Counter[str] = Counter()
    by_language: Counter[str] = Counter()
    for path in files:
        suffix = path.suffix.lower()
        if suffix not in CODE_SUFFIXES:
            continue
        rel_path = _relative(path, root)
        if suffix == ".py":
            symbols, failure = _python_symbols(path, rel_path, max_parse_bytes=max_parse_bytes)
            language = "python"
        elif suffix in JS_TS_SUFFIXES:
            symbols, failure = _js_ts_symbols(path, rel_path, max_parse_bytes=max_parse_bytes)
            language = "typescript" if suffix in {".ts", ".tsx"} else "javascript"
        else:
            symbols, failure = [], ""
        if failure:
            parse_failures[f"{language}:{failure}"] += 1
        if symbols:
            by_language[language] += len(symbols)
        rows.extend(symbols)

    payload = {
        "schema_version": SYMBOL_MAP_SCHEMA_VERSION,
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": generated_at,
        "head_commit": head_commit,
        "summary": {
            "status": "pass",
            "symbol_count": len(rows),
            "by_language": dict(sorted(by_language.items())),
            "parse_failures": dict(sorted(parse_failures.items())),
        },
        "symbols": rows,
    }
    return payload, parse_failures


def _dependency_graph_payload(
    *,
    root: Path,
    files: Sequence[Path],
    generated_at: str,
    head_commit: str,
    max_parse_bytes: int,
) -> tuple[dict[str, Any], Counter[str]]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    parse_failures: Counter[str] = Counter()
    by_language: Counter[str] = Counter()
    for path in files:
        suffix = path.suffix.lower()
        if suffix not in CODE_SUFFIXES:
            continue
        rel_path = _relative(path, root)
        surface_id, _owner = _surface_for(rel_path)
        language = "python" if suffix == ".py" else ("typescript" if suffix in {".ts", ".tsx"} else "javascript")
        nodes[rel_path] = {
            "id": rel_path,
            "path": rel_path,
            "kind": "path",
            "surface_id": surface_id,
            "language": language,
        }
        if suffix == ".py":
            found, failure = _python_import_edges(root, path, rel_path, max_parse_bytes=max_parse_bytes)
        else:
            found, failure = _js_ts_import_edges(root, path, rel_path, max_parse_bytes=max_parse_bytes)
        if failure:
            parse_failures[f"{language}:{failure}"] += 1
        if found:
            by_language[language] += len(found)
        for edge in found:
            target = str(edge.get("to") or "")
            if "/" in target or target.endswith(tuple(CODE_SUFFIXES)):
                nodes.setdefault(
                    target,
                    {
                        "id": target,
                        "path": target,
                        "kind": "path",
                        "surface_id": _surface_for(target)[0],
                        "language": "",
                    },
                )
            else:
                nodes.setdefault(
                    target,
                    {
                        "id": target,
                        "name": target,
                        "kind": "symbol",
                        "language": "",
                    },
                )
            edges.append(edge)

    payload = {
        "schema_version": DEPENDENCY_GRAPH_SCHEMA_VERSION,
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": generated_at,
        "head_commit": head_commit,
        "summary": {
            "status": "pass",
            "node_count": len(nodes),
            "edge_count": len(edges),
            "by_language": dict(sorted(by_language.items())),
            "parse_failures": dict(sorted(parse_failures.items())),
        },
        "nodes": sorted(nodes.values(), key=lambda item: str(item.get("id") or "")),
        "edges": edges,
    }
    return payload, parse_failures


def _surface_map_payload(
    *,
    generated_at: str,
    head_commit: str,
    by_surface: Mapping[str, int],
) -> dict[str, Any]:
    surfaces: list[dict[str, Any]] = []
    for surface_id, count in sorted(by_surface.items()):
        _unused, owner = _surface_for(f"{surface_id}/placeholder")
        owner_by_surface = {
            "configuration": "config_owner",
            "documentation": "docs_owner",
            "examples": "example_owner",
            "github_automation": "automation_owner",
            "operations_scripts": "ops_owner",
            "repo_root": "repo_owner",
            "source_code": "source_owner",
            "test_suite": "test_owner",
        }
        surfaces.append(
            {
                "surface_id": surface_id,
                "owner": owner_by_surface.get(surface_id, owner),
                "path": surface_id,
                "file_count": count,
                "authority_effect": "none",
            }
        )
    return {
        "schema_version": SURFACE_MAP_SCHEMA_VERSION,
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": generated_at,
        "head_commit": head_commit,
        "summary": {"status": "pass", "surface_count": len(surfaces)},
        "surfaces": surfaces,
    }


def _manifest_payload() -> dict[str, Any]:
    return {
        "schema_version": MANIFEST_SCHEMA,
        "authority_boundary": {"authority_effect": "none", "no_apply": True},
        "sources": [
            {
                "source_id": "repo_file_inventory",
                "role": "evidence_index",
                "required": True,
                "path": DEFAULT_INVENTORY_NAME,
                "verifier": "dcf discover-project-context",
            },
            {
                "source_id": "repo_code_symbols",
                "role": "advisory_source_symbol_graph",
                "required": False,
                "path": DEFAULT_SYMBOLS_NAME,
                "verifier": "stdlib_ast_and_conservative_regex_parse",
            },
            {
                "source_id": "repo_dependency_graph",
                "role": "advisory_dependency_graph",
                "required": False,
                "path": DEFAULT_DEPENDENCIES_NAME,
                "verifier": "stdlib_import_parse",
            },
            {
                "source_id": "repo_surface_map",
                "role": "project_surface",
                "required": True,
                "path": DEFAULT_SURFACES_NAME,
                "verifier": "dcf discover-project-context",
            },
        ],
    }


def scan_repository(
    *,
    root: Path,
    output_dir: Path,
    write: bool = False,
    max_files: int = 5000,
    max_parse_bytes: int = 1_000_000,
    include_hashes: bool = False,
    max_hash_bytes: int = 1_000_000,
    exclude_dirs: set[str] | None = None,
) -> dict[str, Any]:
    """Scan a repository and generate starter federation sources.

    The scanner is deliberately read-only with respect to the target repository.
    When ``write`` is true it writes only generated advisory JSON into
    ``output_dir`` and never mutates source files, hooks, live configs, or
    runtime state.
    """

    root = root.expanduser().resolve()
    started = time.perf_counter()
    resolved_output = output_dir.expanduser()
    if not resolved_output.is_absolute():
        resolved_output = root / resolved_output
    resolved_output = resolved_output.resolve()
    excludes = set(DEFAULT_EXCLUDE_DIRS if exclude_dirs is None else exclude_dirs)
    generated_at = utc_now()
    git = git_info(root)
    head_commit = str(git.get("head_commit") or "")

    files, walk_summary = iter_repo_files(root, exclude_dirs=excludes, max_files=max_files)
    inventory, by_surface, by_suffix = _file_inventory_payload(
        root=root,
        files=files,
        generated_at=generated_at,
        head_commit=head_commit,
        include_hashes=include_hashes,
        max_hash_bytes=max_hash_bytes,
        truncated=bool(walk_summary.get("truncated")),
    )
    symbols, parse_failures = _symbol_map_payload(
        root=root,
        files=files,
        generated_at=generated_at,
        head_commit=head_commit,
        max_parse_bytes=max_parse_bytes,
    )
    dependency_graph, dependency_parse_failures = _dependency_graph_payload(
        root=root,
        files=files,
        generated_at=generated_at,
        head_commit=head_commit,
        max_parse_bytes=max_parse_bytes,
    )
    surfaces = _surface_map_payload(generated_at=generated_at, head_commit=head_commit, by_surface=by_surface)
    manifest = _manifest_payload()

    output_paths = {
        "manifest": (resolved_output / DEFAULT_MANIFEST_NAME).as_posix(),
        "inventory": (resolved_output / DEFAULT_INVENTORY_NAME).as_posix(),
        "symbols": (resolved_output / DEFAULT_SYMBOLS_NAME).as_posix(),
        "legacy_python_symbols": (resolved_output / DEFAULT_LEGACY_SYMBOLS_NAME).as_posix(),
        "surfaces": (resolved_output / DEFAULT_SURFACES_NAME).as_posix(),
        "dependencies": (resolved_output / DEFAULT_DEPENDENCIES_NAME).as_posix(),
    }
    if write:
        write_json(Path(output_paths["inventory"]), inventory)
        write_json(Path(output_paths["symbols"]), symbols)
        write_json(Path(output_paths["legacy_python_symbols"]), symbols)
        write_json(Path(output_paths["dependencies"]), dependency_graph)
        write_json(Path(output_paths["surfaces"]), surfaces)
        write_json(Path(output_paths["manifest"]), manifest)

    duration_seconds = max(0.0, time.perf_counter() - started)
    file_count = int(inventory["summary"]["file_count"])
    symbol_count = int(symbols["summary"]["symbol_count"])
    dependency_edge_count = int(dependency_graph["summary"]["edge_count"])
    return {
        "schema_version": SCAN_SCHEMA_VERSION,
        "ok": True,
        "status": "pass",
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": generated_at,
        "root": root.as_posix(),
        "output_dir": resolved_output.as_posix(),
        "write": bool(write),
        "git": git,
        "summary": {
            "file_count": file_count,
            "symbol_count": symbol_count,
            "dependency_edge_count": dependency_edge_count,
            "surface_count": int(surfaces["summary"]["surface_count"]),
            "total_bytes": int(inventory["summary"]["total_bytes"]),
            "duration_seconds": round(duration_seconds, 6),
            "files_per_second": round(file_count / duration_seconds, 3) if duration_seconds else 0,
            "symbols_per_second": round(symbol_count / duration_seconds, 3) if duration_seconds else 0,
            "dependency_edges_per_second": round(dependency_edge_count / duration_seconds, 3) if duration_seconds else 0,
            "truncated": bool(walk_summary.get("truncated")),
            "skipped_dirs": walk_summary.get("skipped_dirs") or {},
            "by_surface": dict(sorted(by_surface.items())),
            "by_suffix": dict(sorted(by_suffix.items())),
            "parse_failures": dict(sorted(parse_failures.items())),
            "dependency_parse_failures": dict(sorted(dependency_parse_failures.items())),
        },
        "outputs": output_paths,
    }


def markdown_scan(result: Mapping[str, Any]) -> str:
    summary = result.get("summary") if isinstance(result.get("summary"), Mapping) else {}
    outputs = result.get("outputs") if isinstance(result.get("outputs"), Mapping) else {}
    lines = [
        "# Deep Context Federation Repo Scan",
        "",
        f"- Status: `{result.get('status')}`",
        f"- Authority effect: `{result.get('authority_effect')}`",
        f"- No apply: `{result.get('no_apply')}`",
        f"- Root: `{result.get('root')}`",
        f"- Files: `{summary.get('file_count')}` symbols=`{summary.get('symbol_count')}` dependencies=`{summary.get('dependency_edge_count')}` surfaces=`{summary.get('surface_count')}` truncated=`{summary.get('truncated')}`",
        f"- Scan time: `{summary.get('duration_seconds')}`s files/sec=`{summary.get('files_per_second')}`",
        "",
        "## Outputs",
        "",
    ]
    for key, value in sorted(outputs.items()):
        lines.append(f"- `{key}`: `{value}`")
    federation = result.get("federation") if isinstance(result.get("federation"), Mapping) else {}
    if federation:
        fed_summary = federation.get("summary") if isinstance(federation.get("summary"), Mapping) else {}
        lines.extend(
            [
                "",
                "## Federation Build",
                "",
                f"- Status: `{federation.get('status')}`",
                f"- Sources: `{fed_summary.get('source_count')}` entities=`{fed_summary.get('entity_count')}` edges=`{fed_summary.get('edge_count')}`",
                f"- Conflicts: `{fed_summary.get('conflict_count')}` errors=`{fed_summary.get('error_count')}` warnings=`{fed_summary.get('warning_count')}`",
            ]
        )
    lines.extend(["", "## Surfaces", ""])
    by_surface = summary.get("by_surface") if isinstance(summary.get("by_surface"), Mapping) else {}
    for key, value in sorted(by_surface.items()):
        lines.append(f"- `{key}`: `{value}` files")
    return "\n".join(lines).rstrip() + "\n"
