# Phase 19.2.2 — Behaviour Profile Persistence & Repository

## Status

**Complete — locally accepted on 2026-08-10.**

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

Schema 6 introduces `behaviour_profiles` with explicit relational columns for profile ID, version, schema version, name, description, behaviour category, action identifier, authority, and created/updated timestamps.

Structured BEP value objects are persisted as JSON: applicable asset categories, aliases, parameters, preconditions, constraints, outcomes, interaction requirements, tags, provenance, and metadata.

### Version identity

The database enforces a unique constraint on `(profile_id, version)`. This intentionally permits multiple versions of the same BEP to coexist.

## Migration

Opening a schema-5 project advances it to schema 6 and creates the Behaviour Profile table. Existing project tables and data are not rewritten.

## Repository contract

`BehaviourProfileRepository` provides create, exact get, filtered list, version list, exact update, and exact delete operations.

## Persistence validation

On read, nested JSON is validated through the Phase 19.2.1 domain value types. Invalid persisted data raises `BehaviourProfileRepositoryError` rather than silently replacing corrupt behaviour knowledge with defaults.

## Acceptance

Local acceptance confirmed on 2026-08-10 after Ruff lint, Ruff formatting, mypy, focused BEP domain/repository/migration tests, full pytest coverage acceptance, VSCS startup, existing-project load, and CAP UI regression verification all passed.

## Architectural record

See `docs/adr/ADR-0012-Behaviour-Profile-Persistence-and-Repository.md`.

## Next phase

**Phase 19.2.3 — Behaviour Profile Services & Governance** builds application-level authority transitions, version governance, revisions, and production-facing behaviour resolution on top of this repository.
