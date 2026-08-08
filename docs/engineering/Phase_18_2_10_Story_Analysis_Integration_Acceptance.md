# Phase 18.2.10 — Story Analysis Integration & Acceptance

## Purpose

Close Phase 18.2 by validating Story Analysis as one integrated production subsystem rather than adding another analysis feature.

## Acceptance boundary

The acceptance layer is read-only. It must never invoke an AI provider, approve or reject entities, create XPD assets, create CAPs, edit Story source content, or alter Story lifecycle state.

## Integrated pipeline

Story → explicit Analyse/Reanalyse → deterministic analysis → configured AI semantic analysis → entity resolution → XPD canonical matching → human review → Approved Story Intelligence → Story Knowledge Graph → Story Intelligence Dashboard → production readiness.

## Acceptance checks

The Integration Acceptance report validates:

- Story source remains readable.
- A persisted Story Analysis cache exists.
- Cached revision is current or explicitly reported stale.
- Cached deterministic AnalysisResult is readable.
- Cached AI EntityResolutionResult is readable.
- Cached StoryKnowledgeGraph is readable.
- Analysis provider metadata is recorded.
- Approved Story Intelligence can be loaded.
- Every approved entity canonical link resolves to the current Asset registry.
- Pending human review is surfaced as a production warning rather than a subsystem failure.
- Shot Planning readiness is reported independently of integration health.
- Generation Asset/CAP readiness is reported independently of integration health.

## Result semantics

PASS means the integration contract is healthy.

WARNING means the subsystem is healthy but production work requires attention, for example a stale analysis revision, pending AI entity review, or incomplete CAP readiness.

FAIL means an integration artifact is missing or invalid, such as a missing cache, unreadable source, corrupted cached artifact, unreadable Story Intelligence, or a broken approved canonical Asset link.

## Cache and AI execution rule

The Integration Acceptance report consumes persisted artifacts only. Refreshing the report must not call OpenAI or any other configured AI provider. Only explicit Analyse Story or Reanalyse Story commands may execute the analysis pipeline.

## Failure/recovery expectations

A missing source or cache produces an actionable FAIL report without mutating prior Story Intelligence. A stale cache remains viewable and is reported as WARNING until the user explicitly reanalyses. Corrupt cached artifacts produce FAIL and should not silently replace previously valid canon or decisions.

## Manual acceptance workflow

1. Analyse a Story once with OpenAI and confirm the provider diagnostic.
2. Open Integration Acceptance and confirm the provider, cache revision and artifact checks.
3. Refresh the report repeatedly and confirm there is no OpenAI delay or new API execution.
4. Close/reopen the project and restart VSCS; confirm the same persisted analysis remains available.
5. Modify the Story source and confirm Integration Acceptance reports the cache as stale without invoking AI.
6. Explicitly reanalyse and confirm the analysis version increments and the cache becomes current.
7. Approve an existing XPD-matched entity and confirm the canonical-link check passes after restart.
8. Leave one AI entity Proposed and confirm the report is PASSED WITH WARNINGS, not FAILED.
9. Complete entity review while leaving one CAP incomplete and confirm integration still passes while Generation readiness remains not ready.
10. Verify Review AI Entities, Story Intelligence, cached graph reload and Integration Acceptance never trigger AI.

## Phase 18.2 completion criterion

Phase 18.2 is complete when Ruff, formatting, focused acceptance tests, all Story Analysis/AI/XPD/cache regressions and the manual acceptance workflow pass with no unresolved integration failures.
