# Phase 19.1 — Structured CAP Persistence

## Status

Implementation / acceptance candidate.

## Objective

Transform Canonical Asset Profiles from prose-dominant records into persisted, machine-understandable production knowledge without breaking existing projects or weakening Phase 18 governance.

## Production principle

> Production knowledge is represented as structured data before it is represented as natural language.

Natural-language CAP fields remain useful for humans and provider prompts, but downstream production systems must not repeatedly parse prose to discover canonical capabilities, constraints, or facts.

## Structured persistence contract

Schema version 5 extends `canonical_asset_profiles` with JSON-backed fields for:

- facts
- functional identity / capabilities
- canonical constraints
- semantic tags
- production classifications
- behaviour references
- production metadata
- structured CAP schema version

Legacy fields remain unchanged.

### Authority

Structured facts, capabilities, and constraints support four authority levels:

- Draft
- Proposed
- Approved
- Canonical

Only Approved and Canonical items may satisfy deterministic Production Readiness or be published to downstream Production Projection consumers.

## Database migration

Opening a schema-4 project upgrades it to schema 5. The migration adds only missing structured columns and initializes them to empty JSON values. Existing CAP descriptions, visual identity, production notes, references, IDs, and lifecycle state are not rewritten.

## CAP editor

The CAP editor exposes structured production knowledge in four groups:

1. Facts
2. Capabilities
3. Constraints
4. Classification / behaviour / metadata

Human-entered values are persisted as Approved production knowledge.

## AI-assisted migration

Existing CAP prose can be submitted to the configured CAP AI provider through **Propose Structured Knowledge…**.

The provider may propose:

- canonical facts
- functional capabilities
- continuity constraints
- prohibited variations
- semantic tags
- production classifications
- behaviour references
- production metadata

AI output is non-mutating and remains Proposed. The operator reviews the proposal before placing it in the editor and must still save the CAP before it becomes persisted Approved knowledge.

Unsupported information must remain empty rather than being invented.

## Readiness integration

`CAPReadinessService` continues to be deterministic and AI-free. Categories that require capabilities or constraints only pass those gates when persisted structured values have Approved or Canonical authority.

## Production Projection integration

Production Projection schema 2.0 publishes:

- approved/canonical facts
- approved/canonical functional capabilities
- approved/canonical constraints
- semantic tags
- production classifications
- behaviour references
- production metadata
- structured schema version

Proposed structured items are excluded.

## Compatibility

The existing Phase 18 Production Contract types remain public. Persisted structured types extend those contracts with authority/provenance rather than replacing them. Existing CAP creation code remains valid because all structured fields have backward-compatible defaults.

## Acceptance criteria

Phase 19.1 is accepted when:

1. A new structured CAP round-trips through SQLite without data loss.
2. A schema-4 database upgrades to schema 5 while preserving legacy CAP prose.
3. Proposed knowledge does not satisfy Production Readiness.
4. Proposed knowledge is excluded from Production Projection.
5. Approved structured knowledge is published by Production Projection.
6. AI proposal generation does not mutate the CAP before human approval.
7. CAP editor can create and update structured facts, capabilities, constraints, classifications, behaviours, and metadata.
8. Existing Phase 18 CAP, reference, readiness, projection, UI, and generation tests remain green.
9. Full repository Ruff and pytest acceptance passes.

## Architectural record

See `docs/adr/ADR-0010-Structured-Production-Knowledge.md`.
