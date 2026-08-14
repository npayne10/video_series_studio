# ADR-0031 — Environment Production Automation

## Status
Accepted for Phase 19.5.7 implementation.

## Decision
Phase 19.5.7 may interpret current Shot and Action/Performance proposals into reviewable physical Environment proposals. It reuses the governed Phase 19.3.7 Environment contract and enums for environment context, time context, atmosphere, weather, optional physical values, surface state, environmental motion, hazards, continuity and constraints.

AutomationProposal remains the only persistence authority for Phase 19.5.7 output. Environment automation must not call GovernedEnvironmentPlanningService.create_suggested(), create(), update(), mark_ready() or any other governed planning mutation.

Unknown physical values are first-class. AI and deterministic automation must preserve gravity, pressure, temperature, visibility, atmospheric composition, weather and hazards as unknown when the Story does not establish them. Plausibility is not permission to invent canon.

Environment automation owns physical-world interpretation only. It must not decide camera framing or lenses, lighting/exposure, canonical Asset identity, visual style, renderer prompts, provider models or production approval.

Every Environment proposal retains current Story revision provenance and lineage to both the parent Shot proposal and its current Action/Performance proposal. Current Action/Performance proposals are required before Environment proposals are generated.

The shared Review Proposals surface remains the human inspection mechanism. Proposal generation is not acceptance, Ready state or production authority.
