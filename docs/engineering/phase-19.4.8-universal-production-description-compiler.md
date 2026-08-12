# Phase 19.4.8 — Universal Production Description Compiler

## Purpose

The Universal Production Description Compiler assembles the approved Shot production authorities into one canonical provider-neutral description. It is the final renderer-neutral semantic production description before provider-specific output compilation.

## Authority model

The compiler consumes only current Production Package authority. It does not invent missing creative intent and it does not contain provider/model/workflow syntax.

Final approval remains with the user. A Draft may be assembled early for inspection, but Ready & Compile is blocked until Action & Performance, Assets, Camera, Lighting, Continuity and Style are all complete.

## Inputs

- Story and Shot context
- Action & Performance authority
- Asset authority and canonical references
- Camera authority
- Lighting authority
- Environment context
- Continuity authority
- Style authority
- Governed dialogue and effects when present

## Output

The compiler writes `universal_description` as a new immutable Production Package revision and marks `universal_description_complete=true`. The output includes a structured governed representation and a deterministic `universal_text` projection for downstream provider compilation.

## Governance

- Draft → Ready lifecycle
- Ready immutability until Return to Draft
- Dependency fingerprint staleness detection
- Refresh from current Production Package while preserving human review notes
- No provider output generation in this phase
- No automatic final approval
