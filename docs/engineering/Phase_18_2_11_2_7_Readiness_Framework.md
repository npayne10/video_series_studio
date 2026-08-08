# Phase 18.2.11.2.7 — Readiness Framework

## Purpose

Define one deterministic, typed readiness contract for Canonical Asset Profiles so every later VSCS production subsystem can consume the same decision rather than implementing its own readiness rules.

## Authoritative report

`CAPReadinessService.evaluate(asset_id)` returns a frozen `ReadinessReport` containing four independent assessments:

- Identity
- References
- Generation
- Production

Each assessment publishes a normalized state, a 0–100 score, and typed actionable gaps. The report also publishes weighted overall readiness, blocking gaps, warnings, `generation_ready`, and `production_ready`.

The current overall weighting is:

- Identity: 25%
- References: 30%
- Generation: 20%
- Production: 25%

## Determinism rule

Readiness evaluation is strictly deterministic and uses persisted canonical data. It contains no AI calls, randomness, semantic inference, user prompts, or UI-derived state.

## Identity readiness

Identity checks canonical name, canonical description, and a Locked MASTER. Visual production categories also report Visual Identity coverage. The Locked MASTER remains the authoritative ChatGPT-authored identity reference established by earlier Phase 18.2.11 work.

## Reference readiness

Reference readiness consumes the category template defined by Phase 18.2.11.2.6.

Coverage and readiness intentionally differ:

- Candidate references count as present for generation coverage, preventing duplicate generation.
- Only Approved or Locked references satisfy readiness.
- Rejected and Archived references do not satisfy either active coverage or readiness.
- MASTER must specifically be Locked for production readiness.

Required references contribute 80% of the reference score when recommended views exist; recommended references contribute the remaining 20%. Categories without recommended views score entirely from required references.

## Generation readiness

Generation is Ready only when:

1. CAP status is Approved.
2. Identity Readiness is Ready.
3. Reference Readiness is Ready.

Otherwise Generation is Blocked with explicit reasons.

## Production readiness

Production readiness requires Generation Readiness and applicable canonical production metadata. Production guidance is evaluated as a warning-level completeness item. Categories whose production behavior depends on structured functionality or constraints publish blocking gaps when those structured fields are absent.

The current legacy persisted CAP record does not yet store the full structured `functional_identity` and `constraints` collections introduced by the Canonical Production Contract. The readiness engine therefore does not infer them from prose. For categories where those structures are required, the report correctly remains Blocked until the contract persistence layer exposes them.

This is intentional: readiness must report architecture truth rather than manufacture readiness from unstructured text.

## UI integration

Canonical Profiles receives a `Readiness` action. The report dialog displays overall score, each independent readiness dimension, and all blocking/warning gaps.

Assets receives a sortable `Readiness` percentage column and a readiness filter:

- All
- Ready
- Partial
- Blocked

The UI is a consumer only. It does not calculate readiness.

## Public service API

- `evaluate(asset_id)`
- `evaluate_all()`
- `overall_percentage(asset_id)`
- `blocking_gaps(asset_id)`

## Downstream contract

Future Production Planning, Prompt Compilation, Video Generation, Render Management and Quality Control should consume `ReadinessReport`. Enforcement is intentionally deferred until those subsystems are integrated; this phase defines the authoritative decision contract and exposes it through CAP/Asset management.

## Acceptance boundary

This phase includes readiness domain models, deterministic application evaluation, CAP readiness UI, Asset Manager readiness visibility/filtering, and automated unit/integration coverage.

It does not persist new functional-identity/constraint fields, implement Prompt Compiler override policy, or enforce readiness inside a future Video Engine. Those integrations consume this framework in their own phases.
