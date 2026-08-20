# ADR 0070 — Phase 20.15.1a Provider-Ready Production Package Resolution

## Status

Accepted for implementation in Phase 20.15.1a. Phase acceptance remains subject to local automated, static and UI/functional validation.

## Context

Phase 20.15.1 established compilation of approved ProductionTask authority into the ComfyUI v7.1.4 Production Package. Live A004 validation proved that attaching the correct package file is not sufficient to prove that the provider receives enforceable production inputs.

A004 demonstrated four gaps:

1. a 22 second approved shot compiled to 145 frames at 24 fps and therefore rendered only about six seconds;
2. the governed package seed existed but the committed workflow used a hard-coded RandomNoise seed;
3. canonical references remained project-relative planning references rather than resolved provider-accessible visual inputs with an explicit reference strategy;
4. ComfyUI could report a successful history output while VSCS failed production reconciliation when the configured output directory was nested below ComfyUI's history-relative `output` root.

The previous Xorix production compiler demonstrated a useful execution contract: resolved visual assets, resolved production profiles, explicit reference plans, timing/generation/output contracts, compiled positive and negative prompts, and continuity policies. VSCS must retain those capabilities without making the architecture production-specific.

## Decision

### Provider-neutral authority remains authoritative

Phase 19 approved ProductionTask/ProductionPackage authority remains the source of truth. Phase 20.15.1a does not create a second approval system and does not alter human governance.

### Filesystem resolution belongs to infrastructure

The application compiler continues to compile provider-neutral timing, prompts, render settings and deterministic seed values. Local project filesystem resolution is performed by infrastructure using the active VSCS project root.

A reference such as:

`assets\characters\CAP-CHR-001-Master-V1.png`

is resolved against the active project directory. Required path-like canonical references must physically exist before the package can become executable. Stored checksums are verified when present.

### Provider-ready package sections

The executable package adds additive provider-ready sections:

- `resolved_visual_assets`
- `resolved_production_profiles`
- `profile_prompt_instructions`
- `reference_plan`
- `temporal_start_policy`
- `resolved_render_contract`
- `timing`
- `generation`
- `prompts`
- `output`
- `continuity_contract`
- `validation_contract`

The existing approved `production_authority` remains embedded unchanged for provenance and audit.

### Reference strategy

The default local ComfyUI reference strategy is `identity_first_minimal`.

Character, ship and vehicle canonical images with valid resolved paths become IC-LoRA identity references. Other governed visual assets remain prompt/composition metadata unless a later provider capability explicitly maps them differently. Canonical assets must not be silently merged, substituted or repurposed as continuity frames.

### Timing consistency

When approved authority contains an explicit frame count it remains authoritative. When frame count is absent but an approved duration exists, the compiler derives:

`frame_count = round(duration_seconds * fps)`

The executable package stores all three values and rejects materially inconsistent timing contracts.

### Governed seed enforcement

The committed v7.1.4 workflow must consume the Production Package seed. `RandomNoise.noise_seed` is therefore wired to Production Package loader output 12. Static ComfyUI input assurance includes this consumer path.

### Output-root reconciliation

ComfyUI history output paths are relative to ComfyUI's `output` root. If the configured ComfyUI output directory points to a nested folder under an ancestor named `output`, the production backend normalizes reconciliation to that root. A correctly configured root is preserved unchanged.

### No authority changes

This phase does not change:

- ProductionTask approval authority;
- schedule or queue authority;
- provider selection authority;
- profile-scoped attempt/retry authority from Phase 20.16.2;
- Generated Media review, approval or selection authority;
- ProductionTask completion reconciliation rules.

## Consequences

A Production Package can now be structurally complete yet non-executable if a required canonical file is missing or its checksum no longer matches approved authority. This is intentional fail-safe behavior.

The ComfyUI custom Production Package Loader and Canonical Composition Builder remain provider-specific runtime components. Local UI validation must prove that their installed versions accept the additive provider-ready contract and that loader output 12 is the governed seed output before Phase 20.15.1a is accepted.

## Validation requirement

Phase 20.15.1a is not accepted until local tests, Ruff, mypy and full regression are clean and a manual UI validation proves:

1. the current task recompiles a provider-ready Production Package;
2. project-relative canonical paths resolve to real project files;
3. the 22-second A004-equivalent shot compiles to 528 frames at 24 fps;
4. submitted ComfyUI history shows the correct package path and RandomNoise seed binding/value;
5. resolved canonical identity references are consumed by the installed composition/reference nodes;
6. ComfyUI output is reconciled and ingested as Generated Media when the physical file exists;
7. profile-scoped execution/retry behavior remains unchanged.
