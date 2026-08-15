# ADR-0033 — Continuity-Aware Automation

## Status
Accepted for Phase 19.5.9 implementation.

## Decision
Phase 19.5.9 resolves continuity deterministically from the current proposal chain rather than invoking AI. It reuses the Phase 19.4.6 continuity semantics for previous-Shot closing-state inheritance, preservation directives, screen direction, lighting continuity, environment state and explicit conflict reporting.

Continuity automation consumes current Shot, Action/Performance, Environment, Camera and Lighting proposals. It produces `CONTINUITY` `AutomationProposal` records only. It never creates a `ContinuityCompilationDraft`, marks continuity Ready, compiles a Production Package, or approves production.

Detected conflicts are preserved as review findings. Automation must not silently choose a winner when the current opening state disagrees with the previous closing state or when screen direction reverses. Human review remains the authority boundary.

This phase intentionally does not add an AI provider. Cross-Shot state inheritance is deterministic production logic; using AI would add variation without adding trustworthy authority.
