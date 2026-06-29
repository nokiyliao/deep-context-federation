"""Token efficiency reports for DCF workflow runs."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from deep_context_federation.builder import read_json
from deep_context_federation.builder import utc_now
from deep_context_federation.context_pack import estimate_tokens

EFFICIENCY_REPORT_SCHEMA_VERSION = "deep_context_federation_efficiency_report_v1"
DEFAULT_EFFICIENCY_REPORT_JSON_NAME = "deep_context_federation_efficiency_report.json"
DEFAULT_EFFICIENCY_REPORT_MD_NAME = "DEEP_CONTEXT_FEDERATION_EFFICIENCY_REPORT.md"


def _resolve_path(path: str | Path, *, base_dir: Path) -> Path:
    candidate = Path(str(path)).expanduser()
    if not candidate.is_absolute():
        candidate = base_dir / candidate
    return candidate.resolve()


def _json_text(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    except Exception:
        return str(value)


def _artifact_row(path: Path, *, roles: Sequence[str], required: bool) -> dict[str, Any]:
    exists = path.exists() and path.is_file()
    text = ""
    if exists:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            text = ""
    return {
        "path": path.as_posix(),
        "roles": sorted(set(str(role) for role in roles if role)),
        "required": bool(required),
        "exists": exists,
        "bytes": path.stat().st_size if exists else 0,
        "estimated_tokens": estimate_tokens(text) if text else 0,
        "schema_version": _schema_version(text),
    }


def _schema_version(text: str) -> str:
    if not text:
        return ""
    try:
        payload = json.loads(text)
    except Exception:
        return ""
    if isinstance(payload, Mapping):
        return str(payload.get("schema_version") or "")
    return ""


def _rows_for_roles(role_paths: Mapping[str, Sequence[str]], *, base_dir: Path) -> list[dict[str, Any]]:
    roles_by_path: dict[str, set[str]] = defaultdict(set)
    required_by_path: dict[str, bool] = defaultdict(bool)
    for role, paths in role_paths.items():
        for raw in paths:
            if not raw:
                continue
            path = _resolve_path(raw, base_dir=base_dir).as_posix()
            roles_by_path[path].add(role)
            if role in {"workflow_run", "read_first", "baseline"}:
                required_by_path[path] = True
    return [
        _artifact_row(Path(path), roles=sorted(roles), required=required_by_path[path])
        for path, roles in sorted(roles_by_path.items())
    ]


def _sum_tokens(rows: Sequence[Mapping[str, Any]], role: str) -> int:
    return sum(int(row.get("estimated_tokens") or 0) for row in rows if role in (row.get("roles") or []))


def _first_existing_tokens(rows: Sequence[Mapping[str, Any]], role: str) -> int:
    values = [int(row.get("estimated_tokens") or 0) for row in rows if role in (row.get("roles") or []) and row.get("exists")]
    return values[0] if values else 0


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), 6)


def _percent_savings(selected: int, baseline: int) -> float | None:
    if baseline <= 0:
        return None
    return round(max(0.0, (float(baseline) - float(selected)) / float(baseline)) * 100.0, 3)


def _workflow_outputs(workflow_run: Mapping[str, Any]) -> dict[str, str]:
    outputs = workflow_run.get("outputs") if isinstance(workflow_run.get("outputs"), Mapping) else {}
    return {str(key): str(value) for key, value in outputs.items() if value}


def _agent_intake_outputs(outputs: Mapping[str, str], *, base_dir: Path) -> dict[str, str]:
    intake_path = outputs.get("agent_intake_json")
    if not intake_path:
        return {}
    intake = read_json(_resolve_path(intake_path, base_dir=base_dir))
    raw_outputs = intake.get("outputs") if isinstance(intake.get("outputs"), Mapping) else {}
    return {str(key): str(value) for key, value in raw_outputs.items() if value}


def build_efficiency_report(
    workflow_run: Mapping[str, Any],
    *,
    workflow_run_path: Path,
    extra_baselines: Sequence[Path] = (),
) -> dict[str, Any]:
    """Build a machine-readable token efficiency report for a workflow run."""

    workflow_run_path = workflow_run_path.expanduser().resolve()
    base_dir = workflow_run_path.parent
    handoff = workflow_run.get("model_handoff") if isinstance(workflow_run.get("model_handoff"), Mapping) else {}
    outputs = _workflow_outputs(workflow_run)
    intake_outputs = _agent_intake_outputs(outputs, base_dir=base_dir)
    read_first = [str(item) for item in handoff.get("read_first") or [] if item]
    read_next = [str(item) for item in handoff.get("read_next_if_gate_passes") or [] if item]
    baseline_paths = []
    federation_path = intake_outputs.get("federation_json")
    if federation_path:
        baseline_paths.append(federation_path)
    baseline_paths.extend(path.as_posix() for path in extra_baselines)
    role_paths = {
        "workflow_run": [workflow_run_path.as_posix()],
        "read_first": read_first,
        "read_next_if_gate_passes": read_next,
        "baseline": baseline_paths,
        "available_output": list(outputs.values()) + list(intake_outputs.values()),
    }
    artifacts = _rows_for_roles(role_paths, base_dir=base_dir)
    read_first_tokens = _sum_tokens(artifacts, "read_first")
    read_next_tokens = _sum_tokens(artifacts, "read_next_if_gate_passes")
    gate_pass_tokens = read_first_tokens + read_next_tokens
    baseline_tokens = _first_existing_tokens(artifacts, "baseline")
    all_available_tokens = _sum_tokens(artifacts, "available_output")
    effective_baseline = baseline_tokens or all_available_tokens
    missing_required = [
        row["path"]
        for row in artifacts
        if row.get("required") and not row.get("exists")
    ]
    warnings: list[str] = []
    if not baseline_tokens:
        warnings.append("No full federation baseline artifact was available; using all available output tokens as fallback.")
    if not read_first_tokens:
        warnings.append("No read_first artifacts were available for token measurement.")
    status = "pass_efficiency_report"
    ok = True
    if missing_required:
        status = "fail_efficiency_report"
        ok = False
    elif warnings:
        status = "warn_efficiency_report"
    result = {
        "schema_version": EFFICIENCY_REPORT_SCHEMA_VERSION,
        "ok": ok,
        "status": status,
        "authority_effect": "none",
        "no_apply": True,
        "generated_at": utc_now(),
        "workflow_run_ref": workflow_run_path.as_posix(),
        "workflow_run_status": workflow_run.get("status"),
        "task": workflow_run.get("task"),
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "model_context_budget": {
            "read_first_estimated_tokens": read_first_tokens,
            "read_next_if_gate_passes_estimated_tokens": read_next_tokens,
            "gate_pass_estimated_tokens": gate_pass_tokens,
            "full_federation_estimated_tokens": baseline_tokens,
            "all_available_output_estimated_tokens": all_available_tokens,
            "effective_baseline_estimated_tokens": effective_baseline,
            "read_first_ratio_vs_baseline": _ratio(read_first_tokens, effective_baseline),
            "gate_pass_ratio_vs_baseline": _ratio(gate_pass_tokens, effective_baseline),
            "read_first_token_savings": max(0, effective_baseline - read_first_tokens),
            "gate_pass_token_savings": max(0, effective_baseline - gate_pass_tokens),
            "read_first_savings_percent": _percent_savings(read_first_tokens, effective_baseline),
            "gate_pass_savings_percent": _percent_savings(gate_pass_tokens, effective_baseline),
        },
        "missing_required_artifacts": missing_required,
        "warnings": warnings,
        "recommendations": _recommendations(read_first_tokens, gate_pass_tokens, effective_baseline, missing_required),
        "safety_boundaries": {
            "authority_effect": "none",
            "no_apply": True,
            "mutation_allowed": False,
            "external_model_calls": False,
            "measures_generated_artifacts_only": True,
        },
    }
    result["json_estimated_tokens"] = estimate_tokens(_json_text(result))
    return result


def _recommendations(read_first: int, gate_pass: int, baseline: int, missing_required: Sequence[str]) -> list[str]:
    if missing_required:
        return ["Repair missing required artifacts before using the workflow run as model context."]
    if baseline <= 0:
        return ["Generate a workflow run with an agent intake artifact so a full-federation baseline can be measured."]
    recommendations = []
    first_ratio = _ratio(read_first, baseline)
    gate_ratio = _ratio(gate_pass, baseline)
    if first_ratio is not None and first_ratio > 0.5:
        recommendations.append("Read-first context is more than half of baseline; tighten workflow handoff or prompt payloads.")
    if gate_ratio is not None and gate_ratio > 0.8:
        recommendations.append("Gate-pass context is close to baseline; prefer target review summaries over full target details.")
    if not recommendations:
        recommendations.append("Use read_first artifacts as the default model entrypoint; expand only after gates pass.")
    return recommendations


def markdown_efficiency_report(result: Mapping[str, Any]) -> str:
    budget = result.get("model_context_budget") if isinstance(result.get("model_context_budget"), Mapping) else {}
    lines = [
        "# Deep Context Federation Efficiency Report",
        "",
        f"- Status: `{result.get('status')}`",
        f"- OK: `{result.get('ok')}`",
        f"- Task: `{result.get('task')}`",
        f"- Workflow run: `{result.get('workflow_run_ref')}`",
        f"- Read-first tokens: `{budget.get('read_first_estimated_tokens')}`",
        f"- Gate-pass tokens: `{budget.get('gate_pass_estimated_tokens')}`",
        f"- Baseline tokens: `{budget.get('effective_baseline_estimated_tokens')}`",
        f"- Read-first savings: `{budget.get('read_first_savings_percent')}`%",
        f"- Gate-pass savings: `{budget.get('gate_pass_savings_percent')}`%",
        "",
        "## Recommendations",
        "",
    ]
    for item in result.get("recommendations") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Artifacts", ""])
    for row in result.get("artifacts") or []:
        if isinstance(row, Mapping):
            lines.append(
                "- `{path}` roles=`{roles}` exists=`{exists}` tokens=`{tokens}`".format(
                    path=row.get("path"),
                    roles=",".join(row.get("roles") or []),
                    exists=row.get("exists"),
                    tokens=row.get("estimated_tokens"),
                )
            )
    return "\n".join(lines).rstrip() + "\n"
