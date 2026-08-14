# ADR-0026 — Semantic Story Interpretation

## Status

Accepted

## Context

Phase 19.5 requires semantic understanding of Story authority before automated production planning can begin. VSCS already has a mature Phase 18 Story Analysis pipeline, an optional OpenAI structured-output enrichment provider, deterministic entity resolution against project XPD assets, source evidence spans, and human-reviewed Story Intelligence.

Creating a second semantic engine would duplicate those capabilities and risk divergent entity identity and continuity behaviour.

## Decision

Phase 19.5.2 reuses the existing Story Analysis and `EntityResolutionService` as its semantic intelligence source.

`SemanticStoryInterpretationService` converts that existing result into the Phase 19.5 governed `AutomationProposal` contract. It:

- requires Story identity and an explicit source revision;
- rejects a baseline from another Story or a stale revision;
- preserves the existing source-grounded entity evidence;
- preserves deterministic XPD matching results rather than asking AI to rediscover known canonical identity;
- records a SHA-256 fingerprint of the interpreted source;
- records narrative metadata and production-relevant entity proposals;
- persists the result as a `STORY_INTERPRETATION` proposal;
- never creates Episode, Scene, Shot, Asset or specialist planning authority;
- never sets Ready or Approved state;
- never submits provider work.

The existing OpenAI Story Analysis provider remains optional. When configured, AI performs semantic extraction only. Canonical entity matching remains deterministic VSCS logic, and all resulting automation remains reviewable under ADR-0025.

## Consequences

- Phase 19.5 gains semantic interpretation without replacing Phase 18 Story Intelligence.
- Existing Xorix XPD assets can be reused when they are available to the active project/catalog.
- New entities remain proposals rather than silently becoming canonical assets.
- Story revision drift is detected before semantic automation is propagated.
- Later Phase 19.5 stages can consume one stable proposal contract independent of the configured AI provider.

## Non-goals

Phase 19.5.2 does not perform Story-to-Scene decomposition, Shot creation, CAP generation, Master Reference generation, continuity propagation, or production approval. Those remain later governed phases.
