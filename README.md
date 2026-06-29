# Deep Context Federation

Deep Context Federation is a small, read-only aggregation layer for large codebases and agent workflows.

It joins local context surfaces such as:

- project truth snapshots
- evidence and receipt indexes
- operator or governance projections
- advisory source maps
- code graph or memory adapters

The output is a machine-readable federation graph of sources, entities, edges, conflicts, and local "Codex Fusion" synthesis roles. It is designed to help humans and coding agents ask, "Which surface says this, what evidence supports it, and is this source stale or advisory?"

## Boundary

This tool is deliberately non-authoritative:

- `authority_effect: none`
- `no_apply: true`
- no live/runtime/broker/promotion mutation
- no task-ledger replacement
- no external model calls
- no automatic installer or watcher for optional tools

It does not decide production truth. It only projects and checks consistency across existing truth surfaces.

## Install

```bash
python -m pip install .
```

For development:

```bash
python -m pip install -e ".[dev]"
```

## Quickstart

Run the bundled example after installation:

```bash
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
```

If installed as a package, use `dcf`:

```bash
dcf build --manifest examples/deep_context_federation.example.json --root examples --output-dir .dcf --write
dcf verify --manifest examples/deep_context_federation.example.json --root examples --input .dcf/deep_context_federation_latest.json
dcf query --input .dcf/deep_context_federation_latest.json --preset surface-splits --format markdown
```

From a fresh source checkout without installing first, prefix commands with `PYTHONPATH=src`:

```bash
PYTHONPATH=src python -m deep_context_federation.cli build \
  --manifest examples/deep_context_federation.example.json \
  --root examples \
  --output-dir .dcf \
  --write
```

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
