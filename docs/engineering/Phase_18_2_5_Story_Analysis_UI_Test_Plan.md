# Phase 18.2.5 — Story Analysis UI Manual Test Plan

Use the saved Xorix Trailer Test Story with a supported source file.

## Startup

1. Launch VSCS.
2. Open the project containing the test Story.
3. Open Story Workspace.

Pass: application starts without Story Analysis registration, Qt, or service errors.

## Launch Analysis

1. Select the Xorix Trailer Test Story.
2. Confirm the Story action reads **Analyse Story**.
3. Click **Analyse Story**.

Pass: Story Analysis workspace opens and automatically runs analysis.

## Source Panel

Pass criteria:
- complete source text is visible;
- source is read-only;
- selecting an analysis item moves/selects the corresponding source range;
- source text is not modified by analysis.

## Inspector

Verify sections exist where extracted data is available:
- Characters
- Locations
- Technology
- Props
- Dialogue
- Actions
- Emotions
- Relationships
- Timeline

Select representative records such as James Spence, Cheryl Draker, Xorix, dialogue,
and a timeline event.

Pass: details and confidence display, graph selection follows inspector selection, and
source navigation works when provenance is available.

## Search and Filter

1. Search for `James`.
2. Select the Characters filter.
3. Clear search and test several other filters.

Pass: inspector contents narrow without changing analysis data.

## Knowledge Graph

1. Inspect nodes and connecting edges.
2. Use Zoom +, Zoom -, and Fit.
3. Pan the graph.
4. Select an inspector record and confirm its graph node is highlighted when represented.

Pass: graph remains responsive and no layout or selection exception occurs.

## Validation and Diagnostics

1. Click **Validate Story**.
2. Review unresolved speakers, low-confidence nodes, and timeline count.
3. Review the diagnostics list.

Pass: validation summary opens and diagnostics remain readable.

## Export

1. Export Analysis to JSON.
2. Export Graph to JSON.
3. Open both files in a text editor.

Pass: valid JSON is written and contains the selected Story identity and structured data.

## Lifecycle

Close the Story Analysis workspace.

Pass for Draft/Imported Story: Story status changes to `Analysed` only after successful
analysis. Pass for an already Analysed/Approved/Locked Story: analysis can be reviewed
without changing that later lifecycle state.

## Regression

Verify Story Browser, Story metadata, Shot Planner, ACPP Editor, project close/reopen,
and application shutdown still function normally.

## Log Check

No unhandled occurrence of:

- Traceback
- ValidationError
- StorySourceReadError for a supported valid source
- ServiceAlreadyRegisteredError
- ServiceNotRegisteredError
- StoryAnalysisEngine
- StoryKnowledgeGraph
- ERROR
- CRITICAL
