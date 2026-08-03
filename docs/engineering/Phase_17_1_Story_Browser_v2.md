# Phase 17.1 — Story Browser v2

## Purpose

Story Browser v2 changes the Story workspace from a flat scene list into the central
production navigator for VSCS.

The implementation preserves the existing `story/scenes.json` schema. Existing projects
therefore open without migration while the browser projects their scenes into a richer
production hierarchy.

## Production hierarchy

The first v2 hierarchy is:

```text
Current Production
├── Season 1
│   └── EP-001
│       └── Act 1
│           └── Scene
│               └── Generated Shot
└── Promotional Content
    └── Trailer, Teaser, Promo, Test or Special container
        └── Act 1
            └── Scene
                └── Generated Shot
```

Season and act metadata are currently safe projections over the existing scene model.
Later production phases may persist explicit seasons and acts without changing this
browser contract.

## Production dashboard

The dashboard reports:

- production containers;
- scenes;
- generated shots;
- planned scenes;
- ready scenes;
- draft scenes;
- estimated duration;
- unique referenced assets.

## Readiness states

Story Browser v2 derives status without changing stored scene data:

- **Draft** — one or more required scene fields are incomplete;
- **Ready** — required story fields are complete;
- **Planned** — an SSIE plan has been generated;
- **Complete** — reserved for downstream production completion.

## Search and filtering

The workspace supports free-text search across visible hierarchy labels, types,
identifiers and statuses. A status selector filters the hierarchy while preserving
matching parent paths.

## Compatibility

The following existing behaviour remains available:

- New Scene;
- Edit Scene;
- Delete Scene;
- Generate SSIE Plan;
- canonical location, participant and required-asset catalogs;
- Scene Editor onboarding framework;
- scene and shot detail inspection;
- existing `scenes.json` project storage.

## Architecture

`vscs.application.story.hierarchy` contains the UI-independent hierarchy projection,
status derivation and statistics. `StoryBrowserV2Widget` consumes that projection and
keeps the presentation layer separate from story persistence and SSIE planning.

## Phase boundary

Phase 17.1 establishes the production navigation and dashboard foundation. The following
work intentionally belongs to later phases:

- detailed shot editing — Phase 17.2;
- ACPP creation and editing — Phase 17.3;
- prompt compilation — Phase 17.4;
- deeper canonical-asset preview integration — Phase 17.5;
- render execution and production status completion — Phase 17.6.

## Quality gate

Phase 17.1 uses the VSCS Development Methodology v2 Level 1 gate:

- Ruff clean;
- targeted hierarchy and Story Browser tests;
- existing StoryService and Scene Editor regression tests;
- manual verification through the real VSCS Story workspace.
