"""Generic, read-only collectors for immutable DCF v2 generations.

The collectors intentionally know nothing about an embedding project's Python
modules.  Project-specific locations are data carried by :class:`ProjectLayout`.
Missing optional ledgers are represented as typed collection findings instead
of being guessed from neighbouring files.
"""

from __future__ import annotations

import ast
import fnmatch
import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def canonical_json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class CollectionError(RuntimeError):
    """A typed failure to read a configured project source."""

    def __init__(self, code: str, source: str, detail: str) -> None:
        self.code = code
        self.source = source
        self.detail = detail
        super().__init__(f"{code}:{source}:{detail}")

    def as_finding(self) -> dict[str, Any]:
        return {
            "finding_id": f"{self.code}:{self.source}",
            "code": self.code,
            "source": self.source,
            "detail": self.detail,
            "authority_effect": "none",
            "no_apply": True,
        }


@dataclass(frozen=True)
class ProjectLayout:
    """Configurable project boundary used by every runtime collector."""

    root: Path
    runtime_root: Path | None = None
    dcf_contract: Path = Path("config/contracts/dcf_v2_contract.json")
    surface_contract: Path = Path("config/contracts/repo_surface_boundary_governance_v1.json")
    active_lease_dir: Path | None = Path("output/task_runtime/active")
    completed_receipt_dir: Path | None = Path("output/task_runtime/completed")
    evidence_dirs: tuple[Path, ...] = (Path("docs/reports/canonical"),)
    source_roots: tuple[Path, ...] = (
        Path("src"),
        Path("lib"),
        Path("app"),
        Path("scripts"),
        Path("tests"),
    )
    source_suffixes: tuple[str, ...] = (".py", ".js", ".jsx", ".ts", ".tsx")
    max_evidence_files: int = 200
    max_receipts: int = 200
    timeline_limit: int = 20

    def __post_init__(self) -> None:
        root = self.root.expanduser().resolve()
        object.__setattr__(self, "root", root)
        if self.runtime_root is not None:
            object.__setattr__(self, "runtime_root", self.runtime_root.expanduser().resolve())

    def resolve(self, relative: Path | None) -> Path | None:
        if relative is None:
            return None
        return relative if relative.is_absolute() else self.root / relative

    @property
    def resolved_runtime_root(self) -> Path:
        return self.runtime_root or self.root / "output" / "dcf_runtime" / "v2"


@dataclass(frozen=True)
class SymbolRow:
    entity_id: str
    fqn: str
    name: str
    kind: str
    path: str
    line: int
    summary: str = ""
    references: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "fqn": self.fqn,
            "name": self.name,
            "kind": self.kind,
            "path": self.path,
            "line": self.line,
            "summary": self.summary,
            "references": list(self.references),
        }


def _run(layout: ProjectLayout, *command: str, check: bool = True) -> str:
    completed = subprocess.run(
        command,
        cwd=layout.root,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and completed.returncode != 0:
        raise CollectionError("command_failed", command[0], completed.stderr.strip())
    return completed.stdout


def git_status_rows(layout: ProjectLayout) -> list[str]:
    return [row for row in _run(layout, "git", "status", "--porcelain=v1", "-uall").splitlines() if row]


def _dirty_path(row: str) -> str:
    value = row[3:]
    return value.split(" -> ", 1)[-1]


def _row_digest(rows: Iterable[str]) -> str:
    return sha256_bytes("\n".join(sorted(rows)).encode("utf-8"))


def _path_digest(path: Path | None) -> str:
    if path is None or not path.exists():
        return sha256_bytes(b"missing")
    if path.is_file():
        return sha256_file(path)
    rows = [
        f"{item.relative_to(path)}:{sha256_file(item)}"
        for item in sorted(path.rglob("*.json"))
        if item.is_file() and not item.is_symlink()
    ]
    return _row_digest(rows)


def _worktree_fingerprint(layout: ProjectLayout, rows: list[str]) -> str:
    evidence: list[str] = []
    for row in rows:
        relative = _dirty_path(row)
        path = layout.root / relative
        if path.is_file() and not path.is_symlink():
            evidence.append(f"{row}:{sha256_file(path)}")
        elif path.is_dir():
            evidence.append(f"{row}:directory")
        else:
            evidence.append(f"{row}:missing")
    return _row_digest(evidence)


def quick_fingerprints(layout: ProjectLayout) -> dict[str, str]:
    head = _run(layout, "git", "rev-parse", "HEAD").strip()
    branch = _run(layout, "git", "branch", "--show-current").strip()
    status = git_status_rows(layout)
    repo_head = sha256_bytes(f"{head}:{branch}".encode())
    worktree = _worktree_fingerprint(layout, status)
    contract = _path_digest(layout.resolve(layout.dcf_contract))
    surface = _path_digest(layout.resolve(layout.surface_contract))
    leases = _path_digest(layout.resolve(layout.active_lease_dir))
    receipts = _path_digest(layout.resolve(layout.completed_receipt_dir))
    evidence = _row_digest(str(_path_digest(layout.resolve(path))) for path in layout.evidence_dirs)
    source_files: set[str] = set()
    for relative in layout.source_roots:
        path = layout.resolve(relative)
        if path is None or not path.exists():
            continue
        output = _run(layout, "git", "ls-files", "--", str(relative), check=False)
        source_files.update(row for row in output.splitlines() if row)
    source_rows: list[str] = []
    for relative in sorted(source_files):
        path = layout.root / relative
        if path.is_file() and not path.is_symlink():
            source_rows.append(f"{relative}:{sha256_file(path)}")
        elif path.is_symlink():
            source_rows.append(f"{relative}:symlink:{path.readlink()}")
        else:
            source_rows.append(f"{relative}:missing")
    source = _row_digest(source_rows)
    repo = sha256_bytes(f"{repo_head}:{worktree}".encode())
    return {
        "repo": repo,
        "repo_head": repo_head,
        "surface": surface,
        "contract": contract,
        "lease": leases,
        "receipt": receipts,
        "evidence": evidence,
        "source": source,
    }


def input_fingerprint(fingerprints: dict[str, str]) -> str:
    return sha256_bytes(canonical_json_bytes(fingerprints))


def collect_repo(layout: ProjectLayout) -> dict[str, Any]:
    rows = git_status_rows(layout)
    return {
        "root": str(layout.root),
        "head_commit": _run(layout, "git", "rev-parse", "HEAD").strip(),
        "branch": _run(layout, "git", "branch", "--show-current").strip(),
        "worktree_fingerprint": _worktree_fingerprint(layout, rows),
        "dirty_count": len(rows),
        "dirty_paths": [_dirty_path(row) for row in rows],
        "dirty_rows": rows,
        "working_state_semantics": "advisory_only_not_mutation_authority",
    }


def _read_json(path: Path, source: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CollectionError("source_unavailable", source, str(path)) from exc
    except (json.JSONDecodeError, OSError, UnicodeError) as exc:
        raise CollectionError("source_invalid", source, str(exc)) from exc
    if not isinstance(payload, dict):
        raise CollectionError("source_invalid", source, "top level must be an object")
    return payload


def collect_dcf_contract(layout: ProjectLayout) -> dict[str, Any]:
    path = layout.resolve(layout.dcf_contract)
    assert path is not None
    contract = _read_json(path, "dcf_contract")
    if contract.get("authority_effect") != "none" or contract.get("no_apply") is not True:
        raise CollectionError("safety_boundary_invalid", "dcf_contract", "authority_effect=none and no_apply=true are required")
    capabilities = contract.get("capabilities", [])
    if capabilities is not None and not isinstance(capabilities, list):
        raise CollectionError("source_invalid", "dcf_contract", "capabilities must be a list")
    return contract


def collect_surfaces(layout: ProjectLayout) -> dict[str, Any]:
    path = layout.resolve(layout.surface_contract)
    assert path is not None
    contract = _read_json(path, "surface_contract")
    raw_surfaces = contract.get("surfaces")
    if not isinstance(raw_surfaces, list):
        raise CollectionError("source_invalid", "surface_contract", "surfaces must be a list")
    expected = contract.get("surface_count_expected")
    if expected is not None and (not isinstance(expected, int) or expected != len(raw_surfaces)):
        raise CollectionError("source_invalid", "surface_contract", "surface_count_expected does not match surfaces")
    rows: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_surfaces):
        if not isinstance(raw, dict):
            conflicts.append({"conflict_id": f"surface_row:{index}", "reason": "not_an_object"})
            continue
        surface_id = str(raw.get("id") or raw.get("surface_id") or "").strip()
        owner_lane = str(raw.get("owner_lane") or "").strip()
        if not surface_id or surface_id in seen:
            conflicts.append({"conflict_id": f"surface_identity:{surface_id or index}", "reason": "missing_or_duplicate_id"})
            continue
        seen.add(surface_id)
        if not owner_lane:
            conflicts.append({"conflict_id": f"surface_owner:{surface_id}", "reason": "owner_missing"})
        rows.append(
            {
                "surface_id": surface_id,
                "display": str(raw.get("display") or surface_id),
                "owner_board": str(raw.get("owner_board") or ""),
                "owner_lane": owner_lane,
                "surface_class": str(raw.get("surface_class") or ""),
                "authority_role": str(raw.get("authority_role") or ""),
                "protected_class": str(raw.get("protected_class") or ""),
                "read_only": bool(raw.get("read_only", False)),
                "requires_heavy_harness": bool(raw.get("requires_heavy_harness", False)),
                "logical_ref": [str(value) for value in raw.get("logical_ref", [])],
                "allowed_write_scopes": [str(value) for value in raw.get("allowed_write_scopes", [])],
                "allowed_command_templates": [
                    str(value) for value in raw.get("allowed_command_templates", [])
                ],
                "required_verifiers": [str(value) for value in raw.get("required_verifiers", [])],
                "claim_boundary": str(raw.get("claim_boundary") or ""),
                "forbidden_crossings": [str(value) for value in raw.get("forbidden_crossings", [])],
                "authority_effect": "none",
                "no_apply": True,
            }
        )
    return {
        "contract_path": str(layout.surface_contract),
        "surface_count": len(rows),
        "surfaces": rows,
        "conflicts": conflicts,
    }


def _collect_json_dir(path: Path | None, *, limit: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if path is None or not path.is_dir():
        return [], []
    rows: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for item in sorted(path.glob("*.json"), key=lambda value: value.stat().st_mtime_ns, reverse=True)[:limit]:
        try:
            payload = json.loads(item.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("top level is not an object")
        except (json.JSONDecodeError, OSError, UnicodeError, ValueError) as exc:
            findings.append({"code": "advisory_artifact_invalid", "path": str(item), "detail": str(exc)})
            continue
        rows.append({"path": str(item), "sha256": sha256_file(item), "payload": payload})
    return rows, findings


def collect_evidence(layout: ProjectLayout, surfaces: dict[str, Any]) -> dict[str, Any]:
    artifacts: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    known_surfaces = {row["surface_id"] for row in surfaces.get("surfaces", [])}
    remaining = layout.max_evidence_files
    for relative in layout.evidence_dirs:
        rows, row_findings = _collect_json_dir(layout.resolve(relative), limit=max(remaining, 0))
        findings.extend(row_findings)
        for row in rows:
            payload = row.pop("payload")
            surface_ids: list[str] = []
            for key in ("surface_id", "surface_ids"):
                value = payload.get(key)
                candidates = value if isinstance(value, list) else [value]
                surface_ids.extend(str(item) for item in candidates if isinstance(item, str) and item in known_surfaces)
            artifacts.append(
                {
                    "artifact_id": f"evidence:{row['sha256'][:20]}",
                    **row,
                    "schema_version": str(payload.get("schema_version") or "unknown"),
                    "surface_ids": sorted(set(surface_ids)),
                    "verifier_result": {
                        "status": "pass" if payload.get("ok") is True else ("fail" if payload.get("ok") is False else "unverified"),
                        "self_reported": True,
                        "advisory_only": True,
                    },
                    "authority_effect": "none",
                    "no_apply": True,
                }
            )
        remaining -= len(rows)
        if remaining <= 0:
            break
    return {"artifacts": artifacts, "findings": findings, "summary": {"artifact_count": len(artifacts), "parse_failure_count": len(findings)}}


def collect_authority(layout: ProjectLayout, surfaces: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    claims: list[dict[str, Any]] = []
    verifier_gates: list[dict[str, Any]] = []
    artifacts = evidence.get("artifacts", [])
    for surface in surfaces.get("surfaces", []):
        surface_id = surface["surface_id"]
        surface_artifacts = [row for row in artifacts if surface_id in row.get("surface_ids", [])]
        claims.append(
            {
                "claim_id": f"surface.{surface_id}.ownership",
                "statement": f"{surface['display']} is owned by {surface['owner_lane']}",
                "surface_id": surface_id,
                "authority": [str(layout.surface_contract)],
                "evidence": list(surface.get("logical_ref", [])),
                "evidence_artifact_ids": [row["artifact_id"] for row in surface_artifacts],
                "verifiers": list(surface.get("required_verifiers", [])),
                "authority_effect": "none",
                "no_apply": True,
            }
        )
        for command in surface.get("required_verifiers", []):
            verifier_gates.append(
                {
                    "verifier_id": sha256_bytes(command.encode("utf-8"))[:16],
                    "surface_id": surface_id,
                    "command": command,
                    "declared": True,
                    "result_status": "unverified",
                    "result_trust": "advisory_only",
                }
            )
    return {
        "authority_contract": str(layout.surface_contract),
        "claims": claims,
        "verifier_gates": verifier_gates,
        "artifacts": artifacts,
        "summary": {
            "claim_count": len(claims),
            "verifier_count": len(verifier_gates),
            "artifact_count": len(artifacts),
        },
    }


def _advisory_records(path: Path | None, *, limit: int, record_type: str) -> dict[str, Any]:
    records, findings = _collect_json_dir(path, limit=limit)
    projected: list[dict[str, Any]] = []
    for row in records:
        payload = row.pop("payload")
        projected.append({**payload, "source_path": row["path"], "source_sha256": row["sha256"], "advisory_only": True, "authority_effect": "none", "no_apply": True})
    return {record_type: projected, "count": len(projected), "findings": findings, "advisory_only": True}


def collect_working_state(layout: ProjectLayout) -> dict[str, Any]:
    active = _advisory_records(layout.resolve(layout.active_lease_dir), limit=layout.max_receipts, record_type="active_leases")
    completed = _advisory_records(layout.resolve(layout.completed_receipt_dir), limit=layout.max_receipts, record_type="completed_receipts")
    return {
        "active_leases": active["active_leases"],
        "active_count": active["count"],
        "completed_receipts": completed["completed_receipts"],
        "completed_count": completed["count"],
        "findings": [*active["findings"], *completed["findings"]],
        "semantics": "advisory_only_not_execution_or_mutation_authority",
        "authority_effect": "none",
        "no_apply": True,
    }


def collect_timeline(layout: ProjectLayout) -> dict[str, Any]:
    output = _run(layout, "git", "log", f"-{layout.timeline_limit}", "--format=%H%x09%cI%x09%s", check=False)
    events = []
    for row in output.splitlines():
        parts = row.split("\t", 2)
        if len(parts) == 3:
            events.append({"commit": parts[0], "committed_at": parts[1], "subject": parts[2]})
    return {"events": events, "event_count": len(events), "authority_effect": "none", "no_apply": True}


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def collect_symbols(layout: ProjectLayout) -> dict[str, Any]:
    symbols: list[SymbolRow] = []
    failures: list[dict[str, str]] = []
    tracked = _run(layout, "git", "ls-files", check=False).splitlines()
    paths = [path for path in tracked if Path(path).suffix in layout.source_suffixes and any(path == str(root) or path.startswith(f"{root}/") for root in layout.source_roots)]
    for relative in paths:
        if not relative.endswith(".py"):
            continue
        try:
            source = (layout.root / relative).read_text(encoding="utf-8")
            tree = ast.parse(source, filename=relative)
        except (OSError, UnicodeError, SyntaxError) as exc:
            failures.append({"path": relative, "error": str(exc)})
            continue
        module = relative[:-3].replace("/", ".")
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            fqn = f"{module}.{node.name}"
            refs = tuple(sorted({name for child in ast.walk(node) if isinstance(child, ast.Call) and (name := _call_name(child.func))}))
            symbols.append(SymbolRow(f"symbol:{sha256_bytes(fqn.encode())[:20]}", fqn, node.name, "class" if isinstance(node, ast.ClassDef) else "function", relative, node.lineno, references=refs))
    return {
        "status": "warn" if failures else "pass",
        "symbols": [row.as_dict() for row in symbols],
        "files_scanned": len(paths),
        "parse_failures": failures[:200],
        "typescript_engine": "not_configured",
    }


def path_matches_surface(path: str, surface: dict[str, Any]) -> bool:
    for raw in [*surface.get("logical_ref", []), *surface.get("allowed_write_scopes", [])]:
        pattern = str(raw).split(" ", 1)[0].removeprefix("./")
        if not pattern or pattern.startswith("-"):
            continue
        normalized = pattern.replace("**", "*")
        if fnmatch.fnmatch(path, normalized) or path == pattern or path.startswith(pattern.rstrip("/*") + "/"):
            return True
    return False


def collect_native(layout: ProjectLayout) -> dict[str, Any]:
    repo = collect_repo(layout)
    errors: dict[str, dict[str, Any]] = {}
    try:
        contract = collect_dcf_contract(layout)
    except CollectionError as exc:
        contract = {}
        errors["contract"] = exc.as_finding()
    try:
        surfaces = collect_surfaces(layout)
    except CollectionError as exc:
        surfaces = {"contract_path": str(layout.surface_contract), "surface_count": 0, "surfaces": [], "conflicts": []}
        errors["surface"] = exc.as_finding()
    evidence = collect_evidence(layout, surfaces)
    authority = collect_authority(layout, surfaces, evidence)
    working_state = collect_working_state(layout)
    return {
        "generated_at": utc_now(),
        "contract": contract,
        "repo": repo,
        "surfaces": surfaces,
        "authority": authority,
        "working_state": working_state,
        "timeline": collect_timeline(layout),
        "symbols": collect_symbols(layout),
        "source_errors": errors,
        "authority_effect": "none",
        "no_apply": True,
    }
