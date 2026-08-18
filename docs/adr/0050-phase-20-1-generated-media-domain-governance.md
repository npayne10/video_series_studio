# ADR 0050 — Phase 20.1 Generated Media Domain & Governance

## Status

Accepted for implementation; local validation pending.

## Context

Phase 19 established provider-neutral ProductionTask compilation, readiness, resource scheduling, explicit human schedule review, ProductionQueue runtime coordination, worker/lease/retry handling, monitoring/recovery, and integrated production readiness. Phase 20 connects that orchestration architecture to live production providers and introduces authoritative Generated Media management.

The repository already contains renderer-neutral `RenderOutput` records. `RenderOutput` is intentionally an execution-layer artifact: it identifies what a renderer produced for one request and contains renderer/workflow provenance. It is not an authoritative production-media object and does not own production governance.

Live provider execution will produce files that need stable VSCS identity, production ownership, provenance, governance state, review history, and later persistence/versioning. Provider execution must therefore not become the source of truth for production media.

## Decision

1. Introduce `GeneratedMedia` as a new authoritative VSCS domain object under `vscs.domain.generated_media`.
2. `GeneratedMedia` owns stable media identity, provider-neutral media kind, production/episode/scene/shot/ProductionTask scope, execution provenance, project-relative file identity, technical metadata, revision, governance state, and immutable governance history.
3. Provider details such as provider ID, provider job ID, workflow ID, worker ID, render request ID, and RenderOutput ID are retained only as provenance. They do not control media identity, approval, selection, or lifecycle authority.
4. Existing `RenderOutput` remains unchanged. It is an execution result. A later ingestion phase may create a `GeneratedMedia` record from one or more provider outputs, but Phase 20.1 does not add that mapper.
5. Generated Media lifecycle states are `GENERATED`, `UNDER_REVIEW`, `APPROVED`, `REJECTED`, `INVALID`, and `SUPERSEDED`.
6. New Generated Media starts only in `GENERATED`. Direct construction as approved/rejected/superseded is invalid without matching governance history.
7. Human review is explicit. Approval and rejection are permitted only from `UNDER_REVIEW`; provider completion, technical validation, or AI assistance cannot silently approve media.
8. `INVALID` is distinct from `REJECTED`: invalidation represents unusable/technically invalid media, while rejection represents an explicit governance decision that otherwise valid media is unsuitable for production use.
9. Only `APPROVED` media may be `SUPERSEDED`, and supersession must identify a separate replacement media identity.
10. Governance transitions are immutable and append an auditable event containing source state, target state, actor, reason, timestamp, and replacement media identity where applicable.
11. Project-relative file paths are mandatory. Optional SHA-256 checksum and file size belong to file identity but Phase 20.1 does not inspect or persist physical files.

## Consequences

- VSCS, not a provider, owns generated production media authority.
- Provider changes do not alter the Generated Media governance model.
- Existing renderer contracts remain backward compatible.
- Future ingestion can preserve `RenderOutput` provenance while registering a separate authoritative media object.
- Human approval remains an explicit governance boundary before media becomes approved production material.
- Technical invalidation can be represented without conflating technical failure with creative rejection.

## Deliberately deferred

- Generated Media repository and project persistence (20.2).
- Provider execution contract modernisation (20.3).
- Provider registry/configuration and capability resolution (20.4).
- Live ComfyUI execution (20.5).
- Queue-to-provider execution integration (20.6).
- Durable provider execution jobs and attempts (20.7).
- Live provider monitoring/recovery (20.8).
- Provider output ingestion into Generated Media (20.9).
- File probing and technical validation (20.10).
- Review UI and persistence of review decisions (20.11 and later persistence work).
- Full version/variant selection and supersession lineage rules (20.12).
- ProductionTask completion reconciliation (20.13).
- Generated Media and execution UI (20.14–20.15).
- Restart/provider reconciliation (20.16).
- Multi-provider proof and final Phase 20 acceptance (20.17–20.18).
