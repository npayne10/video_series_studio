# Phase 20.18.2 — Semantic Hardware-Aware Shot Decomposition

## Decision

Hardware-aware replanning must preserve narrative Shot authority before applying the
GPU/provider runtime ceiling. VSCS must not divide a Scene into anonymous equal-duration
chunks.

The governed flow is:

Story / Ready Scene
→ semantic Shot authority
→ semantic source recovery from current or archived governed Shot Plans
→ per-beat hardware decomposition
→ short Draft governed Shots
→ downstream specialist planning
→ one normal provider execution per Shot.

## Semantic source selection

The replanner considers:

1. the current governed Shot Plan;
2. preserved Shot Plan archives under
   `planning/shot_plan_history/<scene_id>/`;
3. a Ready Scene event-based fallback only when no complete governed semantic plan
   covers the Scene runtime.

Only candidates whose total Shot runtime exactly matches the Ready Scene runtime are
eligible. Candidates are scored for narrative specificity. Generic hardware-generated
labels such as `Story Beat NNN`, `Establish — ...`, and `Close — ...` are penalised,
while distinct titles, narrative purposes, required actions and dialogue requirements
increase semantic density.

This allows a previously archived seven-beat narrative plan to outrank a later generic
26-shot hardware plan without deleting either history.

## Hardware decomposition

Each semantic source Shot is decomposed independently using the current validated
hardware limit. For the validated RTX 4060 8 GB LTX-2.3 profile the maximum governed
Shot runtime is 7 seconds.

For each semantic source Shot, VSCS preserves:

- source title and semantic identity;
- narrative purpose;
- production objective;
- required action;
- dialogue intent without duplicating the same line across every child Shot;
- incoming and outgoing continuity;
- source Shot provenance in Shot constraints.

Long semantic beats become intentional editorial coverage such as Establish, Detail,
Reaction, Coverage, Progression, Response and Resolve. Runtime is distributed within
each semantic beat so the source beat duration and complete Scene duration are both
preserved exactly.

## Governance

The current plan is archived before replacement. New decomposed Shots remain Draft.
No downstream Asset, Camera, Lighting, Environment, Planning Review, compilation or
provider authority is bypassed.

The confirmation UI exposes the semantic source provenance and source beat count before
the human approves replacement.

## Acceptance

For the current 3:00 Xorix Scene, acceptance requires:

- semantic source recovery identifies the richer archived pre-hardware narrative plan;
- every resulting Shot is at most 7 seconds;
- the complete Scene remains exactly 180 seconds;
- generated titles remain traceable to meaningful source beats rather than generic
  `Story Beat NNN` labels;
- dialogue is carried intentionally and not duplicated across every decomposed Shot;
- previous current authority is archived before replacement;
- all new Shots are Draft.

Phase 20.18.2 remains open until automated, UI, downstream planning, live provider and
GeneratedMedia acceptance all pass and the owner explicitly accepts the phase.
