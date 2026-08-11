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

Every authority must be Ready and current. Environment physical-consistency rules remain owned by Environment Planning.

## Governance

A Planning Review begins in Draft. Reviewer notes may be recorded while Draft. Approval is allowed only when all five deterministic checks pass. Approved reviews are immutable until explicitly returned to Draft.

Approval stores a fingerprint of the complete reviewed package. Any subsequent change to Shot, Asset, Camera, Lighting or Environment authority makes that approval stale and therefore not production-ready.

## Persistence

Project-local reviews are stored in `planning/planning_reviews.json` with schema version `1.0`. The review stores only review identity, Shot identity, the reviewed planning fingerprint, reviewer notes and governance status. It does not duplicate upstream plan content.

## UI

A `Planning Review…` action follows the Environment Planner and becomes available only when the Environment Plan is itself production-ready. The dialog presents PASS/BLOCKED results for every reviewed planning area, reviewer notes, Start Review, Save Notes, Approve Planning and Return to Draft actions.

## Explicit exclusions

Phase 19.3.8 does not own or alter Episode, Scene, Shot, Asset, Camera, Lighting or Environment planning. It does not compile prompts, generate ACPP packages, select renderer settings, schedule rendering, or perform post-render QA.

## Acceptance criteria

- incomplete or stale upstream planning is visibly blocked;
- complete current planning can be reviewed and approved;
- approved reviews are immutable until returned to Draft;
- changes to any reviewed authority make approval stale;
- persistence is deterministic and project-local;
- UI exposes the review only after governed Environment readiness;
- standard Ruff, formatting, mypy, pytest and coverage gates pass.
