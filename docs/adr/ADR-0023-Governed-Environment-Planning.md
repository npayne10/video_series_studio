# ADR-0023 — Governed Environment Planning

## Status

Accepted for Phase 19.3.7 implementation.

## Context

Phase 19.3 has established one authoritative planning chain through Episode, Scene, Shot, Asset Resolution, Camera Planning and Lighting Planning. Environment state was still implicit in Scene setting text, legacy production records or later renderer/prompt decisions.

VSCS requires a renderer-neutral environment authority that is useful for production automation and continuity without duplicating Camera, Lighting or Asset ownership. Because the production may be science fiction, the system must also avoid fabricating physical properties merely to fill fields.

## Decision

VSCS introduces one authoritative `EnvironmentPlan` per governed Shot.

Environment Planning is downstream of:

1. the current Ready governed Shot;
2. current Ready Shot Asset Resolution context;
3. the current Ready Camera Plan; and
4. the current Ready Lighting Plan.

The Environment Plan owns only physical world/environment state required to produce the Shot:

- environment context (interior, surface exterior, atmospheric flight, orbital/deep space, subterranean or underwater);
- time/light-cycle context as a world state, not a lighting instruction;
- atmospheric state;
- weather state;
- optional gravity in m/s²;
- optional pressure in kPa;
- optional temperature in °C;
- optional visibility in metres;
- surface/environment state;
- environmental motion;
- environmental hazards;
- environment continuity notes; and
- environment-specific constraints.

Environment Planning explicitly does **not** own:

- Camera framing, movement, lens or focus;
- Lighting source design, exposure strategy or illumination controls;
- Asset/CAP creation or selection;
- Behaviour Profile authoring;
- prompt text;
- renderer/workflow selection; or
- renderer-specific simulation, particle or material controls.

## Unknown physical values

Unknown values remain `None`/blank. VSCS must not invent gravity, pressure, atmospheric composition, temperature, visibility or other physical quantities when canon has not established them.

Deterministic suggestions may populate values only when directly supported by the setting. Examples:

- orbital/deep-space context establishes vacuum, zero atmospheric pressure and no weather;
- explicit Earth context may use Earth-normal baseline values;
- an unspecified fictional planetary surface keeps gravity, pressure and temperature unknown.

This rule is part of grounded-realism governance, not merely a UI preference.

## Physical consistency

The service rejects internally contradictory states, including:

- non-zero atmospheric pressure in vacuum;
- atmospheric weather in vacuum;
- non-vacuum atmosphere for orbital/deep-space environment context;
- non-submerged atmosphere for underwater context; and
- atmospheric weather for underwater context.

## Lifecycle

`No plan → Draft → Ready`

A Draft may be created only when the upstream Lighting Plan is current and production-ready. Ready Environment Plans are immutable until explicitly returned to Draft.

A Ready Environment Plan becomes stale when the governed Shot, resolved Asset context, Camera Plan or Lighting Plan changes or ceases to be production-ready.

## Persistence

Environment Plans are stored atomically in:

`planning/environment_plans.json`

Schema version: `1.0`.

## Automation

`GovernedEnvironmentPlanningService.suggested_plan()` provides deterministic conservative Draft defaults from the governed Scene setting requirement and Shot intent. Suggestions never become Ready automatically.

The policy distinguishes vacuum, atmospheric flight, surface exterior, controlled interior, subterranean and underwater contexts while preserving unknown fictional physics.

## Consequences

Environment state becomes independently governable, stale-aware and suitable for downstream Planning Review and production compilation. Lighting remains a separate authority: Environment Planning may describe that a sun, atmosphere, weather or physical setting exists, but it does not redesign the Lighting Plan. Later renderer adapters may translate the environment contract into implementation-specific world, simulation or atmospheric controls without making those controls authoritative planning data.
