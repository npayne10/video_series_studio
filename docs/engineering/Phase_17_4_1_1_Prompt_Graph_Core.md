# Phase 17.4.1.1 — Prompt Graph Core

## Purpose

Phase 17.4.1.1 introduces the renderer-neutral graph used to represent production knowledge before prompt compilation.

The graph does not yet build itself from Story, Shot Planner, ACPP, CAP, continuity, voice or workflow data. Those integrations begin in Phase 17.4.1.2.

## Core model

A `PromptGraph` owns immutable:

- `PromptGraphMetadata`
- `PromptNode` records
- `PromptEdge` relationships
- an optional root node

Graph metadata binds the graph to production, container, scene, shot and optional clip identities.

## Node vocabulary

The initial node vocabulary includes:

- scene and shot
- visual intent
- character, ship, vehicle, location, environment and prop
- camera, lighting, movement and effect
- continuity, dialogue and audio
- style and quality
- restriction and negative prompt knowledge
- renderer information

Nodes may carry canonical asset identity, approved reference identities, mandatory status, ordered attributes and production sequence.

## Edge vocabulary

Directed semantic relationships include:

- contains
- depends on
- describes
- located at
- uses
- affects
- follows and precedes
- speaks and targets
- references
- constrains and overrides

## Integrity rules

The core enforces:

- unique graph node IDs
- unique edge IDs
- valid edge endpoints
- valid root identity
- no self-referencing edge
- unique attribute keys
- deterministic node and edge ordering

Production completeness is deliberately not enforced here. Missing CAP data, continuity, dialogue and renderer information are validation concerns for Phase 17.4.1.3.

## Traversal

The graph provides:

- incoming and outgoing edge lookup
- node filtering by kind
- cycle-safe breadth-first reachability
- deterministic topological ordering
- explicit cycle detection

A cyclic graph remains inspectable, but topological traversal raises `PromptGraphCycleError`.

## Serialization

Graphs serialize to JSON-compatible primitives and reconstruct through validated `from_dict()` contracts. Enum values and tuple-backed immutable data are preserved through round-tripping.

## Snapshots

`PromptGraphSnapshot` captures:

- snapshot identity
- complete immutable graph
- timezone-aware creation time
- canonical SHA-256 graph checksum

The checksum is generated from sorted, compact JSON and makes snapshots reproducible and suitable for later differencing and provenance.

## Registries

Bootstrap registers empty:

- `PromptGraphRegistry`
- `PromptGraphSnapshotRegistry`

Persistence is intentionally deferred. The registries establish the application contracts that later phases can replace or extend with project-backed repositories.

## Deferred scope

This phase does not provide:

- automatic graph construction
- CAP expansion
- continuity resolution
- completeness scoring
- prompt section compilation
- renderer-specific prompt output
- graph diffing
- UI integration

## Readiness

The immutable graph, traversal, serialization, snapshot and registry contracts are ready for Phase 17.4.1.2 — Prompt Graph Builder.
