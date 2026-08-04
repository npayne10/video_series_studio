# Phase 17.4.0.4 — ComfyUI Adapter Foundation

## Status

Build and integration implementation.

No HTTP connection, queue submission, WebSocket monitoring, renderer cancellation,
or output retrieval from a live ComfyUI installation is included.

## Objective

Provide the first concrete renderer adapter behind the renderer-neutral
`RenderAdapter` contract. The adapter loads ComfyUI API workflow JSON, resolves
manifest-declared nodes, injects approved request values, and produces the exact
payload shape required by the future live ComfyUI client.

## Architecture

```text
RenderRequest
    ↓
WorkflowRegistry
    ↓
WorkflowCompatibilityValidator
    ↓
ComfyUIInputResolver
    ↓
ComfyUIWorkflowCompiler
    ↓
CompiledRenderRequest
    ↓
Dry-run RenderJob
```

The adapter is registered as `RendererKind.COMFYUI` through the existing
`RenderAdapterRegistry`.

## Workflow loading

`ComfyUIWorkflowCompiler` loads the API workflow declared by
`WorkflowManifest.workflow_file`. The path is resolved beneath the configured
workflow root and may not escape that directory.

The accepted workflow format is the ComfyUI API dictionary form:

```json
{
  "12": {
    "class_type": "CLIPTextEncode",
    "inputs": {"text": ""},
    "_meta": {"title": "VSCS Positive Prompt"}
  }
}
```

## Stable node resolution

A manifest binding resolves a node in this order:

1. Explicit node ID
2. Node title, optionally combined with class type
3. Class type

Missing and ambiguous selectors fail compilation with a clear
`ComfyUIAdapterError`. Upstream production code never depends directly on
ComfyUI node numbers.

## Field injection

Manifest `field_path` values such as `inputs.text`, `inputs.width`, and
`inputs.seed` are written into a deep copy of the workflow. The source workflow
file remains unchanged.

Required bindings must have a resolved value. Optional bindings are skipped when
no value is available.

## Input resolution

`ComfyUIInputResolver` is a protocol so the Prompt Graph can later supply full
positive and negative prompts, canonical references, LoRAs, audio, and
continuity frames.

`MetadataComfyUIInputResolver` is the temporary implementation. It resolves:

- Width, height, frame count, and FPS from `RenderSettings`
- Output directory and filename from `OutputSettings`
- Seed from `RenderSettings`
- Prompt, reference, LoRA, audio, and boundary-frame values from request metadata

This temporary metadata bridge will be replaced or supplemented during Prompt
Graph integration without changing the workflow compiler.

## Compiled payload

The adapter produces a `CompiledRenderRequest` containing:

```json
{
  "prompt": {},
  "client_id": "request identity",
  "extra_data": {
    "vscs_request_id": "...",
    "production_id": "...",
    "scene_id": "...",
    "shot_id": "...",
    "clip_id": "...",
    "quality_level": "preview"
  }
}
```

The `prompt` object is the fully injected ComfyUI API workflow. `extra_data`
preserves VSCS provenance through future queue execution.

## Validation

Adapter validation confirms:

- The request targets ComfyUI
- The workflow manifest is registered
- The request is compatible with the manifest
- The workflow JSON can be loaded
- Every required input is available
- Every node selector resolves uniquely
- Every field path is writable

Validation returns `RequestValidation`; compatibility and preparation failures
do not contact a renderer.

## Dry-run job lifecycle

`submit()` creates a queued `RenderJob` with a `dry-run:` renderer-job identity.
No network request is made. The job can be cancelled while queued. Monitoring
returns the unchanged job and output retrieval returns the job’s existing output
collection.

Live queue execution is deliberately deferred to a later phase.

## Dependency injection

Bootstrap registers:

- `ComfyUIAdapter`
- `ComfyUIWorkflowCompiler` as an adapter dependency
- The adapter inside `RenderAdapterRegistry`

The workflow root is:

```text
<config_root>/workflows
```

Manifests continue to be discovered beneath:

```text
<config_root>/workflows/manifests
```

## Completion outcome

VSCS can now transform a validated renderer-neutral render request into a
manifest-driven ComfyUI API payload without hard-coded node numbers and without
executing a render. The next integration step can add a live ComfyUI client for
queue submission, monitoring, cancellation, resource inventory, and output
collection while preserving the contracts introduced here.
