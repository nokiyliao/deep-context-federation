# Deep Context Federation

Deep Context Federation is a small, read-only aggregation layer for large codebases and agent workflows.

It joins local context surfaces such as:

- project truth snapshots
- evidence and receipt indexes
- operator or governance projections
- advisory source maps
- code graph or memory adapters

The output is a machine-readable federation graph of sources, entities, edges, conflicts, local "Codex Fusion" synthesis roles, and a SQLite read model. It is designed to help humans and coding agents ask, "Which surface says this, what evidence supports it, and is this source stale or advisory?"

## Why It Exists

Most code-intelligence tools optimize one lane:

- symbol graph navigation
- repository surface maps
- long-term code memory
- evidence receipt indexing
- dashboard/operator projection

Deep Context Federation is the integration layer across those lanes. It does not try to be the best symbol parser or the best long-term memory store. It makes those tools safer and more useful together by enforcing a common read-only boundary, ranking source health, joining claims to evidence, and exposing stale or conflicting context before agents act on it.

## Boundary

This tool is deliberately non-authoritative:

- `authority_effect: none`
- `no_apply: true`
- no live/runtime/broker/promotion mutation
- no task ledger replacement
- no external model calls
- no automatic installer or watcher for optional tools

It does not decide production truth. It only projects and checks consistency across existing truth surfaces.

## Integrated Capabilities

Deep Context Federation now combines several capabilities that are usually split across separate tools:

- generic JSON federation for arbitrary governance artifacts
- self-bootstrap repo scan that emits starter inventory, surface, code-symbol, and dependency-graph sources
- typed adapters for surface maps, symbol maps, and graph exports
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
- agent CI continuation decision that chains workflow run, efficiency report, and efficiency gate into one read-first artifact
- agent context bundle that materializes selected `agent-ci` read-plan artifacts into one bounded prompt/context payload
- agent context gate that enforces token, missing-artifact, truncation, and schema thresholds before model handoff
- agent handoff command that runs the CI decision, bounded context bundle, and context gate in one pipeline
- agent route command that normalizes discovery into a stable global-wrapper route decision
- agent ready command that turns a safe handoff or manifest+task into verified model prompt input
- agent profile contract that lets global wrappers drive `agent-ready` from one validated JSON file
- agent profile init command that generates that wrapper profile from repo-local manifest and policy paths
- agent onboard command that generates the profile and runs the fail-closed ready path in one global-wrapper capsule
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
python -m deep_context_federation.cli capabilities \
  --format json \
  --output .dcf/deep_context_federation_capabilities.json
```

Export the built-in JSON Schema registry and validate artifact shape before deeper gates:

```bash
python -m deep_context_federation.cli schema \
  --format json \
  --output .dcf/deep_context_federation_schema_registry.json

python -m deep_context_federation.cli validate-artifact \
  --input .dcf/deep_context_federation_bootstrap.json \
  --artifact bootstrap \
  --output .dcf/deep_context_federation_contract_validation.json
```

Self-bootstrap a fresh repository into a verified federation:

```bash
python -m deep_context_federation.cli bootstrap \
  --root . \
  --output-dir .dcf \
  --format markdown
```

For a fresh agent or CI run, create the full intake packet in one step:

```bash
python -m deep_context_federation.cli intake \
  --root . \
  --output-dir .dcf \
  --task "dashboard operator evidence authority" \
  --token-budget 4000 \
  --format markdown
```

Plan a run before any agent reads broad context:

```bash
python -m deep_context_federation.cli workflow-plan \
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
python -m deep_context_federation.cli workflow-run \
  --root . \
  --output-dir .dcf \
  --task "dashboard operator evidence authority" \
  --target dashboard_readiness_projection \
  --target research_only_boundary \
  --output .dcf/deep_context_federation_workflow_run.json
```

`workflow-run` writes generated DCF artifacts only. It runs intake, contract validation, optional target review, review gate, and priority target resolution, then emits a compact `model_handoff` that tells an agent what to read first and what to skip by default.

Measure the token savings from that run:

```bash
python -m deep_context_federation.cli efficiency-report \
  --input .dcf/deep_context_federation_workflow_run.json \
  --output .dcf/deep_context_federation_efficiency_report.json
```

The report compares the `read_first` and gate-pass artifact sets against available generated baselines such as the full federation JSON. This makes the context reduction measurable instead of merely advisory.

Enforce token-efficiency thresholds before an agent continues:

```bash
python -m deep_context_federation.cli efficiency-gate \
  --input .dcf/deep_context_federation_efficiency_report.json \
  --min-read-first-savings-percent 50 \
  --max-read-first-ratio 0.5 \
  --output .dcf/deep_context_federation_efficiency_gate.json
```

Or let DCF create the full continuation decision in one command:

```bash
python -m deep_context_federation.cli agent-ci \
  --root . \
  --output-dir .dcf \
  --task "dashboard operator evidence authority" \
  --target dashboard_readiness_projection \
  --efficiency-policy examples/efficiency_gate_policy.example.json \
  --output .dcf/deep_context_federation_agent_ci.json
```

`agent-ci` writes the workflow run, efficiency report, efficiency gate, and final `agent_ci` artifact. External Codex, Claude, AGY, GitHub Actions, or another runner can read only `deep_context_federation_agent_ci.json` first, inspect `decision.action`, then follow `next_reads` instead of loading the full repository or full federation by default.

Materialize that read plan into one bounded model context:

```bash
python -m deep_context_federation.cli agent-context \
  --input .dcf/deep_context_federation_agent_ci.json \
  --mode read-first \
  --token-budget 4000 \
  --max-artifact-tokens 1200 \
  --output .dcf/deep_context_federation_agent_context.json
```

`agent-context` consumes the `agent_ci.artifact_read_plan`, embeds selected artifact content under a token budget, records skipped/truncated sections, and emits a single read-only `deep_context_federation_agent_context_v1` bundle for model prompts.

Gate the bounded context before handing it to a model:

```bash
python -m deep_context_federation.cli agent-context-gate \
  --input .dcf/deep_context_federation_agent_context.json \
  --policy examples/agent_context_gate_policy.example.json \
  --output .dcf/deep_context_federation_agent_context_gate.json
```

The gate exits with code `2` when required context invariants fail, such as missing artifacts, prompt budget overflow, contract failure, or required schema versions not appearing in the selected context bundle.

Or run the full gated handoff in one command:

```bash
python -m deep_context_federation.cli agent-handoff \
  --root . \
  --output-dir .dcf \
  --task "dashboard operator evidence authority" \
  --target dashboard_readiness_projection \
  --efficiency-policy examples/efficiency_gate_policy.example.json \
  --context-gate-policy examples/agent_context_gate_policy.example.json \
  --output .dcf/deep_context_federation_agent_handoff.json
```

`agent-handoff` writes the underlying `agent-ci`, `agent-context`, `agent-context-gate`, and `agent-handoff-verification` artifacts, then emits one `deep_context_federation_agent_handoff_v1` decision that points to the gated model prompt source. The prompt source is a prompt-only Markdown file, while the full `agent-context` JSON remains available as `machine_context_source` for audit/debug reads. The handoff also includes `read_first_artifacts`, `audit_artifacts`, `token_economics`, and `agent_handoff_verification_summary` so runners can verify hashes and token savings without opening every generated file first.

Global wrappers can route from the current repo state before deciding what to run:

```bash
python -m deep_context_federation.cli agent-route \
  --root . \
  --task "dashboard operator evidence authority"
```

`agent-route` is read-only and does not execute its recommended command. It normalizes discovery into `ready_agent_route`, `needs_agent_handoff`, `needs_task_agent_route`, `needs_bootstrap_agent_route`, `needs_manifest_refresh_agent_route`, or `blocked_agent_route`, then returns `route_steps` and `recommended_next_command`. This gives Codex, Claude, AGY, GitHub runners, or shell wrappers one stable routing contract instead of making each wrapper hard-code DCF status branching.

When a wrapper wants DCF to perform the safe generated-artifact steps and return model input, use:

```bash
python -m deep_context_federation.cli agent-ready \
  --root . \
  --task "dashboard operator evidence authority" \
  --format prompt
```

`agent-ready` is fail-closed. It emits prompt text only after an existing handoff passes `agent-model-input`, or after a manifest plus task builds a gated handoff that then passes `agent-model-input`. It does not auto-install tools, call external models, mutate source files, or claim project authority.

For global wrappers that should not hard-code a long command line, validate a profile first:

```bash
python -m deep_context_federation.cli agent-onboard \
  --root . \
  --profile-output .dcf/agent_ready_profile.json \
  --task "dashboard operator evidence authority" \
  --target dashboard_readiness_projection \
  --output .dcf/deep_context_federation_agent_onboard.json
```

`agent-onboard` is the one-command path for Codex, Claude, AGY, GitHub runners, or shell wrappers. It generates a profile, validates it, runs the fail-closed `agent-ready` path, and returns one machine-readable capsule with `profile_init_summary`, `profile_validation_summary`, `agent_ready_summary`, `model_input_ready`, prompt token counts, and output paths.

When the wrapper wants to split generation and execution into separate audited steps:

```bash
python -m deep_context_federation.cli agent-profile-init \
  --root . \
  --output .dcf/agent_ready_profile.json \
  --task "dashboard operator evidence authority" \
  --target dashboard_readiness_projection

python -m deep_context_federation.cli agent-profile \
  --profile .dcf/agent_ready_profile.json
```

Then use the same profile as the single entrypoint:

```bash
python -m deep_context_federation.cli agent-ready \
  --profile .dcf/agent_ready_profile.json \
  --format prompt
```

The profile schema is still read-only: `authority_effect: none` and `no_apply: true`. `agent-profile-init` writes only the generated profile file after input checks pass, then validates it with the same loader used by `agent-ready`. Relative paths resolve from the profile file, not from the caller's shell, so Codex, Claude, AGY, GitHub runners, or shell wrappers can share the same machine-readable launch contract without duplicating manifest, policy, target, and token-budget flags. Invalid profiles return `fail_agent_ready` with `action_taken: blocked_by_profile` and emit no prompt.

Fresh `agent-handoff` artifacts include an `input_fingerprint` digest over the manifest and explicitly listed source files. When `agent-ready` reuses an existing handoff and can see the current manifest, it compares that digest first; if a manifest-declared source changed, it returns `fail_agent_ready` and emits no prompt.

Use lower-level discovery when a wrapper only needs to probe the repo state:

```bash
python -m deep_context_federation.cli agent-discover \
  --root .
```

`agent-discover` is read-only. It reports whether a repo already has a verified handoff ready for `agent-model-input`, only has a manifest, only has federation artifacts, or is not configured yet. The output includes `recommended_next_command`; `agent-route` wraps that lower-level probe into a stronger global-wrapper contract.

`agent-handoff` writes `deep_context_federation_agent_handoff_verification.json` automatically. Re-run verification explicitly when a handoff or generated prompt may have moved, been copied, or been modified:

```bash
python -m deep_context_federation.cli verify-handoff \
  --input .dcf/deep_context_federation_agent_handoff.json
```

`verify-handoff` recomputes listed generated-artifact fingerprints, prompt/context token estimates, and token economics. It exits with code `2` if prompt files, context files, hashes, or economics no longer match the handoff.

Emit the model prompt through a fail-closed reader:

```bash
python -m deep_context_federation.cli agent-model-input \
  --input .dcf/deep_context_federation_agent_handoff.json \
  --format prompt
```

`agent-model-input` verifies the handoff first. It prints prompt text only when the handoff, generated artifacts, and token economics pass verification; otherwise it exits with code `2` and emits no prompt in `prompt` mode.

Bootstrap can also merge curated manifests into the same graph:

```bash
python -m deep_context_federation.cli bootstrap \
  --root . \
  --output-dir .dcf \
  --manifest team_evidence/deep_context_federation.json \
  --format markdown
```

Then enforce a machine-readable quality policy:

```bash
python -m deep_context_federation.cli quality-gate \
  --input .dcf/deep_context_federation_bootstrap.json \
  --policy .dcf/quality_gate_policy.json \
  --output .dcf/deep_context_federation_quality_gate.json
```

Pack only the relevant context for a model or agent task:

```bash
python -m deep_context_federation.cli pack \
  --input .dcf/deep_context_federation_latest.json \
  --task "dashboard operator evidence authority" \
  --token-budget 4000 \
  --output .dcf/deep_context_federation_context_pack.json
```

Or generate a full task routing brief before handing work to an agent:

```bash
python -m deep_context_federation.cli brief \
  --input .dcf/deep_context_federation_latest.json \
  --task "dashboard operator evidence authority" \
  --token-budget 4000 \
  --output .dcf/deep_context_federation_task_brief.json
```

Run only the repository scan when you want starter source snapshots without the full pipeline:

```bash
python -m deep_context_federation.cli scan \
  --root . \
  --output-dir .dcf \
  --write \
  --build \
  --format markdown

python -m deep_context_federation.cli query \
  --input .dcf/deep_context_federation_latest.json \
  --preset code-to-authority \
  --format markdown
```

Compose self-scan output with another manifest before building:

```bash
python -m deep_context_federation.cli compose-manifest \
  --manifest .dcf/deep_context_federation.generated.json \
  --manifest examples/deep_context_federation.example.json \
  --output .dcf/deep_context_federation.composed.json \
  --write \
  --format markdown

python -m deep_context_federation.cli build \
  --manifest .dcf/deep_context_federation.composed.json \
  --root . \
  --output-dir .dcf \
  --write
```

Run the bundled example after installation:

```bash
python -m deep_context_federation.cli validate-manifest \
  --manifest examples/deep_context_federation.example.json

python -m deep_context_federation.cli build \
  --manifest examples/deep_context_federation.example.json \
  --root examples \
  --output-dir .dcf \
  --write

python -m deep_context_federation.cli verify \
  --manifest examples/deep_context_federation.example.json \
  --root examples \
  --input .dcf/deep_context_federation_latest.json

python -m deep_context_federation.cli query \
  --input .dcf/deep_context_federation_latest.json \
  --preset claim-lineage \
  --format markdown

python -m deep_context_federation.cli trace \
  --input .dcf/deep_context_federation_latest.json \
  --match dashboard \
  --depth 2 \
  --format markdown

python -m deep_context_federation.cli resolve \
  --input .dcf/deep_context_federation_latest.json \
  --target dashboard_readiness_projection \
  --format markdown

python -m deep_context_federation.cli adjudicate \
  --input .dcf/deep_context_federation_latest.json \
  --target dashboard_readiness_projection \
  --format markdown

python -m deep_context_federation.cli review-targets \
  --input .dcf/deep_context_federation_latest.json \
  --target dashboard_readiness_projection \
  --target ui/dashboard/app.py \
  --output .dcf/deep_context_federation_target_review.json

python -m deep_context_federation.cli review-gate \
  --input .dcf/deep_context_federation_target_review.json \
  --max-no-match 0 \
  --max-priority-score 99 \
  --format markdown

python -m deep_context_federation.cli doctor \
  --input .dcf/deep_context_federation_latest.json \
  --format markdown

python -m deep_context_federation.cli rank \
  --input .dcf/deep_context_federation_latest.json \
  --kind entities \
  --format markdown

python -m deep_context_federation.cli sql \
  --sqlite .dcf/deep_context_federation_latest.sqlite \
  --preset search \
  --search dashboard \
  --format markdown

python -m deep_context_federation.cli bench \
  --manifest examples/deep_context_federation.example.json \
  --root examples \
  --iterations 5
```

If installed as a package, use `dcf`:

```bash
dcf build --manifest examples/deep_context_federation.example.json --root examples --output-dir .dcf --write
dcf verify --manifest examples/deep_context_federation.example.json --root examples --input .dcf/deep_context_federation_latest.json
dcf query --input .dcf/deep_context_federation_latest.json --preset surface-splits --format markdown
dcf trace --input .dcf/deep_context_federation_latest.json --match dashboard --depth 2 --format markdown
dcf doctor --input .dcf/deep_context_federation_latest.json --format markdown
dcf rank --input .dcf/deep_context_federation_latest.json --kind sources --format markdown
dcf sql --sqlite .dcf/deep_context_federation_latest.sqlite --preset source-health
```

From a fresh source checkout without installing first, prefix commands with `PYTHONPATH=src`:

```bash
PYTHONPATH=src python -m deep_context_federation.cli build \
  --manifest examples/deep_context_federation.example.json \
  --root examples \
  --output-dir .dcf \
  --write
```

## Repo Scan Bootstrap

`dcf scan` gives the tool a self-starting path on unfamiliar codebases. It walks the repository with safe default excludes (`.git`, `.venv`, `node_modules`, `output`, `data`, `.codebase-memory`, and generated `.dcf*` folders), then writes:

- `repo_file_inventory.json`: file/path/artifact inventory with surface hints
- `repo_code_symbols.json`: Python AST plus conservative JS/TS symbol map with path and surface links
- `repo_dependency_graph.json`: Python import plus JS/TS import/require dependency graph
- `repo_surface_map.json`: starter surface map with owner placeholders
- `deep_context_federation.generated.json`: manifest that can be fed into `dcf build`

One command can scan and build:

```bash
dcf scan --root . --output-dir .dcf --write --build
```

For backward compatibility, the scanner also writes `repo_python_symbols.json` as an alias of the code-symbol snapshot during the early alpha period.

The scanner is still read-only from an authority perspective: every generated source declares `authority_effect: none` and `no_apply: true`. It does not install external tools, start watchers, modify hooks, or replace project-specific authority manifests. JS/TS extraction is intentionally conservative and dependency-free; projects that need full semantic precision should feed a dedicated parser or codegraph export into the same federation manifest.

Every scan summary includes lightweight performance fields such as `duration_seconds`, `files_per_second`, `symbols_per_second`, and `dependency_edges_per_second`. These are meant for CI and agent routing, not for absolute benchmarking.

## Bootstrap Pipeline

`dcf intake` is the highest-level agent workflow. It runs `bootstrap`, evaluates `quality-gate`, builds a `task_brief`, and writes one `deep_context_federation_agent_intake.json` packet with all generated output paths and next actions.

`dcf bootstrap` is the lower-level federation workflow:

1. run `dcf scan` into the output directory
2. optionally compose the generated manifest with one or more curated manifests
3. build the federation JSON, Markdown, and SQLite read model
4. run the verifier
5. run doctor diagnostics
6. write `deep_context_federation_bootstrap.json` and `DEEP_CONTEXT_FEDERATION_BOOTSTRAP.md`

Use `bootstrap` when you only need the federation artifact. Use `intake` when a coding agent or CI job needs a single packet with repo state, quality gate, and task routed model context while preserving `authority_effect: none` and `no_apply: true`.

## Workflow Plan

`dcf workflow-plan` is a planning layer for agent orchestration. It returns `deep_context_federation_workflow_plan_v1`, a small JSON artifact that lists:

- ordered DCF commands and their expected output schemas
- deterministic stop gates before wider context expansion
- target review and review gate steps when targets are supplied
- model first reads and context that should be skipped by default
- safety boundaries proving the plan is read-only and does not execute commands

This is the preferred first artifact for token-sensitive agents. It lets Codex, Claude, AGY, GitHub runners, or another orchestrator decide whether to continue from a compact contract rather than loading the full federation, SQLite export, README set, or raw source tree.

## Workflow Run

`dcf workflow-run` is the executable read-only companion to `workflow-plan`. It creates:

- `deep_context_federation_workflow_plan.json`
- `deep_context_federation_agent_intake.json`
- `deep_context_federation_agent_intake_contract_validation.json`
- optional `deep_context_federation_target_review.json`
- optional `deep_context_federation_target_review_gate.json`
- optional `deep_context_federation_priority_resolve.json`
- `deep_context_federation_workflow_run.json`

The run capsule summarizes each step, records pass/fail gates, and gives a compact `model_handoff` with `read_first`, `read_next_if_gate_passes`, and `skip_by_default`. It still preserves `authority_effect: none` and `no_apply: true`; it does not mutate source code, authority, runtime state, broker paths, or promotion surfaces.

## Efficiency Report

`dcf efficiency-report` reads a `workflow_run` artifact and computes:

- token estimates for `read_first`
- token estimates for `read_next_if_gate_passes`
- gate-pass total context size
- full federation or generated-output baseline size
- estimated token savings and compression ratios
- missing required artifacts and recommendations

Use it when you need to prove that DCF is reducing model input cost. It is also read-only and `authority_effect: none`; it measures generated artifacts and does not inspect or mutate source authority.

## Efficiency Gate

`dcf efficiency-gate` turns that report into a deterministic pass/fail result. The default policy requires:

- report status is OK
- no missing required artifacts
- no report warnings
- full baseline tokens are available
- `read_first` is at most half of baseline
- `read_first` savings are at least 50 percent
- required artifact roles include `read_first` and `baseline`

Use a policy JSON or CLI overrides when a repo needs stricter context budgets. The gate is designed for CI and agent routing: if it fails, the agent should tighten the workflow handoff before expanding model context.

A starter policy is available at `examples/efficiency_gate_policy.example.json`.

## Agent CI

`dcf agent-ci` is the highest-level machine entrypoint for token-sensitive agent continuation. It runs:

1. `workflow-run`
2. `efficiency-report`
3. `efficiency-gate`

and emits `deep_context_federation_agent_ci_v1` with:

- `decision.action`: `continue`, `continue_with_caution`, or `stop`
- `decision.continue_agent`: boolean continuation gate
- `workflow_run_summary`, `efficiency_report_summary`, and `efficiency_gate_summary`
- `contract_validations`: built-in contract checks for the generated workflow, report, gate, and agent CI artifacts
- `next_reads.read_first` and `next_reads.read_next_if_decision_allows`
- `artifact_read_plan`: ordered file refs with existence, schema version, byte size, and estimated tokens
- `safety_boundaries` proving generated-output-only, no external model calls, and no source or authority mutation

This is the preferred artifact for external orchestrators. It reduces model input by making the first read a compact decision artifact, then expanding only into the listed workflow, report, gate, or target evidence files when the decision allows.

## Agent Context

`dcf agent-context` is the second-stage context materializer. It reads a completed `agent_ci` artifact and selects artifacts from `artifact_read_plan` by mode:

- `read-first`: only the mandatory first-read set
- `decision-allowed`: first-read plus decision-allowed follow-up artifacts
- `all`: every read-plan row

It emits `deep_context_federation_agent_context_v1` with selected sections, skipped rows, truncation flags, source artifact hashes, prompt text, and token estimates. Use this when the next model call should receive one bounded context object instead of opening several JSON artifacts manually.

## Agent Context Gate

`dcf agent-context-gate` evaluates that context bundle before model handoff. It checks:

- the context artifact contract and read-only boundary
- source `agent_ci` contract validation
- missing, skipped, and truncated artifact counts
- selected-context tokens and prompt tokens
- prompt and selected content staying within declared budgets
- required schema versions inside the selected sections

Use `examples/agent_context_gate_policy.example.json` as a starter policy. The default gate is permissive about truncation and skipped rows, but strict about missing artifacts, read-only boundaries, source contract validity, and token budget overflow.

## Agent Handoff

`dcf agent-handoff` is the highest-level runner entrypoint. It executes:

1. `agent-ci`
2. `agent-context`
3. `agent-context-gate`

and emits `deep_context_federation_agent_handoff_v1` with a final `decision`, compact summaries, generated output paths, and `model_handoff.model_prompt_source`. This is the command to use when an external runner wants one deterministic pass/fail handoff instead of orchestrating DCF subcommands itself.

For token efficiency, `model_handoff.model_prompt_source` points at `DEEP_CONTEXT_FEDERATION_AGENT_MODEL_PROMPT.md`, not the full machine JSON. The JSON context is still recorded as `model_handoff.machine_context_source`, so agents can default to the smaller prompt-only surface and open the heavier JSON only when auditing evidence, hashes, or skipped/truncated rows. `model_handoff.token_economics` records prompt/context estimated tokens, ratio, and estimated savings; `read_first_artifacts` and `audit_artifacts` record path, bytes, SHA-256, and default-model-input flags.

Run `dcf verify-handoff --input <handoff.json>` before giving a copied or externally transferred `model_prompt_source` to a model. The verifier is read-only and emits `deep_context_federation_agent_handoff_verification_v1`; it checks safety boundaries, pass/fail semantics, artifact hashes, prompt/context token estimates, and `token_economics` consistency. Fresh `dcf agent-handoff` runs already include the same verification summary and verification artifact.

For global wrappers, prefer `dcf agent-model-input --input <handoff.json> --format prompt` as the final handoff step. It reruns verification and returns only the prompt body on success, which lets Codex, Claude, AGY, GitHub runners, or shell wrappers consume DCF without reimplementing the verification logic.

Use `dcf agent-route --root <repo> --task '<task>'` as the first global step. If it returns `ready_agent_route`, execute the terminal `agent-model-input` step; if it returns `needs_agent_handoff`, execute the handoff step and then rediscover; if it returns `needs_bootstrap_agent_route`, run the scan/build step first; if it returns `blocked_agent_route` or `needs_task_agent_route`, do not emit model input.

Use `dcf agent-ready --root <repo> --task '<task>' --format prompt` when the runner wants one command that can consume an existing safe handoff or build a task handoff from an existing manifest, then emit prompt text only if the final model-input gate passes.

Use `dcf agent-onboard --root <repo> --profile-output <profile.json> --task '<task>' --format json` when the runner wants one onboarding capsule that creates the profile and immediately runs the safe ready path. The result is still read-only with respect to source and authority surfaces; it only writes generated DCF outputs.

Use `dcf agent-profile-init --root <repo> --output <profile.json> --task '<task>'` to generate one launch contract, `dcf agent-profile --profile <profile.json>` to validate it, and then `dcf agent-ready --profile <profile.json> --format prompt` when the runner should consume that contract. Profile fields act as defaults; explicit CLI arguments can still add or override the operational request without changing the profile file.

Reused handoffs are freshness-aware when their original `input_fingerprint` is present. A changed manifest-declared source produces `input_fingerprint_mismatch`, so wrappers do not accidentally feed a model prompt built from stale evidence.

Reused handoffs are also request-bound. If a wrapper supplies a task or targets when reusing a handoff, `agent-ready` compares them with the handoff's recorded `task` and `targets`; a mismatch returns `request_binding_mismatch` and emits no prompt.

## Capabilities Manifest

`dcf capabilities` is the self-describing entrypoint for agent orchestration. It returns a stable JSON object with:

- command names, intents, output schemas, and write boundaries
- artifact contracts and generated source contracts
- JSON query presets and SQLite query presets
- edge types and local fusion roles
- process exit-code meanings
- explicit safety boundaries such as `authority_effect: none`, `no_apply: true`, no external installer, and generated-output-only writes

Use it before dispatching DCF from CI, AGY, Codex, Claude, GitHub Actions, or another runner:

```bash
dcf capabilities \
  --format json \
  --output .dcf/deep_context_federation_capabilities.json
```

## Schema Registry And Contract Validation

`dcf schema` emits built-in JSON Schema documents for DCF artifacts:

```bash
dcf schema --format json
dcf schema --artifact federation --format json
```

`dcf validate-artifact` validates an artifact against the built-in top-level contract subset:

```bash
dcf validate-artifact \
  --input .dcf/deep_context_federation_latest.json \
  --artifact federation \
  --format markdown
```

This is intentionally a contract-shape gate: it checks schema identity, required top-level fields, `authority_effect: none`, `no_apply: true`, and basic JSON types. Deeper project semantics still belong to `dcf verify`, `dcf doctor`, and `dcf quality-gate`.

## Token-Aware Context Packing

`dcf pack` is the model-efficiency layer. It takes a full federation artifact plus a task string, scores sources/entities/edges/conflicts locally, and emits a bounded context bundle:

```bash
dcf pack \
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

`dcf brief` is the agent start surface. It consumes a federation artifact plus a task string and emits:

- selected query presets with the terms that triggered them
- compact routed query samples
- doctor status and recommended actions
- embedded `context_pack.prompt_text`
- token budget, compression, coverage, and recommended follow-up commands

Use it when an agent should not decide from scratch whether to run `query`, `doctor`, `trace`, or `pack`. The brief remains `authority_effect: none` / `no_apply: true`; it routes context and diagnostics only.

## Target Resolve

`dcf resolve` is the target-level evidence explorer. It takes a specific claim id, path, surface id, symbol, or keyword and emits a compact evidence card:

- matched entities
- neighboring graph edges
- related source rows
- related conflicts
- target-specific prompt text and embedded context pack
- recommended follow-up commands

Use it after `brief` when the agent needs to inspect one concrete assertion, file, or surface instead of browsing every preset result. Like the rest of DCF, it is read-only and `authority_effect: none`.

## Target Adjudication

`dcf adjudicate` builds on `resolve` and emits a deterministic verdict for one target:

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

`dcf review-gate` turns that portfolio into a CI/agent routing gate. It checks policy thresholds such as:

- `max_blocked`
- `max_no_match`
- `max_advisory_only`
- `max_warn`
- `max_priority_score`
- `min_average_confidence`
- disallowed risk flags
- required reviewed targets

Use `quality-gate` to verify federation health; use `review-gate` to decide whether a target portfolio is safe enough for agent continuation.

## Quality Gate

`dcf quality-gate` turns a bootstrap or federation artifact into a strict machine-readable pass/fail report. It checks:

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
dcf quality-gate \
  --input .dcf/deep_context_federation_bootstrap.json \
  --policy .dcf/quality_gate_policy.json \
  --output .dcf/deep_context_federation_quality_gate.json
```

The command exits `0` on pass and `2` on failure. Use `--output` to write stable JSON for CI, GitHub Actions, or another agent. Individual CLI threshold flags can still override policy fields for ad hoc local checks:

```bash
dcf quality-gate \
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

`dcf compose-manifest` merges multiple federation manifests into one buildable manifest:

```bash
dcf compose-manifest \
  --manifest .dcf/deep_context_federation.generated.json \
  --manifest team_evidence/deep_context_federation.json \
  --output .dcf/deep_context_federation.composed.json \
  --write
```

Identical duplicate `source_id` entries are collapsed. Conflicting duplicate `source_id` entries are kept by deterministically renaming the later source and reporting a warning conflict. Relative source paths are rebased to the composed manifest output directory so the result can be passed directly to `dcf build`.

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

SQL presets:

- `source-health`
- `stale-sources`
- `claim-lineage`
- `surface-splits`
- `code-to-authority`
- `operator-projection`
- `search`

Example:

```bash
dcf sql --sqlite .dcf/deep_context_federation_latest.sqlite --preset search --search governance
```

## Source Quality

Each source row includes a `quality` object with a numeric score and reasons. The score penalizes stale sources, missing required sources, authority-boundary drift, missing verifiers, and optional unavailable adapters. This gives agents an immediate signal about which context is reliable enough to use and which needs refresh or owner review first.

## Semantic Adapters

The builder recognizes common export shapes:

- `surfaces` or `surface_map.surfaces`: emits `surface_id`, `owner_id`, `path`, and `OWNS` / `DERIVES_FROM` edges.
- `symbols` or `code_map.symbols`: emits `symbol_fqn`, `path`, `surface_id`, and `REFERENCES_SYMBOL` edges.
- `nodes` / `edges` or `graph.nodes` / `graph.edges`: maps generic graph exports into federation entities and edge types.

This is the layer that lets the tool absorb advantages from codegraph-style symbol maps, Understand Anything-style surface maps, evidence/claim reports, and codebase-memory-style graph exports without letting any single source become production authority.

## Graph Trace

Use `trace` to start from any matching entity and expand through federation edges:

```bash
dcf trace --input .dcf/deep_context_federation_latest.json --match dashboard --depth 2 --format markdown
```

The output is useful for "code-to-authority" and "claim-to-evidence" exploration because it traverses the unified entity graph rather than one source's private graph.

## Ranking And Doctor

`rank` turns the federation into a prioritization surface:

```bash
dcf rank --input .dcf/deep_context_federation_latest.json --kind entities --limit 20
dcf rank --input .dcf/deep_context_federation_latest.json --kind sources --limit 20
```

Entity ranking combines graph degree, semantic edge weights, source quality, and entity type. Source ranking highlights risky sources by combining quality score, required status, and conflict counts.

`doctor` gives a compact health verdict:

```bash
dcf doctor --input .dcf/deep_context_federation_latest.json --format markdown
```

It checks hard conflicts, missing required sources, stale sources, low-quality sources, graph connectivity, and unresolved warnings. The output includes recommended actions for automation or human review.

## Federation Diff

Compare two builds:

```bash
dcf diff --before old.json --after new.json --format markdown
```

The diff reports source changes, entity/edge additions and removals, conflict changes, and summary deltas. This helps track whether governance work is reducing fragmentation or simply moving it around.

## Incremental Cache

`dcf build --write` writes `.dcf/source_fingerprints.json`. The next run reports changed, unchanged, new, and removed sources under `incremental_cache`. This does not change authority semantics; it gives automation a cheap signal for whether an expensive context refresh is actually needed.

## Benchmarking

Use `bench` to track local build performance:

```bash
dcf bench --manifest examples/deep_context_federation.example.json --root examples --iterations 20 --json
```

## Optional codebase-memory adapter

The optional `codebase-memory-mcp` adapter is disabled by default. When enabled, this tool only checks for a safe external cache configuration. It does not install, index, watch, or mutate agent configuration.

Safe mode requires:

- `--include-codebase-memory`
- `--codebase-memory-cache-dir` or `CBM_CACHE_DIR`
- cache directory outside the repository
- no tracked `.codebase-memory/graph.db.zst`

## Output

`dcf build --write` emits:

- `.dcf/deep_context_federation_latest.json`
- `.dcf/DEEP_CONTEXT_FEDERATION_LATEST.md`
- `.dcf/deep_context_federation_latest.sqlite`

## Tests

```bash
python -m pytest -q
```

## License

MIT
