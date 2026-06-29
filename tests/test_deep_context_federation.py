from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from deep_context_federation.adjudicate import adjudicate_target
from deep_context_federation.agent_ci import build_agent_ci
from deep_context_federation.bench import benchmark_build
from deep_context_federation.bootstrap import bootstrap_federation
from deep_context_federation.builder import build_federation, codebase_memory_source
from deep_context_federation.capabilities import build_capabilities
from deep_context_federation.cache import DEFAULT_CACHE_NAME
from deep_context_federation.compose import compose_manifests
from deep_context_federation.context_pack import pack_context
from deep_context_federation.diff import diff_federations
from deep_context_federation.doctor import doctor_federation
from deep_context_federation.efficiency_gate import evaluate_efficiency_gate
from deep_context_federation.efficiency_gate import load_efficiency_gate_policy
from deep_context_federation.efficiency_gate import normalize_efficiency_gate_policy
from deep_context_federation.efficiency_report import build_efficiency_report
from deep_context_federation.graph import trace_federation
from deep_context_federation.intake import build_agent_intake
from deep_context_federation.manifest import validate_manifest
from deep_context_federation.quality_gate import evaluate_quality_gate
from deep_context_federation.quality_gate import load_quality_gate_policy
from deep_context_federation.quality_gate import normalize_quality_gate_policy
from deep_context_federation.query import query_federation
from deep_context_federation.rank import rank_entities
from deep_context_federation.rank import rank_sources
from deep_context_federation.resolve import resolve_target
from deep_context_federation.scanner import scan_repository
from deep_context_federation.schemas import build_schema_registry
from deep_context_federation.schemas import validate_artifact_contract
from deep_context_federation.sqlite_query import query_sqlite
from deep_context_federation.target_review import review_targets
from deep_context_federation.target_review_gate import evaluate_target_review_gate
from deep_context_federation.target_review_gate import normalize_target_review_gate_policy
from deep_context_federation.task_brief import build_task_brief
from deep_context_federation.verifier import verify_federation
from deep_context_federation.workflow_plan import build_workflow_plan
from deep_context_federation.workflow_run import build_workflow_run


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_MANIFEST = REPO_ROOT / "examples/deep_context_federation.example.json"
EXAMPLE_QUALITY_GATE_POLICY = REPO_ROOT / "examples/quality_gate_policy.example.json"
EXAMPLE_EFFICIENCY_GATE_POLICY = REPO_ROOT / "examples/efficiency_gate_policy.example.json"


def test_quality_gate_policy_example_loads() -> None:
    policy = load_quality_gate_policy(EXAMPLE_QUALITY_GATE_POLICY)

    assert policy["schema_version"] == "deep_context_federation_quality_gate_policy_v1"
    assert policy["policy_id"] == "example_context_minimum"
    assert policy["authority_effect"] == "none"
    assert policy["no_apply"] is True
    assert policy["unknown_keys"] == []
    assert policy["validation_errors"] == []
    assert "repo_file_inventory" in policy["require_sources"]


def test_efficiency_gate_policy_example_loads() -> None:
    policy = load_efficiency_gate_policy(EXAMPLE_EFFICIENCY_GATE_POLICY)

    assert policy["schema_version"] == "deep_context_federation_efficiency_gate_policy_v1"
    assert policy["policy_id"] == "example_context_efficiency_minimum"
    assert policy["authority_effect"] == "none"
    assert policy["no_apply"] is True
    assert policy["schema_supported"] is True
    assert policy["unknown_keys"] == []
    assert policy["validation_errors"] == []
    assert policy["min_read_first_savings_percent"] == 50.0
    assert "read_first" in policy["require_artifact_roles"]
    assert validate_artifact_contract(policy)["ok"] is True


def test_capabilities_manifest_is_machine_readable() -> None:
    payload = build_capabilities()

    assert payload["schema_version"] == "deep_context_federation_capabilities_v1"
    assert payload["status"] == "ok"
    assert payload["authority_effect"] == "none"
    assert payload["no_apply"] is True
    assert payload["package"]["cli"] == "dcf"
    assert payload["package"]["version"] == "0.26.0"

    command_names = {row["command"] for row in payload["commands"]}
    assert {
        "capabilities",
        "bootstrap",
        "workflow-plan",
        "workflow-run",
        "efficiency-report",
        "efficiency-gate",
        "agent-ci",
        "intake",
        "build",
        "scan",
        "schema",
        "validate-artifact",
        "adjudicate",
        "brief",
        "pack",
        "quality-gate",
        "query",
        "resolve",
        "review-targets",
        "review-gate",
        "sql",
        "doctor",
    } <= command_names
    query_presets = {row["preset"] for row in payload["query_presets"]}
    assert {"surface-splits", "claim-lineage", "code-to-authority", "operator-projection"} <= query_presets
    sql_presets = {row["preset"] for row in payload["sql_presets"]}
    assert {"source-health", "search", "code-to-authority"} <= sql_presets

    contracts = payload["contracts"]["artifact_contracts"]
    by_kind = {row["artifact_kind"]: row for row in contracts}
    assert by_kind["quality_gate_policy"]["schema_version"] == "deep_context_federation_quality_gate_policy_v1"
    assert by_kind["quality_gate_policy"]["authority_effect"] == "none"
    assert by_kind["quality_gate_policy"]["no_apply"] is True
    assert by_kind["federation"]["schema_version"] == "deep_context_federation_v1"
    assert by_kind["efficiency_gate"]["schema_version"] == "deep_context_federation_efficiency_gate_v1"
    assert by_kind["efficiency_gate_policy"]["schema_version"] == "deep_context_federation_efficiency_gate_policy_v1"
    assert by_kind["efficiency_report"]["schema_version"] == "deep_context_federation_efficiency_report_v1"
    assert by_kind["agent_ci"]["schema_version"] == "deep_context_federation_agent_ci_v1"
    assert by_kind["workflow_plan"]["schema_version"] == "deep_context_federation_workflow_plan_v1"
    assert by_kind["workflow_run"]["schema_version"] == "deep_context_federation_workflow_run_v1"
    assert payload["safety_boundaries"]["external_tool_install"] == "never"


def test_schema_registry_and_contract_validation() -> None:
    registry = build_schema_registry()

    assert registry["schema_version"] == "deep_context_federation_schema_registry_v1"
    assert registry["authority_effect"] == "none"
    assert registry["no_apply"] is True
    by_kind = {row["artifact_kind"]: row for row in registry["artifact_schemas"]}
    assert by_kind["federation"]["schema_version"] == "deep_context_federation_v1"
    assert by_kind["quality_gate_policy"]["schema_version"] == "deep_context_federation_quality_gate_policy_v1"
    assert by_kind["contract_validation"]["schema_version"] == "deep_context_federation_contract_validation_v1"
    assert by_kind["context_pack"]["schema_version"] == "deep_context_federation_context_pack_v1"
    assert by_kind["task_brief"]["schema_version"] == "deep_context_federation_task_brief_v1"
    assert by_kind["agent_intake"]["schema_version"] == "deep_context_federation_agent_intake_v1"
    assert by_kind["resolve"]["schema_version"] == "deep_context_federation_resolve_v1"
    assert by_kind["adjudication"]["schema_version"] == "deep_context_federation_adjudicate_v1"
    assert by_kind["target_review"]["schema_version"] == "deep_context_federation_target_review_v1"
    assert by_kind["target_review_gate"]["schema_version"] == "deep_context_federation_target_review_gate_v1"
    assert by_kind["target_review_gate_policy"]["schema_version"] == "deep_context_federation_target_review_gate_policy_v1"
    assert by_kind["efficiency_gate"]["schema_version"] == "deep_context_federation_efficiency_gate_v1"
    assert by_kind["efficiency_gate_policy"]["schema_version"] == "deep_context_federation_efficiency_gate_policy_v1"
    assert by_kind["efficiency_report"]["schema_version"] == "deep_context_federation_efficiency_report_v1"
    assert by_kind["agent_ci"]["schema_version"] == "deep_context_federation_agent_ci_v1"
    assert by_kind["workflow_plan"]["schema_version"] == "deep_context_federation_workflow_plan_v1"
    assert by_kind["workflow_run"]["schema_version"] == "deep_context_federation_workflow_run_v1"

    policy = json.loads(EXAMPLE_QUALITY_GATE_POLICY.read_text(encoding="utf-8"))
    valid = validate_artifact_contract(policy)
    assert valid["schema_version"] == "deep_context_federation_contract_validation_v1"
    assert valid["ok"] is True
    assert valid["artifact_kind"] == "quality_gate_policy"

    invalid = dict(policy)
    invalid.pop("no_apply")
    failed = validate_artifact_contract(invalid, artifact_kind="quality_gate_policy")
    assert failed["ok"] is False
    error_ids = {row["id"] for row in failed["errors"]}
    assert "$.no_apply:required" in error_ids


def test_workflow_plan_sequences_bounded_agent_run(tmp_path: Path) -> None:
    plan = build_workflow_plan(
        root=REPO_ROOT / "examples",
        output_dir=tmp_path / "workflow",
        task="dashboard operator evidence authority",
        targets=["dashboard_readiness_projection", "research_only_boundary", "dashboard_readiness_projection"],
        token_budget=900,
        query_limit=5,
        max_presets=3,
        max_files=200,
    )

    assert plan["schema_version"] == "deep_context_federation_workflow_plan_v1"
    assert plan["authority_effect"] == "none"
    assert plan["no_apply"] is True
    assert plan["status"] == "ready_with_targets"
    assert plan["target_count"] == 2
    assert plan["targets"] == ["dashboard_readiness_projection", "research_only_boundary"]
    step_ids = [row["step_id"] for row in plan["steps"]]
    assert step_ids == [
        "01_agent_intake",
        "02_validate_intake_contract",
        "03_review_targets",
        "04_review_gate",
        "05_inspect_priority_target",
    ]
    assert plan["steps"][0]["token_role"] == "produce_bounded_context_pack"
    assert plan["steps"][3]["stop_on_failure"] is True
    assert any(row["gate_id"] == "target_review_gate" for row in plan["gates"])
    assert "full federation artifact" in plan["token_efficiency"]["skip_by_default"]
    assert plan["safety_boundaries"]["executes_commands"] is False
    assert plan["prompt_text"].startswith("# Deep Context Federation Workflow Plan")
    assert plan["prompt_estimated_tokens"] > 0
    assert validate_artifact_contract(plan)["ok"] is True


def test_workflow_plan_without_targets_warns(tmp_path: Path) -> None:
    plan = build_workflow_plan(
        root=REPO_ROOT / "examples",
        output_dir=tmp_path / "workflow",
        task="dashboard operator evidence authority",
        targets=[],
        token_budget=900,
    )

    assert plan["status"] == "ready_no_targets"
    assert plan["target_count"] == 0
    assert [row["step_id"] for row in plan["steps"]] == [
        "01_agent_intake",
        "02_validate_intake_contract",
        "03_task_brief_only",
    ]
    assert any("No targets supplied" in warning for warning in plan["warnings"])
    assert all(row["authority_effect"] == "none" and row["no_apply"] is True for row in plan["steps"])
    assert validate_artifact_contract(plan)["ok"] is True


def test_workflow_run_executes_compact_readonly_capsule(tmp_path: Path) -> None:
    review_policy = {
        "schema_version": "deep_context_federation_target_review_gate_policy_v1",
        "authority_effect": "none",
        "no_apply": True,
        "max_warn": 1,
        "max_priority_score": 120,
    }
    result = build_workflow_run(
        root=REPO_ROOT / "examples",
        output_dir=tmp_path / "workflow_run",
        manifests=[EXAMPLE_MANIFEST],
        task="dashboard operator evidence authority",
        targets=["dashboard_readiness_projection", "dashboard_readiness_projection"],
        target_review_gate_policy=review_policy,
        token_budget=900,
        query_limit=5,
        max_presets=3,
        max_files=200,
    )

    assert result["schema_version"] == "deep_context_federation_workflow_run_v1"
    assert result["authority_effect"] == "none"
    assert result["no_apply"] is True
    assert result["ok"] is True
    assert result["status"] == "pass_workflow_run"
    assert result["target_count"] == 1
    step_ids = [row["step_id"] for row in result["step_results"]]
    assert step_ids == [
        "00_workflow_plan",
        "01_agent_intake",
        "02_validate_intake_contract",
        "03_review_targets",
        "04_review_gate",
        "05_priority_resolve",
    ]
    by_step = {row["step_id"]: row for row in result["step_results"]}
    assert by_step["04_review_gate"]["ok"] is True
    assert by_step["05_priority_resolve"]["status"] in {"matched", "warn"}
    assert "full federation artifact" in result["model_handoff"]["skip_by_default"]
    assert Path(result["outputs"]["workflow_run_json"]).exists()
    assert Path(result["outputs"]["workflow_plan_json"]).exists()
    assert Path(result["outputs"]["target_review_gate_json"]).exists()
    assert validate_artifact_contract(result)["ok"] is True


def test_workflow_run_without_targets_warns_and_skips_review(tmp_path: Path) -> None:
    result = build_workflow_run(
        root=REPO_ROOT / "examples",
        output_dir=tmp_path / "workflow_run",
        manifests=[EXAMPLE_MANIFEST],
        task="dashboard operator evidence authority",
        targets=[],
        token_budget=900,
        max_files=200,
    )

    assert result["ok"] is True
    assert result["status"] == "warn_workflow_run"
    assert result["target_count"] == 0
    by_step = {row["step_id"]: row for row in result["step_results"]}
    assert by_step["03_review_targets"]["status"] == "skipped"
    assert by_step["03_review_targets"]["ok"] is None
    assert result["outputs"]["target_review_json"] == ""
    assert validate_artifact_contract(result)["ok"] is True


def test_efficiency_report_measures_workflow_run_token_savings(tmp_path: Path) -> None:
    review_policy = {
        "schema_version": "deep_context_federation_target_review_gate_policy_v1",
        "authority_effect": "none",
        "no_apply": True,
        "max_warn": 1,
        "max_priority_score": 120,
    }
    run = build_workflow_run(
        root=REPO_ROOT / "examples",
        output_dir=tmp_path / "workflow_run",
        manifests=[EXAMPLE_MANIFEST],
        task="dashboard operator evidence authority",
        targets=["dashboard_readiness_projection"],
        target_review_gate_policy=review_policy,
        token_budget=900,
        max_files=200,
    )
    report = build_efficiency_report(
        run,
        workflow_run_path=Path(run["outputs"]["workflow_run_json"]),
    )

    assert report["schema_version"] == "deep_context_federation_efficiency_report_v1"
    assert report["authority_effect"] == "none"
    assert report["no_apply"] is True
    assert report["ok"] is True
    assert report["status"] == "pass_efficiency_report"
    budget = report["model_context_budget"]
    assert budget["read_first_estimated_tokens"] > 0
    assert budget["full_federation_estimated_tokens"] > 0
    assert budget["read_first_estimated_tokens"] < budget["full_federation_estimated_tokens"]
    assert budget["read_first_token_savings"] > 0
    assert budget["read_first_savings_percent"] > 0
    roles = {role for row in report["artifacts"] for role in row["roles"]}
    assert {"read_first", "read_next_if_gate_passes", "baseline"} <= roles
    assert validate_artifact_contract(report)["ok"] is True


def test_efficiency_gate_enforces_token_savings_policy(tmp_path: Path) -> None:
    review_policy = {
        "schema_version": "deep_context_federation_target_review_gate_policy_v1",
        "authority_effect": "none",
        "no_apply": True,
        "max_warn": 1,
        "max_priority_score": 120,
    }
    run = build_workflow_run(
        root=REPO_ROOT / "examples",
        output_dir=tmp_path / "workflow_run",
        manifests=[EXAMPLE_MANIFEST],
        task="dashboard operator evidence authority",
        targets=["dashboard_readiness_projection"],
        target_review_gate_policy=review_policy,
        token_budget=900,
        max_files=200,
    )
    report = build_efficiency_report(
        run,
        workflow_run_path=Path(run["outputs"]["workflow_run_json"]),
    )

    passed = evaluate_efficiency_gate(report)
    assert passed["schema_version"] == "deep_context_federation_efficiency_gate_v1"
    assert passed["authority_effect"] == "none"
    assert passed["no_apply"] is True
    assert passed["ok"] is True
    assert passed["status"] == "pass_efficiency_gate"
    assert passed["summary"]["read_first_savings_percent"] >= 50
    assert validate_artifact_contract(passed)["ok"] is True

    strict_policy = normalize_efficiency_gate_policy(
        {
            "schema_version": "deep_context_federation_efficiency_gate_policy_v1",
            "authority_effect": "none",
            "no_apply": True,
            "policy_id": "unit_strict_efficiency_gate",
            "min_read_first_savings_percent": 95,
        }
    )
    failed = evaluate_efficiency_gate(report, policy=strict_policy)
    assert failed["ok"] is False
    assert failed["status"] == "fail_efficiency_gate"
    failed_ids = {row["id"] for row in failed["errors"]}
    assert "read_first_savings_minimum" in failed_ids
    assert validate_artifact_contract(strict_policy)["ok"] is True
    assert validate_artifact_contract(failed)["ok"] is True


def test_agent_ci_runs_integrated_continuation_gate(tmp_path: Path) -> None:
    review_policy = {
        "schema_version": "deep_context_federation_target_review_gate_policy_v1",
        "authority_effect": "none",
        "no_apply": True,
        "max_warn": 1,
        "max_priority_score": 120,
    }
    result = build_agent_ci(
        root=REPO_ROOT / "examples",
        output_dir=tmp_path / "agent_ci",
        manifests=[EXAMPLE_MANIFEST],
        task="dashboard operator evidence authority",
        targets=["dashboard_readiness_projection"],
        target_review_gate_policy=review_policy,
        efficiency_gate_policy=load_efficiency_gate_policy(EXAMPLE_EFFICIENCY_GATE_POLICY),
        token_budget=900,
        query_limit=5,
        max_presets=3,
        max_files=200,
    )

    assert result["schema_version"] == "deep_context_federation_agent_ci_v1"
    assert result["authority_effect"] == "none"
    assert result["no_apply"] is True
    assert result["ok"] is True
    assert result["status"] == "pass_agent_ci"
    assert result["decision"]["action"] == "continue"
    assert result["decision"]["continue_agent"] is True
    assert result["workflow_run_summary"]["status"] == "pass_workflow_run"
    assert result["efficiency_report_summary"]["status"] == "pass_efficiency_report"
    assert result["efficiency_gate_summary"]["status"] == "pass_efficiency_gate"
    assert result["efficiency_report_summary"]["read_first_savings_percent"] >= 50
    assert result["contract_validation_summary"]["ok"] is True
    assert result["contract_validation_summary"]["artifact_count"] == 4
    assert result["contract_validations"]["workflow_run"]["ok"] is True
    assert result["contract_validations"]["efficiency_report"]["ok"] is True
    assert result["contract_validations"]["efficiency_gate"]["ok"] is True
    assert result["contract_validations"]["agent_ci"]["ok"] is True
    assert result["artifact_read_plan"]["ok"] is True
    assert result["artifact_read_plan"]["totals"]["missing_artifact_count"] == 0
    assert result["artifact_read_plan"]["totals"]["read_first_estimated_tokens"] > 0
    assert any(row["schema_version"] == "deep_context_federation_agent_ci_v1" for row in result["artifact_read_plan"]["rows"])
    assert Path(result["outputs"]["agent_ci_json"]).exists()
    assert Path(result["outputs"]["workflow_run_json"]).exists()
    assert Path(result["outputs"]["efficiency_report_json"]).exists()
    assert Path(result["outputs"]["efficiency_gate_json"]).exists()
    assert Path(result["outputs"]["agent_ci_contract_validation_json"]).exists()
    assert result["outputs"]["agent_ci_json"] in result["next_reads"]["read_first"]
    assert result["safety_boundaries"]["source_or_authority_mutation"] is False
    assert validate_artifact_contract(result)["ok"] is True


def test_agent_ci_stops_on_efficiency_gate_failure(tmp_path: Path) -> None:
    review_policy = {
        "schema_version": "deep_context_federation_target_review_gate_policy_v1",
        "authority_effect": "none",
        "no_apply": True,
        "max_warn": 1,
        "max_priority_score": 120,
    }
    strict_efficiency_policy = normalize_efficiency_gate_policy(
        {
            "schema_version": "deep_context_federation_efficiency_gate_policy_v1",
            "authority_effect": "none",
            "no_apply": True,
            "policy_id": "unit_strict_agent_ci",
            "min_read_first_savings_percent": 95,
        }
    )

    result = build_agent_ci(
        root=REPO_ROOT / "examples",
        output_dir=tmp_path / "agent_ci_strict",
        manifests=[EXAMPLE_MANIFEST],
        task="dashboard operator evidence authority",
        targets=["dashboard_readiness_projection"],
        target_review_gate_policy=review_policy,
        efficiency_gate_policy=strict_efficiency_policy,
        token_budget=900,
        query_limit=5,
        max_presets=3,
        max_files=200,
    )

    assert result["ok"] is False
    assert result["status"] == "fail_agent_ci"
    assert result["decision"]["action"] == "stop"
    assert result["decision"]["continue_agent"] is False
    assert result["decision"]["stop_reasons"][0]["id"] == "efficiency_gate_failed"
    assert "read_first_savings_minimum" in result["efficiency_gate_summary"]["failed_check_ids"]
    assert result["next_reads"]["read_next_if_decision_allows"] == []
    assert result["artifact_read_plan"]["ok"] is True
    assert result["contract_validation_summary"]["ok"] is True
    assert validate_artifact_contract(result)["ok"] is True


def test_context_pack_is_token_bounded(tmp_path: Path) -> None:
    payload = build_federation(
        manifest_path=EXAMPLE_MANIFEST,
        root=REPO_ROOT / "examples",
        output_dir=tmp_path,
        write=False,
    )

    pack = pack_context(payload, task="dashboard operator evidence authority", token_budget=700, max_rows=12)

    assert pack["schema_version"] == "deep_context_federation_context_pack_v1"
    assert pack["authority_effect"] == "none"
    assert pack["no_apply"] is True
    assert pack["estimated_tokens"] <= 700
    assert pack["prompt_estimated_tokens"] == pack["estimated_tokens"]
    assert pack["prompt_text"].startswith("# Deep Context Federation Prompt Pack")
    assert pack["original_estimated_tokens"] > pack["estimated_tokens"]
    assert pack["estimated_token_savings"] > 0
    assert 0 < pack["compression_ratio"] < 1
    assert 0 < pack["budget_utilization"] <= 1
    assert pack["summary"]["selected_count"] == len(pack["rows"])
    assert pack["summary"]["dropped_count"] > 0
    assert any(row["matched_terms"] for row in pack["rows"])
    assert pack["coverage"]["selected_source_count"] > 0
    assert pack["coverage"]["matched_term_ratio"] > 0
    assert "authority" in pack["coverage"]["matched_terms"]
    assert validate_artifact_contract(pack)["ok"] is True

    rows_only = pack_context(
        payload,
        task="dashboard operator evidence authority",
        token_budget=700,
        max_rows=12,
        include_prompt=False,
    )
    assert rows_only["prompt_text"] == ""
    assert rows_only["prompt_estimated_tokens"] == 0


def test_task_brief_routes_agent_context(tmp_path: Path) -> None:
    payload = build_federation(
        manifest_path=EXAMPLE_MANIFEST,
        root=REPO_ROOT / "examples",
        output_dir=tmp_path,
        write=False,
    )

    brief = build_task_brief(
        payload,
        task="dashboard operator evidence authority",
        token_budget=900,
        query_limit=5,
        max_presets=3,
    )

    assert brief["schema_version"] == "deep_context_federation_task_brief_v1"
    assert brief["authority_effect"] == "none"
    assert brief["no_apply"] is True
    assert brief["status"] in {"ready", "warn", "blocked"}
    assert brief["context_pack"]["prompt_text"].startswith("# Deep Context Federation Prompt Pack")
    assert brief["context_pack"]["estimated_tokens"] <= 900
    assert brief["context_budget"]["estimated_token_savings"] > 0
    assert brief["coverage"]["selected_source_count"] > 0
    selected_presets = {row["preset"] for row in brief["selected_presets"]}
    assert {"claim-lineage", "operator-projection"} <= selected_presets
    assert len(brief["routed_queries"]) == len(brief["selected_presets"])
    assert any(row["purpose"] == "generate_bounded_model_context" for row in brief["recommended_commands"])
    assert brief["safety_boundaries"]["mutation_allowed"] is False
    assert validate_artifact_contract(brief)["ok"] is True


def test_resolve_target_builds_evidence_card(tmp_path: Path) -> None:
    payload = build_federation(
        manifest_path=EXAMPLE_MANIFEST,
        root=REPO_ROOT / "examples",
        output_dir=tmp_path,
        write=False,
    )

    result = resolve_target(
        payload,
        target="dashboard_readiness_projection",
        limit=10,
        token_budget=900,
    )

    assert result["schema_version"] == "deep_context_federation_resolve_v1"
    assert result["authority_effect"] == "none"
    assert result["no_apply"] is True
    assert result["status"] in {"matched", "warn"}
    assert result["summary"]["matched_entity_count"] > 0
    assert result["summary"]["related_source_count"] > 0
    assert result["summary"]["related_edge_count"] > 0
    assert result["context_pack"]["estimated_tokens"] <= 900
    assert result["prompt_estimated_tokens"] <= 900
    assert result["prompt_rendered_counts"]["matched_entities"] > 0
    assert result["prompt_text"].startswith("# Deep Context Federation Target Resolution")
    assert any(item["row"].get("value") == "dashboard_readiness_projection" for item in result["matched_entities"])
    assert validate_artifact_contract(result)["ok"] is True


def test_adjudicate_target_classifies_support(tmp_path: Path) -> None:
    payload = build_federation(
        manifest_path=EXAMPLE_MANIFEST,
        root=REPO_ROOT / "examples",
        output_dir=tmp_path,
        write=False,
    )

    result = adjudicate_target(
        payload,
        target="dashboard_readiness_projection",
        limit=10,
        token_budget=900,
    )

    assert result["schema_version"] == "deep_context_federation_adjudicate_v1"
    assert result["authority_effect"] == "none"
    assert result["no_apply"] is True
    assert result["verdict"] in {"supported", "warn"}
    assert result["confidence_score"] >= 50
    assert result["support"]["authority_sources"]
    assert result["recommended_use"]["model_context_allowed"] is True
    assert result["recommended_use"]["safe_for_mutation"] is False
    assert result["prompt_text"].startswith("# Deep Context Federation Adjudication")
    assert result["prompt_estimated_tokens"] <= 900
    assert validate_artifact_contract(result)["ok"] is True


def test_review_targets_prioritizes_target_portfolio(tmp_path: Path) -> None:
    payload = build_federation(
        manifest_path=EXAMPLE_MANIFEST,
        root=REPO_ROOT / "examples",
        output_dir=tmp_path,
        write=False,
    )

    result = review_targets(
        payload,
        targets=[
            "dashboard_readiness_projection",
            "research_only_boundary",
            "missing_target_for_review",
        ],
        token_budget=900,
    )

    assert result["schema_version"] == "deep_context_federation_target_review_v1"
    assert result["authority_effect"] == "none"
    assert result["no_apply"] is True
    assert result["target_count"] == 3
    assert result["reviewed_count"] == 3
    assert result["summary"]["verdict_counts"]["no_match"] == 1
    assert result["priority_order"][0]["target"] == "missing_target_for_review"
    assert result["recommended_next_targets"][0] == "missing_target_for_review"
    assert result["prompt_text"].startswith("# Deep Context Federation Target Review")
    assert result["prompt_estimated_tokens"] <= 900
    assert validate_artifact_contract(result)["ok"] is True


def test_target_review_gate_enforces_policy(tmp_path: Path) -> None:
    payload = build_federation(
        manifest_path=EXAMPLE_MANIFEST,
        root=REPO_ROOT / "examples",
        output_dir=tmp_path,
        write=False,
    )
    review = review_targets(
        payload,
        targets=[
            "dashboard_readiness_projection",
            "missing_target_for_review",
        ],
        token_budget=900,
    )

    failed = evaluate_target_review_gate(review)
    assert failed["schema_version"] == "deep_context_federation_target_review_gate_v1"
    assert failed["ok"] is False
    assert failed["status"] == "fail_target_review_gate"
    failed_ids = {row["id"] for row in failed["errors"]}
    assert "no_match_within_limit" in failed_ids
    assert "priority_score_within_limit" in failed_ids
    assert validate_artifact_contract(failed)["ok"] is True

    policy = normalize_target_review_gate_policy(
        {
            "schema_version": "deep_context_federation_target_review_gate_policy_v1",
            "policy_id": "unit_target_review_gate",
            "authority_effect": "none",
            "no_apply": True,
            "max_no_match": 1,
            "max_priority_score": 120,
            "max_warn": 1,
            "require_targets": ["dashboard_readiness_projection", "missing_target_for_review"],
        }
    )
    passed = evaluate_target_review_gate(review, policy=policy)
    assert passed["ok"] is True
    assert passed["status"] == "pass_target_review_gate"
    assert passed["policy"]["policy_id"] == "unit_target_review_gate"
    assert passed["summary"]["failed_check_count"] == 0
    assert validate_artifact_contract(policy)["ok"] is True
    assert validate_artifact_contract(passed)["ok"] is True


def test_agent_intake_runs_full_agent_packet(tmp_path: Path) -> None:
    policy = {
        "schema_version": "deep_context_federation_quality_gate_policy_v1",
        "authority_effect": "none",
        "no_apply": True,
        "min_sources": 1,
        "min_entities": 1,
        "min_edges": 1,
        "max_warnings": 20,
        "require_query_presets": ["claim-lineage", "operator-projection"],
    }
    result = build_agent_intake(
        root=REPO_ROOT / "examples",
        output_dir=tmp_path / "intake",
        manifests=[EXAMPLE_MANIFEST],
        task="dashboard operator evidence authority",
        quality_gate_policy=policy,
        token_budget=900,
        query_limit=5,
        max_presets=3,
        max_files=200,
    )

    assert result["schema_version"] == "deep_context_federation_agent_intake_v1"
    assert result["authority_effect"] == "none"
    assert result["no_apply"] is True
    assert result["ok"] is True
    assert result["status"] in {"pass_agent_intake", "warn_agent_intake"}
    assert result["quality_gate"]["status"] == "pass_quality_gate"
    assert result["task_brief"]["context_pack"]["estimated_tokens"] <= 900
    assert result["task_brief"]["context_budget"]["estimated_token_savings"] > 0
    assert Path(result["outputs"]["agent_intake_json"]).exists()
    assert Path(result["outputs"]["quality_gate_json"]).exists()
    assert Path(result["outputs"]["task_brief_json"]).exists()
    assert validate_artifact_contract(result)["ok"] is True


def test_build_verify_and_query_example(tmp_path: Path) -> None:
    payload = build_federation(
        manifest_path=EXAMPLE_MANIFEST,
        root=REPO_ROOT / "examples",
        output_dir=tmp_path,
        write=True,
    )

    assert payload["schema_version"] == "deep_context_federation_v1"
    assert payload["authority_effect"] == "none"
    assert payload["no_apply"] is True
    assert payload["summary"]["error_count"] == 0
    assert payload["summary"]["entity_count"] > 0
    assert payload["graph_summary"]["edge_type_counts"]["OWNS"] > 0
    assert payload["graph_summary"]["edge_type_counts"]["REFERENCES_SYMBOL"] > 0
    assert (tmp_path / "deep_context_federation_latest.json").exists()
    assert (tmp_path / "DEEP_CONTEXT_FEDERATION_LATEST.md").exists()
    assert (tmp_path / "deep_context_federation_latest.sqlite").exists()
    assert (tmp_path / DEFAULT_CACHE_NAME).exists()

    manifest = json.loads(EXAMPLE_MANIFEST.read_text(encoding="utf-8"))
    result = verify_federation(payload, manifest=manifest, root=REPO_ROOT)
    assert result["ok"] is True

    query = query_federation(payload, preset="claim-lineage", limit=10)
    assert query["schema_version"] == "deep_context_federation_query_v1"
    assert query["row_count"] > 0

    sqlite_query = query_sqlite(tmp_path / "deep_context_federation_latest.sqlite", preset="search", search="dashboard", limit=10)
    assert sqlite_query["schema_version"] == "deep_context_federation_sql_query_v1"
    assert sqlite_query["row_count"] > 0

    source_health = query_sqlite(tmp_path / "deep_context_federation_latest.sqlite", preset="source-health", limit=10)
    assert source_health["row_count"] > 0
    assert "quality_score" in source_health["rows"][0]

    trace = trace_federation(payload, match="dashboard", depth=2, limit=20)
    assert trace["schema_version"] == "deep_context_federation_trace_v1"
    assert trace["seed_count"] > 0
    assert trace["node_count"] > 0

    entity_rank = rank_entities(payload, limit=5)
    assert entity_rank["schema_version"] == "deep_context_federation_entity_rank_v1"
    assert entity_rank["row_count"] == 5
    assert entity_rank["rows"][0]["score"] >= entity_rank["rows"][-1]["score"]

    source_rank = rank_sources(payload, limit=5)
    assert source_rank["schema_version"] == "deep_context_federation_source_rank_v1"
    assert source_rank["row_count"] == 5

    doctor = doctor_federation(payload)
    assert doctor["schema_version"] == "deep_context_federation_doctor_v1"
    assert doctor["ok"] is True
    assert doctor["status"] == "pass"


def test_incremental_cache_marks_unchanged_sources(tmp_path: Path) -> None:
    first = build_federation(
        manifest_path=EXAMPLE_MANIFEST,
        root=REPO_ROOT / "examples",
        output_dir=tmp_path,
        write=True,
    )
    second = build_federation(
        manifest_path=EXAMPLE_MANIFEST,
        root=REPO_ROOT / "examples",
        output_dir=tmp_path,
        write=True,
    )

    assert first["incremental_cache"]["previous_cache_available"] is False
    assert second["incremental_cache"]["previous_cache_available"] is True
    assert second["incremental_cache"]["unchanged_source_count"] > 0


def test_diff_federations_reports_added_conflict(tmp_path: Path) -> None:
    before = build_federation(
        manifest_path=EXAMPLE_MANIFEST,
        root=REPO_ROOT / "examples",
        output_dir=tmp_path,
        write=False,
    )
    after = json.loads(json.dumps(before))
    after["conflicts"].append(
        {
            "conflict_id": "source_stale:example",
            "conflict_type": "source_stale",
            "severity": "warning",
            "source_id": "current_truth_snapshot",
            "detail": {"source_head": "old"},
        }
    )
    after["summary"]["warning_count"] = 1
    after["summary"]["conflict_count"] = 1

    result = diff_federations(before, after)

    assert result["schema_version"] == "deep_context_federation_diff_v1"
    assert result["conflicts"]["added"] == ["source_stale:example"]
    assert "warning_count" in result["summary_delta"]


def test_verifier_rejects_authority_drift(tmp_path: Path) -> None:
    payload = build_federation(
        manifest_path=EXAMPLE_MANIFEST,
        root=REPO_ROOT / "examples",
        output_dir=tmp_path,
        write=False,
    )
    payload["sources"][0]["authority_effect"] = "production_authority"
    payload["conflicts"].append(
        {
            "conflict_id": "authority_advisory_mixed:test",
            "conflict_type": "authority_advisory_mixed",
            "severity": "error",
            "source_id": payload["sources"][0]["source_id"],
            "detail": {"authority_effect": "production_authority"}
        }
    )
    payload["summary"]["error_count"] = 1

    result = verify_federation(payload, manifest={}, root=REPO_ROOT)

    assert result["ok"] is False
    assert any(error["id"] == "no_error_conflicts" for error in result["errors"])


def test_manifest_validation_rejects_duplicates() -> None:
    manifest = {
        "schema_version": "deep_context_federation_manifest_v1",
        "sources": [
            {"source_id": "same", "role": "current_truth", "required": True, "path": "a.json"},
            {"source_id": "same", "role": "evidence", "required": False, "path": "b.json"},
        ],
    }

    result = validate_manifest(manifest)

    assert result["ok"] is False
    assert any(error["id"] == "source_ids_unique" for error in result["errors"])


def test_build_rejects_invalid_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "deep_context_federation_manifest_v1",
                "sources": [
                    {"source_id": "missing_role", "required": True, "path": "a.json"},
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="manifest validation failed"):
        build_federation(
            manifest_path=manifest_path,
            root=tmp_path,
            output_dir=tmp_path / ".dcf",
            write=False,
        )


def test_build_benchmark_reports_timings(tmp_path: Path) -> None:
    result = benchmark_build(
        manifest_path=EXAMPLE_MANIFEST,
        root=REPO_ROOT / "examples",
        output_dir=tmp_path,
        iterations=2,
    )

    assert result["schema_version"] == "deep_context_federation_benchmark_v1"
    assert result["iterations"] == 2
    assert result["seconds_mean"] >= 0
    assert result["last_summary"]["error_count"] == 0


def test_codebase_memory_adapter_safety(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    disabled, disabled_conflicts = codebase_memory_source(tmp_path, include=False, cache_dir=None)
    assert disabled["status"] == "optional_disabled"
    assert disabled_conflicts == []

    monkeypatch.setattr("deep_context_federation.builder.shutil.which", lambda name: None)
    missing, missing_conflicts = codebase_memory_source(tmp_path, include=True, cache_dir=tmp_path.parent / "cbm")
    assert missing["status"] == "optional_unavailable"
    assert missing_conflicts == []

    monkeypatch.setattr("deep_context_federation.builder.shutil.which", lambda name: "/usr/bin/true")
    safe, safe_conflicts = codebase_memory_source(tmp_path, include=True, cache_dir=tmp_path.parent / "cbm")
    assert safe["status"] == "loaded"
    assert safe["summary"]["indexing_invoked"] is False
    assert safe_conflicts == []

    unsafe, unsafe_conflicts = codebase_memory_source(tmp_path, include=True, cache_dir=tmp_path / "local")
    assert unsafe["status"] == "error"
    assert unsafe_conflicts[0]["conflict_type"] == "codebase_memory_policy_violation"


def test_repo_scan_bootstraps_buildable_federation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src/pkg").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "config").mkdir()
    (repo / "output").mkdir()
    (repo / "README.md").write_text("# Example\n", encoding="utf-8")
    (repo / "config/app.json").write_text('{"enabled": true}\n', encoding="utf-8")
    (repo / "output/ignored.json").write_text('{"large": true}\n', encoding="utf-8")
    (repo / "src/pkg/mod.py").write_text(
        "\n".join(
            [
                "from .util import value",
                "",
                "class Thing:",
                "    def run(self):",
                "        return value",
                "",
                "def helper():",
                "    return Thing().run()",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (repo / "src/pkg/util.py").write_text("value = 1\n", encoding="utf-8")
    (repo / "src/app.ts").write_text(
        "\n".join(
            [
                "import { helper } from './pkg/mod';",
                "",
                "export class Panel {}",
                "export const renderPanel = () => helper();",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (repo / "tests/test_mod.py").write_text("from src.pkg.mod import helper\n", encoding="utf-8")

    result = scan_repository(root=repo, output_dir=repo / ".dcf-scan", write=True, max_files=100)

    assert result["schema_version"] == "deep_context_federation_repo_scan_v1"
    assert result["authority_effect"] == "none"
    assert result["no_apply"] is True
    assert result["summary"]["file_count"] == 6
    assert result["summary"]["symbol_count"] >= 4
    assert result["summary"]["dependency_edge_count"] >= 2
    assert result["summary"]["duration_seconds"] >= 0
    assert result["summary"]["files_per_second"] >= 0
    assert "output" in result["summary"]["skipped_dirs"]

    manifest_path = Path(result["outputs"]["manifest"])
    assert manifest_path.exists()
    assert Path(result["outputs"]["inventory"]).exists()
    assert Path(result["outputs"]["symbols"]).exists()
    assert Path(result["outputs"]["legacy_python_symbols"]).exists()
    assert Path(result["outputs"]["surfaces"]).exists()
    assert Path(result["outputs"]["dependencies"]).exists()

    symbol_payload = json.loads(Path(result["outputs"]["symbols"]).read_text(encoding="utf-8"))
    symbols = [row["symbol_fqn"] for row in symbol_payload["symbols"]]
    assert any(symbol.endswith(".Thing") for symbol in symbols)
    assert any(symbol.endswith(".helper") for symbol in symbols)
    assert any(symbol.endswith(".Panel") for symbol in symbols)
    assert any(symbol.endswith(".renderPanel") for symbol in symbols)

    dependency_payload = json.loads(Path(result["outputs"]["dependencies"]).read_text(encoding="utf-8"))
    assert dependency_payload["summary"]["edge_count"] >= 2
    assert any(row["to"] == "src/pkg/mod.py" for row in dependency_payload["edges"])
    assert any(row["from"] == "src/app.ts" and row["to"] == "src/pkg/mod.py" for row in dependency_payload["edges"])
    assert any(row["from"] == "tests/test_mod.py" and row["to"] == "src/pkg/mod.py" for row in dependency_payload["edges"])
    assert any(row["from"] == "src/pkg/mod.py" and row["to"] == "src/pkg/util.py" for row in dependency_payload["edges"])

    payload = build_federation(
        manifest_path=manifest_path,
        root=repo,
        output_dir=repo / ".dcf-scan",
        write=True,
    )

    assert payload["ok"] is True
    assert payload["summary"]["error_count"] == 0
    assert payload["graph_summary"]["edge_type_counts"]["OWNS"] > 0
    assert payload["graph_summary"]["edge_type_counts"]["REFERENCES_SYMBOL"] > 0
    assert any(source["source_id"] == "repo_dependency_graph" for source in payload["sources"])

    query = query_federation(payload, preset="code-to-authority", limit=20)
    values = {row["value"] for row in query["rows"]}
    assert "src/pkg/mod.py" in values


def test_compose_manifests_rebases_and_renames_conflicting_sources(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    scan_dir = repo / ".dcf-scan"
    curated_dir = repo / "curated"
    composed_dir = repo / ".dcf-composed"
    curated_dir.mkdir(parents=True)
    (repo / "src").mkdir(parents=True)
    (repo / "src/main.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    (curated_dir / "evidence.json").write_text(
        json.dumps(
            {
                "schema_version": "curated_evidence_v1",
                "authority_effect": "none",
                "no_apply": True,
                "summary": {"status": "pass"},
                "claims": [
                    {
                        "claim_id": "curated_claim",
                        "label": "Curated evidence survives manifest composition.",
                        "supporting_artifacts": ["evidence.json"],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    curated_manifest = curated_dir / "deep_context_federation.json"
    curated_manifest.write_text(
        json.dumps(
            {
                "schema_version": "deep_context_federation_manifest_v1",
                "authority_boundary": {"authority_effect": "none", "no_apply": True},
                "sources": [
                    {
                        "source_id": "repo_file_inventory",
                        "role": "curated_evidence",
                        "required": True,
                        "path": "evidence.json",
                        "verifier": "unit-test",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    scan = scan_repository(root=repo, output_dir=scan_dir, write=True, max_files=100)
    result = compose_manifests(
        [Path(scan["outputs"]["manifest"]), curated_manifest],
        output_path=composed_dir / "combined.json",
        write=True,
    )

    assert result["schema_version"] == "deep_context_federation_manifest_compose_v1"
    assert result["ok"] is True
    assert result["summary"]["source_count"] == 5
    assert result["summary"]["warning_count"] == 1
    assert result["conflicts"][0]["conflict_type"] == "source_id_renamed"
    assert (composed_dir / "combined.json").exists()

    composed = json.loads((composed_dir / "combined.json").read_text(encoding="utf-8"))
    source_ids = {row["source_id"] for row in composed["sources"]}
    assert "repo_file_inventory" in source_ids
    assert any(source_id.startswith("repo_file_inventory__from_deep_context_federation") for source_id in source_ids)
    assert all(not Path(row["path"]).is_absolute() for row in composed["sources"])

    payload = build_federation(
        manifest_path=composed_dir / "combined.json",
        root=repo,
        output_dir=composed_dir,
        write=True,
    )
    assert payload["ok"] is True
    assert payload["summary"]["source_count"] == 6
    assert payload["summary"]["error_count"] == 0

    query = query_federation(payload, preset="claim-lineage", limit=20)
    assert any(row.get("value") == "curated_claim" for row in query["rows"])


def test_bootstrap_runs_full_pipeline_with_curated_manifest(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    curated = repo / "curated"
    output_dir = repo / ".dcf-bootstrap"
    (repo / "src").mkdir(parents=True)
    curated.mkdir(parents=True)
    (repo / "src/main.py").write_text(
        "\n".join(
            [
                "import json",
                "",
                "def main():",
                "    return json.dumps({'ok': True})",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (curated / "claims.json").write_text(
        json.dumps(
            {
                "schema_version": "curated_claims_v1",
                "authority_effect": "none",
                "no_apply": True,
                "summary": {"status": "pass"},
                "claims": [
                    {
                        "claim_id": "bootstrap_curated_claim",
                        "label": "Bootstrap keeps curated claims in the same federation.",
                        "supporting_artifacts": ["claims.json"],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = curated / "deep_context_federation.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "deep_context_federation_manifest_v1",
                "authority_boundary": {"authority_effect": "none", "no_apply": True},
                "sources": [
                    {
                        "source_id": "curated_claims",
                        "role": "claim_lineage",
                        "required": True,
                        "path": "claims.json",
                        "verifier": "unit-test",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = bootstrap_federation(root=repo, output_dir=output_dir, manifests=[manifest], max_files=100)

    assert result["schema_version"] == "deep_context_federation_bootstrap_v1"
    assert result["ok"] is True
    assert result["status"] == "pass_bootstrap"
    assert result["scan"]["status"] == "pass"
    assert result["compose"]["status"] == "pass_manifest_compose"
    assert result["build"]["status"] == "pass_deep_context_federation"
    assert result["verify"]["status"] == "pass_deep_context_federation"
    assert result["doctor"]["status"] == "pass"
    assert result["build"]["summary"]["error_count"] == 0
    assert result["build"]["summary"]["source_count"] == 6
    assert Path(result["outputs"]["bootstrap_json"]).exists()
    assert Path(result["outputs"]["bootstrap_markdown"]).exists()
    assert Path(result["outputs"]["federation_sqlite"]).exists()

    payload = json.loads(Path(result["outputs"]["federation_json"]).read_text(encoding="utf-8"))
    query = query_federation(payload, preset="claim-lineage", limit=20)
    assert any(row.get("value") == "bootstrap_curated_claim" for row in query["rows"])

    policy_path = output_dir / "quality_gate_policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "schema_version": "deep_context_federation_quality_gate_policy_v1",
                "policy_id": "unit_bootstrap_policy",
                "authority_effect": "none",
                "no_apply": True,
                "min_sources": 6,
                "min_entities": 5,
                "min_edges": 5,
                "require_roles": ["claim_lineage", "project_surface", "evidence_index"],
                "require_sources": ["curated_claims", "repo_file_inventory"],
                "require_query_presets": ["claim-lineage", "code-to-authority"],
                "max_duration_seconds": 10,
                "max_scan_duration_seconds": 10,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    gate = evaluate_quality_gate(result, federation_payload=payload, policy=load_quality_gate_policy(policy_path))
    assert gate["schema_version"] == "deep_context_federation_quality_gate_v1"
    assert gate["ok"] is True
    assert gate["status"] == "pass_quality_gate"
    assert gate["policy"]["schema_version"] == "deep_context_federation_quality_gate_policy_v1"
    assert gate["policy"]["policy_id"] == "unit_bootstrap_policy"
    assert gate["policy"]["min_sources"] == 6
    assert gate["policy"]["require_roles"] == ["claim_lineage", "project_surface", "evidence_index"]
    assert gate["policy"]["unknown_keys"] == []
    assert gate["policy"]["validation_errors"] == []
    assert gate["summary"]["failed_check_count"] == 0
    assert gate["summary"]["check_count"] == len(gate["checks"])

    failing_gate = evaluate_quality_gate(
        result,
        federation_payload=payload,
        require_roles=["missing_role"],
        require_sources=["missing_source"],
    )
    assert failing_gate["ok"] is False
    assert failing_gate["status"] == "fail_quality_gate"
    error_ids = {row["id"] for row in failing_gate["errors"]}
    assert "required_role_present:missing_role" in error_ids
    assert "required_source_present:missing_source" in error_ids

    malformed_policy = normalize_quality_gate_policy(
        {
            "schema_version": "deep_context_federation_quality_gate_policy_v1",
            "authority_effect": "apply",
            "no_apply": False,
            "unknown_gate": True,
            "min_sources": -1,
        }
    )
    malformed_gate = evaluate_quality_gate(result, federation_payload=payload, policy=malformed_policy)
    malformed_error_ids = {row["id"] for row in malformed_gate["errors"]}
    assert "policy_authority_effect_none" in malformed_error_ids
    assert "policy_no_apply_true" in malformed_error_ids
    assert "policy_unknown_keys_absent" in malformed_error_ids
    assert "policy_validation_errors_absent" in malformed_error_ids
