# ADR-0019 — Governed Shot Planning Boundary

## Status

Accepted

## Context

VSCS already contains the Phase 17.2 Shot Planner and `ProductionShot` persistence. That editor combines narrative shot intent with camera movement, shot size, lens family, camera profiles, lighting profiles, lighting mood, blocking, storyboard references, dialogue and asset allocation.

Phase 19.3 introduced an authoritative production-planning hierarchy and assigned later specialist ownership to Asset Resolution, Camera Planning, Lighting Planning and Environment Planning. Reusing the Phase 17.2 editor as the Phase 19.3.3 authoritative Shot Planner would therefore duplicate ownership and violate the single-authoritative-editor rule established by ADR-0018.

## Decision

Phase 19.3.3 introduces a separate governed `ShotPlan` model and service.

The authoritative Shot Plan records only the renderer-neutral production contract required before specialist planning:

- identity and sequence;
- title;
- narrative purpose;
- production objective;
- target runtime;
- required action;
- dialogue requirement;
- continuity in/out;
- shot-specific constraints;
- governance status;
- fingerprint of the parent Scene contract.

Authoritative Shot Plans are stored in `planning/shot_plans.json` and are independent of legacy Phase 17 `story/shots.json` records.

A Shot Plan may be created only beneath a production-ready governed Scene Plan. A Ready Shot Plan becomes stale if its Scene contract changes and cannot be considered production-ready until reviewed against the new Scene contract.

Legacy Phase 17 shots remain preserved. They may be displayed in the authoritative Shot Planner as `Legacy / Inactive` reference rows, but they are not automatically migrated and cannot be edited or promoted through the governed planner.

## Consequences

- Shot Planning has one unambiguous source of truth.
- Phases 19.3.4–19.3.7 can attach specialist planning data without competing with fields embedded in the Shot Plan.
- Existing Phase 17 projects retain their data without destructive migration.
- Downstream systems can distinguish governed Shot Plans from compatibility records.
- Scene changes propagate explicit stale state into Shot Planning.
- Runtime allocation can be governed at the Scene → Shot boundary.

## Alternatives considered

### Re-enable the Phase 17.2 Shot Planner

Rejected because it already owns camera, lens, lighting, asset and blocking decisions that now belong to later authoritative specialist planners.

### Extend `ProductionShot` and ignore its specialist fields

Rejected because the resulting model would still expose two meanings for the same persisted record and make downstream authority ambiguous.

### Automatically migrate legacy shots into governed Shot Plans

Rejected because legacy records contain implementation choices and semantics that cannot be safely converted into the lean governed contract without explicit operator review.

## Future notes

Phase 19.3.4 Asset Resolver must consume only production-ready governed Shot Plans. It must not treat legacy `ProductionShot.required_asset_ids` or `subject_asset_ids` as authoritative asset-resolution input unless an explicit migration workflow is introduced and accepted.
