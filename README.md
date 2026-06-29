# Deep Context Federation

Deep Context Federation is a small, read-only unified context plane for large codebases and agent workflows.

It collapses local context capabilities such as:

- project truth snapshots
- evidence and receipt indexes
- operator or governance projections
- surface maps
- symbol/call graphs
- long-term context memory

The output is a machine-readable DCF graph of entities, edges, conflicts, local "Codex Fusion" synthesis roles, and a SQLite read model. It is designed to help humans and coding agents ask, "What is the unified DCF view, what evidence supports it, and what is stale, conflicting, or unsafe to use?"

## Why It Exists

Most code-intelligence tools optimize one lane:

- symbol graph navigation
- repository surface maps
- long-term code memory
- evidence receipt indexing
- dashboard/operator projection

Deep Context Federation is the native integration layer across those lanes. It owns the unified query, index, governance, and model-handoff plane; specialized upstream outputs can be ingested, but they are collapsed into DCF capability rows rather than exposed as competing user-facing source identities.

## Boundary

This tool is deliberately non-authoritative:

- `authority_effect: none`
- `no_apply: true`
- no live/runtime/broker/promotion mutation
- no task ledger replacement
- no external model calls
- no automatic installer or watcher for optional tools

It does not decide production truth. It projects and checks consistency through one DCF read model while preserving auditability for the immutable evidence records underneath.

## Integrated Capabilities

Deep Context Federation now combines several capabilities that are usually split across separate tools:

- generic JSON federation for arbitrary governance artifacts
- self-bootstrap repo scan that emits starter inventory, surface, code-symbol, and dependency-graph sources
- native ingestion for surface maps, symbol maps, and graph exports
- claim-to-evidence lineage extraction
- source health scoring and freshness warnings
- semantic edges such as `OWNS`, `SUPPORTS`, `DERIVES_FROM`, and `REFERENCES_SYMBOL`
- SQLite read model with search presets
- graph trace from any matching entity
- target resolver for claim/path/surface/symbol evidence cards
- deterministic target adjudication across authority, evidence, and advisory tiers
- batch target review for governance prioritization across many targets
- target review gate for CI and agent routing thresholds
- manifest composition for merging self-scan output with curated evidence/context sources
- one-command bootstrap pipeline for scan, compose, build, verify, and doctor
- one-command agent intake packet for bootstrap, quality gate, and task brief
- workflow plan artifact that sequences intake, validation, target review, gates, and bounded context reads
- workflow run capsule that executes the read-only DCF chain and returns one compact handoff artifact
- efficiency report that measures read-first and gate-pass token savings against generated baselines
- efficiency gate that turns token-savings targets into CI or agent routing thresholds
- context-advantage proof that combines unified-plane and token-efficiency evidence before claiming DCF is the better default entrypoint
- continuation decision that chains workflow run, efficiency report, and efficiency gate into one read-first artifact
- model context bundle that materializes selected `decide-continuation` read-plan artifacts into one bounded prompt/context payload
- model context gate that enforces token, missing-artifact, truncation, and schema thresholds before model handoff
- model handoff command that runs the continuation decision, bounded context bundle, and context gate in one pipeline
- model-readiness route command that normalizes discovery into a stable global-wrapper route decision
- model-input preparation command that turns a safe handoff or manifest+task into verified model prompt input
- run profile contract that lets global wrappers drive `prepare-model-input` from one validated JSON file
- run profile init command that generates that wrapper profile from repo-local manifest and policy paths
- runner onboarding command that generates the profile and runs the fail-closed ready path in one global-wrapper capsule
- native integration plan that collapses overlapping tool identities into DCF-owned capabilities
- memory ledger that materializes generated handoff, ready, onboard, workflow, and fingerprint artifacts into reusable DCF-native context memory
- unified context index that collapses graph, memory, commands, and native capability rows into source-hidden function facets
- unified-plane audit that checks command naming, ownership collapse, context-index facets, and source-identity leakage
- self-describing capabilities manifest for commands, contracts, presets, and safety boundaries
- JSON Schema registry and built-in artifact contract validation
- task routing brief that selects query presets, runs diagnostics, and embeds a bounded prompt pack
- token-aware context packing for bounded model prompts
- machine-readable quality gate for CI and agent routing
- entity/source ranking for prioritization
- doctor-style diagnostics with recommended actions
- federation diff between two builds
- source fingerprint cache for incremental runs
- local benchmark command for build-time tracking

## Install

```bash
python -m pip install .
```

For development:

```bash
python -m pip install -e ".[dev]"
```

## Quickstart

Inspect the tool's machine-readable contract surface:

```bash
python -m deep_context_federation.cli describe-abilities \
  --format json \
  --output .dcf/deep_context_federation_capabilities.json
```

Export the built-in JSON Schema registry and validate artifact shape before deeper gates:

```bash
python -m deep_context_federation.cli describe-contracts \
  --format json \
  --output .dcf/deep_context_federation_schema_registry.json

python -m deep_context_federation.cli check-artifact \
  --input .dcf/deep_context_federation_bootstrap.json \
  --artifact bootstrap \
  --output .dcf/deep_context_federation_contract_validation.json
```

Inspect how overlapping tools collapse into DCF-native capabilities:

```bash
python -m deep_context_federation.cli plan-capability-ownership \
  --function symbol-call-graph \
  --function surface-map \
  --function long-term-context-memory \
  --format json \
  --output .dcf/deep_context_federation_native_integration_plan.json
```

Build the reusable context index from generated DCF artifacts:

```bash
python -m deep_context_federation.cli reuse-context \
  --input-dir .dcf \
  --format json \
  --output .dcf/deep_context_federation_memory_ledger.json
```

Collapse graph, reusable context, commands, and capability ownership into one DCF function-facet index:

```bash
python -m deep_context_federation.cli unify-context \
  --input .dcf/deep_context_federation_latest.json \
  --reuse-index .dcf/deep_context_federation_memory_ledger.json \
  --ability-registry .dcf/deep_context_federation_capabilities.json \
  --ownership-plan .dcf/deep_context_federation_native_integration_plan.json \
  --format json \
  --output .dcf/deep_context_federation_unified_index.json
```

Self-bootstrap a fresh repository into a verified federation:

```bash
python -m deep_context_federation.cli bootstrap-context \
  --root . \
  --output-dir .dcf \
  --format markdown
```

For a fresh agent or CI run, create the full intake packet in one step:

```bash
python -m deep_context_federation.cli prepare-task-intake \
  --root . \
  --output-dir .dcf \
  --task "dashboard operator evidence authority" \
  --token-budget 4000 \
  --format markdown
```

Plan a run before any agent reads broad context:

```bash
python -m deep_context_federation.cli plan-workflow \
  --root . \
  --output-dir .dcf \
  --task "dashboard operator evidence authority" \
  --target dashboard_readiness_projection \
  --target research_only_boundary \
  --output .dcf/deep_context_federation_workflow_plan.json
```

The plan does not execute commands. It emits the intended run order, stop gates, artifact paths, and token-efficiency guidance so a model can first read a compact plan and then expand only into the bounded `task_brief`, `target_review`, or target resolver artifacts it actually needs.

Execute that read-only DCF chain into a single compact run capsule:

```bash
python -m deep_context_federation.cli run-workflow \
  --root . \
  --output-dir .dcf \
  --task "dashboard operator evidence authority" \
  --target dashboard_readiness_projection \
  --target research_only_boundary \
  --output .dcf/deep_context_federation_workflow_run.json
```

`run-workflow` writes generated DCF artifacts only. It runs intake, contract validation, optional target review, review gate, and priority target resolution, then emits a compact `model_handoff` that tells an agent what to read first and what to skip by default.

Measure the token savings from that run:

```bash
python -m deep_context_federation.cli measure-token-efficiency \
  --input .dcf/deep_context_federation_workflow_run.json \
  --output .dcf/deep_context_federation_efficiency_report.json
```

The report compares the `read_first` and gate-pass artifact sets against available generated baselines such as the full federation JSON. This makes the context reduction measurable instead of merely advisory.

Enforce token-efficiency thresholds before an agent continues:

```bash
python -m deep_context_federation.cli gate-token-efficiency \
  --input .dcf/deep_context_federation_efficiency_report.json \
  --min-read-first-savings-percent 50 \
  --max-read-first-ratio 0.5 \
  --output .dcf/deep_context_federation_efficiency_gate.json
```

Or let DCF create the full continuation decision in one command:

```bash
python -m deep_context_federation.cli decide-continuation \
  --root . \
  --output-dir .dcf \
  --task "dashboard operator evidence authority" \
  --target dashboard_readiness_projection \
  --efficiency-policy examples/efficiency_gate_policy.example.json \
  --output .dcf/deep_context_federation_agent_ci.json
```

`decide-continuation` writes the workflow run, efficiency report, efficiency gate, and final `agent_ci` artifact. External Codex, Claude, AGY, GitHub Actions, or another runner can read only `deep_context_federation_agent_ci.json` first, inspect `decision.action`, then follow `next_reads` instead of loading the full repository or full federation by default.

Materialize that read plan into one bounded model context:

```bash
python -m deep_context_federation.cli pack-task-context-model-context \
  --input .dcf/deep_context_federation_agent_ci.json \
  --mode read-first \
  --token-budget 4000 \
  --max-artifact-tokens 1200 \
  --output .dcf/deep_context_federation_agent_context.json
```

`pack-model-context` consumes the `agent_ci.artifact_read_plan`, embeds selected artifact content under a token budget, records skipped/truncated sections, and emits a single read-only `deep_context_federation_agent_context_v1` bundle for model prompts.

Gate the bounded context before handing it to a model:

```bash
python -m deep_context_federation.cli gate-model-context \
  --input .dcf/deep_context_federation_agent_context.json \
  --policy examples/agent_context_gate_policy.example.json \
  --output .dcf/deep_context_federation_agent_context_gate.json
```

The gate exits with code `2` when required context invariants fail, such as missing artifacts, prompt budget overflow, contract failure, or required schema versions not appearing in the selected context bundle.

Or run the full gated handoff in one command:

```bash
python -m deep_context_federation.cli prepare-model-handoff \
  --root . \
  --output-dir .dcf \
  --task "dashboard operator evidence authority" \
  --target dashboard_readiness_projection \
  --efficiency-policy examples/efficiency_gate_policy.example.json \
  --context-gate-policy examples/agent_context_gate_policy.example.json \
  --output .dcf/deep_context_federation_agent_handoff.json
```

`prepare-model-handoff` writes the underlying `decide-continuation`, `pack-model-context`, `gate-model-context`, `unify-context`, `select-context`, and `prepare-model-handoff-verification` artifacts, then emits one `deep_context_federation_agent_handoff_v1` decision that points to the gated model prompt source. The prompt source is a prompt-only Markdown file, while the full `pack-model-context` JSON remains available as `machine_context_source` for audit/debug reads. The handoff records `model_handoff.selected_context_source`, a compact task-scoped DCF working set that appears in `read_first` without exposing upstream source identities. The full `model_handoff.unified_context_source` remains available as an audit artifact. The handoff includes `read_first_artifacts`, `audit_artifacts`, `token_economics`, and `agent_handoff_verification_summary` so runners can verify hashes and token savings without opening every generated file first.

Global wrappers can route from the current repo state before deciding what to run:

```bash
python -m deep_context_federation.cli route-model-readiness \
  --root . \
  --task "dashboard operator evidence authority"
```

`route-model-readiness` is read-only and does not execute its recommended command. It normalizes discovery into `ready_agent_route`, `needs_agent_handoff`, `needs_task_agent_route`, `needs_bootstrap_agent_route`, `needs_manifest_refresh_agent_route`, or `blocked_agent_route`, then returns `route_steps` and `recommended_next_command`. This gives Codex, Claude, AGY, GitHub runners, or shell wrappers one stable routing contract instead of making each wrapper hard-code DCF status branching.

When a wrapper wants DCF to perform the safe generated-artifact steps and return model input, use:

```bash
python -m deep_context_federation.cli prepare-model-input \
  --root . \
  --task "dashboard operator evidence authority" \
  --format prompt
```

`prepare-model-input` is fail-closed. It emits prompt text only after an existing handoff passes `emit-model-input`, or after a manifest plus task builds a gated handoff that then passes `emit-model-input`. It does not auto-install tools, call external models, mutate source files, or claim project authority.

For global wrappers that should not hard-code a long command line, validate a profile first:

```bash
python -m deep_context_federation.cli onboard-runner \
  --root . \
  --profile-output .dcf/agent_ready_profile.json \
  --task "dashboard operator evidence authority" \
  --target dashboard_readiness_projection \
  --output .dcf/deep_context_federation_agent_onboard.json
```

`onboard-runner` is the one-command path for Codex, Claude, AGY, GitHub runners, or shell wrappers. It generates a profile, validates it, runs the fail-closed `prepare-model-input` path, and returns one machine-readable capsule with `profile_init_summary`, `profile_validation_summary`, `agent_ready_summary`, `model_input_ready`, prompt token counts, and output paths.

When the wrapper wants to split generation and execution into separate audited steps:

```bash
python -m deep_context_federation.cli init-run-profile \
  --root . \
  --output .dcf/agent_ready_profile.json \
  --task "dashboard operator evidence authority" \
  --target dashboard_readiness_projection

python -m deep_context_federation.cli validate-run-profile \
  --profile .dcf/agent_ready_profile.json
```

Then use the same profile as the single entrypoint:

```bash
python -m deep_context_federation.cli prepare-model-input \
  --profile .dcf/agent_ready_profile.json \
  --format prompt
```

The profile schema is still read-only: `authority_effect: none` and `no_apply: true`. `init-run-profile` writes only the generated profile file after input checks pass, then validates it with the same loader used by `prepare-model-input`. Relative paths resolve from the profile file, not from the caller's shell, so Codex, Claude, AGY, GitHub runners, or shell wrappers can share the same machine-readable launch contract without duplicating manifest, policy, target, and token-budget flags. Invalid profiles return `fail_agent_ready` with `action_taken: blocked_by_profile` and emit no prompt.

Fresh `prepare-model-handoff` artifacts include an `input_fingerprint` digest over the manifest and explicitly listed source files. When `prepare-model-input` reuses an existing handoff and can see the current manifest, it compares that digest first; if a manifest-declared source changed, it returns `fail_agent_ready` and emits no prompt.

Use lower-level discovery when a wrapper only needs to probe the repo state:

```bash
python -m deep_context_federation.cli discover-model-readiness \
  --root .
```

`discover-model-readiness` is read-only. It reports whether a repo already has a verified handoff ready for `emit-model-input`, only has a manifest, only has federation artifacts, or is not configured yet. The output includes `recommended_next_command`; `route-model-readiness` wraps that lower-level probe into a stronger global-wrapper contract.

`prepare-model-handoff` writes `deep_context_federation_agent_handoff_verification.json` automatically. Re-run verification explicitly when a handoff or generated prompt may have moved, been copied, or been modified:

```bash
python -m deep_context_federation.cli verify-model-handoff \
  --input .dcf/deep_context_federation_agent_handoff.json
```

`verify-model-handoff` recomputes listed generated-artifact fingerprints, prompt/context token estimates, and token economics. It exits with code `2` if prompt files, context files, hashes, or economics no longer match the handoff.

Emit the model prompt through a fail-closed reader:

```bash
python -m deep_context_federation.cli emit-model-input \
  --input .dcf/deep_context_federation_agent_handoff.json \
  --format prompt
```

`emit-model-input` verifies the handoff first. It prints prompt text only when the handoff, generated artifacts, and token economics pass verification; otherwise it exits with code `2` and emits no prompt in `prompt` mode.

Bootstrap can also merge curated manifests into the same graph:

```bash
python -m deep_context_federation.cli bootstrap-context \
  --root . \
  --output-dir .dcf \
  --manifest team_evidence/deep_context_federation.json \
  --format markdown
```

Then enforce a machine-readable quality policy:

```bash
python -m deep_context_federation.cli gate-quality \
  --input .dcf/deep_context_federation_bootstrap.json \
  --policy .dcf/quality_gate_policy.json \
  --output .dcf/deep_context_federation_quality_gate.json
```

Pack only the relevant context for a model or agent task:

```bash
python -m deep_context_federation.cli pack-task-context \
  --input .dcf/deep_context_federation_latest.json \
  --task "dashboard operator evidence authority" \
  --token-budget 4000 \
  --output .dcf/deep_context_federation_context_pack.json
```

Or generate a full task routing brief before handing work to an agent:

```bash
python -m deep_context_federation.cli brief-task \
  --input .dcf/deep_context_federation_latest.json \
  --read-model .dcf/deep_context_federation_latest.sqlite \
  --task "dashboard operator evidence authority" \
  --token-budget 4000 \
  --output .dcf/deep_context_federation_task_brief.json
```

Run only the repository scan when you want starter source snapshots without the full pipeline:

```bash
python -m deep_context_federation.cli map-repo \
  --root . \
  --output-dir .dcf \
  --write \
  --build \
  --format markdown

python -m deep_context_federation.cli query-context \
  --input .dcf/deep_context_federation_latest.json \
  --preset code-to-authority \
  --format markdown
```

Compose self-scan output with another manifest before building:

```bash
python -m deep_context_federation.cli combine-inputs \
  --manifest .dcf/deep_context_federation.generated.json \
  --manifest examples/deep_context_federation.example.json \
  --output .dcf/deep_context_federation.composed.json \
  --write \
  --format markdown

python -m deep_context_federation.cli assemble-context \
  --manifest .dcf/deep_context_federation.composed.json \
  --root . \
  --output-dir .dcf \
  --write
```

Run the bundled example after installation:

```bash
python -m deep_context_federation.cli validate-inputs \
  --manifest examples/deep_context_federation.example.json

python -m deep_context_federation.cli assemble-context \
  --manifest examples/deep_context_federation.example.json \
  --root examples \
  --output-dir .dcf \
  --write

python -m deep_context_federation.cli verify-context \
  --manifest examples/deep_context_federation.example.json \
  --root examples \
  --input .dcf/deep_context_federation_latest.json

python -m deep_context_federation.cli query-context \
  --input .dcf/deep_context_federation_latest.json \
  --preset claim-lineage \
  --format markdown

python -m deep_context_federation.cli trace-context \
  --input .dcf/deep_context_federation_latest.json \
  --match dashboard \
  --depth 2 \
  --format markdown

python -m deep_context_federation.cli resolve-evidence \
  --input .dcf/deep_context_federation_latest.json \
  --target dashboard_readiness_projection \
  --format markdown

python -m deep_context_federation.cli adjudicate-evidence \
  --input .dcf/deep_context_federation_latest.json \
  --target dashboard_readiness_projection \
  --format markdown

python -m deep_context_federation.cli review-targets \
  --input .dcf/deep_context_federation_latest.json \
  --target dashboard_readiness_projection \
  --target ui/dashboard/app.py \
  --output .dcf/deep_context_federation_target_review.json

python -m deep_context_federation.cli gate-target-review \
  --input .dcf/deep_context_federation_target_review.json \
  --max-no-match 0 \
  --max-priority-score 99 \
  --format markdown

python -m deep_context_federation.cli diagnose-context \
  --input .dcf/deep_context_federation_latest.json \
  --format markdown

python -m deep_context_federation.cli rank-context \
  --input .dcf/deep_context_federation_latest.json \
  --kind entities \
  --format markdown

python -m deep_context_federation.cli query-context-store \
  --read-model .dcf/deep_context_federation_latest.sqlite \
  --preset search \
  --search dashboard \
  --format markdown

python -m deep_context_federation.cli benchmark-context-build \
  --manifest examples/deep_context_federation.example.json \
  --root examples \
  --iterations 5
```

If installed as a package, use `dcf`:

```bash
dcf assemble-context --manifest examples/deep_context_federation.example.json --root examples --output-dir .dcf --write
dcf verify-context --manifest examples/deep_context_federation.example.json --root examples --input .dcf/deep_context_federation_latest.json
dcf query-context --input .dcf/deep_context_federation_latest.json --preset surface-splits --format markdown
dcf trace-context --input .dcf/deep_context_federation_latest.json --match dashboard --depth 2 --format markdown
dcf diagnose-context --input .dcf/deep_context_federation_latest.json --format markdown
dcf rank-context --input .dcf/deep_context_federation_latest.json --kind sources --format markdown
dcf query-context-store --read-model .dcf/deep_context_federation_latest.sqlite --preset source-health
```

From a fresh source checkout without installing first, prefix commands with `PYTHONPATH=src`:

```bash
PYTHONPATH=src python -m deep_context_federation.cli assemble-context \
  --manifest examples/deep_context_federation.example.json \
  --root examples \
  --output-dir .dcf \
  --write
```

## Repo Scan Bootstrap

`dcf map-repo` gives the tool a self-starting path on unfamiliar codebases. It walks the repository with safe default excludes (`.git`, `.venv`, `node_modules`, `output`, `data`, `.codebase-memory`, and generated `.dcf*` folders), then writes:

- `repo_file_inventory.json`: file/path/artifact inventory with surface hints
- `repo_code_symbols.json`: Python AST plus conservative JS/TS symbol map with path and surface links
- `repo_dependency_graph.json`: Python import plus JS/TS import/require dependency graph
- `repo_surface_map.json`: starter surface map with owner placeholders
- `deep_context_federation.generated.json`: manifest that can be fed into `dcf assemble-context`

One command can scan and build:

```bash
dcf map-repo --root . --output-dir .dcf --write --build
```

For backward compatibility, the scanner also writes `repo_python_symbols.json` as an alias of the code-symbol snapshot during the early alpha period.

The scanner is still read-only from an authority perspective: every generated source declares `authority_effect: none` and `no_apply: true`. It does not install external tools, start watchers, modify hooks, or replace project-specific authority manifests. JS/TS extraction is intentionally conservative and dependency-free; projects that need full semantic precision should feed a dedicated parser export into the same DCF manifest.

Every scan summary includes lightweight performance fields such as `duration_seconds`, `files_per_second`, `symbols_per_second`, and `dependency_edges_per_second`. These are meant for CI and agent routing, not for absolute benchmarking.

## Bootstrap Pipeline

`dcf prepare-task-intake` is the highest-level agent workflow. It runs `bootstrap-context`, evaluates `gate-quality`, builds a `task_brief`, and writes one `deep_context_federation_agent_intake.json` packet with all generated output paths and next actions.

`dcf bootstrap-context` is the lower-level federation workflow:

1. run `dcf map-repo` into the output directory
2. optionally compose the generated manifest with one or more curated manifests
3. build the federation JSON, Markdown, and SQLite read model
4. run the verifier
5. run doctor diagnostics
6. write `deep_context_federation_bootstrap.json` and `DEEP_CONTEXT_FEDERATION_BOOTSTRAP.md`

Use `bootstrap-context` when you only need the federation artifact. Use `prepare-task-intake` when a coding agent or CI job needs a single packet with repo state, quality gate, and task routed model context while preserving `authority_effect: none` and `no_apply: true`.

## Workflow Plan

`dcf plan-workflow` is a planning layer for agent orchestration. It returns `deep_context_federation_workflow_plan_v1`, a small JSON artifact that lists:

- ordered DCF commands and their expected output schemas
- deterministic stop gates before wider context expansion
- target review and review gate steps when targets are supplied
- model first reads and context that should be skipped by default
- safety boundaries proving the plan is read-only and does not execute commands

This is the preferred first artifact for token-sensitive agents. It lets Codex, Claude, AGY, GitHub runners, or another orchestrator decide whether to continue from a compact contract rather than loading the full federation, SQLite export, README set, or raw source tree.

## Workflow Run

`dcf run-workflow` is the executable read-only companion to `plan-workflow`. It creates:

- `deep_context_federation_workflow_plan.json`
- `deep_context_federation_agent_intake.json`
- `deep_context_federation_agent_intake_contract_validation.json`
- optional `deep_context_federation_target_review.json`
- optional `deep_context_federation_target_review_gate.json`
- optional `deep_context_federation_priority_resolve.json`
- `deep_context_federation_workflow_run.json`

The run capsule summarizes each step, records pass/fail gates, and gives a compact `model_handoff` with `read_first`, `read_next_if_gate_passes`, and `skip_by_default`. It still preserves `authority_effect: none` and `no_apply: true`; it does not mutate source code, authority, runtime state, broker paths, or promotion surfaces.

## Efficiency Report

`dcf measure-token-efficiency` reads a `workflow_run` artifact and computes:

- token estimates for `read_first`
- token estimates for `read_next_if_gate_passes`
- gate-pass total context size
- full federation or generated-output baseline size
- estimated token savings and compression ratios
- missing required artifacts and recommendations

Use it when you need to prove that DCF is reducing model input cost. It is also read-only and `authority_effect: none`; it measures generated artifacts and does not inspect or mutate source authority.

## Efficiency Gate

`dcf gate-token-efficiency` turns that report into a deterministic pass/fail result. The default policy requires:

- report status is OK
- no missing required artifacts
- no report warnings
- full baseline tokens are available
- `read_first` is at most half of baseline
- `read_first` savings are at least 50 percent
- required artifact roles include `read_first` and `baseline`

Use a policy JSON or CLI overrides when a repo needs stricter context budgets. The gate is designed for CI and agent routing: if it fails, the agent should tighten the workflow handoff before expanding model context.

A starter policy is available at `examples/efficiency_gate_policy.example.json`.

## Continuation Decision

`dcf decide-continuation` is the highest-level machine entrypoint for token-sensitive continuation. It runs:

1. `run-workflow`
2. `measure-token-efficiency`
3. `gate-token-efficiency`

and emits `deep_context_federation_agent_ci_v1` with:

- `decision.action`: `continue`, `continue_with_caution`, or `stop`
- `decision.continue_agent`: boolean continuation gate
- `workflow_run_summary`, `efficiency_report_summary`, and `efficiency_gate_summary`
- `contract_validations`: built-in contract checks for the generated workflow, report, gate, and continuation artifacts
- `next_reads.read_first` and `next_reads.read_next_if_decision_allows`
- `artifact_read_plan`: ordered file refs with existence, schema version, byte size, and estimated tokens
- `safety_boundaries` proving generated-output-only, no external model calls, and no source or authority mutation

This is the preferred artifact for external orchestrators. It reduces model input by making the first read a compact decision artifact, then expanding only into the listed workflow, report, gate, or target evidence files when the decision allows.

## Model Context Pack

`dcf pack-task-context-model-context` is the second-stage context materializer. It reads a completed `agent_ci` artifact and selects artifacts from `artifact_read_plan` by mode:

- `read-first`: only the mandatory first-read set
- `decision-allowed`: first-read plus decision-allowed follow-up artifacts
- `all`: every read-plan row

It emits `deep_context_federation_agent_context_v1` with selected sections, skipped rows, truncation flags, source artifact hashes, prompt text, and token estimates. Use this when the next model call should receive one bounded context object instead of opening several JSON artifacts manually.

## Model Context Gate

`dcf gate-model-context` evaluates that context bundle before model handoff. It checks:

- the context artifact contract and read-only boundary
- source `agent_ci` contract validation
- missing, skipped, and truncated artifact counts
- selected-context tokens and prompt tokens
- prompt and selected content staying within declared budgets
- required schema versions inside the selected sections

Use `examples/agent_context_gate_policy.example.json` as a starter policy. The default gate is permissive about truncation and skipped rows, but strict about missing artifacts, read-only boundaries, source contract validity, and token budget overflow.

## Model Handoff

`dcf prepare-model-handoff` is the highest-level runner entrypoint. It executes:

1. `decide-continuation`
2. `pack-model-context`
3. `gate-model-context`

and emits `deep_context_federation_agent_handoff_v1` with a final `decision`, compact summaries, generated output paths, and `model_handoff.model_prompt_source`. This is the command to use when an external runner wants one deterministic pass/fail handoff instead of orchestrating DCF subcommands itself.

For token efficiency, `model_handoff.model_prompt_source` points at `DEEP_CONTEXT_FEDERATION_AGENT_MODEL_PROMPT.md`, not the full machine JSON. The JSON context is still recorded as `model_handoff.machine_context_source`, so agents can default to the smaller prompt-only surface and open the heavier JSON only when auditing evidence, hashes, or skipped/truncated rows. `model_handoff.selected_context_source` points at `deep_context_federation_selected_context.json`, a compact task-scoped machine working set selected from `model_handoff.unified_context_source`. The full unified index collapses upstream tool/source identities into DCF-owned facets and is kept as audit context, not default model input. `model_handoff.token_economics` records prompt/context/unified-index/selected-context estimated tokens, ratio, and estimated savings; `read_first_artifacts` and `audit_artifacts` record path, bytes, SHA-256, and default-model-input flags.

Run `dcf verify-model-handoff --input <handoff.json>` before giving a copied or externally transferred `model_prompt_source` to a model. The verifier is read-only and emits `deep_context_federation_agent_handoff_verification_v1`; it checks safety boundaries, pass/fail semantics, artifact hashes, prompt/context token estimates, and `token_economics` consistency. Fresh `dcf prepare-model-handoff` runs already include the same verification summary and verification artifact.

For global wrappers, prefer `dcf emit-model-input --input <handoff.json> --format prompt` as the final handoff step. It reruns verification and returns only the prompt body on success, which lets Codex, Claude, AGY, GitHub runners, or shell wrappers consume DCF without reimplementing the verification logic.

Use `dcf route-model-readiness --root <repo> --task '<task>'` as the first global step. If it returns `ready_agent_route`, execute the terminal `emit-model-input` step; if it returns `needs_agent_handoff`, execute the handoff step and then rediscover; if it returns `needs_bootstrap_agent_route`, run the scan/build step first; if it returns `blocked_agent_route` or `needs_task_agent_route`, do not emit model input.

Use `dcf prepare-model-input --root <repo> --task '<task>' --format prompt` when the runner wants one command that can consume an existing safe handoff or build a task handoff from an existing manifest, then emit prompt text only if the final model-input gate passes.

Use `dcf onboard-runner --root <repo> --profile-output <profile.json> --task '<task>' --format json` when the runner wants one onboarding capsule that creates the profile and immediately runs the safe ready path. The result is still read-only with respect to source and authority surfaces; it only writes generated DCF outputs.

Use `dcf init-run-profile --root <repo> --output <profile.json> --task '<task>'` to generate one launch contract, `dcf validate-run-profile --profile <profile.json>` to validate it, and then `dcf prepare-model-input --profile <profile.json> --format prompt` when the runner should consume that contract. Profile fields act as defaults; explicit CLI arguments can still add or override the operational request without changing the profile file.

Reused handoffs are freshness-aware when their original `input_fingerprint` is present. A changed manifest-declared source produces `input_fingerprint_mismatch`, so wrappers do not accidentally feed a model prompt built from stale evidence.

Reused handoffs are also request-bound. If a wrapper supplies a task or targets when reusing a handoff, `prepare-model-input` compares them with the handoff's recorded `task` and `targets`; a mismatch returns `request_binding_mismatch` and emits no prompt.

## Capabilities Manifest

`dcf describe-abilities` is the self-describing entrypoint for agent orchestration. It returns a stable JSON object with:

- command names, intents, output schemas, and write boundaries
- artifact contracts and generated source contracts
- JSON query presets and SQLite query presets
- edge types and local fusion roles
- process exit-code meanings
- explicit safety boundaries such as `authority_effect: none`, `no_apply: true`, no external installer, and generated-output-only writes

Use it before dispatching DCF from CI, AGY, Codex, Claude, GitHub Actions, or another runner:

```bash
dcf describe-abilities \
  --format json \
  --output .dcf/deep_context_federation_capabilities.json
```

The public CLI is intentionally named by the function a runner wants to accomplish: `map-repo`, `assemble-context`, `query-context`, `prove-unified-context`, `select-context`, and `prepare-model-handoff`. Legacy source-shaped or implementation-shaped names remain hidden compatibility aliases only; new machine guidance should use the function names emitted by `describe-abilities`.

## Native Unified Integration

`dcf plan-capability-ownership` is the governance surface for replacing scattered tool identities with DCF-owned capabilities. Use function names such as `symbol-call-graph`, `surface-map`, `long-term-context-memory`, `evidence-lineage`, `operator-projection`, and `workflow-orchestration`; the emitted artifact is DCF-only:

- `public_identity: deep_context_federation`
- `hide_upstream_tool_identity: true`
- `adapter_only_allowed: false`
- `consume_only_allowed: false`
- `user_facing_source_identity_collapsed_to_dcf: true`

This lets DCF absorb symbol graphs, surface maps, long-term memory, evidence lineage, operator projection, and model handoff into one query/index/governance plane. Any upstream provenance is retained only for internal audit and reproducibility, not as a competing source identity for agents or operators.

```bash
dcf plan-capability-ownership --format markdown
dcf check-artifact \
  --input .dcf/deep_context_federation_native_integration_plan.json \
  --artifact native_integration_plan
```

## Reusable Context Index

`dcf reuse-context` is the DCF function for scattered long-term context recall. It reads generated DCF artifacts such as `prepare-model-handoff`, `prepare-model-input`, `onboard-runner`, `run-workflow`, and `input-fingerprint`, then emits one reusable context index:

- `rows`: normalized memory records for generated DCF artifacts
- `reuse_index`: prompt/context entries that are safe to reuse
- `input_fingerprint_digests`: freshness anchors for request-bound reuse
- `safety_boundaries`: confirms no source, authority, external model, watcher, or tool identity mutation

```bash
dcf reuse-context --input-dir .dcf --format markdown
dcf check-artifact \
  --input .dcf/deep_context_federation_memory_ledger.json \
  --artifact memory_ledger
```

The ledger is generated-output-only. It does not crawl the source tree by default, install memory tools, start watchers, or expose an upstream memory provider as a user-facing identity.

## Unified Context Index

`dcf unify-context` is the DCF function for making agents stop jumping across graph rows, reuse rows, command manifests, and capability ownership plans. It emits one source-collapsed function-facet index:

- `surface`, `symbol`, `claim`, `path`, `artifact`, `memory`, `command`, `capability`, and `conflict` rows
- `source_identity_policy` proving `source_ids_exposed: false` and `source_table_exposed: false`
- graph scores, memory reuse rows, functional commands, and native capability ownership in one sorted working set
- optional `--query` filtering without reopening separate source-specific tools

The original artifacts remain the audit location. The unified index is the public DCF audit plane, with `authority_effect: none` and `no_apply: true`. `dcf prepare-model-handoff` builds this index automatically and records it in `model_handoff.unified_context_source`.

```bash
dcf unify-context \
  --input .dcf/deep_context_federation_latest.json \
  --reuse-index .dcf/deep_context_federation_memory_ledger.json \
  --ability-registry .dcf/deep_context_federation_capabilities.json \
  --ownership-plan .dcf/deep_context_federation_native_integration_plan.json \
  --query dashboard \
  --format markdown
```

## Unified Plane Audit

`dcf prove-unified-context` is the machine gate that checks whether DCF is really acting like one integrated tool:

- public command manifest uses function names, not legacy/source names
- ownership plan collapses upstream identity into `deep_context_federation`
- `task_brief` exposes `query_plan` for machine runners
- context index hides source identity and includes command/capability facets
- working set preserves DCF-only identity for model read-first use

By default, `native_partial` capabilities are warnings. Add `--require-all-owned` when using the audit as a stricter CI or final-acceptance gate.

```bash
dcf prove-unified-context \
  --ability-registry .dcf/deep_context_federation_capabilities.json \
  --ownership-plan .dcf/deep_context_federation_native_integration_plan.json \
  --context-index .dcf/deep_context_federation_unified_index.json \
  --working-set .dcf/deep_context_federation_selected_context.json \
  --format markdown
```

## Context Advantage Proof

`dcf prove-context-advantage` is the fail-closed proof surface for the core DCF claim: use DCF as the default model entrypoint because it is both integrated and measurably smaller than scattered context reads.

It consumes existing artifacts only:

- `prove-unified-context`: proves DCF is one function-named, source-collapsed read plane
- `measure-token-efficiency`: measures read-first tokens against full-federation/generated-output baselines
- optional `gate-token-efficiency`: enforces policy thresholds before accepting the proof

The proof requires baseline evidence, read-first context smaller than baseline, a configurable savings threshold, and a passing unified-plane audit. It remains `authority_effect: none` / `no_apply: true`; it does not run tools, mutate files, or call external models.

```bash
dcf prove-context-advantage \
  --unified-plane-audit .dcf/deep_context_federation_unified_plane_audit.json \
  --efficiency-report .dcf/deep_context_federation_efficiency_report.json \
  --efficiency-gate .dcf/deep_context_federation_efficiency_gate.json \
  --min-read-first-savings-percent 50 \
  --max-read-first-ratio 0.5 \
  --format markdown
```

## Selected Context

`dcf select-context` is the optimized model read-first layer on top of `unify-context`. It selects a compact task-scoped working set from the full unified index:

- keeps `source_identity_policy.source_ids_exposed: false`
- truncates long labels/values for predictable token use
- supports `--max-tokens` so the selected JSON is packed to a model budget instead of a fixed row count
- uses balanced facet selection by default, so surfaces, claims, conflicts, symbols, paths, commands, and capabilities do not silently collapse into one high-score row type
- records `optimization_policy.full_index_role: audit_only`
- records `expansion_plan` with `read_full_index_ref`, selected/omitted facet counts, recommended `select-context` argv, and next actions for controlled expansion
- preserves row ids, facets, scores, conflict attention, and command/capability hints

`dcf prepare-model-handoff` runs this automatically and places the result in `model_handoff.selected_context_source`. The full unified index remains in `audit_artifacts`.

```bash
dcf select-context \
  --input .dcf/deep_context_federation_unified_index.json \
  --query "dashboard operator" \
  --limit 24 \
  --max-tokens 900 \
  --facet-mode balanced \
  --min-facets 4 \
  --format markdown
```

Use `--facet-mode ranked` when strict score order is more important than broad system-surface coverage. In balanced mode, `summary.facet_coverage_met` and `selected_context_facet_coverage_below_target` make coverage loss explicit when the token budget is too small. Runners should follow `expansion_plan.recommended_commands` before opening the full context index; `read_full_index_ref` remains audit-only unless the compact working set is insufficient.

## Schema Registry And Contract Validation

`dcf describe-contracts` emits built-in JSON Schema documents for DCF artifacts:

```bash
dcf describe-contracts --format json
dcf describe-contracts --artifact federation --format json
```

`dcf check-artifact` validates an artifact against the built-in top-level contract subset:

```bash
dcf check-artifact \
  --input .dcf/deep_context_federation_latest.json \
  --artifact federation \
  --format markdown
```

This is intentionally a contract-shape gate: it checks schema identity, required top-level fields, `authority_effect: none`, `no_apply: true`, and basic JSON types. Deeper project semantics still belong to `dcf verify-context`, `dcf diagnose-context`, and `dcf gate-quality`.

## Token-Aware Context Packing

`dcf pack-task-context` is the model-efficiency layer. It takes a full federation artifact plus a task string, scores sources/entities/edges/conflicts locally, and emits a bounded context bundle:

```bash
dcf pack-task-context \
  --input .dcf/deep_context_federation_latest.json \
  --task "claim lineage for dashboard readiness" \
  --token-budget 8000 \
  --max-rows 80 \
  --output .dcf/deep_context_federation_context_pack.json
```

The output includes:

- `prompt_text`: a ready-to-send bounded prompt surface for the task
- selected rows with score, matched terms, and estimated token cost
- dropped-row summary with budget or rank reasons
- original estimated tokens, packed estimated tokens, token savings, and compression ratio
- budget utilization and coverage metrics for selected sources, matched task terms, entity types, and conflict severities
- source snapshot and explicit `authority_effect: none` / `no_apply: true`

This is the intended way to reduce model input tokens: run local federation queries and packing first, then feed `prompt_text` to the model instead of the whole repository or full federation JSON. Use `--no-prompt` when an agent only needs the machine-readable scored rows and will render its own prompt.

## Task Brief

`dcf brief-task` is the agent start surface. It consumes a federation artifact plus a task string and emits:

- selected query presets with the terms that triggered them
- compact routed query samples
- doctor status and recommended actions
- machine-readable `query_plan` steps with argv, read roles, stop gates, and optional read-model queries
- embedded `context_pack.prompt_text`
- token budget, compression, coverage, and recommended follow-up commands

Use it when an agent should not decide from scratch whether to run `query-context`, `diagnose-context`, `trace-context`, `pack-task-context`, or `query-context-store`. The brief remains `authority_effect: none` / `no_apply: true`; it routes context and diagnostics only. `query_plan` is execution guidance, not an executor: DCF records the intended `argv`, read role, and expansion policy, while the runner remains responsible for actually running those commands and honoring gates.

## Target Resolve

`dcf resolve-evidence` is the target-level evidence explorer. It takes a specific claim id, path, surface id, symbol, or keyword and emits a compact evidence card:

- matched entities
- neighboring graph edges
- related source rows
- related conflicts
- target-specific prompt text and embedded context pack
- recommended follow-up commands

Use it after `brief-task` when the agent needs to inspect one concrete assertion, file, or surface instead of browsing every preset result. Like the rest of DCF, it is read-only and `authority_effect: none`.

## Target Adjudication

`dcf adjudicate-evidence` builds on `resolve-evidence` and emits a deterministic verdict for one target:

- `supported`: enough authority/evidence support and no risk flags
- `warn`: usable as model context, but with caveats
- `blocked`: error conflict present
- `advisory_only`: only advisory context was found
- `no_match`: no relevant target evidence found

It classifies related sources into authority, evidence, advisory, context, and unavailable buckets, computes a bounded confidence score, and reports whether the result is allowed for model context or requires human review. It never authorizes mutation; `safe_for_mutation` is always false.

## Batch Target Review

`dcf review-targets` runs target adjudication across a portfolio and returns a compact risk ranked table:

- one summary row per target
- verdict counts and risk flag counts
- priority score for governance/agent routing
- recommended next targets
- optional full adjudication payloads with `--include-details`

Targets can be passed repeatedly with `--target` or loaded from `--targets-file` as either a JSON list or newline-delimited text. This is the batch surface for large projects where an agent needs to decide which claims, paths, or surfaces deserve attention first.

`dcf gate-target-review` turns that portfolio into a CI/agent routing gate. It checks policy thresholds such as:

- `max_blocked`
- `max_no_match`
- `max_advisory_only`
- `max_warn`
- `max_priority_score`
- `min_average_confidence`
- disallowed risk flags
- required reviewed targets

Use `gate-quality` to verify federation health; use `gate-target-review` to decide whether a target portfolio is safe enough for agent continuation.

## Quality Gate

`dcf gate-quality` turns a bootstrap or federation artifact into a strict machine-readable pass/fail report. It checks:

- `authority_effect: none` and `no_apply: true`
- quality policy schema, unknown keys, validation errors, and policy authority boundary
- max error/warning counts
- minimum source/entity/edge counts
- required source roles, source ids, and query presets
- bootstrap step health when the input is `deep_context_federation_bootstrap.json`
- optional duration and scan-duration ceilings

The preferred CI shape is policy-as-code. Store the threshold policy in JSON, commit it with the repo that owns the context contract, and pass it with `--policy`:

```json
{
  "schema_version": "deep_context_federation_quality_gate_policy_v1",
  "policy_id": "ci_context_minimum",
  "authority_effect": "none",
  "no_apply": true,
  "min_sources": 5,
  "min_entities": 50,
  "min_edges": 50,
  "max_errors": 0,
  "max_warnings": 0,
  "max_duration_seconds": 10,
  "max_scan_duration_seconds": 10,
  "require_roles": ["project_surface", "evidence_index"],
  "require_sources": ["repo_file_inventory", "repo_code_symbols", "repo_dependency_graph"],
  "require_query_presets": ["surface-splits", "code-to-authority"],
  "require_bootstrap_steps": true
}
```

A starter copy is available at `examples/quality_gate_policy.example.json`.

```bash
dcf gate-quality \
  --input .dcf/deep_context_federation_bootstrap.json \
  --policy .dcf/quality_gate_policy.json \
  --output .dcf/deep_context_federation_quality_gate.json
```

The command exits `0` on pass and `2` on failure. Use `--output` to write stable JSON for CI, GitHub Actions, or another agent. Individual CLI threshold flags can still override policy fields for ad hoc local checks:

```bash
dcf gate-quality \
  --input .dcf/deep_context_federation_bootstrap.json \
  --policy .dcf/quality_gate_policy.json \
  --require-source repo_file_inventory \
  --require-source repo_code_symbols \
  --require-source repo_dependency_graph \
  --require-role project_surface \
  --require-query-preset surface-splits \
  --output .dcf/deep_context_federation_quality_gate.json
```

## Manifest Composition

`dcf combine-inputs` merges multiple federation manifests into one buildable manifest:

```bash
dcf combine-inputs \
  --manifest .dcf/deep_context_federation.generated.json \
  --manifest team_evidence/deep_context_federation.json \
  --output .dcf/deep_context_federation.composed.json \
  --write
```

Identical duplicate `source_id` entries are collapsed. Conflicting duplicate `source_id` entries are kept by deterministically renaming the later source and reporting a warning conflict. Relative source paths are rebased to the composed manifest output directory so the result can be passed directly to `dcf assemble-context`.

## Manifest

The manifest lists JSON sources and their governance role:

```json
{
  "schema_version": "deep_context_federation_manifest_v1",
  "sources": [
    {
      "source_id": "current_truth_snapshot",
      "role": "current_truth",
      "required": true,
      "path": "fixtures/current_truth_snapshot.json",
      "verifier": "scripts/verify_current_truth.py"
    }
  ]
}
```

Paths are resolved relative to the manifest directory first, then relative to `--root`.

## Query Presets

- `surface-splits`: surface ownership and advisory split hints
- `claim-lineage`: claim to authority/evidence/verifier lineage
- `stale-sources`: missing, stale, or unavailable sources
- `code-to-authority`: path and symbol entities joined into the federation
- `r19-context`: text filter for projects that use R19 research lanes
- `operator-projection`: dashboard/operator/governance projection context

## SQLite Read Model

The generated SQLite file is intended for agent and automation use. It contains:

- `sources`
- `entities`
- `edges`
- `conflicts`
- `search_index`

Read-model presets:

- `source-health`
- `stale-sources`
- `claim-lineage`
- `surface-splits`
- `code-to-authority`
- `operator-projection`
- `search`

Example:

```bash
dcf query-context-store --read-model .dcf/deep_context_federation_latest.sqlite --preset search --search governance
```

## Source Quality

Each internal source row includes a `quality` object with a numeric score and reasons. The score penalizes stale inputs, missing required inputs, authority-boundary drift, missing verifiers, and optional unavailable imports. This gives agents an immediate signal about which context is reliable enough to use and which needs refresh or owner review first, while the user-facing identity remains DCF.

## Native Ingestion

The builder recognizes common export shapes:

- `surfaces` or `surface_map.surfaces`: emits `surface_id`, `owner_id`, `path`, and `OWNS` / `DERIVES_FROM` edges.
- `symbols` or `code_map.symbols`: emits `symbol_fqn`, `path`, `surface_id`, and `REFERENCES_SYMBOL` edges.
- `nodes` / `edges` or `graph.nodes` / `graph.edges`: maps generic graph exports into federation entities and edge types.

This is the layer that lets DCF absorb symbol maps, surface maps, evidence/claim reports, and memory-style graph exports into one DCF graph without letting any upstream identity become a competing user-facing authority.

## Graph Trace

Use `trace-context` to start from any matching entity and expand through federation edges:

```bash
dcf trace-context --input .dcf/deep_context_federation_latest.json --match dashboard --depth 2 --format markdown
```

The output is useful for "code-to-authority" and "claim-to-evidence" exploration because it traverses the unified entity graph rather than one source's private graph.

## Ranking And Doctor

`rank-context` turns the federation into a prioritization surface:

```bash
dcf rank-context --input .dcf/deep_context_federation_latest.json --kind entities --limit 20
dcf rank-context --input .dcf/deep_context_federation_latest.json --kind sources --limit 20
```

Entity ranking combines graph degree, semantic edge weights, source quality, and entity type. Source ranking highlights risky sources by combining quality score, required status, and conflict counts.

`diagnose-context` gives a compact health verdict:

```bash
dcf diagnose-context --input .dcf/deep_context_federation_latest.json --format markdown
```

It checks hard conflicts, missing required sources, stale sources, low-quality sources, graph connectivity, and unresolved warnings. The output includes recommended actions for automation or human review.

## Federation Diff

Compare two builds:

```bash
dcf diff-context --before old.json --after new.json --format markdown
```

The diff reports source changes, entity/edge additions and removals, conflict changes, and summary deltas. This helps track whether governance work is reducing fragmentation or simply moving it around.

## Incremental Cache

`dcf assemble-context --write` writes `.dcf/source_fingerprints.json`. The next run reports changed, unchanged, new, and removed sources under `incremental_cache`. This does not change authority semantics; it gives automation a cheap signal for whether an expensive context refresh is actually needed.

## Benchmarking

Use `benchmark-context-build` to track local build performance:

```bash
dcf benchmark-context-build --manifest examples/deep_context_federation.example.json --root examples --iterations 20 --json
```

## Optional Memory Import

The optional memory import path is disabled by default. When enabled, DCF only checks for a safe external cache configuration and collapses imported memory observations into DCF-native records. It does not install, index, watch, mutate agent configuration, or expose the memory tool as a separate user-facing identity.

Safe mode requires:

- `--include-memory-import`
- `--memory-import-cache-dir` or `CBM_CACHE_DIR`
- cache directory outside the repository
- no tracked `.codebase-memory/graph.db.zst`

## Output

`dcf assemble-context --write` emits:

- `.dcf/deep_context_federation_latest.json`
- `.dcf/DEEP_CONTEXT_FEDERATION_LATEST.md`
- `.dcf/deep_context_federation_latest.sqlite`

## Tests

```bash
python -m pytest -q
```

## License

MIT
