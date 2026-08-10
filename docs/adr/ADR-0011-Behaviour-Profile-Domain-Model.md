# ADR-0011 — Behaviour Profile Domain Model

**Status:** Accepted  
**Decision scope:** Production behaviour knowledge  
**Phase:** 19.2.1 — Behaviour Profile Domain Model

## Context

Phase 19.1 established structured Canonical Asset Profile knowledge describing what an asset is, including facts, capabilities, constraints, classifications and behaviour references. Phase 19.2 must describe how production assets behave without encoding provider prompts, UI state, persistence details or renderer-specific implementation choices.

The behaviour representation must support very different production assets — for example a ship docking, a character walking, a prop being operated or an effect transitioning — while remaining deterministic enough for later readiness, planning, projection and prompt-compilation phases.

## Decision

1. VSCS introduces **Behaviour Profiles (BEPs)** as the canonical domain representation of how production assets behave.
2. A BEP is independent of a specific CAP instance. It declares one or more applicable asset categories and may later be referenced by CAP structured knowledge.
3. Every BEP has a stable `BEP-` identifier, version, name, machine-readable action identifier and high-level behaviour category.
4. Behaviour inputs are represented as typed parameters with optional units, numeric bounds and enumerated values.
5. Preconditions are deterministic subject/operator/value expressions rather than natural-language-only conditions.
6. Canonical behaviour constraints are distinct from parameters and carry production significance.
7. Outcomes represent observable results or resulting states.
8. Interaction requirements describe required counterpart roles, applicable asset categories and capabilities without coupling the domain to a particular scene or renderer.
9. BEPs preserve governance authority and provenance. Draft and Proposed profiles are not production authority; Approved and Canonical profiles are.
10. The Phase 19.2.1 domain model is immutable and provider-neutral. Persistence, repositories, services, UI, CAP linking, readiness and projection are deferred to later Phase 19.2 sub-phases.

## Consequences

- CAP continues to answer **what an asset is** while BEP answers **how an asset behaves**.
- Production Planning can eventually reason over structured actions, requirements and outcomes instead of parsing prose.
- Behaviour definitions can be reused across many assets and productions where their applicability rules match.
- Renderer or AI-provider changes do not alter canonical behaviour knowledge.
- Later persistence work can evolve independently while preserving the public domain contract.

## Alternatives considered

### Store behaviours as free-form CAP prose
Rejected because planning, readiness and prompt compilation would repeatedly reinterpret natural language and could derive inconsistent results.

### Store behaviours directly inside each CAP
Rejected as the primary model because shared behaviours such as walking, docking or operating a console should be reusable and versionable independently. CAPs will reference approved Behaviour Profiles instead.

### Provider-specific behaviour templates
Rejected because provider constraints and prompts are compiled outputs, not canonical production knowledge.

## Future notes

Phase 19.2.2 will define persistence and repository contracts for Behaviour Profiles. Later Phase 19.2 work will add governance services, editing, CAP integration, readiness, projection, AI proposals and migration support without changing the fundamental BEP responsibility defined here.
