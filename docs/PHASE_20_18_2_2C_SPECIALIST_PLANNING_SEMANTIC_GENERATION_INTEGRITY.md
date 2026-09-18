# Phase 20.18.2.2c — Specialist Planning Semantic Generation Integrity

## Problem

SHT-001 exposed two systemic generation defects that could affect future stories and
Shots even when every governance object was current and Ready.

### Camera polarity inversion

The camera suggestion engine searched the full governed Shot text for keywords.
SHT-001 correctly contained the negative guardrail:

`Do not spend this Shot on a close reaction or insert.`

The word `reaction` was nevertheless treated as affirmative camera intent. Because
the reaction rule ran after the establishing rule, it overwrote the correct wide
establishing suggestion with a close-up / 85 mm portrait / push-in reaction plan.

### Future Scene continuity leakage

Environment continuity concatenated, for every Shot:

1. Scene continuity-in
2. Shot continuity-in
3. Shot continuity-out
4. Scene continuity-out

Scene continuity-out describes the state at the end of the Scene. Applying it to
SHT-001 leaked later story knowledge into an earlier Shot before Sandra had reported
the anomaly.

## Correction

Camera generation now:

- evaluates lexical camera hints with negation awareness;
- ignores keyword occurrences governed by phrases such as `do not`, `must not`,
  `never`, `avoid`, `without` and `no`;
- treats explicit `CinematicCoverageRole` as stronger authority than lexical hints;
- deterministically maps establishing, dialogue-delivery, reaction and detail-insert
  coverage to suitable framing families.

Environment continuity now treats Scene continuity as boundary authority:

- Scene continuity-in is included only for the first governed Shot;
- Scene continuity-out is included only for the last governed Shot;
- every Shot always carries its own continuity-in and continuity-out;
- middle Shots receive neither Scene boundary state.

## Acceptance intent

The regression suite proves that:

- a negative `reaction` guardrail cannot create reaction framing;
- a negative `move/track` guardrail cannot create camera tracking;
- explicit Reaction coverage still produces reaction framing;
- Establishing coverage remains wide even when Shot text contains a negative
  close-reaction sentence;
- an early Shot cannot inherit future Scene continuity-out;
- middle Shots receive only Shot-local continuity;
- the final Shot receives Scene continuity-out.

Existing SHT-001 planning data must still be regenerated from the corrected services.
The code fix prevents recurrence; rebuilding the current Camera and Environment plans
is the migration step for already-persisted stale outcomes.
