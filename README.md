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
- manifest composition for merging self-scan output with curated evidence/context sources
- one-command bootstrap pipeline for scan, compose, build, verify, and doctor
- one-command agent intake packet for bootstrap, quality gate, and task brief
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
