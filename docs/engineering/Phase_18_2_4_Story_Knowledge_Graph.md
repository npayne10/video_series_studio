# Phase 18.2.4 — Story Knowledge Graph

## Objective

Convert the structured `AnalysisResult` produced by Phase 18.2.3 into a deterministic,
traceable Story Knowledge Graph (SKG) that later planning, persistence, diagnostics,
and presentation phases can query without reparsing manuscript text.

## Implemented Scope

- Immutable graph node, edge, node-kind, and edge-kind domain contracts.
- Immutable `StoryKnowledgeGraph` aggregate.
- Duplicate node and edge identifier validation.
- Dangling-edge validation.
- Incoming and outgoing edge navigation helpers.
- Deterministic `StoryKnowledgeGraphBuilder`.
- Graph nodes for characters, locations, technology, props, dialogue, actions,
  emotions, and timeline events.
- Graph edges for narrative relationships, speaking, addressing, acting, targeting,
  location, emotion ownership, timeline participation, and chronological precedence.
- Source provenance and confidence propagated from the Story Model into graph facts.
- `StoryKnowledgeGraphStage` registered after the Analysis Engine stage.
- Published graph artifact key: `story.knowledge_graph`.
- Unit and pipeline integration coverage.

## Architectural Rules

The SKG is a derived projection of `AnalysisResult`; it is not an independent source
of truth. Phase 18.2.4 never reparses raw manuscript text and never mutates the Story
Model.

All graph edges must resolve to existing graph nodes. Every derived fact preserves
available `SourceSpan` evidence and confidence values so later UI and diagnostics can
trace graph conclusions back to manuscript material.

The graph remains renderer-independent, AI-provider-independent, and persistence-
independent.

## Execution Order

The default story-analysis pipeline now executes:

1. `story.analysis.engine` — order 100
2. `story.knowledge_graph` — order 200

The second stage requires the `story.analysis.result` artifact and publishes
`story.knowledge_graph`.

## Deliberately Deferred

- Graph database persistence.
- Cross-story/global knowledge graphs.
- Production asset resolution against XPD/CAP.
- Semantic graph enrichment through external AI providers.
- Story Analysis / graph visualization UI.

These belong to later Phase 18.2 increments.

## Completion Criteria

Phase 18.2.4 is complete when valid Analysis Results produce deterministic graphs,
source provenance survives projection, dangling edges are rejected, timeline order
is represented explicitly, the default pipeline publishes both Story Model and SKG
artifacts, and all prior Story Workspace / Story Analysis regressions remain green.
