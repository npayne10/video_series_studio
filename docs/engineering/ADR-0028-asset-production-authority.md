# ADR-0028 — Governed Assets as Production Package Authority

**Status:** Accepted for Phase 19.4.3 implementation  
**Date:** 2026-08-12

## Context

Phase 19.3.4 resolves Shot asset requirements against approved project assets, CAPs and canonical references. Phase 19.4.1 preserves that approved planning snapshot in the Production Package foundation, while Phase 19.4.2 begins specialist compilation with Action & Performance.

Production generation must not reinterpret asset identity from free-form prompt text or silently substitute assets. The canonical Production Package therefore needs an explicit reviewed Asset authority before downstream prompt/provider translation.

## Decision

VSCS SHALL maintain a provider-neutral Asset Compiler authority per current Production Package.

A new Asset Compiler Draft is seeded only from the governed `ProductionPackage.assets` snapshot. VSCS SHALL NOT invent additional characters, ships, props, locations or other asset requirements during compilation.

The compiler preserves the authoritative planning binding and canonical resolution, and adds a normalized provider-neutral production view containing the resolved asset identity, binding identity, production role, requirement, category, canonical reference and dependency checksum where available.

An operator may add production review notes. A current reviewed Draft may be marked Ready, at which point it compiles into a new immutable Production Package revision and records `assets_complete` validation authority.

Changes to the underlying approved Phase 19.3 planning source make the Asset Compiler Draft stale. A stale Draft cannot be compiled as current authority. Refreshing a stale Draft replaces its governed asset snapshot with the current Production Package assets while preserving human review notes. A stale Ready record must first return to Draft.

## UI decision

The existing Phase 19.4 Production Planning workspace remains the single production-compilation environment. Phase 19.4.3 adds an **Assets** compiler tab beside **Action & Performance** rather than creating another top-level application.

## Consequences

Asset identity becomes explicit, inspectable and traceable before provider prompt generation. Canonical references remain governed production inputs rather than provider suggestions. Historical Production Package revisions are preserved, and provider/model syntax remains downstream of canonical production planning.
