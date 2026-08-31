"""Typed public schema for DCF v2 snapshots and generation manifests."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProjectionStatus = Literal["pass", "warn", "blocked"]
DomainVerdict = Literal["pass", "warn", "blocked", "not_applicable"]
FreshnessStatus = Literal["current", "stale", "missing", "unverified"]
ReadinessTier = Literal["blocked", "context_only", "current_state_ready", "clean_tree_ready"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SafetyBoundary(StrictModel):
    authority_effect: Literal["none"] = "none"
    no_apply: Literal[True] = True
    protected_mutation_authorized: Literal[False] = False
    command_queue_authority: Literal["proposal_only"] = "proposal_only"


class TemporalBoundary(StrictModel):
    formula: Literal["market_tz -> timeblock x weekday x dst x direction = cell"] = (
        "market_tz -> timeblock x weekday x dst x direction = cell"
    )
    weekday_dst_first_class: Literal[True] = True


class CapabilitySnapshot(StrictModel):
    capability_id: str
    projection_status: ProjectionStatus
    domain_verdict: DomainVerdict
    freshness_status: FreshnessStatus
    readiness_tier: ReadinessTier
    stale_override_allowed: bool = False
    required_domains: list[str] = Field(default_factory=list)
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)


class DcfSnapshot(StrictModel):
    schema_version: Literal["dcf_snapshot_v2"] = "dcf_snapshot_v2"
    generation_id: str
    generated_at: str
    reason: str
    input_fingerprint: str
    repo: dict[str, Any]
    source_fingerprints: dict[str, str]
    safety: SafetyBoundary = Field(default_factory=SafetyBoundary)
    p0_temporal_decoupling: TemporalBoundary = Field(default_factory=TemporalBoundary)
    projection_status: ProjectionStatus
    domain_verdict: DomainVerdict
    freshness_status: FreshnessStatus
    readiness_tier: ReadinessTier
    capabilities: dict[str, CapabilitySnapshot]
    context_pack: dict[str, Any]
    metrics: dict[str, Any] = Field(default_factory=dict)

    @field_validator("context_pack")
    @classmethod
    def bounded_context_pack(cls, value: dict[str, Any]) -> dict[str, Any]:
        import json

        encoded = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
        if len(encoded) > 15_000:
            raise ValueError(f"context_pack exceeds 15000 JSON chars: {len(encoded)}")
        return value


class GenerationFile(StrictModel):
    sha256: str
    size_bytes: int = Field(ge=0)


class GenerationManifest(StrictModel):
    schema_version: Literal["dcf_generation_manifest_v2"] = "dcf_generation_manifest_v2"
    generation_id: str
    generated_at: str
    repo_head: str
    worktree_fingerprint: str
    input_fingerprint: str
    safety: SafetyBoundary = Field(default_factory=SafetyBoundary)
    files: dict[str, GenerationFile]
    metrics: dict[str, Any] = Field(default_factory=dict)


class GenerationPointer(StrictModel):
    schema_version: Literal["dcf_generation_pointer_v2"] = "dcf_generation_pointer_v2"
    generation_id: str
    generation_path: str
    published_at: str
    reconciled_at: str | None = None
    manifest_sha256: str


class QueryResponse(StrictModel):
    schema_version: Literal["dcf_query_response_v2"] = "dcf_query_response_v2"
    generation_id: str
    capability_id: str
    target: str | None = None
    depth: int = Field(ge=1, le=4)
    projection_status: ProjectionStatus
    domain_verdict: DomainVerdict
    freshness_status: FreshnessStatus
    readiness_tier: ReadinessTier
    safety: SafetyBoundary = Field(default_factory=SafetyBoundary)
    result: dict[str, Any]


class StatusResponse(StrictModel):
    schema_version: Literal["dcf_status_v2"] = "dcf_status_v2"
    generation_id: str | None
    generated_at: str | None
    projection_status: ProjectionStatus
    domain_verdict: DomainVerdict
    freshness_status: FreshnessStatus
    readiness_tier: ReadinessTier
    unified_tool_ready: bool
    repo: dict[str, Any]
    capabilities: dict[str, dict[str, Any]]
    safety: SafetyBoundary = Field(default_factory=SafetyBoundary)
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    diagnostic_health: dict[str, Any] = Field(default_factory=dict)
    execution_admission: dict[str, Any] = Field(default_factory=dict)
    blocking_capabilities: list[dict[str, Any]] = Field(default_factory=list)
    unrelated_findings: list[dict[str, Any]] = Field(default_factory=list)
