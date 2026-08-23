# ADR 0070 — Phase 20.17 Wan 2.2 Provider Capability Validation

## Status

Accepted for implementation in Phase 20.17.

## Context

VSCS can register and execute providers, ingest their outputs as authoritative Generated Media, and govern those media independently of the provider. Before a new generation capability is treated as production-ready, VSCS needs repeatable evidence that the provider can satisfy the production behaviours expected of that capability.

Wan 2.2 is the first capability evaluated through this mechanism. Embedding Wan-specific quality rules in the core provider registry, ProductionTask domain, or Generated Media lifecycle would violate the provider-neutral architecture and would incorrectly allow provider implementation details to influence VSCS authority.

A computed quality recommendation must also remain distinct from the human decision to approve or reject a capability for production use.

## Decision

1. Introduce a provider-neutral capability-validation domain consisting of validation packs, scenarios, criteria, evidence-linked results, computed recommendations, and explicit human decisions.
2. Keep concrete provider validation definitions at the infrastructure/provider edge. The Wan 2.2 video pack is identified as `wan-2.2-video-v1` and validates five required scenarios:
   - text-to-video baseline;
   - image-to-video reference fidelity;
   - camera and motion control;
   - character/subject continuity;
   - complex production shot.
3. Validation evidence references existing VSCS Generated Media IDs. The validation service verifies that evidence exists and was produced by the provider under validation. It never changes Generated Media identity, lifecycle state, selection, or approval.
4. A completed required scenario must contain Generated Media evidence and explicit criterion outcomes recorded by a human actor.
5. Recommendation is deterministic:
   - missing or blocked required scenario => `insufficient_evidence`;
   - any failed required scenario => `not_recommended`;
   - all required scenarios pass with optional failures => `conditional`;
   - all required scenarios pass => `recommended`.
6. Recommendation does not approve or reject provider capability. Human authority remains a separate `pending`, `approved`, or `rejected` decision with actor, reason, and timestamp.
7. Persist capability-validation sessions separately from provider registration, execution jobs, ProductionTasks, and Generated Media.
8. Provide an operator workspace for recording criterion outcomes, linking Generated Media evidence, reviewing the computed recommendation, and making an explicit human decision.

## Consequences

- The validation framework can be reused for future providers without changing core Generated Media or ProductionTask models.
- Wan 2.2 criteria can evolve through a versioned provider-edge validation pack.
- Provider capability claims are no longer equivalent to production acceptance; they can be backed by durable evidence.
- Generated Media remains the authoritative VSCS representation of generated outputs.
- Automated recommendation cannot silently grant production authority.
- Re-recording evidence resets a previous human decision to `pending`, ensuring the decision always applies to the current evidence set.

## Exclusions

Phase 20.17 does not:

- modify LTX 2.3 remediation or provider workflows;
- bypass production execution governance or attempt limits;
- automatically enable, disable, rank, or select a provider from a validation recommendation;
- approve Generated Media;
- make Wan-specific types part of the provider-neutral domain.
