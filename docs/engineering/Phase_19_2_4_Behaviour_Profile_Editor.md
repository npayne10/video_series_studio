# Phase 19.2.4 — Behaviour Profile Editor

## Status

**Implementation complete — acceptance pending local verification.**

## Objective

Expose the governed Behaviour Profile capability as a first-class VSCS desktop workspace without weakening the domain, persistence, or governance boundaries established in Phases 19.2.1–19.2.3.

## User-facing capability

The main navigation now contains **Behaviour Profiles**. The workspace provides:

- list/table view of persisted BEP versions
- text search
- behaviour-category filtering
- authority filtering
- creation of new Draft BEPs
- Draft editing
- governed read-only viewing
- Draft deletion
- Submit, Return to Draft, Approve and Make Canonical actions
- new Draft revision creation from an existing version

## Editor contract

The Behaviour Profile editor is scrollable and resizable and exposes:

- profile identity
- version
- name
- description
- category
- action identifier
- applicable asset categories
- aliases
- tags
- authority display
- parameters
- preconditions
- constraints
- outcomes
- interactions
- provenance
- production metadata

Nested structured values are represented as validated JSON tabs in Phase 19.2.4. Pydantic domain validation remains authoritative when the user saves.

## Governance enforcement

The editor does not expose authority as an editable field. Authority mutations are explicit service commands.

Only Draft versions can be edited or deleted. Proposed, Approved and Canonical versions open read-only. Governed versions can be revised into a new Draft version without rewriting history.

## Composition

`ensure_behaviour_profile_service()` registers/reuses one shared `BehaviourProfileRepository` and `BehaviourProfileService` in the application service registry. This lets the editor remain an application-service client and avoids direct database access from presentation code.

## Testing

Focused Qt coverage verifies:

1. editor is resizable and uses a widget-resizable scroll area;
2. a Draft BEP round-trips through the editor model builder;
3. governed versions are read-only;
4. workspace governance controls change according to authority;
5. revision creation preserves the governed source and creates a new Draft version.

Repository-wide Ruff, formatting, mypy and full pytest acceptance must remain green.

## Deliberate exclusions

Phase 19.2.4 does not implement:

- CAP-to-BEP linking
- readiness integration
- Production Projection integration
- AI behaviour proposals
- existing-CAP behaviour migration
- specialized graphical sub-editors for each nested BEP value type

## Acceptance criteria

Phase 19.2.4 is accepted when:

1. Behaviour Profiles appears in the main VSCS workspace navigation.
2. Opening a project enables BEP creation.
3. New Draft BEPs can be created and persisted.
4. Existing Draft BEPs can be edited.
5. Proposed/Approved/Canonical BEPs are read-only in the editor.
6. Authority action buttons obey the Phase 19.2.3 transition graph.
7. Draft deletion is available only for Draft versions.
8. New Revision creates a separate Draft version and preserves source history.
9. The editor is resizable and scrollable on smaller screens.
10. Focused BEP editor Qt tests pass.
11. Existing CAP UI tests continue to pass.
12. Repository-wide Ruff, format, mypy and full pytest acceptance remain green with coverage >= 70%.

## Architectural record

See `docs/adr/ADR-0014-Behaviour-Profile-Editor.md`.

## Next phase

**Phase 19.2.5 — CAP ↔ Behaviour Profile Integration** will establish governed links from structured CAP knowledge to Behaviour Profiles.
