# ADR-0030 — Lighting Production Authority

## Status
Accepted for Phase 19.4.5 implementation.

## Decision
Phase 19.4.5 introduces a governed, provider-neutral Lighting Compiler between approved Phase 19.3 Lighting Planning and later provider-specific prompt/workflow compilation.

The compiler SHALL:

- seed only from the current approved Production Package Lighting Plan;
- preserve the governed Lighting Plan verbatim as provenance-bearing authority;
- derive a normalized production Lighting view without provider/model syntax;
- preserve continuity notes and Lighting constraints rather than recreating them downstream;
- support Draft, Ready, Return-to-Draft and stale-source recovery;
- preserve human review notes during source refresh;
- require explicit user approval before Ready/Compile;
- append an immutable Production Package revision with `lighting_complete=true`.

The compiler SHALL NOT:

- invent missing Lighting intent;
- override or silently replace the governed Lighting Plan;
- select ComfyUI models/workflows;
- emit renderer/provider prompt syntax;
- auto-approve Lighting authority on behalf of the user.

## Rationale
Lighting is a major contributor to visual continuity. VSCS must carry established lighting state forward as structured production authority rather than rely on repeated prompt wording. Automation should prepare and inherit governed Lighting information, while final creative approval remains with the user.
