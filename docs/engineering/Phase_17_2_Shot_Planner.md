# Phase 17.2 — Shot Planner

## Objective

Convert structured scenes into persistent, editable production shots that can feed the future ACPP Editor, Prompt Compiler and Production Queue.

## Delivered capability

- Project-backed `story/shots.json` storage with schema version 1.0.
- Stable shot identities derived from scene identity and sequence.
- Create, replace, delete and reorder operations.
- Scene-scoped Shot Planner launched from Story Browser v2.
- Purpose, shot size, camera movement and lens-family controls.
- Canonical camera and lighting profile selectors from Asset Manager.
- Lighting mood and estimated duration.
- Incoming-shot continuity links and continuity notes.
- Actor blocking instructions for position, movement and eyelines.
- Storyboard reference placeholders.
- Dialogue allocation per shot.
- Draft and Ready validation states.
- Responsive, scrollable editing form.
- Persistent production shots displayed beneath their scene.
- Persistent shots replace generated SSIE placeholders with matching IDs.
- Shot Planning service registered through the application bootstrap.
- Targeted service, dialog and Story Browser integration tests.

## Storage

```text
<project>/story/shots.json
```

Existing `scenes.json` projects remain compatible. Shot planning is additive and does not rewrite scene records or generated SSIE plans.

## Downstream contract

`ProductionShot` is the persistent source record intended for Phase 17.3. It supplies:

- shot and scene identity;
- sequence and duration;
- narrative purpose and description;
- camera and lens intent;
- camera and lighting profile references;
- actor blocking and continuity relationships;
- storyboard reference;
- dialogue and asset allocation;
- readiness status.

## Architecture

`ShotPlanningService` is registered in the Phase 16.1 application service graph and injected into Story Browser. Presentation widgets do not create their own service instances.

## Development gate

Phase 17.2 follows VSCS Development Methodology v2 Level 1:

- Ruff clean;
- focused unit tests;
- Story Browser integration tests;
- existing Story, bootstrap and main-window regressions remain green.

No separate certification cycle is required at this feature stage.
