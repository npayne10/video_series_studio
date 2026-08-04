# Phase 17.3 — ACPP Editor

## Objective

Convert each persistent `ProductionShot` into a versioned, editable Advanced Clip Production Package using the existing renderer-neutral ACPP foundation.

## Delivered capability

- Project-backed current-package storage under `story/acpp`.
- Immutable archived versions under `story/acpp/history`.
- Deterministic clip identity derived from production, scene, shot and clip order.
- Shot-to-ACPP prefill for identity, timing, prompt intent, camera, lighting, blocking, continuity, dialogue and asset bindings.
- Five-section editor: Identity, Prompt, Assets, Continuity & Audio, and Render & Output.
- Render controls for dimensions, frame rate, frame count, quality and seed policy.
- Structured prompt sections retained in provider-neutral form.
- Asset-binding add and remove workflow.
- Continuity references, incoming clip, start/end references and outgoing state.
- Dialogue, voice, ambience, music and sound-effect allocation.
- Output path and filename controls.
- Established ACPP validation reused directly.
- Draft, Ready and Approved editor statuses.
- Version-history display.
- Story Browser action enabled only for persistent production shots.
- Story Browser shot annotation with ACPP status and version.
- Dependency-injected `ACPPEditorService`.

## Storage

```text
<project>/story/acpp/<clip-id>.json
<project>/story/acpp/history/<clip-id>/v0001.json
```

The current file is the downstream source of truth. Saving a revised package archives the previous current package before writing the new version.

## Downstream compatibility

The editor persists the existing `ClipProductionPackage` contract. Phase 17.4 can therefore consume packages directly through the existing ACPP Prompt Compiler without another schema translation.

## Development gate

Phase 17.3 follows VSCS Development Methodology v2 Level 1:

- Ruff clean;
- focused service tests;
- focused editor tests;
- Story Browser integration tests;
- ACPP foundation, Story, Shot Planner, bootstrap and main-window regressions remain green.

No separate certification cycle is required at this feature stage.
