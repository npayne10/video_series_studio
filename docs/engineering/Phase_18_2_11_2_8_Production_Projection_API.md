# Phase 18.2.11.2.8 — Production Projection API

## Purpose

Publish a stable, read-only, repository-independent canonical asset contract for Production
Planning and later VSCS production subsystems.

Downstream systems must not read CAP repository models, reference-library persistence, or UI
state directly. They consume `ProductionProjection` through `ProductionProjectionService`.

## Public contract

`ProductionProjection` is immutable and schema-versioned. It publishes:

- canonical identity and CAP version;
- canonical description;
- structured facts when persistence provides them;
- visual identity;
- structured functional capabilities when persistence provides them;
- structured canonical constraints when persistence provides them;
- production guidance;
- only Approved or Locked production references;
- the authoritative Phase 18.2.11.2.7 `ReadinessReport`;
- a deterministic SHA-256 checksum for caching and dependency invalidation.

The projection does not contain scene, shot, camera, renderer, workflow, UI, database, or
repository state.

## Application API

`ProductionProjectionService` is registered in the VSCS `ApplicationServices` composition
root and exposes:

- `project(asset_id)` — diagnostic projection, including readiness blockers;
- `require_ready(asset_id)` — enforced projection that raises
  `ProductionProjectionBlockedError` unless Production Readiness is Ready;
- `project_all()` — deterministic asset-ID ordered projections;
- `production_ready()` — only production-ready projections;
- `checksum(asset_id)` — deterministic projection fingerprint.

## Readiness policy

Projection publication and production authorization are intentionally separate.

A blocked asset may still be projected through `project()` so Production Planning and
operator diagnostics can explain exactly what is incomplete. Execution-oriented consumers
must use `require_ready()` when production-ready canonical data is mandatory.

No override policy is introduced in this phase. Any future override must be explicit,
audited, and owned by the consuming subsystem's integration phase.

## Reference policy

Only `APPROVED` and `LOCKED` reference-library entries are exposed downstream. Candidate,
Rejected, and Archived references are never published as usable production references.

The MASTER remains governed by the existing CAP/reference lifecycle and retains its
ChatGPT-authored provenance and lineage semantics.

## Persistence migration truth

The current legacy CAP persistence model does not yet persist the complete structured
`facts`, `functional_identity`, and `constraints` collections defined by the production
contract. The projection therefore publishes empty collections when those fields are absent.
It never derives structured production facts from prose.

The Phase 18.2.11.2.7 readiness engine remains responsible for blocking categories whose
required structured production metadata is not yet persisted.

## Acceptance criteria

1. Projection contract is immutable and versioned.
2. Identity and readiness asset IDs cannot diverge.
3. Projection checksum is deterministic for identical canonical input.
4. Only Approved/Locked references are published.
5. Diagnostic projection remains available when Production Readiness is blocked.
6. `require_ready()` rejects blocked assets with a typed error carrying the diagnostic
   projection.
7. Ready assets pass `require_ready()` unchanged.
8. Projection API is registered once in the application composition root.
9. Public CAP domain/application packages export the production projection contract/service.
10. Full existing CAP, readiness, derived-reference, bootstrap and application regressions
    remain green.

## Architectural boundary

This phase publishes the contract. It does not yet modify Production Planning, Prompt Graph,
ACPP, rendering, or video engines to consume it. Those integrations must use the shared
`ProductionProjectionService` rather than reconstructing CAP data independently.
