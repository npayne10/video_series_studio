# Phase 19.2.1 — Behaviour Profile Domain Model

## Status

**Accepted — local verification passed.**

## Objective

Introduce a provider-neutral, persistence-independent domain model for Behaviour Profiles (BEPs), defining how production assets behave without embedding renderer, prompt, UI or repository concerns.

## Architectural responsibility

- **CAP** defines what an asset is.
- **BEP** defines how an asset behaves.
- **Production Projection** will later publish approved production knowledge to downstream consumers.

A Behaviour Profile is reusable across any asset whose category and production capabilities satisfy the profile's applicability and interaction requirements.

## Domain contract

Phase 19.2.1 introduces:

- `BehaviourProfile`
- `BehaviourAuthority`
- `BehaviourCategory`
- `BehaviourParameter` and typed parameter kinds
- deterministic `BehaviourPrecondition`
- `BehaviourConstraint` with production significance
- `BehaviourOutcome`
- `BehaviourInteractionRequirement`
- `BehaviourProvenance`
- `is_production_behaviour_authority()`

### Identity and versioning

Each Behaviour Profile owns a stable `BEP-` identifier, human-readable name, version and lower-case machine action identifier.

### Applicability

A Behaviour Profile must apply to at least one existing VSCS `AssetCategory`. This allows one behaviour definition to support multiple compatible asset categories while remaining independent of a particular CAP instance.

### Parameters

Behaviour parameters are machine-readable and support string, integer, number, boolean, duration, distance, speed, angle, enum and asset-reference types. Numeric parameters may define bounds and units. Enum parameters must define allowed values.

### Preconditions

Preconditions use deterministic subject/operator/value expressions. Existence checks intentionally carry no value; comparison and membership operators require one.

### Constraints

Behaviour constraints express canonical production rules and are classified as Required, Warning or Advisory.

### Outcomes

Outcomes describe observable results and may declare a resulting production state.

### Interaction requirements

Interaction requirements identify counterpart roles and may constrain counterpart asset categories or required capabilities. They do not identify a concrete scene instance or provider object.

### Governance

Behaviour Profiles support four authority levels:

- Draft
- Proposed
- Approved
- Canonical

Only Approved and Canonical profiles are production authority. This mirrors the human-governed production-knowledge boundary introduced in Phase 19.1 without coupling BEP to CAP persistence types.

### Provenance

Each profile can retain source, source reference, author and notes so later persistence/governance phases can maintain traceability.

## Validation rules

The domain layer currently guarantees:

1. BEP identifiers use the `BEP-` namespace.
2. Action identifiers are stable lower-case machine identifiers.
3. At least one applicable asset category is required.
4. Parameter names are normalized to lower snake case and must be unique within the profile.
5. Numeric minimum may not exceed maximum.
6. Enum parameters require allowed values; non-enum parameters reject them.
7. Preconditions enforce deterministic value requirements.
8. Empty/duplicate tags, aliases, capabilities and metadata entries are normalized away.
9. Domain models are immutable after validation.

## Deliberate exclusions

Phase 19.2.1 does **not** implement:

- database schema changes
- repository persistence
- application services or CRUD
- CAP-to-BEP linking
- Behaviour Profile UI
- readiness rules
- Production Projection publication
- AI-generated behaviour proposals
- migration tooling

Those responsibilities belong to subsequent Phase 19.2 sub-phases.

## Acceptance criteria

Phase 19.2.1 is accepted when:

1. Behaviour Profiles can represent reusable production behaviours for multiple asset categories.
2. Identity, versioning, action and category are explicit and validated.
3. Parameters, preconditions, constraints, outcomes and interactions are structured domain data.
4. Governance authority and provenance are explicit.
5. Only Approved/Canonical profiles qualify as production authority.
6. Invalid identifiers, empty applicability, duplicate parameters, invalid bounds, enum misuse and invalid preconditions are rejected deterministically.
7. The domain package has no dependency on persistence, presentation, AI providers or renderer-specific modules.
8. Focused unit tests pass.
9. Repository Ruff, formatting, mypy and full pytest acceptance remain green.
10. No UI regression is introduced because Phase 19.2.1 adds no UI surface.

All acceptance criteria were verified on the development machine before Phase 19.2.2 began.

## Architectural record

See `docs/adr/ADR-0011-Behaviour-Profile-Domain-Model.md`.

## Next phase

**Phase 19.2.2 — Behaviour Profile Persistence & Repository** persists BEPs and defines repository contracts without changing the domain responsibility established here.
