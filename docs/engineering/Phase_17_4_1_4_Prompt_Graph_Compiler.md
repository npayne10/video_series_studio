# Phase 17.4.1.4 — Prompt Graph Compiler

## Purpose

Compile a validated renderer-neutral `PromptGraph` into a deterministic, traceable
`PromptPackage` without applying renderer-specific optimization.

## Pipeline

```text
PromptGraph
→ PromptGraphValidator
→ ordered PromptSection objects
→ positive and negative prompt views
→ PromptPackage
```

Compilation is blocked when validation contains errors. Production compilation is
also blocked when the graph does not meet the configured completeness threshold.
Preview tooling may explicitly allow a valid but non-production-ready graph.

## Structured output

The package preserves independent sections for visual intent, scene, characters,
environment, camera, lighting, movement, continuity, effects, dialogue, audio,
style, quality, restrictions, negative constraints, renderer information and
uncategorized production knowledge.

Each section contains traceable `PromptFragment` records rather than unstructured
text. A fragment preserves its originating node ID, label, canonical asset ID,
approved references, attributes, mandatory state and production sequence.

## Positive and negative separation

Restrictions and negative nodes compile into `negative_prompt`. All other prompt
sections compile into `positive_prompt`. The structured sections remain available
so future renderer profiles do not need to parse either combined string.

## Canonical detail retention

The compiler does not shorten, summarize or reinterpret node content. Full graph
content such as spacecraft class, physical dimensions, engine placement, engine
trail colour, uniforms, props, lighting and continuity constraints is retained.
Renderer-specific optimization belongs to Phase 17.4.4.

## Provenance

Every package records graph identity, graph version, SHA-256 graph checksum,
production, container, scene, shot and optional clip identity. Canonical asset and
reference IDs are deduplicated and sorted for deterministic downstream processing.

## Deliberate exclusions

This phase does not add renderer-specific profiles, token optimization, batch
compilation, UI integration, ComfyUI execution or graph differencing.
