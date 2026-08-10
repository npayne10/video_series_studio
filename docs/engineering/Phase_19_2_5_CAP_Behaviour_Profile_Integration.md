# Phase 19.2.5 — CAP ↔ Behaviour Profile Integration

## Objective

Connect Canonical Asset Profiles to governed Behaviour Profiles without weakening either lifecycle. CAPs identify the behaviours an asset can perform; production resolution supplies the current authoritative BEP version.

## Scope

Phase 19.2.5 adds:

- `CAPBehaviourIntegrationService`;
- validation of BEP production authority before CAP linkage;
- CAP asset-category compatibility validation;
- stable BEP identity persistence in existing `behaviour_references`;
- deterministic production resolution to Canonical/Approved BEP versions;
- CAP workspace action `Behaviour Profiles…`;
- a selection dialog that exposes only compatible production-authoritative BEPs;
- stale/unavailable link visibility and clean-up on save;
- unit and Qt integration tests;
- ADR-0015.

## Explicit non-goals

This phase does not:

- change the Behaviour Profile domain schema;
- add another database migration or join table;
- allow Draft or Proposed BEPs into production CAP links;
- embed provider-specific rendering or simulation instructions;
- consume behaviours in shot planning or prompt compilation yet.

## Application contract

`CAPBehaviourIntegrationService.available_for_cap(asset_id)` returns one current production-authoritative version per compatible BEP identity.

`set_behaviours(asset_id, profile_ids)` normalizes and deduplicates BEP identities, validates production authority and category compatibility, then persists them through `CAPService.update()`.

`resolve_for_cap(asset_id)` converts CAP-stored BEP identities to concrete governed BEP versions for downstream production use.

`link()` and `unlink()` provide focused mutations while retaining the same validation boundary.

## Resolution policy

For a given BEP identity:

1. Canonical beats Approved.
2. When no Canonical version exists, the highest Approved version is selected.
3. Draft and Proposed versions are ignored.
4. A missing production-authoritative version blocks resolution.
5. The resolved BEP must include the asset's category.

## UI contract

The Canonical Profiles workspace gains a `Behaviour Profiles…` button. It is enabled only when a CAP row is selected.

The dialog lists compatible production-authoritative BEPs with:

- BEP identity;
- name;
- resolved version;
- authority.

Existing stale or incompatible references are displayed as unavailable and are removed if the user saves a corrected selection.

## Acceptance tests

Automated acceptance must prove:

- stable BEP identities are persisted;
- Canonical precedence over Approved revisions;
- Draft-only identities are rejected;
- incompatible asset categories are rejected;
- available lists exclude Draft and incompatible profiles;
- duplicate links are removed;
- unlink persistence works;
- CAP workspace exposes the linkage action;
- the dialog round-trips selected links;
- existing CAP/BEP/bootstrap tests remain green.

## Manual acceptance

1. Open a project containing a CAP and at least one Approved/Canonical compatible BEP.
2. Open **Canonical Profiles** and select the CAP.
3. Click **Behaviour Profiles…**.
4. Verify only compatible production-authoritative BEPs are selectable.
5. Select one or more BEPs and save.
6. Reopen the dialog and verify the selection persists.
7. Create a newer Approved revision of a linked BEP while retaining an older Canonical version; verify production resolution still returns the Canonical version.
8. Confirm CAP editing, Behaviour Profile editing, and project reopen behavior are unchanged.
