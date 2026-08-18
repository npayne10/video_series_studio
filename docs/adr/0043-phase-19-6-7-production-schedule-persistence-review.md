# ADR 0043 — Phase 19.6.7 ProductionSchedule Persistence & Review

## Status

Accepted for implementation in Phase 19.6.7.

## Context

Phase 19.6.6 introduced a deterministic, provider-neutral scheduler that produces an in-memory `ProductionSchedule` from authoritative `READY` ProductionTasks and the ProductionResource catalog. The schedule is intentionally non-executing: it assigns compatible resource identities for one scheduling pass but does not create RenderJobs, queue entries, leases, provider requests, or task lifecycle transitions.

A transient schedule is insufficient for governed production. VSCS must be able to preserve what was scheduled, compare revisions, review the exact allocation that a human saw, and retain historical decisions without allowing an old approval to become authority for a newer schedule.

Existing VSCS approval workflows establish the governance pattern that human decisions must be explicit, attributable, persisted, and tied to the exact governed content reviewed.

## Decision

### 1. Persist immutable schedule revisions

Introduce `ProductionScheduleSnapshot` as the durable representation of one schedule revision. Each snapshot records:

- stable schedule identity scoped to the production;
- production identity;
- monotonically increasing revision;
- deterministic schedule fingerprint;
- complete provider-neutral `ProductionSchedule` content;
- creation timestamp.

Creating a new schedule never overwrites a prior revision.

### 2. Fingerprint the provider-neutral schedule content

The fingerprint covers:

- production identity;
- task-to-resource assignments;
- task priority captured in each assignment;
- required ProductionCapabilities;
- scheduling deferrals and their reasons/candidate resources;
- ignored task identities.

Runtime timestamps, provider details, RenderJobs, workflows, endpoints and executor configuration are excluded.

A persisted snapshot validates that its fingerprint still matches its schedule content when reconstructed.

### 3. Separate schedule content from review decisions

A schedule revision remains immutable. Human review is stored separately as `ProductionScheduleReviewRecord` and contains:

- exact schedule identity and revision;
- exact schedule fingerprint;
- `APPROVED` or `REJECTED` decision;
- reviewer identity;
- required review notes;
- review timestamp.

A schedule revision may be reviewed only once. Changing the allocation requires a new schedule revision rather than rewriting an existing reviewed record.

### 4. Only the current revision may be reviewed

When a newer schedule revision is created, any older revision becomes effectively `SUPERSEDED` for downstream governance even if that historical revision had previously been approved.

The historical review is retained. Supersession changes currentness, not history.

The effective review states are:

- `PENDING_REVIEW`;
- `APPROVED`;
- `REJECTED`;
- `SUPERSEDED`.

### 5. Persistence uses an application repository boundary

Introduce `ProductionScheduleRepository` in the application layer and `JsonProductionScheduleRepository` as the initial infrastructure adapter.

The JSON adapter stores immutable revision documents and append-only review history using atomic file replacement for review-history updates.

This keeps filesystem concerns outside the production scheduling domain and permits later persistence replacement without changing scheduling or review semantics.

### 6. Review does not execute production

Approval of a ProductionSchedule does not:

- transition ProductionTasks to `RUNNING`;
- claim a worker;
- reserve a GPU;
- create an execution lease;
- compile or submit a RenderJob;
- select a provider/model/workflow;
- mutate the legacy RenderQueue.

A later execution-planning boundary may consume only the current approved schedule revision.

## Consequences

- Scheduling decisions become durable and auditable.
- Human review is tied to the exact allocation fingerprint reviewed.
- Rescheduling creates traceable revision history instead of destructive replacement.
- Historical approvals remain visible but cannot silently authorize newer allocations.
- Provider neutrality established in Phases 19.6.1–19.6.6 remains intact.
- Existing legacy render queue and execution infrastructure remain unchanged.
- No UI is introduced in this subphase; a later presentation step can consume the review view without owning governance logic.

## Validation

Focused Phase 19.6.7 coverage must verify:

- deterministic, content-sensitive schedule fingerprinting;
- monotonically increasing revisions with preserved history;
- blank identity rejection;
- explicit reviewer identity and notes;
- exact fingerprint binding of review decisions;
- one review decision per revision;
- current-revision-only review;
- supersession without deletion of historical review;
- JSON persistence surviving repository reopen;
- no mutation of authoritative ProductionTask runtime state;
- preservation of Phase 19.6 scheduler/resource/graph regressions and the full VSCS suite.
