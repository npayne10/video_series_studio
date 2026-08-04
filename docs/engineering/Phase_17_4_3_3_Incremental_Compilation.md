# Phase 17.4.3.3 — Incremental Compilation

## Objective

Avoid recompiling unchanged prompt work while preserving deterministic output and explicit dependency control.

## Delivered

- `CompilationDependencyKind`
- `CompilationDependency`
- `CompilationFingerprint`
- `CompiledPromptRecord`
- `IncrementalCompilationHistory`
- `IncrementalCompilationService`
- Batch `SKIPPED` item status
- Graph/profile/dependency checksum comparison
- Explicit item invalidation
- Dependency-triggered invalidation
- Forced recompilation
- Scheduler integration through the shared batch service

## Fingerprint

Each compiled item is identified by a SHA-256 fingerprint composed of:

1. Prompt Graph checksum
2. Renderer prompt profile identity and checksum
3. Ordered dependency identities and checksums

Dependency categories include canonical assets, reference images, continuity, voice, camera and lighting profiles, renderer profiles, workflow manifests and future dependency types.

## Incremental policy

- No previous record: compile.
- Matching fingerprint: return the previous profiled package as `skipped`.
- Changed graph: compile.
- Changed renderer profile: compile.
- Changed dependency checksum: compile.
- Explicitly invalidated item: compile.
- Invalidated dependency: compile only affected items.
- `force_recompile=True`: compile regardless of fingerprint.

Skipped items count as successfully processed and remain available through `BatchCompilationJob.packages`.

## Boundaries

This phase keeps history in memory. Persistent compiled-package storage, restart recovery and durable invalidation state remain reserved for Phase 17.4.3.5.

No UI and no live renderer execution are included.
