# Phase 17.4.0.3.1 — Workflow Manifest Model

## Status

Build and integration implementation.

Workflow discovery, filesystem loading, compatibility validation and ComfyUI
execution are intentionally deferred to later phases.

## Objective

Define the immutable, versioned contract used by VSCS to describe installed
renderer workflows without embedding ComfyUI node numbers or renderer-specific
logic in Story, Shot Planner, ACPP or future Prompt Graph code.

## Manifest identity

Each `WorkflowManifest` contains `WorkflowMetadata` with:

- Stable workflow ID
- Display name and description
- Renderer family
- Workflow version
- Manifest schema version
- Optional author

The workflow ID is the authoritative registry key.

## Renderer-neutral node bindings

A `WorkflowNodeBinding` maps a renderer-neutral input such as:

- Positive prompt
- Negative prompt
- Width and height
- Frame count and FPS
- Seed
- Start and end frames
- Canonical reference images
- LoRAs
- Audio
- Output directory and filename

to a `WorkflowNodeSelector` and field path.

Selectors use a stable logical name and at least one physical discovery hint:

- Node ID
- Node title
- Class type

The logical name is the VSCS contract. Physical hints are adapter concerns and
may change between workflow revisions.

## Requirements

`WorkflowRequirement` declares external dependencies using typed categories:

- Checkpoint
- Video model
- LoRA
- VAE
- ControlNet
- Custom node
- Other

Each requirement may include a version and may be marked optional. Actual
installation checks are deferred to compatibility validation.

## Supported production modes

A manifest records:

- Preview and/or Production quality levels
- Capability identifiers
- Output kinds
- Supported lip-sync modes
- Tags
- Optional project-relative workflow file

This phase stores those declarations but does not evaluate a `RenderRequest`
against them.

## Serialization and schema

`WorkflowManifest.to_dict()` emits JSON-compatible primitives.
`WorkflowManifest.from_dict()` reconstructs and validates a manifest.
`workflow_manifest_schema()` exposes the stable draft-2020-12 JSON schema
foundation for authoring tools and the future manifest loader.

## Registry

`WorkflowRegistry` supports:

- Registering manifests
- Explicit replacement
- Duplicate protection
- Lookup and required lookup
- Removal and clearing
- Filtering by renderer, quality level and tag
- Stable workflow-ID ordering

The registry is registered empty through the application dependency graph.
Automatic discovery is deferred to Phase 17.4.0.3.2.

## Architectural boundary

The completed flow is:

```text
Workflow author
    ↓
WorkflowManifest
    ↓
WorkflowRegistry
    ↓
Manifest discovery (17.4.0.3.2)
    ↓
Compatibility validation (17.4.0.3.3)
    ↓
ComfyUI adapter compilation (17.4.0.4)
```

## Completion outcome

VSCS can now describe, serialize, validate structurally and catalogue workflow
manifests using renderer-neutral contracts. No workflow is discovered,
validated against available resources or executed during this phase.
