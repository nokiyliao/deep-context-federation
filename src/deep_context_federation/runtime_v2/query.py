"""Capability-aware DCF v2 query engine with real graph traversal."""

from __future__ import annotations

import time
from collections.abc import Callable, Collection
from pathlib import Path
from typing import Any, Protocol

from .capabilities import CapabilityClass, capability_policy
from .models import QueryResponse

GraphTraversal = Callable[..., dict[str, Any]]
DEFAULT_HARD_STALE_CAPABILITIES = frozenset(
    {
        "current-state",
        "operator-projection",
        "authority-lineage",
        "evidence-ledger",
        "governance-cockpit",
    }
)


class GenerationStoreProtocol(Protocol):
    def load_current(
        self, *, verify_file_hashes: bool = True
    ) -> tuple[Any, Any, Path]: ...

    def graph_paths(
        self, generation_dir: Path, *, verify_file_hashes: bool = True
    ) -> tuple[Path, Path | None]: ...


class DcfRuntimeProtocol(Protocol):
    store: GenerationStoreProtocol

    def capability_views(
        self, *, include_data: bool, snapshot: Any
    ) -> tuple[Any, dict[str, dict[str, Any]], Any]: ...


class UnknownCapability(ValueError):
    """Caller/configuration error for a name absent from the capability registry."""

    error_code = "UNKNOWN_CAPABILITY"


class InvalidQuery(ValueError):
    """Raised when a capability query is structurally invalid."""


class FreshnessBlocked(RuntimeError):
    """Raised when a query cannot safely consume stale current-state evidence."""


GRAPH_CAPABILITIES = {"claim-lineage", "code-to-authority", "source-navigation"}
TARGET_REQUIRED = {"code-to-authority"}


def _claim_lineage(
    traverse_graph: GraphTraversal,
    index_path: Path,
    base_index_path: Path | None,
    target: str | None,
    depth: int,
) -> dict[str, Any]:
    query_target = target or "claim:"
    if not target:
        # Surface ownership claims are deterministic and every path must end in authority/evidence/verifier.
        query_target = "ownership"
    return traverse_graph(
        index_path,
        base_index_path=base_index_path,
        target=query_target,
        depth=depth,
        terminal_types={"authority_contract", "evidence", "path", "verifier", "surface"},
        edge_types={"DECLARES", "SUPPORTED_BY", "VERIFIED_BY", "RESULT_RECORDED_IN", "ABOUT"},
        direction="outgoing",
    )


def _code_to_authority(
    traverse_graph: GraphTraversal,
    index_path: Path,
    base_index_path: Path | None,
    target: str,
    depth: int,
) -> dict[str, Any]:
    return traverse_graph(
        index_path,
        base_index_path=base_index_path,
        target=target,
        depth=depth,
        terminal_types={"surface", "authority_contract", "owner"},
        edge_types={"DEFINED_IN", "BELONGS_TO", "DECLARES", "OWNED_BY"},
        direction="outgoing",
    )


def _source_navigation(
    traverse_graph: GraphTraversal,
    index_path: Path,
    base_index_path: Path | None,
    target: str | None,
    depth: int,
) -> dict[str, Any]:
    if not target:
        raise InvalidQuery("source-navigation requires --target")
    return traverse_graph(
        index_path,
        base_index_path=base_index_path,
        target=target,
        depth=depth,
        terminal_types=None,
        edge_types={"DEFINED_IN", "REFERENCES_SYMBOL", "MAY_RESOLVE_TO", "BELONGS_TO"},
        direction="both",
    )


def query_capability(
    runtime: DcfRuntimeProtocol,
    *,
    capability_id: str,
    target: str | None = None,
    depth: int = 2,
    allow_stale: bool = False,
    graph_traverse: GraphTraversal | None = None,
    hard_stale_capabilities: Collection[str] = DEFAULT_HARD_STALE_CAPABILITIES,
) -> tuple[QueryResponse, float]:
    started = time.perf_counter()
    if depth < 1 or depth > 4:
        raise InvalidQuery("depth must be between 1 and 4")
    policy = capability_policy(capability_id)
    if policy is None:
        raise UnknownCapability(capability_id)
    snapshot, _, generation_dir = runtime.store.load_current(verify_file_hashes=True)
    _, capabilities, _ = runtime.capability_views(include_data=True, snapshot=snapshot)
    capability = capabilities.get(capability_id)
    if capability is None:
        raise UnknownCapability(capability_id)
    if policy.capability_class == CapabilityClass.LIVE_CONTROL_SURFACE:
        try:
            projector = getattr(runtime, str(policy.live_projector))
            capability = projector(snapshot=snapshot, capability=capability)
        except (AttributeError, OSError, RuntimeError, ValueError) as exc:
            raise FreshnessBlocked(
                f"{capability_id} live authoritative readback failed: {type(exc).__name__}: {exc}"
            ) from exc
    freshness = str(capability["freshness_status"])
    if freshness != "current":
        if capability_id in hard_stale_capabilities or not allow_stale or not capability.get("stale_override_allowed", False):
            raise FreshnessBlocked(f"{capability_id} is {freshness}; refresh is required")
    if capability_id in TARGET_REQUIRED and not target:
        raise InvalidQuery(f"{capability_id} requires --target")

    if capability_id in GRAPH_CAPABILITIES:
        if graph_traverse is None:
            raise InvalidQuery(
                f"{capability_id} requires a graph traversal adapter"
            )
        index_path, base_index_path = runtime.store.graph_paths(
            generation_dir, verify_file_hashes=False
        )
        if capability_id == "claim-lineage":
            result = _claim_lineage(
                graph_traverse, index_path, base_index_path, target, depth
            )
        elif capability_id == "code-to-authority":
            result = _code_to_authority(
                graph_traverse, index_path, base_index_path, str(target), depth
            )
        else:
            result = _source_navigation(
                graph_traverse, index_path, base_index_path, target, depth
            )
    elif capability_id == "surface-splits":
        data = capability.get("data", {})
        result = {
            "surfaces": data.get("surfaces", []),
            "conflicts": data.get("conflicts", []),
            "surface_count": data.get("surface_count", 0),
        }
    elif capability_id == "surface-map" and target:
        rows = [row for row in capability.get("data", {}).get("surfaces", []) if row.get("surface_id") == target]
        result = {"surfaces": rows, "resolved": bool(rows)}
    elif capability_id == "authority-lineage" and target:
        data = capability.get("data", {})
        claims = [
            row
            for row in data.get("claims", [])
            if target in str(row.get("claim_id", ""))
            or target in str(row.get("surface_id", ""))
            or target in str(row.get("statement", ""))
        ]
        surface_ids = {str(row.get("surface_id", "")) for row in claims}
        result = {
            "authority_contract": data.get("authority_contract"),
            "claims": claims,
            "verifier_gates": [
                row
                for row in data.get("verifier_gates", [])
                if str(row.get("surface_id", "")) in surface_ids
            ],
            "resolved": bool(claims),
        }
    else:
        result = capability.get("data", {})
    response = QueryResponse(
        generation_id=snapshot.generation_id,
        capability_id=capability_id,
        target=target,
        depth=depth,
        projection_status=capability["projection_status"],
        domain_verdict=capability["domain_verdict"],
        freshness_status=capability["freshness_status"],
        readiness_tier=capability["readiness_tier"],
        result=result,
    )
    return response, (time.perf_counter() - started) * 1000
