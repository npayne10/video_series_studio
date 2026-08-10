# ADR-0010 — Structured Production Knowledge Authority and Persistence

**Status:** Accepted  
**Decision scope:** Production knowledge / CAP  
**Phase:** 19.1 — Structured CAP Persistence

## Context

Phase 18 established CAP as a governed production contract and exposed deterministic Readiness and Production Projection services. The legacy CAP persistence model, however, retained important production knowledge primarily as free-form `canonical_description`, `visual_identity`, and `production_notes`. The Production Contract already defined structured facts, functional capabilities, and constraints, but those values were not persisted.

This created a legitimate readiness gap: categories such as ships, vehicles, props, technology, characters, and uniforms could have complete visual references yet remain Production BLOCKED because required machine-readable capabilities or constraints did not exist in persisted canonical data.

## Decision

1. CAP persists structured production knowledge as a versioned extension of the existing CAP record.
2. The structured schema includes facts, functional capabilities, canonical constraints, semantic tags, production classifications, behaviour references, and production metadata.
3. Facts, capabilities, and constraints carry an explicit authority level: `draft`, `proposed`, `approved`, or `canonical`.
4. Only `approved` and `canonical` structured items may satisfy deterministic Production Readiness or be published through Production Projection.
5. AI-generated structured knowledge is always `proposed` until a human review action explicitly accepts it.
6. Human-entered structured CAP values are persisted as `approved` unless a future governance workflow deliberately supports another authority state.
7. Existing CAP prose remains intact and backward-compatible. Schema migration adds structured fields with empty defaults; it does not infer or rewrite canonical knowledge.
8. Production Projection schema 2.0 publishes the approved structured knowledge needed by future Production Planning and Production Package compilation.

## Consequences

- Existing projects migrate safely without losing prose, references, or CAP identity.
- Legacy CAPs may remain blocked until they are modernized; this is intentional production truth rather than a migration failure.
- The migration assistant can use the configured CAP AI provider to propose structured backfill without mutating canonical project data before approval.
- Future Production Behaviour and Production Planning phases can consume structured capabilities/classifications directly instead of parsing prose.
- Production Projection checksums now include structured production knowledge, enabling downstream cache invalidation when canonical knowledge changes.

## Alternatives considered

### Parse CAP prose on demand
Rejected because different subsystems could derive inconsistent interpretations and readiness would cease to be deterministic.

### Automatically promote AI extraction to canonical data
Rejected because model output must not silently become production authority.

### Separate structured knowledge database detached from CAP
Rejected for Phase 19.1 because the data is part of the CAP production contract. A future normalized knowledge graph may supersede the storage implementation without changing the CAP-facing contract.

## Future notes

Phase 19.2 may introduce formal Behaviour Contracts referenced by `behaviour_references`. Phase 19.4 Production Package & Prompt Compilation will consume Production Projection rather than the CAP persistence schema directly.
