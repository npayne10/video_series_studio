# ADR-0029 — Camera Production Authority

## Status
Accepted for Phase 19.4.4 implementation.

## Decision
Phase 19.4.4 introduces a governed, provider-neutral Camera Compiler between approved Phase 19.3 Camera Planning and later provider-specific prompt/workflow compilation.

The compiler SHALL:

- seed only from the current approved Production Package Camera Plan;
- preserve the governed Camera Plan verbatim as provenance-bearing authority;
- derive a normalized production Camera view without provider/model syntax;
- preserve screen-direction and continuity constraints rather than recreating them downstream;
- support Draft, Ready, Return-to-Draft and stale-source recovery;
- preserve human review notes during source refresh;
- require explicit user approval before Ready/Compile;
- append an immutable Production Package revision with `camera_complete=true`.

The compiler SHALL NOT:

- invent missing Camera intent;
- override or silently replace the governed Camera Plan;
- select ComfyUI models/workflows;
- emit renderer/provider prompt syntax;
- auto-approve Camera authority on behalf of the user.

## Rationale
VSCS automation should prepare production intelligence automatically wherever governed upstream information exists, while final creative approval remains with the user. Camera continuity is production state, not merely prompt wording, so screen direction, lens intent, framing and movement constraints must remain structured and traceable through later stages.
