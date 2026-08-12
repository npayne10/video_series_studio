# ADR-0031 — Continuity Production Authority

## Status
Accepted for Phase 19.4.6 implementation.

## Decision
VSCS SHALL treat continuity as structured inherited production state rather than prompt prose.

The Continuity Compiler SHALL:

- derive state from the current Shot and immediately preceding current Shot;
- inherit previous closing state automatically when current opening state is not explicitly governed;
- preserve explicit current opening state and expose mismatches as review conflicts;
- carry canonical asset identities, screen direction, lighting continuity and environment context forward as structured evidence;
- track both current and previous continuity-relevant dependencies for staleness;
- preserve human review notes during refresh;
- require explicit user approval before Ready/Compile;
- append an immutable Production Package revision with `continuity_complete=true`.

The compiler SHALL NOT:

- invent a previous state for the first Shot;
- silently rewrite a governed current opening state to match inheritance;
- generate renderer/provider prompt syntax;
- select ComfyUI models or workflows;
- auto-approve final continuity authority.

## Rationale
Continuity is a series-scale production requirement. A Shot should begin from the state established by preceding approved production unless the story explicitly changes it. Encoding this relationship as structured, dependency-tracked authority makes downstream image/video generation and later AI automation able to preserve people, assets, locations, lighting and spatial relationships consistently while retaining user control over final approval.
