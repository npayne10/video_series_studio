# Phase 20.18.2.3.6.6b.2 — Production Planning Snapshot Performance Hardening

## Objective

Remove multi-second UI stalls caused by repeatedly traversing the same governed
planning authority during one Production Planning refresh, without weakening any
currentness, readiness, fingerprint, or human-governance checks.

## Observed baseline

The live Xorix project showed that almost all Production Planning refresh latency
was inside `ProductionPlanningSnapshot.capture()`:

- project-open snapshot: approximately 6.558 seconds;
- later snapshot with SHT-003 participating: approximately 9.379 seconds;
- corresponding complete refreshes: approximately 6.596 and 9.416 seconds;
- individual compiler-state and selected-editor loads were generally measured in
  milliseconds.

This demonstrated that the bottleneck was repeated authority traversal rather
than Qt table population or the specialist compiler editors.

## Root cause

A single refresh previously called `GovernedPlanningIntegrationService.current_package()`
for every integrated Shot. That method correctly revalidates governed authority,
but each Shot-level validation recursively revisited the same persisted state:

- Planning Reviews;
- Shot Plans;
- Scene / Episode authority;
- Asset bindings;
- canonical Asset/CAP/reference resolution;
- Camera Plans;
- Lighting Plans;
- Environment Plans;
- inference/readiness checks.

Camera, Lighting and Environment currentness also recursively call lower-level
readiness functions, causing identical Shot and Asset checks to be repeated many
times during the same synchronous refresh.

The behavior was safe but unnecessarily expensive.

## Hardening strategy

`ProductionPlanningSnapshot.capture()` now opens a refresh-local governed
authority read cache.

The cache:

1. lives only for the duration of one synchronous Production Planning snapshot;
2. loads JSON-backed authoritative collections once and serves subsequent
   filtered reads from that immutable-in-practice copy;
3. memoizes deterministic readiness/currentness calls within the refresh;
4. memoizes canonical asset resolution by asset identity/category so the same
   CAP/reference authority shared across multiple Shots is not repeatedly
   resolved;
5. memoizes Shot asset inference/readiness for repeated downstream dependency
   checks;
6. restores every original service method when snapshot capture exits.

The cache is discarded after each refresh. A later refresh therefore re-reads
current persisted authority and cannot hide changes made by the operator between
actions.

## Governance boundary

This phase is an optimization only.

It does **not**:

- trust persisted Ready flags without revalidation;
- bypass Planning Review;
- bypass Shot / Asset / Camera / Lighting / Environment currentness;
- preserve cache data across user actions;
- alter fingerprints;
- change Production Package materialization semantics;
- mutate accepted production authority.

The same existing governed methods still make all readiness/currentness decisions.
The optimization only prevents an identical read or deterministic calculation
from being repeated within one refresh transaction.

## Expected scaling improvement

Shared canonical assets are common across adjacent Shots. For example, multiple
bridge Shots may use the same characters, location, ship, planet and environment.
Previously each downstream planner could resolve those assets repeatedly for every
Shot. The refresh-local cache reduces those repeated resolutions to one
authoritative result per asset/category for that refresh.

The target for the live Xorix project is:

- substantially below the previous 6–9 second snapshot baseline;
- preferably below 1 second for the current 2–3 integrated-Shot working set;
- no growth pattern that makes normal navigation impractical as more of the
  17-Shot Scene becomes production-ready.

The measured live result governs acceptance; the target is not implemented as a
hard timing assertion because CI and development hardware vary.

## Regression coverage

Performance regression tests verify that, within one snapshot:

- integrated package history is loaded once;
- Planning Review history is loaded once;
- governed Asset bindings are loaded once;
- repeated Review snapshots are memoized by Shot;
- repeated Shot asset readiness is memoized;
- shared canonical asset resolution is executed once per asset/category;
- governed Shot-plan collection reads are reused;
- existing Production Packages are not rematerialized.

A separate regression proves that the cache is **not** reused across successive
refreshes: every new refresh re-enters authoritative persistence and recomputes
currentness.

## Acceptance criteria

Phase 20.18.2.3.6.6b.2 is accepted when:

1. Ruff lint and formatting pass.
2. mypy passes.
3. focused Production Planning performance tests pass.
4. the full repository regression passes.
5. the working tree is clean.
6. the live `D:\VSCS TSR2` project opens without governance or startup regressions.
7. PPROF shows a substantial reduction in `snapshot.capture` and total refresh
   time relative to the 6.558–9.379 second baseline.
8. SHT-001 and SHT-002 remain accepted and unchanged.
9. SHT-003 remains current and can continue through downstream planning normally.

## Acceptance evidence

Validation completed on 2026-10-11:

- Ruff lint passed.
- Ruff formatting check passed across 1313 files.
- mypy passed across 594 source files.
- Focused Production Planning / Planning Integration / Planning Review /
  Production Package validation passed: 26 tests.
- Full repository regression passed: 1885 tests in 25.34 seconds.
- The live `D:\VSCS TSR2` project opened successfully with no startup or
  governance exception.
- Live PPROF after hardening measured `snapshot.capture = 0.149 s` and
  `REFRESH TOTAL = 0.186 s` with SHT-001, SHT-002 and SHT-003 participating.
- Compared with the observed 9.379 s / 9.416 s later-refresh baseline, this is an
  approximately 98% reduction in both snapshot and total-refresh latency.
- Individual compiler-state and selected-editor loads remained in the
  millisecond range.

Repository cleanliness was verified after the full regression:

- `git diff --check` returned no output.
- `git status --short` returned no output.

## Phase state

**Phase 20.18.2.3.6.6b.2 — COMPLETE / ACCEPTED.**
