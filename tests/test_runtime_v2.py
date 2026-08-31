from __future__ import annotations

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from deep_context_federation.cli import main as dcf_main
from deep_context_federation.runtime_v2.cli import _reconcile_pending_events
from deep_context_federation.runtime_v2.events import enqueue_event, pending_events
from deep_context_federation.runtime_v2.jspace import (
    JSpaceCompileError,
    compile_jspace_contract,
    compile_task_context_capsule,
)
from deep_context_federation.runtime_v2.query import FreshnessBlocked
from deep_context_federation.runtime_v2.runtime import DcfRuntime
from deep_context_federation.runtime_v2.storage import GenerationUnavailable


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.strip()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _project(tmp_path: Path, *, with_contracts: bool = True) -> tuple[Path, Path]:
    root = tmp_path / "project"
    runtime_root = tmp_path / "runtime"
    root.mkdir()
    (root / "src").mkdir()
    (root / "src/example.py").write_text(
        "def hello(name: str) -> str:\n    return f'hello {name}'\n",
        encoding="utf-8",
    )
    (root / ".gitignore").write_text("output/\n", encoding="utf-8")
    if with_contracts:
        _write_json(
            root / "config/contracts/dcf_v2_contract.json",
            {
                "schema_version": "dcf_v2_contract",
                "capabilities": [
                    "surface-map",
                    "source-navigation",
                    "model-context",
                ],
                "authority_effect": "none",
                "no_apply": True,
            },
        )
        _write_json(
            root / "config/contracts/repo_surface_boundary_governance_v1.json",
            {
                "schema_version": "repo_surface_boundary_governance_v1",
                "surface_count_expected": 1,
                "surfaces": [
                    {
                        "id": "application_source",
                        "display": "Application source",
                        "owner_lane": "application",
                        "owner_board": "engineering",
                        "surface_class": "source",
                        "authority_role": "implementation",
                        "protected_class": "none",
                        "read_only": False,
                        "requires_heavy_harness": False,
                        "logical_ref": ["src/**"],
                        "allowed_write_scopes": ["src/**"],
                        "required_verifiers": ["python -m pytest -q"],
                        "claim_boundary": "source ownership only",
                        "forbidden_crossings": ["production authority"],
                    }
                ],
                "authority_effect": "none",
                "no_apply": True,
            },
        )
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "DCF Test")
    _git(root, "config", "user.email", "dcf@example.invalid")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "fixture")
    return root, runtime_root


def test_no_write_refresh_is_typed_and_has_no_runtime_effect(tmp_path: Path) -> None:
    root, runtime_root = _project(tmp_path)
    runtime = DcfRuntime(root, runtime_root=runtime_root)

    result = runtime.refresh(write=False, reason="test")

    assert result["status"] == "validated_no_write"
    assert result["authority_effect"] == "none"
    assert result["no_apply"] is True
    assert not runtime_root.exists()


def test_publish_status_query_and_integrity_share_one_generation(tmp_path: Path) -> None:
    root, runtime_root = _project(tmp_path)
    runtime = DcfRuntime(root, runtime_root=runtime_root)

    published = runtime.refresh(write=True, reason="test")
    status = runtime.status()
    surface = runtime.query("surface-map", target="application_source")
    symbol = runtime.query("source-navigation", target="hello")
    verified = runtime.verify_current()

    generation_id = published["generation_id"]
    assert status.generation_id == generation_id
    assert surface["generation_id"] == generation_id
    assert surface["result"]["resolved"] is True
    assert symbol["generation_id"] == generation_id
    assert symbol["result"]["resolved"]
    assert verified["ok"] is True
    assert (runtime_root / "current.json").is_file()
    assert (runtime_root / "last_good.json").is_file()


def test_missing_project_contracts_are_explicit_typed_absence(tmp_path: Path) -> None:
    root, runtime_root = _project(tmp_path, with_contracts=False)
    runtime = DcfRuntime(root, runtime_root=runtime_root)

    result = runtime.refresh(write=False, reason="missing-contracts")

    snapshot = result["snapshot"]
    assert snapshot["projection_status"] == "blocked"
    blocker_codes = {
        blocker["code"]
        for capability in snapshot["capabilities"].values()
        for blocker in capability.get("blockers", [])
    }
    assert "source_unavailable" in blocker_codes
    assert not runtime_root.exists()


def test_event_reconcile_coalesces_without_replaying_events(
    tmp_path: Path,
) -> None:
    root, runtime_root = _project(tmp_path)
    enqueue_event(root, kind="git", payload={"reason": "one"}, runtime_root=runtime_root)
    enqueue_event(
        root,
        kind="receipt",
        payload={"reason": "two"},
        runtime_root=runtime_root,
    )

    exit_code = dcf_main(
        [
            "runtime",
            "reconcile-events",
            "--repo-root",
            str(root),
            "--runtime-root",
            str(runtime_root),
            "--json",
        ]
    )

    assert exit_code == 0
    assert pending_events(root, runtime_root=runtime_root) == []
    receipts = list((runtime_root / "events/processed").glob("*.json"))
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert receipt["event_ids"] and len(receipt["event_ids"]) == 2


def test_explicit_runtime_root_overrides_environment(tmp_path: Path, monkeypatch) -> None:
    root, runtime_root = _project(tmp_path)
    environment_root = tmp_path / "environment-runtime"
    monkeypatch.setenv("DCF_RUNTIME_ROOT", str(environment_root))

    runtime = DcfRuntime(root, runtime_root=runtime_root)
    enqueue_event(root, kind="operator", runtime_root=runtime_root)

    assert runtime.store.root == runtime_root.resolve()
    assert pending_events(root, runtime_root=runtime_root)
    assert not environment_root.exists()


def test_concurrent_event_reconcilers_consume_one_batch_once(tmp_path: Path) -> None:
    root, runtime_root = _project(tmp_path)
    enqueue_event(root, kind="git", payload={"reason": "one"}, runtime_root=runtime_root)
    enqueue_event(root, kind="receipt", payload={"reason": "two"}, runtime_root=runtime_root)

    def reconcile() -> dict[str, object]:
        return _reconcile_pending_events(
            DcfRuntime(root, runtime_root=runtime_root),
            repo_root=root,
            runtime_root=runtime_root,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: reconcile(), range(2)))

    assert sorted(result["status"] for result in results) == ["published", "unchanged"]
    assert sum(int(result["coalesced_event_count"]) for result in results) == 2
    assert len(list((runtime_root / "generations").iterdir())) == 1
    assert len(list((runtime_root / "events/processed").glob("*.json"))) == 1


def test_jspace_and_task_context_capsule_are_bounded_and_deterministic(
    tmp_path: Path,
) -> None:
    root, runtime_root = _project(tmp_path)
    runtime = DcfRuntime(root, runtime_root=runtime_root)
    runtime.refresh(write=True, reason="test")
    action = {
        "repo_root": str(root),
        "operations": ["read"],
        "read_scopes": ["src/**"],
        "mission": {
            "mission_id": "public-runtime-test",
            "mode": "DELIVERY",
            "current_predicate": "RUNTIME_QUERY_WORKS",
            "objective": "Read one source surface through DCF v2",
        },
        "context_summary": "Inspect the configured application source without mutation.",
        "evidence_refs": [
            {"id": "fixture-source", "kind": "git_commit", "sha256": "0" * 64}
        ],
        "forbidden_effects": ["production_mutation"],
    }

    contract = compile_jspace_contract(
        runtime,
        surface_id="application_source",
        action=action,
    )
    first = compile_task_context_capsule(contract, action=action)
    second = compile_task_context_capsule(contract, action=action)

    assert contract["matched_surface_ids"] == ["application_source"]
    assert first == second
    assert first["semantic_sha256"] == second["semantic_sha256"]
    assert first["jspace_semantic_sha256"] == contract["authorization_semantic_sha256"]
    assert len(first["context_summary"]) < 32_000


def test_jspace_rejects_out_of_surface_reads_and_undeclared_commands(
    tmp_path: Path,
) -> None:
    root, runtime_root = _project(tmp_path)
    runtime = DcfRuntime(root, runtime_root=runtime_root)
    runtime.refresh(write=True, reason="test")
    base_action = {
        "repo_root": str(root),
        "operations": ["read"],
        "read_scopes": ["secrets/**"],
    }

    with pytest.raises(JSpaceCompileError, match="read scope is not contained") as read_error:
        compile_jspace_contract(
            runtime,
            surface_id="application_source",
            action=base_action,
        )
    assert read_error.value.error_code == "JSPACE_READ_SCOPE_OUTSIDE_SURFACE"

    command_action = {
        "repo_root": str(root),
        "operations": ["read", "command"],
        "read_scopes": ["src/**"],
        "command_templates": ["rm -rf /"],
    }
    with pytest.raises(JSpaceCompileError, match="command is not declared") as command_error:
        compile_jspace_contract(
            runtime,
            surface_id="application_source",
            action=command_action,
        )
    assert command_error.value.error_code == "JSPACE_COMMAND_NOT_DECLARED"

    admitted = {
        **command_action,
        "command_templates": ["python -m pytest -q"],
    }
    contract = compile_jspace_contract(
        runtime,
        surface_id="application_source",
        action=admitted,
    )
    assert contract["command_templates"][0]["argv"] == ["python", "-m", "pytest", "-q"]


def test_query_and_jspace_reject_same_size_generation_tampering(tmp_path: Path) -> None:
    root, runtime_root = _project(tmp_path)
    runtime = DcfRuntime(root, runtime_root=runtime_root)
    generation_id = runtime.refresh(write=True, reason="test")["generation_id"]
    context = runtime_root / "generations" / generation_id / "context.json"
    original = context.read_bytes()
    tampered = original.replace(
        b'"projection_status": "pass"',
        b'"projection_status": "warn"',
        1,
    )
    assert tampered != original and len(tampered) == len(original)
    context.write_bytes(tampered)

    with pytest.raises(GenerationUnavailable):
        runtime.query("surface-map")
    with pytest.raises(GenerationUnavailable):
        compile_jspace_contract(
            runtime,
            surface_id="application_source",
            action={
                "repo_root": str(root),
                "operations": ["read"],
                "read_scopes": ["src/**"],
            },
        )


def test_source_and_working_state_changes_invalidate_their_capabilities(
    tmp_path: Path,
) -> None:
    root, runtime_root = _project(tmp_path)
    runtime = DcfRuntime(root, runtime_root=runtime_root)
    runtime.refresh(write=True, reason="test")

    (root / "src/example.py").write_text("VALUE = 1\n", encoding="utf-8")
    with pytest.raises(FreshnessBlocked, match="source-navigation is stale"):
        runtime.query("source-navigation", target="hello")

    (root / "src/example.py").write_text(
        "def hello(name: str) -> str:\n    return f'hello {name}'\n",
        encoding="utf-8",
    )
    lease = root / "output/task_runtime/active/example.json"
    _write_json(lease, {"task_id": "example-task"})
    with pytest.raises(FreshnessBlocked, match="current-state is stale"):
        runtime.query("current-state")
    intake = runtime.query("report-back-intake")
    assert [row["task_id"] for row in intake["result"]["active_tasks"]] == [
        "example-task"
    ]


def test_top_level_cli_preserves_legacy_namespace_and_exposes_runtime(
    tmp_path: Path, capsys
) -> None:
    root, runtime_root = _project(tmp_path)
    runtime = DcfRuntime(root, runtime_root=runtime_root)
    generation_id = runtime.refresh(write=True, reason="test")["generation_id"]

    exit_code = dcf_main(
        [
            "runtime",
            "status",
            "--repo-root",
            str(root),
            "--runtime-root",
            str(runtime_root),
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["generation_id"] == generation_id
    assert payload["safety"]["authority_effect"] == "none"


def test_current_generation_hash_tampering_fails_closed(tmp_path: Path) -> None:
    root, runtime_root = _project(tmp_path)
    runtime = DcfRuntime(root, runtime_root=runtime_root)
    generation_id = runtime.refresh(write=True, reason="test")["generation_id"]
    context = runtime_root / "generations" / generation_id / "context.json"
    context.write_text("{}\n", encoding="utf-8")

    result = runtime.verify_current()

    assert result["ok"] is False
    assert result["status"] == "blocked"
