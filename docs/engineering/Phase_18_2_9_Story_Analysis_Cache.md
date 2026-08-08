# Phase 18.2.9 — Story Analysis Cache, Revision Control & Incremental Reanalysis

## Purpose

Prevent Story Analysis and AI enrichment from rerunning merely because a user opens or refreshes a review window. Story Analysis is treated as an explicit, persisted build artifact.

## Execution rule

Only an explicit **Analyse Story** (when no cache exists) or **Reanalyse Story** command may execute the Story Analysis pipeline and configured AI provider.

The following are read-only consumers of cached analysis:

- Story Analysis viewer reloads
- AI Entity Review
- Story Intelligence Workspace / Production Dashboard
- Knowledge Graph view reloads

## Persistent cache

Each Story has a project-local cache document under:

`.vscs/story_analysis_cache/<story-id>.json`

The cache records:

- Story ID
- SHA-256 analysis revision
- monotonically increasing analysis version
- analysis timestamp
- execution duration
- provider used (OpenAI / Template / Unknown)
- pipeline status and stage summaries
- deterministic AnalysisResult
- AI EntityResolutionResult
- StoryKnowledgeGraph
- diagnostics

## Revision semantics

The revision hash is based on analysis-relevant Story identity/source values plus the complete extracted source text. Changing the source file, source path, title or Story description invalidates the cache without running AI.

States:

- `missing` — no successful cached analysis
- `current` — cached analysis revision equals current Story revision
- `stale` — Story/source changed since the cached analysis

Failed analyses do not overwrite the previous successful cache.

## Explicit reanalysis

When a stale Story is opened through Analyse Story, VSCS informs the user that the analysis is out of date and asks whether to reanalyse. Choosing No keeps the old cache available for reference. Choosing Yes explicitly reruns the pipeline.

The Story Analysis toolbar also exposes **Reanalyse Story** with an explicit confirmation warning that the configured AI provider may be called.

## Incremental reanalysis foundation

Phase 18.2.9 does not claim semantic partial-document reanalysis. It establishes the revision identity, persisted artifact boundary, analysis versioning and cache-only engine contract required for later per-section/stage incremental reuse.

## Canon boundary

The cache does not replace Approved Story Intelligence. Human entity review decisions remain persisted separately and are overlaid on fresh or cached AI entity proposals by the existing Story Intelligence service.

## Manual UI acceptance plan

1. Configure OpenAI and analyse a Story once. Confirm diagnostics show `OpenAI Story Analysis provider used`.
2. Close Story Analysis and reopen it. The cached result must appear without an OpenAI wait/API call.
3. Open **Review AI Entities** repeatedly. It must load immediately from cache and must not rerun OpenAI.
4. Open **Story Intelligence** and press **Reload Cached Dashboard** repeatedly. It must not rerun OpenAI.
5. In Story Analysis, press **Reload Cached Analysis**, **Reload Cached Graph**, and **Reload Cached**. None may rerun OpenAI.
6. Press **Reanalyse Story**. VSCS must ask for confirmation. Choosing No performs no analysis. Choosing Yes reruns OpenAI and replaces the cache only after successful completion.
7. Edit the Story source text/file, then open Analyse Story. VSCS must report that analysis is out of date and ask whether to reanalyse.
8. Choose No. The prior cached analysis remains viewable and no AI call occurs.
9. Choose Yes. Analysis runs and the cache revision/version advances.
10. Restart VSCS and reopen the project. Cached analysis must survive the restart.
11. Confirm AI Entity approval/rejection persistence continues to work and is not erased by cache reloads.
12. Confirm failed reanalysis does not destroy the previous successful cache.

## Acceptance criteria

- Ruff and Ruff format pass.
- Focused cache/revision tests pass.
- Existing Story Analysis, AI Entity Resolution, XPD, Story Intelligence and dashboard tests remain green.
- Full pytest has no regressions.
- Opening AI-enabled review/view windows results in zero new AI calls.
- Only explicit Analyse/Reanalyse commands execute AI.
- Source changes produce `stale` state without automatically running AI.
- Cache survives application restart.
- Successful explicit reanalysis increments analysis version and revision.
- Failed reanalysis leaves the prior successful artifact intact.
