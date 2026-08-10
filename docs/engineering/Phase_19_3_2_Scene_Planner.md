# Phase 19.3.2 — Scene Planner

## Status

Implementation complete; local acceptance pending.

## Objective

Decompose an authoritative Ready Episode Plan into deterministic scene-level production intent that Shot Planning can consume, while recording only information genuinely required to produce the video series.

## Governing planning principles

Every Scene Planner field must support at least one of:

1. actual video-series production;
2. downstream automation;
3. continuity preservation;
4. reduced operator repetition/ease of use;
5. grounded production or physical-reality enforcement.

Information owned by later Asset, Shot, Camera, Lighting and Environment planners is explicitly excluded.

## Upstream contract

Scene Planning consumes a Phase 19.3.1 `EpisodePlan` only when its status is `ready`.

A Draft Episode is not a stable planning input. Existing Scene Plans remain visible while an Episode is Draft, but new scene creation and scene editing are blocked until the Episode is Ready again.

## Production contract

`ScenePlan` persists:

- `scene_id`
- `episode_id`
- `sequence_number`
- `title`
- `story_scope`
- `production_objective`
- `target_runtime_seconds`
- `setting_requirement`
- `required_events`
- `continuity_in`
- `continuity_out`
- `scene_constraints`
- `episode_contract_hash`
- `status` (`draft` or `ready`)

Stable scene IDs use the existing production-container convention, for example `EP-001-SCN-001`.

## Data deliberately not stored

Scene Plans do not persist:

- resolved assets or CAPs;
- Behaviour Profile selections;
- shots;
- lenses or camera movement;
- lighting setup;
- weather or environment implementation parameters;
- prompt text;
- render settings.

Those are later Phase 19.3 responsibilities.

## Persistence

Scene plans are stored at:

`planning/scene_plans.json`

The payload uses schema version `1.0` and atomic temporary-file replacement.

No project database schema migration is required.

## Runtime automation

Each Scene Plan receives a target runtime. `ScenePlanningService` exposes allocated and remaining Episode runtime and rejects create/update operations that would cause the sum of scene runtimes to exceed the parent Episode target.

Unallocated Episode runtime is allowed during Scene Planning; exact completeness is a later Planning Review concern.

## Constraint inheritance

Episode constraints remain authoritative at Episode level and are not copied into every Scene Plan.

`effective_constraints(scene)` returns the deduplicated combination of:

1. Episode production constraints;
2. scene-specific constraints.

This prevents repeated input and constraint drift.

## Upstream staleness protection

A Scene Plan stores a SHA-256 fingerprint of the Ready Episode contract against which it was planned.

If the Episode is later changed, the existing scene is visibly stale. A stale scene cannot be considered production-ready for Shot Planning.

Recovery is explicit:

1. return the scene to Draft if needed;
2. review/edit and save against the current Ready Episode;
3. mark the scene Ready again.

This prevents downstream automation from silently consuming obsolete continuity, runtime or production constraints.

## Governance

- New Scene Plans enter Draft.
- Draft scenes may be edited or deleted.
- Ready scenes are immutable.
- Ready scenes must explicitly return to Draft before editing/deletion.
- A scene is production-ready only when its own status is Ready and its upstream Episode fingerprint remains current.

## UI

Scene Planning is nested under the selected Episode in the Episode Planner using `Scene Planner…`.

The Scene Planner shows:

- Episode upstream state;
- allocated / target / remaining runtime;
- scene identity, title, runtime, status/staleness, setting, scope and objective;
- New Scene;
- Edit;
- Delete Draft;
- Mark Ready;
- Return to Draft.

The Scene editor is resizable and vertically scrollable. Episode constraints are visible read-only, while only scene-specific constraints are editable.

## Tests

Focused acceptance coverage includes:

- deterministic stable Scene IDs;
- project-backed persistence;
- Ready Episode requirement;
- runtime budget enforcement;
- inherited constraint composition;
- Draft/Ready governance;
- Ready immutability;
- required-event validation and normalization;
- upstream Episode staleness detection;
- stale-scene recovery;
- resizable/scrollable UI;
- runtime budget display;
- Episode → Scene Planner navigation;
- stale state surfaced in the UI;
- full repository regression suite.

## Explicitly deferred

The following remain outside Phase 19.3.2:

- shot decomposition and shot runtime allocation — Phase 19.3.3;
- CAP/BEP asset resolution — Phase 19.3.4;
- camera implementation — Phase 19.3.5;
- lighting implementation — Phase 19.3.6;
- environment implementation — Phase 19.3.7;
- cross-plan completeness review — Phase 19.3.8;
- planning-system integration acceptance — Phase 19.3.9.

## Acceptance

Phase 19.3.2 is accepted only after Ruff lint, Ruff formatting, mypy, focused Scene Planner tests, Episode/Story UI regressions, full pytest/coverage, and manual UI verification all pass locally.