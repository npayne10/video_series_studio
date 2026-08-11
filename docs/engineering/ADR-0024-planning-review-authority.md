# ADR-0024 — Planning Review Authority

**Status:** Accepted for Phase 19.3.8 implementation  
**Date:** 2026-08-11

## Context

Phase 19.3 now produces governed Shot, Asset, Camera, Lighting and Environment contracts. Before Phase 19.3.9 integrates planning into downstream production, VSCS needs one explicit human gate that proves those independent authorities are simultaneously Ready and current.

## Decision

Planning Review is a downstream governance boundary, not another planner.

For each governed Shot it:

- reads the authoritative Shot, Asset, Camera, Lighting and Environment contracts;
- reports a deterministic PASS/BLOCKED check for each planning area;
- records reviewer notes and explicit human approval;
- fingerprints the complete reviewed planning package;
- treats an approved review as stale whenever any reviewed authority changes; and
- exposes production readiness only when approval, current fingerprints and every upstream readiness rule all agree.

Planning Review MUST NOT edit, reinterpret or duplicate upstream planning authority. It MUST NOT compile prompts, select renderer implementation, create ACPP packages or perform render-time quality control.

## Consequences

Phase 19.3 gains a single auditable completion gate per Shot. Downstream Phase 19.3.9 integration can consume one `is_production_ready()` decision without weakening the ownership boundaries established in Phases 19.3.3–19.3.7. Any upstream change invalidates approval deterministically rather than silently allowing stale production planning to proceed.
