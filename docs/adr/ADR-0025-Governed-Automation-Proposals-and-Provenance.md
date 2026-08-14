# ADR-0025 — Governed Automation Proposals and Provenance

## Status

Accepted

## Context

Phase 19.5 introduces production automation above the authoritative Phase 19.3 planning hierarchy and Phase 19.4 compilation pipeline. VSCS already owns governed Episode, Scene, Shot and specialist planning boundaries. Automation must reduce manual work without creating a competing source of production truth, weakening canonical continuity, or allowing an AI provider to approve production authority.

VSCS also already contains deterministic Story Analysis, entity resolution, CAP/XPD authority and provider-neutral AI patterns. Phase 19.5 must extend those capabilities rather than replace them.

## Decision

VSCS introduces a provider-neutral `AutomationProposal` boundary.

Automation follows the rule:

`AI interprets → VSCS resolves → automation proposes/propagates → humans govern`.

An Automation Proposal:

- targets an existing governed planning or production boundary;
- contains structured proposed content rather than directly mutating authority;
- records explicit provenance for Story facts, AI inference, deterministic resolution and manual contribution;
- records Story identity and revision, source scope, confidence, provider/model identity where applicable, inference notes and resolution method;
- progresses only through `Proposed → Reviewed → Accepted` or `Rejected`;
- is consumable by a governed planner only after explicit human acceptance;
- never represents `Ready`, `Approved`, production authorization or provider execution authority.

AI providers implement a semantic proposal protocol only. They are not passed authoritative planning services and therefore have no approval capability.

Known canonical entities must be resolved through deterministic VSCS services such as XPD/Asset/CAP resolution rather than repeatedly asking AI to rediscover known identity. This preserves continuity and reduces semantic drift.

The same automation contracts apply regardless of project scale. Trailer, episode, series and feature-film production differ in scope, not in governance or continuity standards.

## Consequences

- Phase 19.5 can automate aggressively without creating a second production authority.
- Every AI-derived decision can remain distinguishable from Story fact and deterministic resolution.
- Human approval remains in the existing governed planners and review services.
- Existing Story Analysis, entity resolution and Phase 19.3/19.4 services remain reusable.
- Future semantic providers can be added behind a stable application protocol.
- Continuity remains based on canonical authority rather than prompt similarity.

## Explicit non-goals for Phase 19.5.1

- no OpenAI story interpretation implementation;
- no automatic Scene or Shot creation;
- no automatic Ready/Approved transitions;
- no replacement of SSIE, Story Analysis, governed planners, CAP/XPD resolution or Phase 19.4 compilers.
