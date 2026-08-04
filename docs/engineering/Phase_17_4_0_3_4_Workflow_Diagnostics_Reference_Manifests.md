# Phase 17.4.0.3.4 — Workflow Diagnostics and Reference Manifests

## Status

Build and integration implementation.

No ComfyUI workflow execution, prompt injection, queue submission, or renderer
communication is included.

## Objective

Complete the workflow-manifest foundation with readable diagnostics and approved
reference manifests for LTX 2.3 Preview and Production workflow families.

## Human-readable diagnostics

`WorkflowDiagnosticsFormatter` converts structured discovery and compatibility
results into deterministic text suitable for:

- User-interface panels
- Logs
- Support reports
- Automated production summaries
- Future command-line tools

Compatibility reports include:

- PASS or FAIL status
- Workflow and request identity
- Optional workflow metadata
- Errors
- Warnings
- Informational findings

Discovery reports include:

- Files discovered
- Manifests loaded
- Error count
- Loaded workflow IDs
- Per-file diagnostics

The formatter does not replace the machine-readable contracts. It is a view over
`WorkflowCompatibilityReport` and `ManifestDiscoveryResult`.

## Reference manifest location

Approved reference manifests are stored under:

```text
resources/workflows/manifests/
```

They are source-controlled examples and validation fixtures. They are not copied
to the configured runtime manifest directory automatically in this phase.

## LTX 2.3 Preview reference

```text
ltx23_preview_v1.json
```

Purpose:

- Fast continuity-aware preview generation
- Composition and camera review
- Shot timing review
- Canonical-reference checking

Declared quality level:

- Preview

Declared capabilities include:

- Text-to-video
- Image-to-video
- Start-frame conditioning
- Canonical reference images
- Multiple references
- LoRA support
- Seed control

The reference manifest supports no visible lip-sync pass. Dialogue may remain
off-screen during preview rendering.

## LTX 2.3 Production reference

```text
ltx23_production_v1.json
```

Purpose:

- High-quality final video generation
- Stronger continuity conditioning
- Start- and end-frame control
- Canonical references and LoRAs
- Stable seed control
- Resume-capable production workflows

Declared quality level:

- Production

Declared capabilities include:

- Text-to-video
- Image-to-video
- Start-frame conditioning
- End-frame conditioning
- Canonical reference images
- Multiple references
- LoRA support
- Seed control
- Resume support

Final lip-sync remains a separate downstream workflow, consistent with the
approved production architecture.

## Logical node bindings

Both manifests use stable VSCS logical selectors such as:

- `positive_prompt`
- `negative_prompt`
- `video_settings`
- `start_frame`
- `end_frame`
- `canonical_references`
- `sampler`
- `output`

The bindings describe expected node titles and class types without making the
upstream production system dependent on ComfyUI node numbers.

## Requirements

The reference manifests declare illustrative dependencies including:

- LTX 2.3 video model
- ComfyUI LTXVideo custom nodes
- Licon MSR continuity/reference support
- Optional temporal-refinement support

These identifiers are contract examples. Phase 17.4.0.4 will compare them with
the actual ComfyUI installation and workflow JSON.

## Validation

Focused tests confirm that both reference manifests:

- Parse through `WorkflowManifestLoader`
- Use the expected renderer and quality profile
- Expose required prompt and continuity bindings
- Pass `WorkflowCompatibilityValidator` when their declared resources are
  available

## Completion outcome

The workflow-manifest subsystem can now:

1. Define workflow contracts.
2. Discover installed manifests.
3. Validate render-request compatibility.
4. Present readable diagnostics.
5. Provide approved Preview and Production reference manifests.

This completes Phase 17.4.0.3 and prepares VSCS for Phase 17.4.0.4 — ComfyUI
Adapter Foundation.
