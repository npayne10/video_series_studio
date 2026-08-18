# ADR 0054 — Phase 20.5 Live ComfyUI Provider Adapter

## Status

Accepted for implementation in Phase 20.5; functional acceptance remains pending local validation.

## Context

Phase 19 established authoritative ProductionTask scheduling, queue, worker, lease, retry, monitoring and readiness behavior. Phase 20.3 introduced a provider-neutral execution envelope that can carry that authority into provider adapters. Phase 20.4 introduced durable provider registrations, resource binding and provider capability resolution.

The existing ComfyUI renderer integration is intentionally dry-run. It already owns manifest discovery, workflow compatibility validation, API-workflow loading and renderer-specific compilation. Replacing that code would duplicate a mature boundary and risk divergence between dry-run and live rendering.

Phase 20.5 must connect VSCS to a real ComfyUI HTTP server without allowing the provider to become production authority and without prematurely wiring automatic ProductionQueue execution, which belongs to Phase 20.6.

## Decision

### 1. Preserve the existing ComfyUI compilation foundation

`ComfyUIAdapter` remains the dry-run renderer foundation and continues to own:

- workflow capability reporting,
- renderer compatibility validation,
- manifest-driven input injection,
- `RenderRequest` to `CompiledRenderRequest` compilation.

Phase 20.5 adds `LiveComfyUIAdapter` beside it. The live adapter delegates validation and compilation to the existing foundation and adds real provider communication only.

### 2. Isolate HTTP communication behind a transport boundary

`ComfyUITransport` defines the minimal JSON transport contract. `UrllibComfyUITransport` is the production implementation and uses Python standard-library HTTP support, avoiding a new HTTP dependency.

`ComfyUIClient` owns the ComfyUI endpoint semantics used by VSCS:

- `GET /system_stats` for health,
- `POST /prompt` for workflow submission,
- `GET /queue` for pending/running observation,
- `GET /history/{prompt_id}` for terminal state and output discovery,
- `POST /queue` with `delete` for safe queued-prompt cancellation.

Tests use deterministic fake transports and do not require a running ComfyUI server.

### 3. ComfyUI prompt IDs are provider job IDs

The `prompt_id` returned by `/prompt` is captured as `RenderJob.renderer_job_id` and later exposed through the Phase 20.3 provider bridge as `ProviderExecutionHandle.provider_job_id`.

VSCS job identity remains separate from provider job identity.

### 4. Provider status is reconciled into existing RenderJob state

Monitoring checks history before the active queue. Successful terminal history maps to `COMPLETED`, failed terminal history maps to `FAILED`, active queue membership maps to `RUNNING`, and pending queue membership remains `QUEUED`.

HTTP polling does not provide reliable fine-grained progress, so Phase 20.5 reports bounded coarse progress only. Durable execution history and richer monitoring belong to Phase 20.7 and Phase 20.8.

### 5. VSCS will not use ComfyUI's global interrupt endpoint for ordinary cancellation

Queued prompts can be deleted individually through `/queue`.

A running ComfyUI prompt would normally require `/interrupt`, which affects the running workload at the ComfyUI instance level and is not safely scoped to one VSCS execution. VSCS therefore refuses running-job cancellation rather than risk interrupting unrelated work.

A future provider-specific cancellation mechanism may replace this rule if ComfyUI exposes scoped cancellation semantics.

### 6. Output discovery does not create Generated Media authority

Completed ComfyUI history is inspected for output descriptors. Only provider outputs whose descriptor type is `output` are considered; temporary/preview artifacts are ignored.

Phase 20.5 converts supported video and image files into existing `RenderOutput` descriptors. These remain provider/execution artifacts only.

`RenderOutput -> GeneratedMedia` ingestion remains Phase 20.9.

### 7. Phase 20.5 initially supports the tested video-generation path

The first live workload boundary is existing ComfyUI video generation. Video files are classified as preview or production video according to the compiled quality level. Image files are represented as reference-frame outputs when returned by the workflow.

Unsupported file types fail explicitly instead of being guessed into an incorrect media contract.

### 8. ProviderRegistration composes the live adapter explicitly

`ComfyUIProviderAdapterFactory` builds a live ComfyUI renderer from a Phase 20.4 `ProviderRegistration`, then wraps it in the Phase 20.3 `RenderProviderExecutionAdapter` using the stable provider ID.

The factory requires:

- `adapter_type == comfyui`,
- an enabled provider registration,
- a configured endpoint.

Secrets are still references only and are not resolved in this phase.

### 9. Normal bootstrap remains dry-run

Phase 20.5 does not replace the bootstrap's currently registered dry-run ComfyUI renderer with the live adapter.

Live provider activation must remain explicit until Phase 20.6 connects authoritative ProductionQueue execution to provider selection/submission. This prevents normal desktop startup or existing rendering workflows from unexpectedly submitting real jobs.

## Consequences

Positive consequences:

- VSCS now has a real ComfyUI HTTP execution path.
- Existing workflow compilation remains the single implementation.
- Provider identity and ComfyUI prompt identity remain distinct and traceable.
- Live provider behavior can be tested deterministically without network dependency.
- Global provider interruption is avoided.
- Generated Media authority remains untouched.
- Existing dry-run behavior and bootstrap compatibility are preserved.

Deferred consequences:

- provider execution records are not yet durable,
- live output-classification context is transient across restart,
- queue-to-provider dispatch remains manual/explicit,
- detailed provider progress is not available through this HTTP polling contract,
- provider secret resolution is not implemented,
- running-job scoped cancellation is unavailable,
- Generated Media ingestion remains later work.

These are intentional boundaries of Phase 20.5 and are addressed by later Phase 20 subphases.
