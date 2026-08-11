# ADR-0027 — Action & Performance as Temporal Production Authority

**Status:** Accepted for Phase 19.4.2 implementation  
**Date:** 2026-08-11

## Context

The most important part of a video-generation instruction is often the actual temporal story of the Shot: who acts, what happens in what order, what is spoken, how characters perform and react, and what state the Shot reaches at its end. Phase 19.3 governs Shot intent but deliberately keeps the Shot contract lean. Phase 19.4 must expand that approved intent into production intelligence before provider-specific prompt translation.

## Decision

VSCS SHALL maintain a provider-neutral Action & Performance authority per current Production Package.

A new draft is seeded only from already-governed Shot fields: required action, dialogue requirement, continuity-in, continuity-out and runtime. VSCS SHALL NOT invent additional story beats during deterministic seeding.

The human operator may refine the temporal narrative, spoken content, performance direction, opening state, closing state and timing notes. A reviewed Ready Action & Performance record SHALL compile into the canonical `ProductionPackage.action_performance` section.

The compiled section SHALL remain independent of LTX, Veo, Qwen, WAN, Flux, ComfyUI or any other provider syntax. Provider prompts are later translations of this authority.

A change to the underlying Phase 19.3 planning source invalidates Action & Performance currency and requires review against the new Production Package.

## UI decision

The existing left-side `Production Planning` navigation workspace becomes the Phase 19.4 home. Phase 19.4.2 replaces its placeholder with the first Production Package workspace and Action & Performance editor. Later 19.4 compilers extend this same workspace rather than creating competing top-level environments.

## Consequences

The actual Shot story becomes explicit and inspectable before prompt compilation. Production intent remains stable across AI providers, while operator review prevents deterministic compilation from silently inventing narrative content.
