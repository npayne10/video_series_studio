# VSCS Version 1.0 Milestone Tracker

## Status legend

- ✅ Complete and approved
- 🧪 Implemented, awaiting local test
- 🚧 In progress
- ⏳ Planned
- ⛔ Blocked

## Current milestone

| Milestone | Status | Acceptance gate |
|---|---|---|
| Phase 20.18.2.3.6 — Automated Introduction Boundary Synthesis & Span Orchestration | 🧪 Implemented, awaiting local test | Ruff, mypy, focused 3.1–3.6 regressions, ComfyUI node deployment, live SHT-002 orchestration, owner approval |

## Milestone register

| ID | Milestone | Status | Commit / PR | Local tests | Approval |
|---|---|---|---|---|---|
| 11.10.1 | CAR Migrator v2 | ✅ Complete | `v0.11.10.1` | Passed | Approved |
| 12.1 | Validator modularisation | ✅ Complete | `b998d01` baseline | Confirmed | Approved |
| 12.1.1-4B2-1A | Prompt Package Discovery | 🧪 Implemented | `05ad266` milestone head | Not run | Pending |
| 20.18.2.3.6 | Automated Introduction Boundary Synthesis & Span Orchestration | 🧪 Implemented | branch `phase-20.18.2.3.6-automated-introduction-span-orchestration` | Not run | Pending |
| 12.1.1-4B2-1B | Prompt Content Validation | ⏳ Planned | — | Not run | Pending |
| 12.1.1-4B2-1C | Template and Metadata Validation | ⏳ Planned | — | Not run | Pending |
| 12.1.1-4B2-1D | Prompt Package Integration | ⏳ Planned | — | Not run | Pending |
| 12.1.2 | Behaviour Test Validation | ⏳ Planned | — | Not run | Pending |
| 12.1.3 | Behaviour Dependency Validation | ⏳ Planned | — | Not run | Pending |
| 12.2 | Repository Health Scoring | ⏳ Planned | — | Not run | Pending |
| 12.3 | Validation Reports | ⏳ Planned | — | Not run | Pending |
| 13 | CAR Repository Builder | ⏳ Planned | — | Not run | Pending |
| 14 | Asset Packaging System | ⏳ Planned | — | Not run | Pending |
| 15 | Asset Dependency Engine | ⏳ Planned | — | Not run | Pending |
| 16 | Repository Management CLI | ⏳ Planned | — | Not run | Pending |
| 17 | VSCS Pipeline Integration | ⏳ Planned | — | Not run | Pending |
| 18 | Production Pipeline | ⏳ Planned | — | Not run | Pending |
| 19 | Plugin Architecture | ⏳ Planned | — | Not run | Pending |
| 20 | Project Manager | ⏳ Planned | — | Not run | Pending |
| 21 | Production Dashboard | ⏳ Planned | — | Not run | Pending |
| 22 | Documentation | ⏳ Planned | — | Not run | Pending |
| 23 | System Testing | ⏳ Planned | — | Not run | Pending |
| 24 | User Acceptance Testing | ⏳ Planned | — | Not run | Pending |
| 25 | Release Candidate | ⏳ Planned | — | Not run | Pending |
| 1.0.0 | VSCS Version 1.0 | ⏳ Planned | — | Not run | Pending |

## Current forward backlog — Phase 20 H3 multi-frame provider evaluation

**Recorded 2026-11-17.** This backlog is a Phase 20
provider-capability refinement under the authoritative
[Architecture vNext roadmap](VSCS_ARCHITECTURE_VNEXT_ROADMAP.md).
The **Current milestone** register above is retained as a historical
tracking entry; this new backlog is not a claim that any prior
production phase has been re-approved.

**Finding:** User-supplied
`video_minimax_h3_multiframe_reference_VSCS(1).json`
contains 41 nodes / 53 links and is not production-ready.
See [full assessment and required fixes](../PHASE_20_H3_MF_MULTIFRAME_REFERENCE_WORKFLOW_ASSESSMENT.md).
Primary GitHub tracking issue:
[#52](https://github.com/npayne10/video_series_studio/issues/52).

| ID | Task | Priority | State | Evidence needed | Owner acceptance |
|---|---|---|---|---|---|
| H3-MF1 | Offline multi-frame workflow qualification: immutable fixture, `<Picture N>` binding correction, frame-zero anchor policy, guide bounds, deterministic seed, editor→API compilation and negative tests | **P1 — NEXT** | ⏳ Planned | GitHub code + Ruff/Mypy/pytest + operator read-only UI evidence; no GPU | Pending |
| H3-MF2 | Separately approved disposable 5-second fixed-seed GPU A/B and RTX 5060 Ti 16 GiB memory benchmark | P1 | ⛔ Blocked on MF1 and explicit GPU consent | Measured VRAM, time, source/guide manifests, outputs | Pending |
| H3-MF3 | Frame-guide similarity, character/scene continuity and H3 audio QC | P1 | ⛔ Blocked on MF2 | Quantitative metrics and human quality review | Pending |
| H3-MF4 | Governed H3 multi-frame provider mode with ProductionTask, exact Shot boundaries, GeneratedMedia QC and recovery | P2 | ⛔ Blocked on MF3 | End-to-end isolated Shot and no duplicate/unauthorized production outputs | Pending |

**Explicit non-goals for H3-MF1:** changing the existing
H3 production default, `POST /prompt`, GPU/model inference,
AI API charges, modification of accepted production images,
CAP/Canon/MASTER promotion, new GeneratedMedia, attempt
reservation, or executing the C4 still-image correction work.

## Milestone completion checklist

A milestone may be marked complete only when all applicable items are checked:

- [x] Scope implemented
- [x] Public interfaces documented
- [x] Unit tests added or updated
- [ ] Focused tests pass locally
- [ ] Full regression suite passes locally
- [ ] No new critical or high-severity defect
- [x] Changelog updated
- [x] Roadmap status updated
- [x] Commit or PR recorded
- [ ] Project-owner approval recorded

## Standard local verification record

Copy this block beneath the relevant milestone when recording results:

```text
Milestone:
Commit tested:
Test date:
Tester:
Environment:
Focused command:
Focused result:
Regression command:
Regression result:
Defects raised:
Decision: Approved / Rework required
```

## Governance rule

No new milestone begins until the current milestone passes its acceptance gate, unless the project owner explicitly approves parallel development.
