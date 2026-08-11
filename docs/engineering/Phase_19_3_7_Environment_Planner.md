# Phase 19.3.7 — Environment Planner

## Purpose

Introduce the single authoritative Environment Planning layer beneath governed Lighting Planning.

The Environment Planner captures only physical world/environment information required to produce the Shot while supporting automation, continuity, ease of use and grounded realism.

## Upstream authority

An Environment Plan belongs to exactly one governed Shot.

Environment Planning requires:

- a current Ready governed Shot;
- current Ready Shot Asset Resolution context;
- a current Ready Camera Plan; and
- a current Ready Lighting Plan.

The parent Scene's `setting_requirement` is consumed as planning input but is not duplicated as a second setting authority.

## Authoritative contract

`EnvironmentPlan` stores:

- stable environment-plan identity derived from Shot identity;
- Shot identity;
- environment context;
- time/light-cycle context;
- atmosphere state;
- weather state;
- optional gravity in m/s²;
- optional pressure in kPa;
- optional temperature in °C;
- optional visibility in metres;
- surface/environment state;
- environmental motion;
- environmental hazards;
- environment continuity notes;
- environment-specific constraints;
- Shot-contract fingerprint;
- Asset-context fingerprint;
- Camera-context fingerprint;
- Lighting-context fingerprint;
- Draft/Ready status.

## Production necessity

Every persisted value has a direct downstream production purpose:

- context/time/atmosphere/weather constrain environment generation;
- optional physical values constrain physically based simulation and scale when canon establishes them;
- surface state determines terrain/material/environment expectations;
- environmental motion constrains wind, water, cloud, dust or vacuum behaviour;
- hazards affect visible production state and character/equipment requirements;
- continuity notes preserve world state across adjacent Shots;
- dependency fingerprints protect downstream automation from stale planning truth.

No field exists purely for administrative completeness.

## Unknown values and grounded realism

VSCS must preserve unknown fictional physics instead of inventing them.

Gravity, pressure, temperature and visibility are optional. Suggestions fill them only when supported by the governed setting. An unspecified fictional planet therefore does not automatically receive Earth-normal values.

Physical-consistency validation rejects contradictory states such as atmospheric weather in vacuum or non-zero atmospheric pressure for vacuum.

## Explicit exclusions

Phase 19.3.7 does not store or edit:

- camera framing, lens, movement or focus;
- lighting source direction, fill or exposure design;
- Asset/CAP authoring or Asset Resolver selections;
- Behaviour Profile authoring;
- prompt text;
- renderer/workflow selection;
- renderer-specific world nodes, particle systems, material parameters or simulation settings.

## Persistence

Authoritative data is stored atomically in `planning/environment_plans.json` using schema version `1.0`.

## Automation

`GovernedEnvironmentPlanningService.suggested_plan()` provides deterministic conservative defaults from the parent Scene setting requirement plus governed Shot intent.

The deterministic policy recognises:

- controlled interiors;
- orbital/deep-space vacuum;
- atmospheric flight/descent;
- planetary/surface exteriors;
- subterranean environments; and
- underwater/submerged environments.

Weather and time context are inferred only from explicit setting/story terms. Suggestions are Draft input only and never automatically become production authority.

## Governance

Lifecycle:

`No plan → Draft → Ready`

Ready plans are immutable until returned to Draft.

A Ready Environment Plan becomes stale if:

- the governed Shot contract changes;
- the Shot Asset Resolution context changes;
- the governed Camera Plan changes or ceases to be production-ready; or
- the governed Lighting Plan changes or ceases to be production-ready.

## UI

The governed Lighting Planner exposes `Environment Planner…` only for a current production-ready Lighting Plan.

The Environment Planner provides:

- `Create Suggested Draft`;
- `Create Blank Draft`;
- `Edit`;
- `Mark Ready`;
- `Return to Draft`;
- `Delete Draft`.

The editor is resizable and scrollable. Unknown physical values are represented by blank fields and clearly explained rather than forced to fabricated defaults.

## Acceptance criteria

- deterministic Environment Plan persistence and reload;
- Environment Planning requires a current Ready Lighting Plan;
- orbital/deep-space suggestions enforce vacuum and no atmospheric weather;
- unspecified fictional planetary physics remain unknown;
- contradictory physical state is rejected;
- Shot changes stale the Environment Plan;
- Asset-context changes stale the Environment Plan;
- Camera Plan changes stale the Environment Plan;
- Lighting Plan changes stale the Environment Plan;
- Ready plans cannot be edited/deleted without returning to Draft;
- UI is resizable/scrollable;
- UI contains no Camera, Lighting, Prompt or Renderer-specific authoring controls;
- navigation is Lighting Planner → Environment Planner;
- Ruff, Ruff format, mypy and full pytest regression gates pass;
- coverage remains at or above 70%.
