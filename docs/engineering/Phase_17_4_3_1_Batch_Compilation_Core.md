# Phase 17.4.3.1 — Batch Compilation Core

## Purpose

Phase 17.4.3.1 introduces deterministic synchronous orchestration for compiling multiple shots through the established Prompt Graph pipeline.

## Pipeline

Each batch item executes the same approved path used for individual compilation:

1. `PromptGraphBuilder`
2. `PromptGraphCompiler`, including validation
3. `RendererPromptProfileRegistry`
4. `RendererPromptCompiler`
5. `ProfiledPromptPackage`

The batch layer does not bypass graph validation or renderer-profile formatting.

## Contracts

`BatchCompilationItem` contains a stable item identity, graph build context, canonical resource inventory, sequence, optional explicit renderer profile and Production-readiness policy.

`BatchCompilationRequest` contains one or more unique items and exposes deterministic production ordering.

`BatchCompilationProgress` provides total, completed, failed, remaining and current-item values together with a percentage.

`BatchCompilationJob` is the immutable final outcome and exposes successful packages and isolated failures.

## Failure policy

A failure in one item is recorded as a `BatchCompilationItemResult` and does not stop later items. The final status is:

- `completed` when every item succeeds;
- `completed_with_failures` when some items succeed;
- `failed` when no item succeeds.

The failure record preserves exception type and message for later reporting phases.

## Determinism

Items are ordered by sequence, container, scene, shot, clip and item identity. The output result order therefore remains stable even when callers submit items in a different order.

## Deliberate exclusions

This phase does not add queue scheduling, asynchronous execution, cancellation, persistence, incremental compilation, dependency invalidation, history, resume or recovery. Those capabilities belong to Phases 17.4.3.2 through 17.4.3.5.

## Bootstrap

`BatchPromptCompilationService` is registered with the shared builder, graph compiler, renderer-profile registry and renderer compiler. This ensures batch and single-shot compilation use identical services and rules.

## Readiness

The core is ready for Phase 17.4.3.2 — Batch Queue and Scheduler once the focused unit and integration suites pass locally.
