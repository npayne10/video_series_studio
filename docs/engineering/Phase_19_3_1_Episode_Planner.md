# Phase 19.3.1 — Episode Planner

## Status

Implementation complete; local acceptance pending.

## Objective

Introduce the first production-planning layer that converts a selected Story into deterministic episode-level production intent without collecting information that belongs to later planners.

## Governing planning principles

Every Episode Planner field must satisfy at least one of these tests:

1. it is required to make the video series;
2. it enables downstream automation;
3. it preserves continuity;
4. it reduces repeated operator input;
5. it constrains production toward grounded physical or narrative reality.

If a value cannot satisfy one of these tests, it does not belong in the Episode Plan.

## Production contract

`EpisodePlan` persists:

- `episode_id`
- `story_id`
- `sequence_number`
- `title`
- `story_scope`
- `production_objective`
- `target_runtime_seconds`
- `continuity_in`
- `continuity_out`
- `production_constraints`
- `status` (`draft` or `ready`)

No scene, shot, asset, camera, lighting or environment fields are stored at this layer.

## Persistence

Episode plans are stored under the active project at:

`planning/episode_plans.json`

The payload has schema version `1.0` and is written atomically through a temporary file before replacement.

## Governance

- New plans enter as Draft.
- Draft plans may be edited or deleted.
- A complete Draft may be marked Ready.
- Ready plans are immutable and cannot be deleted.
- A Ready plan must explicitly return to Draft before changes are allowed.

This Ready boundary is the intended input contract for Phase 19.3.2 Scene Planner.

## UI

The Story workspace gains `Episode Planner…` for the selected non-archived Story.

The planner provides:

- New Episode
- Edit
- Delete Draft
- Mark Ready
- Return to Draft

The editor is resizable and vertically scrollable. It deliberately exposes only episode-level production information.

## Automation and continuity

`story_scope` tells downstream planning exactly which source material this episode owns. `production_objective` states what the generated production must accomplish. `target_runtime_seconds` provides a deterministic planning budget. `continuity_in` and `continuity_out` establish state boundaries that Scene Planning must inherit. `production_constraints` carries only enforceable production/realism requirements.

## Tests

Focused acceptance coverage includes:

- deterministic episode identities;
- persistence and Story ownership;
- required production fields;
- runtime validation;
- constraint normalization;
- Draft/Ready governance;
- Ready immutability;
- resizable/scrollable editor UI;
- Story workspace Episode Planner availability;
- planner table and governance controls;
- full repository regression suite.

## Explicitly deferred

The following are Phase 19.3.2+ responsibilities:

- scene generation/decomposition;
- scene count and scene duration allocation;
- asset resolution;
- shot planning;
- camera planning;
- lighting planning;
- environment planning;
- cross-plan review and integration.

## Acceptance

Phase 19.3.1 is accepted only after Ruff lint, Ruff formatting, mypy, focused Episode Planner tests, Story UI regressions, full pytest/coverage, and manual UI verification all pass locally.
