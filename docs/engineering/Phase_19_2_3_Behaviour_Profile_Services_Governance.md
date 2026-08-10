# Phase 19.2.3 — Behaviour Profile Services & Governance

## Status
Implementation candidate — pending local acceptance.

## Purpose
Place a governed application-service boundary above the version-preserving Behaviour Profile repository introduced in Phase 19.2.2.

## Delivered
- `BehaviourProfileService` application boundary.
- Explicit Draft -> Proposed -> Approved -> Canonical authority lifecycle.
- Proposed -> Draft rework path.
- New versions must begin as Draft.
- Draft-only content editing and deletion.
- Immutable governed history once a version leaves Draft.
- Revision creation from any existing version into a new Draft version.
- Production resolution that excludes Draft/Proposed, prefers Canonical, otherwise resolves the highest Approved version.
- Service-level error translation so callers do not depend on persistence exceptions.
- Focused unit tests for lifecycle, mutation protection, revisions and production authority.
- ADR-0013 documenting the governance boundary.

## Architectural Boundary
This phase does not add UI, CAP linking, readiness integration, production projection, AI proposal support, or migration tools. Persistence schema remains version 6.

## Governance Rules
1. Every newly created BEP version starts as Draft.
2. Draft may transition to Proposed.
3. Proposed may return to Draft or advance to Approved.
4. Approved may advance to Canonical.
5. Canonical is terminal for that exact version.
6. Only Draft versions may be edited or deleted.
7. Governed content changes require a new Draft revision.
8. Only Approved and Canonical versions are production authority.
9. Canonical production authority takes precedence over Approved authority.

## Acceptance
Required gates:
- `ruff check .`
- `ruff format --check .`
- `mypy`
- `pytest tests/unit/test_behaviour_profile_service.py -v`
- Behaviour Profile domain and repository regression tests
- full pytest suite with coverage >= 70%
- normal VSCS startup and existing CAP UI regression smoke test

No new manual Behaviour Profile UI test is expected in 19.2.3 because no BEP UI is introduced.
