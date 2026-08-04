# Phase 17.4.0.5 — Integration and Foundation Tests

## Status

Build → Integrate phase. No separate certification cycle.

## Objective

Prove that the renderer-neutral contracts, workflow-manifest subsystem and dry-run
ComfyUI adapter operate as one coherent foundation before Prompt Graph development
begins.

This phase does not add UI controls and does not contact a live ComfyUI server.

## Integrated production chain

```text
RenderRequest
  → continuity, voice and lip-sync references
  → WorkflowRegistry
  → WorkflowManifestLoader
  → WorkflowCompatibilityValidator
  → WorkflowDiagnosticsFormatter
  → ComfyUIAdapter
  → CompiledRenderRequest
  → dry-run RenderJob
```

## Foundation test matrix

### Reference workflow discovery

The LTX 2.3 Preview and Production reference manifests are copied into an isolated
workflow catalogue and discovered through the production `WorkflowManifestLoader`.
The tests verify that malformed or absent external installations are not required to
exercise the manifest foundation.

### Preview production path

The Preview request verifies:

- renderer and quality-profile selection;
- positive and negative prompt injection;
- technical render-setting injection;
- compiled payload provenance;
- dry-run queue creation;
- monitoring without side effects;
- output isolation; and
- cancellation of a queued dry-run job.

### Production production path

The Production request verifies:

- previous-frame and next-frame continuity inputs;
- canonical reference-image injection;
- LoRA binding;
- Production quality separation;
- exact workflow-manifest binding use; and
- renderer-neutral request provenance.

### Continuity, voice and lip-sync diagnostics

The compatibility integration test verifies that:

- a resolved continuity package belongs to the target shot;
- voice requirements are inferred from the request;
- visible lip-sync requirements are inferred from the request;
- unsupported capabilities produce blocking diagnostics;
- unresolved detailed lip-sync contracts produce warnings rather than exceptions;
- missing mandatory models or custom nodes produce errors; and
- optional requirements remain non-blocking warnings.

### Bootstrap integration

The dependency graph verifies availability of:

- `RenderingContracts` version `17.4.0.5`;
- `RenderAdapterRegistry`;
- registered `ComfyUIAdapter`;
- `WorkflowCompatibilityValidator`; and
- `WorkflowDiagnosticsFormatter`.

## Expected failure behaviour

The foundation must fail before queueing when:

- a workflow manifest is unavailable;
- renderer or quality selection is incompatible;
- a required manifest input cannot be resolved;
- a workflow node is missing or ambiguous;
- a mandatory model or custom node is unavailable;
- continuity belongs to another shot; or
- requested voice or lip-sync capabilities are unsupported.

Compatibility failures are returned as structured diagnostics. Workflow compilation
failures use `ComfyUIAdapterError`. Neither class of failure contacts ComfyUI.

## Provenance guarantee

Every compiled payload carries:

- VSCS request ID;
- production ID;
- scene ID;
- shot ID;
- clip ID; and
- quality level.

The render-job and output contracts retain renderer, workflow and request identity for
later live execution and output tracking.

## Deliberate exclusions

Phase 17.4.0 does not include:

- live HTTP or WebSocket communication with ComfyUI;
- model and custom-node inventory discovery from a running installation;
- Prompt Graph or Prompt Package generation;
- voice synthesis;
- lip-sync execution;
- render queue persistence;
- UI integration; or
- final video assembly.

These exclusions prevent temporary execution or UI concerns from altering the stable
foundation contracts.

## Readiness decision

When Ruff and the focused integration/regression suite pass, Phase 17.4.0 is closed.
The foundation is ready for Phase 17.4.1 — Prompt Graph Foundation.

The Prompt Graph may provide a new `ComfyUIInputResolver` implementation without
changing workflow manifests, the compiler, adapter contracts or upstream story data.
