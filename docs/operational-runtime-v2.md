# Operational DCF v2

Operational DCF v2 turns configured project evidence into immutable,
independently verifiable context generations. It is an evidence and context
plane, not an execution authority.

## Generation Transaction

Each refresh follows one transaction:

1. Resolve the project layout and collect source fingerprints.
2. Read configured contracts, surfaces, evidence, leases, receipts, Git state,
   history, and supported source symbols.
3. Project capability rows with explicit freshness and typed blockers.
4. Build a SQLite graph in a private staging directory.
5. Hash every generation member and write `manifest.json` last inside staging.
6. Rename staging to an immutable generation directory.
7. Atomically publish `last_good.json`, then `current.json`.

A pointer is consumable only when its manifest digest and every declared member
hash verify. If `current.json` is damaged, readers may fall back to the verified
last-good generation. They never infer a generation from directory ordering.

The default retention mode is `current_only`. After a successful publish or
no-change reconciliation, DCF verifies the current generation and removes all
superseded generations before returning. Historical retention is an explicit
opt-in through `DCF_RETENTION_MODE=history`; it is not required for latest-state
navigation.

## Project Layout

`ProjectLayout` makes repository assumptions explicit. A host can configure:

- runtime root;
- DCF and surface contracts;
- active lease and completed receipt directories;
- evidence directories;
- source roots and supported suffixes;
- bounded collection limits.

The default layout is useful for conventional repositories, but no caller path
is silently promoted into execution or mutation authority.

## Capability and Graph Queries

Capability projections carry:

- `projection_status`;
- `domain_verdict`;
- `freshness_status`;
- `readiness_tier`;
- required source domains;
- typed blockers;
- `authority_effect: none` and `no_apply: true` through the safety envelope.

Graph-backed capabilities resolve an exact entity first, then bounded FTS and
substring matches. Traversal depth is limited to 1-4. Project working state is
always advisory and cannot create a lease, complete a task, or authorize a
command.

Status can evaluate only the capabilities required by the caller:

```bash
dcf runtime status --repo-root . \
  --required-capability surface-map \
  --required-capability source-navigation --json
```

The response keeps global `diagnostic_health` separate from
`execution_admission`. Unrelated stale capabilities remain visible, but they do
not block a task whose required capabilities are current and passing.

An external scheduler can use the same bounded reconciliation path without
running a persistent DCF daemon:

```bash
dcf runtime watchdog --once --repo-root . --json
```

The watcher consumes the configured runtime root's pending event directory,
coalesces the batch, and creates at most one generation. The event producer,
watcher, and query process must resolve the same repository and runtime root.

## J-Space and Task Context

`compile-jspace` binds one action to:

- one immutable DCF generation;
- exact surface ownership;
- declared read and write scopes;
- exact command templates and target paths;
- focused verifier declarations;
- denied effects;
- action-scoped source fingerprints.

The optional `task_context_capsule_v1` carries bounded mission context and
hash-bound evidence references. It does not duplicate path or command authority;
those remain in the separately hashed J-Space contract.

## Safety Boundary

Operational DCF does not:

- execute project commands;
- mutate source, runtime, deployment, broker, or production state;
- infer missing contracts, authority, evidence, or verifier success;
- replace a task ledger, lease store, CAS owner, or mission controller.

Its runtime writes are context artifacts only. A consumer must independently
apply its own execution and protected-effect authority.
