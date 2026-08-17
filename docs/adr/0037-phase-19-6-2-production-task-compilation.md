# ADR-0037 — Phase 19.6.2 ProductionTask Compilation

## Decision

VSCS introduces a deterministic `ProductionTaskCompilerService` between governed Universal Production Description (UPD) authority and later scheduling/execution.

The compiler consumes only current, Ready, cross-authority-consistent UPD production authority and emits immutable provider-neutral `ProductionTask` objects in `PLANNED` state.

The compiler does not create `ProductionNode`, mutate `ProductionGraph`, submit `RenderQueue` work, choose a provider, compile a workflow, select a model, or invoke execution.

## Initial compilation scope

Phase 19.6.2 deliberately compiles one primary shot-level `VIDEO_GENERATION` task from one approved shot UPD.

This is intentionally narrower than the complete `ProductionTaskType` domain. Voice, lip-sync, audio, quality-control, repair, scene assembly, episode assembly, mastering and delivery decomposition require explicit governed production rules and must not be inferred speculatively from legacy UPD content.

Later compilation phases may add those deterministic decompositions without changing the ProductionTask execution boundary.

## Authority identity and provenance

Each compiled task preserves:

- stable UPD authority identity (`UPD-<SHOT_ID>`);
- explicit authority revision;
- deterministic SHA-256 fingerprint of the current compiled UPD payload;
- explicit human approver identity;
- production, episode, scene and shot scope;
- current Production Package provenance;
- canonical reference inputs;
- required provider-neutral production capability;
- expected provider-neutral output contract.

Task identity is deterministic over UPD authority identity, authority revision, UPD fingerprint and task type. Recompiling unchanged authority therefore produces the same task identity; a governed authority revision or content change produces a different identity.

## Legacy UPD compatibility boundary

The existing Phase 19.4 UPD persistence records Ready/Draft state and current dependency authority, but it does not persist all vNext authority fields required by ProductionTask governance, particularly human approver identity and an explicit authority revision.

Phase 19.6.2 therefore does not invent those values or silently reinterpret provider-specific final review as UPD authority. The compiler requires them through an explicit `ProductionTaskCompilationContext` until the UPD authority model is migrated in a later controlled phase.

This preserves backward compatibility with existing Phase 19.4 Production Packages and avoids a broad rewrite of the established production-planning pipeline.

## Provider neutrality

No provider, renderer, workflow, model, endpoint, node graph or adapter identity is emitted by the compiler.

Canonical references are represented as governed task inputs, not provider bindings. Provider/resource matching remains downstream of ProductionTask compilation.

## Migration

Phase 19.6.2 does not remove or replace:

- `ProductionNode`;
- `ProductionGraph`;
- `RenderQueue`;
- provider compiler outputs;
- ACPP;
- existing Phase 19.4 UPD persistence.

ProductionNode/ProductionGraph migration remains reserved for later Phase 19.6 work.
