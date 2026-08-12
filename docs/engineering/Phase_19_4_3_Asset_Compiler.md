# Phase 19.4.3 — Asset Compiler

## Objective

Turn governed Shot asset bindings and canonical resolutions into explicit, reviewed, provider-neutral Asset authority inside the canonical Production Package.

## Authoritative input

The input is the current Phase 19.4 `ProductionPackage`, derived from the current approved Phase 19.3 Integrated Planning Package.

The Asset Compiler consumes only the package's governed `assets` snapshot. It does not discover substitute assets, create missing story entities or select provider-specific references.

## Draft authority

`AssetCompilationDraft` stores:

- Shot identity;
- source Production Package identity;
- source planning fingerprint;
- detached governed asset binding/resolution snapshots;
- optional human production review notes; and
- Draft/Ready governance state.

Creating a Draft copies only governed Production Package asset information.

## Compilation

Only a current Ready Asset Compiler Draft may compile.

For each governed asset entry, compilation preserves the original `binding` and `resolution` and adds a normalized `production` view containing, where available:

- asset ID;
- binding ID;
- production role;
- asset requirement;
- category;
- canonical reference;
- dependency checksum; and
- `provider_neutral = true`.

Compilation derives a new immutable Production Package revision. It updates only the canonical `assets`, derived `references`, Asset validation state and package lifecycle state. Existing Action & Performance, Camera, Lighting, Environment and all other package sections remain preserved.

The validation marker is:

`assets_complete = true`

Historical Production Package revisions remain preserved and identical compilation is idempotent.

## Staleness and recovery

If approved Phase 19.3 planning changes, the current Production Package source fingerprint and/or governed asset snapshot changes. The existing Asset Compiler Draft becomes stale and cannot be marked Ready or compiled.

A stale Draft exposes **Refresh from Current Package**. Refresh replaces only governed asset input with the current package snapshot and updates source identity/fingerprint while preserving human production review notes.

A stale Ready record must first be returned to Draft before it can be refreshed and reviewed.

## Workspace

Phase 19.4.3 extends the existing Production Planning workspace with an **Assets** tab beside **Action & Performance**.

The left Shot table exposes independent Action and Asset compiler states. The Assets tab shows governed binding ID, resolved asset ID, role, requirement and canonical reference, plus optional human review notes and governance actions.

No model, renderer, sampler, ComfyUI workflow or provider prompt controls are introduced.

## Acceptance criteria

- Asset Compiler Draft is seeded only from governed current Production Package assets.
- No missing asset identity or requirement is fabricated.
- Governed binding and canonical resolution remain preserved in compiled output.
- Compiled Asset production views are provider-neutral.
- Ready Asset records are immutable until Return to Draft.
- Only current Ready Asset authority may compile.
- Upstream approved planning changes make existing Asset authority stale.
- Stale Draft refresh loads current governed assets while preserving human review notes.
- Compilation derives a new immutable Production Package revision.
- Existing Action & Performance and all unrelated package sections remain unchanged.
- Canonical reference index remains synchronized with compiled assets.
- `assets_complete` is recorded.
- Historical package revisions are preserved and deterministic recompilation is idempotent.
- Production Planning exposes the Asset Compiler in the same Phase 19.4 workspace.
- Provider-specific controls remain absent.
- Focused tests, Ruff, Ruff format, strict mypy, full pytest and coverage gates pass.
