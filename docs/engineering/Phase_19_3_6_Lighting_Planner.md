# Phase 19.3.6 — Lighting Planner

## Purpose

Introduce the single authoritative Lighting Planning layer beneath governed Camera Planning.

The Lighting Planner captures only illumination information required to produce the Shot while preserving renderer neutrality, physical plausibility, continuity and specialist ownership boundaries.

## Upstream authority

A Lighting Plan belongs to exactly one governed Shot.

Lighting Planning requires:

- a current Ready governed Shot;
- current Ready Shot Asset Resolution context; and
- a current Ready Camera Plan.

## Authoritative contract

`LightingPlan` stores:

- stable lighting-plan identity derived from Shot identity;
- Shot identity;
- lighting intent;
- key/dominant source direction;
- key/dominant source quality;
- target colour temperature in Kelvin;
- fill level percentage;
- renderer-neutral exposure intent;
- motivated source strategy;
- shadow strategy;
- subject readability strategy;
- separation strategy;
- lighting continuity notes;
- lighting-specific constraints;
- optional Lighting Profile Asset identity;
- Shot-contract fingerprint;
- Asset-context fingerprint;
- Camera-context fingerprint;
- Lighting Profile fingerprint;
- Draft/Ready status.

## Explicit exclusions

Phase 19.3.6 does not store or edit:

- environment/weather/time-of-day state;
- camera framing, movement, lens or focus decisions;
- production Asset/CAP authoring;
- Behaviour Profile authoring;
- prompts;
- renderer/workflow selection;
- renderer-specific light nodes, exposure values or render settings.

## Persistence

Authoritative data is stored atomically in `planning/lighting_plans.json` using schema version `1.0`.

## Automation

`GovernedLightingPlanningService.suggested_plan()` provides deterministic conservative defaults from the governed Shot contract and current Camera authority.

The deterministic policy includes:

- naturalistic, directionally motivated defaults for orbital/exterior material;
- practical-motivated soft coverage for dialogue;
- controlled low-key treatment for danger/tension material;
- functional high-key treatment for medical/lab/inspection contexts;
- explicit silhouette handling when requested.

Suggestions are Draft input only and never automatically become production authority.

## Governance

Lifecycle:

`No plan → Draft → Ready`

Ready plans are immutable until returned to Draft.

A Ready Lighting Plan becomes stale if:

- the governed Shot contract changes;
- the Shot Asset Resolution context changes;
- the governed Camera Plan changes or ceases to be production-ready; or
- an optional Lighting Profile changes or ceases to resolve as an approved Lighting Asset/CAP.

## UI

The governed Camera Planner exposes `Lighting Planner…` only for a current production-ready Camera Plan.

The Lighting Planner provides:

- `Create Suggested Draft`;
- `Create Blank Draft`;
- `Edit`;
- `Mark Ready`;
- `Return to Draft`;
- `Delete Draft`.

The editor is resizable and scrollable. It contains lighting-only controls and clearly states that Environment/weather/time-of-day, Camera, Asset, Prompt and Renderer ownership remain elsewhere.

## Acceptance criteria

- deterministic Lighting Plan persistence and reload;
- Lighting Planning requires a current Ready Camera Plan;
- Shot changes stale the Lighting Plan;
- Asset-context changes stale the Lighting Plan;
- Camera Plan changes stale the Lighting Plan;
- Lighting Profile changes stale the Lighting Plan;
- Ready plans cannot be edited/deleted without returning to Draft;
- suggested lighting values are deterministic, physically motivated and renderer-neutral;
- UI is resizable/scrollable;
- UI contains no Environment, Camera or Renderer-specific authoring controls;
- navigation is Camera Planner → Lighting Planner;
- Ruff, Ruff format, mypy and full pytest regression gates pass;
- coverage remains at or above 70%.
