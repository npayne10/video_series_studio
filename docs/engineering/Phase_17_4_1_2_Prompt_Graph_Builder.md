# Phase 17.4.1.2 — Prompt Graph Builder

## Outcome

VSCS can now construct an immutable renderer-neutral `PromptGraph` from authoritative production contributions resolved for a shot.

## Components

- `PromptGraphBuildContext` carries production, scene, shot, renderer, quality and workflow ownership.
- `PromptGraphSource` represents one resolved story, ACPP, CAP, continuity, voice or renderer contribution.
- `PromptGraphResolver` is the read-only boundary between the builder and persistence-backed services.
- `PromptGraphBuilder` creates the root node, production nodes and semantic edges deterministically.
- `PromptGraphBuildReport` records node and edge totals plus structured diagnostics.

## Canonical expansion

Resolved sources retain canonical asset IDs, approved reference IDs, mandatory traits and ordered attributes. This permits later service adapters to expand CAPs, continuity and voice contracts without changing the graph builder.

## Failure behaviour

A missing parent source does not discard a production contribution. The builder attaches the node to the graph root and emits `builder.parent_missing` as a warning. Duplicate identities and invalid edge endpoints remain graph-integrity errors enforced by the Prompt Graph Core.

## Deliberate exclusions

This phase does not score production completeness, compile prompt text, integrate a UI or submit rendering jobs. Those responsibilities remain in Phases 17.4.1.3, 17.4.1.4 and later production integration phases.
