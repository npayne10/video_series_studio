# Phase 19.3.5 — Camera Planner

## Purpose

Introduce the single authoritative Camera Planning layer beneath governed Shot Planning and governed Asset Resolution.

The Camera Planner must capture only camera information that is required to produce the Shot, while supporting automation, continuity, ease of use and physically grounded production decisions.

## Upstream authority

A Camera Plan belongs to exactly one governed Shot Plan.

Draft Camera Planning requires a current Ready Shot. Ready Camera Planning additionally requires the Shot's declared Asset Resolution context to be complete, current and Ready.

## Authoritative contract

`CameraPlan` stores:

- stable camera-plan identity derived from Shot identity;
- Shot identity;
- shot size;
- camera angle;
- camera movement;
- lens family;
- full-frame-equivalent focal length in millimetres;
- physical camera height in metres;
- structured screen direction;
- composition intent;
- focus strategy;
- movement/physical notes;
- camera continuity notes;
- camera-specific constraints;
- optional Camera Profile Asset identity;
- Shot-contract fingerprint;
- Asset-context fingerprint;
- Camera Profile fingerprint;
- Draft/Ready status.

## Explicit exclusions

Phase 19.3.5 does not store or edit:

- lighting setup;
- exposure/illumination design;
- environment/weather implementation;
- production Asset authoring;
- Behaviour Profile authoring;
- prompts;
- renderer/workflow selection;
- render settings.

## Persistence

Authoritative data is stored atomically in `planning/camera_plans.json` using schema version `1.0`.

## Automation

`GovernedCameraPlanningService.suggested_plan()` provides deterministic conservative defaults from Shot intent. It handles establishing/environmental Shots, dialogue coverage, reactions and moving action while preserving physically plausible movement guidance.

Suggested values are Draft input only and never automatically become production authority.

## Governance

Lifecycle:

`No plan → Draft → Ready`

Ready plans are immutable until returned to Draft.

A Ready Camera Plan becomes stale if:

- the governed Shot contract changes;
- the Shot Asset Resolution context changes;
- an Asset Binding ceases to be current/Ready; or
- an optional Camera Profile changes or ceases to resolve as an approved Camera Asset/CAP.

## UI

The governed Shot Planner exposes `Camera Planner…` for a current Ready Shot.

The Camera Planner provides:

- `Create Suggested Draft`;
- `Create Blank Draft`;
- `Edit`;
- `Mark Ready`;
- `Return to Draft`;
- `Delete Draft`.

The editor is resizable and scrollable. It contains camera-only controls and clearly states that Lighting and Environment are owned by later specialist planners.

The UI passes editor values through an explicit dataclass-to-mapping conversion, and Camera Plan approval is disabled until the governed Shot Asset Resolution context is current and Ready.

## Acceptance criteria

- deterministic Camera Plan persistence and reload;
- Draft planning can begin on a current Ready Shot;
- Ready is blocked until governed Shot Asset Resolution is complete/current;
- Shot changes stale the Camera Plan;
- Asset-context changes stale the Camera Plan;
- Camera Profile changes stale the Camera Plan;
- Ready plans cannot be edited/deleted without returning to Draft;
- suggested camera values are deterministic and physically conservative;
- UI is resizable/scrollable;
- UI contains no Lighting or Environment authoring controls;
- Ruff, Ruff format, mypy and full pytest regression gates pass;
- coverage remains at or above 70%.
