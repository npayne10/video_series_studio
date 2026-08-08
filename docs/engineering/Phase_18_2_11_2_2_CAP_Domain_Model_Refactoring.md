# Phase 18.2.11.2.2 — CAP Domain Model Refactoring

## Purpose

Introduce the backend Canonical Production Contract domain model approved in Phase 18.2.11.2.1 without prematurely migrating persistence or redesigning the CAP UI.

## Architectural boundary

The existing `CanonicalAssetProfile` and `CanonicalReference` persistence models remain operational for compatibility. The new immutable contract models define the target production API that later 18.2.11 phases will populate from persisted CAP data.

No database migration, UI redesign, asset-creation automation, category template engine or derived-image generator is introduced in this phase.

## New contract model

`CanonicalProductionContract` owns only scene-independent canonical information:

- `CanonicalIdentity`
- human-readable canonical description
- structured `CanonicalFact` records
- visual identity
- structured `FunctionalCapability` records
- structured `CanonicalConstraint` records
- production guidance
- structured `ProductionReference` records
- independent `CAPReadiness` gates

Scene actions, camera, lighting, dialogue, transient emotional state and other shot-specific facts remain outside CAP.

## Reference contract

Exactly one reference in a valid Canonical Production Contract must belong to the `MASTER` family.

The MASTER:

- uses the MASTER view;
- has `CHATGPT_MASTER` origin;
- has no parent;
- is the authoritative visual identity.

VSCS-derived references:

- use a non-MASTER production view;
- record `VSCS_DERIVED` origin;
- record the MASTER as their explicit parent;
- enter the normal candidate/review/approval lifecycle;
- never become an independent canonical authority.

The initial viewpoint taxonomy includes MASTER, three-quarter, front, rear, left/right, port/starboard, top/bottom, character profiles, full body, face, aerial, orbit, surface, interior, detail and variant roles. Later category-template work will decide which roles are required for each asset category.

## Reference families

The domain now distinguishes:

- MASTER
- Production View
- Detail
- Interior
- Variant

These families replace the future production dependency on the legacy Primary/Secondary/Supplementary importance model. Legacy reference models remain unchanged until the dedicated lifecycle/migration phase.

## Provenance

The contract distinguishes:

- ChatGPT-authored MASTER
- VSCS-derived production reference
- imported legacy reference
- other external reference

Each production reference can carry parent identity, generator identity, version, lifecycle, approver and advisory quality score.

## Readiness

The new contract separates:

- Identity readiness
- Reference readiness
- Generation readiness
- Production readiness
- Canonical lock state

Each gate can be incomplete, ready, blocked or not applicable, with blockers and warnings retained separately.

## Production projection

`ProductionAssetProjection` is the read-only downstream boundary. It is created from a `CanonicalProductionContract` and publishes only APPROVED or LOCKED references.

Production Planning and later systems must consume this projection rather than legacy CAP repository/UI details.

## Backward compatibility

Legacy `CanonicalAssetProfile.reference_paths` is intentionally untouched in this phase. It remains readable by existing projects and UI code while the structured production contract is introduced alongside it. Later migration work will retire the duplicate path collection only after the repository and UI consume the structured reference contract.

## Approved image-generation policy

The Phase 18.2.11.1 assessment is updated to reflect the approved policy:

- VSCS does not author or silently regenerate the MASTER.
- ChatGPT remains the authoritative MASTER creator.
- VSCS retains derived production-reference generation.
- Existing Generate Canonical Images behavior is to be replaced by Generate Production References.
- Feedback regeneration remains valid only for derived candidate references.

## Acceptance criteria

- New contract models are scene-independent and immutable.
- A contract requires exactly one ChatGPT-authored MASTER.
- VSCS-derived references require direct MASTER traceability.
- Reference IDs are unique within one CAP contract.
- Structured facts, capabilities and constraints are machine-consumable.
- Readiness dimensions are independent.
- The production projection hides candidate/rejected/archived references.
- Legacy CAP models continue to instantiate and coexist with the new contract.
- No persistence migration or UI behavior change occurs in this phase.
