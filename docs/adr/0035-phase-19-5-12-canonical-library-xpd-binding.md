# ADR-0035 — Phase 19.5.12 Canonical Library Import, XPD Matching & Shot Asset Binding

## Decision

VSCS reuses an existing XPD as canonical library authority before considering AI generation of new asset identity.

The existing Phase 18.2.6 XPD workbook reader/importer remains the only workbook ingestion path. Phase 19.5.12 extends that path with deterministic Story-to-XPD rematching and Shot-scoped asset binding evidence.

## Governance

- Import does not fabricate CAPs or Master References.
- A locked/approved XPD row may create an approved Asset registry entry, but downstream CAP/reference readiness remains independently governed.
- Story entities are rematched against current project XPD after import.
- Only resolved existing canonical identities may be bound to Shots automatically.
- Ambiguous/new entities remain human-governed blockers.
- Shot binding is evidence/proposal data; it does not mark Asset Plans Ready and does not approve production.
- AI is not required for canonical matching and has no approval authority.

## Continuity rule

An established universe must reuse canonical identity. `Commander James Spence` must resolve to the existing XPD asset (for the supplied Xorix XPD, `CAP-CHR-001`) rather than generating a duplicate character.
