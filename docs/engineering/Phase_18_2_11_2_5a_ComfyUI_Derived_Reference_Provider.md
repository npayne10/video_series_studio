# Phase 18.2.11.2.5a — ComfyUI Derived Reference Provider

## Purpose

Replace the non-production grey preview path with a production-capable, MASTER-conditioned ComfyUI provider while preserving the Phase 18.2.11 production-reference lifecycle.

## Managed workflow

VSCS ships the authoritative workflow template at:

`src/vscs/workflows/image/VSCS_Qwen_Derived_Reference_Workflow_API_v2.1.json`

Stable workflow ID: `qwen.derived-reference.v2.1`.

The template is immutable at runtime. VSCS copies/patches it into the active project's runtime area for each job.

## Runtime layout

`<project>/.vscs/runtime/comfyui/`

- `queues/` — per-job XCIC Qwen reference queue JSON
- `compiled/` — per-job patched ComfyUI API workflow
- `jobs/<uuid>/job.json` — provenance/diagnostic manifest
- `jobs/<uuid>/output/` — raw ComfyUI candidate output

Successful outputs are then copied by the application service into the governed CAP location under `Canonical Assets/<ASSET>/Images/Derived` and registered as Candidate references.

## Provider contract

The provider receives the absolute locked MASTER path, positive prompt, negative prompt, requested production view, seed, active project directory and requested dimensions. The Qwen workflow uses the MASTER through `XCICQwenReferenceJobLoader` and `FluxKontextImageScale`; it is therefore a reference-conditioned edit workflow, not text-to-image generation.

The current workflow derives actual image geometry from the MASTER. Width/height are retained in the request and provenance but are not falsely patched into a node that does not expose dimensions.

## ComfyUI transport

The provider reuses `XCICCoreClient` for:

1. `/system_stats` health check
2. `/object_info` node validation
3. `/prompt` submission
4. `/history/<prompt_id>` completion/error monitoring

The custom `XCICSaveReferenceCandidate` node writes the expected PNG to the project runtime output directory. The provider reads that file after ComfyUI reports completion.

Default endpoint: `http://127.0.0.1:8188`.

Optional override: environment variable `VSCS_COMFYUI_URL`.

## Queue contract

For compatibility with the existing `XCICQwenReferenceJobLoader`, the runtime queue is a JSON list and each item carries the six logical loader outputs: MASTER image, positive prompt, negative prompt, Lightning-LoRA flag, output directory and output filename. Self-describing aliases are included for diagnostics and forward compatibility.

## Lifecycle

ComfyUI output remains non-authoritative until human review:

`Locked ChatGPT MASTER → ComfyUI Derived Candidate → Review → Approve → Lock`

Every production-library entry is `VSCS_DERIVED`, points directly to the active MASTER, records the MASTER version, and records the ComfyUI provider as generator.

## Acceptance boundary

This phase does not implement category-specific required views, readiness scoring, automatic missing-view generation, or downstream Production Projection selection. Those remain in later approved 18.2.11.2 phases.
