from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from deep_context_federation.builder import build_federation, codebase_memory_source
from deep_context_federation.query import query_federation
from deep_context_federation.verifier import verify_federation


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_MANIFEST = REPO_ROOT / "examples/deep_context_federation.example.json"


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
    assert (tmp_path / "deep_context_federation_latest.json").exists()
    assert (tmp_path / "DEEP_CONTEXT_FEDERATION_LATEST.md").exists()
    assert (tmp_path / "deep_context_federation_latest.sqlite").exists()

    manifest = json.loads(EXAMPLE_MANIFEST.read_text(encoding="utf-8"))
    result = verify_federation(payload, manifest=manifest, root=REPO_ROOT)
    assert result["ok"] is True

    query = query_federation(payload, preset="claim-lineage", limit=10)
    assert query["schema_version"] == "deep_context_federation_query_v1"
    assert query["row_count"] > 0


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
