# Phase 17.4.1.5 — Graph Snapshots and Differencing

## Objective

Provide immutable, versioned Prompt Graph captures and deterministic comparisons between graph versions and compiled prompt packages.

## Delivered services

- `PromptGraphSnapshotService`
- `PromptGraphDiffer`
- `PromptGraphDiff`
- `PromptGraphChange`
- `PromptGraphChangeKind`
- `PromptGraphChangeArea`

## Snapshot lifecycle

A snapshot captures the complete immutable graph, creation time and canonical SHA-256 checksum. The snapshot service registers captures in `PromptGraphSnapshotRegistry`, returns ordered history per graph and exposes the latest version.

Snapshots remain in-memory in this phase. Project persistence will be introduced when the production-storage lifecycle is defined.

## Graph differencing

Graph comparisons classify:

- metadata changes
- added, removed and modified nodes
- added, removed and modified edges
- continuity-sensitive node changes

Ordering is deterministic by change area, subject and change kind.

## Prompt-package differencing

Compiled package comparisons classify:

- prompt-section changes
- positive-prompt changes
- negative-prompt changes
- canonical asset additions and removals
- approved reference additions and removals

This supports later prompt preview, version history, renderer comparison, change review and render provenance.

## Continuity sensitivity

Changes to `PromptNodeKind.CONTINUITY` or the compiled continuity section are explicitly marked as continuity-sensitive. Future UI and QC services can therefore escalate changes that may break shot-to-shot consistency.

## Bootstrap

The application composition root registers one shared:

- `PromptGraphSnapshotRegistry`
- `PromptGraphSnapshotService`
- `PromptGraphDiffer`

## Exclusions

This phase does not add:

- UI history or diff views
- database persistence
- automatic snapshot creation during editing
- merge or rollback operations
- renderer-specific prompt comparison

## Readiness

The Prompt Graph subsystem can now capture reproducible versions and explain exactly what changed between graph or prompt-package revisions. This prepares the system for Phase 17.4.1.6 integration testing and later Production workspace history tools.
