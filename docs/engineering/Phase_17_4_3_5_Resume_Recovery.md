# Phase 17.4.3.5 — Resume and Recovery

## Objective

Provide durable batch-compilation checkpoints and deterministic restart behavior without introducing distributed execution or database-backed package storage.

## Architecture

```text
BatchCompilationScheduler
        |
        +-- BatchRecoveryService
                |
                +-- BatchRecoveryStore
                        |
                        +-- config/recovery/batch_compilation.json
```

## Recovery document

The recovery store writes one versioned JSON document using an atomic temporary-file replacement. Each checkpoint contains:

- the complete original `BatchCompilationRequest`;
- graph-build context for every item;
- canonical resource inventory;
- renderer profile selection;
- dependency checksums;
- force-recompile and readiness policies;
- the latest terminal status known for each item;
- a timezone-aware update timestamp.

The document is deterministic and sorted by batch identity.

## Resume policy

Successful work is represented by item states `completed` and `skipped`. These items are excluded from a resumed request.

Failed items are included by default and can be excluded with `retry_failed=False`. Cancelled and unconfirmed items return to the pending set because they have no confirmed successful output.

An interrupted item is never assumed to have completed. This conservative rule prevents silent loss of production work.

## Scheduler integration

`BatchCompilationScheduler.enqueue()` creates the initial checkpoint. Terminal item results are recorded after each controlled scheduler run. A new application process calls:

```python
scheduler.restore_pending()
```

Recovered requests preserve original item ordering while containing only unfinished work.

## Safety properties

- Recovery files are project-configuration relative.
- Writes use temporary-file replacement.
- Unknown recovery-document versions are rejected.
- Duplicate or unknown checkpoint item identities are rejected.
- Completed batches are not offered for restoration.
- Existing scheduler entries are never duplicated.
- Resumed work still uses normal validation, renderer profiles and incremental compilation.

## Current boundary

This phase persists requests and item outcomes. Full compiled prompt-package artifact persistence remains a later production-storage concern. Recovery therefore prevents recompilation of confirmed successful items, while the authoritative compiled artifacts remain governed by the output and package persistence layers introduced later.

## Tests

The phase adds coverage for:

- request and dependency round-tripping;
- successful-item exclusion;
- failed-item retry policy;
- completed-checkpoint filtering;
- scheduler restoration;
- bootstrap registration;
- restart simulation using two application contexts.

## Readiness

Phase 17.4.3.5 establishes the recovery contract required for long-running episode and season compilation. Phase 17.4.3.6 can now certify the complete Batch Prompt Compilation subsystem.
