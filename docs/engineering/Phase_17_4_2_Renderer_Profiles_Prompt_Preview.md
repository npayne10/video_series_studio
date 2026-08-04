# Phase 17.4.2 — Renderer Profiles and Prompt Preview

## Objective

Provide renderer- and quality-specific prompt presentation without allowing renderer formatting rules to alter canonical production knowledge in the Prompt Graph.

## Architecture

```text
PromptGraph
→ PromptGraphCompiler
→ renderer-neutral PromptPackage
→ RendererPromptProfile
→ RendererPromptCompiler
→ ProfiledPromptPackage
→ PromptPreviewService
→ PromptPreview
```

## Renderer prompt profiles

`RendererPromptProfile` defines:

- stable profile identity and display name;
- renderer and quality level;
- prompt-section order;
- positive and negative separators;
- optional prefixes and suffixes;
- optional character limits;
- optional section labels.

The initial approved profiles are:

- `comfyui_preview_v1`;
- `comfyui_production_v1`.

Preview uses compact comma-separated formatting and bounded prompt sizes. Production preserves labelled sections and full detail.

## Separation of concerns

The Prompt Graph remains renderer-neutral. CAP descriptions, continuity, dialogue, camera, lighting and restrictions are compiled once into a `PromptPackage`. Renderer profiles only control the final presentation of those existing sections.

The source package is immutable and is never shortened or rewritten by a profile. Character limits affect only the profiled view and are reported as warnings in the preview.

## Prompt preview

`PromptPreviewService` exposes:

- final positive and negative prompts;
- structured prompt sections;
- fragment counts;
- canonical asset IDs by section;
- approved reference IDs by section;
- prompt character counts;
- asset and reference totals;
- truncation and missing-data warnings;
- stable plain-text formatting for logs and early UI integration.

This model is ready for a future Prompt Preview panel without coupling the application layer to PySide6.

## Bootstrap services

The application graph registers:

- `RendererPromptProfileRegistry`;
- `RendererPromptCompiler`;
- `PromptPreviewService`.

## Deliberate exclusions

This phase does not add:

- live ComfyUI execution;
- renderer-specific prompt optimisation;
- automatic token budgeting;
- batch compilation;
- editable prompt UI;
- the full Production workspace.

Those capabilities build on this profile and preview foundation in subsequent phases.
