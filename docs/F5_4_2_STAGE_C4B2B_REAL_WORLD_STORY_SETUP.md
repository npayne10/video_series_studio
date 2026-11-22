# VSCS F5.4.2 C4B.2B — Real-World Disposable Story and CAP Qualification Route

**Status:** C4B.2B Ready 18-second Shot and 20-second planner limit operator-verified; targeted CAP source-context correction awaiting Windows acceptance; CAP pending; no GPU run  
**Date:** 2026-11-17  
**Branch:** `phase-f5.4.2-c4b2b-supervised-disposable-gpu-qualification`  
**Parent:** [C4B.2B supervised controller](F5_4_2_STAGE_C4B2B_SUPERVISED_GPU_QUALIFICATION.md)  
**Tracking:** [Issue #53](https://github.com/npayne10/video_series_studio/issues/53)

## 1. Operator decision and genuine-evidence requirement

Neill chose **Approach B: create a real, new VSCS Story → governed planning → reviewed Draft CAP → local visual Candidate → genuine saved AI evaluation → current reviewed C1/C2 mask → sealed external C4B.2A bundle**. This is deliberately slower and potentially billable, but qualifies the workflow with real production-style evidence. A deterministic synthetic asset would not substitute for this choice.

The new VSCS project `C4B2B_DISPOSABLE_GPU_01` was visually confirmed at `D:\VSCS\C4B2B_DISPOSABLE_GPU_01`. Operator PowerShell verified that its root is not a symlink/junction and that `.c4b2_disposable_project` contains the exact UTF-8 text `C4B2_DISPOSABLE_PROJECT\n` (24 bytes). The folder has the usual VSCS project directories and `project.vscs`. This is an operator-attested checkpoint, not an independent disk audit.

**Protected baseline:** The original `B5_22_DISPOSABLE_CAP_ACCEPTANCE_UI` Diagnostic Console Candidate 4, saved AI/C2.1 evidence, both historical masks and governed Attempt 2/2 remain untouched. Do not import or copy them into the new project. No CAP/Canon/MASTER/gallery promotion, protected correction, new provider run or paid evaluation is permitted by this decision alone.

**No fake prerequisites:** Do not manually invent accepted CAP values, a semantic failure, a C1 proposal or a C2 reviewed mask. Each must follow supported VSCS workflows and be genuinely reviewed. If the new Candidate passes its semantic checks, do not manufacture a failed report merely to reach the edit experiment.

## 2. Original Story input prepared in GitHub (DRAFT)

Source: [C4B2B_Real_World_Story_Source.txt](fixtures/C4B2B_Real_World_Story_Source.txt). It describes a freestanding graphite diagnostic console, one blue display, a shallow shelf with exactly three buttons and a rotary dial recessed below the shelf plane, ribbed sides, and a physically separate maintenance workstation. It is a single short inspection sequence (~18 seconds, subject to governed planning).

This file is **draft Story source**, not an approved CAP or governed production design. The operator must read it and verify it is suitable before importing.

## 3. Exact non-paid first operator stage — from VSCS closed

1. In PowerShell activate the existing VSCS virtual environment. Run:

   ```powershell
   cd D:\VSCS\video_series_studio
   git fetch origin
   git switch phase-f5.4.2-c4b2b-supervised-disposable-gpu-qualification
   git pull --ff-only origin phase-f5.4.2-c4b2b-supervised-disposable-gpu-qualification

   $from = "D:\VSCS\video_series_studio\docs\fixtures\C4B2B_Real_World_Story_Source.txt"
   $to = "D:\VSCS\C4B2B_DISPOSABLE_GPU_01\C4B2B_Real_World_Story_Source.txt"
   if (-not (Test-Path -LiteralPath $from -PathType Leaf)) { throw "STOP: Draft Story input missing" }
   if (Test-Path -LiteralPath $to) { throw "STOP: Target Story input already exists" }
   Copy-Item -LiteralPath $from -Destination $to -ErrorAction Stop
   Get-FileHash -LiteralPath $from -Algorithm SHA256
   Get-FileHash -LiteralPath $to -Algorithm SHA256
   ```

   The hashes must match. This creates only an original text source inside the **new disposable** project. It does not alter the VSCS project database or make an AI request.

2. Open the copied text file in a text viewer and confirm it accurately describes the intended diagnostic console and room. If you want to change the story, stop and discuss it before continuing so that the source and later Story-revision fingerprints remain clear.
3. Start VSCS using `vscs` from the same `(.venv)`.
4. On **Dashboard → Active Project**, verify exactly `C4B2B_DISPOSABLE_GPU_01` and `D:\VSCS\C4B2B_DISPOSABLE_GPU_01`. If another project is open, **STOP**.
5. Open **Story → Story Definition** (Story Workspace) and choose **New Story**.
6. Enter title `Blue Signal — Diagnostic Console Inspection`.
7. Enter a short description such as `Disposable C4B.2B real-world visual-correction qualification, one engineering console inspection scene; no production publishing.`
8. Set **Source type** to **Plain Text** and browse **Source path** to the copied file `D:\VSCS\C4B2B_DISPOSABLE_GPU_01\C4B2B_Real_World_Story_Source.txt`. Merely entering a description is insufficient; the Story must have a readable source file.
9. Complete the Story's available metadata using truthful operator-reviewed values. Suggested entries: author `VSCS Qualification`, synopsis `An automated camera inspects a freestanding diagnostic console and its recessed control dial in an empty survey-vessel engineering bay.`, genre `Science Fiction`, theme `Reliability and precision`, target audience `Adult`, language `English`. Adjust to the UI's actual fields; never fill unrelated mandatory fields with invented claims.
10. **Save** the new Story. Select it and verify that the displayed Story ID, title, source type/path, metadata and **Draft/Imported** status belong to this new project. Take a screenshot of the Story Definition state.
11. **STOP BEFORE `Analyse Story`.** It is a provider-backed action that may incur cost. Do not click `Analyse Story`, `Reanalyse`, Planning/Shot Proposals, AI CAP proposals, visual Candidate generation or semantic evaluation yet. Close the view normally if you wish; keep saved Story evidence.

Expected outcome: only a newly saved Draft Story in the separate project, with matching source-file hashes and no provider/network/GPU activity.

**If any UI field or path differs:** stop at that screen and report the actual label/screenshot. The navigation in steps 4–10 is documented in the VSCS User Manual, but this exact new-project-to-C4B.2B Story path still needs operator verification.

## 4. Later separately accepted gates (NOT INSTRUCTIONS TO EXECUTE NOW)

1. **Story Analysis:** one provider-backed call only after explicit cost authorization; review, save and approve the genuine analyzed Story. Reload cached results instead of repeating paid work.
2. **Planning and Shot authority:** Story → Automation → Planning Proposals → Review/Accept → Compile Accepted; then Shot Proposals and relevant accepted Shot bindings. Confirm persisted IDs in Story → Episode Planner and Scene/Shot planners; a generated proposal is not governed authority.
3. **Asset and CAP:** Canonical Profiles → Story → CAP Batch; Discover Shot Assets, inspect offline context/queue, use a current cached proposal where possible or seek separate paid proposal authorization. Review accepted/deferred fields and save a genuine Draft CAP. No fabricated geometry.

   **Issue #57 exception:** If every proposed physical field is rejected/deferred, preserve those deliberate human decisions as an *unresolved review-only audit*, **without** creating a fifth or placeholder CAP. Use the separate save confirmation and `Inspect Saved Detail Reviews (Offline)` to inspect/reopen the record; reuse the current cached proposal without paid generation if later authoritative evidence supports a corrected CAP. The physical inspection camera described as an offscreen viewpoint is governed by Camera Planning, not proof of `CAP-TEC-001` robot hardware.
4. **Local image Candidate:** Canonical Profiles → select new Draft CAP → Prepare Visual Identity (offline readiness). Only when Ready, separately confirm one local ComfyUI text-to-image Candidate. Keep its source image, asset/ref ID and generation digest.
5. **Genuine quality evaluation:** perform free technical check first; obtain independent approval before one possibly billable semantic evaluation. If no genuine failed field, stop rather than rewrite the result.
6. **C1/C2:** use saved failed review, select an accepted field and ROI on the new source, inspect white-edit/black-protect preview, save a human-reviewed **current** mask. Do not reuse historical masks or a protected source.
7. **Staging integration gap:** the existing `prepare_c4b2_disposable_bundle` accepts Python evidence objects but there is **no production UI/CLI that safely collects and stages this new project's current evidence**. Implement and Windows-test a fail-closed, non-generating operator-facing bridge only after actual new source and mask metadata are known. Do not invent a JSON workaround.
8. **Isolated live preflight:** stage into a separate external bundle, verify digests, Qwen model paths and selected model dropdown options, then show the read-only `--inspect` fingerprint. Independent model-file hashes and memory/offload compatibility remain pending.
9. **Supervised GPU:** require a fresh one-shot consent specific to that inspected fingerprint; one isolated 127.0.0.1:8298 request only. Save the result, external output, zero-protected-pixel audit, inside-mask change and human semantic review. No automatic Candidate registration or governed Attempt consumption.

## 5. Record for each checkpoint

Project path and name, Story ID/revision, original text hash, UI screenshot, Story status, any paid-provider authorization and result, generated proposal IDs and governed compiled IDs, CAP spec/accepted-field fingerprints, Candidate reference/image SHA, quality-report ID, current C1 proposal, current C2 mask SHA and evidence, exact external bundle root, run log/prompt ID, VRAM, timing, pixel counts, and final operator disposition. If a step fails or times out, stop before rerunning; assess whether an external provider request may already have been accepted.


## 6. C4B.2B operator evidence and targeted Shot-duration correction (2026-11-18)

The operator completed the original `Blue Signal — Diagnostic Console Inspection` Story `STORY-001`, approved it, approved five entity identities linked to existing XPD/CAP asset IDs, and compiled one Episode (`EP-001`), Scene (`EP-001-SC-001`) and Shot (`EP-001-SC-001-SHT-001`). Episode, Scene and Shot are **Ready at 0:18**. The independent Shot compilation popup reported **Shots 1 created, Ready promotions 1, Blockers 5**, with no final Production Approval/provider submission. All five Draft assets still need human CAP preparation; compilation's blockers are expected and are **not** duration errors.

The Shot Planner UI displayed a **15-second provider-neutral governed ceiling** despite the operator's valid 18-second Ready Shot. The AI Scene/Shot proposal service already enforces **15–20 seconds**. The targeted correction raises the governed planner's default **maximum** to **20 seconds**, preserves the provider-specific hardware/generation limits, and blocks promotion of an oversized Draft Shot to Ready. Semantic replanning at the default 20-second ceiling with source beats at least 15 seconds refuses decompositions that would yield pieces shorter than 15 seconds; it does not silently truncate or stretch approved runtime (e.g. 35 seconds → 18+17 is valid, whereas a 21-second beat cannot be auto-split within this window). Existing Ready Shot records are not migrated or rewritten. Existing legacy shorter Shots remain readable; this is not a blanket backdated minimum-duration rule.

**Windows verification recorded:** The operator subsequently observed the governed 20-second maximum with the same Ready 18-second Shot, and reported Ruff/Mypy success and **2,919 passed, 2 skipped** for the full Python regression suite (2026-11-18). The earlier commands remain reproducible checks after any new pull:

```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git switch phase-f5.4.2-c4b2b-supervised-disposable-gpu-qualification
git pull --ff-only origin phase-f5.4.2-c4b2b-supervised-disposable-gpu-qualification
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q tests/unit/test_governed_shot_planning_service.py tests/unit/test_governed_shot_planner_ui.py tests/unit/test_scene_shot_proposal_automation.py tests/unit/test_proposal_acceptance_orchestration.py
python -m pytest -q
git status --short
```

For read-only UI acceptance: restart VSCS, select exactly `C4B2B_DISPOSABLE_GPU_01`, navigate **Story → Episode Planner → Scene Planner… → Shot Planner…**, and verify the label now reads **maximum governed Shot 20s** and the same `EP-001-SC-001-SHT-001` is still **Ready, 0:18** within the approved 18-second Scene. Preserve the five unresolved-asset blockers until CAP governance is genuinely completed. **Do not click “Re-plan Scene from Story” or rerun paid proposal calls** for this source-only correction. Stop on any differing identity, duration, readiness or unexpected mutation.

This GitHub change does not authorize a new provider run, a GPU request, final Production Approval or CAP/MASTER promotion; the previously agreed billable qualification workflow and separate supervised GPU controls remain governed by their own checkpoints.


## 7. Targeted CAP provider-context correction — before first paid call (2026-11-18)

**Problem observed, no CAP charge incurred:** In `C4B2B_DISPOSABLE_GPU_01`, `Story → Canonical Profiles → CAP Batch…` discovered all five registered assets. The five Shot asset bindings remained Draft, correctly making their Shot evidence `unverified_shot`. Offline `Prepare CAP Context` for `CAP-PRP-002` initially contained only the short Story summary plus Shot actions/objectives; the paid CAP worker would have sent only the short summary to the provider. It omitted the original Story source's concrete console geometry and the Shot's own explicit constraints. An AI proposal could therefore miss the recessed dial, exact three-button arrangement, graphite ribs or independent workstation despite authoritative Story source text.

**Targeted GitHub change, awaiting fresh Windows verification:** CAP context preparation now incorporates the full approved Story source file (where configured) as `approved_story_context` with source provenance and cache fingerprint. A configured missing/unreadable file blocks generation. Governed Shot `shot_constraints` are forwarded with `verified_ready_shot` or `unverified_shot` provenance; Draft bindings cannot promote them to canon. The paid worker uses the prepared, immutable provider context, while canonical design expansion/grounding stays restricted to approved Story text. Cache keys now vary with the source bytes and Shot constraints; stale proposals cannot silently be replayed as current. No CAP is created or approved by context preparation. No provider requests were made while implementing this correction.

**Operator's next non-paid acceptance (do not click AI yet):**

1. Close VSCS, pull this development branch, and run Ruff lint, Ruff format check, Mypy and the focused CAP context/batch tests, then full pytest. Keep unrelated untracked files untouched.
2. Launch `vscs`, verify the active project is exactly `D:\VSCS\C4B2B_DISPOSABLE_GPU_01`, and open **Story → Canonical Profiles → CAP Batch…**.
3. Select `STORY-001 — Blue Signal — Diagnostic Console Inspection`; click **Discover Shot Assets** and select `CAP-PRP-002 — Diagnostic console`.
4. Click **Prepare CAP Context (Offline)**. Check the manifest contains `[approved_story_context] approved_story STORY-001.source_text` and the original source wording for **exactly three circular buttons**, **cobalt-blue display**, **outermost dial surface below the surrounding shelf plane**, **vertical ribbed grip panels**, **separate maintenance workstation** and **no extra controls**. The Shot `shot_constraints` should appear as `[unverified_shot]` while bindings are Draft, and the warning must remain truthful. The context fingerprint should differ from the former `b3a6f5a2a11320a244fe5036c5c95732e8cdd0ea061da3958fead4469a420536`.
5. Use **Review Cached Proposal** to check for an eligible current cache (it never incurs an AI charge). If missing, stop and report the offline manifest screenshot and test results for review before the **first explicit paid CAP generation**. Do not rerun Story Analysis, Episode/Scene or Shot proposals.

After these checks, request separate one-asset provider consent and review the paid confirmation. Accepting a provider proposal will still not create Canon/MASTER authority. Preserve all existing project artifacts, asset bindings and protected Candidate 4.


## 8. Resizable CAP context viewer — targeted UI-only correction (2026-11-18)

**Operator finding:** On `STORY-001` and `CAP-PRP-002`, the offline CAP manifest correctly displayed the full approved Story source (three circular buttons, cobalt-blue display, recessed dial, ribbed housing, separate workstation and no additional controls), with the Shot's detailed constraints explicitly labelled `unverified_shot`. The new fingerprint differed from the previous context. Ruff, formatting and Mypy passed on Windows; the focused regression reported 16 passing tests, and the full regression reported **2,924 passed, 2 skipped**. No CAP/Canon was changed and no paid CAP generation occurred. However, the long-text `QMessageBox.information()` popup could not be resized at its edges and was awkward to inspect.

**Targeted GitHub update; Windows UI acceptance pending:** Replace only the long-text modal information popup with a dedicated resizable `CAPContextInspectionDialog`. Default size is 1,000 × 700; minimum size is 650 × 400, with a window size grip, scrollable read-only plain text, **Copy Context** and **Close**. The underlying CAP Batch summary still receives the identical text. No source fingerprints, providers, governed assets, CAP proposals, approvals or storage behaviour are changed by this UI fix. Tests verify dialog dimensions, read-only presentation, exact clipboard content via a fake clipboard, and that the original offline button opens this dialog rather than a fixed message box.

**Non-paid operator acceptance:** After pulling and running Ruff, format, Mypy and tests, restart VSCS; verify the active project is `D:\VSCS\C4B2B_DISPOSABLE_GPU_01`. Open **Story → Canonical Profiles → CAP Batch…**, select `STORY-001`, **Discover Shot Assets**, select `CAP-PRP-002`, and click **Prepare CAP Context (Offline)**. Verify the new window can be resized both wider/narrower and taller/shorter by dragging its edges/corners, its text scrolls and remains read-only, and **Copy Context** yields the complete fingerprint, approved source and `unverified_shot` warning when pasted into a disposable text viewer. Close the dialog, verify the same text remains in the CAP Batch summary and the active project remains unchanged. Do not click **Generate / Regenerate Using AI (Paid)**, repeat earlier proposal calls or start GPU execution during this UI test; provider authorization is a separate gate.

## 9. P0-A camera viewpoint versus physical asset — Issue #56 (Windows UI accepted 2026-11-21)

**Observed real-world fault:** The Shot's cinematic moving camera viewpoint caused `CAP-TEC-001` to be interpreted as an on-screen self-propelled robot, inventing a body, wheels, bumper and drive motors. `STORY-001`'s actual 18-second interior Shot requires the console, workstation and engineering-bay setting, but the camera perspective need not become a visible technology asset. The enclosing `CAP-SHP-001` survey vessel similarly need not have an invented exterior silhouette in this interior Shot.

**Code correction:** The Shot Asset Resolver now shows deterministic source-grounded *visibility suggestions*, with an explicit **Review Visibility…** dialog and Operator confirmation. It persists the human classification and an append-only review history with evidence, timestamps, Shot/Scene fingerprints and reviewer. The reviewed `camera_viewpoint` and separately reviewed `setting_context` bindings remain in the original five-row set, but are excluded from visible-asset CAP/reference readiness **only while their source Shot is current**. A visible robot or exterior vessel stays a real physical requirement. Reviewed camera motion appears in **Draft Camera Planning**. An AI inference provider is additionally instructed not to invent diegetic camera hardware from camera-movement verbs; this change never invokes that provider. Downstream integration preserves nonvisual bindings as audit records rather than canonical image assets.

**Real-world operator acceptance (2026-11-21):** In the unchanged Ready 18-second `Automated Console Inspection` Shot, Neill reviewed `CAP-TEC-001` as offscreen camera viewpoint and `CAP-SHP-001` as enclosing setting context. All five original bindings remained, with Asset Resolver reporting **5 declared, 0 production-ready, 3 unresolved, 2 reviewed nonvisual**. The saved camera review changed the `asset_resolutions.json` SHA-256 from `8B25AAC216172DF75DCA44474F58B731A79E453627AFC1F7C3A1E21127E9700B` to `6B817C6E6F5FED01E093AEA5EB7F0FC5E27C61BD69DDC04DEFBF74A90B828411`; the second value is only the intermediate post-camera-review checksum, **not** the final checksum after the ship review. The new governed **Draft Camera Plan** showed **Push In** with the source-grounded human viewpoint evidence. After a full application restart, both human classifications and their saved audit histories persisted. Windows validation: global Ruff lint and formatting clean, Mypy clean (715 files), **2,937 passed, 2 skipped** (symlink privileges). No CAP/MASTER authority, historical Candidate 4, or production/video generation was changed or approved by these reviews.

**Non-paid Windows QA after merging/pulling #56:**

```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git switch phase-f5.4.2-c4b2b-supervised-disposable-gpu-qualification
git pull --ff-only origin phase-f5.4.2-c4b2b-supervised-disposable-gpu-qualification
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q tests/unit/test_governed_asset_resolution_service.py tests/unit/test_governed_asset_resolver_ui.py tests/unit/test_governed_camera_planning_service.py tests/unit/test_governed_planning_integration_service.py
python -m pytest -q
git status --short
```

1. Restart VSCS and verify the active project is **exactly** `D:\VSCS\C4B2B_DISPOSABLE_GPU_01`. Open `EP-001-SC-001-SHT-001` in Shot Planner and then **Asset Resolver…**. Confirm there are five existing Draft/Partial requirements; record the current `asset_resolutions.json` file hash and the visible table before changing anything.
2. Click **Analyze Requirements** and verify `CAP-TEC-001` has a source-grounded **camera_viewpoint** suggestion. Do not click any paid regeneration. Review the current Shot action: it must describe moving camera *viewpoint*, not a visible self-moving robot. If the suggestion does not fit the actual governed Shot, **STOP** and report its displayed evidence; do not force an exemption.
3. Select existing `CAP-TEC-001`, click **Review Visibility…**, inspect source evidence, select **Offscreen camera viewpoint — Camera Planning**, confirm explicitly, save. Observe **Viewpoint-only (reviewed)** / **Visibility Reviewed**; the record is still Draft with the same binding ID and CAP-TEC asset association. This is not approval of the robot or its CAP. Confirm the other four bindings still exist and their Draft/Partial readiness has not been promoted.
4. Inspect `CAP-SHP-001`. If its setting text establishes **only** the vessel carrying the interior engineering bay, review it as **Enclosing setting context** with its own evidence and confirmation. Stop if the Shot calls for a visible exterior hull. Do **not** classify `CAP-LOC-001`, `CAP-PRP-001`, or `CAP-PRP-002` as nonvisual to bypass their genuine readiness blockers.
5. Enter Camera Planning for the same Shot and inspect the draft movement suggestion. An advancing viewpoint should propose a **push-in** and retain the reviewed Shot evidence; it must not generate a camera robot or mark the Camera Plan Ready. Confirm the physical CAP/reference blockers remain for the genuinely visible assets and no Production Approval, MASTER lock, Candidate approval or video generation has occurred.
6. Save a screenshot of the reviewed bindings and the draft Camera Plan suggestion plus the QA terminal transcript. If an upstream Shot is edited later, the previous visibility review must show stale and stop contributing to readiness until explicitly refreshed and reviewed again. **Do not edit the Ready Shot solely to exercise that test in the real project**; stale/visible-robot regression coverage belongs to automated fixtures.

**No-go boundary:** Do not create/approve canonical references or publish video merely because #56 is merged. Continue the outstanding CAP/MASTER/canonical and production-planning backlog under separate user-authorized steps. No provider billable call or GPU execution is part of this fix.

## 10. P0-C Story-grounded CAP field normalization — Issue #54 (Windows acceptance pending)

**Observed problem:** Approved `STORY-001.source_text` already specifies the Diagnostic Console's physical material, display, three-button layout, recessed rotary dial and ribbed grips. Earlier cached AI output bundled physical facts under `geometry`, left required `materials` and `components` to manual transcription, or suggested invented numerical scale. A first-pass Location proposal similarly lacked separate grounded `layout` and `lighting`. Ship dimensions and workstation geometry must never be inferred from nearby objects or the enclosed bay. Unverified or verified *Shot* descriptions can give context but are not approved Story authority for a permanent CAP design.

**Change under review:** A local, deterministic reconciliation step reads `approved_story_context` sources only, identifies missing required fields with asset-scoped verbatim excerpts, and labels each field with origin, Story ID/field/SHA and current context fingerprint. Existing provider content and cached human edits are preserved. AI alternatives and Shot-only evidence remain separately labelled; unsupported scale and containing-vessel dimensions cause advisory quality warnings. The detail review shows attribution and offers an *explicit, non-persisting* button to preselect supported Story-source fields while leaving AI-only/unresolved values deferred. Operators retain field-by-field Accept/Edit/Reject/Defer authority and separate final save confirmation; all-Defer/Reject remains an immutable review-only outcome under Issue #57. No new provider request, CAP, image, reference or Production Approval is initiated by reconciliation.

**Windows baseline already confirmed (before the existing-Draft extension):** Neill reported Ruff and format clean (1,715 files), Mypy clean (717 files), **23 targeted passed**, and **2,960 full regression passed with two expected symlink skips**. The initial UI instructions incorrectly selected `CAP-PRP-002` in the *new-CAP* dropdown. The screenshot proved the asset has an **existing reviewed Draft CAP** and is correctly present in the *lower* Existing Draft CAPs selector. The extension below adds an offline Story-source option to the separate, already-governed single deferred/rejected field revision. It preserves previously accepted fields and requires an explicit operator reason, save confirmation, refreshed source check and Draft compare-and-swap. It makes no paid request or CAP mutation just by inspecting the candidate.

**Safe Windows non-paid test sequence (do not skip the initial hashes):**

1. Close VSCS, check for unrelated working edits, then fetch and update the Issue #54 branch or reviewed PR test commit. Run Ruff lint and format, Mypy and `python -m pytest -q tests/test_issue_54_story_grounded_cap_fields.py tests/test_issue_54_existing_draft_story_integration.py tests/test_cap_existing_draft_revision.py tests/test_cap_existing_draft_revision_dialog.py tests/test_issue_57_unresolved_cap_review.py`, followed by full `python -m pytest -q`. Two existing Windows symlink privilege skips are expected; other skips/failures must be investigated. Record branch, commit, counts and the active project path.
2. In PowerShell, capture the current planning asset-bindings hash *before launching the UI*:

   ```powershell
   $assetFile = 'D:\VSCS\C4B2B_DISPOSABLE_GPU_01\planning\asset_resolutions.json'
   $beforeHash = (Get-FileHash -LiteralPath $assetFile -Algorithm SHA256).Hash
   Write-Host "Asset bindings before: $beforeHash"
   ```

3. Start VSCS with **exactly** `D:\VSCS\C4B2B_DISPOSABLE_GPU_01` active. Verify `STORY-001` remains Approved and `EP-001-SC-001-SHT-001` remains Ready, 0:18, without modifying either. The Asset Resolver must retain all five original bindings, the two reviewed nonvisual classifications, and exactly three physical Draft/Partial requirements. Do not edit/resave them for this test.
4. Open **Canonical Profiles → Story → CAP Batch…** and click **Discover Shot Assets**. `CAP-PRP-002` is **not** selectable in the upper dropdown: that list is only for assets missing a CAP. Instead select **Diagnostic console — CAP-PRP-002** in the lower **Existing Draft CAPs** dropdown and click **Edit Existing Draft CAP…**. If the editor reports stale Story/context or non-Draft status, **STOP**; do not recreate or replace the CAP.
5. In **Edit Existing Draft CAP**, confirm earlier Accepted/Edited fields are displayed in the **read-only** panel and are not offered for revision. Select `materials` if it remains Deferred/Rejected (otherwise inspect `components` if eligible). Click **Review Approved Story Field Suggestion (Offline — No AI Charge)**. The proposed value must be read-only, cite `STORY-001.source_text` with SHA/context fingerprint and retain the Story's **matte graphite-coated metal** for materials, or **cobalt-blue display, three circular buttons, recessed dial below the shelf and ribbed grips** for components. `scale` must not obtain invented metres from the Story. If there is no supported candidate, report it; do **not** click **Generate / Regenerate Field Proposal (AI — Paid)** to force one.
6. For the *non-persistence* UI test, verify that merely loading the Story suggestion does **not** save or approve it. A source-backed save requires a separate **Operator Story-source review reason** followed by **Save Reviewed Draft Revision** and another confirmation. **Do not submit those controls in this first test.** Click **Cancel**, reopen the existing Draft editor and confirm the same original Accepted/Deferred/Rejected decisions are present. To inspect a second eligible field, select it and repeat. Switching fields must discard the prior candidate and its typed reason. Screenshot the field source SHA, approved quotation, prior locked fields and unchanged Draft status.
7. If another previously reviewed Draft asset has eligible Deferred/Rejected source-backed fields, the same offline inspection is available, but **do not** create duplicate CAPs just to exercise it. For the bay, only Story-supported layout and diffuse overhead utility lighting may be suggested; not invented room dimensions, wall material, service chase or doorway. The vessel's interior bay dimensions must not become ship dimensions. If no such eligible Draft field exists, record *not exercised*, not failed. Do not change reviewed nonvisual Shot classifications or production-plan records.
8. Close VSCS and rehash the asset bindings:

   ```powershell
   $afterHash = (Get-FileHash -LiteralPath $assetFile -Algorithm SHA256).Hash
   Write-Host "Asset bindings after:  $afterHash"
   if ($beforeHash -eq $afterHash) { Write-Host 'PASS: no asset-binding mutation' -ForegroundColor Green } else { Write-Host 'FAIL: asset bindings changed; STOP' -ForegroundColor Red }
   ```

9. Verify there was **no CAP specification or review-audit mutation** from loading/cancelling the existing Draft offline suggestion, and no new CAP, reference, MASTER or production execution. The offline existing-Draft inspection does not even write the proposal cache. Capture source/field screenshots, before/after hashes, focused/full test output, and report whether the candidate was offered and accurately grounded. **Do not approve/canonize candidates merely to complete the test.** A subsequent deliberate one-field Draft save is a separate operator-authorised test with an explicit recorded reason and new audit-history entry.

**Stop criteria:** Unexpected source label/SHA; stale Story/Shot; console inheriting workstation hardware; bay inheriting console materials; ship inheriting interior dimensions; invented scale silently accepted; implicit Accept/Canon/MASTER; mutated `asset_resolutions.json`; any provider charge. The operator should report these before proceeding to final Draft CAP review, canonical Candidate creation or Production Planning.
