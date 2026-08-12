# Phase 19.4.7 — Style Compiler

## Purpose

The Style Compiler creates canonical provider-neutral Style authority for each governed Shot without inventing a new aesthetic. It assembles style-relevant production decisions that already exist in approved Shot, Asset, Camera, Lighting, Environment and Continuity authority.

## Governance

- Final approval remains with the user.
- The normal lifecycle is Draft → Ready & Compile → Return to Draft.
- Ready Style authority is immutable until returned to Draft.
- If upstream governed production authority changes, the Style Draft becomes stale and must be refreshed.
- Refresh preserves human production-review notes.
- Missing declared style or tone is left empty; the compiler does not manufacture creative intent.
- Provider, model and ComfyUI workflow syntax remain downstream concerns.

## Compiled authority

The compiler records declared style and tone when supplied upstream, camera language, lighting language, continuity language, environment context, canonical asset identities and canonical references. Compiling appends a new immutable Production Package revision and sets `style_complete=true`.

## Automation principle

Style is assembled automatically from governed production state. Human interaction is primarily approval and exception review, consistent with the VSCS principle of automation by default and final user authority.
