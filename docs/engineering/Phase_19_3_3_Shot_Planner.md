# Phase 19.3.3 — Shot Planner

## Status

Implementation complete; CI and local acceptance required before phase closure.

## Objective

Add the authoritative Shot Planning layer beneath governed Scene Plans without reintroducing the legacy Phase 17 Shot Planner as a competing source of truth.

Authoritative hierarchy:

`Story → Episode Planner → Scene Planner → Shot Planner → specialist planners → production compilation`.

## Governing boundary

A governed Shot Plan defines **what the shot must accomplish**, not how specialist departments implement it.

Phase 19.3.3 owns:

- stable Shot identity and sequence;
- title;
- narrative purpose;
- production objective;
- target runtime;
- required action;
- dialogue requirement;
- continuity in/out;
- shot-specific constraints;
- Draft/Ready governance;
- Scene contract fingerprinting and stale detection.

Phase 19.3.3 deliberately does **not** own:

- asset resolution — Phase 19.3.4;
- camera, shot size, lens or movement implementation — Phase 19.3.5;
- lighting implementation — Phase 19.3.6;
- environment implementation — Phase 19.3.7;
- renderer/workflow selection or production compilation.

## Storage

Authoritative records are stored separately from legacy Phase 17 shots:

```text
<project>/planning/shot_plans.json
```

Schema version: `1.0`.

Legacy Phase 17 records remain in:

```text
<project>/story/shots.json
```

They are preserved and may be displayed as **Legacy / Inactive**, but they cannot be edited, promoted or consumed as governed Shot Plans until an explicit migration path is implemented.

## Upstream contract

Shot creation requires a Scene Plan that is:

1. `Ready`;
2. current against its Episode contract; and
3. production-ready according to `ScenePlanningService`.

Each Shot Plan stores a deterministic Scene contract hash. If the Scene changes, existing Shot Plans become stale and are blocked from downstream production readiness until reviewed and saved against the new Scene contract.

## Runtime governance

The sum of governed Shot Plan runtimes may not exceed the parent Scene runtime target. The Shot Planner displays allocated and remaining runtime.

## UI integration

- A production-ready Scene exposes `Shot Planner…` from the authoritative Scene Planner.
- The Shot Planner provides New, Edit, Delete Draft, Mark Ready, Return to Draft, Move Up and Move Down actions.
- Legacy shots are visible as read-only inactive rows.
- Governed Shot Plans are projected beneath Scene Plans in the Story Workspace Production Overview.
- `Open in Planner` routes governed Shot selections to the authoritative Shot Planner.

## Downstream contract

A `Ready` governed Shot Plan is the source record for the specialist planning phases. No specialist planning data is embedded in the Shot Plan itself.

## Acceptance criteria

1. Shot Plans cannot be created beneath a non-production-ready Scene.
2. Runtime allocation cannot exceed the Scene target.
3. Ready Shot Plans are immutable until returned to Draft.
4. Scene changes make dependent Shot Plans stale.
5. Legacy Phase 17 shots remain preserved and inactive.
6. Story Workspace projects governed Shot Plans and can navigate to their authoritative planner.
7. Shot Planner UI contains no camera, lens, lighting, asset or environment authoring controls.
8. Ruff lint, Ruff format, strict mypy and the complete pytest suite pass.

## Architecture record

See ADR-0019 — Governed Shot Planning Boundary.
