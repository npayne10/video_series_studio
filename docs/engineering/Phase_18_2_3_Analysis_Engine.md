# Phase 18.2.3 — Analysis Engine

## Objective

Introduce the first concrete Story Analysis stage that converts saved story text into the Phase 18.2.2 structured Story Model while preserving deterministic source traceability.

## Implemented Scope

- `StoryStructureParser` for deterministic section/scene detection.
- `StoryTokenizer` producing offset-preserving sentence spans.
- `DeterministicStoryAnalyzer` producing a structured `AnalysisResult`.
- Character extraction from explicit titles and dialogue attribution patterns.
- Heuristic location, technology, and prop extraction.
- Dialogue extraction with source spans.
- Narrative action extraction.
- Lightweight emotion cue extraction.
- Conservative character co-occurrence relationships.
- Section-based timeline generation.
- Stable deterministic identifiers for extracted entities.
- `StoryAnalysisEngineStage` publishing `story.analysis.result` into the Phase 18.2.1 pipeline artifact map.
- Default stage registration through `register_story_analysis()`.
- Unit and integration tests.

## Design Boundary

This phase is intentionally local and provider-independent. It does not require OpenAI or another model provider to perform baseline analysis. The deterministic engine establishes a reproducible fallback and test oracle for future AI-assisted extractors.

The Story Knowledge Graph is not created in this phase. `Relationship` and `TimelineEvent` records remain Story Model records until Phase 18.2.4 constructs the SKG.

Persistence and user-facing Story Analysis controls remain later Phase 18.2 increments.

## Pipeline Artifact

The concrete stage publishes:

```text
story.analysis.result -> AnalysisResult
```

Later stages consume this artifact without reparsing the manuscript.

## Traceability

All extracted facts that originate from source text retain `SourceSpan` values containing source revision, character offsets, line numbers, and excerpts. This permits later UI inspection and provenance navigation.

## Completion Criteria

Phase 18.2.3 is complete when structure parsing, source spans, baseline extraction, deterministic identifiers, pipeline publication, and regression tests pass without altering existing Story Workspace behaviour.
