"""Explicit DCF capability freshness classes and query policies."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CapabilityClass(StrEnum):
    LIVE_CONTROL_SURFACE = "LIVE_CONTROL_SURFACE"
    SNAPSHOT_ANALYTICS = "SNAPSHOT_ANALYTICS"


@dataclass(frozen=True)
class CapabilityPolicy:
    capability_class: CapabilityClass
    live_projector: str | None = None


_SNAPSHOT_CAPABILITIES = {
    "architecture-timeline",
    "claim-lineage",
    "code-to-authority",
    "command-transaction-preflight",
    "convergence-commander",
    "current-state",
    "evidence-ledger",
    "governance-cockpit",
    "lease-autopilot",
    "model-context",
    "operator-projection",
    "promotion-boundary",
    "r19-context",
    "safety-boundary-action",
    "source-health",
    "source-navigation",
    "surface-map",
    "surface-splits",
    "unified-tool-readiness",
    "verifier-gates",
}

CAPABILITY_REGISTRY: dict[str, CapabilityPolicy] = {
    capability_id: CapabilityPolicy(CapabilityClass.SNAPSHOT_ANALYTICS)
    for capability_id in sorted(_SNAPSHOT_CAPABILITIES)
}
CAPABILITY_REGISTRY.update(
    {
        "authority-lineage": CapabilityPolicy(
            CapabilityClass.LIVE_CONTROL_SURFACE,
            live_projector="live_authority_lineage",
        ),
        "report-back-intake": CapabilityPolicy(
            CapabilityClass.LIVE_CONTROL_SURFACE,
            live_projector="live_report_back_intake",
        ),
    }
)


def capability_policy(capability_id: str) -> CapabilityPolicy | None:
    return CAPABILITY_REGISTRY.get(capability_id)
