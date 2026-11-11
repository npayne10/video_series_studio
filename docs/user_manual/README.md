# VSCS — Operator Help and User Manual Index

**Version:** v0.2 (living documentation, updated 2026-11-10)  
**Source:** Current VSCS development branch; do not treat work-in-progress instructions as accepted production authority.

## Open first

1. [VSCS User Manual](VSCS_User_Manual.md) — project creation, Story, analysis, approved Story workflow, proposal/authority separation, CAP review, safety and acceptance steps.
2. [Automation Progress Audit](Automation_Progress_Audit.md) — which Story Automation buttons lack running feedback, safety constraints, remediation and Qt acceptance criteria.
3. [Production workflow architecture](../engineering/VSCS_Video_Production_Workflow_V2.md) — architecture/aspirational workflow for context; verify every action against the user manual and actual UI.
4. [B.5.22 disk-backed acceptance](../engineering/Phase_20_19_3B5_22_Disk_Backed_CAP_Persistence_Acceptance.md) — automated SQLite durability, governance and separate desktop operator acceptance.

## Known verified current path for B.5.22

`B5_22_DISPOSABLE_CAP_ACCEPTANCE_UI` → `STORY-001` Approved → Story Analysis complete → **Planning Proposals generated** (1 Episode + 1 Scene, no authority yet) → **Review Proposals…** → review/accept → **Compile Accepted…** → inspect actual **Production Planning** Episode/Scene records.

Next: Shot Proposals, review/accept/compile, register and bind assets, CAP context/queue/review, reviewed Draft CAP save, project close/reopen and provenance/status check. Each stage is a separate acceptance checkpoint. Do not modify `B5_19A_ACCEPTANCE`.

## B.5.26F F5 operator procedures — updated 2026-11-10

Read [VSCS User Manual — B.5.26F, F5.0–F5.3](VSCS_User_Manual.md#b526f--qwen-image-editing-f5-hardware-tests-and-gpu-memory-release-operator-procedure) for the **mandatory numbered procedure** when creating a fresh disposable Candidate lineage, running dual-workflow inspection, checking F5 hardware readiness, releasing ComfyUI GPU cache and conducting the first controlled source-conditioned Qwen edit.

**Operator-verified:** F5.1 and F5.2 code validated with **2,681 passed, 1 Windows symlink skip**; release button sent one accepted local `/free` request while idle; refreshed F5 readiness showed **14,174 MiB free of 16,311 MiB**, with Qwen nodes/model choices available. **Still pending:** genuine local Qwen GPU inference, new Candidate registration and visual quality acceptance.

The old `B5_22_DISPOSABLE_CAP_ACCEPTANCE_UI` Engineering Control Room source **Candidate 2 is at attempt 2/2**, so do not use it for initial F5.3 hardware qualification. The manual now describes how to establish an **independent disposable project, genuine approved Draft CAP, source Candidate and saved failed semantic report** without fabricating evidence. Screens not yet walked end to end are marked as checkpoints. The paid semantic review requires separate cost approval.

**Mandatory documentation contract:** Every future recommendation implying action by the operator must provide a numbered, UI-accurate, reproducible step-by-step procedure, explicit preconditions, isolation, expected responses, evidence, stop/retry rules and separate acceptance gates. Update this index and the User Manual in the **same development phase and GitHub branch as the feature**. Do not present a mock-test pass or read-only preflight as real GPU acceptance.


## Governed revision of existing Draft CAPs — development update

The existing CAP Batch **Discover Shot Assets** dropdown excludes assets
already holding a structured CAP. The new separate **Existing Draft CAPs**
selector and **Edit Existing Draft CAP…** dialog enable a review-controlled
revision of **one Deferred/Rejected field**, preserving all accepted field
decisions and failing stale or approved database writes.

See the numbered
[Diagnostic Console revision acceptance procedure](VSCS_User_Manual.md#b526f-f53-prerequisite--edit-existing-draft-cap-new-governed-revision-workflow).
**Development status:** committed; Windows regression and real UI acceptance
pending. Never infer that the Geometry blocker is cleared before the
actual saved Draft and subsequent Visual Identity inspection are verified.


## Automation-first existing Draft CAP revisions — correction (2026-11-10)

**The current Edit Existing Draft CAP workflow is an audited manual-review/persistence mechanism, not automated content generation.** It is **not accepted for F5.3 automated source preparation** until VSCS can propose the deferred Geometry field itself from governed Story and accepted CAP context. The operator must review and approve a generated, evidence-labelled proposal, rather than type/paste a replacement just to clear readiness. Explicit paid-provider consent, structured validation, cached provenance and governed one-field persistence are mandatory.

**Immediate operator action:** Cancel the open Diagnostic Console Geometry editor; leave Geometry **Defer**, preserve Materials/Components/Scale and Engineering Control Room Candidate 2 attempt 2/2. See [automation-first corrective procedure](VSCS_User_Manual.md#vscs-automation-principle--correction-to-f53-acceptance).


## Automated existing Draft CAP field proposals — implementation update

The former manual Geometry-entry route is superseded by **Generate / Regenerate Field Proposal (AI — Paid)** in the existing Draft CAP editor. The operator reviews automatically generated, source-grounded fields, which are **read-only** in the dialog. The separate **Load Latest Cached Field Proposal (No AI Charge)** button reopens a completed proposal without another provider call; **Reject Generated Proposal (Keep Draft)** clears the selection without changing the CAP. Saving still requires a separate reviewed Draft-only confirmation.

[Read the full numbered operator acceptance and safe paid-provider test procedure](VSCS_User_Manual.md#b526f--automated-existing-draft-cap-field-regeneration-operator-procedure).

**Status:** Committed to GitHub and **not yet operator-accepted**. Ruff/Mypy/full regression and UI checks are required before initiating a paid test. The Diagnostic Console Geometry is still deferred; no automatically generated CAP value has been accepted yet. The Engineering Control Room Candidate 2 attempt **2/2** remains out of scope.


## F5.3 — Isolated Qwen GPU acceptance (outside CAP)

**Implemented, not yet locally validated:** `python -m vscs.application.caps.qwen_f53_isolated_acceptance` supports offline **--prepare** (copy disposable source image, write bounded single-job Qwen queue and graph in an external directory) and explicitly confirmed **--execute** (one real source-conditioned ComfyUI GPU request). It does not import or call CAP registration, CAP quality report or guided correction-attempt journal. The actual GPU test has **not yet been run** and no acceptance can be claimed from mocked pytest.

See [F5.3 isolated managed Qwen GPU acceptance — numbered operator instructions](VSCS_User_Manual.md#b526f-f53--isolated-managed-qwen-gpu-acceptance-no-cap-correction).

**Do not change the existing Diagnostic Console Candidate 3 or its genuine `HUMAN_REVIEW_REQUIRED` semantic report; do not spend the Engineering Control Room Candidate 2 attempt 2/2.** The test uses an exact byte-for-byte **copy** of Candidate 3 in a new directory **outside** the VSCS project, with a separate output. GPU inference requires independent operator confirmation and must follow successful Ruff/Mypy/pytest acceptance.


## Required documentation for each UI action

| Item | Requirement |
|---|---|
| UI location | Navigation path, actual control label and screenshot |
| Preconditions | Project, Story/Shot/asset states and provider configuration |
| Effect | Read-only/proposal/Draft/Canon/governed/paid authority level |
| Result | Actual data path/record and expected status |
| Failure | Error text, underlying cause and safe recovery |
| Verification | Automated test ID and actual operator screenshot |
| Progress | Whether operation shows Running, provider, elapsed time, success/failure |
| Source status | UI verified / code confirmed / planned / not yet evidenced |

When a feature changes, modify the User Manual in the **same GitHub branch** as the code, then update applicable help UI and screenshots after local operator acceptance.

## Manual completion tracker

- [x] Project lifecycle basics — UI verified
- [x] Story source, metadata, analysis, approval — UI verified
- [x] Planning Proposal generation and proposal-vs-authority distinction — UI verified
- [x] Story Automation actions inventory — code confirmed
- [x] CAP batch read-only discovery and caching — prior operator UI verified
- [x] Disk-backed Draft CAP durability — automated integration verified
- [x] Proposal review/accept/compile — UI verified for one Episode and one Scene, no blockers
- [ ] Shot proposal review → governed Shot plan — awaiting current operator UI walkthrough
- [ ] Actual desktop Draft CAP save/reopen — awaiting current operator UI walkthrough
- [ ] Asset and reference canonical approval
- [ ] Provider selection, internal/hybrid/external generation
- [ ] Production Task / H3 readiness / scheduling
- [ ] Generated media, Episode Assembly and Post-production
- [ ] Project preferences, export, backup/restore, diagnostics
- [ ] Complete Automation progress indicator implementation — shared Planning/Shot runner committed, local acceptance pending; other actions outstanding
- [x] F5.1 dual-workflow and F5.2 ComfyUI memory-release operator guidance — documented and UI observed
- [x] Existing Draft CAP guarded manual-review persistence — 2,695 passed, 1 skipped baseline
- [x] Automated existing Draft field generation/cache UI — Diagnostic Console Geometry proposal recovered without additional provider charge and saved in governed Draft; Visual Identity READY, operator observed
- [x] F5.3 isolated one-shot Qwen GPU inference — RTX 5060 Ti actual run completed 2026-11-10: 1392 × 752 PNG, 371.54 s, verified output SHA-256; independent CAP isolation audit and visual quality comparison pending
- [ ] F5.4.1B Isolated Mask-Aware Qwen Workflow Qualification — separate experimental masked graph, external ROI/mask preparation, one-shot guarded ComfyUI test runner and pixel-preservation audit committed; Windows regression, node compatibility and real GPU/semantic acceptance pending
- [ ] F5.4.1 Qwen Spatial Edit Fidelity — read-only managed graph/PNG diagnostic and fail-closed degraded final attempt gate committed; local regression/UI acceptance pending; genuine masked spatial editing NOT YET IMPLEMENTED
- [ ] F5.4 governed human-review correction — implementation committed: immutable reviewer disposition for saved HUMAN_REVIEW_REQUIRED reports, accepted-field scope, sealed worker check and tighter Qwen edit prompt; local regression and UI acceptance pending
- [ ] Context-sensitive Help integration in VSCS

**No part of this index lifts the H3 live-execution hold or authorises paid provider work without explicit operator action.**

## Latest operator checkpoint — 2026-11-04

The `B5_22_DISPOSABLE_CAP_ACCEPTANCE_UI` Episode and Scene both show Ready and 0:35 runtime, with 0:00 Scene budget remaining. Navigation relabelled in GitHub (Story → Episode Planner, top-level Production Packages) and approved by operator, awaiting local quality gates. Shared progress runner for Planning/Shot proposal generation committed, awaiting targeted and full regression. **Do not rerun Planning Proposals to test progress; it could overwrite accepted proposal records.** Run Shot Proposals once only after local validation, then inspect resulting proposal IDs/durations before human acceptance.

**Automation UX scope update:** shared progress is now committed for six Story proposal-generation actions; SQLite-linked Resolve Assets and synchronous Review Gaps are not migrated. Local acceptance is pending.

## F5.3 confirmed hardware inference — 2026-11-10

The operator completed the **first real RTX 5060 Ti 16 GB source-conditioned Qwen Image Edit run** using the external `D:\VSCS_QWEN_F53_ACCEPTANCE\run_001` bundle. `GPU_OUTPUT_VERIFIED_NO_CAP_CHANGES` was reported, output **1392 × 752**, runtime **371.54 s**, checksum `59832d36eaa59fe3746e91ca29639e2ab2361122b5771607e91692e75d696778`; external bundle includes the reservation and result evidence. Post-run GPU allocation was **13,018 MiB** of **16,311 MiB**, but **peak was not measured**. The implementation reports no Candidate registration, Canon approval or correction attempt. Independent GUI persistence audit and visual-quality assessment remain outstanding; Candidate 3's original semantic decision remains `HUMAN_REVIEW_REQUIRED` and cannot be rewritten. **Never rerun `run_001`.** See [F5.3 hardware acceptance evidence and non-generative next steps](VSCS_User_Manual.md#b526f-f53--real-rtx-5060-ti-hardware-acceptance-evidence-2026-11-10).

## F5.4 governance and edit fidelity — 2026-11-10

F5.4 is committed but **not locally validated**. It adds **Record Human Correction From Saved Review…** to the Canonical Reference Editor (no new OpenAI charge), allowing a named reviewer to select exactly **one already accepted Draft CAP field** and save an immutable discrepancy finding associated with the original Candidate image and semantic-report checksums. It does **not** rewrite the original `HUMAN_REVIEW_REQUIRED` report, approve the Candidate or generate an image. The existing **Correct From Saved Review…** route then verifies that disposition as an independent correction authority while retaining the two-attempt cap and current CAP/Candidate checks. Managed Qwen Image Edit receives tighter accepted-field-specific edit and source-preservation instructions; the worker rechecks the reviewer record hash before and after the real GPU run. The original F5.3 external GPU success remains a separate milestone; these F5.4 behaviors require Ruff, Mypy, pytest and guarded UI review before any new inference. See [F5.4 User Manual](VSCS_User_Manual.md#b526f-f54--governed-human-review-correction-and-qwen-edit-fidelity).

## F5.4.1 spatial fidelity and final-attempt protection

Candidate 4's real semantic review returned `REGENERATE_RECOMMENDED` with semantic **81 (from 88)** and design consistency **68 (from 75)**; the raised dial remained unresolved. The existing Qwen managed graph has **KSampler denoise=1.0**, source-image conditioning but **no validated region mask/inpainting input**. F5.4.1 commits a **read-only** capability inspector, optional PNG-level difference diagnostics and a **degraded final-attempt safety guard**. In **Correct From Saved Review…** for Candidate 4, click **F5.4.1 Inspect Spatial Edit Fidelity (No Generation)**. If the final attempt is **2/2** and the prior evaluation reports declining effectiveness, both Generate controls are blocked. It does not spend an attempt or make an API call. Genuine region-controlled Qwen editing requires separate workflow development and isolated GPU qualification. See [the full F5.4.1 guide](VSCS_User_Manual.md#f541--qwen-spatial-edit-fidelity-first-guarded-capability-assessment).

## F5.4.1B isolated masked Qwen qualification

Implementation creates a **separate experimental** Qwen Image Edit graph using `LoadImageMask` → `SetLatentNoiseMask` → the existing KSampler, followed by **ImageCompositeMasked** against the original source. The second composite is necessary for exact protection outside the editable white mask. The **trusted managed graph remains unchanged**. External offline bundles contain `source.png`, `mask.png`, `experimental_masked_api.json` and `qualification_manifest.json`; no mask upload or GPU generation occurs at this step. A separate operator-authorised one-shot test runner checks local node schemas, models and bundle integrity, uploads the disposable mask to ComfyUI and preserves a reservation before possible GPU submission. It compares exact RGB pixels outside the mask after inference, but **does not prove the requested geometry was corrected**. It is not yet tested on Windows or accepted on GPU. The genuine Candidate 4 Attempt **2/2 remains disabled**. See [F5.4.1B step-by-step acceptance workflow](VSCS_User_Manual.md#f541b--isolated-mask-aware-qwen-workflow-qualification).

### F5.4.1B live qualification — 2026-11-11

The first **isolated** masked Qwen GPU run completed in external `run_002` (344.7 seconds; ComfyUI prompt `329001b5-e2b1-4e51-96f7-b8efcb1a08b3`). The saved qualification returned `SPATIAL_PIXEL_PRESERVATION_VERIFIED` and **0 changed RGB pixels outside the reviewed mask**. The produced dial still looks **raised rather than visibly recessed**, so **geometry-edit fidelity is not accepted**. No CAP registration, Canon approval, or governed Attempt 2/2 consumption occurred. Preserve the existing experimental bundle. See the full evidence table and disposition in [VSCS User Manual](VSCS_User_Manual.md#f541b--first-real-isolated-mask-aware-gpu-qualification-evidence-2026-11-11).
