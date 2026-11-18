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
