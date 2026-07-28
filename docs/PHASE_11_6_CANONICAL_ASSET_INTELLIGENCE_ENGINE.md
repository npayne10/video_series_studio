# Phase 11.6 — Canonical Asset Intelligence Engine (CAIE)

## Purpose

CAIE is the semantic layer between Canonical Asset Profiles and XCIC Core. It converts CAP facts into model-ready positive and negative prompts while preserving category meaning, production style and canonical constraints.

## Rendering path

```text
CAP + registered Asset category
        ↓
CAIE v1.0
  - source cleaning
  - category knowledge
  - semantic disambiguation
  - style profile
  - targeted negative prompt
  - prompt validation
        ↓
XCIC Core Rendering Library v1.0
        ↓
ComfyUI
        ↓
Canonical Candidate reference
```

## Initial category intelligence

CAIE v1.0 includes explicit rules for ships, vehicles, characters, locations, environments, planets, props, technology, uniforms and effects. Unsupported or non-visual categories use a safe generic production-reference rule.

The ship rule explicitly establishes an asset as an orbital spacecraft operating in vacuum and excludes maritime interpretations such as harbour tugboats, oceans, masts, rigging, anchors and tyre fenders.

## Metadata protection

CAP headings and metadata-style lines are removed before prompt compilation. All generated prompts explicitly prohibit captions, labels, title cards, specification panels, UI overlays, logos, watermarks and readable writing.

## Prompt provenance

Generation manifests now record:

- asset category;
- CAIE version;
- style profile;
- target model;
- prompt warnings;
- final positive prompt;
- final negative prompt;
- XCIC/ComfyUI generation settings.

## Validation

Before rendering, CAIE verifies that category-defining semantic anchors are present. A ship prompt, for example, must contain spacecraft, vacuum and orbital anchors. Rendering stops with a clear error when the category cannot be represented safely.

## Current scope

CAIE v1.0 is deterministic and provider-neutral. Later versions can add configurable series style profiles, model-specific optimization, prompt preview/diff tools, user-authored category templates and automatic image evaluation feedback.
