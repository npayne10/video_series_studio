# Phase 18.2.1 — Story Analysis Framework

## Objective

Establish the renderer-agnostic application framework that later Story Analysis
increments use for parsing, extraction, narrative modelling, knowledge-graph
construction, persistence, and presentation.

## Implemented Scope

- Immutable analysis request, context, stage-result, and report contracts.
- `StoryAnalysisStage` plugin protocol for independently deployable analysis stages.
- `StoryAnalysisEngine` application-facing protocol.
- Ordered stage registry with duplicate protection, replacement, removal, lookup,
  enablement, and deterministic ordering.
- Fail-fast pipeline orchestration with accumulated immutable artifacts.
- Structured diagnostics for stage exceptions and invalid stage results.
- Service-composition helper registering the registry, concrete pipeline, and public
  engine contract in `ApplicationServices`.
- Unit tests for validation, registry behaviour, ordering, artifact propagation,
  failure isolation, and dependency registration.

## Architectural Boundary

This phase intentionally contains no narrative entity model, tokenizer, manuscript
parser, extractor, Story Knowledge Graph, persistence adapter, or UI. Those are
separate Phase 18.2 increments and plug into this framework through
`StoryAnalysisStage` without changing Story Workspace consumers.

## Extension Pattern

A later stage implements:

```python
class ChapterParsingStage:
    stage_id = "story.chapter-parsing"
    order = 100
    enabled = True

    def analyze(self, context: AnalysisContext) -> StageResult:
        ...
```

The stage is registered with `StoryAnalysisStageRegistry`. Consumers invoke only
`StoryAnalysisEngine.analyze(...)`, preserving renderer and provider independence.

## Completion Criteria

Phase 18.2.1 is complete when the framework contracts are importable, stages execute
in deterministic order, artifacts flow between stages, failures produce stable
reports, and the service graph resolves both concrete and protocol-level services.
