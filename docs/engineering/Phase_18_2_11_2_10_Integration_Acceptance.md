# Phase 18.2.11.2.10 — Integration & Acceptance

## Purpose

Phase 18.2.11.2.10 formally closes the Phase 18.2.11.2 Canonical Production Contract implementation by proving that the independently implemented CAP subsystems operate as one governed production pipeline.

This phase does not introduce a new canonical authority. It validates and integrates the authorities already established by the preceding phases.

## Authoritative Pipeline

The accepted end-to-end flow is:

1. Asset registration establishes the production asset identity.
2. The approved ChatGPT MASTER is registered, approved, and locked through governed Asset/CAP creation.
3. Category Reference Templates determine required, recommended, and optional production views.
4. Derived Reference Generation creates MASTER-conditioned Candidate views.
5. The Reference Library governs approval, locking, rejection, archival, provenance, and lineage.
6. The Readiness Framework evaluates Identity, References, Generation, and Production independently.
7. Production Projection publishes an immutable downstream representation containing only Approved/Locked production references.
8. The CAP UI consumes the same application services and does not recalculate lifecycle, readiness, or projection rules.
9. Production Planning and later systems must consume `ProductionProjectionService` rather than reading CAP persistence directly.

## Integration Refinement

The desktop MainWindow now resolves the shared `ProductionProjectionService` from `ApplicationServices` and supplies that exact instance to the Canonical Profiles workspace.

This removes a duplicate application-service construction path that previously existed in the UI integration layer. The CAP workspace therefore consumes the same projection/readiness authority that future Production Planning will consume.

A fallback service construction path remains inside the standalone widget installer only for isolated widget tests or embedding contexts that do not own the VSCS composition root.

## Acceptance Matrix

| Capability | Acceptance condition |
|---|---|
| Production Contract specification | Stable canonical domain contract exists and remains scene-independent |
| CAP domain compatibility | Legacy CAP persistence remains compatible while newer structured contract types coexist |
| Reference Library | MASTER and derived references retain provenance, lifecycle, lineage and file ownership |
| Asset creation integration | New assets can establish a governed locked ChatGPT MASTER |
| Derived reference generation | Required views are generated from the locked MASTER through replaceable providers |
| ComfyUI provider | Qwen workflow integration can create a real derived reference candidate |
| Category templates | Required/recommended/optional reference requirements are category-driven |
| Readiness | Identity, Reference, Generation and Production readiness are deterministic and AI-free |
| Projection API | Downstream consumers receive immutable, versioned projections with deterministic checksums |
| CAP UI | Canonical Profiles exposes production state without becoming a second source of truth |
| Shared composition | MainWindow/CAP UI consume the composition-root `ProductionProjectionService` |

## Readiness and Persistence Truth

The acceptance suite deliberately preserves the distinction between reference coverage and production readiness.

Candidate references may satisfy coverage for duplicate-generation prevention, but only Approved or Locked references satisfy Reference Readiness and may appear in Production Projection.

The legacy CAP persistence model still does not persist all structured Production Contract collections. In particular, categories such as Ship that require structured functional capabilities and canonical constraints remain Production BLOCKED even when all required visual references are approved.

This is intentional. Phase 18.2.11.2.10 does not infer structured canonical data from prose and does not weaken readiness gates to manufacture a READY state.

A Location asset is used as the positive acceptance path because its current category contract can legitimately reach Production READY using the persisted fields available today. A Ship asset is used as the negative acceptance path to verify that missing structured persistence remains visible as explicit blockers.

## Projection Invalidation

`ProductionProjection.checksum()` is accepted as the deterministic dependency fingerprint for downstream caches and planning artifacts.

The acceptance suite verifies that changes to canonical CAP content alter the projection checksum. Later systems may therefore store the checksum alongside planning/render artifacts and invalidate them when the canonical production contract changes.

## UI Acceptance

The Canonical Profiles workspace must expose:

- Asset ID
- CAP Title
- Category
- Version
- Status
- Published References
- Readiness
- Production state
- Generate Production References
- Readiness
- Production Projection

The UI must not expose a competing legacy canonical-image generation path as the production mechanism.

MASTER ownership remains in Assets. Derived production-view generation remains in Generate Production References. Lifecycle governance remains in the Reference Library.

## Automated Acceptance

The phase adds two acceptance suites:

- `tests/unit/test_cap_integration_acceptance.py`
- `tests/integration/test_cap_production_contract_acceptance.py`

They prove:

- MainWindow consumes the shared projection service from the composition root.
- The CAP workspace exposes the governed production actions.
- A Location progresses from locked MASTER through missing-reference generation, approval, readiness and a production-ready projection.
- Candidate references are excluded from Production Projection until approved.
- A Ship with complete approved visual coverage remains blocked when required structured functional identity and constraints are absent.
- `require_ready()` enforces the authoritative Production gate.
- Projection checksums change when canonical contract content changes.
- The refactored CAP UI reflects the same projection state used by the application API.

## Non-goals

This close-out phase does not:

- implement Production Planning;
- persist new structured CAP facts/capabilities/constraints;
- integrate Prompt Compilation with Production Projection;
- integrate Video Generation with Production Projection;
- alter ComfyUI generation algorithms;
- introduce a new readiness heuristic;
- infer canonical facts using AI.

Those responsibilities belong to later dedicated phases.

## Completion Boundary

Phase 18.2.11.2 is accepted when:

1. Ruff check and format checks pass for all changed files.
2. The focused Integration & Acceptance suite passes.
3. The broader CAP Production Contract regression suite passes.
4. The full project pytest suite passes.
5. The manual Canonical Profiles smoke test confirms the production workspace, governed generation action, readiness view and Production Projection inspector remain operational.

After acceptance, the CAP subsystem is considered a stable upstream production dependency and VSCS may proceed into Production Planning using `ProductionProjectionService` as the canonical asset boundary.
