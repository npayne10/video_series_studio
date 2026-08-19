# ADR 0061 — Phase 20.12 Generated Media Versioning, Supersession, and Selection

## Status

Accepted for Phase 20.12 implementation; pending local validation.

## Context

Phase 20.9 introduced authoritative Generated Media records, Phase 20.10 added technical validation, and Phase 20.11 added explicit human review and approval. Multiple provider executions may legitimately produce multiple immutable, technically valid, approved candidates for the same ProductionTask. VSCS therefore requires a deterministic way to distinguish revisions, select one authoritative candidate, and replace it later without deleting history or allowing multiple conflicting active selections.

The Generated Media domain already contains a `revision` field and an `APPROVED -> SUPERSEDED` governance transition with `replacement_media_id`. Phase 20.12 should activate those existing primitives rather than create a second media-version domain.

## Decision

### Production intent slot

One authoritative Generated Media selection slot is identified by:

- `production_id`
- `episode_id`
- `production_task_id`
- `GeneratedMediaKind`

The ProductionTask remains the production-intent authority. Provider identity, workflow identity, render request identity, and provider output identity remain provenance and do not create selection slots.

### Revision assignment

Generated Media ingestion assigns revisions monotonically within the production intent slot:

- first candidate: revision 1
- next candidate: max(existing revisions) + 1

Re-ingesting the same deterministic media identity remains idempotent and keeps its original revision.

Before assigning a new revision, ingestion rejects an existing slot containing duplicate revision numbers. This prevents silently extending ambiguous version history.

### Selection authority

A separate `GeneratedMediaSelection` record stores the single authoritative selection for one production intent slot. Its `selection_id` is a deterministic hash of the slot identity. Because there is one durable record per deterministic selection identity, VSCS cannot create multiple parallel active selections for the same slot through this service.

Selection requires:

- the candidate exists as authoritative Generated Media;
- the candidate is `APPROVED`;
- an explicit Phase 20.11 human review actor;
- a nonblank selection reason/comment;
- no existing active selection for the slot.

Selection does not alter the selected media's governance state.

### Supersession

`supersede_and_select()` replaces the currently selected candidate only when:

- the replacement is `APPROVED`;
- the current selection resolves to an `APPROVED` candidate;
- current and replacement media belong to the same production intent slot;
- the replacement revision is strictly greater than the selected revision;
- an explicit human actor and reason are supplied.

The operation updates the authoritative selection to the replacement and then records the existing Generated Media governance transition:

`APPROVED -> SUPERSEDED`

on the prior candidate with `replacement_media_id` pointing at the newly selected media.

No file or Generated Media record is deleted or overwritten.

### Persistence ordering

Generated Media selection and Generated Media governance are separate persistence boundaries and there is no cross-repository transaction in the current JSON architecture. During supersession, the new selection is persisted before the old media is marked `SUPERSEDED`.

This ordering intentionally prefers an unambiguous authoritative selection if the second persistence write fails. In that failure case, the former candidate may temporarily remain `APPROVED`, but it is no longer selected. The inverse ordering could leave a `SUPERSEDED` media item still recorded as the authoritative selection, which would be a stronger authority contradiction.

A future transactional persistence implementation may make these writes atomic without changing the application contract.

### Selection history

`GeneratedMediaSelection` contains immutable selection events recording:

- previous media identity;
- selected media identity;
- selected revision;
- human actor identity;
- reason/comment;
- timestamp.

Selection revisions must increase and event history must be continuous.

### Human authority

Phase 20.12 reuses `GeneratedMediaReviewActor` from Phase 20.11. Provider, automation, system, and AI execution identities cannot become authoritative selectors through the Phase 20.12 application service.

## Consequences

- Multiple generated candidates remain preserved with complete provider provenance.
- Revision order is deterministic and provider-neutral.
- Approval and selection are separate authorities: approved media is eligible, not automatically selected.
- One production intent slot has at most one authoritative selected media record.
- Superseded media remains fully queryable and auditable.
- Downstream ProductionTask completion may later consume the selected media in Phase 20.13 without guessing among approved candidates.

## Deliberately deferred

Phase 20.12 does not implement:

- ProductionTask completion reconciliation;
- automatic candidate ranking or AI selection;
- user interface for media comparison or selection;
- multi-user locking or distributed transactions;
- rollback of a supersession decision;
- deletion or garbage collection of superseded media;
- delivery/mastering selection profiles beyond the ProductionTask + media-kind slot.
