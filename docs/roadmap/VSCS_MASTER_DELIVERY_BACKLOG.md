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
| **Current capability** | **UPSTREAM EPISODE PLANNING GATE — then W2.2** | 2026-11-26 real Asset Resolver: **5 declared / 0 production-ready / 3 visible unresolved-Draft-stale / 2 reviewed nonvisual**. Camera/Lighting/Environment Ready, Planning Review and Production Packages not yet accepted. **GPU launch ON HOLD.** [Full episode runbook](../user_manual/VSCS_Episode_Production_Runbook.md) |
| **W0 — Baseline reconciliation** | Engineering reconciliation COMPLETE; live Windows shot contract still needs current-state confirmation | [W0 starting baseline](../engineering/VSCS_W0_Integrated_Delivery_Starting_Baseline_v1.md) |
| **W1 — Governed visual references / Issue #61** | Strict geometry approval still separate; **cinematic-only cross-view acceptance implementation awaiting Windows validation** | Draft PR #66; approved MASTER/Front preserved; Rear/Left/Right can receive separately reviewed, hash-fresh cinematic suitability while remaining canonical Candidates. [Operator acceptance](../engineering/Issue_61_Cross_View_Cinematic_Acceptance.md) |
| **Camera-angle refinement** | **DEFERRED / ACCEPT KNOWN LIMITATION FOR VIDEO PROOF** | Left/Right Detailed views remained angled; expected impact to cinematic shots is unmeasured. Reopen only on demonstrable video identity/continuity defect or strict product-view requirement |
| **MiniMax H3 multi-frame** | **ASSESSED; DEFERRED / CONDITIONAL W2.3** | Existing governed **H3 Ref2VA** single-span route is distinct from unbound experimental timed multi-guide workflow; revisit only if first-clip continuity warrants it. No live trial implied |
| **Current Windows checks** | 2026-11-26 operator reported Ruff check/format and mypy PASS; 23 focused tests PASS | These are verification of source, not live video acceptance |
| **First proof contract** | PROPOSED, not yet frozen against persisted project/shot data | `CAP-PRP-002` diagnostic console, unoccupied engineering bay, advancing three-quarter front-left shot, target 15–20 s; validate current shot ID and Ready state |
| **Merge / release** | NOT AUTHORIZED | PR #66 remains Draft; no automatic issue closure or release declaration |

### Immediate next action (the default answer to “what's next?”)

**Complete reviewed CAP structured knowledge offline, then resume Asset Resolver for the diagnostic-console Shot.** Use **Prepare from Reviewed CAP (Offline)…** for reviewable Facts, visible affordances and Constraints with no provider call; human acceptance, CAP and Asset approval remain separate. Review the three visible rows (`CAP-LOC-001`, `CAP-PRP-002`, `CAP-PRP-001`), inspect their precise Partial/Draft CAP/Asset/reference blockers and complete valid human approvals. Preserve the two reviewed nonvisual classifications. Then finish **Camera Planner → Lighting Planner → Environment Planner → Planning Review → Production Packages** (all five compiler/review tabs) → Production Tasks and readiness. Only after these gates are current and approved may W2.2 H3 GPU qualification be considered, with a **separate one-use authorization**. Follow the [per-Episode production runbook](../user_manual/VSCS_Episode_Production_Runbook.md).

## 3. Ordered delivery backlog

These W-IDs are the **current operational work-package names**. The earlier [Accelerated Completion Assessment v1](../engineering/VSCS_Accelerated_Completion_Assessment_v1.md) used W2 for CAP readiness and W3 for first clip. This register **supersedes that package numbering** for execution; no previously delivered work is deleted. Effort ranges below are provisional engineering working days, **not commitments or additive elapsed schedules**. Re-estimate after the first video and export.

| ID / priority | Deliverable and bounded scope | State | Dependency / acceptance exit | Indicative effort |
|---|---|---|---|---|
| **W0 / completed engineering** | Baseline, ancestry, integration map and protected project snapshot | COMPLETE (Windows shot recheck pending) | [W0 record](../engineering/VSCS_W0_Integrated_Delivery_Starting_Baseline_v1.md) | — |
| **W1 / P0 enabling** | Governed MASTER, derived reference Candidates, independent human QC and source freshness | IMPLEMENTED; partial live qualification; deferred angle refinement | Approved Front available; strict Rear/Left/Right and unseen geometry NOT production-approved | No further camera work unless W2 exposes blocker |
| **W2.1 / completed source review** | Reconcile **LTX-2.3/LTX-2.5**, governed **H3 Ref2VA** and experimental H3 timed multi-frame; select first clip route | **COMPLETE — source-level only** | [W2.1 evidence and exact readiness gates](../engineering/VSCS_W2_1_Video_Generation_Capability_Reconciliation.md); Windows models, Shot Ready and hardware remain unverified | — |
| **W2.2 / P0 ACTIVE — UPSTREAM BLOCKED** | Operator-authorized first governed **15 s H3 Ref2VA** video; verify playable MP4, job provenance, recovery and GeneratedMedia QC; consider ~18 s LTX-2.5 spans only if blocked | **H3 safeguard implemented; Episode Asset Resolver and downstream planning/package gates INCOMPLETE; GPU HOLD** | [Windows acceptance](../engineering/VSCS_W2_2_First_Governed_Video_Windows_Acceptance.md): persisted Ready Shot/approved Introduction Keyframe; H3 models; separate GPU approval; human review | 4–9 d provisional |
| **W2.3 / P1 conditional** | H3 timed multi-frame guides if needed after observing actual first-clip continuity | **DEFERRED**; source assessment complete | Reuse [H3-MF1–MF4 plan](../PHASE_20_H3_MF_MULTIFRAME_REFERENCE_WORKFLOW_ASSESSMENT.md); no unreviewed canvas/API execution; separate consent | 4–8 d only if justified |
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
| **D-009 / 2026-11-26** | **W2.1 source-level reconciliation: select governed 15 s MiniMax H3 Ref2VA single-span as first W2.2 trial candidate** | H3 15 s is a source limit, **not** verified Windows execution; Windows Ready/approved keyframe/models and one-use consent are mandatory. LTX-2.5 ~18 s multi-span is fallback; experimental H3 multi-frame deferred until demonstrated need. [Evidence](../engineering/VSCS_W2_1_Video_Generation_Capability_Reconciliation.md) |
| **D-010 / 2026-11-26** | **W2.2 execution safeguard: require a fresh, copyable, exact-match authorization phrase before UI-submitted automated video GPU execution** | Added in Draft PR #66 with focused Qt tests. Readiness and backend launch claims still apply; actual Windows inference and GeneratedMedia QC remain operator-held acceptance, not code-completion evidence. [Procedure](../engineering/VSCS_W2_2_First_Governed_Video_Windows_Acceptance.md) |

| **D-012 / 2026-11-26** | **Automate reviewed CAP-to-structured knowledge preparation (offline first)** | Review-audit and field-value-verified proposals from saved human-reviewed Facts/visible affordances/Constraints; explicit human acceptance, merge without replacing prior entries; AI provider only behind separate cost confirmation. CAP and reference approval remain independent. [Procedure](../engineering/VSCS_Automated_Structured_CAP_Knowledge_Completion.md) |
| **D-013 / 2026-11-26** | **Accept valid persisted CAP reviews after MASTER prompt reconstruction** | Historical audit result hashes precede a reviewed MASTER prompt rebuild. Verify review decisions and exact current canonical fields through the shared review validator; reject altered/unreviewed or deferred content. No bypass of CAP/Asset/image approvals. |
| **D-014 / 2026-11-26** | **Make qualified-view approval interruptions explicit** | Operator observed the Rear approval flow returning to Candidate after camera confirmation. Compare Qt confirmation values explicitly and show a precise nonapproval notice for camera, geometry, or final-confirmation decline. Keep independent geometry evidence required and preserve Candidate state on interruption. |
| **D-015 / 2026-11-27** | **Improve qualified-view evidence entry without weakening approval** | Replace fixed-width Qt input boxes with wrapped, resizable review dialogs. Long typed observations are audit evidence, not generation controls. Future operator-effort reduction should prefill only verifiable metadata, never fabricate independent design evidence or approve a reference automatically. |
| **D-016 / 2026-11-27** | **Automated reference-approval context preparation** | Show persisted asset ID, requested view, reference ID, file, lifecycle and source MASTER version in a selectable, read-only panel for both qualified-view approvals. Explicitly label camera/geometry as unverified; keep operator observations blank and distinct, and maintain independent Yes/No decisions. No AI, GPU, status mutation or inferred geometry evidence. |
| **D-017 / 2026-11-27** | **Cross-view cinematic-use acceptance distinct from canonical approval** | Explicit operator QC compares MASTER, approved Front and candidate cardinal views, records cross-view/image-hash evidence with freshness checks and offers an opt-in cinematic readiness/projection API. Strict readiness remains unchanged; no default video-execution bypass, automatic canonical promotion or GPU authorization. [Acceptance](../engineering/Issue_61_Cross_View_Cinematic_Acceptance.md) |
| **D-011 / 2026-11-26** | **Restore the actual end-to-end Episode sequence as W2.2 prerequisite; halt video trial until planning and package authority are current** | Screenshot shows 5 asset bindings, 0 Ready, 3 visible unresolved/Draft/stale and 2 reviewed nonvisual. Complete Asset Resolver → Camera → Lighting → Environment → Planning Review → package compiler tabs → Tasks/Readiness. Keep H3 code ready but no GPU. [Runbook](../user_manual/VSCS_Episode_Production_Runbook.md) |

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
- [W2.1 Video Generation Capability Reconciliation](../engineering/VSCS_W2_1_Video_Generation_Capability_Reconciliation.md) — first-video provider decision, real duration limits, Windows readiness contract and GeneratedMedia checkpoints.
- [Automated Structured CAP Knowledge Completion](../engineering/VSCS_Automated_Structured_CAP_Knowledge_Completion.md) — offline reviewed source proposals and explicit human acceptance; paid AI is optional.
- [Per-Episode Production Runbook](../user_manual/VSCS_Episode_Production_Runbook.md) — authoritative UI order for each Episode, including all planning and package gates.
- [W2.2 First Governed Video Windows Acceptance](../engineering/VSCS_W2_2_First_Governed_Video_Windows_Acceptance.md) — exact operator steps, one-use authorization boundary and live-result ledger.
- [Issue #61 W1 Governed Multiple-Angle Acceptance](../engineering/Issue_61_W1_Governed_Multiple_Angle_Operator_Acceptance.md) — reference governance and Windows acceptance.
- [H3 Multi-Frame Assessment](../PHASE_20_H3_MF_MULTIFRAME_REFERENCE_WORKFLOW_ASSESSMENT.md) — exact source-workflow findings and qualification gates.
- [Episode Assembly and Postproduction Architecture](../PHASE_20_18_2_3_7_EPISODE_ASSEMBLY_TIMELINE_POSTPRODUCTION_ARCHITECTURE.md) — proposed timeline/voice/lip-sync architecture; architectural changes still require approval.
- [Decision register](DECISIONS.md), [Milestone tracker](MILESTONE_TRACKER.md), [Release plan](RELEASE_PLAN.md) — retained historical and specialist records; their stale snapshots do not override §2–5 of this file.

**Next update trigger:** Windows CAP-PRP-002 offline reviewed-knowledge preparation/approval, then Asset Resolver resolves the three currently blocked visible requirements, then current Camera/Lighting/Environment Ready, Planning Review Approved/Integrated and Production Packages approved; only then W2.2 readiness and separately authorized GPU trial.
