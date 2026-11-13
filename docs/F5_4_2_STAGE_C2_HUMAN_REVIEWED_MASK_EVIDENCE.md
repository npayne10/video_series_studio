# VSCS Phase F5.4.2 — Stage C2: Human-Reviewed Mask Evidence

**Status: C2 IMPLEMENTATION CANDIDATE — NOT ACCEPTED.** Based on the
operator-accepted C1 commit `9d91587`. No GPU, ComfyUI, API requests, Candidate
registration, CAP/Canon promotion, or attempt-counter mutations are authorized.

## Engineering contract

1. C2 accepts only a successfully sealed Stage C1 `GovernedCorrectionProposal`.
2. The local source image must be an existing canonical Visual Candidate PNG
   directly under `Canonical Assets/<asset_id>/Images/Visual Candidates`.
   The complete source bytes must match the C1 SHA-256.
3. Preview uses the source dimensions and rasterizes normalized ROI by
   `floor(left/top)` and `ceil(right/bottom)` with exclusive right/bottom
   bounds. Operators MUST inspect the actual image with the red overlay.
   **The Stage B example `0.1,0.2,0.3,0.4` is not a verified correction area.**
4. Mask is 8-bit grayscale PNG, exactly source dimensions. **White (255)**
   marks proposed editable pixels inside the reviewed rectangle; **black (0)**
   marks protected pixels outside it. No soft edge or automatic dilation.
5. Preview and confirmation are separate operations. A preview must not claim
   approval. Confirmation permits only construction of immutable, source-bound
   mask evidence in memory.
6. Mask inspection checks the source and proposal identity, PNG mode/size,
   mask digest, pixel area and EVERY mask pixel against the reviewed bounds.
7. An explicit Save action writes only a new `c2-...`.png evidence file under
   the asset's `.metadata/spatial_masks` directory. It uses exclusive create;
   no overwrites, auto-imports, candidate-image edits or CAP/attempt writes.
   The metadata parent must already be canonical and non-symlink.
8. **A C2 evidence mask is not a validated provider input or a proof of
   protected-pixel preservation.** These require the separate C3/C4 gates.
9. Candidate 4's historical final Attempt 2/2 stays protected. No dial-specific
   GPU experiments are reopened.

## Stage C1 user-interface correction included

The reviewed CAP field dropdown now restores the selected field's operator
status, observed evidence, defect and ROI from the in-memory review. A
`X of Y fields reviewed` indicator makes the operation visible. An active
C1 proposal is invalidated whenever Stage B evidence is changed.

## Operator acceptance procedure

1. Open an existing saved semantic quality review; do not rerun paid analysis.
2. Review accepted fields in Stage B; leave real failures as FAILED.
3. Inspect the Stage C1 governed handoff (No Generation).
4. Click **Preview Stage C2 Editable Region (No Generation)** and compare the
   red overlay against the actual source image. Wrong ROI? Revisit Stage B and
   enter the correct normalized coordinates. The proposal must be reissued.
5. Check **I reviewed the mask preview against the source image** only after
   inspection. Click **Inspect C2 Mask Evidence (No Generation)**.
6. Verify source size, pixel bounds, editable pixel count, mask SHA-256, and
   explicit non-execution notice. Only after approval of that preview, click
   **Save C2 Mask Evidence (No Generation)** if you intend to retain the mask.
7. Confirm the new mask file exists in `.metadata/spatial_masks` with the
   recorded hash. Attempt a duplicate save: it must refuse to overwrite.
8. Verify source Candidate bytes, semantic report, CAP authority, gallery
   registration, Canon/MASTER and governed attempts are unchanged.
9. Confirm the saved mask has not been queued to ComfyUI and is not marked
   as a provider-validated mask.

**Important UI note:** The mask preview is a red overlay on the original source
image; the stored grayscale mask uses white for the same proposed editable
pixels. There is no provider generation, even when Save is clicked.

## Windows validation

```powershell
cd D:\VSCS\video_series_studio
git status --short
git fetch origin
git switch phase-f5.4.2-stage-c2-human-reviewed-mask-evidence
git pull --ff-only origin phase-f5.4.2-stage-c2-human-reviewed-mask-evidence
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q tests/test_cap_human_reviewed_mask_evidence.py tests/test_cap_governed_visual_correction_handoff.py tests/test_cap_spatial_visual_evidence.py tests/test_cap_general_visual_correction_triage.py tests/test_cap_geometry_correction_policy.py tests/test_cap_visual_candidate_regeneration.py
python -m pytest -q
git diff --check
git status --short
```

Pending: Windows lint/format/Mypy, focused and full regression, UI screenshot
of mask overlay and evidence hash, exclusive-write verification, Candidate/CAP
non-mutation check and explicit operator acceptance. Only then close C2.
