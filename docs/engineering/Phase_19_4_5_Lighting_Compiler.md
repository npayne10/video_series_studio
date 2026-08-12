# Phase 19.4.5 — Lighting Compiler

## Objective
Compile approved Phase 19.3 Lighting Planning into canonical, renderer-neutral production Lighting authority inside the existing Phase 19.4 Production Package workflow.

## Architectural principles

- Continuity by inheritance, not recreation.
- Automation by default, human intervention by exception.
- Final creative approval remains with the user.
- Provider/model/workflow decisions remain downstream.

## Inputs
The compiler consumes only the current Production Package Lighting Plan originating from approved governed Planning Integration.

## Governed lifecycle

1. Create from Package.
2. Review governed Lighting values and optional production review notes.
3. Mark Ready & Compile only after user approval.
4. Ready authority is immutable until Return to Draft.
5. If approved Planning changes, the draft becomes stale.
6. Refresh from Current Package rebases the governed Lighting Plan and preserves human review notes.

## Canonical output
The compiler writes a new immutable Production Package revision whose Lighting section contains:

- `governed`: the complete approved upstream Lighting Plan;
- `production`: normalized provider-neutral Lighting intent including lighting intent, key direction and quality, colour temperature, fill level, exposure intent, source and shadow strategies, subject readability, separation strategy, continuity notes, constraints and optional canonical Lighting Profile asset ID.

The package validation map records `lighting_complete=true` and optional `lighting_review_notes`.

## Continuity responsibility
Lighting continuity is structured production state. The compiler preserves upstream continuity notes and constraints so subsequent Continuity, Universal Description and provider-output stages can inherit established lighting state rather than independently recreating it.

## UI
Production Planning gains:

- a Lighting status column alongside Action, Assets and Camera;
- a Lighting compiler tab;
- governed Lighting field/value review;
- optional user review notes;
- Create, Refresh, Save Review Notes, Mark Ready & Compile and Return to Draft actions.

## Non-goals
Phase 19.4.5 does not select ComfyUI models or workflows, generate provider prompts, modify the governed Lighting Plan automatically, or auto-approve final Lighting authority.

## Acceptance

- Ruff lint and format checks pass.
- strict mypy passes.
- focused Lighting Compiler tests pass.
- immutable Production Package Lighting derivation test passes.
- Lighting UI tests pass offscreen.
- full regression suite remains above the repository coverage threshold.
- local functional validation confirms governed Lighting data, user approval and persistence in the running VSCS UI.
