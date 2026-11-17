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

## Current active corrective subphase — C4B.2B (supervised GPU controller)

**Date:** 2026-11-17  
**Branch:** `phase-f5.4.2-c4b2b-supervised-disposable-gpu-qualification`  
**State:** 🧪 Implementation candidate — Windows tests and live GPU operator qualification pending  
**Engineering contract:** [C4B.2B supervised one-shot qualification](../F5_4_2_STAGE_C4B2B_SUPERVISED_GPU_QUALIFICATION.md).

| Gate | Work | Status |
|---|---|---|
| C4B.1 | Offline graph and localhost GET-only schema inspection | ✅ Accepted 2026-11-17 |
| C4B.2A | External sealed disposable source/C1/C2 staging, preview, offline GPU inventory and synthetic pixel audit | ✅ Formally accepted 2026-11-17 (54 focused, 2,902 full tests; operator non-mutation) |
| C4B.2B | Exact one-use consent, PID/port isolation, local model hashes, single disposable Qwen GPU prompt and protected-pixel audit | 🧪 Code candidate; **NO GPU TEST OR AUTHORIZATION** |
| C4 production | Governed correction attempt, Candidate quality assurance and registration | ⛔ Not authorized |
| H3-MF1 | Video multi-frame provider evaluation | ⏳ Deferred until image-correction closure |

C4B.2B has a controlled execution route but is **not** yet
accepted. The new test suite uses fake processes and HTTP
responses. No real model load, ComfyUI launch, GPU prompt, paid
evaluation or attempt has been performed by the development step.
Actual hardware testing requires successful Windows regression,
reviewed disposable source/current mask and fresh operator consent.

## C4B.1 current subphase — operator accepted (offline only, 2026-11-17)

**Branch:** `phase-f5.4.2-c4b-isolated-mask-provider-qualification`  
**Status:** ✅ Operator accepted for offline graph and GET-only diagnostics; live GPU C4B.2 remains unauthorized  
**Technical record:** [C4B isolated Qwen contract](../F5_4_2_STAGE_C4B_ISOLATED_MASK_PROVIDER_QUALIFICATION.md).

C4B.1 contains only offline source/mask graph binding, synthetic
negative tests and optional operator-consented GET-only model/node
inventory. **Windows acceptance:** 51 focused passed, 2,890 full
passed with one symlink skip, Ruff and formatting clean (1,704
files), Mypy clean (713 source files). **UI acceptance:** stale-mask
rejection, explicit GET-only Yes/No dialog, No cancellation without
report, inventory of all nine required classes (15.9/14.7 GiB
total/free GPU memory), and operator-attested non-mutation of
Candidate 4 and its governed attempt counter. **No runtime
inference has occurred; C4B as a whole is not qualified.**
Next gate: separately approved disposable C4B.2 live GPU/pixel-fidelity
qualification. Then governed C4 integration, Candidate quality
assessment and end-to-end acceptance as distinct tasks.
H3-MF1 remains deferred.

## Current development priority — finish governed image correction

**Reprioritized 2026-11-17:** Complete the accepted C4A image-correction
workstream before beginning H3-MF1. **C4B is NEXT**, with isolated,
explicitly authorized, disposable masked-Qwen runtime qualification:
source/mask binding, polarity, actual VRAM and latency, and exact
protected-pixel preservation. Candidate 4 and its protected final
Attempt 2/2 must not be used for qualification.

Once C4B is evidenced and approved, design/implement the remaining
C4 production provider integration, separate execution consent,
fail-closed attempt and recovery handling, corrected-Candidate quality
verification/registration and end-to-end image-correction acceptance.
These later work packages are *proposed*, not automatically approved
for execution. H3-MF1 through H3-MF4 stay recorded as deferred work.

## Deferred forward backlog — Phase 20 H3 multi-frame provider evaluation

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
| H3-MF1 | Offline multi-frame workflow qualification: immutable fixture, `<Picture N>` binding correction, frame-zero anchor policy, guide bounds, deterministic seed, editor→API compilation and negative tests | **Deferred until image-correction completion** | ⏳ Planned; not started | GitHub code + Ruff/Mypy/pytest + operator read-only UI evidence; no GPU | Pending |
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
