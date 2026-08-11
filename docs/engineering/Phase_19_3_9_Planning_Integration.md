# Phase 19.3.9 — Planning Integration

## Objective

Close Phase 19.3 Production Planning by converting a current Approved Planning Review into one immutable renderer-neutral planning package that becomes the authoritative input to Phase 19.4 Prompt Compilation.

## Input authority

Integration consumes only governed, reviewed planning:

1. Shot Plan;
2. Shot-to-Asset bindings plus resolved Asset/CAP/canonical-reference/behaviour context;
3. Camera Plan;
4. Lighting Plan;
5. Environment Plan; and
6. current Approved Planning Review.

If the Planning Review is missing, Draft, stale or otherwise not production-ready, integration is blocked.

## Package contract

The package is persisted in `planning/integrated_planning_packages.json` with schema version `1.0`. Each package stores its deterministic identity, Shot and Review provenance, planning fingerprint, package fingerprint and canonical JSON payload.

The payload is a snapshot, not another authoring model. It deliberately preserves the exact governed planning values needed downstream and includes resolved Behaviour Profile context already supplied by Asset Resolution.

## Automation and history

Approving Planning Review automatically materializes the package. Repeating integration without any planning change returns the existing package. If planning changes, the old package ceases to be current. Once the revised planning is reviewed and approved, integration creates a new package and preserves the previous one for audit/history.

## Phase 19.4 handoff

`require_current_package(shot_id)` is the application boundary for Prompt Compilation. Phase 19.4 should consume this package rather than independently reading mutable Shot, Asset, Camera, Lighting or Environment services.

## Explicit exclusions

Phase 19.3.9 does not compile natural-language prompts, renderer prompts, ACPP, workflows, render requests, audio, scheduling or QA. Those belong to later production phases.

## Acceptance criteria

- integration requires a current Approved Planning Review;
- the package contains all governed Shot-level planning authorities and resolved asset context;
- identical planning integrates idempotently;
- history is preserved across later reviewed revisions;
- stale planning has no current package;
- package persistence is deterministic and atomic;
- Planning Review displays Phase 19.4 handoff status and auto-integrates on approval;
- no new creative authoring is introduced by Integration;
- Ruff, Ruff format, mypy, focused tests, complete pytest and coverage gates pass.
