# Phase 17.5.5 — Dependency and Change Propagation

## Objective

Track which shots depend on each production asset and propagate authoritative Asset Manager, CAP, and canonical-reference changes into Prompt Graph sources and incremental compilation state.

## Architecture

```text
Prompt Graph asset enrichment
        ↓
AssetDependencyIndex
        ↓
Asset/CAP/reference changes
        ↓
AssetChangePropagationService
        ├─ refresh affected Prompt Graph sources
        ├─ compare dependency checksums
        └─ invalidate affected compiled prompt items
```

## Public contracts

- `AssetDependencyIndex`
- `ShotAssetDependencyRecord`
- `AssetDependencyChangeKind`
- `AssetDependencyChange`
- `AssetPropagationReport`
- `AssetChangePropagationService`

## Behaviour

`track()` records the dependency snapshot produced by Prompt Graph asset enrichment. `propagate(asset_id)` finds every indexed shot using that asset, reruns enrichment, compares asset, CAP, and approved-reference checksums, refreshes the resolver sources, and invalidates only compiled items belonging to changed shots.

Unchanged dependencies do not trigger recompilation. Removed or unresolved canonical data is reported as a dependency removal. Results are deterministic and ordered by shot and item identity.

## Scope boundary

This phase provides application-layer propagation. Automatic invocation from Asset Manager edit, CAP approval, and canonical-reference lifecycle commands will be reviewed during Phase 17.6 workflow consolidation, where the final UI ownership and editing paths will be defined.

## Testing

Unit coverage verifies reverse indexing, CAP-change detection, deterministic affected-shot lookup, unchanged dependency handling, and shared bootstrap registration. Existing Prompt Graph enrichment and incremental compilation tests provide regression coverage for the connected subsystems.
