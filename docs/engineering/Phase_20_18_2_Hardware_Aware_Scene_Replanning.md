# Phase 20.18.2 — Hardware-Aware Scene Replanning

## Decision

Phase 20.18.2 no longer treats a long governed Shot as one provider job that is
secretly segmented and reassembled. The authoritative planning flow is now:

Story / Ready Scene authority
→ Hardware-aware Shot Planning
→ one governed short Shot
→ downstream specialist planning
→ one normal provider execution.

For the validated RTX 4060 8 GB LTX-2.3 profile, the governed Shot ceiling is
7 seconds. At 24 fps this is 168 governed frames; provider-only frame adaptation
may use 169 frames to satisfy the LTX 8n+1 rule, with governed output restored
before media authority is created.

## Governed replanning behavior

The authoritative Shot Planner exposes **Re-plan Scene from Story** only when the
upstream Scene is Ready and current.

The action:

1. reads the current persisted hardware capability, using the conservative 7-second
   safe default if no live snapshot has yet been persisted;
2. derives the number of Shots needed to cover the complete Scene runtime;
3. proposes a deterministic replacement plan without mutating current authority;
4. shows the current/proposed Shot counts, hardware limit, Scene runtime and an
   initial Shot preview;
5. requires explicit human confirmation;
6. archives the existing governed Shot Plan under
   `planning/shot_plan_history/<scene_id>/`;
7. replaces the current Scene Shot Plan with new Draft Shots;
8. preserves the exact Scene runtime while keeping every Shot within the active
   hardware ceiling.

New Shots remain Draft so narrative purpose, required action, continuity and
downstream specialist planning can be reviewed before advancing.

## Authority and provenance

The Ready Scene remains the upstream authority. Replanning does not rewrite Scene
authority, delete prior Shot history, or bypass planning review. Old Shot Plans are
archived before replacement. Existing downstream planning remains subject to its
normal source-fingerprint/current-authority checks.

## UI acceptance

For a 3:00 Scene on the validated 8 GB profile:

- the Shot Planner shows the hardware-aware 7-second ceiling;
- **Re-plan Scene from Story** is enabled only for a current Ready Scene;
- the proposal contains enough Shots to cover all 180 seconds;
- no proposed Shot exceeds 7 seconds;
- confirmation archives the old plan and replaces it with Draft Shots;
- manual New/Edit runtime controls cannot exceed 7 seconds.

## Phase state

This implementation does not close Phase 20.18.2. Local automated validation,
UI acceptance, downstream replanning, one-Shot provider execution, GeneratedMedia
provenance and explicit owner acceptance remain required.
