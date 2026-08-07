# Phase 18.2.2 — Story Model

## Objective

Define the stable, renderer-agnostic domain model used to represent structured
story-analysis output while preserving traceability back to the source manuscript.

## Implemented Scope

- `SourceSpan` provenance model with source revision, character offsets, optional
  line range, and excerpt.
- `StoryAttribute` for small typed entity facts.
- `StoryEntity` base model with aliases, attributes, source evidence, and confidence.
- Concrete narrative entities:
  - `Character`
  - `Location`
  - `Technology`
  - `Prop`
- Structured narrative records:
  - `Dialogue`
  - `Action`
  - `Emotion`
  - `Relationship`
  - `TimelineEvent`
- `AnalysisResult` aggregate for one story source revision.
- Unique identifier validation within each aggregate collection.
- Deterministic timeline ordering and entity lookup helpers.
- Integration validation proving that a typed `AnalysisResult` can flow through the
  Phase 18.2.1 analysis pipeline as an immutable artifact.

## Domain Rules

- Models are immutable after construction.
- Confidence and emotion intensity use normalized values from 0.0 through 1.0.
- Source spans must have forward-moving offsets and valid line ranges.
- Concrete entity types enforce their `EntityKind` and cannot be mislabeled.
- Relationships require two distinct endpoints.
- Identifiers must be unique within each `AnalysisResult` collection.
- Timeline ordering is derived without mutating the extractor's original event order.

## Architectural Boundary

Phase 18.2.2 defines data only. It does not parse manuscripts, infer entities,
construct the Story Knowledge Graph, persist analysis output, resolve production
assets, or expose analysis in the UI. Those concerns remain assigned to later
Phase 18.2 increments.

The model lives in `vscs.domain.story_analysis` so extraction implementations,
persistence adapters, UI presenters, and production-planning services can depend on
one stable narrative vocabulary without depending on a renderer or AI provider.

## Traceability Principle

Every extracted fact capable of influencing downstream production should carry a
`SourceSpan` directly or through its containing entity/event. This allows later UI
and quality-control phases to show why VSCS believes a character, location, action,
relationship, or timeline event exists and where that conclusion originated.

## Completion Criteria

Phase 18.2.2 is complete when all supported story concepts can be represented using
immutable validated models, source evidence is preserved, invalid domain states are
rejected, `AnalysisResult` provides deterministic lookup/ordering behaviour, and the
Phase 18.2.1 framework transports the aggregate without conversion or information
loss.
