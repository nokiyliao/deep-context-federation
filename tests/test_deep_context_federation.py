from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from deep_context_federation.bench import benchmark_build
from deep_context_federation.builder import build_federation, codebase_memory_source
from deep_context_federation.cache import DEFAULT_CACHE_NAME
from deep_context_federation.diff import diff_federations
from deep_context_federation.doctor import doctor_federation
from deep_context_federation.graph import trace_federation
from deep_context_federation.manifest import validate_manifest
from deep_context_federation.query import query_federation
from deep_context_federation.rank import rank_entities
from deep_context_federation.rank import rank_sources
from deep_context_federation.scanner import scan_repository
from deep_context_federation.sqlite_query import query_sqlite
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
                "class Thing:",
                "    def run(self):",
                "        return 1",
                "",
                "def helper():",
                "    return Thing().run()",
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
    assert result["summary"]["file_count"] == 4
    assert result["summary"]["symbol_count"] >= 2
    assert "output" in result["summary"]["skipped_dirs"]

    manifest_path = Path(result["outputs"]["manifest"])
    assert manifest_path.exists()
    assert Path(result["outputs"]["inventory"]).exists()
    assert Path(result["outputs"]["symbols"]).exists()
    assert Path(result["outputs"]["surfaces"]).exists()

    symbol_payload = json.loads(Path(result["outputs"]["symbols"]).read_text(encoding="utf-8"))
    symbols = [row["symbol_fqn"] for row in symbol_payload["symbols"]]
    assert any(symbol.endswith(".Thing") for symbol in symbols)
    assert any(symbol.endswith(".helper") for symbol in symbols)

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

    query = query_federation(payload, preset="code-to-authority", limit=20)
    values = {row["value"] for row in query["rows"]}
    assert "src/pkg/mod.py" in values
