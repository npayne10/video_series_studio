# Phase 19.2.2 — Behaviour Profile Persistence & Repository

## Status

**Implementation complete — acceptance pending local verification.**

## Objective

Persist Phase 19.2.1 Behaviour Profiles (BEPs) safely inside each VSCS project and provide a typed repository that round-trips the provider-neutral domain model without introducing application-service, CAP-integration, UI, readiness, projection or AI concerns.

## Architectural responsibility

- **BehaviourProfile** remains the domain authority for how an asset class behaves.
- **BehaviourProfileRecord** is the SQLite persistence representation for one BEP version.
- **BehaviourProfileRepository** maps between persisted records and domain objects.
- Application services will later decide governance workflows and current-version semantics.

The repository does not decide whether a Draft, Proposed, Approved or Canonical profile may be used in production. That rule remains a domain/application concern.

## Database schema

Project database schema advances from **5 to 6**.

Schema 6 introduces `behaviour_profiles` with explicit relational columns for:

- profile ID
- version
- schema version
- name
- description
- behaviour category
- action identifier
- authority
- created/updated timestamps

Structured BEP value objects are persisted as JSON:

- applicable asset categories
- aliases
- parameters
- preconditions
- constraints
- outcomes
- interaction requirements
- tags
- provenance
- metadata

### Version identity

The database enforces a unique constraint on:

`(profile_id, version)`

This intentionally permits multiple versions of the same BEP to coexist. Phase 19.2.2 does not infer which version is current or superseded.

## Migration

Opening a schema-5 project advances it to schema 6 and creates the Behaviour Profile table. Existing project tables and data are not rewritten.

The migration is additive and contains no CAP transformation, no behaviour inference and no authority changes.

## Repository contract

`BehaviourProfileRepository` provides:

- create one exact BEP version
- get one exact `(profile_id, version)`
- list profiles with optional query/category/authority/asset-category filtering
- list all persisted versions for one profile ID
- update the contents of one exact BEP version
- delete one exact BEP version

Repository identity is immutable during update: an update cannot silently rename the profile ID or change its version key.

## Persistence validation

On read, nested JSON is validated through the Phase 19.2.1 domain value types. Invalid persisted data raises `BehaviourProfileRepositoryError`; the repository does not silently replace corrupt behaviour knowledge with empty defaults.

This differs intentionally from some backward-compatibility handling in older CAP persistence: Behaviour Profile storage begins as a structured schema and therefore can enforce stronger integrity from its first version.

## Query behavior

Relational filtering is used for behaviour category and authority. Core textual search covers profile ID, name, description, action and tags. Asset-category filtering is evaluated against the validated structured applicability list so the repository does not depend on SQLite JSON extensions.

## Deliberate exclusions

Phase 19.2.2 does **not** implement:

- Behaviour Profile application service / governance workflows
- current-version or supersession resolution
- CAP-to-BEP links
- readiness integration
- Production Projection integration
- Behaviour Profile editor/workspace
- AI behaviour proposals
- migration of CAP behaviour references

These responsibilities remain in later Phase 19.2 sub-phases.

## Acceptance criteria

Phase 19.2.2 is accepted when:

1. Project database schema is version 6.
2. A schema-5 project upgrades to schema 6 without losing existing data.
3. Complete Behaviour Profiles round-trip through SQLite without loss of structured data.
4. Multiple versions of one profile ID can coexist.
5. Duplicate `(profile_id, version)` creation is rejected deterministically.
6. Exact versions can be read, updated and deleted.
7. Repository list/search/category/authority/asset-category filters behave deterministically.
8. Invalid persisted nested behaviour data is not silently accepted.
9. Phase 19.2.1 domain models remain persistence-independent.
10. Repository-wide Ruff, formatting, mypy and full pytest acceptance remain green.
11. No UI regression is introduced because Phase 19.2.2 adds no UI surface.

## Architectural record

See `docs/adr/ADR-0012-Behaviour-Profile-Persistence-and-Repository.md`.

## Next phase

**Phase 19.2.3 — Behaviour Profile Services & Governance** will build application-level CRUD, authority transitions, version governance and project-facing behaviour operations on top of this repository.
