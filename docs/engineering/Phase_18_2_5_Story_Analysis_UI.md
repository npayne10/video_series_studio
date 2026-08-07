# Phase 18.2.5 — Story Analysis UI

## Objective

Expose the Phase 18.2 Story Analysis Engine and Story Knowledge Graph as a
human-reviewable workspace without making the UI a second source of narrative truth.

## Implemented Scope

- Replaces the passive `Mark Analysed` action with `Analyse Story`.
- Opens a dedicated Story Analysis review workspace for the selected Story.
- Reads local plain text, Markdown, Final Draft XML, and DOCX Story sources.
- Runs the registered `StoryAnalysisEngine` and displays both `AnalysisResult` and SKG.
- Read-only manuscript/source panel with source-span highlighting.
- Structured inspector for characters, locations, technology, props, dialogue, actions,
  emotions, relationships, and timeline events.
- Search and category filtering across extracted analysis records.
- Deterministic Story Knowledge Graph viewer with pan, zoom and fit controls.
- Inspector selection synchronizes the graph and manuscript source span.
- Validation summary for unresolved dialogue speakers and low-confidence nodes.
- Pipeline and model diagnostics panel.
- JSON export for structured Story Analysis and Story Knowledge Graph.
- Successful analysis transitions Draft/Imported Story records to `Analysed` after the
  review workspace closes; existing later lifecycle states are not rewritten.
- Application composition injects the public `StoryAnalysisEngine` contract rather than
  a concrete implementation.

## Source Support

Phase 18.2.5 uses the existing runtime dependency set. It supports:

- `.txt`
- `.md` / `.markdown`
- `.fdx`
- `.docx`

PDF source extraction is intentionally deferred until a PDF ingestion dependency or
adapter is part of the VSCS document-import architecture. The UI reports this clearly
rather than attempting unreliable extraction.

## Architectural Boundary

This phase is an inspection and review surface. It does not implement AI entity
recognition, approval queues, automatic entity merging, XPD/CAP synchronization,
persistent analysis snapshots, graph editing, or cross-story knowledge graphs.
AI analysis and entity resolution are planned for Phase 18.2.6.

## User Workflow

1. Select a Story with a supported source file.
2. Choose **Analyse Story**.
3. The pipeline parses and analyses the source and builds the SKG.
4. Review manuscript/source, structured inspector, diagnostics, and graph.
5. Use search/filter and graph navigation to inspect extracted facts.
6. Validate or export analysis as needed.
7. Close the workspace. A Draft/Imported Story with successful analysis becomes
   `Analysed` and can proceed through the existing approval workflow.

## Completion Criteria

Phase 18.2.5 is complete when the UI can run the registered analysis pipeline against a
real Story source, display traceable results and graph data, search/filter them, export
both structured artifacts, preserve manuscript content, and leave all existing Story,
Shot, ACPP, and Production Browser workflows operational.
