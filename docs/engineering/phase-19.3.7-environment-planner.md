# Phase 19.3.7 — Environment Planner

## Status

Implemented on `phase-19.3.7-environment-planner`, based on the formally accepted Phase 19.3.6 Lighting Planner.

## Purpose

Phase 19.3.7 introduces a governed, renderer-neutral Environment Planner beneath Ready Lighting Planning. It owns only the physical world state required to render the governed Shot and deliberately excludes Camera, Lighting design, Asset/CAP definition, prompt compilation and renderer-specific controls.

## Authoritative hierarchy

Story → Episode → Scene → Shot → Asset Resolver → Camera Planner → Lighting Planner → Environment Planner.

One Environment Plan is authoritative per governed Shot.

## Environment Plan contract

The Environment Plan records:

- environment context
- time context
- atmosphere state
- weather state
- optional gravity in m/s²
- optional pressure in kPa
- optional temperature in °C
- optional visibility in metres
- surface/environment state
- environmental motion
- hazard notes
- continuity notes
- environment-specific constraints
- Shot, Asset, Camera and Lighting contract fingerprints
- Draft/Ready governance status

Unknown physical values remain unknown when canon does not establish them. The deterministic suggestion engine must not invent fictional planetary gravity, pressure, temperature or visibility merely to complete the plan.

## Environment ownership boundary

Environment Planner owns physical world state and continuity that materially affects production rendering. It does not own:

- camera framing, movement, lens choice or composition
- lighting source design, exposure strategy or key/fill decisions
- canonical asset identity or CAP content
- prompt wording or prompt compilation
- model, sampler, renderer or generation-engine controls

## Deterministic suggestion rules

The authoritative Scene `setting_requirement` determines the broad environment class. Governed Shot text can refine time, weather, hazards and continuity, but incidental Shot wording must not override the Scene's setting authority.

Examples:

- Orbital/deep-space settings establish vacuum, no atmospheric weather and zero atmospheric pressure.
- Unknown fictional planetary surfaces retain unknown gravity/pressure/temperature unless established by canon.
- Atmospheric-flight settings leave density/composition unspecified unless the governed story establishes them.
- Underwater conditions require submerged environment state and prohibit atmospheric weather.

## Physical consistency validation

The service rejects contradictory environment states, including:

- vacuum with atmospheric weather
- vacuum with non-zero atmospheric pressure
- orbital/deep-space context with a non-vacuum atmosphere
- underwater context without submerged state
- underwater context with atmospheric weather

## Upstream governance

A Ready Environment Plan remains production-ready only while all authoritative upstream contracts remain current:

1. governed Shot
2. governed Asset bindings
3. governed Camera Plan
4. governed Lighting Plan

The Environment Plan stores independent fingerprints for all four. Any change makes the Ready Environment Plan stale and prevents downstream production authority until it is returned to Draft, reviewed and re-approved.

Focused acceptance coverage explicitly proves independent Shot, Asset, Camera and Lighting staleness.

## Persistence

Environment Plans persist atomically in:

`<project>/planning/environment_plans.json`

Schema version: `1.0`.

## UI

Lighting Planner exposes an Environment Planner action only when its current Lighting Plan is production-ready.

Environment Planner supports:

- Create Suggested Draft
- Create Blank Draft
- Edit Draft
- Mark Ready
- Return to Draft
- Delete Draft

The specialist editor is resizable and scrollable and keeps optional physical values genuinely optional.

## Validation gates

Phase acceptance requires the untouched repository CI pipeline to pass:

- Ruff lint
- Ruff format check
- strict mypy
- full pytest suite
- configured coverage threshold

No temporary formatting or validation workflow is part of the final phase branch. The final acceptance run must originate from a normal branch commit after all temporary maintenance workflows have been removed.

The final validation commit exists only to exercise that standard repository CI gate against the cleaned Phase 19.3.7 branch.
