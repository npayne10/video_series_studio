# ADR-0013 — Behaviour Profile Services and Governance

## Status
Accepted for Phase 19.2.3 implementation.

## Context
Phase 19.2.1 defined the provider-neutral Behaviour Profile (BEP) domain model and Phase 19.2.2 added version-preserving persistence. The repository deliberately does not decide which versions may be edited, promoted, deleted, or consumed as production authority. Those decisions belong at the application-service boundary.

## Decision
VSCS introduces `BehaviourProfileService` as the governed application boundary for Behaviour Profiles.

Authority follows an explicit human-governed lifecycle:

`Draft -> Proposed -> Approved -> Canonical`

A Proposed profile may be returned to Draft for rework. Other backward transitions are rejected. Draft and Proposed profiles are not production authority. Approved and Canonical profiles are production authority.

New profile versions must enter as Draft. Only Draft versions may have their production content edited or be deleted. Once a version leaves Draft, its content is retained as governed history. Further content changes require creation of a new Draft revision with a new version identifier.

Production resolution prefers Canonical versions. If no Canonical version exists, the highest Approved version is selected. Draft and Proposed versions are never returned by production resolution.

## Consequences
- Repository persistence remains governance-neutral.
- UI, AI, and future automation must use the service rather than bypass governance with direct repository authority changes.
- Production consumers receive only Approved or Canonical BEPs.
- Historical approved/canonical definitions cannot be silently rewritten or deleted.
- Version identifiers remain user/domain identifiers; the service uses deterministic natural ordering without imposing SemVer.

## Deferred
Phase 19.2.3 does not add a Behaviour Profile editor, CAP-to-BEP linking, readiness rules, production projection, AI behaviour proposal, or migration UI. Those remain later Phase 19.2 responsibilities.
