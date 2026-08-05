# Phase 17.5.3 — CAP and Canonical Reference Resolution

## Purpose

This phase establishes one authoritative application-layer service for resolving a Canonical Asset Profile and its approved canonical references into deterministic production bindings.

The service is independent of the Prompt Graph and renderer layers. It prepares canonical truth for later Prompt Graph enrichment and dependency propagation.

## Resolution pipeline

```text
Asset ID
→ CAP lookup
→ CAP approval validation
→ approved canonical-reference lookup
→ type and role filtering
→ deterministic ordering
→ primary-reference selection
→ dependency fingerprint
```

## Public contracts

The phase adds:

- `CanonicalResolutionRequest`
- `CanonicalResolutionResult`
- `CanonicalResolutionStatus`
- `CanonicalReferenceBinding`
- `CanonicalDependencyFingerprint`
- `CanonicalResolutionService`

## Production readiness

A result is `READY` when:

- the CAP exists;
- the CAP satisfies the requested approval policy;
- the minimum approved-reference count is met; and
- an approved primary reference exists when required.

A result is `PARTIAL` when the CAP exists but one or more requested production requirements are not met.

A result is `UNRESOLVED` when no CAP exists for the asset.

## Reference selection

Only approved canonical references are considered. Optional request filters can restrict the result by reference type or role.

References are ordered deterministically by:

1. primary, secondary, supplementary role;
2. reference type;
3. stable numeric reference identity.

When multiple approved primary references exist, the first deterministic match is selected and a warning diagnostic is emitted.

## Dependency fingerprint

The combined fingerprint contains:

- asset ID;
- CAP checksum;
- ordered selected-reference checksums.

Any CAP or approved-reference change therefore changes the canonical fingerprint. Phase 17.5.5 can use this value to trigger selective recompilation.

## Asset browser integration

The resolution-aware asset browser now exposes:

- canonical status;
- selected primary-reference ID;
- CAP version;
- approved-reference count;
- canonical diagnostics.

The Production-ready filter now also requires canonical readiness, including an approved primary reference.

## Deliberate exclusions

This phase does not yet:

- create Prompt Graph nodes from CAP content;
- attach canonical dependencies to batch items;
- invalidate compiled shots automatically;
- edit CAPs or references from the picker;
- validate media file contents.

Those responsibilities belong to later Phase 17.5 increments.

## Readiness decision

Phase 17.5.3 is complete when automated tests confirm deterministic CAP/reference resolution, primary selection, filtering, diagnostics, stable fingerprints, bootstrap registration and real project integration, and when the asset browser displays the canonical readiness fields correctly.
