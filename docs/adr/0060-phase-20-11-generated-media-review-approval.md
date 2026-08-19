# ADR 0060 — Phase 20.11 Generated Media Review & Approval

## Status
Accepted for Phase 20.11 implementation.

## Context

Phase 20.9 introduced authoritative VSCS Generated Media ingestion. Phase 20.10 introduced deterministic technical validation and explicit technical invalidation without granting approval.

The next boundary is human governance. Provider execution, ingestion, technical validation, AI assistance, and automation must never silently approve generated production media.

The existing Generated Media domain already contains the required governance states and immutable audit events:

- `GENERATED`
- `UNDER_REVIEW`
- `APPROVED`
- `REJECTED`
- `INVALID`
- `SUPERSEDED`

and `GeneratedMediaGovernanceEvent` already persists actor, reason, timestamp, source state, and target state.

## Decision

Phase 20.11 introduces `GeneratedMediaReviewService` as the authoritative application entry point for review submission and review decisions.

### Technical validation gate

Only Generated Media with persisted:

`technical_validation.status = passed`

may enter `UNDER_REVIEW` through the Phase 20.11 service.

The same technical-pass evidence must still be present when an approval or rejection decision is applied.

Technical validation does not itself submit media for review or approve it.

### Human authority only

Review actors are represented by `GeneratedMediaReviewActor` and an explicit `ReviewAuthorityType`.

The authority categories are:

- `HUMAN`
- `SYSTEM`
- `AUTOMATION`
- `PROVIDER`

Only `HUMAN` is accepted by `GeneratedMediaReviewActor`. System, automation, and provider identities are rejected before any governance mutation occurs.

The durable governance actor identity is normalized as:

`human:<actor_id>`

The human display name and authority source remain application context and do not replace the stable actor identity in governance history.

### Review submission

A valid submission requires:

- media exists;
- media state is `GENERATED`;
- technical-validation status is `passed`;
- submitter has explicit human authority;
- nonblank reason/comment.

The existing governance transition is reused:

`GENERATED -> UNDER_REVIEW`

### Review decision

A valid decision requires:

- media exists;
- media state is `UNDER_REVIEW`;
- technical-validation status is still `passed`;
- reviewer has explicit human authority;
- nonblank reason/comment;
- explicit `APPROVE` or `REJECT` decision.

The existing governance transitions are reused:

- `UNDER_REVIEW -> APPROVED`
- `UNDER_REVIEW -> REJECTED`

A rejection is a human creative/governance decision and is not converted into technical `INVALID` state.

### Durable audit history

No second review database is introduced.

Submission and decisions are persisted through the existing `GeneratedMediaPersistenceService` and `JsonGeneratedMediaRepository`. `GeneratedMediaGovernanceEvent` is the authoritative durable review audit record, preserving:

- previous state;
- resulting state;
- human actor identity;
- required reason/comment;
- decision timestamp.

Repository restart therefore reconstructs the complete human review history.

### No automatic approval

Provider execution, Generated Media ingestion, technical validation, monitoring/recovery, and future AI assistance do not receive review authority through this service.

Approval requires an explicit call carrying a `GeneratedMediaReviewActor` whose authority is `HUMAN` and a nonblank review reason/comment.

The existing lower-level governance service remains available as a domain transition primitive for backward compatibility, but Phase 20.11 establishes `GeneratedMediaReviewService` as the application-level review/approval boundary for new production workflows.

## Consequences

### Positive

- human approval authority is explicit and typed;
- technical pass and human approval remain separate decisions;
- review comments/reasons are mandatory and durable;
- provider/system/automation identities cannot use the Phase 20.11 review API;
- existing Generated Media governance and JSON persistence are reused;
- approval/rejection survives restart without another persistence model.

### Trade-offs

- identity authentication/authorization remains outside this subphase; the service consumes an already-resolved human actor;
- reviewer role/permission policy can be layered on the actor-resolution boundary later;
- UI workflow is deferred to Phase 20.14/20.15.

## Deliberately deferred

Phase 20.11 does not implement:

- versioning, supersession, or selected-media authority — Phase 20.12;
- ProductionTask completion reconciliation — Phase 20.13;
- Generated Media UI — Phase 20.14;
- Production Execution UI — Phase 20.15;
- authentication provider integration;
- multi-reviewer voting/quorum workflows;
- AI-generated approval decisions.
