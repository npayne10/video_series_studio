# ADR-0020 — Governed Shot Asset Resolution

## Status

Accepted

## Context

Phase 19.3.3 established a lean authoritative `ShotPlan` that deliberately excludes asset identity. VSCS already has a mature Asset Manager, CAP repository, canonical-reference library and lower-level resolution services. Reintroducing asset IDs directly into Shot Plans, or creating a second production asset registry, would duplicate authority and make downstream compilation dependent on mutable records without an explicit governance boundary.

Phase 19.3.4 therefore requires a separate planning layer that answers a narrower question: **which authoritative project asset satisfies each production requirement declared for this Shot?**

## Decision

VSCS will store Shot-level production asset requirements and their authoritative bindings in:

```text
<project>/planning/asset_resolutions.json
```

Each `ShotAssetBinding` records:

- stable binding identity and sequence;
- parent governed Shot identity;
- production role;
- human-readable requirement;
- expected asset category;
- selected Asset Manager/XPD identity;
- optional notes;
- Shot contract fingerprint;
- combined Asset/CAP/reference dependency fingerprint;
- Draft/Ready governance state.

The Asset Resolver does **not** duplicate Asset, CAP or canonical-reference data. It uses the existing `AssetResolutionService` and `AssetBrowserService` as the source of current project truth.

A binding may be saved unbound or partially resolved while Draft. It may be marked Ready only when:

1. the parent governed Shot is Ready, current and production-ready;
2. a project asset is selected;
3. the selected asset matches the required category;
4. the Asset record is approved;
5. an approved CAP exists;
6. at least one approved canonical reference exists; and
7. both the Shot contract and asset dependency fingerprints are current.

A later change to the Shot, Asset, CAP or selected canonical references makes a Ready binding stale. VSCS must expose the stale state and block downstream production readiness rather than silently rebinding or accepting changed canonical truth.

Camera, lighting and standalone reference categories are excluded from Phase 19.3.4 authoring. Camera and lighting are owned by Phases 19.3.5 and 19.3.6; canonical references are dependencies of an asset binding rather than independent Shot assets.

## Consequences

- Shot Plans remain renderer-neutral and asset-neutral.
- Asset Manager/XPD remains the sole authority for production asset identity.
- CAP and canonical-reference approval participate directly in production readiness.
- Asset changes propagate naturally through deterministic dependency fingerprints.
- Downstream planners can consume stable Ready `ShotAssetBinding` records without copying canonical data.
- Draft planning can proceed before every asset is production-ready, while Ready governance remains strict.

## Alternatives considered

### Store asset IDs directly on `ShotPlan`

Rejected because this mixes Shot narrative intent with a specialist implementation decision and would require Shot edits whenever canonical asset resolution changes.

### Reuse legacy Phase 17 Shot asset fields

Rejected because legacy shots combine multiple specialist responsibilities and are explicitly inactive under ADR-0019.

### Copy CAP/reference content into planning records

Rejected because copied canonical truth would immediately create duplicate sources of authority and stale-data risk.

## Future notes

Phase 19.3.5 and later specialist planners should consume only current Ready governed Shot asset bindings. Asset creation or CAP remediation remains an Asset Manager workflow and is not performed by the Asset Resolver.
