# ADR-0012 — Behaviour Profile Persistence and Repository

**Status:** Accepted  
**Decision scope:** Behaviour Profile persistence  
**Phase:** 19.2.2 — Behaviour Profile Persistence & Repository

## Context

Phase 19.2.1 established Behaviour Profiles (BEPs) as provider-neutral domain contracts describing how production asset classes behave. The domain deliberately excluded storage concerns. VSCS now needs durable, project-scoped BEP storage without coupling the behaviour model to SQLite, CAP persistence, presentation code or production providers.

Behaviour Profiles are explicitly versioned. Persistence must therefore preserve historical versions rather than treating a BEP identifier as a one-row singleton. Nested behaviour knowledge must also round-trip without flattening structured parameters, preconditions, constraints, outcomes, interactions or provenance into prose.

## Decision

1. Project database schema version 6 introduces a dedicated `behaviour_profiles` table.
2. A persisted BEP version is uniquely identified by `(profile_id, version)`.
3. Multiple versions of the same `profile_id` may coexist in one project database.
4. Searchable and governance-critical values — profile ID, version, name, category, action and authority — are stored as explicit relational columns.
5. Structured collections and nested contracts are persisted as versioned JSON payloads inside the BEP record.
6. Repository code maps between the database record and the Phase 19.2.1 `BehaviourProfile` domain model. The domain model remains persistence-independent.
7. Repository reads validate persisted JSON against the domain types. Corrupt or incompatible persisted behaviour data fails explicitly rather than being silently discarded.
8. Repository update operations modify the contents of one exact `(profile_id, version)` identity; they do not silently rename or re-version a BEP.
9. Schema-5 projects migrate to schema 6 without modifying existing CAP, asset, reference or story data.
10. Behaviour Profile application services, governance workflows and current-version resolution remain outside the repository and are deferred to Phase 19.2.3.

## Consequences

- BEP history can be retained and later governed without redesigning the storage key.
- The repository supports deterministic create/read/list/update/delete operations while remaining independent of UI and AI providers.
- Later CAP integration can reference stable BEP IDs and versions rather than embedding behaviour definitions inside CAP records.
- JSON payloads keep the nested behaviour contract intact while explicit columns support common project queries and filtering.
- Semantic rules such as which version is current, whether a version may be superseded, and who may promote authority belong to the application-service layer rather than SQLite.

## Alternatives considered

### One row per `profile_id`
Rejected because overwriting one BEP row would destroy version history and weaken later governance/audit requirements.

### Store the whole Behaviour Profile as one JSON blob
Rejected because identity, action, category and authority are important query and governance fields and should not require repeated JSON extraction.

### Normalize every parameter, precondition and constraint into separate tables
Deferred. The current structured objects are version-owned value objects rather than independently managed entities. Full normalization would add complexity without improving Phase 19.2.2 behaviour. A later scale requirement may justify a migration without changing the domain contract.

### Persist behaviours inside CAP records
Rejected because BEPs are reusable production knowledge that can apply to multiple asset categories and multiple CAPs.

## Future notes

Phase 19.2.3 will introduce Behaviour Profile services and governance on top of this repository. CAP-to-BEP linking, readiness, projection and UI remain later Phase 19.2 responsibilities.
