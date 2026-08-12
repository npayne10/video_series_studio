# Phase 19.4.2 — Action & Performance Compiler

## Objective

Make the actual temporal story of a governed Shot explicit, reviewable and compilable into the canonical Production Package before provider-specific prompt generation.

## Input

The authoritative input is the current Phase 19.4 `ProductionPackage`, itself derived from the current approved Phase 19.3 Integrated Planning Package.

## Draft authority

`ActionPerformanceDraft` stores:

- temporal narrative;
- spoken content / dialogue;
- performance direction;
- opening state;
- closing state;
- timing notes;
- source Production Package identity/fingerprint; and
- Draft/Ready governance state.

A new draft is seeded only from governed Shot `required_action`, `dialogue_requirement`, `continuity_in`, `continuity_out` and target runtime. Empty or unspecified production detail remains empty rather than being invented.

## Compilation

Only a current Ready Action & Performance draft may compile. Compilation derives a new immutable Production Package revision with a populated `action_performance` section and `action_performance_complete` validation marker. Historical foundation/revision packages remain preserved.

The compiled representation is provider-neutral and contains no model, renderer, workflow, sampler or prompt-specific settings.

## Workspace

The existing left navigation item `Production Planning` becomes the Phase 19.4 workspace. Current approved Shots and Production Packages are listed on the left; the Action & Performance editor is shown on the right. Later Phase 19.4 compilers extend this same workspace.

## Staleness and recovery

If upstream approved planning changes, the Production Package source fingerprint changes. The existing Action & Performance record is then stale and cannot be edited or compiled as current authority until reviewed against the new package.

A stale Draft exposes `Refresh from Current Shot`. This operation rebases only the draft's source Production Package identity/fingerprint while preserving all authored temporal narrative, dialogue, performance, opening/closing state and timing content. After refresh the Draft becomes current and editable again. A stale Ready record must first be returned to Draft, then refreshed against the current Shot before review and recompilation.

## Acceptance corrections

Phase 19.4.2 acceptance also normalizes legacy `isinstance()` union syntax required by the current Ruff UP038 rule. These syntax-only corrections do not change runtime validation behaviour and keep local development and CI quality gates aligned.

## Acceptance criteria

- left-side Production Planning placeholder is replaced with the real Phase 19.4 workspace;
- current approved Shots automatically materialize canonical Production Packages;
- Create from Shot does not invent story content;
- temporal narrative is required for Ready;
- Ready records are immutable until Return to Draft;
- stale Drafts can be refreshed against current approved planning without losing authored content;
- Ready compilation populates only `action_performance` and preserves other package sections;
- provider-specific controls are absent;
- persistence survives project reopen;
- changed Phase 19.3 source makes the Action & Performance record stale;
- Ruff, format, mypy, focused pytest, full pytest and coverage gates pass.
