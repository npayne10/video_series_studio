# ADR-0028 — Scene → Shot Proposal Automation

## Status

Accepted

## Context

Phase 19.5.3 produces reviewable Episode and Scene automation proposals without mutating the authoritative Phase 19.3 planners. The next automation boundary must derive production-useful Shot intent from those Scene proposals while preserving the established ownership boundary of `GovernedShotPlanningService`.

The governed Shot Planner already owns renderer-neutral Shot fields such as narrative purpose, production objective, runtime, required action, dialogue requirement, continuity boundaries and Shot constraints. Camera, lighting, assets and environment remain separate specialist planning concerns.

## Decision

Phase 19.5.4 introduces `SceneShotProposalAutomationService` and a provider-neutral `SceneShotProposalProvider` contract.

The service:

- consumes current Phase 19.5.3 `SCENE` proposals for the same Story revision;
- uses cached Story Analysis context rather than rerunning Story semantic interpretation;
- generates only `SHOT` `AutomationProposal` records;
- mirrors the renderer-neutral intent fields owned by the existing governed Shot Planner;
- assigns stable target identities using the governed `{scene_id}-SHT-{sequence:03d}` convention;
- preserves lineage to the parent Scene proposal;
- validates contiguous Shot sequence numbers and prevents proposed Shot runtime from exceeding the Scene proposal runtime budget;
- records provider/model identity, confidence, Story revision and source fingerprint provenance;
- never creates `ShotPlan` authority and never invokes `mark_ready` or approval behaviour.

The OpenAI provider may semantically decompose a Scene into Shots, but it is explicitly prohibited from choosing camera lenses, camera movement, lighting design, canonical assets, renderer models or provider-specific prompt language. Those remain later governed specialist phases.

A deterministic template provider remains available for tests and offline development.

## Governance Boundary

`SCENE AutomationProposal → SHOT AutomationProposal` is a proposal transformation only.

A Shot proposal is not a `ShotPlan`, is not Ready, is not Approved, and is not production authorization. Conversion into governed planning authority remains a later explicit human-governed automation phase.

## Consequences

- Story decomposition can now continue from Story → Episode → Scene → Shot without manual Shot drafting.
- Existing Phase 19.3 Shot Planning remains the sole authoritative Shot source.
- Runtime budget errors are caught before proposals can later be consumed by planning authority.
- Specialist concerns remain separated, preventing semantic automation from collapsing Camera, Lighting, Assets and Environment into Shot authority.
- The same Scene/Shot automation contract applies to trailers, episodes, series and feature productions.
