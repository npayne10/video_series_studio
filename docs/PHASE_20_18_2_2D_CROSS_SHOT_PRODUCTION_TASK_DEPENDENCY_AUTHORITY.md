# Phase 20.18.2.2d — Cross-Shot ProductionTask Dependency Authority

## Defect

Production Scheduling is intentionally production-scoped while the Production Tasks
table is Shot-scoped. SHT-001 exposed a structural gap: the current SHT-001 task was
READY, but an older READY SHT-002 task was scheduled first and SHT-001 was deferred as
`resource_already_assigned`.

The scheduler itself was following its contract. READY tasks are ordered by priority,
then creation time, then task identity. The deeper defect was that compiled
VIDEO_GENERATION tasks always had an empty dependency tuple. ProductionTaskGraph
therefore treated SHT-002 as independent READY work even though governed continuity
declared SHT-001 as its explicit previous Shot.

## Correction

ProductionTask compilation context now carries governed task dependencies.

The Production Tasks UI resolves `continuity.previous_shot_id` from the current
Production Package. When a predecessor exists it must resolve to exactly one active
VIDEO_GENERATION ProductionTask in the same production. That predecessor task ID is
compiled into the successor task's immutable `dependencies` contract.

Task identity incorporates dependencies only when the dependency tuple is non-empty.
This preserves existing root-Shot task identities while creating a new deterministic
identity when a successor gains governed cross-Shot dependency authority.

ProductionTaskGraph already requires dependencies to reach COMPLETED before promoting a
successor from PLANNED to READY. Therefore a continuity-bound SHT-002 can no longer
compete with SHT-001 for LOCAL-GPU-01 while SHT-001 is still pending.

Supersession governance now also permits replacement when UPD authority is unchanged but
the governed ProductionTask dependency contract changed. This is required to migrate
legacy dependency-free successor tasks safely while preserving them as provenance.

## Safety rules

- No previous Shot: dependency tuple remains empty.
- One active predecessor VIDEO_GENERATION task: compile that task ID as the dependency.
- No active predecessor task: block successor compilation.
- Multiple active predecessor tasks: block successor compilation until obsolete tasks
  are superseded.
- CANCELLED and SUPERSEDED predecessor tasks are never dependency authority.
- Scheduling remains production-scoped; this phase fixes dependency generation rather
  than disguising the issue by making Scheduling Shot-scoped.

## SHT-001 / SHT-002 expected state

After migration:

- current SHT-001 task `PT-VIDEO-GENERATION-D4D1548CB87F5248`: READY;
- rebuilt SHT-002 task: PLANNED while SHT-001 is incomplete and explicitly depends on
  the current SHT-001 task;
- legacy dependency-free SHT-002 task
  `PT-VIDEO-GENERATION-71E2B550F581E0C4`: SUPERSEDED;
- next schedule revision: SHT-001 assigned to LOCAL-GPU-01; SHT-002 successor ignored
  until dependency completion.

This change fixes future stories and Shots at the task-generation boundary instead of
using manual priority changes as a scheduling workaround.
