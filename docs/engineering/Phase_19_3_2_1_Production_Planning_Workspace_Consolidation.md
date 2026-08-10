# Phase 19.3.2.1 — Production Planning Workspace Consolidation

## Status

Implementation, canonical formatting, strict typing, and legacy regression-test alignment complete; final CI and local acceptance pending.

## Objective

Remove overlapping production-authoring paths from the Story Workspace and establish one authoritative production-planning hierarchy before Phase 19.3.3 Shot Planner begins.

## Governing rule

VSCS has exactly one authoritative editor for each planning level. Other surfaces may inspect or navigate planning information, but they must not independently mutate the same production object.

Authoritative hierarchy:

`Story → Episode Planner → Scene Planner → Shot Planner → specialist planners → production compilation`.

## Story Workspace changes

The Story Workspace is the story-level entry point and governed production overview. It is not an independent production-object editor.

- The story-level planning action is labelled **Production Planning…**.
- Governed Episode and Scene plans are projected from `EpisodePlanningService` and `ScenePlanningService`.
- `Open in Planner` routes Episode selections to the Episode Planner and Scene selections to the Scene Planner.
- Draft, Ready, and upstream-stale state is visible in the overview.
- Runtime metrics are based on governed production plans.

## Competing authoring paths

The following legacy Story Workspace actions are hidden and disabled in the consolidated workspace:

- New Scene
- Edit Scene
- Delete Scene
- Generate SSIE Plan
- direct Shot Planner
- ACPP Editor

The underlying legacy components and persisted project records remain available for compatibility and regression coverage, but they are not presented as authoritative production planning.

## Compatibility and regression policy

Pre-19.3.2.1 Story Browser, Shot Browser, and ACPP Browser component tests continue to exercise their legacy components directly. They no longer use the application main window as evidence that those legacy authoring paths remain part of the authoritative Story Workspace.

This preserves backwards-compatible component behaviour while enforcing the Phase 19.3.2.1 main-window architecture contract.

## Acceptance criteria

1. Story Workspace exposes exactly one production-planning entry point.
2. Episode and Scene plans shown in the overview originate from governed planning services.
3. Legacy Scene/SSIE/Shot/ACPP authoring actions are not available from the authoritative Story Workspace.
4. Existing legacy records are not deleted or silently migrated.
5. Episode and Scene selections navigate to their authoritative planners.
6. Upstream-stale Scene Plans are visibly identified.
7. Ruff lint, Ruff format, strict mypy, and the complete pytest suite pass before Phase 19.3.2.1 is accepted.

## Architecture record

See ADR-0018 — Authoritative Production Planning Workspace.
