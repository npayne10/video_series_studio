# ADR-0027 — Episode/Scene Proposal Automation

## Status

Accepted

## Context

VSCS already has authoritative Phase 19.3 Episode and Scene planners. Phase 19.5 must automate production planning without introducing a second source of truth or allowing AI to create Ready/Approved planning authority directly.

Phase 19.5.2 established source-revision-aware Semantic Story Interpretation. Phase 19.5.3 must transform that interpretation into production-useful Episode and Scene structure while preserving the existing planning boundaries.

## Decision

VSCS introduces `EpisodeSceneProposalAutomationService` above the authoritative Episode and Scene planners.

The service:

- consumes the same Story revision used by deterministic Story Analysis and Semantic Story Interpretation;
- rejects stale or cross-Story analysis/semantic inputs;
- uses a provider-neutral `EpisodeSceneProposalProvider` boundary;
- supports a deterministic offline provider for tests/development;
- supports OpenAI structured output when the configured AI provider is available;
- creates `EPISODE` and `SCENE` `AutomationProposal` records only;
- preserves episode/scene sequence, story scope, production objective, runtime, setting requirements, required events, continuity and constraints;
- fingerprints the source Story and links every proposal back to the Phase 19.5.2 semantic proposal;
- never calls `EpisodePlanningService.create`, `ScenePlanningService.create`, `mark_ready`, or any approval service;
- never creates provider execution authority.

A short self-contained Story should normally remain one Episode. AI may propose multiple Episodes only when the supplied source clearly warrants it.

## Governance

The Phase 19.3 models remain authoritative. Episode/Scene automation produces reviewable proposals, not planning records.

The intended boundary is:

`Story → Semantic Interpretation → Episode/Scene Proposals → Human Review → later governed consumption → existing Episode/Scene planners`

Proposal acceptance is not equivalent to Episode/Scene Ready state. Later Phase 19.5 orchestration is responsible for explicit proposal consumption while preserving human governance.

## Continuity and consistency

The provider is instructed not to invent unsupported characters, locations, props, technology or events. Canonical identity remains the responsibility of deterministic VSCS entity/XPD resolution. The same proposal contracts apply to trailers, episodes, series and feature productions; project scale changes scope, not governance.

## Consequences

- VSCS can automate Story decomposition without replacing Phase 19.3 planners.
- Provider choice is isolated behind a stable protocol.
- Offline tests remain deterministic.
- AI-derived planning structure remains explicitly distinguishable by provenance.
- Story revision changes invalidate the proposal-generation input boundary.

## Non-goals

Phase 19.5.3 does not create Shot proposals, consume accepted proposals into authoritative planners, mark Episode/Scene plans Ready, approve production authority, create CAPs/Master References, or submit provider jobs.
