# ADR 0071 — Phase 20.15.1b Prompt Distillation & Workflow Input Normalization

## Status

Accepted for implementation; local and UI acceptance pending.

## Context

The governed Production Package contains rich structured authority for Shot intent, Assets, Action & Performance, Camera, Lighting, Environment, Continuity, Style, dialogue and canonical references. Earlier executable compilation concatenated large serialized authority blocks into the model-facing positive prompt. That preserved information but weakened the semantic quality of text conditioning and coupled prompt quality to JSON serialization.

The committed ComfyUI v7.1.4 graph already consumes stable loader outputs for positive prompt, negative prompt, continuity frame, filename prefix, width, height, frame count, seed, FPS, CFG, IC-LoRA strength and composition plan. Replacing that proven loader without an in-repository node implementation would create unnecessary provider coupling.

## Decision

VSCS separates governed structured authority from provider-facing text conditioning.

1. The Production Package remains the source of truth.
2. `ProductionPromptDistillationService` deterministically converts governed authority into concise cinematic natural language.
3. Raw serialized `SHOT`, `ASSETS`, `CAMERA`, `LIGHTING`, `ENVIRONMENT`, `CONTINUITY`, `STYLE` and similar JSON blocks are not inserted into model-facing positive or negative text conditioning.
4. Provider-ready packages expose a canonical `workflow_inputs` contract containing distilled prompts plus atomic execution inputs such as seed, FPS, frame count, dimensions, filename prefix, reference plan and continuity image path.
5. Existing v7.1.4 top-level loader fields remain compatibility projections so the committed ComfyUI graph can consume the normalized package without a speculative custom-node replacement.
6. Structured composition/reference plans remain available to composition nodes separately from natural-language text prompts.
7. Human-approved production authority is never changed by prompt distillation; distillation is an execution compilation step.

## Consequences

- Text encoders receive concise cinematic language instead of JSON-heavy metadata.
- Workflow control data remains typed and independently traceable.
- Provider adapters can evolve without changing the governed Production Package schema.
- Existing v7.1.4 workflow wiring remains backward compatible.
- Future loader versions should consume `workflow_inputs` directly and may retire legacy top-level projections only through an explicit compatibility phase.

## Acceptance Gates

Local acceptance requires Ruff, focused unit tests, static typing and regression tests. UI acceptance requires compiling a real provider-ready Production Package and proving that `prompts.positive` / `workflow_inputs.compiled_positive_prompt` contain no raw authority JSON while preserving approved shot, identity, camera, lighting, environment, continuity, dialogue and timing intent. A Preview ComfyUI submission must then prove the committed workflow consumes the distilled prompt and normalized execution values without hard-coded fallbacks.
