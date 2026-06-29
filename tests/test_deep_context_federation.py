from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from deep_context_federation.adjudicate import adjudicate_target
from deep_context_federation.agent_context import build_agent_context
from deep_context_federation.agent_context_gate import evaluate_agent_context_gate
from deep_context_federation.agent_context_gate import load_agent_context_gate_policy
from deep_context_federation.agent_context_gate import normalize_agent_context_gate_policy
from deep_context_federation.agent_ci import build_agent_ci
from deep_context_federation.agent_discover import discover_agent_context
from deep_context_federation.agent_handoff import build_agent_handoff
from deep_context_federation.agent_handoff_verify import verify_agent_handoff
from deep_context_federation.agent_model_input import build_agent_model_input
from deep_context_federation.agent_onboard import build_agent_onboard
from deep_context_federation.agent_profile import load_agent_profile
from deep_context_federation.agent_profile_init import build_agent_profile_init
from deep_context_federation.agent_ready import build_agent_ready
from deep_context_federation.agent_route import route_agent_context
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
from deep_context_federation.native_integration import build_native_integration_plan
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
EXAMPLE_AGENT_CONTEXT_GATE_POLICY = REPO_ROOT / "examples/agent_context_gate_policy.example.json"
EXAMPLE_AGENT_READY_PROFILE = REPO_ROOT / "examples/agent_ready_profile.example.json"


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


def test_agent_context_gate_policy_example_loads() -> None:
    policy = load_agent_context_gate_policy(EXAMPLE_AGENT_CONTEXT_GATE_POLICY)

    assert policy["schema_version"] == "deep_context_federation_agent_context_gate_policy_v1"
    assert policy["policy_id"] == "example_agent_context_minimum"
    assert policy["authority_effect"] == "none"
    assert policy["no_apply"] is True
    assert policy["schema_supported"] is True
    assert policy["unknown_keys"] == []
    assert policy["validation_errors"] == []
    assert policy["max_missing_artifacts"] == 0
    assert policy["enforce_prompt_within_token_budget"] is True
    assert "deep_context_federation_agent_ci_v1" in policy["require_schema_versions"]
    assert validate_artifact_contract(policy)["ok"] is True


def test_agent_profile_example_loads_and_validates() -> None:
    raw_profile = json.loads(EXAMPLE_AGENT_READY_PROFILE.read_text(encoding="utf-8"))
    assert validate_artifact_contract(raw_profile, artifact_kind="agent_profile")["ok"] is True
    profile = load_agent_profile(EXAMPLE_AGENT_READY_PROFILE)

    assert profile["schema_version"] == "deep_context_federation_agent_profile_validation_v1"
    assert profile["ok"] is True
    assert profile["status"] == "pass_agent_profile"
    assert profile["authority_effect"] == "none"
    assert profile["no_apply"] is True
    assert profile["profile_id"] == "example_agent_ready_profile"
    assert profile["normalized"]["root"] == (REPO_ROOT / "examples").resolve().as_posix()
    assert profile["normalized"]["manifests"] == [(REPO_ROOT / "examples/deep_context_federation.example.json").resolve().as_posix()]
    assert profile["normalized"]["targets"] == ["dashboard_readiness_projection"]
    assert profile["summary"]["field_count"] > 0
    assert validate_artifact_contract(profile, artifact_kind="agent_profile_validation")["ok"] is True


def test_agent_profile_rejects_wrong_field_types(tmp_path: Path) -> None:
    profile_path = tmp_path / "bad_profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "schema_version": "deep_context_federation_agent_profile_v1",
                "authority_effect": "none",
                "no_apply": True,
                "root": ".",
                "targets": "dashboard_readiness_projection",
                "workflow_token_budget": "900",
                "include_prompt": "false",
            }
        ),
        encoding="utf-8",
    )

    profile = load_agent_profile(profile_path)

    assert profile["ok"] is False
    error_ids = {row["id"] for row in profile["errors"]}
    assert {"targets_list", "workflow_token_budget_integer", "include_prompt_boolean"} <= error_ids
    assert validate_artifact_contract(profile, artifact_kind="agent_profile_validation")["ok"] is True


def test_agent_profile_init_writes_valid_profile(tmp_path: Path) -> None:
    profile_root = tmp_path / "profile_init"
    profile_root.mkdir()
    shutil.copytree(REPO_ROOT / "examples/fixtures", profile_root / "fixtures")
    manifest_path = profile_root / "deep_context_federation.json"
    manifest_path.write_text(EXAMPLE_MANIFEST.read_text(encoding="utf-8"), encoding="utf-8")
    efficiency_policy = profile_root / "efficiency_policy.json"
    efficiency_policy.write_text(EXAMPLE_EFFICIENCY_GATE_POLICY.read_text(encoding="utf-8"), encoding="utf-8")
    context_policy = profile_root / "agent_context_policy.json"
    context_policy.write_text(EXAMPLE_AGENT_CONTEXT_GATE_POLICY.read_text(encoding="utf-8"), encoding="utf-8")
    profile_path = profile_root / ".dcf" / "agent_ready_profile.json"

    result = build_agent_profile_init(
        root=profile_root,
        profile_path=profile_path,
        task="dashboard operator evidence authority",
        targets=["dashboard_readiness_projection"],
        manifests=[manifest_path],
        efficiency_policy_path=efficiency_policy,
        context_gate_policy_path=context_policy,
        workflow_token_budget=900,
        context_token_budget=1800,
        max_artifact_tokens=500,
        write=True,
    )

    assert result["schema_version"] == "deep_context_federation_agent_profile_init_v1"
    assert result["ok"] is True
    assert result["status"] == "pass_agent_profile_init"
    assert result["authority_effect"] == "none"
    assert result["no_apply"] is True
    assert result["profile"]["root"] == ".."
    assert result["profile"]["output_dir"] == "."
    assert result["profile"]["manifests"] == ["../deep_context_federation.json"]
    assert result["profile"]["include_memory_import"] is False
    assert "include_codebase_memory" not in result["profile"]
    assert result["profile_validation_summary"]["status"] == "pass_agent_profile"
    assert Path(result["outputs"]["agent_profile_json"]).exists()
    assert validate_artifact_contract(result, artifact_kind="agent_profile_init")["ok"] is True
    assert validate_artifact_contract(json.loads(profile_path.read_text(encoding="utf-8")), artifact_kind="agent_profile")["ok"] is True
    profile = load_agent_profile(profile_path)
    assert profile["ok"] is True
    assert profile["normalized"]["root"] == profile_root.resolve().as_posix()
    assert profile["normalized"]["include_memory_import"] is False
    assert "include_codebase_memory" not in profile["normalized"]
    assert validate_artifact_contract(profile, artifact_kind="agent_profile_validation")["ok"] is True


def test_agent_profile_init_does_not_write_when_inputs_fail(tmp_path: Path) -> None:
    profile_root = tmp_path / "profile_init_fail"
    profile_root.mkdir()
    profile_path = profile_root / ".dcf" / "agent_ready_profile.json"

    result = build_agent_profile_init(
        root=profile_root,
        profile_path=profile_path,
        task="dashboard operator evidence authority",
        manifests=[profile_root / "missing_manifest.json"],
        write=True,
    )

    assert result["ok"] is False
    assert result["status"] == "fail_agent_profile_init"
    assert {row["id"] for row in result["errors"]} == {"manifest_exists"}
    assert result["outputs"] == {}
    assert result["safety_boundaries"]["writes_profile_only"] is False
    assert not profile_path.exists()
    assert validate_artifact_contract(result, artifact_kind="agent_profile_init")["ok"] is True


def test_capabilities_manifest_is_machine_readable() -> None:
    payload = build_capabilities()

    assert payload["schema_version"] == "deep_context_federation_capabilities_v1"
    assert payload["status"] == "ok"
    assert payload["authority_effect"] == "none"
    assert payload["no_apply"] is True
    assert payload["package"]["cli"] == "dcf"
    assert payload["package"]["version"] == "0.43.0"

    command_names = {row["command"] for row in payload["commands"]}
    assert {
        "capabilities",
        "bootstrap",
        "workflow-plan",
        "workflow-run",
        "efficiency-report",
        "efficiency-gate",
        "agent-ci",
        "agent-context",
        "agent-context-gate",
        "agent-discover",
        "agent-handoff",
        "agent-model-input",
        "agent-onboard",
        "agent-profile",
        "agent-profile-init",
        "agent-ready",
        "agent-route",
        "verify-handoff",
        "intake",
        "build",
        "scan",
        "schema",
        "validate-artifact",
        "native-integration-plan",
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
    assert by_kind["agent_context"]["schema_version"] == "deep_context_federation_agent_context_v1"
    assert by_kind["agent_context_gate"]["schema_version"] == "deep_context_federation_agent_context_gate_v1"
    assert by_kind["agent_context_gate_policy"]["schema_version"] == "deep_context_federation_agent_context_gate_policy_v1"
    assert by_kind["agent_handoff"]["schema_version"] == "deep_context_federation_agent_handoff_v1"
    assert by_kind["agent_handoff_verification"]["schema_version"] == "deep_context_federation_agent_handoff_verification_v1"
    assert by_kind["agent_model_input"]["schema_version"] == "deep_context_federation_agent_model_input_v1"
    assert by_kind["agent_onboard"]["schema_version"] == "deep_context_federation_agent_onboard_v1"
    assert by_kind["native_integration_plan"]["schema_version"] == "deep_context_federation_native_integration_plan_v1"
    assert by_kind["agent_profile"]["schema_version"] == "deep_context_federation_agent_profile_v1"
    assert by_kind["agent_profile_validation"]["schema_version"] == "deep_context_federation_agent_profile_validation_v1"
    assert by_kind["agent_profile_init"]["schema_version"] == "deep_context_federation_agent_profile_init_v1"
    assert by_kind["agent_discovery"]["schema_version"] == "deep_context_federation_agent_discovery_v1"
    assert by_kind["agent_ready"]["schema_version"] == "deep_context_federation_agent_ready_v1"
    assert by_kind["agent_route"]["schema_version"] == "deep_context_federation_agent_route_v1"
    assert by_kind["input_fingerprint"]["schema_version"] == "deep_context_federation_input_fingerprint_v1"
    assert by_kind["input_fingerprint_compare"]["schema_version"] == "deep_context_federation_input_fingerprint_compare_v1"
    assert by_kind["request_binding"]["schema_version"] == "deep_context_federation_request_binding_v1"
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
    assert by_kind["agent_context"]["schema_version"] == "deep_context_federation_agent_context_v1"
    assert by_kind["agent_context_gate"]["schema_version"] == "deep_context_federation_agent_context_gate_v1"
    assert by_kind["agent_context_gate_policy"]["schema_version"] == "deep_context_federation_agent_context_gate_policy_v1"
    assert by_kind["agent_handoff"]["schema_version"] == "deep_context_federation_agent_handoff_v1"
    assert by_kind["agent_handoff_verification"]["schema_version"] == "deep_context_federation_agent_handoff_verification_v1"
    assert by_kind["agent_model_input"]["schema_version"] == "deep_context_federation_agent_model_input_v1"
    assert by_kind["agent_onboard"]["schema_version"] == "deep_context_federation_agent_onboard_v1"
    assert by_kind["native_integration_plan"]["schema_version"] == "deep_context_federation_native_integration_plan_v1"
    assert by_kind["agent_profile"]["schema_version"] == "deep_context_federation_agent_profile_v1"
    assert by_kind["agent_profile_validation"]["schema_version"] == "deep_context_federation_agent_profile_validation_v1"
    assert by_kind["agent_profile_init"]["schema_version"] == "deep_context_federation_agent_profile_init_v1"
    assert by_kind["agent_discovery"]["schema_version"] == "deep_context_federation_agent_discovery_v1"
    assert by_kind["agent_ready"]["schema_version"] == "deep_context_federation_agent_ready_v1"
    assert by_kind["agent_route"]["schema_version"] == "deep_context_federation_agent_route_v1"
    assert by_kind["input_fingerprint"]["schema_version"] == "deep_context_federation_input_fingerprint_v1"
    assert by_kind["input_fingerprint_compare"]["schema_version"] == "deep_context_federation_input_fingerprint_compare_v1"
    assert by_kind["request_binding"]["schema_version"] == "deep_context_federation_request_binding_v1"
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


def test_native_integration_plan_collapses_upstream_identity() -> None:
    plan = build_native_integration_plan(capabilities=["symbol-call-graph", "surface-map", "long-term-context-memory"])

    assert plan["schema_version"] == "deep_context_federation_native_integration_plan_v1"
    assert plan["ok"] is True
    assert plan["authority_effect"] == "none"
    assert plan["no_apply"] is True
    assert plan["integration_policy"]["public_identity"] == "deep_context_federation"
    assert plan["integration_policy"]["hide_upstream_tool_identity"] is True
    assert plan["integration_policy"]["adapter_only_allowed"] is False
    assert plan["integration_policy"]["consume_only_allowed"] is False
    assert plan["safety_boundaries"]["user_facing_source_identity_collapsed_to_dcf"] is True
    capability_ids = {row["capability_id"] for row in plan["capabilities"]}
    assert capability_ids == {"symbol_call_graph", "surface_map", "long_term_context_memory"}
    assert all(row["input_identity_collapsed"] is True for row in plan["capabilities"])
    assert all("external_overlap" not in row for row in plan["capabilities"])
    assert all("requested_as" not in row for row in plan["capabilities"])
    assert validate_artifact_contract(plan, artifact_kind="native_integration_plan")["ok"] is True


def test_native_integration_plan_cli_validates(tmp_path: Path) -> None:
    output_path = tmp_path / "native_integration_plan.json"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "deep_context_federation.cli",
            "native-integration-plan",
            "--function",
            "symbol-call-graph",
            "--function",
            "operator-projection",
            "--output",
            str(output_path),
            "--format",
            "json",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["status"] == "warn_native_integration_plan"
    assert payload["outputs"]["native_integration_plan_json"] == output_path.resolve().as_posix()
    assert output_path.exists()
    assert {row["capability_id"] for row in payload["capabilities"]} == {"symbol_call_graph", "operator_projection"}
    assert all("external_overlap" not in row for row in payload["capabilities"])
    assert validate_artifact_contract(payload, artifact_kind="native_integration_plan")["ok"] is True


def test_native_integration_plan_does_not_accept_source_names_as_functions() -> None:
    plan = build_native_integration_plan(capabilities=["codegraph"])

    assert plan["status"] == "warn_native_integration_plan"
    assert plan["summary"]["manual_review_count"] == 1
    assert plan["capabilities"][0]["capability_id"] == "codegraph"
    assert plan["capabilities"][0]["known"] is False
    assert plan["capabilities"][0]["integration_mode"] == "manual_native_design_required"


def test_memory_import_cli_uses_function_names_in_help() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "deep_context_federation.cli",
            "build",
            "--help",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0
    assert "--include-memory-import" in completed.stdout
    assert "--memory-import-cache-dir" in completed.stdout
    assert "--include-codebase-memory" not in completed.stdout
    assert "--codebase-memory-cache-dir" not in completed.stdout

    native = subprocess.run(
        [
            sys.executable,
            "-m",
            "deep_context_federation.cli",
            "native-integration-plan",
            "--help",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )
    assert native.returncode == 0
    assert "--function" in native.stdout
    assert "--capability" not in native.stdout


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


def test_agent_context_materializes_bounded_read_plan(tmp_path: Path) -> None:
    review_policy = {
        "schema_version": "deep_context_federation_target_review_gate_policy_v1",
        "authority_effect": "none",
        "no_apply": True,
        "max_warn": 1,
        "max_priority_score": 120,
    }
    agent_ci = build_agent_ci(
        root=REPO_ROOT / "examples",
        output_dir=tmp_path / "agent_context",
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

    result = build_agent_context(
        agent_ci,
        agent_ci_path=Path(agent_ci["outputs"]["agent_ci_json"]),
        mode="read-first",
        token_budget=1800,
        max_artifact_tokens=500,
    )

    assert result["schema_version"] == "deep_context_federation_agent_context_v1"
    assert result["authority_effect"] == "none"
    assert result["no_apply"] is True
    assert result["ok"] is True
    assert result["status"] in {"pass_agent_context", "warn_agent_context"}
    assert result["mode"] == "read-first"
    assert result["source_contract_validation"]["ok"] is True
    assert result["summary"]["candidate_artifact_count"] >= result["summary"]["selected_artifact_count"] > 0
    assert result["summary"]["selected_estimated_tokens"] <= int(result["token_budget"] * 0.65)
    assert all(section["role"] == "read_first" for section in result["sections"])
    assert all(section["content"] for section in result["sections"])
    assert any(section["schema_version"] == "deep_context_federation_agent_ci_v1" for section in result["sections"])
    assert result["prompt_text"].startswith("# Deep Context Federation Agent Context")
    assert result["safety_boundaries"]["source_or_authority_mutation"] is False
    assert validate_artifact_contract(result)["ok"] is True

    metadata_only = build_agent_context(
        agent_ci,
        agent_ci_path=Path(agent_ci["outputs"]["agent_ci_json"]),
        mode="decision-allowed",
        token_budget=500,
        max_artifact_tokens=100,
        include_content=False,
        include_prompt=False,
    )
    assert metadata_only["ok"] is True
    assert metadata_only["include_content"] is False
    assert metadata_only["prompt_text"] == ""
    assert metadata_only["summary"]["selected_estimated_tokens"] == 0
    assert all(section["content"] == "" for section in metadata_only["sections"])
    assert validate_artifact_contract(metadata_only)["ok"] is True


def test_agent_context_gate_enforces_model_handoff_policy(tmp_path: Path) -> None:
    review_policy = {
        "schema_version": "deep_context_federation_target_review_gate_policy_v1",
        "authority_effect": "none",
        "no_apply": True,
        "max_warn": 1,
        "max_priority_score": 120,
    }
    agent_ci = build_agent_ci(
        root=REPO_ROOT / "examples",
        output_dir=tmp_path / "agent_context_gate",
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
    context = build_agent_context(
        agent_ci,
        agent_ci_path=Path(agent_ci["outputs"]["agent_ci_json"]),
        mode="read-first",
        token_budget=1800,
        max_artifact_tokens=500,
    )

    passed = evaluate_agent_context_gate(
        context,
        policy=load_agent_context_gate_policy(EXAMPLE_AGENT_CONTEXT_GATE_POLICY),
    )
    assert passed["schema_version"] == "deep_context_federation_agent_context_gate_v1"
    assert passed["authority_effect"] == "none"
    assert passed["no_apply"] is True
    assert passed["ok"] is True
    assert passed["status"] == "pass_agent_context_gate"
    assert passed["summary"]["prompt_estimated_tokens"] <= passed["summary"]["token_budget"]
    assert validate_artifact_contract(passed)["ok"] is True

    strict_policy = normalize_agent_context_gate_policy(
        {
            "schema_version": "deep_context_federation_agent_context_gate_policy_v1",
            "authority_effect": "none",
            "no_apply": True,
            "policy_id": "unit_strict_agent_context_gate",
            "max_prompt_tokens": 10,
        }
    )
    failed = evaluate_agent_context_gate(context, policy=strict_policy)
    assert failed["ok"] is False
    assert failed["status"] == "fail_agent_context_gate"
    failed_ids = {row["id"] for row in failed["errors"]}
    assert "prompt_tokens_within_limit" in failed_ids
    assert validate_artifact_contract(strict_policy)["ok"] is True
    assert validate_artifact_contract(failed)["ok"] is True


def test_agent_handoff_runs_gated_model_handoff(tmp_path: Path) -> None:
    review_policy = {
        "schema_version": "deep_context_federation_target_review_gate_policy_v1",
        "authority_effect": "none",
        "no_apply": True,
        "max_warn": 1,
        "max_priority_score": 120,
    }
    result = build_agent_handoff(
        root=REPO_ROOT / "examples",
        output_dir=tmp_path / "agent_handoff",
        manifests=[EXAMPLE_MANIFEST],
        task="dashboard operator evidence authority",
        targets=["dashboard_readiness_projection"],
        target_review_gate_policy=review_policy,
        efficiency_gate_policy=load_efficiency_gate_policy(EXAMPLE_EFFICIENCY_GATE_POLICY),
        agent_context_gate_policy=load_agent_context_gate_policy(EXAMPLE_AGENT_CONTEXT_GATE_POLICY),
        workflow_token_budget=900,
        context_token_budget=1800,
        max_artifact_tokens=500,
        query_limit=5,
        max_presets=3,
        max_files=200,
    )

    assert result["schema_version"] == "deep_context_federation_agent_handoff_v1"
    assert result["authority_effect"] == "none"
    assert result["no_apply"] is True
    assert result["ok"] is True
    assert result["status"] in {"pass_agent_handoff", "warn_agent_handoff"}
    assert result["decision"]["handoff_allowed"] is True
    assert result["agent_ci_summary"]["status"] == "pass_agent_ci"
    assert result["agent_context_gate_summary"]["status"] == "pass_agent_context_gate"
    prompt_path = Path(result["outputs"]["agent_model_prompt_markdown"])
    context_path = Path(result["outputs"]["agent_context_json"])
    assert result["model_handoff"]["model_prompt_source"] == result["outputs"]["agent_model_prompt_markdown"]
    assert result["model_handoff"]["model_prompt_format"] == "markdown"
    assert result["model_handoff"]["machine_context_source"] == result["outputs"]["agent_context_json"]
    assert result["model_handoff"]["read_first"][-1] == result["outputs"]["agent_model_prompt_markdown"]
    assert result["model_handoff"]["model_prompt_estimated_tokens"] > 0
    assert result["model_handoff"]["machine_context_estimated_tokens"] > result["model_handoff"]["model_prompt_estimated_tokens"]
    assert result["input_fingerprint_summary"]["status"] == "pass_input_fingerprint"
    assert len(result["input_fingerprint_summary"]["digest"]) == 64
    assert result["input_fingerprint"]["source_count"] > 0
    assert validate_artifact_contract(result["input_fingerprint"], artifact_kind="input_fingerprint")["ok"] is True
    assert result["agent_handoff_verification_summary"]["status"] == "pass_agent_handoff_verification"
    assert result["agent_handoff_verification_summary"]["ok"] is True
    assert Path(result["outputs"]["agent_handoff_json"]).exists()
    assert Path(result["outputs"]["agent_ci_json"]).exists()
    assert Path(result["outputs"]["agent_handoff_verification_json"]).exists()
    assert Path(result["outputs"]["agent_handoff_verification_markdown"]).exists()
    discovery = discover_agent_context(root=tmp_path, handoff_path=Path(result["outputs"]["agent_handoff_json"]))
    assert discovery["schema_version"] == "deep_context_federation_agent_discovery_v1"
    assert discovery["ok"] is True
    assert discovery["status"] == "ready_model_input"
    assert discovery["ready_for_model_input"] is True
    assert discovery["selected_handoff"] == Path(result["outputs"]["agent_handoff_json"]).as_posix()
    assert "agent-model-input" in discovery["recommended_next_command"]
    assert discovery["model_input_summary"]["status"] == "pass_agent_model_input"
    assert validate_artifact_contract(discovery)["ok"] is True
    route = route_agent_context(root=tmp_path, handoff_path=Path(result["outputs"]["agent_handoff_json"]))
    assert route["schema_version"] == "deep_context_federation_agent_route_v1"
    assert route["status"] == "ready_agent_route"
    assert route["action"] == "emit_model_input"
    assert route["model_input_ready"] is True
    assert route["route_steps"][0]["terminal_model_input"] is True
    assert "agent-model-input" in route["recommended_next_command"]
    assert validate_artifact_contract(route)["ok"] is True
    ready = build_agent_ready(root=tmp_path, output_dir=tmp_path / "agent_ready", handoff_path=Path(result["outputs"]["agent_handoff_json"]))
    assert ready["schema_version"] == "deep_context_federation_agent_ready_v1"
    assert ready["ok"] is True
    assert ready["status"] == "pass_agent_ready"
    assert ready["action_taken"] == "read_existing_handoff"
    assert ready["input_freshness"]["status"] == "not_checked_no_current_manifest"
    assert ready["request_binding"]["status"] == "not_checked_no_request_binding"
    assert ready["prompt_text"].startswith("# Deep Context Federation Agent Context")
    assert ready["model_input_summary"]["status"] == "pass_agent_model_input"
    assert validate_artifact_contract(ready)["ok"] is True
    assert context_path.exists()
    assert prompt_path.exists()
    assert prompt_path.read_text(encoding="utf-8").startswith("# Deep Context Federation Agent Context")
    assert prompt_path.stat().st_size < context_path.stat().st_size
    prompt_artifact = next(row for row in result["model_handoff"]["read_first_artifacts"] if row["role"] == "model_prompt")
    gate_artifact = next(row for row in result["model_handoff"]["read_first_artifacts"] if row["role"] == "context_gate")
    context_artifact = next(row for row in result["model_handoff"]["audit_artifacts"] if row["role"] == "machine_context")
    assert prompt_artifact["path"] == prompt_path.as_posix()
    assert prompt_artifact["exists"] is True
    assert prompt_artifact["default_model_input"] is True
    assert len(prompt_artifact["sha256"]) == 64
    assert gate_artifact["exists"] is True
    assert context_artifact["path"] == context_path.as_posix()
    assert context_artifact["estimated_tokens"] == result["model_handoff"]["machine_context_estimated_tokens"]
    economics = result["model_handoff"]["token_economics"]
    assert economics["status"] == "measured"
    assert economics["default_model_input"] == "model_prompt_source"
    assert economics["model_prompt_estimated_tokens"] == result["model_handoff"]["model_prompt_estimated_tokens"]
    assert economics["machine_context_estimated_tokens"] == result["model_handoff"]["machine_context_estimated_tokens"]
    assert 0 < economics["model_prompt_to_machine_context_ratio"] < 1
    assert economics["estimated_token_savings"] > 0
    assert economics["estimated_token_savings_percent"] > 50
    assert Path(result["outputs"]["agent_context_gate_json"]).exists()
    assert validate_artifact_contract(result)["ok"] is True
    verified = verify_agent_handoff(result, handoff_path=Path(result["outputs"]["agent_handoff_json"]))
    assert verified["schema_version"] == "deep_context_federation_agent_handoff_verification_v1"
    assert verified["ok"] is True
    assert verified["status"] == "pass_agent_handoff_verification"
    assert verified["summary"]["token_economics_status"] == "measured"
    assert validate_artifact_contract(verified)["ok"] is True
    verification_payload = json.loads(Path(result["outputs"]["agent_handoff_verification_json"]).read_text(encoding="utf-8"))
    assert verification_payload["status"] == "pass_agent_handoff_verification"
    assert validate_artifact_contract(verification_payload, artifact_kind="agent_handoff_verification")["ok"] is True
    model_input = build_agent_model_input(result, handoff_path=Path(result["outputs"]["agent_handoff_json"]))
    assert model_input["schema_version"] == "deep_context_federation_agent_model_input_v1"
    assert model_input["ok"] is True
    assert model_input["status"] == "pass_agent_model_input"
    assert model_input["prompt_text"].startswith("# Deep Context Federation Agent Context")
    assert model_input["prompt_source"] == prompt_path.as_posix()
    assert model_input["prompt_sha256"] == prompt_artifact["sha256"]
    assert model_input["verification_summary"]["status"] == "pass_agent_handoff_verification"
    assert model_input["safety_boundaries"]["prompt_emitted_only_after_verification"] is True
    assert validate_artifact_contract(model_input)["ok"] is True

    prompt_path.write_text(prompt_path.read_text(encoding="utf-8") + "\nmutated\n", encoding="utf-8")
    tampered = verify_agent_handoff(result, handoff_path=Path(result["outputs"]["agent_handoff_json"]))
    assert tampered["ok"] is False
    assert tampered["status"] == "fail_agent_handoff_verification"
    tamper_error_ids = {row["id"] for row in tampered["errors"]}
    assert "artifact_sha256_match:model_prompt" in tamper_error_ids
    tampered_model_input = build_agent_model_input(result, handoff_path=Path(result["outputs"]["agent_handoff_json"]))
    assert tampered_model_input["ok"] is False
    assert tampered_model_input["status"] == "fail_agent_model_input"
    assert tampered_model_input["prompt_text"] == ""
    assert {row["id"] for row in tampered_model_input["errors"]} >= {"handoff_verification_ok"}

    strict_context_gate_policy = normalize_agent_context_gate_policy(
        {
            "schema_version": "deep_context_federation_agent_context_gate_policy_v1",
            "authority_effect": "none",
            "no_apply": True,
            "policy_id": "unit_strict_handoff_context_gate",
            "max_prompt_tokens": 10,
        }
    )
    failed = build_agent_handoff(
        root=REPO_ROOT / "examples",
        output_dir=tmp_path / "agent_handoff_strict",
        manifests=[EXAMPLE_MANIFEST],
        task="dashboard operator evidence authority",
        targets=["dashboard_readiness_projection"],
        target_review_gate_policy=review_policy,
        efficiency_gate_policy=load_efficiency_gate_policy(EXAMPLE_EFFICIENCY_GATE_POLICY),
        agent_context_gate_policy=strict_context_gate_policy,
        workflow_token_budget=900,
        context_token_budget=1800,
        max_artifact_tokens=500,
        query_limit=5,
        max_presets=3,
        max_files=200,
    )
    assert failed["ok"] is False
    assert failed["status"] == "fail_agent_handoff"
    assert failed["decision"]["action"] == "stop"
    assert failed["decision"]["stop_reasons"][0]["id"] == "agent_context_gate_failed"
    assert failed["model_handoff"]["model_prompt_source"] == ""
    assert failed["model_handoff"]["machine_context_source"] == failed["outputs"]["agent_context_json"]
    assert failed["model_handoff"]["token_economics"]["status"] == "not_applicable"
    assert failed["model_handoff"]["token_economics"]["default_model_input"] == ""
    assert failed["model_handoff"]["token_economics"]["model_prompt_estimated_tokens"] == 0
    assert failed["model_handoff"]["token_economics"]["estimated_token_savings"] == 0
    assert failed["agent_handoff_verification_summary"]["status"] == "pass_agent_handoff_verification"
    assert validate_artifact_contract(failed)["ok"] is True
    blocked_verified = verify_agent_handoff(failed, handoff_path=Path(failed["outputs"]["agent_handoff_json"]))
    assert blocked_verified["ok"] is True
    assert blocked_verified["summary"]["token_economics_status"] == "not_applicable"
    assert validate_artifact_contract(blocked_verified)["ok"] is True
    blocked_model_input = build_agent_model_input(failed, handoff_path=Path(failed["outputs"]["agent_handoff_json"]))
    assert blocked_model_input["ok"] is False
    assert blocked_model_input["status"] == "fail_agent_model_input"
    assert blocked_model_input["prompt_text"] == ""
    assert {row["id"] for row in blocked_model_input["errors"]} >= {"handoff_ok", "model_prompt_source_present"}
    assert validate_artifact_contract(blocked_model_input)["ok"] is True


def test_agent_discovery_reports_repo_readiness_states(tmp_path: Path) -> None:
    empty = discover_agent_context(root=tmp_path)
    assert empty["status"] == "not_configured"
    assert empty["ready_for_model_input"] is False
    assert "dcf scan" in empty["recommended_next_command"]
    assert validate_artifact_contract(empty)["ok"] is True

    missing_handoff = discover_agent_context(root=tmp_path, handoff_path=tmp_path / "missing_handoff.json")
    assert missing_handoff["status"] == "blocked_handoff_unreadable"
    assert missing_handoff["ready_for_model_input"] is False
    assert "verify-handoff" in missing_handoff["recommended_next_command"]
    assert validate_artifact_contract(missing_handoff)["ok"] is True

    manifest_root = tmp_path / "manifest_only"
    manifest_root.mkdir()
    manifest_path = manifest_root / "deep_context_federation.json"
    manifest_path.write_text(EXAMPLE_MANIFEST.read_text(encoding="utf-8"), encoding="utf-8")
    manifest_only = discover_agent_context(root=manifest_root)
    assert manifest_only["status"] == "manifest_available"
    assert manifest_only["ready_for_model_input"] is False
    assert manifest_only["discovered"]["manifests"] == [manifest_path.as_posix()]
    assert "agent-handoff" in manifest_only["recommended_next_command"]
    assert validate_artifact_contract(manifest_only)["ok"] is True


def test_agent_route_normalizes_discovery_for_global_wrappers(tmp_path: Path) -> None:
    empty = route_agent_context(root=tmp_path)
    assert empty["status"] == "needs_bootstrap_agent_route"
    assert empty["action"] == "scan_and_build"
    assert empty["route_ready"] is True
    assert "dcf scan" in empty["recommended_next_command"]
    assert validate_artifact_contract(empty)["ok"] is True

    missing_handoff = route_agent_context(root=tmp_path, handoff_path=tmp_path / "missing_handoff.json")
    assert missing_handoff["status"] == "blocked_agent_route"
    assert missing_handoff["action"] == "verify_handoff"
    assert missing_handoff["route_ready"] is False
    assert "verify-handoff" in missing_handoff["recommended_next_command"]
    assert validate_artifact_contract(missing_handoff)["ok"] is True

    manifest_root = tmp_path / "manifest_only"
    manifest_root.mkdir()
    manifest_path = manifest_root / "deep_context_federation.json"
    manifest_path.write_text(EXAMPLE_MANIFEST.read_text(encoding="utf-8"), encoding="utf-8")

    missing_task = route_agent_context(root=manifest_root)
    assert missing_task["status"] == "needs_task_agent_route"
    assert missing_task["route_ready"] is False
    assert missing_task["requires_user_input"][0]["id"] == "task_required"
    assert validate_artifact_contract(missing_task)["ok"] is True

    runnable = route_agent_context(
        root=manifest_root,
        task="dashboard operator evidence authority",
        targets=["dashboard_readiness_projection"],
        output_dir=Path(".dcf"),
    )
    assert runnable["status"] == "needs_agent_handoff"
    assert runnable["action"] == "build_agent_handoff"
    assert runnable["route_ready"] is True
    assert "agent-handoff" in runnable["recommended_next_command"]
    assert manifest_path.as_posix() in runnable["recommended_next_command"]
    assert "--target 'dashboard_readiness_projection'" in runnable["recommended_next_command"]
    assert runnable["wrapper_contract"]["rerun_agent_discover_after_nonterminal_steps"] is True
    assert validate_artifact_contract(runnable)["ok"] is True


def test_agent_ready_builds_or_blocks_model_input(tmp_path: Path) -> None:
    manifest_root = tmp_path / "manifest_ready"
    manifest_root.mkdir()
    manifest_path = manifest_root / "deep_context_federation.json"
    manifest_path.write_text(EXAMPLE_MANIFEST.read_text(encoding="utf-8"), encoding="utf-8")

    missing_task = build_agent_ready(root=manifest_root, output_dir=manifest_root / ".dcf")
    assert missing_task["ok"] is False
    assert missing_task["status"] == "fail_agent_ready"
    assert {row["id"] for row in missing_task["errors"]} == {"task_required"}
    assert missing_task["prompt_text"] == ""
    assert validate_artifact_contract(missing_task)["ok"] is True

    missing_handoff = build_agent_ready(root=manifest_root, output_dir=manifest_root / ".dcf", handoff_path=manifest_root / "missing.json")
    assert missing_handoff["ok"] is False
    assert missing_handoff["action_taken"] == "blocked_by_route"
    assert missing_handoff["prompt_text"] == ""
    assert validate_artifact_contract(missing_handoff)["ok"] is True

    shutil.copytree(REPO_ROOT / "examples/fixtures", manifest_root / "fixtures")

    ready = build_agent_ready(
        root=manifest_root,
        output_dir=manifest_root / ".dcf",
        task="dashboard operator evidence authority",
        targets=["dashboard_readiness_projection"],
        efficiency_gate_policy=load_efficiency_gate_policy(EXAMPLE_EFFICIENCY_GATE_POLICY),
        agent_context_gate_policy=load_agent_context_gate_policy(EXAMPLE_AGENT_CONTEXT_GATE_POLICY),
        workflow_token_budget=900,
        context_token_budget=1800,
        max_artifact_tokens=500,
    )
    assert ready["ok"] is True
    assert ready["status"] == "pass_agent_ready"
    assert ready["action_taken"] == "build_agent_handoff"
    assert ready["route_summary"]["status"] == "needs_agent_handoff"
    assert ready["input_freshness"]["status"] == "freshly_built"
    assert ready["request_binding"]["status"] == "freshly_built"
    assert ready["handoff_summary"]["status"] in {"pass_agent_handoff", "warn_agent_handoff"}
    assert ready["model_input_summary"]["status"] == "pass_agent_model_input"
    assert ready["prompt_source"]
    assert ready["prompt_estimated_tokens"] > 0
    assert ready["prompt_text"].startswith("# Deep Context Federation Agent Context")
    assert validate_artifact_contract(ready)["ok"] is True

    reused = build_agent_ready(
        root=manifest_root,
        output_dir=manifest_root / ".dcf",
        handoff_path=manifest_root / ".dcf/deep_context_federation_agent_handoff.json",
    )
    assert reused["ok"] is True
    assert reused["action_taken"] == "read_existing_handoff"
    assert reused["input_freshness"]["status"] == "pass_input_fingerprint_compare"
    assert reused["input_freshness"]["matches"] is True
    assert reused["request_binding"]["status"] == "not_checked_no_request_binding"
    assert validate_artifact_contract(reused["input_freshness"], artifact_kind="input_fingerprint_compare")["ok"] is True
    assert validate_artifact_contract(reused["request_binding"], artifact_kind="request_binding")["ok"] is True
    assert validate_artifact_contract(reused)["ok"] is True

    wrong_task = build_agent_ready(
        root=manifest_root,
        output_dir=manifest_root / ".dcf",
        handoff_path=manifest_root / ".dcf/deep_context_federation_agent_handoff.json",
        task="different task",
    )
    assert wrong_task["ok"] is False
    assert wrong_task["status"] == "fail_agent_ready"
    assert wrong_task["request_binding"]["status"] == "fail_request_binding"
    assert {row["id"] for row in wrong_task["errors"]} == {"request_binding_mismatch"}
    assert wrong_task["prompt_text"] == ""
    assert validate_artifact_contract(wrong_task["request_binding"], artifact_kind="request_binding")["ok"] is True
    assert validate_artifact_contract(wrong_task)["ok"] is True

    wrong_target = build_agent_ready(
        root=manifest_root,
        output_dir=manifest_root / ".dcf",
        handoff_path=manifest_root / ".dcf/deep_context_federation_agent_handoff.json",
        targets=["research_only_boundary"],
    )
    assert wrong_target["ok"] is False
    assert wrong_target["request_binding"]["status"] == "fail_request_binding"
    assert {row["id"] for row in wrong_target["errors"]} == {"request_binding_mismatch"}
    assert wrong_target["prompt_text"] == ""
    assert validate_artifact_contract(wrong_target["request_binding"], artifact_kind="request_binding")["ok"] is True

    source_path = manifest_root / "fixtures/current_truth_snapshot.json"
    source_path.write_text(source_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    stale = build_agent_ready(
        root=manifest_root,
        output_dir=manifest_root / ".dcf",
        handoff_path=manifest_root / ".dcf/deep_context_federation_agent_handoff.json",
    )
    assert stale["ok"] is False
    assert stale["status"] == "fail_agent_ready"
    assert stale["input_freshness"]["status"] == "fail_input_fingerprint_compare"
    assert validate_artifact_contract(stale["input_freshness"], artifact_kind="input_fingerprint_compare")["ok"] is True
    assert {row["id"] for row in stale["errors"]} == {"input_fingerprint_mismatch"}
    assert stale["prompt_text"] == ""
    assert validate_artifact_contract(stale)["ok"] is True


def test_agent_ready_cli_uses_profile(tmp_path: Path) -> None:
    profile_root = tmp_path / "profile_ready"
    profile_root.mkdir()
    shutil.copytree(REPO_ROOT / "examples/fixtures", profile_root / "fixtures")
    (profile_root / "deep_context_federation.json").write_text(EXAMPLE_MANIFEST.read_text(encoding="utf-8"), encoding="utf-8")
    (profile_root / "efficiency_policy.json").write_text(EXAMPLE_EFFICIENCY_GATE_POLICY.read_text(encoding="utf-8"), encoding="utf-8")
    (profile_root / "agent_context_policy.json").write_text(EXAMPLE_AGENT_CONTEXT_GATE_POLICY.read_text(encoding="utf-8"), encoding="utf-8")
    profile_path = profile_root / "agent_ready_profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "schema_version": "deep_context_federation_agent_profile_v1",
                "profile_id": "tmp_agent_ready_profile",
                "authority_effect": "none",
                "no_apply": True,
                "root": ".",
                "output_dir": ".dcf",
                "manifests": ["deep_context_federation.json"],
                "task": "dashboard operator evidence authority",
                "targets": ["dashboard_readiness_projection"],
                "efficiency_policy": "efficiency_policy.json",
                "context_gate_policy": "agent_context_policy.json",
                "workflow_token_budget": 900,
                "context_token_budget": 1800,
                "max_artifact_tokens": 500,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    profile = load_agent_profile(profile_path)
    assert profile["ok"] is True
    assert profile["normalized"]["root"] == profile_root.resolve().as_posix()
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "deep_context_federation.cli",
            "agent-ready",
            "--profile",
            str(profile_path),
            "--format",
            "json",
        ],
        cwd=profile_root,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    ready = json.loads(completed.stdout)
    assert ready["schema_version"] == "deep_context_federation_agent_ready_v1"
    assert ready["ok"] is True
    assert ready["status"] == "pass_agent_ready"
    assert ready["action_taken"] == "build_agent_handoff"
    assert ready["task"] == "dashboard operator evidence authority"
    assert ready["targets"] == ["dashboard_readiness_projection"]
    assert ready["agent_profile_summary"]["status"] == "pass_agent_profile"
    assert ready["prompt_estimated_tokens"] > 0
    assert validate_artifact_contract(ready)["ok"] is True


def test_agent_profile_init_cli_feeds_agent_ready(tmp_path: Path) -> None:
    profile_root = tmp_path / "profile_init_cli"
    profile_root.mkdir()
    shutil.copytree(REPO_ROOT / "examples/fixtures", profile_root / "fixtures")
    (profile_root / "deep_context_federation.json").write_text(EXAMPLE_MANIFEST.read_text(encoding="utf-8"), encoding="utf-8")
    (profile_root / "efficiency_policy.json").write_text(EXAMPLE_EFFICIENCY_GATE_POLICY.read_text(encoding="utf-8"), encoding="utf-8")
    (profile_root / "agent_context_policy.json").write_text(EXAMPLE_AGENT_CONTEXT_GATE_POLICY.read_text(encoding="utf-8"), encoding="utf-8")
    profile_path = profile_root / ".dcf" / "agent_ready_profile.json"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src")

    init = subprocess.run(
        [
            sys.executable,
            "-m",
            "deep_context_federation.cli",
            "agent-profile-init",
            "--root",
            str(profile_root),
            "--output",
            str(profile_path),
            "--task",
            "dashboard operator evidence authority",
            "--target",
            "dashboard_readiness_projection",
            "--manifest",
            "deep_context_federation.json",
            "--efficiency-policy",
            "efficiency_policy.json",
            "--context-gate-policy",
            "agent_context_policy.json",
            "--workflow-token-budget",
            "900",
            "--context-token-budget",
            "1800",
            "--max-artifact-tokens",
            "500",
            "--format",
            "json",
        ],
        cwd=profile_root,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )
    assert init.returncode == 0, init.stderr + init.stdout
    init_payload = json.loads(init.stdout)
    assert init_payload["status"] == "pass_agent_profile_init"
    assert init_payload["profile_validation_summary"]["status"] == "pass_agent_profile"
    assert profile_path.exists()
    assert validate_artifact_contract(init_payload, artifact_kind="agent_profile_init")["ok"] is True

    ready = subprocess.run(
        [
            sys.executable,
            "-m",
            "deep_context_federation.cli",
            "agent-ready",
            "--profile",
            str(profile_path),
            "--format",
            "json",
        ],
        cwd=profile_root,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )
    assert ready.returncode == 0, ready.stderr + ready.stdout
    ready_payload = json.loads(ready.stdout)
    assert ready_payload["status"] == "pass_agent_ready"
    assert ready_payload["action_taken"] == "build_agent_handoff"
    assert ready_payload["agent_profile_summary"]["status"] == "pass_agent_profile"
    assert ready_payload["prompt_estimated_tokens"] > 0
    assert validate_artifact_contract(ready_payload, artifact_kind="agent_ready")["ok"] is True


def test_agent_onboard_builds_profile_and_ready(tmp_path: Path) -> None:
    profile_root = tmp_path / "agent_onboard"
    profile_root.mkdir()
    shutil.copytree(REPO_ROOT / "examples/fixtures", profile_root / "fixtures")
    manifest_path = profile_root / "deep_context_federation.json"
    manifest_path.write_text(EXAMPLE_MANIFEST.read_text(encoding="utf-8"), encoding="utf-8")
    efficiency_policy = profile_root / "efficiency_policy.json"
    efficiency_policy.write_text(EXAMPLE_EFFICIENCY_GATE_POLICY.read_text(encoding="utf-8"), encoding="utf-8")
    context_policy = profile_root / "agent_context_policy.json"
    context_policy.write_text(EXAMPLE_AGENT_CONTEXT_GATE_POLICY.read_text(encoding="utf-8"), encoding="utf-8")
    profile_path = profile_root / ".dcf" / "agent_ready_profile.json"

    result = build_agent_onboard(
        root=profile_root,
        profile_path=profile_path,
        task="dashboard operator evidence authority",
        targets=["dashboard_readiness_projection"],
        manifests=[manifest_path],
        efficiency_policy_path=efficiency_policy,
        context_gate_policy_path=context_policy,
        workflow_token_budget=900,
        context_token_budget=1800,
        max_artifact_tokens=500,
    )

    assert result["schema_version"] == "deep_context_federation_agent_onboard_v1"
    assert result["ok"] is True
    assert result["status"] == "pass_agent_onboard"
    assert result["authority_effect"] == "none"
    assert result["no_apply"] is True
    assert result["profile_init_summary"]["status"] == "pass_agent_profile_init"
    assert result["profile_validation_summary"]["status"] == "pass_agent_profile"
    assert result["agent_ready_summary"]["status"] == "pass_agent_ready"
    assert result["model_input_ready"] is True
    assert result["prompt_estimated_tokens"] > 0
    assert Path(result["outputs"]["agent_profile_json"]).exists()
    assert Path(result["outputs"]["agent_handoff_json"]).exists()
    assert "agent-ready --profile" in result["recommended_next_command"]
    assert validate_artifact_contract(result, artifact_kind="agent_onboard")["ok"] is True
    assert validate_artifact_contract(result["agent_ready"], artifact_kind="agent_ready")["ok"] is True


def test_agent_onboard_cli_single_command(tmp_path: Path) -> None:
    profile_root = tmp_path / "agent_onboard_cli"
    profile_root.mkdir()
    shutil.copytree(REPO_ROOT / "examples/fixtures", profile_root / "fixtures")
    (profile_root / "deep_context_federation.json").write_text(EXAMPLE_MANIFEST.read_text(encoding="utf-8"), encoding="utf-8")
    (profile_root / "efficiency_policy.json").write_text(EXAMPLE_EFFICIENCY_GATE_POLICY.read_text(encoding="utf-8"), encoding="utf-8")
    (profile_root / "agent_context_policy.json").write_text(EXAMPLE_AGENT_CONTEXT_GATE_POLICY.read_text(encoding="utf-8"), encoding="utf-8")
    profile_path = profile_root / ".dcf" / "agent_ready_profile.json"
    onboard_path = profile_root / ".dcf" / "agent_onboard.json"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "deep_context_federation.cli",
            "agent-onboard",
            "--root",
            str(profile_root),
            "--profile-output",
            str(profile_path),
            "--output",
            str(onboard_path),
            "--task",
            "dashboard operator evidence authority",
            "--target",
            "dashboard_readiness_projection",
            "--manifest",
            "deep_context_federation.json",
            "--efficiency-policy",
            "efficiency_policy.json",
            "--context-gate-policy",
            "agent_context_policy.json",
            "--workflow-token-budget",
            "900",
            "--context-token-budget",
            "1800",
            "--max-artifact-tokens",
            "500",
            "--format",
            "json",
        ],
        cwd=profile_root,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["status"] == "pass_agent_onboard"
    assert payload["profile_validation_summary"]["status"] == "pass_agent_profile"
    assert payload["agent_ready_summary"]["status"] == "pass_agent_ready"
    assert payload["outputs"]["agent_onboard_json"] == onboard_path.resolve().as_posix()
    assert profile_path.exists()
    assert onboard_path.exists()
    assert validate_artifact_contract(payload, artifact_kind="agent_onboard")["ok"] is True


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
