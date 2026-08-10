# ADR-0015 — CAP ↔ Behaviour Profile Integration

**Status:** Accepted  
**Phase:** 19.2.5  
**Date:** 2026-08-10

## Context

Canonical Asset Profiles (CAPs) describe what a production asset is. Behaviour Profiles (BEPs) describe governed, reusable ways in which asset classes can act. The CAP schema already contains `behaviour_references`, while Phase 19.2.3 established versioned BEP governance and production-authoritative resolution.

The integration must preserve governed BEP history, avoid binding every CAP to disposable draft revisions, remain provider-neutral, and allow production systems to resolve the current authoritative behaviour definition deterministically.

## Decision

A CAP stores **stable Behaviour Profile identities** (`BEP-*` IDs) in `behaviour_references`; it does not store an exact BEP version.

At production resolution time, each stored identity is resolved through `BehaviourProfileService.production_profile()`:

1. a Canonical version is preferred when one exists;
2. otherwise the highest Approved version is used;
3. Draft and Proposed versions are never production-authoritative.

A CAP may link a BEP identity only when:

- an Approved or Canonical version exists; and
- the CAP asset category is included in the resolved BEP's `applicable_asset_categories`.

The application service `CAPBehaviourIntegrationService` owns these validation and resolution rules. The presentation layer may select links, but it must not bypass the service.

No database migration is required because CAP persistence already stores `behaviour_references` as structured JSON.

## Consequences

- CAPs remain stable when BEP revisions are created.
- Canonical BEPs automatically remain authoritative even when newer Approved revisions exist.
- Production callers receive concrete governed BEP versions while authoring stores only stable identities.
- Invalid, unavailable, or category-incompatible BEP links are rejected at the service boundary.
- Existing CAPs with empty `behaviour_references` remain fully compatible.

## Alternatives considered

### Store exact `profile_id@version` references

Rejected because every approved BEP revision would require CAP rewrites and would tightly couple CAP lifecycle to BEP revision lifecycle.

### Allow Draft/Proposed profiles to be linked

Rejected because CAP behaviour references are production knowledge and must not resolve to ungoverned definitions.

### Add a CAP/BEP join table

Deferred. The existing CAP JSON field is already authoritative and sufficient for the current many-reference contract. A normalized relation may be introduced later if query volume, audit requirements, or cross-project analytics justify it.

## Future notes

Downstream shot planning, prompt compilation, simulation and rendering phases should consume `CAPBehaviourIntegrationService.resolve_for_cap()` rather than reading raw CAP behaviour IDs directly.
