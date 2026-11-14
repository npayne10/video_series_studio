# VSCS — Operator Help and User Manual Index

**Version:** v0.3 (living documentation, updated 2026-11-14)  
**Source:** Current VSCS development branch; do not treat work-in-progress instructions as accepted production authority.

## Open first

1. [VSCS User Manual](VSCS_User_Manual.md) — project creation, Story, analysis, approved Story workflow, proposal/authority separation, CAP review, safety and acceptance steps.
2. [Automation Progress Audit](Automation_Progress_Audit.md) — which Story Automation buttons lack running feedback, safety constraints, remediation and Qt acceptance criteria.
3. [Production workflow architecture](../engineering/VSCS_Video_Production_Workflow_V2.md) — architecture/aspirational workflow for context; verify every action against the user manual and actual UI.
4. [B.5.22 disk-backed acceptance](../engineering/Phase_20_19_3B5_22_Disk_Backed_CAP_Persistence_Acceptance.md) — automated SQLite durability, governance and separate desktop operator acceptance.

## ROI selector silent-click diagnostic — 2026-11-14

The initial Windows UI test reported no visible action from **Select ROI on
Source Image (No Generation)**. The handler now catches unexpected Qt/Python
exceptions, displays an **ROI Selection Failed** message, and writes a traceback
to the application logger. This is a diagnostic fix, **not yet confirmed to
resolve the underlying runtime problem**. Pull the latest branch, restart VSCS,
reopen the existing saved review without a paid request, repeat the click and
capture the dialog or error. See [controlled troubleshooting](VSCS_User_Manual.md#f542-c2--interactive-source-image-roi-selection-implementation-candidate).
Stage C1/C2 acceptance must remain paused until the selector operates correctly.

## Interactive source-image ROI selection — F5.4.2 C2 (2026-11-14)

**Code implemented; Windows and UI acceptance pending.** The Stage B
normalized ROI field is now **read-only**. Press **Select ROI on Source Image
(No Generation)** to open a 100%-pixel-resolution, scrollable Candidate preview.
Drag the red rectangle around the actual defect, check the pixel and normalized
coordinates, then press **Apply Selected ROI (No Generation)**. This is an
uncommitted proposal until **Inspect Stage B Evidence / ROI (No Generation)**.
Cancel does nothing. The Candidate source hash is revalidated before display
and application. Pixel-edge conversion is made stable against floating point
rounding, avoiding an extra row or column in a later mask.

Use the [fully controlled VSCS-launch-to-ROI test](VSCS_User_Manual.md#f542-c2--interactive-source-image-roi-selection-implementation-candidate)
before accepting this change. The procedure includes the saved (non-billable)
AI review, exact sidebar and CAP gallery route, a cancellation negative test,
field isolation, screenshots and source/CAP/attempt non-mutation confirmation.
**The ROI selector cannot approve a mask or generate an image.**

## Saved Candidate AI review reuse — no repeat charge (2026-11-14)

**Implementation added; Windows/UI validation pending.** In **Canonical Profiles
→ Edit Selected → Canonical Reference Gallery**, select the existing reviewed
supplementary image Candidate and choose **Open Saved Candidate Review…**.
This new control opens the previously saved AI semantic-quality report and
F5.4.2 Stage B/C1/C2 review UI **without running OpenAI, rerunning CIEE,
consuming attempts or generating**. It checks the current source-image SHA,
CAP fingerprints, reviewed requirements and report metadata; stale or missing
reports fail closed. The AI result persists, while Stage B field findings and
C1 proposals remain in-memory per dialog session.

For complete preflight, **VSCS startup**, exact navigation, expected output,
negative tests, and non-mutation acceptance use
[Controlled UI test F5.4.2-SAVED-01](VSCS_User_Manual.md#f542--reopen-saved-candidate-review-without-repeating-paid-ai-analysis-new-workflow).
Never click **Review Visual Candidate… → Yes** merely to access the saved
review; that invokes an additional billable vision evaluation.

## Mandatory feature documentation and controlled UI acceptance (2026-11-14)

Every implemented functionality change must update **this index** and the
[VSCS User Manual](VSCS_User_Manual.md) on the same GitHub development
branch. In particular, C2 now has a complete numbered procedure starting
from the installed `vscs` startup command, through active project verification,
Canonical Profiles and the Candidate Quality dialog, Stage B/C1 review, mask
overlay, explicit operator confirmation, mask evidence save, duplicate-write
rejection and source/CAP/attempt non-mutation checks.

**Current phase:** F5.4.2 Stage A, B and C1 are accepted; **C2 is code
implemented but awaits operator UI acceptance**, with C3/C4 still gated.
Read the [F5.4.2 controlled launch-to-C2 procedure](VSCS_User_Manual.md#f542-stage-b-c1-and-c2--controlled-visual-correction-operator-guide-2026-11-14).
The C2 code is governed by [its detailed engineering contract](../F5_4_2_STAGE_C2_HUMAN_REVIEWED_MASK_EVIDENCE.md).

**Required shape of every future UI test:** branch and preflight → application
launch → confirm active project and Candidate identity → exact sidebar/menu
navigation → named controls and values → expected result after each action →
evidence capture → stop/abort rules → non-mutation audit → explicit operator
acceptance. Never infer a saved-report viewer from the existing button to start
a fresh potentially billable evaluation. If no safe path exists, stop and
document the missing control rather than asking for an unauthorized API call.

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

## F5.4.1C — Geometry-aware masked Qwen qualification

Following the first isolated masked Qwen GPU test, pixel preservation **passed** (zero outside-mask changed pixels), but the rotary dial remained visibly **raised**. F5.4.1C introduces a separately SHA-bound **recessed-dial geometry intent**, an external-only `run_003` preparation workflow, an operator-only dial context crop and independent measurements of changes **inside** the mask. The isolated Qwen GPU runner uses the new intent only after verifying its reviewed prompt, source/mask hashes and context provenance. Any in-mask change is **not** proof of a recessed dial; geometry acceptance still requires visual review. **Code committed; local static/pytest and new GPU tests pending.** The trusted graph, `run_002`, Candidate 4 and final governed Attempt 2/2 stay unchanged. See [F5.4.1C operator stages](VSCS_User_Manual.md#f541c--geometry-aware-masked-qwen-correction-isolated-qualification).


### F5.4.1C first isolated geometry-aware output — 2026-11-12

The `run_003` geometry-aware masked Qwen output **preserved all 1,039,784 outside-mask pixels** (0 changes) and changed **6,581/7,000 pixels inside** the mask (94.0143%). Visual review shows a recessed circular **well but no visible rotary dial within it**, so **complete geometry fidelity remains unaccepted**. Preserve `run_003`, its history and all CAP records; do not consume Candidate 4 final Attempt 2/2. See [F5.4.1C evidence and disposition](VSCS_User_Manual.md#f541c--first-real-geometry-aware-masked-gpu-output-2026-11-12).


### F5.4.1D reusable geometry correction (foundation)

The next stage is intentionally **generalised**, not another unlimited rotary-dial experiment. Following the F5.4.1C result (recess present, dial absent), the new offline `geometry_correction_policy.py` classifies that state as a `missing_component` defect and plans `reconstruct_component → verify_design`. It also defines reusable failure categories for merged objects, wrong count/placement/proportions/materials and unreviewed features; hashes reviewed source/mask evidence; requires outside-mask preservation and explicit review; and enforces **one** new disposable GPU trial in the plan. The planning module cannot authorize GPU execution, approve Canon, register a CAP Candidate or consume Attempt 2/2. **The generic policy is not yet connected to automated production or source-bound reconstructive inference.** See [F5.4.1D operator and engineering policy](VSCS_User_Manual.md#f541d--reusable-staged-visual-geometry-correction-policy-implementation-foundation).


### F5.4.1D final isolated reconstruction preparation (code committed)

The generic F5.4.1D policy passed **2,777 tests, 1 Windows symlink skip**, with clean Ruff/Mypy. The follow-on implementation creates **external `run_004`** directly from the verified output of completed F5.4.1C `run_003`, using a **smaller mask constrained to the prior cavity** and sealed `inset_dial_intent.json` / `geometry_repair_plan.json`. The one-shot isolated worker checks parent output and result SHA, mask/source hashes, generic defect classification (`missing_component`) and the one-trial limit, while leaving all CAP and earlier external evidence untouched. **This follow-on source-linked capability has not yet passed local regression or real GPU acceptance.** Do not execute GPU inference before the reviewed mask and separate readiness test. See [F5.4.1D one-shot run_004 operator procedure](VSCS_User_Manual.md#f541d--single-source-linked-inset-dial-reconstruction-experiment-implementation-validation-pending).


### F5.4.1D final trial disposition — 2026-11-12

The one permitted isolated `run_004` Qwen GPU reconstruction finished (353.14 seconds; prompt `a37e8035-b2e5-4e74-9858-2384a7bb8b88`) with **0 outside-mask pixels changed**. A previously absent rotary dial is now visible in the target cavity, but close review does **not** reliably confirm that its top lies below the shelf plane: the outer grooved rim still looks raised. **Partial component recovery, final geometry NOT accepted.** Machine semantic/geometry acceptance remains `null`. The agreed dial-specific GPU investigation is **closed**; no extra retry, CAP registration, Canon approval, or governed Attempt 2/2 release. Next focus is integration of the reusable defect-stage, mask-preservation and mandatory-feature review into general VSCS Candidate production. See [final F5.4.1D evidence](VSCS_User_Manual.md#f541d--final-isolated-source-linked-inset-dial-gpu-result-2026-11-12).


### F5.4.2 generalized Candidate visual correction — Stage A

The operator has **visually approved the final isolated F5.4.1D `run_004` illustration** as acceptable for the experiment. This is **human advisory visual acceptance**, not CAP registration, Canon/MASTER approval, semantic auto-pass or release of Candidate 4 Attempt 2/2. The dial-specific GPU trials are closed. F5.4.2 Stage A introduces `general_visual_correction_triage.py` plus **F5.4.2 Review General Visual Correction (No Generation)…** in the existing Candidate Quality Review UI. Every reviewed Draft CAP field appears as an **unverified mandatory visual check**; an operator can select an accepted field and defect category, describe the visible discrepancy and inspect the deterministic correction stage sequence, without a new API call or any generation/approval. The existing source-provenance and final-attempt guards remain unchanged. **Implementation committed; local Ruff/Mypy/pytest/UI acceptance pending.** Full automated pixel-to-defect attribution, mask suggestion and controlled corrected-Candidate generation remain later stages. See [F5.4.2 operator workflow](VSCS_User_Manual.md#f542--generalized-visual-correction-integration-stage-a-candidate-review-first-triage).

### F5.4.2 Stage A operator acceptance — 2026-11-12

Software validation **2,800 passed, 1 skipped**, Ruff/Mypy clean. UI screenshot confirms the Candidate review shows four reviewed fields as unverified, separates advisory semantic findings, and routes operator-selected `components` + `missing_component` to `reconstruct_component -> verify_design` with no generation action. **Stage A accepted** for visible workflow; no independent CAP non-mutation audit was supplied. Candidate 4's historic report remains distinct from visually approved external `run_004`. Candidate 4 governed final Attempt 2/2 remains protected. See [Stage A acceptance record](VSCS_User_Manual.md#f542-stage-a--operator-ui-acceptance-evidence-2026-11-12).
