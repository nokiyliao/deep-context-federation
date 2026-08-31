"""Transactional, project-configurable DCF v2 generation runtime.

This module is deliberately read-only with respect to project authority.  Its
only writes are immutable runtime generations and their atomic pointers.
"""

from __future__ import annotations

import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .collectors import (
    ProjectLayout,
    collect_native,
    input_fingerprint,
    quick_fingerprints,
)
from .graph import build_index, graph_summary, traverse
from .models import DcfSnapshot, GenerationFile, GenerationManifest, StatusResponse
from .storage import (
    GenerationStore,
    GenerationTransactionError,
    GenerationUnavailable,
    atomic_write_json,
    canonical_json_bytes,
    sha256_file,
    utc_now,
)


RUNTIME_SCHEMA_VERSION = "dcf_runtime_v2"
SNAPSHOT_SCHEMA_VERSION = "dcf_snapshot_v2"
TEMPORAL_FORMULA = "market_tz -> timeblock x weekday x dst x direction = cell"


DEFAULT_CAPABILITIES = (
    "current-state",
    "operator-projection",
    "surface-map",
    "authority-lineage",
    "claim-lineage",
    "evidence-ledger",
    "verifier-gates",
    "architecture-timeline",
    "source-navigation",
    "code-to-authority",
    "model-context",
    "source-health",
    "lease-autopilot",
    "report-back-intake",
    "unified-tool-readiness",
)


def _capability(
    capability_id: str,
    data: dict[str, Any],
    *,
    status: str = "pass",
    verdict: str | None = None,
    freshness: str = "current",
    readiness: str = "context_only",
    required_domains: list[str] | None = None,
    blockers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "capability_id": capability_id,
        "projection_status": status,
        "domain_verdict": verdict or status,
        "freshness_status": freshness,
        "readiness_tier": readiness,
        "stale_override_allowed": capability_id in {"architecture-timeline", "source-navigation", "claim-lineage"},
        "required_domains": required_domains or [],
        "blockers": blockers or [],
        "data": data,
    }


def _project_capabilities(native: dict[str, Any], fingerprints: dict[str, str]) -> dict[str, dict[str, Any]]:
    repo = native["repo"]
    surfaces = native["surfaces"]
    authority = native["authority"]
    state = native["working_state"]
    symbols = native["symbols"]
    errors = native.get("source_errors", {})
    typed_blockers = list(errors.values()) + list(surfaces.get("conflicts", []))
    missing_contract = "contract" in errors
    missing_surface = "surface" in errors
    surface_status = "blocked" if missing_surface or surfaces.get("conflicts") else "pass"
    source_status = "blocked" if errors else ("warn" if symbols.get("status") == "warn" else "pass")
    working_state_status = "warn" if repo.get("dirty_count") or state.get("findings") else "pass"

    current_state = {
        "repo": repo,
        "working_state": state,
        "surface_summary": {"surface_count": surfaces.get("surface_count", 0), "conflict_count": len(surfaces.get("conflicts", []))},
        "authority_summary": authority.get("summary", {}),
        "typed_blockers": typed_blockers,
        "working_state_advisory_only": True,
        "authority_effect": "none",
        "no_apply": True,
    }
    surface_map = {"surface_count": surfaces.get("surface_count", 0), "surfaces": surfaces.get("surfaces", []), "conflicts": surfaces.get("conflicts", [])}
    authority_lineage = {key: authority.get(key) for key in ("authority_contract", "claims", "verifier_gates", "summary")}
    symbol_summary = {key: symbols.get(key) for key in ("status", "files_scanned", "parse_failures", "typescript_engine")}
    symbol_summary["symbol_count"] = len(symbols.get("symbols", []))
    capabilities: dict[str, dict[str, Any]] = {
        "current-state": _capability("current-state", current_state, status="blocked" if missing_contract or missing_surface else working_state_status, verdict="blocked" if missing_contract or missing_surface else working_state_status, readiness="current_state_ready", required_domains=["repo", "contract", "surface", "lease", "receipt"], blockers=typed_blockers),
        "operator-projection": _capability("operator-projection", {"schema_version": "dcf_operator_projection_v2", "current_state": current_state, "authority_effect": "none", "no_apply": True}, status="blocked" if missing_contract or missing_surface else working_state_status, required_domains=["repo", "contract", "surface", "lease", "receipt"], blockers=typed_blockers),
        "surface-map": _capability("surface-map", surface_map, status=surface_status, required_domains=["surface"], blockers=typed_blockers if missing_surface else surfaces.get("conflicts", [])),
        "authority-lineage": _capability("authority-lineage", authority_lineage, status=surface_status, required_domains=["surface", "evidence"], blockers=typed_blockers if missing_surface else []),
        "claim-lineage": _capability("claim-lineage", {"claims": authority.get("claims", [])}, status=surface_status, required_domains=["surface", "evidence"]),
        "evidence-ledger": _capability("evidence-ledger", {"artifacts": authority.get("artifacts", []), "claims": authority.get("claims", []), "summary": authority.get("summary", {})}, status=surface_status, required_domains=["surface", "evidence"]),
        "verifier-gates": _capability("verifier-gates", {"verifier_gates": authority.get("verifier_gates", []), "summary": authority.get("summary", {})}, status=surface_status, required_domains=["surface", "evidence"]),
        "architecture-timeline": _capability("architecture-timeline", native["timeline"], required_domains=["repo_head"]),
        "source-navigation": _capability("source-navigation", symbol_summary, status="warn" if symbols.get("status") == "warn" else "pass", required_domains=["source"]),
        "code-to-authority": _capability("code-to-authority", symbol_summary, status="blocked" if missing_surface else ("warn" if symbols.get("status") == "warn" else "pass"), required_domains=["source", "surface"]),
        "lease-autopilot": _capability("lease-autopilot", {"working_state": state, "advisory_only": True}, status=working_state_status, required_domains=["lease"]),
        "report-back-intake": _capability("report-back-intake", {"active_tasks": state.get("active_leases", []), "completed_receipts": state.get("completed_receipts", []), "advisory_only": True}, status="warn" if state.get("findings") else "pass", required_domains=["lease", "receipt"]),
        "source-health": _capability("source-health", {"domains": {key: {"fingerprint": value, "freshness_status": "missing" if key in errors else "current", "error": errors.get(key)} for key, value in fingerprints.items()}, "typed_blockers": typed_blockers}, status=source_status, required_domains=list(fingerprints), blockers=typed_blockers),
    }
    context = {
        "repo": {key: repo.get(key) for key in ("head_commit", "branch", "dirty_count", "working_state_semantics")},
        "surface_count": surfaces.get("surface_count", 0),
        "active_task_count": state.get("active_count", 0),
        "recent_commits": native["timeline"].get("events", [])[:10],
        "typed_blockers": typed_blockers,
        "authority_effect": "none",
        "no_apply": True,
    }
    capabilities["model-context"] = _capability("model-context", context, status=source_status, required_domains=["repo", "contract", "surface", "lease", "receipt"], blockers=typed_blockers)
    ready = not errors and not surfaces.get("conflicts") and symbols.get("status") == "pass"
    capabilities["unified-tool-readiness"] = _capability(
        "unified-tool-readiness",
        {"unified_tool_ready": ready, "blocked_capabilities": [key for key, row in capabilities.items() if row["projection_status"] == "blocked"]},
        status="pass" if ready else "warn",
        verdict="pass" if ready else "warn",
        readiness="clean_tree_ready" if ready and not repo.get("dirty_count") else "current_state_ready",
        required_domains=list(fingerprints),
        blockers=typed_blockers,
    )

    declared = native.get("contract", {}).get("capabilities")
    for capability_id in declared if isinstance(declared, list) else DEFAULT_CAPABILITIES:
        if not isinstance(capability_id, str) or capability_id in capabilities:
            continue
        blocker = {
            "finding_id": f"collector_not_configured:{capability_id}",
            "code": "collector_not_configured",
            "capability_id": capability_id,
            "detail": "the project contract declares a capability without a generic collector",
            "authority_effect": "none",
            "no_apply": True,
        }
        capabilities[capability_id] = _capability(capability_id, {"typed_absence": blocker}, status="warn", verdict="warn", blockers=[blocker])
    return capabilities


class DcfRuntime:
    """Build and query immutable DCF v2 runtime generations."""

    def __init__(
        self,
        repo_root: Path | None = None,
        *,
        runtime_root: Path | None = None,
        layout: ProjectLayout | None = None,
    ) -> None:
        if layout is None:
            if repo_root is None:
                raise ValueError("repo_root or layout is required")
            layout = ProjectLayout(repo_root, runtime_root=runtime_root)
        elif repo_root is not None and repo_root.expanduser().resolve() != layout.root:
            raise ValueError("repo_root and layout.root disagree")
        elif runtime_root is not None and runtime_root.expanduser().resolve() != layout.resolved_runtime_root:
            raise ValueError("runtime_root and layout.runtime_root disagree")
        self.layout = layout
        self.repo_root = layout.root
        self.store = GenerationStore(self.repo_root, runtime_root=layout.resolved_runtime_root)

    def _build_snapshot(self, generation_id: str, reason: str, fingerprints: dict[str, str], native: dict[str, Any]) -> DcfSnapshot:
        capabilities = _project_capabilities(native, fingerprints)
        statuses = [row["projection_status"] for row in capabilities.values()]
        projection = "blocked" if "blocked" in statuses else ("warn" if "warn" in statuses else "pass")
        verdicts = [row["domain_verdict"] for row in capabilities.values()]
        verdict = "blocked" if "blocked" in verdicts else ("warn" if "warn" in verdicts else "pass")
        ready = bool(capabilities["unified-tool-readiness"]["data"]["unified_tool_ready"])
        context_pack = dict(capabilities["model-context"]["data"])
        return DcfSnapshot.model_validate({
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "generation_id": generation_id,
            "generated_at": utc_now(),
            "reason": reason,
            "input_fingerprint": input_fingerprint(fingerprints),
            "repo": native["repo"],
            "source_fingerprints": fingerprints,
            "safety": {"authority_effect": "none", "no_apply": True, "protected_mutation_authorized": False, "command_queue_authority": "proposal_only"},
            "p0_temporal_decoupling": {"formula": TEMPORAL_FORMULA, "weekday_dst_first_class": True},
            "projection_status": projection,
            "domain_verdict": verdict,
            "freshness_status": "current",
            "readiness_tier": "clean_tree_ready" if ready and not native["repo"].get("dirty_count") else ("current_state_ready" if ready else "context_only"),
            "capabilities": capabilities,
            "context_pack": context_pack,
            "metrics": {"runtime_schema_version": RUNTIME_SCHEMA_VERSION, "collector_boundary": "project_layout", "working_state_advisory_only": True},
        })

    def _generation_id(self, fingerprints: dict[str, str]) -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        head = subprocess_short_head(self.layout)
        return f"{timestamp}-{head}-{input_fingerprint(fingerprints)[:12]}"

    def _stage_generation(self, directory: Path, snapshot: DcfSnapshot, native: dict[str, Any]) -> dict[str, Any]:
        context_path = directory / "context.json"
        index_path = directory / "index.sqlite"
        atomic_write_json(context_path, snapshot.model_dump(mode="json"))
        return build_index(index_path, snapshot=snapshot.model_dump(mode="json"), native=native)

    def refresh(
        self,
        *,
        write: bool = True,
        if_needed: bool = False,
        reason: str = "manual",
        failpoint: str | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        fingerprints = quick_fingerprints(self.layout)
        fingerprint = input_fingerprint(fingerprints)
        if write and if_needed:
            try:
                current, manifest, _ = self.store.load_current()
                if current.input_fingerprint == fingerprint:
                    reconciled_at = self.store.reconcile_current(current.generation_id)
                    return {"status": "unchanged", "generation_id": current.generation_id, "manifest": manifest.model_dump(mode="json"), "reconciled_at": reconciled_at, "authority_effect": "none", "no_apply": True}
            except GenerationUnavailable:
                pass
        native = collect_native(self.layout)
        generation_id = self._generation_id(fingerprints)
        snapshot = self._build_snapshot(generation_id, reason, fingerprints, native)
        if not write:
            with tempfile.TemporaryDirectory(prefix="dcf-v2-validate-") as temporary:
                stage = Path(temporary) / generation_id
                stage.mkdir()
                graph_metrics = self._stage_generation(stage, snapshot, native)
                files = {
                    name: GenerationFile(sha256=sha256_file(stage / name), size_bytes=(stage / name).stat().st_size)
                    for name in ("context.json", "index.sqlite")
                }
                manifest = GenerationManifest(
                    generation_id=generation_id,
                    generated_at=snapshot.generated_at,
                    repo_head=str(snapshot.repo.get("head_commit", "")),
                    worktree_fingerprint=str(snapshot.repo.get("worktree_fingerprint", "")),
                    input_fingerprint=snapshot.input_fingerprint,
                    files=files,
                    metrics={"graph": graph_metrics},
                )
                graph_summary(stage / "index.sqlite")
            return {"status": "validated_no_write", "generation_id": generation_id, "snapshot": snapshot.model_dump(mode="json"), "manifest": manifest.model_dump(mode="json"), "elapsed_ms": round((time.perf_counter() - started) * 1000, 3), "authority_effect": "none", "no_apply": True}

        with self.store.single_flight():
            try:
                with self.store.new_stage() as stage:
                    graph_metrics = self._stage_generation(stage, snapshot, native)
                    if failpoint == "before_publish":
                        raise GenerationTransactionError("failpoint:before_publish")
                    manifest = self.store.publish_staging(
                        stage_dir=stage,
                        snapshot=snapshot,
                        metrics={"graph": graph_metrics},
                    )
            except Exception as exc:
                self.store.write_failure(reason=reason, error=exc, generation_id=generation_id)
                if isinstance(exc, GenerationTransactionError):
                    raise
                raise GenerationTransactionError(str(exc)) from exc
        pointer = self.store.read_pointer()
        return {"status": "published", "generation_id": generation_id, "generation_path": pointer.generation_path if pointer else str(self.store.generation_dir(generation_id)), "manifest": manifest.model_dump(mode="json"), "snapshot": snapshot.model_dump(mode="json"), "elapsed_ms": round((time.perf_counter() - started) * 1000, 3), "authority_effect": "none", "no_apply": True}

    def capability_views(
        self,
        *,
        include_data: bool = True,
        snapshot: DcfSnapshot | None = None,
    ) -> tuple[DcfSnapshot, dict[str, dict[str, Any]], list[dict[str, Any]]]:
        if snapshot is None:
            snapshot, _, _ = self.store.load_current(verify_file_hashes=True)
        current = quick_fingerprints(self.layout)
        capabilities: dict[str, dict[str, Any]] = {}
        blockers: list[dict[str, Any]] = []
        for capability_id, row in snapshot.capabilities.items():
            payload = row.model_dump(mode="json")
            impacted = [
                domain
                for domain in payload.get("required_domains", [])
                if current.get(domain) != snapshot.source_fingerprints.get(domain)
            ]
            if impacted:
                payload["freshness_status"] = "stale"
                payload["blockers"] = [
                    *payload.get("blockers", []),
                    {
                        "finding_id": f"stale_capability:{capability_id}",
                        "code": "stale_capability",
                        "capability_id": capability_id,
                        "changed_domains": impacted,
                        "generation_id": snapshot.generation_id,
                        "authority_effect": "none",
                        "no_apply": True,
                    },
                ]
            blockers.extend(payload.get("blockers", []))
            if not include_data:
                payload.pop("data", None)
                payload["blocker_count"] = len(payload.get("blockers", []))
                payload.pop("blockers", None)
            capabilities[capability_id] = payload
        return snapshot, capabilities, blockers

    def current_domain_fingerprints(self, domains: list[str]) -> dict[str, str]:
        """Return one forced action-scoped fingerprint token for named domains."""

        current = quick_fingerprints(self.layout)
        missing = sorted(domain for domain in domains if not current.get(domain))
        if missing:
            raise GenerationTransactionError(
                "required DCF domain fingerprints are unavailable: " + ",".join(missing)
            )
        return {domain: str(current[domain]) for domain in sorted(set(domains))}

    def live_authority_lineage(
        self,
        *,
        snapshot: DcfSnapshot,
        capability: dict[str, Any],
    ) -> dict[str, Any]:
        current = quick_fingerprints(self.layout)
        changed = [domain for domain in ("surface", "evidence") if current.get(domain) != snapshot.source_fingerprints.get(domain)]
        if not changed:
            return capability
        native = collect_native(self.layout)
        if native.get("source_errors", {}).get("surface"):
            raise RuntimeError(f"typed_source_unavailable:{native['source_errors']['surface']}")
        payload = dict(capability)
        payload.update({"projection_status": "pass", "domain_verdict": "pass", "freshness_status": "current", "readiness_tier": "context_only"})
        payload["data"] = {
            key: native["authority"].get(key)
            for key in ("authority_contract", "claims", "verifier_gates", "summary")
        }
        payload["data"]["live_readback"] = {
            "schema_version": "dcf_authority_lineage_live_readback_v1",
            "projection_source": "configured_project_layout",
            "base_generation_id": snapshot.generation_id,
            "changed_domains": changed,
            "authority_effect": "none",
            "no_apply": True,
        }
        return payload

    def live_report_back_intake(
        self,
        *,
        snapshot: DcfSnapshot,
        capability: dict[str, Any],
    ) -> dict[str, Any]:
        current = quick_fingerprints(self.layout)
        changed = [domain for domain in ("lease", "receipt") if current.get(domain) != snapshot.source_fingerprints.get(domain)]
        if not changed:
            return capability
        state = collect_native(self.layout)["working_state"]
        payload = dict(capability)
        payload.update({"projection_status": "pass", "domain_verdict": "pass", "freshness_status": "current", "readiness_tier": "context_only"})
        payload["data"] = {
            "active_tasks": state.get("active_leases", []),
            "completed_receipts": state.get("completed_receipts", []),
            "advisory_only": True,
            "live_readback": {
                "schema_version": "dcf_report_back_live_readback_v1",
                "projection_source": "configured_project_layout",
                "base_generation_id": snapshot.generation_id,
                "changed_domains": changed,
                "authority_effect": "none",
                "no_apply": True,
            },
        }
        return payload

    def query(self, capability_id: str, *, target: str | None = None, depth: int = 2) -> dict[str, Any]:
        from .query import query_capability

        response, _ = query_capability(
            self,
            capability_id=capability_id,
            target=target,
            depth=depth,
            graph_traverse=traverse,
        )
        return response.model_dump(mode="json")

    def status(self, *, snapshot: DcfSnapshot | None = None) -> StatusResponse:
        if snapshot is None:
            try:
                snapshot, _, _ = self.store.load_current(verify_file_hashes=True)
            except GenerationUnavailable as exc:
                return StatusResponse(generation_id=None, generated_at=None, projection_status="blocked", domain_verdict="blocked", freshness_status="missing", readiness_tier="blocked", unified_tool_ready=False, repo={}, capabilities={}, blockers=[{"finding_id": "generation_unavailable", "code": "generation_unavailable", "detail": str(exc)}])
        _, capabilities, blockers = self.capability_views(include_data=False, snapshot=snapshot)
        status_order = {"pass": 0, "warn": 1, "blocked": 2}
        freshness_order = {"current": 0, "unverified": 1, "stale": 2, "missing": 3}
        projection = max((row["projection_status"] for row in capabilities.values()), key=lambda value: status_order.get(value, 3), default="pass")
        verdict = max((row["domain_verdict"] for row in capabilities.values()), key=lambda value: status_order.get(value, 3), default="pass")
        freshness = max((row["freshness_status"] for row in capabilities.values()), key=lambda value: freshness_order.get(value, 4), default="current")
        ready = bool(snapshot.capabilities.get("unified-tool-readiness") and snapshot.capabilities["unified-tool-readiness"].data.get("unified_tool_ready")) and freshness == "current" and projection != "blocked"
        return StatusResponse(generation_id=snapshot.generation_id, generated_at=snapshot.generated_at, projection_status=projection, domain_verdict=verdict, freshness_status=freshness, readiness_tier="blocked" if projection == "blocked" else snapshot.readiness_tier, unified_tool_ready=ready, repo=snapshot.repo, capabilities=capabilities, blockers=blockers)

    def verify_current(self) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        try:
            snapshot, _, directory = self.store.load_current(allow_last_good=False)
            checks.append({"check": "generation_integrity", "ok": True, "generation_id": snapshot.generation_id})
            graph = graph_summary(directory / "index.sqlite")
            checks.append({"check": "graph_generation_identity", "ok": graph.get("graph_generation_id") == snapshot.generation_id, **graph})
            checks.append({"check": "authority_effect_none", "ok": snapshot.safety.authority_effect == "none"})
            checks.append({"check": "no_apply", "ok": snapshot.safety.no_apply is True})
            checks.append({"check": "context_bound", "ok": len(canonical_json_bytes(snapshot.context_pack)) <= 15_001})
            checks.append({"check": "p0_temporal_formula", "ok": snapshot.p0_temporal_decoupling.formula == TEMPORAL_FORMULA})
        except Exception as exc:
            checks.append({"check": "generation_integrity", "ok": False, "error": str(exc)})
        ok = all(bool(row.get("ok")) for row in checks)
        return {"schema_version": "dcf_verify_result_v2", "verification_scope": "generation_integrity", "ok": ok, "status": "pass" if ok else "blocked", "checks": checks, "authority_effect": "none", "no_apply": True}


def subprocess_short_head(layout: ProjectLayout) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "--short=10", "HEAD"],
        cwd=layout.root,
        check=False,
        text=True,
        capture_output=True,
    )
    return completed.stdout.strip() or "unknown"
