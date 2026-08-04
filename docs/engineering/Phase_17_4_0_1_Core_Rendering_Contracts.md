# Phase 17.4.0.1 — Core Rendering Contracts

## Purpose

This phase establishes the renderer-independent vocabulary used by the VSCS production pipeline. It defines how future Prompt Graph, ComfyUI, renderer execution, queue management and output tracking components communicate without embedding renderer-specific logic in Story, Shot Planner or ACPP.

No live renderer is created or contacted in this phase.

## Core request lifecycle

```text
Story → Shot → ACPP → Prompt Package → RenderRequest
                                      ↓
                              RenderAdapter contract
                                      ↓
                               Future renderer
```

`RenderRequest` carries stable production identity, selected renderer and workflow, Preview or Production quality intent, prompt and asset references, continuity references, technical render settings and project-relative output requirements.

## Renderer abstraction

`RenderAdapter` is a protocol. Future adapters must expose workflow capabilities, validate and compile universal requests, submit and monitor jobs, cancel work and fetch outputs. `RenderAdapterRegistry` is registered empty during application bootstrap so this foundation does not instantiate ComfyUI or any other renderer.

## Quality profiles

The initial quality registry contains two profiles:

- **Preview** — 960 × 400, 24 fps, lower sampling effort, no upscale, draft audio and draft lip-sync intent.
- **Production** — 1920 × 800, 24 fps, higher sampling effort, upscale enabled, final audio and final lip-sync intent.

These are renderer-neutral defaults. Workflow manifests and adapters may later map them to concrete ComfyUI nodes and model settings.

## Capabilities

`WorkflowCapabilities` declares support for text-to-video, image-to-video, start/end frames, references, LoRAs, audio, lip-sync, seed control, batching and resume. It provides deterministic capability matching and missing-capability reporting before execution.

## Jobs and outputs

`RenderJob` uses validated immutable state transitions from queued through preparation, execution and terminal states. `RenderOutput` records request, renderer, workflow, quality, version, creation time and project-relative path so every generated artifact retains provenance.

## Failure policy

`RetryPolicy` is declarative. It distinguishes retryable and abort-only error codes, maximum retries, delay, notification and future resume intent. No retry loop is executed in this phase.

## Dependency injection

Bootstrap registers:

- `RenderingContracts`
- `RenderAdapterRegistry`
- `QualityProfileRegistry`

The adapter registry intentionally starts empty. Preview and Production quality profiles are available immediately to later application services.

## Extension points

Phase 17.4.0.2 will add detailed continuity, voice and lip-sync contracts. Phase 17.4.0.3 will introduce versioned workflow manifests and workflow validation. Phase 17.4.0.4 will implement manifest-driven ComfyUI payload compilation without live execution.
