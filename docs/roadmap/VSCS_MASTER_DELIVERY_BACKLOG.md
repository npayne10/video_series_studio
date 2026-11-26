# VSCS — Master Delivery Backlog and Decision Register

| Document control | Value |
|---|---|
| ID / version | VSCS-DELIVERY-MASTER / 1.0 |
| As of | 2026-11-26 (Africa/Johannesburg) |
| Owner / decision authority | Neill Payne |
| Status | Active operational delivery baseline |
| Repository | [npayne10/video_series_studio](https://github.com/npayne10/video_series_studio) |
**Active development:** `issue-61-governed-master-workflow` / [Draft PR #66](https://github.com/npayne10/video_series_studio/pull/66)

> **START HERE for every VSCS development session.** This is the single source of truth for **what we do next, priorities, delivery status, dependencies, accepted decisions, and unresolved blockers**. Update this document as part of the same PR/commit when a decision or capability status changes. Do not infer acceptance from a code commit or a passed unit test.

## 1. Governing order and purpose

This operational backlog supersedes previous **day-to-day priorities, W-number sequencing and status snapshots** where they conflict. The adopted [Architecture vNext Roadmap](VSCS_ARCHITECTURE_VNEXT_ROADMAP.md), [Production MVP Roadmap](../engineering/VSCS_Production_MVP_Roadmap.md), approved architecture decisions and individual capability contracts continue to govern **technical invariants, design and acceptance requirements**. A scheduling decision here does not silently approve an architectural change; record such a change in the appropriate ADR/specification too.

**Delivery goal:** a governed Story/Shot and approved CAP references produce a real, quality-reviewed 15–20-second video; accepted shots assemble into scenes/episodes, followed by voice, shot-level lip-sync, audio, mastering and export. Complete a working short proof before attempting all 69 planned E01 shots.

**Working rhythm:** one integrated capability at a time, GitHub-first on the approved branch/PR, automated Ruff lint/format + mypy + regression, and one focused Windows/operator acceptance. Preserve all protected references and historical GeneratedMedia. Actual GPU jobs, paid APIs, protected-data changes, merges and releases require **separate scoped human authorization**. No automatic AI-generated approvals.

## 2. Current delivery position — read first

| Item | Status / decision | Evidence or next condition |
|---|---|---|
| **Current capability** | **W2 — First governed 15–20-second video** | NEXT: inspect current ProductionTask → provider → GeneratedMedia → QC path and execute one operator-authorized disposable shot after resolving only real blockers |
| **W0 — Baseline reconciliation** | Engineering reconciliation COMPLETE; live Windows shot contract still needs current-state confirmation | [W0 starting baseline](../engineering/VSCS_W0_Integrated_Delivery_Starting_Baseline_v1.md) |
| **W1 — Governed visual references / Issue #61** | Implementation and Windows UI qualification demonstrated; **strict cardinal angles and unseen geometry not fully accepted** | Draft PR #66; approved MASTER/Front preserved; Rear/Left/Right candidates remain unapproved unless independently verified |
| **Camera-angle refinement** | **DEFERRED / ACCEPT KNOWN LIMITATION FOR VIDEO PROOF** | Left/Right Detailed views remained angled; expected impact to cinematic shots is unmeasured. Reopen only on demonstrable video identity/continuity defect or strict product-view requirement |
| **MiniMax H3 multi-frame** | **INCLUDE IN W2 PROVIDER ASSESSMENT; integration remains CONDITIONAL** | Review existing [H3-MF assessment](../PHASE_20_H3_MF_MULTIFRAME_REFERENCE_WORKFLOW_ASSESSMENT.md); distinguish semantic references from timed guides and actual provider-supported duration. No live trial implied |
| **Current Windows checks** | 2026-11-26 operator reported Ruff check/format and mypy PASS; 23 focused tests PASS | These are verification of source, not live video acceptance |
| **First proof contract** | PROPOSED, not yet frozen against persisted project/shot data | `CAP-PRP-002` diagnostic console, unoccupied engineering bay, advancing three-quarter front-left shot, target 15–20 s; validate current shot ID and Ready state |
| **Merge / release** | NOT AUTHORIZED | PR #66 remains Draft; no automatic issue closure or release declaration |

### Immediate next action (the default answer to “what's next?”)

**W2.1 — Reconcile the real 15–20-second generation route.** Check the existing LTX and MiniMax H3 provider implementations, active Windows/ComfyUI model capabilities, shot-scoped CAP requirements, exact generation limits, and registration of generated MP4 into governed GeneratedMedia. Select **one** production-capable provider for the first diagnostic-console shot; document measured limitations, not theoretical support. Identify the minimal blocking code changes and implement them directly on PR #66 after the approved W2 scope is confirmed. **Do not submit a GPU job or paid request without fresh one-use authorization.**

## 3. Ordered delivery backlog

These W-IDs are the **current operational work-package names**. The earlier [Accelerated Completion Assessment v1](../engineering/VSCS_Accelerated_Completion_Assessment_v1.md) used W2 for CAP readiness and W3 for first clip. This register **supersedes that package numbering** for execution; no previously delivered work is deleted. Effort ranges below are provisional engineering working days, **not commitments or additive elapsed schedules**. Re-estimate after the first video and export.

| ID / priority | Deliverable and bounded scope | State | Dependency / acceptance exit | Indicative effort |
|---|---|---|---|---|
| **W0 / completed engineering** | Baseline, ancestry, integration map and protected project snapshot | COMPLETE (Windows shot recheck pending) | [W0 record](../engineering/VSCS_W0_Integrated_Delivery_Starting_Baseline_v1.md) | — |
| **W1 / P0 enabling** | Governed MASTER, derived reference Candidates, independent human QC and source freshness | IMPLEMENTED; partial live qualification; deferred angle refinement | Approved Front available; strict Rear/Left/Right and unseen geometry NOT production-approved | No further camera work unless W2 exposes blocker |
| **W2.1 / P0 NEXT** | Identify and bind one working 15–20 s shot path; compare existing **LTX-2.3/LTX-2.5** and **MiniMax H3**, including multi-frame feasibility | NOT STARTED | Read-only capability/source inventory, shot-scoped CAP gates, clear provider selection and exact real test plan | 1–3 d |
| **W2.2 / P0** | Real 15–20 s video generation from approved Shot/CAP context with job provenance, restart/recovery and GeneratedMedia registration | PENDING W2.1 | Explicit trial consent; playable clip; stable subject and camera; technical QC and human review | 4–9 d |
| **W2.3 / P1 conditional** | H3 multi-frame: semantic image references, ordered timed guides, real duration limits, output reconciliation and continuity QC | ASSESS IN W2.1; implement only if valuable | Reuse [H3-MF1–MF4 plan](../PHASE_20_H3_MF_MULTIFRAME_REFERENCE_WORKFLOW_ASSESSMENT.md); separate consent for GPU/paid tests | 4–8 d if needed |
| **W3 / P0** | Assemble accepted shots into scenes/sequences; ordered timeline, continuity, trim/transition, durable playable rough cut | PENDING FIRST CLIP | Governed GeneratedMedia selection; no use of unapproved Candidates in final production | 4–8 d |
| **W4 / P0** | Voice/narration/dialogue generation with stable actor/character identity and provenance | PENDING SHOT + TIMELINE TIMING | Verified voice files, timing, approvals, costs/rights recorded | 3–7 d provisional |
| **W5 / P0** | Shot-level lip-sync for visible speakers; sync QC and derived-media review | PENDING VOICE/TIMING | Approved dialogue and locked timing; no destructive rewrite of source clip | 4–8 d provisional |
| **W6 / P0** | Ambience, SFX/music, mixing, captions as needed; episode timeline export and master QC | PENDING W3–W5 | One playable synchronized, reviewed and reopenable exported proof | 5–10 d provisional |
| **W7 / P0** | Complete pilot episode, multi-shot continuity, failure recovery, operator UAT, delivery packaging | PENDING SHORT PROOF | Actual approved shot list and export, not inferred from 69-shot planning | Re-estimate after proof |
| **W8 / P1** | Repeatable production, batch automation, UX consolidation, publishing, first-run hardening | PENDING PILOT | Demonstrated reliability/throughput and release approval | Re-estimate after pilot |

### Cross-cutting issue work — pull forward only if it blocks the active package

| GitHub issue | Working disposition |
|---|---|
| [#61](https://github.com/npayne10/video_series_studio/issues/61) | W1 governed reference implementation delivered; retain open/draft until evidence and owner acceptance. Camera alignment deferred, not quietly marked solved. |
| [#54](https://github.com/npayne10/video_series_studio/issues/54), [#55](https://github.com/npayne10/video_series_studio/issues/55), [#58](https://github.com/npayne10/video_series_studio/issues/58) | Shot-scoped CAP/completion truth and readiness; correct only blockers for visible assets in W2. |
| [#53](https://github.com/npayne10/video_series_studio/issues/53) | Correct a visual asset only if production QC shows an actual blocking defect; respect attempt budgets. |
| [#52](https://github.com/npayne10/video_series_studio/issues/52) | H3 multi-frame feasibility enters W2.1 now; full provider implementation remains conditional on a clear benefit. |
| [#59](https://github.com/npayne10/video_series_studio/issues/59), [#60](https://github.com/npayne10/video_series_studio/issues/60) | Batch review usability fixes with adjacent UI work unless a blocking operator defect appears. |
| [#67](https://github.com/npayne10/video_series_studio/issues/67) | In-app paid MASTER creation deferred while approved manual MASTER import serves the pilot. |

Issue state above is a **planning disposition**, not a fresh GitHub issue-status audit. Reconcile GitHub issue/PR status before administratively closing or changing any item.

## 4. Production acceptance gates and evidence

| Milestone | Demonstrable acceptance (not just source/tests) | Status |
|---|---|---|
| **M1 — First video** | 15–20 s target or documented provider-limited governed span; real MP4, provenance, GeneratedMedia QC and operator acceptance | PENDING |
| **M2 — Multi-shot assembly** | Two or more approved shots combined into a selectable, persisted and playable scene/sequence; continuity review | PENDING |
| **M3 — Spoken sequence** | Approved voice/dialogue synchronized with visible speaking shot(s), reviewed lip-sync and understandable mix | PENDING |
| **M4 — First exported proof** | Playable final file with verified shots/audio/export manifest, restart recovery and human QC | PENDING |
| **M5 — Pilot episode** | Accepted shot set, completed scenes, coherent edited episode and final master/export | PENDING |
| **M6 — Repeatable release** | Automated recovery, operator guides, normal first-run acceptance, explicit release authorization | PENDING |

**Provisional time reference:** [Accelerated Completion Assessment v1](../engineering/VSCS_Accelerated_Completion_Assessment_v1.md) estimated first 18-second proof **3–6 elapsed weeks**, full pilot **8–16 weeks**, repeatable release **12–24 weeks** from its original planning kickoff. Those are old planning bands, **not deadlines**; do not reset or claim them as updated forecasts. Replace with measured time-to-first-video and clip throughput as soon as W2 yields real output.

## 5. Binding decisions — change log

| ID / date | Decision | Consequence and revisit trigger |
|---|---|---|
| **D-001 / 2026-11-25** | Adopt accelerated, production-first delivery as provisional baseline | One functional capability, CI and one integrated Windows acceptance; maintain scoped consent and human authority |
| **D-002 / 2026-11-25** | W0 repository reconciliation accepted as engineering starting point | Baseline protection and code-route evidence; Windows project truth must be rechecked before real video |
| **D-003 / 2026-11-25** | Issue #61 Fast/Detailed camera qualification enabled; qualified output stays Candidate | Separate GPU consent; image plausibility never establishes unseen canonical geometry |
| **D-004 / 2026-11-25** | Separate viewpoint PASS from independent geometry VERIFIED on qualified views | Do not approve unverified Rear/Left/Right Candidates merely to unblock downstream video |
| **D-005 / 2026-11-26** | **Stop further camera-angle refinement** after Front/Rear/Left/Right evidence | Imperfect side elevations provisionally acceptable for cinematic-video *experimentation*, not strict reference approval. Reopen only on material video identity/continuity failures or precise orthographic deliverable need |
| **D-006 / 2026-11-26** | **Prioritize 15–20 s video → shot assembly → voice → lip-sync → audio/mix → episode export** | Operational W2–W8 sequence now supersedes older package order; first real clip becomes the primary delivery gate |
| **D-007 / 2026-11-26** | **Re-evaluate MiniMax H3 multi-frame during W2** alongside existing LTX routes | Do not treat source workflow as validated API graph or assume 20 s support; implement only when provider evidence justifies it |
| **D-008 / 2026-11-26** | Establish **this** file as the single day-to-day MASTER backlog | Every new change to scope, priority, acceptance, estimate or status updates this register in the same PR, with evidence links |

## 6. Update protocol — mandatory for every development handoff

1. **Start:** read §2 (current position), then §3 (next package), §5 (decisions) and linked capability specifications. Confirm GitHub branch/PR head and local worktree without overwriting user changes.
2. **Before code:** state exact active backlog ID, scope, accepted constraints and whether special authority is needed. Reconcile only relevant source and outstanding issues.
3. **On completion or decision:** update the package status, concrete evidence, new blockers, next action and dated decision in **this file** in the same GitHub PR commit as implementation/documentation. A proposed change is not marked accepted until Neill approves it.
4. **Handoff:** provide GitHub PR/commit, exact Windows `git fetch`/`git pull --ff-only` commands, Ruff check/format, mypy, focused/full pytest commands and focused UI acceptance steps as applicable.
5. **Weekly or material change:** re-estimate after real video/assembly throughput; reconcile related GitHub issues/ADRs/specs. Preserve history by adding a decision entry; supersede rather than silently erase an earlier approval.
6. **Authority:** only Neill may approve paid calls, real GPU/video trials, protected project mutations, merge/release and production-reference/media approval. GitHub commits and automated tests never substitute for this consent.

## 7. Supporting documents (not competing operational backlogs)

- [Architecture vNext Roadmap](VSCS_ARCHITECTURE_VNEXT_ROADMAP.md) — adopted long-term architectural sequencing and dependency constraints.
- [Production MVP Roadmap](../engineering/VSCS_Production_MVP_Roadmap.md) — product and commercial objectives.
- [Accelerated Completion Assessment v1](../engineering/VSCS_Accelerated_Completion_Assessment_v1.md) — original backlog estimates, risks and issue reconciliation; old W-number assignments superseded here.
- [W0 Integrated Delivery Starting Baseline](../engineering/VSCS_W0_Integrated_Delivery_Starting_Baseline_v1.md) — source and protected-hash authority.
- [Issue #61 W1 Governed Multiple-Angle Acceptance](../engineering/Issue_61_W1_Governed_Multiple_Angle_Operator_Acceptance.md) — reference governance and Windows acceptance.
- [H3 Multi-Frame Assessment](../PHASE_20_H3_MF_MULTIFRAME_REFERENCE_WORKFLOW_ASSESSMENT.md) — exact source-workflow findings and qualification gates.
- [Episode Assembly and Postproduction Architecture](../PHASE_20_18_2_3_7_EPISODE_ASSEMBLY_TIMELINE_POSTPRODUCTION_ARCHITECTURE.md) — proposed timeline/voice/lip-sync architecture; architectural changes still require approval.
- [Decision register](DECISIONS.md), [Milestone tracker](MILESTONE_TRACKER.md), [Release plan](RELEASE_PLAN.md) — retained historical and specialist records; their stale snapshots do not override §2–5 of this file.

**Next update trigger:** W2.1 provider/source reconciliation and an operator-confirmed persisted Shot/Ready state, followed by provider selection and an explicitly authorized first actual video-generation trial.
