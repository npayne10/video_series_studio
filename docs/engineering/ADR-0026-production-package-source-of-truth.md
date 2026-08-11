# ADR-0026 — Production Package as Canonical Production Intent

**Status:** Accepted for Phase 19.4.1 implementation  
**Date:** 2026-08-11

## Context

Phase 19.3 ends with an immutable Integrated Planning Package representing approved creative planning. Phase 19.4 must turn that planning into the intelligence that actually describes what the production system must create. Provider prompts are important outputs, but AI providers and their preferred prompt syntax are replaceable.

## Decision

VSCS SHALL own a versioned, renderer-neutral `ProductionPackage` as the canonical representation of production intent for a governed Shot.

The package SHALL preserve provenance to the exact Integrated Planning Package and Planning Review from which it was derived. It SHALL contain normalized sections for story context, Shot, assets, camera, lighting, environment, action/performance, continuity, style, dialogue, effects, references, universal production description, provider outputs and validation.

Phase 19.4.1 establishes the contract and copies only already-governed planning authority into the appropriate foundation sections. It SHALL NOT invent action, dialogue, continuity, style, effects or provider prompt text. Those sections remain explicitly empty until their owning Phase 19.4 specialist compiler is implemented.

Provider-specific prompt text SHALL be treated as a compiled derivative of the Production Package, never as VSCS production authority.

## Consequences

A future provider can be added without rewriting story or production intent. The same canonical Shot can be translated for LTX, Qwen, Flux, WAN, Veo or future systems while retaining identical governed intent. Staleness is determined from the immutable Phase 19.3 integration fingerprint, and historical Production Packages remain available for traceability.
