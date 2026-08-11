# Phase 19.3.8 — Planning Review

## Objective

Provide the human approval gate over the complete renderer-neutral planning package for each governed Shot before Phase 19.3.9 integration.

## Authority reviewed

The review consumes, but does not own:

1. governed Shot Plan;
2. governed Shot-to-Asset bindings and current CAP/reference resolution;
3. governed Camera Plan;
4. governed Lighting Plan; and
5. governed Environment Plan.

Every authority must be Ready and current before approval. Environment physical-consistency rules remain owned by Environment Planning.

## Governance

A Planning Review begins in Draft. Reviewer notes may be recorded while Draft. Approval is allowed only when all five deterministic checks pass. Approved reviews are immutable until explicitly returned to Draft.

Approval stores a fingerprint of the complete reviewed package. Any subsequent change to Shot, Asset, Camera, Lighting or Environment authority makes that approval stale and therefore not production-ready.

## Persistence

Project-local reviews are stored in `planning/planning_reviews.json` with schema version `1.0`. The review stores only review identity, Shot identity, the reviewed planning fingerprint, reviewer notes and governance status. It does not duplicate upstream plan content.

## UI

`Planning Review…` is owned by the governed Shot Planner and is available whenever a governed Shot is selected. The dialog is intentionally openable while planning is incomplete so it can present PASS/BLOCKED diagnostics for Shot, Assets, Camera, Lighting and Environment.

The dialog provides reviewer notes plus Start Review, Save Notes, Approve Planning and Return to Draft actions. `Approve Planning` remains disabled until every reviewed authority is Ready and current.

Planning Review is not owned by Environment Planner and does not require opening Environment Planner merely to inspect planning readiness.

## Explicit exclusions

Phase 19.3.8 does not own or alter Episode, Scene, Shot, Asset, Camera, Lighting or Environment planning. It does not compile prompts, generate ACPP packages, select renderer settings, schedule rendering, or perform post-render QA.

## Acceptance criteria

- a governed Shot exposes `Planning Review…` directly in Shot Planner;
- the review can open while specialist planning is incomplete and visibly report blockers;
- incomplete or stale upstream planning cannot be approved;
- complete current planning can be reviewed and approved;
- approved reviews are immutable until returned to Draft;
- changes to any reviewed authority make approval stale;
- persistence is deterministic and project-local;
- Environment Planner does not own the Planning Review navigation action;
- standard Ruff, formatting, mypy, pytest and coverage gates pass.
