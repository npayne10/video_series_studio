# ADR-0017 — Scene Planner

## Status

Accepted

## Context

Phase 19.3.2 decomposes a Ready Episode Plan into scene-level production intent that Phase 19.3.3 Shot Planner can execute. The Scene Planner must preserve the planning principles established for Phase 19.3: production necessity, automation, continuity, ease of use and grounded realism.

A scene contract must therefore describe what the scene must accomplish without prematurely duplicating the responsibilities of Asset Resolution, Shot, Camera, Lighting or Environment planning.

A second requirement is change safety. Scene Plans are downstream of Episode Plans. If an Episode contract changes after scenes have been planned, VSCS must not silently treat those scenes as current.

## Decision

VSCS introduces a project-backed `ScenePlan` contract owned by one Episode Plan.

A Scene Plan persists only:

- stable scene identity and sequence;
- parent Episode identity;
- scene title;
- the Episode story scope owned by the scene;
- the production objective the scene must accomplish;
- target runtime allocation;
- the story-required setting context needed by later Environment Planning;
- required story events that Shot Planning must realize;
- continuity entering and leaving the scene;
- scene-specific enforceable production/realism constraints;
- a fingerprint of the Ready Episode contract used to create/review the scene;
- Draft or Ready planning state.

Scene Plans are stored in `planning/scene_plans.json` with schema version `1.0` and atomic replacement writes.

Only a Ready Episode may be used to create or edit Scene Plans. The sum of Scene Plan runtime allocations may not exceed the parent Episode target runtime.

Episode constraints are inherited dynamically and are not copied into each Scene Plan. `ScenePlanningService.effective_constraints()` combines Episode and scene-specific constraints for downstream consumption.

Ready Scene Plans are immutable until explicitly returned to Draft.

Each Scene Plan stores a SHA-256 fingerprint of its upstream Episode production contract. If that Episode is later returned to Draft, changed and marked Ready again, the existing Scene Plan becomes `Stale`. A stale Scene Plan is not production-ready until an operator returns it to Draft, reviews/resaves it against the new Episode contract, and marks it Ready again.

The Scene Planner does not persist asset selections, shot definitions, camera parameters, lighting parameters, environment implementation details, prompts or render settings.

## Consequences

- Shot Planning receives deterministic scene objectives, required events, runtime budgets and continuity boundaries.
- Scene runtime allocation can be automated and validated against the Episode target.
- Episode constraints propagate without duplicate data entry or drift.
- Upstream Episode changes cannot silently invalidate downstream planning.
- Scene Plans stay small enough for operators to review quickly.
- Later Asset, Camera, Lighting and Environment planners retain clear ownership of their production decisions.

## Alternatives considered

### Reuse the existing legacy Scene/SSIE editor as the Scene Planner

Rejected because that model already includes camera, lighting, asset and other implementation details that belong to later Phase 19.3 planners. Reusing it would collapse planning layers and create duplicated authority.

### Copy all Episode constraints into every Scene Plan

Rejected because copied constraints can drift when the Episode changes. Scene Plans persist only scene-specific constraints and inherit Episode constraints dynamically.

### Allow scene planning from Draft Episodes

Rejected because downstream planning would have no stable upstream contract. A Ready Episode is the explicit automation boundary.

### Ignore upstream Episode changes after scene creation

Rejected because stale scene plans could preserve obsolete runtime, continuity or production constraints and create expensive continuity failures later in production.

## Future notes

Phase 19.3.3 Shot Planner must consume only Scene Plans for which `ScenePlanningService.is_production_ready()` is true. Shot runtime allocation must remain within each Scene Plan target and required story events must be traceable into the resulting shot plan.