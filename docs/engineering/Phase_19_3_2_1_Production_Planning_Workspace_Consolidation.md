# Phase 19.3.2.1 — Production Planning Workspace Consolidation

## Status

Implementation and canonical formatting complete; final CI and local acceptance pending.

## Objective

Remove overlapping production-authoring paths from the Story Workspace and establish one authoritative production-planning hierarchy before Phase 19.3.3 Shot Planner begins.

## Governing rule

VSCS has exactly one authoritative editor for each planning level. Other surfaces may inspect or navigate planning information, but they must not independently mutate the same production object.

Authoritative hierarchy:

`Story → Episode Planner → Scene Planner → Shot Planner → specialist planners → production compilation`.

## Story Workspace changes

The Story Workspace remains responsible for Story creation, analysis, approval and governance.

Its production-planning entry point is renamed from `Episode Planner…` to `Production Planning…`.

The lower Production Overview is converted from a legacy authoring surface into a governed planning navigator. It now projects data from:

- `EpisodePlanningService`;
- `ScenePlanningService`.

The overview no longer treats legacy Story/SSIE records as Phase 19.3 planning authority.

## Removed competing authoring controls

The following legacy Story Workspace actions are hidden and disabled:

- New Scene;
- Edit Scene;
- Delete Scene;
- Generate SSIE Plan;
- direct legacy Shot Planner;
- direct ACPP Editor.

The underlying legacy data and services remain intact for compatibility and future explicit migration. This phase performs no destructive conversion.

## Production Overview

The lower Story Workspace tree displays:

- governed Episode Plans;
- governed Scene Plans nested beneath their Episode;
- Draft/Ready state;
- Scene staleness when its upstream Episode contract has changed;
- runtime targets.

The dashboard is recomputed from governed planning records. Shot and asset totals remain zero at this stage because governed Shot Planning and Asset Resolution belong to later Phase 19.3 sub-phases.

## Navigation

The lower toolbar is reduced to:

- Open in Planner;
- Refresh Overview.

`Open in Planner` is context-sensitive:

- Episode selection opens Episode Planner at that Episode;
- Scene selection opens Scene Planner at that Scene.

Double-clicking a governed planning row follows the same authoritative route.

## Automation, continuity, usability and realism

### Automation

Downstream systems have one clear source of truth instead of choosing between legacy and governed planning records.

### Continuity

Episode/Scene Ready state and upstream-staleness rules remain authoritative and are surfaced in the navigator.

### Ease of use

The operator enters production planning once. The Story Workspace provides orientation and navigation without duplicating editing controls.

### Grounded realism

Production/realism constraints continue to flow through Episode and Scene planning; consolidation prevents those constraints from being bypassed by a separate legacy editing path.

## Tests

Focused acceptance covers:

- `Production Planning…` as the sole Story-level planning entry;
- all legacy duplicate authoring controls hidden and disabled;
- governed Episode/Scene plans projected into Production Overview;
- legacy scene records preserved but excluded from authoritative planning display;
- context-sensitive `Open in Planner` state;
- governed dashboard counts;
- stale Scene state surfaced;
- Episode Planner regression updated for the consolidated label;
- full repository regression suite.

## Explicitly deferred

- destructive migration/removal of legacy Story/SSIE/Shot/ACPP data;
- governed Shot Planner implementation (Phase 19.3.3);
- governed Shot projection into Production Overview;
- Asset Resolver, Camera, Lighting and Environment planner projections;
- final Planning Review and Integration.

## Acceptance

Phase 19.3.2.1 is accepted only after Ruff lint, Ruff formatting, strict mypy, focused consolidation Qt tests, Episode/Scene regressions, complete pytest/coverage, and manual verification that the Story Workspace exposes only one authoritative production-planning environment.
