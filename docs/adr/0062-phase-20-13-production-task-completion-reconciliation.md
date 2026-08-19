# ADR 0062 — Phase 20.13 ProductionTask Completion Reconciliation

## Status

Accepted for Phase 20.13 implementation; pending local validation.

## Context

Phase 19 established provider-neutral `ProductionTask`, `ProductionQueue`, worker, lease, retry, and lifecycle authority. Queue execution intentionally owns worker/runtime state, while `ProductionTask` lifecycle remains a separate persisted authority. Phase 20.6 therefore proved provider execution and queue completion without automatically completing the owning ProductionTask.

Phases 20.9 through 20.12 introduced authoritative Generated Media ingestion, technical validation, human approval, deterministic revision lineage, and a single human-selected candidate per ProductionTask + media-kind production intent slot.

VSCS now needs to distinguish:

- provider execution completed; from
- production work was technically valid, human accepted, authoritatively selected, and therefore complete.

## Decision

### Completion authority

A ProductionTask may be reconciled to `COMPLETED` only when every supported `expected_outputs` contract is satisfied by authoritative selected Generated Media.

Provider completion, RenderOutput existence, Generated Media ingestion, technical validation, or approval alone are insufficient.

### Output contract resolution

Phase 20.13 resolves provider-neutral ProductionTask output contracts by their canonical leading media-kind segment. For example:

- `video/shot` -> `GeneratedMediaKind.VIDEO`
- `image/reference` -> `GeneratedMediaKind.IMAGE`
- `audio/dialogue` -> `GeneratedMediaKind.AUDIO`
- `metadata/...` -> `GeneratedMediaKind.METADATA`
- `report/...` -> `GeneratedMediaKind.REPORT`

Unsupported contracts are blocking findings and are never guessed from provider-specific output names.

Phase 20.12 currently permits one authoritative selection per ProductionTask + media kind. Therefore multiple expected output contracts resolving to the same media kind are considered ambiguous in Phase 20.13 and block completion. A future finer-grained output-slot architecture may remove that restriction without changing the completion principle.

### Selected media validation

For each required output kind, reconciliation requires exactly one Phase 20.12 selection for the task and verifies that:

- the selection and selected media belong to the same production, episode, and ProductionTask;
- selection kind and media kind satisfy the expected output contract;
- the selected media currently remains `APPROVED`;
- selected revision matches the Generated Media revision;
- selection retains explicit `human:` authority;
- technical validation remains `passed`;
- Generated Media governance history contains explicit human approval;
- ingestion provenance `authority_fingerprint` matches the current ProductionTask authority fingerprint.

A failure produces deterministic findings and no task mutation.

### Phase 19 lifecycle compatibility

The existing Phase 19 lifecycle allows `RUNNING -> COMPLETED` but not `READY -> COMPLETED`. Queue runtime does not mutate ProductionTask state, so a successfully executed task may still be persisted as READY when Generated Media governance finishes.

Phase 20.13 does not add a new direct lifecycle transition. For a READY task with complete governed media evidence, reconciliation applies the existing stage transitions:

`READY -> RUNNING -> COMPLETED`

in memory, then persists only the final COMPLETED task once.

For an already RUNNING task, reconciliation applies only:

`RUNNING -> COMPLETED`

PLANNED, BLOCKED, FAILED, CANCELLED, and SUPERSEDED tasks are not force-completed.

### Durable completion evidence

The final ProductionTask metadata retains deterministic reconciliation evidence under `completion_reconciliation.*`, including:

- completion status and timestamp;
- ProductionTask authority fingerprint;
- expected output contract;
- media kind;
- authoritative selection ID;
- selected Generated Media ID;
- selected revision.

Existing unrelated task metadata is preserved.

### Idempotency

A task already in `COMPLETED` state is not transitioned or saved again by reconciliation. The original completion evidence remains authoritative even if a later Phase 20.12 supersession changes the currently selected media candidate.

### Dependency direction

The reconciliation implementation lives under `application/generated_media` because Generated Media ingestion already depends on ProductionTask contracts. Placing it under the ProductionTask package would reverse that dependency and create a package-level circular import.

The reconciliation service still mutates ProductionTask state exclusively through `ProductionTaskLifecycleService` and its existing `ProductionTaskStageService`.

## Consequences

- Provider execution success no longer implies accepted production completion.
- Human approval and authoritative selection become explicit prerequisites for task completion.
- Phase 19 lifecycle authority is reused rather than bypassed.
- Completion is deterministic, provider-neutral, auditable, and idempotent.
- Downstream task/dependency logic can rely on `ProductionTaskState.COMPLETED` as governed production acceptance rather than renderer success.
- Existing Generated Media and selection persistence remain independent authorities; no duplicate completion database is introduced.

## Deliberately deferred

Phase 20.13 does not implement:

- Generated Media UI;
- Production Execution UI;
- automatic candidate selection;
- automatic technical validation or approval;
- finer-grained multiple output slots of the same GeneratedMediaKind;
- re-opening a completed ProductionTask after media supersession;
- distributed transactions across ProductionTask and Generated Media stores;
- Phase 20.16 restart/provider reconciliation.
