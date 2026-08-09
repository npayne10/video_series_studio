# ADR-0000 — VSCS Architecture Principles

**Status:** Accepted  
**Decision scope:** Core architecture  
**Introduced:** Phase 19 formal ADR practice

## Context

VSCS is intended to remain a professional production platform rather than a collection of model-specific AI workflows. Its subsystems must therefore survive changes in AI providers, rendering engines, UI technology, and production scale.

## Decision

VSCS adopts the following enduring architecture principles:

1. **Structured production intent precedes generated language.** Machine-consumable production knowledge is authoritative; prompts and prose are compiled views of that knowledge.
2. **Canonical data has one owner.** XPD, CAP, Reference Library, Readiness, and Production Projection each own distinct contracts; presentation code does not duplicate their rules.
3. **AI proposes; governed workflows approve.** AI output does not silently become canon or production authority.
4. **Production consumers use stable application contracts.** Downstream systems consume services such as Production Projection rather than persistence or UI models.
5. **Providers are replaceable.** Image, video, audio, LLM, and workflow providers remain behind provider-neutral contracts.
6. **Lineage and provenance are preserved.** Canonical and generated assets must be traceable to their source and lifecycle decisions.
7. **Readiness is deterministic.** Production gates are based on persisted canonical state, not AI judgement or presentation heuristics.
8. **Backward compatibility is preferred during architectural evolution.** Schema migrations must preserve existing project data unless an explicit, reviewed migration states otherwise.
9. **Each phase is testable and reviewable.** New functionality includes focused unit/integration acceptance before the phase is closed.

## Consequences

- More production data is represented explicitly rather than embedded only in prose.
- Model-specific prompts become outputs rather than primary project data.
- UI layers remain relatively thin.
- Some assets may remain blocked until required structured knowledge is genuinely persisted; VSCS will not infer it silently merely to pass readiness.

## Alternatives considered

### Provider-driven architecture
Rejected because model/provider changes would propagate into canonical project data and application workflows.

### Free-form prose as the canonical production representation
Rejected because downstream planning, validation, prompt compilation, and QA would repeatedly need to reinterpret natural language.

## Future notes

A later ADR may supersede an individual principle when a concrete production requirement justifies it, but the change must be explicit and preserve migration/compatibility requirements.
