# Phase 17.5.4 — Prompt Graph Asset Enrichment

## Purpose

Phase 17.5.4 connects authoritative Asset Manager, CAP, and canonical-reference data to the renderer-neutral Prompt Graph.

## Production flow

```text
Selected ACPP asset IDs
→ AssetResolutionService
→ CanonicalResolutionService
→ PromptGraphAssetEnrichmentService
→ PromptGraphResolver
→ PromptGraphBuilder
```

## Enriched content

Each resolved asset contributes one deterministic Prompt Graph source containing:

- Asset identity and category
- CAP canonical description
- CAP visual identity
- CAP production notes
- CAP version and checksums
- Approved canonical-reference IDs
- Selected primary-reference identity
- Canonical readiness status

The canonical description, visual identity, and production notes are joined without rewriting or summarising them. This preserves details such as dimensions, engine configuration, materials, colours, and production restrictions.

## Node mapping

Asset categories map to Prompt Graph node kinds including character, ship, vehicle, location, environment, prop, effect, audio, camera, and lighting. Unsupported categories are retained as `other` rather than discarded.

## Determinism

Asset IDs are normalised and deduplicated. Sources are ordered by asset ID and use stable source identities in the form `asset:<ASSET-ID>`. Re-enrichment replaces the existing source for that asset instead of creating duplicate nodes.

## Additive resolver integration

`PromptGraphResolver.extend()` adds or replaces contributor sources by source ID while preserving unrelated scene, shot, camera, lighting, continuity, dialogue, and restriction sources.

## Dependency metadata

Each enrichment result exposes asset, CAP, and ordered canonical-reference checksums. Phase 17.5.5 will use these values for selective invalidation and change propagation.

## UI impact

This phase changes the application layer and generated Prompt Graph data only. It adds no new visible controls, so no additional manual UI certification is required beyond confirming existing ACPP asset selection still operates.

## Deliberate exclusions

This phase does not yet:

- Automatically discover ACPP asset bindings
- Invalidate compiled prompts when dependencies change
- Add Prompt Preview UI controls
- Execute rendering

Those capabilities remain assigned to later phases.
