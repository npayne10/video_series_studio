# ADR-0022 — Governed Lighting Planning

## Status

Accepted for Phase 19.3.6 implementation.

## Context

Phase 19.3.5 established a single governed Camera Plan beneath each authoritative Ready Shot. VSCS now requires a renderer-neutral Lighting Planning layer that can express production lighting decisions without collapsing camera, environment, prompt or renderer ownership into one record.

Lighting decisions depend on the approved Shot, its current resolved production assets and the approved Camera Plan. They must therefore become stale whenever any of those upstream contracts change.

## Decision

VSCS introduces one authoritative `LightingPlan` per governed Shot.

A Lighting Plan is downstream of:

1. the current Ready governed Shot;
2. the current Ready governed Shot Asset Resolution context; and
3. the current Ready Camera Plan.

Lighting Planning owns only production illumination intent:

- lighting intent;
- dominant/key source direction;
- dominant source quality;
- target colour temperature;
- fill level;
- renderer-neutral exposure intent;
- motivated source strategy;
- shadow strategy;
- subject readability;
- subject/background separation strategy;
- lighting continuity notes;
- lighting-specific constraints; and
- optional governed Lighting Profile Asset binding.

Lighting Planning explicitly does **not** own:

- environment, weather or time-of-day state;
- camera framing, lens, movement or focus;
- production Asset/CAP authoring;
- prompt text;
- renderer/workflow selection; or
- renderer-specific exposure or light-node settings.

## Lifecycle

`No plan → Draft → Ready`

A Draft may be created only when the upstream Camera Plan is current and production-ready. Ready Lighting Plans are immutable until explicitly returned to Draft.

A Ready Lighting Plan becomes stale when:

- the Shot contract changes;
- the Shot Asset Resolution context changes;
- the Camera Plan changes or ceases to be production-ready; or
- an optional Lighting Profile changes or ceases to resolve as an approved Lighting Asset with approved CAP.

## Persistence

Lighting Plans are stored atomically in:

`planning/lighting_plans.json`

Schema version: `1.0`.

## Automation

`GovernedLightingPlanningService.suggested_plan()` provides deterministic conservative Draft defaults. Suggestions use governed Shot intent and Camera authority to choose physically motivated, renderer-neutral starting values. Suggestions never become Ready automatically.

The suggestion policy avoids decorative illumination and unsupported ambient glow. It favours physically motivated sources, controlled fill, credible shadows and production readability.

## Consequences

Lighting decisions are now independently governable, auditable and stale-aware. Later Environment Planning can remain responsible for world/environment state while consuming a stable lighting contract instead of redefining illumination ad hoc. Renderer adapters can later translate the governed Lighting Plan into implementation-specific controls without making those controls authoritative planning data.
