# Phase 20.18.2 — Governed Reference Persistence Repair

## Status

Implemented for local validation. Phase 20.18.2 remains open and is not accepted until automated, UI, live-provider, GeneratedMedia/provenance, and owner acceptance complete.

## Finding

Live projects persist production authority under the project `production` area and do not contain the `story/acpp` directory assumed by the original Phase 20.18.1 UPD bridge. As a result, `PersistedGovernedReferencePlanSource` returned no plan and UPD/XPC could compile without the new governed ReferencePlan even when older compiled packages contained legacy reference authority.

The legacy reference structure is schema `1.1` and contains provider-oriented fields such as `identity_references`, `metadata_assets`, `ic_lora`, and continuity delivery. It is not equivalent to the Phase 20.18.1 provider-neutral governed ReferencePlan.

## Repair

### Durable production authority

Governed shot plans are persisted at:

```text
<project>/production/governed_reference_plans.json
```

The store is keyed by Shot ID and preserves a detached `reference_plan` payload plus provenance metadata.

### Backward compatibility

The former `story/acpp` lookup remains read-only as a compatibility fallback for projects that actually contain those records. It is no longer the primary live persistence contract.

### No silent legacy fallback

If no governed plan exists but a matching compiled package contains legacy schema `1.1` reference authority, UPD resolution raises a migration-required error instead of silently returning `None`.

### Explicit migration

`GovernedReferencePlanPersistenceService` provides an explicit legacy migration path. Migration:

- uses the Phase 20.18.1 `ProviderReadyReferenceResolver`;
- maps the first legacy identity to `primary_identity`;
- maps subsequent identities to `secondary_identity`;
- maps planet/location/environment/set metadata to `environment_reference`;
- preserves legacy asset IDs, image paths, checksums, and fingerprints as provenance-bearing inputs;
- classifies migrated legacy image authority as `canonical_master`;
- never promotes legacy/canonical images to `provider_ready=True` automatically;
- persists failed resolution deliberately so downstream UPD/XPC blocks rather than weakening authority.

### Provider-ready resolution

A passing governed plan must still be produced from explicit provider-ready reference facts through the existing Phase 20.18.1 resolver. Canonical approval alone remains insufficient.

## Required chain

```text
Canonical / provider-ready reference authority
        ↓
Phase 20.18.1 ProviderReadyReferenceResolver
        ↓
production/governed_reference_plans.json
        ↓
Universal Production Description
        ↓
XPC governed reference compilation
        ↓
LTX 2.3 v7.2.1 provider bindings
```

## Regression coverage

`tests/unit/test_phase_20_18_2_governed_reference_persistence.py` covers:

1. the production-authority persistence path;
2. no creation of a fake `story/acpp` store;
3. explicit blocking when only legacy compiled authority exists;
4. conservative legacy role migration;
5. no automatic provider-ready promotion;
6. persisted governed-plan propagation into UPD and XPC.

## Acceptance boundary

This repair does not mark Phase 20.18.2 accepted and does not authorize a live provider run. Local Ruff and focused pytest must pass first. The live project must then obtain a passing persisted governed ReferencePlan using provider-ready references before v7.2.1 Production execution is allowed.
