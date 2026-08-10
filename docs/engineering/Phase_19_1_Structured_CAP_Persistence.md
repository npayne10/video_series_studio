# Phase 19.1 — Structured CAP Persistence

## Status

**Complete — Integration & Acceptance passed.**

Phase 19.1 implementation is complete on `phase-19.1-structured-cap-persistence`. The clean acceptance run passes repository-wide Ruff lint and format checks, strict mypy under the documented legacy-debt baseline, and the complete pytest suite.

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

## Migration Assistant

The Canonical Profiles workspace exposes **Modernise CAP…** for legacy CAPs that do not yet contain structured production knowledge.

The governed migration sequence is:

1. Select a legacy CAP.
2. Choose **Modernise CAP…**.
3. Analyse the existing canonical description, visual identity, production notes, asset description and tags through the configured CAP intelligence provider.
4. Present the structured result as Proposed knowledge for human review.
5. Require an explicit approval confirmation before persistence.
6. Promote reviewed facts, capabilities and constraints to Approved authority and persist classifications, behaviour references and production metadata.
7. Refresh the Canonical Profiles workspace so deterministic Readiness and Production Projection immediately consume the newly approved structured knowledge.

The action is disabled when no CAP is selected or when the selected CAP already contains structured production knowledge. It never silently overwrites or automatically promotes AI output.

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
8. The Modernise CAP migration assistant is available for legacy CAPs, preserves the human approval boundary, persists approved structured knowledge and becomes unavailable once migration is complete.
9. Existing Phase 18 CAP, reference, readiness, projection, UI, and generation tests remain green.
10. Full repository Ruff, type-check and pytest acceptance passes.

All ten criteria are satisfied.

## Acceptance evidence

The clean Phase 19.1 acceptance run completed the full CI sequence successfully:

- Qt runtime dependencies installed for headless UI testing.
- `ruff check .` passed.
- `ruff format --check .` passed.
- `mypy` passed with strict mode retained globally and inherited legacy typing debt explicitly scoped by module.
- `pytest --cov=vscs --cov-report=term-missing` passed the full 759-test suite.
- Repository coverage remained above the required 70% threshold; the preceding diagnostic execution measured 71.79%.

The final integration correction also persists the Scene Editor's explicit client size alongside Qt native geometry so geometry restoration is deterministic in both desktop and headless CI environments.

## Architectural record

See `docs/adr/ADR-0010-Structured-Production-Knowledge.md`.
