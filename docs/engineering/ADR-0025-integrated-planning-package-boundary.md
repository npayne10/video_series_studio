# ADR-0025 — Integrated Planning Package Boundary

**Status:** Accepted for Phase 19.3.9 implementation  
**Date:** 2026-08-11

## Context

Phases 19.3.1–19.3.8 establish independent governed authorities for Episode, Scene, Shot, Asset Resolution, Camera, Lighting, Environment and final human Planning Review. Phase 19.4 Prompt Compilation needs one deterministic input and must not independently query multiple mutable planners during compilation.

## Decision

Phase 19.3.9 materializes each current Approved Planning Review into an immutable, renderer-neutral Integrated Planning Package.

The package contains canonical snapshots of:

- the governed Shot Plan;
- governed Shot-to-Asset bindings and their resolved Asset/CAP/canonical-reference/behaviour context;
- the governed Camera Plan;
- the governed Lighting Plan;
- the governed Environment Plan; and
- Planning Review identity, notes and fingerprint provenance.

The package is canonical JSON with a deterministic SHA-256 fingerprint and deterministic package identity. Re-integrating identical approved planning is idempotent. A later approved planning revision creates a new package while preserving the historical package.

A package is current only while its originating Planning Review remains Approved, production-ready and fingerprint-equivalent to the current governed planning authorities.

## Explicit exclusions

Integration does not author or reinterpret planning. It does not compile prompts, select renderers, generate ACPP packages, create render jobs, schedule production, or perform post-render QA.

## Consequences

Phase 19.4 receives one stable source of production truth per Shot through `require_current_package()`. Compilation no longer needs to reconstruct mutable planning context independently, improving continuity, automation, reproducibility and auditability.
