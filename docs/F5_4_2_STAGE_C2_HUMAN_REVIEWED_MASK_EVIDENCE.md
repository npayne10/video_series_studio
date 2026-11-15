# VSCS Phase F5.4.2 — Stage C2: Human-Reviewed Mask Evidence

**Status: STAGE C2 OPERATOR ACCEPTED — 2026-11-15.** Includes the
interactive full-resolution ROI selector and exclusive source-bound mask evidence.
Based on operator-accepted C1 commit `9d91587`. Acceptance is for
non-executable evidence handling only: no GPU, ComfyUI, API requests, Candidate
registration, CAP/Canon promotion, or attempt-counter mutations are authorized.

## Formal operator acceptance record — 2026-11-15

**Decision:** Stage C2 human-reviewed mask evidence and interactive source
ROI selector **accepted** on the basis of operator screenshots, saved-file
hash checks, exclusive-write rejection and the operator's explicit
non-mutation confirmation.

**Automation and static results previously reported (Windows):**
Ruff lint passed; Mypy passed on 709 source files; focused ROI suite
12 passed; full regression 2,848 passed, 1 skipped (Windows directory
symlink). The final Ruff formatting-only commit `50f46b2` was made
subsequently; a separate post-formatting static output has not been
supplied. Do not misrepresent the earlier results as a new run.

**Controlled UI evidence:**
- The saved Candidate 4 technical/semantic report was reopened without a
  repeated paid evaluation. Four accepted CAP fields were reviewed
  independently, with `components` FAILED and the other three
  operator-verified in the test session.
- The operator selected the `protruding_instead_of_recessed` rotary dial
  on the original 1392 x 752 PNG using the interactive, scrollable
  pixel-resolution selector. The selector displayed a red rectangle,
  precise integer bounds, normalized coordinates and a separate Apply
  action; Stage B retained and displayed the returned ROI.
- Stage C1 produced a sealed, non-executable correction proposal for
  `components`. Stage C2 preview reproduced the red editable area on
  the source image; the operator acknowledged the mask preview.
- Initial saved mask: bounds `(900,342,993,402)`, 5,580 editable
  pixels, SHA-256
  `19564b7fe1531d9e803f3ac34d3c239cdb80b24c909da22c6bba9ddcc2af986f`.
  Operator's PowerShell SHA-256 matched the in-memory digest.
- After a session interruption the user explicitly repeated the Stage
  B/C1/C2 review and redrew a slightly different rectangle. Second
  saved mask: bounds `(898,345,993,400)`, 5,225 editable pixels,
  SHA-256
  `1aa336f61f107ffe58d8331ea89caa6b60ee48ef11c15ea1bbe7d7dfa4dedd15`.
  Operator's PowerShell SHA-256 matched the in-memory digest.
- The operator attempted to save the **second mask again**. VSCS displayed
  `Stage C2 Save Blocked: Mask evidence already exists; never overwrite`.
  This proves the **same-artifact exclusive-write** guard, not
  deduplication of geometrically distinct masks. Both mask evidence
  files intentionally remain preserved; no deletion or implicit replacement.
- On 2026-11-15 the operator **explicitly confirmed** that neither
  session changed Candidate 4, its saved AI evaluation, accepted CAP
  requirements or authority, Canon/MASTER, any production image or
  Candidate registration, or the governed attempt counter. This is
  operator-confirmed non-mutation; it is not presented as an independent
  filesystem audit.

**Outstanding feature improvement, not a C2 blocker:** The paid AI
quality report is persisted, but Stage B/C1 human review and ROI context
are still session-local. On interruption the operator must review fields
and redraw the ROI; different reviewed regions can legitimately create
different evidence PNGs. Before advancing to provider execution, design
governed, source-hash-bound review-session persistence, resumption and
mask-version selection. Do not silently auto-select the newest mask.

**Authority boundary:** The PNG is a proposed editable-area evidence
artifact, **not** proof that a model supports masks or that protected
pixels stay intact after editing. C3 provider mask compatibility and
C4 controlled correction/registration require distinct validations and
explicit approvals. Candidate 4's protected governed final Attempt 2/2
remains unconsumed.

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
4. Use **Select ROI on Source Image (No Generation)** in Stage B to draw
   the correction area at native image resolution, then click
   **Apply Selected ROI (No Generation)** and **Inspect Stage B Evidence / ROI
   (No Generation)**. Next, complete the C1 handoff and click
   **Preview Stage C2 Editable Region (No Generation)** to compare the
   source-bound red overlay. If the ROI is wrong, redraw and reissue
   the proposal; do not hand-enter arbitrary normalized coordinates.
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
git switch phase-f5.4.2-c2-interactive-roi-selection
git pull --ff-only origin phase-f5.4.2-c2-interactive-roi-selection
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q tests/test_cap_human_reviewed_mask_evidence.py tests/test_cap_governed_visual_correction_handoff.py tests/test_cap_spatial_visual_evidence.py tests/test_cap_general_visual_correction_triage.py tests/test_cap_geometry_correction_policy.py tests/test_cap_visual_candidate_regeneration.py
python -m pytest -q
git diff --check
git status --short
```

Stage C2 was accepted by the operator on 2026-11-15 with the evidence
listed above. Recheck static formatting after the final code-only
formatting commit if required by the release process. All C3/C4
generation, mask-provider validation and Canon/MASTER gates remain closed.
