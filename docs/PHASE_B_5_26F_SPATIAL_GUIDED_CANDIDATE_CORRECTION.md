# Phase B.5.26F — Spatially Guided Visual Candidate Correction

Status: **Increment F1 committed, Windows validation pending.** No guided generation has been authorized or executed.

## Baseline and reason for change

On disposable asset `STORY-LOC-A9ED8B387E`, Candidate 2 (attempt 1/2) scored
technical 79 versus 82, semantic 58 versus 72, and consistency 45 versus 45.
It visibly repeated the extra-door constraint violation and introduced drafting
annotations. Phase B.5.26E improved prompt instructions and made regression warnings
visible; the operator verified the read-only prompt/confirmation and was asked
to cancel before the final local generation attempt.

## Repository inspection

Current `XCICImageProvider` config selects the shared
`xcic.qwen.text-to-image` workflow, not a validated image-edit model.
The checked-in `workflows/Xorix_Qwen_XCIC_Image_Creator_v1.0_api.json`
contains `EmptySD3LatentImage`, `KSampler`, queue loader, Qwen text encoders
and PNG output. It provides no evidenced source-image editing, mask,
ControlNet/depth/layout or post-edit quality guarantee.

The XCIC Core queue `XCICCoreJob` contains an optional reference path, but
that alone is **not** evidence that the workflow consumes a reference image.
The render path compiles and submits a loader-based workflow. Existing
provider provenance validates prompts, seeds and outputs, not editable regions.

## Increment F1: implemented

- Add `inspect_spatial_guidance`: a **local file-only**, no-network inventory
  of the configured XCIC API workflow. Report missing/unreadable workflows,
  malformed nodes, loader count, indicative source-image nodes, mask nodes
  and spatial control nodes.
- Deliberately report `guided_execution_verified = False` for *every*
  inspected workflow. Matching node names do not establish connected graph
  paths, correct model, actual source-image preservation, VRAM compatibility,
  or provenance integrity. Never use this inventory to authorize rendering.
- Add **Inspect Spatial Guidance (No Generation)** to the existing Candidate
  correction dialog. The button displays the offline report only, leaving
  the current generation and governance paths unchanged.
- Add unit and Qt UI regression tests for missing input, text-only workflow,
  presence of tentative control nodes, malformed UI graph, and no-generation
  inspection actions.

## Required next gates before a guided rendering option is exposed

1. **F2 capability & hardware audit:** on Windows, obtain local workflow
   exports and installed ComfyUI node/model inventory. Validate the intended
   edit-capable model and mask/layout conditioning path on RTX 5060 Ti 16 GB.
   Read-only inspection must not call `POST /prompt`.
2. **F3 governed spatial correction contract:** select source Candidate and
   immutable SHA256; approved CAP-only spatial constraints; separately
   reviewed editable region/mask and hash; workflow/model version and hash;
   operator preview; bounded attempt policy. Reject untrusted or changed
   image/mask paths and cross-project resources.
3. **F4 opt-in integration:** only after F2–F3, add a distinct guided-image-edit
   provider execution path with explicit consent. Do not silently reinterpret
   a text-to-image invocation as editing, replace the XCIC backend, or
   automatically promote a newly generated Candidate.
4. **F5 acceptance:** deterministic mocked end-to-end tests and a **single
   explicitly authorized** disposable local edit, with image quality review
   and evidence of preserving approved elements.

## Safety / non-goals for F1

No ComfyUI API call, image regeneration, paid OpenAI evaluation, filesystem
writes, asset/reference promotion, retry increment, model download or data
migration. F1 does not make spatial correction executable or validated.
The original two candidates and all recorded audits stay unchanged.

## Windows validation commands

```powershell
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q tests/test_cap_spatial_candidate_guidance.py tests/test_cap_visual_candidate_regeneration.py tests/test_cap_visual_candidate_quality.py
python -m pytest -q
git diff --check
git status --short
```

## Operator test (no generation)

1. Restart VSCS and open `B5_22_DISPOSABLE_CAP_ACCEPTANCE_UI`.
2. Open the gallery and select Candidate 2; click **Correct From Saved Review…**.
3. Click **Inspect Spatial Guidance (No Generation)** in the correction dialog.
4. Verify that the report displays the resolved local workflow path and
   explicitly states `Guided execution verified: NO`. Capture the report.
5. Close the inspection and then cancel the correction dialog. Do **not** press
   **Generate ONE Corrected Local Candidate**. Confirm no ComfyUI job was queued
   and that attempt 2/2 remains available.

GitHub source and the operator's Windows validation results are separate
acceptance gates. Complete F1 only after all regression and UI checks pass.
