# ADR-0014 — Behaviour Profile Editor

## Status
Accepted for Phase 19.2.4 implementation.

## Context
Phase 19.2.1 defined provider-neutral Behaviour Profiles, Phase 19.2.2 persisted versioned BEPs, and Phase 19.2.3 introduced governed application services. Operators now need a desktop surface that exposes those capabilities without bypassing governance rules.

## Decision
VSCS will provide a dedicated Behaviour Profiles workspace in the main navigation.

The workspace is an application-service client, not a persistence client. It must call `BehaviourProfileService` for creation, mutation, authority transitions, revision creation and deletion.

Draft versions are editable. Proposed, Approved and Canonical versions are view-only. Authority changes are explicit commands and may not be simulated by editing an authority field.

The editor is scrollable and resizable and exposes the complete Behaviour Profile contract: identity, category, action, applicability, aliases, tags, description, parameters, preconditions, constraints, outcomes, interactions, provenance and metadata.

Structured nested values are edited as validated JSON in this phase. This preserves the complete domain structure while avoiding premature specialized sub-editors. Later UX phases may replace individual JSON tabs without changing the Behaviour Profile domain or service contracts.

## Governance controls
The workspace exposes only transitions permitted by Phase 19.2.3:

- Draft → Proposed (`Submit`)
- Proposed → Draft (`Return to Draft`)
- Proposed → Approved (`Approve`)
- Approved → Canonical (`Make Canonical`)

Only Draft versions may be deleted. Any governed version may be used as the source for a new Draft revision.

## Consequences
- UI cannot bypass governance by writing directly to the repository.
- Governed history remains immutable.
- The workspace is immediately usable for creating and reviewing Behaviour Profiles.
- JSON tabs are deliberately a transitional structured editor surface rather than a permanent UX commitment.

## Deferred
CAP-to-BEP linking, readiness integration, Production Projection, AI proposals and migration tooling remain outside Phase 19.2.4.
