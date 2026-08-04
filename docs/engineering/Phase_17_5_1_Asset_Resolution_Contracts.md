# Phase 17.5.1 — Asset Resolution Contracts

## Objective

Establish a stable application boundary between Asset Manager data and downstream production systems. Consumers no longer need to understand Asset, CAP, or canonical-reference persistence models.

## Resolution pipeline

```text
AssetResolutionRequest
→ AssetService
→ CAPService
→ CanonicalReferenceService
→ AssetResolutionResult
```

## Public contracts

- `AssetResolutionRequest`
- `AssetResolutionResult`
- `AssetResolutionStatus`
- `AssetResolutionDiagnostic`
- `ResolvedAssetBinding`
- `ResolvedCAPBinding`
- `ResolvedReferenceBinding`
- `AssetDependencyFingerprint`
- `AssetResolutionService`

## Production policy

A request can independently require:

- an approved Asset Manager record;
- a category match;
- a Canonical Asset Profile;
- an approved CAP;
- one or more approved canonical references.

A missing asset produces `unresolved`. An existing asset with incomplete canonical data produces `partial`. A result is `resolved` only when every requested condition is satisfied.

## Stable bindings

The returned bindings contain only production-facing values. Database row details and repository behavior remain hidden behind the application service.

## Dependency fingerprints

Each resolved asset, CAP, and approved reference receives a deterministic SHA-256 checksum. `AssetDependencyFingerprint` combines them into one stable dependency identity for later incremental prompt and render invalidation.

A CAP or approved-reference change therefore produces a different fingerprint without requiring downstream services to inspect those models directly.

## Determinism

- Asset IDs are normalized to uppercase.
- Approved references are ordered by stable numeric identity.
- Multi-resolution requests are ordered by asset ID.
- Checksums use sorted JSON serialization.

## Deliberate exclusions

This phase does not yet add:

- Asset Browser UI integration;
- ACPP or Shot Planner selection changes;
- Prompt Graph enrichment;
- automatic dependency invalidation;
- asset-change event propagation.

Those capabilities belong to Phases 17.5.2 through 17.5.5.
