# Phase 17.5.2 — Asset Browser and Selection Integration

## Objective

Provide a reusable, project-aware browser that exposes Asset Manager records together with their CAP and approved canonical-reference readiness, then use that browser for production asset selection in the ACPP Editor.

## Architecture

```text
AssetService
    +
AssetResolutionService
    ↓
AssetBrowserService
    ↓
ResolutionAssetPickerDialog
    ↓
BrowseableACPPEditorDialog
```

## Application contracts

`AssetBrowserFilter` defines stable filtering by query, category, asset status, and resolution status.

`AssetBrowserItem` combines display-safe asset metadata with the authoritative `AssetResolutionResult`. It exposes CAP version, approved-reference count, resolution status, and selection readiness.

`AssetBrowserResult` records the filtered items and the total project-asset count.

`AssetBrowserService` provides deterministic browsing and explicit single-asset resolution for downstream editors.

## UI integration

`ResolutionAssetPickerDialog` provides:

- text search across ID, name, description, category, and tags;
- category filtering;
- approved-asset filtering;
- Production-ready filtering;
- Asset, resolution, CAP-version, and approved-reference columns;
- diagnostic details for partial assets;
- keyboard and double-click selection through the standard Qt dialog contract.

The existing lightweight `AssetPickerDialog` remains available for compatibility. Production editors can adopt the resolution-aware picker incrementally.

## ACPP integration

The ACPP Assets tab now launches `ResolutionAssetPickerDialog`. A selected browser row supplies its stable Asset ID to the existing ACPP binding workflow. The ACPP package format is unchanged.

The Story workspace registers the shared asset-resolution and browser services lazily after Asset, CAP, and Canonical Reference services are available, then injects `AssetBrowserService` into the ACPP editor path.

## Deliberate exclusions

This phase does not yet:

- inject CAP text into Prompt Graph nodes;
- copy reference paths into renderer requests;
- invalidate dependent shots when an asset changes;
- add multi-select asset binding;
- replace every legacy picker in one step.

Those capabilities belong to Phases 17.5.3 through 17.5.5.

## Verification

Focused coverage verifies browser filtering, deterministic ordering, resolution status, shared service registration, and ACPP selection integration.

## Outcome

VSCS now has one reusable production asset-browser layer that presents authoritative readiness information and connects selected Asset IDs to the ACPP workflow without requiring users to memorise identifiers.
