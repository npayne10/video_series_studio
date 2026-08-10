# Phase 19.3.4 — Asset Resolver

## Status

Implementation complete; CI and local acceptance required before phase closure.

## Objective

Add the authoritative Shot-level Asset Resolution layer beneath governed Ready Shot Plans without duplicating Asset Manager/XPD, CAP or canonical-reference authority.

Authoritative hierarchy:

`Story → Episode Planner → Scene Planner → Shot Planner → Asset Resolver → Camera Planner → Lighting Planner → Environment Planner → production compilation`.

## Governing boundary

Phase 19.3.4 owns **which canonical project asset satisfies each production requirement of a governed Shot**.

It owns:

- stable Shot asset requirement identity and sequence;
- production role;
- requirement description;
- expected asset category;
- selected project asset identity;
- Draft/Ready governance;
- Shot contract fingerprinting and stale detection;
- Asset/CAP/reference dependency fingerprinting and stale detection;
- production-readiness diagnostics.

It deliberately does **not** own:

- creation or editing of Asset Manager/XPD records;
- creation or editing of CAPs or canonical references;
- camera profiles, lens, shot size or movement — Phase 19.3.5;
- lighting profiles or implementation — Phase 19.3.6;
- environment implementation — Phase 19.3.7;
- renderer/workflow selection or production compilation.

## Storage

Authoritative Shot asset bindings are stored in:

```text
<project>/planning/asset_resolutions.json
```

Schema version: `1.0`.

No Asset, CAP or canonical-reference content is copied into this file. The selected project `asset_id` and deterministic dependency fingerprints are persisted instead.

## Upstream contract

Asset requirements may be created or edited only beneath a governed Shot Plan that is:

1. `Ready`;
2. current against its Scene contract; and
3. production-ready according to `GovernedShotPlanningService`.

Each binding stores a deterministic Shot contract hash. If the Shot changes, the binding becomes stale and cannot be treated as production-ready until reviewed and saved against the new Shot contract.

## Asset authority contract

The existing `AssetResolutionService` is the sole source used to validate selected assets.

A Ready binding requires:

- selected asset exists in the active project;
- category matches the declared requirement;
- Asset status is `Approved`;
- CAP exists and is `Approved`;
- at least one approved canonical reference exists.

The resolver stores the resulting Asset/CAP/reference dependency fingerprint. Any subsequent change to those dependencies makes the binding stale.

Draft bindings may remain unbound or may point to incomplete assets so production planning can continue without weakening Ready governance.

## Category boundary

Phase 19.3.4 supports production asset categories except:

- `camera` — Phase 19.3.5;
- `lighting` — Phase 19.3.6;
- `reference` — canonical references are dependencies of a selected asset rather than standalone Shot assignments.

## UI integration

- A current Ready governed Shot exposes `Asset Resolver…` from the authoritative Shot Planner.
- The Asset Resolver provides New Requirement, Edit, Delete Draft, Mark Ready, Return to Draft, Move Up and Move Down actions.
- The editor supports production role, requirement, expected category, project asset selection and notes.
- Asset choices are sourced from the existing project Asset Browser for the selected category.
- Current Asset/CAP/reference resolution status is shown before approval.
- Ready bindings that no longer match their Shot or canonical asset dependencies are visibly stale.

## Downstream contract

A downstream specialist planner may consume only `ShotAssetBinding` records for which `GovernedAssetResolutionService.is_production_ready()` is true.

The binding provides stable asset identity; consumers that require canonical descriptions or references must resolve that identity through the existing asset-resolution services rather than reading copied planning data.

## Acceptance criteria

1. Asset requirements cannot be created beneath a Draft, stale or otherwise non-production-ready governed Shot.
2. Draft requirements may be saved without a selected asset.
3. Camera, lighting and standalone reference categories cannot be authored in Phase 19.3.4.
4. A binding cannot be marked Ready without a category-matching approved Asset, approved CAP and approved canonical reference.
5. Ready bindings are immutable until returned to Draft.
6. Shot changes make dependent asset bindings stale.
7. Asset, CAP or canonical-reference changes make dependent Ready bindings stale.
8. The Asset Resolver uses existing Asset Manager/XPD and canonical-resolution services rather than duplicating canonical data.
9. The governed Shot Planner exposes Asset Resolver only for a current Ready governed Shot.
10. Ruff lint, Ruff format, strict mypy and the complete pytest suite pass.

## Architecture record

See ADR-0020 — Governed Shot Asset Resolution.
