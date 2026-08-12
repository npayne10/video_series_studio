# Phase 19.4.6 — Continuity Compiler

## Objective
Compile continuity as inherited production state across Shots rather than as free-form prompt text.

## Architectural principles

- Continuity by inheritance, not recreation.
- Automation by default, human intervention by exception.
- Final approval remains with the user.
- Provider/model/workflow syntax remains downstream.

## Inputs
The compiler consumes the current Production Package plus the immediately preceding current Shot package when one exists. It uses already-governed Action & Performance, Asset, Camera, Lighting and Environment production state.

## Inheritance behaviour

- The previous Shot closing state is carried forward automatically.
- An explicit current opening state remains authoritative when present.
- If explicit opening state differs from inherited previous closing state, the conflict is exposed for user review rather than silently rewritten.
- Asset identities, screen direction, lighting continuity and environment state are carried as structured continuity evidence.
- The first Shot has `series-entry` inheritance and no invented previous state.

## Dependency model
Continuity staleness is based on a deterministic fingerprint of the continuity-relevant current and previous Production Package sections. Changes to either side invalidate a Draft and expose **Refresh Inherited State**. Human review notes are preserved during refresh.

## Governed lifecycle

1. Create from Inherited State.
2. Review resolved opening/closing state, asset identity, camera direction, lighting continuity and detected conflicts.
3. Add optional production review notes.
4. Mark Ready & Compile only after user approval.
5. Ready authority is immutable until Return to Draft.
6. Upstream current/previous changes make the Draft stale.

## Canonical output
The compiled Production Package Continuity section contains:

- `governed`: the resolved inheritance evidence and conflict record;
- `production`: effective opening state, closing state, previous Shot identity, current/previous asset identities, screen direction, lighting continuity, environment context, conflicts and inheritance mode;
- `provider_neutral=true`.

Validation records `continuity_complete=true` and optional `continuity_review_notes`.

## UI
Production Planning gains:

- a Continuity status column;
- a Continuity compiler tab;
- resolved inherited-state review;
- explicit conflict visibility;
- Create from Inherited State, Refresh Inherited State, Save Review Notes, Mark Ready & Compile and Return to Draft actions.

## Non-goals
Phase 19.4.6 does not generate provider prompts, select ComfyUI workflows, use AI to invent missing continuity state, or auto-approve final Continuity authority.

## Acceptance

- Ruff lint and format checks pass.
- strict mypy passes.
- focused Continuity Compiler tests pass.
- Continuity workspace UI tests pass offscreen.
- full regression coverage remains above 70%.
- local functional validation proves previous-Shot inheritance and explicit user approval.
