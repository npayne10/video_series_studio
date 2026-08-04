# Phase 17.4.3.2 — Batch Queue and Scheduler

## Purpose

This phase adds deterministic queue management around the synchronous batch prompt compilation service introduced in Phase 17.4.3.1.

## Architecture

```text
BatchCompilationRequest
        ↓ enqueue
BatchCompilationScheduler
        ↓ FIFO selection
BatchPromptCompilationService
        ↓
BatchCompilationJob
        ↓
BatchQueueEntry
```

The scheduler is intentionally sequential. Only one batch may execute at a time. This preserves deterministic ordering and avoids introducing concurrency before persistence, recovery and production resource scheduling are available.

## Public contracts

- `BatchCompilationScheduler`
- `BatchQueueEntry`
- `BatchQueueSnapshot`
- `BatchQueueStatus`

The batch core also adds `CANCELLED` lifecycle states and a cancellation predicate checked between compilation items.

## Queue behaviour

- Requests are retained in insertion order.
- `run_next()` executes the earliest pending request.
- `run_all()` drains every pending request sequentially.
- Duplicate batch IDs are rejected.
- Queue snapshots are immutable views and are not changed by later enqueue operations.
- Terminal entries remain available for inspection during the application session.

## Cancellation

Pending jobs are cancelled without invoking the compiler.

Running jobs accept a cancellation request and stop at the next safe item boundary. Work already completed remains available. Items not yet started are recorded as cancelled. An individual prompt graph compilation is never interrupted halfway through.

Persistence and restart recovery are deliberately deferred to Phase 17.4.3.5.

## Bootstrap

`BatchCompilationScheduler` is registered in the application service graph and uses the shared `BatchPromptCompilationService` instance.

## Deliberate exclusions

This phase does not add:

- Parallel compilation
- Background worker threads
- Persistent queue state
- Restart recovery
- Incremental compilation
- Priority scheduling
- UI queue controls
- Live rendering

## Readiness

The queue foundation is ready for Phase 17.4.3.3 — Incremental Compilation. The scheduler can later skip unchanged work without changing its FIFO lifecycle or public queue contracts.
