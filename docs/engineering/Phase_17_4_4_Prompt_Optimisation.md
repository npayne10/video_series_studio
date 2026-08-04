# Phase 17.4.4 — Prompt Optimisation

## Objective

Phase 17.4.4 adds a deterministic, renderer-profile-aware optimisation layer after renderer-neutral prompt compilation. It reduces avoidable prompt noise without changing the Prompt Graph, canonical production knowledge, continuity state, provenance or validation outcome.

## Pipeline

```text
Prompt Graph
→ Prompt Graph Compiler
→ Renderer-neutral PromptPackage
→ Prompt Optimisation Service
→ Renderer-profiled OptimizedPromptPackage
```

## Public contracts

The phase introduces:

- `PromptOptimizationPolicy`
- `PromptOptimizationDiagnostic`
- `PromptOptimizationSeverity`
- `PromptOptimizationReport`
- `OptimizedPromptPackage`
- `PromptOptimizationService`

## Safe optimisation rules

The optimiser may:

- normalise repeated whitespace;
- remove exact duplicate fragments;
- omit optional fragments when a renderer character budget requires it;
- report all removals and omissions;
- measure before-and-after prompt size.

The optimiser must not silently remove authoritative production information.

Protected content includes:

- every mandatory fragment;
- visual intent;
- characters;
- camera;
- lighting;
- continuity;
- dialogue;
- restrictions;
- negative constraints.

Canonical assets, approved references and graph provenance remain attached to the original source package.

## Renderer limits

Optional fragments are removed from the lowest-priority end of the compiled package until the selected renderer profile fits its configured limits.

If protected content alone exceeds a profile limit, the optimiser:

1. preserves the complete protected content;
2. returns the selected profile identity unchanged;
3. marks the result as outside the profile limit;
4. records `optimization.protected_content_exceeds_limit`.

It does not silently truncate essential CAP, continuity, dialogue, camera, lighting or restriction details.

## Diagnostics and metrics

Every optimisation report includes:

- original and final positive-prompt lengths;
- original and final negative-prompt lengths;
- characters saved;
- duplicate fragments removed;
- optional fragments omitted;
- protected fragments preserved;
- renderer-limit compatibility;
- structured diagnostics.

## Bootstrap

`PromptOptimizationService` is registered in the application dependency graph and shares the bootstrapped `RendererPromptCompiler`.

## Tests

The phase adds coverage for:

- whitespace normalisation;
- exact duplicate removal;
- positive and negative prompt separation;
- optional-fragment omission;
- protected-detail preservation;
- renderer-limit incompatibility warnings;
- provenance stability;
- bootstrap service identity;
- graph-to-optimised-prompt integration.

## Deliberate exclusions

This phase does not:

- rewrite canonical descriptions using an AI model;
- infer missing production facts;
- alter Prompt Graph nodes;
- weaken validation rules;
- change ComfyUI workflows;
- add Prompt Preview UI controls;
- submit renders.

## Outcome

VSCS can now produce cleaner renderer prompts while guaranteeing that crucial production details—such as spacecraft identity, dimensions, engine placement, blue-white engine trails, continuity instructions and negative constraints—survive optimisation unchanged.
