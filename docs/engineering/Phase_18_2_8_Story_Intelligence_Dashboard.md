# Phase 18.2.8 — Story Intelligence Workspace & Production Dashboard

## Objective

Expose the Story Analysis, AI Entity Resolution, XPD canon and Approved Story Intelligence layers as one operational production-readiness workspace.

The dashboard is a derived read model. It does not modify manuscript text, AI review decisions, XPD records or CAP state.

## Architecture

```text
Story Source
    ↓
Story Analysis Pipeline
    ↓
AI Entity Resolution
    ↓
Approved Story Intelligence ──→ XPD / Asset Registry
    ↓                              ↓
Story Intelligence Dashboard ← CAP readiness tags
    ↓
Production readiness signals
```

## Dashboard metrics

The workspace reports:

- Story Analysis status and completed stage count
- AI narrative confidence
- approved / proposed / rejected entity counts
- XPD/canonical asset coverage
- unresolved or ambiguous entity count
- approved canonical assets with ready CAPs
- approved canonical assets requiring CAP work
- Story Knowledge Graph node and edge counts
- narrative summary, themes, tone, setting and production notes
- analysis diagnostics
- production blockers and recommended actions

## Entity readiness table

Each AI-recognised production entity exposes:

- review status
- category
- canonical name proposed by AI
- confidence
- resolution kind
- canonical XPD / Asset ID
- CAP status
- next production action

Filters support pending review, approved, rejected, XPD matched, CAP required and ambiguous matches.

## Readiness gates

### Shot Planning

Shot Planning is ready only when:

- Story Analysis completed successfully;
- AI Entity Resolution is available;
- no entity proposals remain awaiting review;
- no active entity has an ambiguous XPD match; and
- every approved entity has a canonical asset identity.

CAP completion does not block Shot Planning.

### Generation Assets

Generation Asset readiness additionally requires every approved canonical entity used by the Story to have a CAP status of `Approved` or `Locked`.

This distinction allows planning to continue while preventing an incomplete canonical asset from being presented as render-ready.

## Canon boundary

The dashboard never:

- approves or rejects entities automatically;
- creates XPD assets;
- modifies XPD workbook content;
- creates or approves CAPs;
- edits the Story manuscript;
- changes Story lifecycle state.

The existing AI Entity Review workflow remains the authority for human entity decisions.

## UI integration

The Story Analysis toolbar gains a `Story Intelligence` action next to `Review AI Entities`.

The dashboard provides:

- refresh;
- direct entry into AI Entity Review;
- automatic refresh after AI review closes;
- entity search and readiness filters;
- XPD and CAP progress indicators;
- narrative intelligence view; and
- production-readiness diagnostics.

## Acceptance criteria

1. Ruff and Ruff formatting pass for all Phase 18.2.8 files.
2. Dashboard unit tests pass.
3. Dashboard Qt integration test passes.
4. Existing Story Analysis, AI Entity Resolution, XPD import and Story Intelligence regressions remain green.
5. The Xorix test Story displays persisted approval decisions and correct XPD matches.
6. `James Spence` continues resolving to canonical `Commander James Spence` / `CAP-CHR-001`.
7. Pending proposals block Shot Planning readiness.
8. Resolving all proposals makes Shot Planning ready.
9. Approved entities without ready CAPs show Generation Asset attention while Shot Planning remains ready.
10. The dashboard performs no canon mutation by itself.
