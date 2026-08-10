# ADR-0016 — Episode Planner

## Status

Accepted

## Context

Phase 19.3 begins Production Planning. The Episode Planner is the first planning layer between approved Story knowledge and later Scene, Shot, Asset, Camera, Lighting and Environment planning.

The planner must not become an administrative metadata store. Every persisted value must have a direct downstream production purpose, support automation or continuity, reduce repeated operator input, or encode a production/physical-reality constraint that later planners must enforce.

## Decision

VSCS introduces a project-backed `EpisodePlan` contract owned by one first-class Story.

An Episode Plan persists only:

- stable episode identity and sequence;
- source Story identity;
- episode title;
- Story scope being adapted;
- production objective;
- target runtime;
- continuity entering the episode;
- continuity leaving the episode;
- explicit production or grounded-reality constraints;
- Draft or Ready planning state.

Episode Plans are stored in `planning/episode_plans.json` with an explicit schema version. Ready plans are immutable until deliberately returned to Draft.

The Episode Planner does not persist scene counts, asset selections, shot structure, camera decisions, lighting decisions or environment decisions. Those belong to later Phase 19.3 planners and must be derived there instead of duplicated here.

## Consequences

- Scene Planning receives a small deterministic episode contract rather than free-form production notes.
- Continuity has an explicit episode boundary before scene decomposition begins.
- Grounded-reality constraints can propagate to later planning stages without hard-coding science-fiction assumptions into individual shots.
- Operators do not have to enter information that later services can derive.
- Ready/Draft state provides a clear automation boundary for Phase 19.3.2.

## Alternatives considered

### Store a full television production breakdown at episode level

Rejected because it duplicates information that belongs to Scene, Shot and specialist planners and increases continuity drift.

### Keep episode planning as free-form notes

Rejected because downstream automation cannot reliably consume unstructured planning prose.

### Reuse legacy scene `episode_id` values without an Episode Plan

Rejected because an identifier alone does not define source scope, runtime, continuity boundaries or production constraints.

## Future notes

Phase 19.3.2 Scene Planner should consume only Episode Plans in `Ready` state and inherit episode continuity and constraints rather than asking the operator to re-enter them.
