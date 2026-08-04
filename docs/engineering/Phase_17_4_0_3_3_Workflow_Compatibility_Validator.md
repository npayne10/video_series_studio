# Phase 17.4.0.3.3 — Workflow Compatibility Validator

## Status

Build and integration implementation.

No workflow compilation, ComfyUI submission, model scanning or media generation is included.

## Objective

Determine whether a renderer-neutral `RenderRequest` can be satisfied by a
registered `WorkflowManifest` before the request enters a render queue.

## Validation inputs

The validator accepts:

- Render request
- Workflow manifest
- Optional installed-resource inventory
- Optional resolved continuity package
- Optional detailed lip-sync request

Compatibility failures are returned as diagnostics rather than raised as
exceptions.

## Request capability inference

Required capabilities are inferred from production data:

- No start frame: text-to-video
- Previous boundary frame: image-to-video and start-frame support
- Next boundary frame: end-frame support
- Canonical references: reference-image support
- Multiple references: multiple-reference support
- LoRA bindings: LoRA support
- Voice request: audio support
- Required lip-sync: lip-sync support
- Fixed seed: seed-control support

## Identity and quality validation

The validator checks:

- Renderer identity
- Workflow identity
- Preview or Production support
- Required workflow capabilities
- Unknown capability declarations

## Continuity validation

A referenced but unresolved continuity package generates a warning. A supplied
package is checked against the render shot. Previous-shot boundary frames require
start-frame support.

## Voice and lip-sync validation

Detailed lip-sync validation checks:

- Shot identity
- Supported lip-sync mode
- Multiple visible speakers
- Precision close-up support

Lip-sync remains a separate post-generation operation.

## Installed resources

`InstalledWorkflowResources` represents currently available:

- Checkpoints
- Video models
- LoRAs
- VAEs
- ControlNets
- Custom nodes
- Other declared resources

Missing mandatory resources are errors. Missing optional resources are warnings.
When no inventory is supplied, declared requirements are reported as unverified.
The future ComfyUI adapter will populate this inventory from the actual runtime.

## Diagnostics

Each finding records:

- Stable code
- Info, warning or error severity
- Human-readable message
- Optional subject identifier

A report passes when it contains no errors. Warnings do not block compatibility.

## Dependency injection

Bootstrap registers one `WorkflowCompatibilityValidator`. It does not contact
ComfyUI or instantiate a renderer.

## Completion outcome

VSCS can now determine whether a workflow matches a render request, its quality
level, continuity needs, dialogue and lip-sync requirements, canonical
references, LoRAs and installed runtime resources before any job is compiled or
queued.
