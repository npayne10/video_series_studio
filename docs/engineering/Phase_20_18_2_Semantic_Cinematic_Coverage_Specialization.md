# Phase 20.18.2 — Semantic Cinematic Coverage Specialization

## Decision

Hardware-safe child Shots must be distinct editorial units, not mechanical
"begin / continue / complete" fragments.

After semantic source recovery and hardware decomposition, VSCS now assigns each
child Shot an explicit renderer-neutral cinematic coverage role before any Asset,
Camera, Lighting or Environment planning occurs.

The authoritative flow is:

Ready Scene / Story authority
→ richest semantic Shot authority
→ hardware-safe duration decomposition
→ cinematic coverage specialization
→ Draft governed Shots
→ downstream specialist planning
→ one provider execution per Shot.

## Coverage roles

The governed Shot contract now carries one of these editorial roles:

- `establishing`
- `primary_subject`
- `secondary_subject`
- `detail_insert`
- `dialogue_delivery`
- `reaction`
- `progression`
- `resolve`
- `unspecified` for legacy/manual authority not yet specialized

Roles remain renderer-neutral. They express what the Shot must accomplish, not a
specific lens, camera move, lighting setup or provider implementation.

## Specialization rules

For a decomposed semantic beat:

- the first child establishes geography and state;
- the final child resolves the beat and hands off editorially;
- dialogue-bearing beats assign one interior child to governed dialogue delivery;
- remaining interior coverage rotates through subject focus, information-bearing
  detail/insert, reaction, secondary subject and progression roles as the number of
  required child Shots increases.

Every role receives a distinct Narrative Purpose and Required Action. The generated
instruction explicitly tells downstream planning not to repeat the establishing
composition when an insert, subject shot, reaction or progression shot is required.

Dialogue is attached to exactly one dialogue-delivery child and explicitly forbids
invented additional spoken content.

## Provenance

Each specialized child retains:

- the semantic source Shot identity and title;
- the original production objective;
- the original beat runtime through exact child-runtime distribution;
- incoming and outgoing continuity;
- source constraints;
- a durable `Cinematic coverage role: <role>` constraint.

The replan archive metadata records
`semantic-cinematic-coverage-v1` as the decomposition strategy.

## UI

The governed Shot Planner now exposes a **Coverage Role** column so the human reviewer
can verify that a decomposed beat contains distinct editorial coverage before any Shot
is marked Ready.

## Acceptance

For the current Xorix Scene, acceptance requires:

- all 29 Shots remain within the 7-second hardware ceiling;
- the Scene remains exactly 180 seconds;
- original semantic beat grouping remains visible;
- child Shots have explicit, non-repetitive coverage roles;
- Required Action differs according to those roles;
- dialogue is carried by one intended child rather than copied across the group;
- all Shots remain Draft until human review;
- existing archive/provenance remains intact.

Phase 20.18.2 remains open until local automated validation, UI review, downstream
planning, live provider execution, GeneratedMedia provenance and explicit owner
acceptance all pass.
