# Session Commander Reference Architecture

This document describes the larger closed-loop agent topology that motivated
operational DCF. It is a reference architecture, not a claim that DCF itself
implements task execution or mission authority.

## Closed Loop

```text
Operator intent
  -> Goal and ordered exit predicates
  -> first false predicate
  -> legal route selection
  -> bounded task contract
  -> lease and CAS ownership
  -> executor and provider route
  -> durable terminal receipt
  -> destination-bound continuation injection
  -> callback acknowledgement
  -> parent mission verification
  -> next false predicate or terminal Goal
```

The Global Commander is the sole owner of parent mission convergence. Executors
may finish bounded work, but they cannot redefine the Goal or close the parent
mission. DCF supplies read-only source, capability, evidence, and receipt
projections to the verification step.

## Node Ownership

| Node | Single owner | Durable output |
| --- | --- | --- |
| Goal and ordered predicates | Global Commander | mission revision |
| Route selection | Global Commander | selected route and abandon condition |
| Bounded task | task planner | task identity and contract digest |
| Lease and CAS | task runtime | active ownership record |
| Provider execution | isolated executor route | provider/runtime identity |
| Terminalization | runtime lifecycle owner | terminal receipt and released lease |
| Callback injection | destination-bound continuation adapter | target thread and turn identity |
| Callback ACK | callback/outbox owner | exactly-once acknowledgement |
| Mission verification | Global Commander | changed predicate state |
| Evidence projection | DCF | immutable generation and query receipt |

## Edge Contracts

1. Every dispatch binds a parent mission revision, task identity, destination,
   bounded scopes, and terminal callback contract before provider execution.
2. A terminal receipt records the exact runtime and effect identity. It is not
   equivalent to parent mission completion.
3. Callback delivery resumes the exact Commander destination and starts one
   guided continuation turn. It is not an unowned message queue.
4. Acknowledgement occurs only after the exact target turn is durably observed.
5. The Commander re-reads the Goal and chooses `MISSION_VERIFICATION` or
   `ROUTE_SELECTION`; it does not trust model prose as predicate state.
6. Missing evidence remains typed absence. A stale projection cannot acquire
   current authority.

## Continuity and Compaction

Long-running sessions should carry a small, verified continuity capsule rather
than replaying raw history into every child. Same-ID compaction must preserve
the externally visible session identity while replacing internal history only
under quiescent CAS ownership. Cold storage may hold immutable raw records, but
continuity pointers do not transfer task, Goal, lease, or execution authority.

## Implementation Status Boundary

The architecture can be implemented incrementally, but status labels must stay
separate:

- `SOURCE_VERIFIED`: code and focused tests exist;
- `CANDIDATE_BUILT`: exact runnable artifacts are bound to source;
- `INSTALLED_ADOPTED`: installed bytes match the candidate;
- `RUNNING_VERIFIED`: process identity and end-to-end callback are proven;
- `TYPED_UNKNOWN`: an edge lacks current durable evidence.

This distinction prevents a source patch, healthy process, or terminal child
task from being mislabeled as an accepted end-to-end collaboration framework.
