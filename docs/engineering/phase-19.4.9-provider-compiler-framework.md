# Phase 19.4.9 — Provider Compiler Framework

## Purpose

The Provider Compiler Framework translates an approved Universal Production Description into deterministic provider-specific production contracts while preserving VSCS governance and provenance.

## Authority model

Provider compilation may begin only after the Universal Production Description is approved and marked cross-authority consistent. Provider compilers consume that approved authority; they do not reinterpret the story or invent missing production intent.

Final provider-output approval remains with the user.

## Framework

The application layer provides:

- `ProviderCompiler` protocol
- `ProviderCompilerRegistry`
- provider descriptors and version identity
- persistent `ProviderCompilationDraft`
- Draft → Ready governance
- dependency-fingerprint staleness detection
- refresh from current Universal authority while preserving human review notes
- immutable Production Package derivation into `provider_outputs`

## Initial provider

Phase 19.4.9 registers the existing ComfyUI production ecosystem through `ComfyUIProviderCompiler`.

The compiler emits the `vscs.comfyui.production-input.v1` contract containing the approved Universal production text, canonical references, Shot, Camera, Lighting, Environment, Continuity and Style authority.

Workflow selection remains deliberately unresolved in this phase. The output records `workflow_id=null` with `selection_policy=downstream-provider-configuration`.

## Execution boundary

Phase 19.4.9 does **not** submit jobs to ComfyUI or any other provider. Compiled provider output always records `execution=not-submitted`. Existing ComfyUI execution infrastructure remains downstream.

## Preconditions

Provider compilation is blocked unless:

- `universal_description_complete=true`
- `cross_authority_consistent=true`
- the approved Universal Production Description contains no unresolved consistency findings

## Production Planning UI

The existing Production Planning workspace adds:

- `Provider` status column
- `Provider Output` tab
- provider selector
- compiled provider contract preview
- review notes
- Compile Provider Draft
- Refresh from Universal
- Mark Ready & Compile
- Return to Draft

The initial selector contains `ComfyUI`; the registry is designed for future image, video, audio and other production providers.

## Output

Ready compilation creates a new immutable Production Package revision under:

`provider_outputs[provider_id]`

and sets a provider-specific validation marker, for example:

`provider_comfyui_complete=true`

## Non-goals

- no workflow execution
- no automatic user approval
- no provider retry/queue management
- no hard-coded provider model selection
- no rewriting of Universal production authority

These remain downstream responsibilities.
