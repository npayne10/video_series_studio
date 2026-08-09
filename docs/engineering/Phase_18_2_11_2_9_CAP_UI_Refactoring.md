# Phase 18.2.11.2.9 — CAP UI Refactoring

## Purpose

Refactor the Canonical Profiles workspace so its presentation matches the Phase 18.2.11 production contract and no longer exposes competing generation paths.

The UI remains a consumer of application/domain services. It must not recalculate readiness, reference lifecycle, category requirements, or production projection rules.

## Canonical Profiles Workspace

The CAP list now presents:

- Asset ID
- CAP title
- Asset category
- CAP version
- CAP status
- Published production reference count
- Overall readiness percentage
- Production gate state

Published reference counts come from `ProductionProjectionService`, therefore only Approved/Locked references are represented as downstream production references.

The Production column reflects the authoritative Phase 18.2.11.2.7 `ReadinessReport.production_ready` gate.

## Production Projection Inspector

A new `Production Projection` action opens a read-only inspector for the selected CAP.

The inspector displays:

- canonical identity
- CAP/projection schema versions
- deterministic projection checksum
- all four readiness dimensions
- canonical description and visual identity
- production guidance
- structured fact/capability/constraint counts
- Approved/Locked production references
- readiness blockers and warnings

The dialog consumes the immutable `ProductionProjection` API introduced in Phase 18.2.11.2.8.

## Reference Workflow Rationalisation

The older CAP-editor `Generate Canonical Images…` path is retired from the production UI. It predates the governed MASTER-derived reference workflow and would duplicate the responsibilities now owned by:

1. Asset MASTER governance;
2. Category Reference Templates;
3. Derived Reference Generation;
4. ComfyUI Derived Reference Provider;
5. Reference Library lifecycle governance.

The CAP editor therefore directs operators to `Generate Production References` in the Canonical Profiles workspace.

`Add Reference…` is reframed as `Import External Reference…`. This remains valid for externally supplied supporting material and does not replace MASTER or VSCS-derived production-reference governance.

## Ownership Boundaries

- MASTER creation/revision: Assets workflow.
- Derived required/recommended/optional views: Generate Production References.
- Reference lifecycle: Reference Library / Canonical Reference Service.
- Readiness: CAPReadinessService.
- Downstream publication: ProductionProjectionService.
- CAP UI: display, selection, navigation and operator actions only.

## Compatibility

Legacy CAP persistence and historical reference tooling remain available to existing code, but redundant generation controls are not exposed as competing production actions.

The refactor is additive at the service/domain boundary and does not change CAP persistence schemas.

## Acceptance Criteria

1. Canonical Profiles lists Category, Published References, Readiness and Production state.
2. Search, status filtering and Refresh retain the refactored eight-column table.
3. Production Projection opens a read-only representation of `ProductionProjection`.
4. Published reference count includes only Approved/Locked production references.
5. Production state is sourced from the authoritative readiness report.
6. CAP editor explains MASTER/derived-reference ownership.
7. External reference import remains available.
8. Legacy `Generate Canonical Images…` is hidden/disabled when the historical extension is installed.
9. No persistence schema or production-domain decision is implemented in presentation code.
10. Existing CAP, reference, readiness, derived-generation and production-projection regression suites remain green.
