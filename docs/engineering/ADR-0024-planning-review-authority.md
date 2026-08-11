# ADR-0024 — Planning Review Authority

**Status:** Accepted for Phase 19.3.8 implementation  
**Date:** 2026-08-11

## Context

Phase 19.3 now produces governed Shot, Asset, Camera, Lighting and Environment contracts. Before Phase 19.3.9 integrates planning into downstream production, VSCS needs one explicit human gate that proves those independent authorities are simultaneously Ready and current.

## Decision

Planning Review is a downstream governance boundary for the complete governed Shot plan, not another planner.

For each governed Shot it:

- reads the authoritative Shot, Asset, Camera, Lighting and Environment contracts;
- reports a deterministic PASS/BLOCKED check for each planning area;
- records reviewer notes and explicit human approval;
- fingerprints the complete reviewed planning package;
- treats an approved review as stale whenever any reviewed authority changes; and
- exposes production readiness only when approval, current fingerprints and every upstream readiness rule all agree.

The governed **Shot Planner is the authoritative navigation owner for Planning Review**. The `Planning Review…` action is available whenever a governed Shot is selected, even when specialist planning is incomplete, because the review surface must be able to explain blockers. `Approve Planning` remains disabled until Shot, Asset, Camera, Lighting and Environment authority are all Ready and current.

Environment Planner remains an independent specialist planner and MUST NOT own or gate access to Planning Review.

Planning Review MUST NOT edit, reinterpret or duplicate upstream planning authority. It MUST NOT compile prompts, select renderer implementation, create ACPP packages or perform render-time quality control.

## Consequences

Phase 19.3 gains a single auditable completion gate per Shot, reachable from the same authoritative Shot-level control point as the specialist planners. Downstream Phase 19.3.9 integration can consume one `is_production_ready()` decision without weakening the ownership boundaries established in Phases 19.3.3–19.3.7. Any upstream change invalidates approval deterministically rather than silently allowing stale production planning to proceed.
