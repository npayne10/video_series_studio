# Phase 19.4.4 — Camera Compiler

## Objective
Compile approved Phase 19.3 Camera Planning into canonical, renderer-neutral production Camera authority inside the existing Phase 19.4 Production Package workflow.

## Architectural principles

- Continuity by inheritance, not recreation.
- Automation by default, human intervention by exception.
- Final creative approval remains with the user.
- Provider/model/workflow decisions remain downstream.

## Inputs
The compiler consumes only the current Production Package Camera Plan originating from approved governed Planning Integration.

## Governed lifecycle

1. Create from Package.
2. Review governed Camera values and optional production review notes.
3. Mark Ready & Compile only after user approval.
4. Ready authority is immutable until Return to Draft.
5. If approved Planning changes, the draft becomes stale.
6. Refresh from Current Package rebases the governed Camera Plan and preserves human review notes.

## Canonical output
The compiler writes a new immutable Production Package revision whose Camera section contains:

- `governed`: the complete approved upstream Camera Plan;
- `production`: normalized provider-neutral Camera intent including shot size, angle, movement, lens family, focal length, camera height, screen direction, composition, focus strategy, movement notes, continuity notes, constraints and optional canonical Camera Profile asset ID.

The package validation map records `camera_complete=true` and optional `camera_review_notes`.

## UI
Production Planning gains:

- a Camera status column alongside Action and Assets;
- a Camera compiler tab;
- governed Camera field/value review;
- optional user review notes;
- Create, Refresh, Save Review Notes, Mark Ready & Compile and Return to Draft actions.

## Non-goals
Phase 19.4.4 does not select ComfyUI models or workflows, generate provider prompts, change the governed Camera Plan automatically, or auto-approve final Camera authority.

## Acceptance

- Ruff lint and format checks pass.
- strict mypy passes.
- focused Camera Compiler tests pass.
- immutable Production Package Camera derivation test passes.
- Camera UI tests pass offscreen.
- full regression suite remains above the repository coverage threshold.
- local functional validation confirms governed Camera data, user approval and persistence in the running VSCS UI.
