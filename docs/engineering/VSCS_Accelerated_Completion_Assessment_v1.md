# VSCS Accelerated Completion Assessment — Version 1.0

**Date:** 2026-11-25 (Africa/Johannesburg)  
**Status:** Proposed delivery-control baseline; Neill approved the accelerated *workflow*, not these estimates or any new GPU/video/API expenditure.  
**Repository:** [npayne10/video_series_studio](https://github.com/npayne10/video_series_studio)  
**Reference branch:** `issue-61-governed-master-workflow`, PR [#66](https://github.com/npayne10/video_series_studio/pull/66)  
**Prepared for:** Neill Payne — VSCS/Xorix

## 1. Executive decision

Switch from one approval per implementation substage to **one approved functional capability, continuous GitHub CI, and one integrated Windows/operator acceptance**. Minor code/test failures inside an approved capability are fixed without separate handoffs. Keep separate explicit consent for GPU, paid API, protected project mutation and PR merging.

**Primary delivery objective:** an approved Story and CAPs lead through a governed render, QC, audio/assembly as needed, and an exported playable video from VSCS. An end-to-end exported output—not another offline preflight—is the outcome.

### Two distinct first-delivery milestones

1. **MVP-A: first governed 18-second Blue Signal production proof**, with actual video output and basic export: provisional **3–6 elapsed weeks** after start, subject to currently unverified render/export capabilities.
2. **MVP-B: complete pilot episode**, with its real shot count, audio, continuity, accepted media and export: provisional **8–16 elapsed weeks**. The full 69-shot E01/Xorix scope cannot be assumed equivalent to an 18-second proof.
3. **Repeatable initial release:** provisional **12–24 weeks**, depending chiefly on GPU throughput, sequence continuity, audio and recovery. These are *planning ranges, not commitments*, and should be re-estimated after the first real governed clip.

The prior 5–9-week pilot estimate should be treated as optimistic until runtime video/export integration is demonstrated.

## 2. Verified inventory versus interpretation

GitHub search on 2026-11-25 found **9 open Issues**: #52, #53, #54, #55, #58, #59, #60, #61, #67. #56 and #57 are closed.

It also found **48 open Draft PRs**: #3–#49 and #66. A full GitHub commit-ancestry comparison of all 47 historical PR heads against the current #66 branch found:

- **46 of 47 older PR heads are ancestors** of the current #66 branch. Their commits already exist in the current development lineage. They are **not 46 missing features**.
- **PR #14 is the exception**, diverging by **2 commits**. Its three changed paths include `src/vscs/application/caps/architecture_assessment.py`, its package export, and a test. Investigate whether those two commits contain any missing behavior before closing/merging.
- **PR #66 is the current active Draft.** The 47 older PRs should be reconciled administratively, with explicit approval before closing or merging; Git ancestry does not itself establish functional acceptance or release inclusion.

Evidence: GitHub `compare_commits` for each historical PR head and `issue-61-governed-master-workflow`. Ancestor status means branch content is included, *not* that those branches were merged to `main`, that code is production-approved, or that every UI feature works.

### Source-level capability observations

| Evidence | What it establishes | What it does **not** establish |
|---|---|---|
| `src/vscs/application/production_pipeline/queue.py` and `queue_models.py` | Dependency-aware job states, scheduling and attempts exist in source | Successful provider execution and clip acceptance |
| `src/vscs/application/rendering/outputs.py` | Renderer output/provenance contracts exist | A fully reconciled/generated MP4 |
| `src/vscs/application/rendering/lip_sync.py` | Lip-sync request/validation contracts exist | Working voice synthesis and synchronised exported audio |
| `src/vscs/application/caps/multiple_angle_execution_guard.py` | Governed offline queue reservation and audit/cancellation logic; #61 B.2F validated | Live multi-angle CameraAngle execution and output QC |
| `docs/engineering/VSCS_Production_MVP_Roadmap.md` | Approved production-first vision and end-to-end intent | Current code-level implementation status; older status tables are stale |
| `docs/engineering/Revised_Production_MVP_Implementation_v2.md` | End-to-end stage architecture (rendering, audio, QC, timeline, export) | Stage completion; this older roadmap marks many phases planned |

**Unproven critical capabilities:** one real governed clip from a Ready shot; reliable GPU output acceptance; media QC; automated or operator-guided sequence assembly; audio path; final playable export. These require code-path inspection and actual local execution evidence, not inference from model/data contracts.

## 3. Open Issue disposition and effort estimates

Effort = *engineering working days* including tests/docs and a small operator handoff, excluding long GPU rendering or approval delays. Each range is conditional until the code-level acceptance audit.

| Issue | MVP classification | Proposed disposition | Remaining effort |
|---|---|---|---:|
| [#61](https://github.com/npayne10/video_series_studio/issues/61) | **P0** | Finish one integrated MASTER→four derived views→QC→approved CAP reference path; current B.2F offline guards are accepted, live provider transport/qualification remain | 5–10 d |
| [#54](https://github.com/npayne10/video_series_studio/issues/54) | **P0** | Source-grounded CAP field completion, provenance, deferred dimensions, fewer manual edits | 3–6 d |
| [#58](https://github.com/npayne10/video_series_studio/issues/58) | **P0 conditional** | Verify whether correlated-field correction is already delivered; complete only remaining truthfulness/ROI blocker | 1–4 d |
| [#55](https://github.com/npayne10/video_series_studio/issues/55) | **P0 umbrella** | Convert historic no-video qualification plan into shot-scoped blockers and integrated Windows UAT; avoid double-counting its child issues | 3–6 d incremental |
| [#53](https://github.com/npayne10/video_series_studio/issues/53) | **P0 if correction required** | Verify disposable Qwen visual-correction readiness for a genuinely blocking defect; avoid protected Attempt 2/2 | 2–5 d |
| [#59](https://github.com/npayne10/video_series_studio/issues/59) | P1 | Reopen cached technical-only candidate review; no paid calls | 1–2 d |
| [#60](https://github.com/npayne10/video_series_studio/issues/60) | P1 | Fix CAP focus, feedback, asset-specific copy; batch with review UI work | 2–3 d |
| [#67](https://github.com/npayne10/video_series_studio/issues/67) | P2 unless manual bridge blocks throughput | In-app paid OpenAI MASTER generation; current manual import can support pilot | 6–10 d |
| [#52](https://github.com/npayne10/video_series_studio/issues/52) | P2 | H3 multi-frame experimental enhancement; defer if existing governed video path works | 4–8 d |

These issue estimates are **not additive** to the capability work packages below: #55 overlaps #54/#58/#61/#53. No automatic issue closure follows this assessment.

## 4. Delivery work packages, order and dependency

| Package | Outcome and acceptance evidence | Predecessor | Effort |
|---|---|---|---:|
| **W0 — Architecture/release reconciliation** | Confirm actual active branch ancestry, PR #14 exception, render/export integration points, working acceptance project and launch command | None | **1–2 d** |
| **W1 — Governed visual reference completion** | #61 end-to-end: single approved MASTER, qualified cardinal view execution, independent QC, no overwrite, persisted references | W0 | **5–10 d** |
| **W2 — Shot-scoped asset/CAP readiness** | #54/#58/#55 blockers resolved for *visible assets in the 18-second test shot*, without fictional camera robot/offscreen ship requirements | W1 in part; overlaps | **5–10 d** |
| **W3 — First actual governed clip** | Real 18-second or bounded shorter clip, explicit one-use GPU consent, provider prompt/job ID, accepted output/recovery and QC | W1/W2 | **6–12 d** |
| **W4 — Media QA and pilot sequence** | Repeatable clip acceptance, continuity, multi-shot sequencing, reviewable rejected versions | W3 | **4–8 d** |
| **W5 — Audio and export integration** | Dialogue/voice as required, audio levels, lip-sync where applicable, final playable file, source-to-export provenance | W3/W4; parallelisable | **7–14 d** |
| **W6 — Pilot hardening and operator UAT** | Reopen/restart, failure recovery, representative project export, docs and first-run guidance | W3–W5 | **5–10 d** |
| **W7 — Repeatable production automation** | Batch/queue resilience, reduced CAP manual review, schedule monitoring, downstream reliability | After first export | **8–15 d** |

**Critical-path uncertainty:** W3 and W5. Source contracts exist, but live provider + actual media/export wiring is not yet verified. The ranges are provisional. The first GPU trial may uncover a model/VRAM or workflow incompatibility and must be separately consented.

## 5. Milestones and provisional schedule

| Milestone | Acceptance (not merely source code) | Indicative timing after kickoff |
|---|---|---|
| M0 | W0 evidence inventory and frozen 18-second test contract | **Week 1** |
| M1 | CAP-PRP-002 MASTER/required derived views and shot CAP gates qualified | **Weeks 2–3** |
| M2 | First real governed clip generated, saved, reopened and human-QC'd | **Weeks 3–5** |
| M3 | First 18-second proof assembled/exported with required audio | **Weeks 3–6** |
| M4 | Complete pilot episode's actual shot list and accepted continuity | **Weeks 6–12** |
| M5 | Full pilot exported and reviewed | **Weeks 8–16** |
| M6 | Repeatable initial release with recoverability and operator guide | **Weeks 12–24** |

These are **elapsed calendar-week planning bands**, assuming one primary AI-assisted development stream and timely Windows/GPU/operator windows. There is no promised completion date; weekends, holidays, GPU time and user availability are not yet modelled. Do not multiply 69 shots by nominal 18 seconds and claim that is an achievable render schedule until actual throughput/continuity are measured.

## 6. Definition of done for the accelerated workflow

1. **Capability consent**: Neill approves a complete functional scope, not each internal implementation substep.
2. **GitHub-first**: implement on the existing approved PR/branch; pinned fast Ruff lint/format, mypy and full regression run automatically.
3. **One Windows acceptance** per capability: explicit small operator script/UI scenario focused on things CI cannot prove, then recorded result.
4. **Evidence economy**: reuse established, unchanged hashes/audits where valid; automate any newly required protection snapshot. No repetitive manual reports without a real authority boundary.
5. **No automatic authority**: MASTER/CAP/references/production approval stays human-governed, never inferred from an AI score or test pass.
6. **Separate dangerous consent**: paid API calls, actual GPU/video generation, destructive changes, protected historical files, PR merge and release require explicit scoped approval.
7. **Working demonstration**: acceptance requires a durable user-visible production artifact and quality review, not only an offline blueprint.
8. **Review cadence**: one weekly backlog/schedule update and a capability-level blocker decision; avoid new named substages for routine refactors.

## 7. Immediate 1-week execution plan

- **Day 1:** W0 code-path and branch inventory; verify #14's two divergent commits; identify existing render worker, GeneratedMedia registration, QA, timeline and export entry points. Produce exact missing integration links.
- **Day 2:** Freeze the bounded 18-second Blue Signal scenario and required visible CAPs; agree on first real clip/provider and one-use GPU consent protocol (consent requested at execution time).
- **Days 3–5:** Implement W1 as one integrated provider+review capability on PR #66, continuously test in GitHub, then one Windows acceptance campaign. Do not merge or generate until respective consent gates.

W1 duration may extend beyond the first week; do not bypass required identity/QC checks to meet a calendar target.

## 8. Deferred and conditional work

- #67 in-app paid OpenAI MASTER creation: postpone if manual approved MASTER import remains usable for the pilot.
- #52 H3 multi-frame experimental workflow: postpone until base governed video generation/continuity has been shown.
- #59/#60 usability defects: batch when touching the CAP/review UI; fast fixes can be pulled forward if they obstruct operator acceptance.
- #53 masked correction: execute only if a real blocking visual defect cannot be resolved safely through the qualified reference route.
- Additional providers, advanced camera/style, full automation, marketing/publishing integration: defer beyond first exported proof unless independently demonstrated as blockers.

## 9. Risks, decisions and next re-estimate

| Risk / unknown | Impact | Mitigation and decision |
|---|---|---|
| RTX 5060 Ti 16 GiB model/offload performance and multi-angle accuracy | High | Bounded first GPU trial, capture VRAM/time/output; separate explicit authorisation |
| Real render-to-GeneratedMedia and export integrations | High | W0 code-path audit, first real clip as early as possible |
| Multiple mandatory CAPs overblocking a visually scoped shot | High | Complete #54/#55 shot-scoped truthfulness; no invented camera robot |
| Source identity drift in derived/reference or video generation | High | Strict MASTER/image QC and human approvals; never weaken |
| 47 historical Draft PRs confusing release status | Medium | 46 ancestors, #14 exception; reconcile administratively, do not mass merge |
| GPU time, holidays, operator availability | Medium/High | Track actual cycle times and weekly burndown; reforecast after M2/M3 |
| Scope creep from optional #52/#67 and polish | High | Defer until first exported proof, unless demonstrable blocker |

**Version 1.0 acceptance sought from Neill:** (a) 18-second proof before full pilot episode, (b) W0→W1→W3 critical path with W2 in parallel, (c) single integrated UAT per capability, (d) conditional/deferred backlog dispositions. This document does **not** authorise real GPU generation, paid calls, protected project writes, PR merges, or issue closure.
