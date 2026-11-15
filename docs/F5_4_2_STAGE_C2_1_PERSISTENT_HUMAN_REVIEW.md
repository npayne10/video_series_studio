# F5.4.2 Stage C2.1 — Persistent Human-Review Sessions

**Status: IMPLEMENTATION CANDIDATE — Windows regression and operator acceptance required.**

Stage C2 was operator accepted on 2026-11-15. This phase adds explicit
immutable session Save/Resume and inspection-only mask-version discovery.
It does not authorize generation, import a mask into ComfyUI, register
Candidates, consume governed attempts, change CAP requirements, or
promote Canon/MASTER.

## Persistence boundaries

- **Save Human Review Session (No Generation)** creates one new
  `c21-<reference_id>-<uuid>.json` under
  `Canonical Assets/<asset_id>/.metadata/human_visual_reviews`.
  It does **not** overwrite a prior human review, Candidate image, SIEE
  report or mask. Stage B fields must first be committed with
  **Inspect Stage B Evidence / ROI**.
- JSON contains source Candidate SHA-256, asset/reference identity,
  reference role/status, specification and reviewed CAP fingerprints,
  every field status and observation, typed defect, normalized ROI,
  optional exact C1 proposal SHA-256, saved UTC and an explicit
  non-authority marker. It has a deterministic content SHA-256 seal.
  **The seal detects accidental alteration; it is not a cryptographic
  signature authenticated by a separate trusted key.**
- The Candidate PNG is rehashed on save and resume. Stored CAP
  fields/requirements and source identity must still match the
  latest **reopened saved quality review**. Each recorded field is
  replayed through the existing Stage B validation contract.
  Stale source/CAP records, invalid fields, malformed JSON,
  unsafe paths, altered seals and unauthorized approval flags block.
- **Resume Selected Human Review (No Generation)** requires explicit
  selection of a saved version. Nothing is automatically applied.
  It restores the field statuses, observations, defect, and ROI,
  and restores the C1 digest as **provenance only**. ROI review, C1
  proposal authority and C2 mask-preview acknowledgements all reset.
  To issue a new C1 proposal the operator must re-confirm the ROI;
  if the saved C1 digest no longer matches, the C1 handoff blocks
  until a new Stage B review has been explicitly made.
- **Save is manual.** The Save action blocks if current editor values
  differ from last inspected Stage B evidence. Use **Inspect Stage B
  Evidence / ROI** before saving. Normal Close, window X and Escape
  display an unsaved-changes confirmation and allow the operator to
  cancel closing. To preserve work, save and confirm the immutable
  session receipt first. Forced termination, crash or power loss can
  still discard unsaved work.
- **Existing C2 mask version discovery** is available after inspecting
  a fresh C1 proposal. Every version is hash-checked, verified as a
  same-size binary grayscale PNG and shown with either `CURRENT`
  (byte-for-byte matches the current source-bound C1 proposal) or
  `HISTORICAL` (not authenticated for the current ROI/proposal).
  Nothing is automatically chosen. Choosing a mask only displays
  provenance and digest; it does not grant model/provider access or
  overwrite an existing mask.

## Controlled UI acceptance: F5.4.2-C2.1-UI-01

1. Close VSCS. In the existing Windows VSCS checkout, activate the
   existing `.venv`, ensure there are no unexpected tracked edits,
   fetch and switch to
   `phase-f5.4.2-c2.1-persistent-human-review`. Keep the
   two known unrelated untracked audit/preflight files untouched.
2. Run Ruff lint, Ruff formatting, Mypy and the focused C2.1/C2/B/C1
   pytest regressions, then the full suite. Stop if anything fails.
3. From `D:\VSCS\video_series_studio` with `(.venv)` active,
   run `vscs`. Confirm **Dashboard → Active Project** points to
   the existing `B5_22_DISPOSABLE_CAP_ACCEPTANCE_UI` project.
4. Open **Canonical Profiles**. Select the Diagnostic Console CAP
   (`STORY-PRO-B00D168E43`), press **Edit Selected**, then in the
   **Canonical Reference Gallery** select the existing supplementary
   Candidate 4. Record the candidate ID and image file SHA-256.
5. Press **Open Saved Candidate Review…** (not the button that starts
   a fresh paid evaluation). Confirm the original semantic report opens,
   with no provider call or billable Yes/No consent prompt.
6. Press **F5.4.2 Review General Visual Correction (No Generation)…**.
   Confirm the new **C2.1 Persisted review session** control group
   and existing-mask group are visible in the scrollable dialog.
7. Re-review Stage B fields against the actual image:
   `components` = FAILED for `protruding instead of recessed`;
   inspect the native-resolution ROI; independently review
   `geometry`, `materials`, `scale`. Do not mark a genuinely
   failed or unverifiable requirement as verified just to pass C1.
   For each field click **Inspect Stage B Evidence / ROI**.
8. Confirm `4 of 4 fields reviewed`, select `components`,
   re-examine its ROI, check **I inspected the ROI against the
   source image**, then click **Inspect Stage C Governed Handoff**.
   Confirm the source SHA, target, defect, correction sequence and
   proposal digest, with all generation authority disabled.
9. Click **Save Human Review Session (No Generation)** once.
   Confirm the immutable `c21-4-....json` path and notice
   that saving neither creates masks nor calls AI.
   Click **Refresh Saved Human Reviews** and confirm the newly
   created file appears. Do not save repeatedly merely to test
   resumption; each Save intentionally creates a new record.
10. Close the F5.4.2 dialog, quality review and VSCS normally.
    Relaunch `vscs`, verify active project and repeat the
    Canonical Profiles → Candidate 4 → **Open Saved Candidate Review…**
    → F5.4.2 navigation without a new paid evaluation.
11. From the **C2.1 saved-session dropdown**, select the exact
    `c21-4-....json` saved in Step 9; press
    **Resume Selected Human Review (No Generation)**.
    Confirm the original statuses, notes, ROI and `4 of 4`
    progress reappear, along with the stored C1 digest. Switching
    between `components` and `geometry` must restore each field's
    own values without cross-contamination.
12. Confirm the ROI and C2 mask checkboxes are **unchecked** after
    resumption. Reinspect the source image before rechecking the ROI
    acknowledgement. Click **Inspect Stage C Governed Handoff** and
    confirm the newly recalculated C1 digest matches the restored
    provenance. This remains review-only.
13. Click **Find Masks for Current C1 Proposal**. The two previously
    saved C2 mask PNG versions must be listed as historical or exact
    current matches, depending on the selected ROI. **No mask is
    automatically selected.** Choose one deliberately, click
    **Inspect Selected Existing Mask (No Generation)** and confirm
    its SHA and `CURRENT`/`HISTORICAL` status. Do not claim
    an historical mask is eligible for the current C1.
14. **Negative acceptance:** in a separate isolated fixture test,
    change the source SHA, CAP review fingerprint or saved JSON
    content and confirm resume blocks. Never modify the real
    Candidate 4 image, CAP or accepted quality report for this test.
15. Close the dialogs and confirm only the new immutable C2.1
    session JSON was intentionally created. Both earlier C2 mask
    files, Candidate 4 bytes, quality report, CAP/Canon/MASTER,
    governed attempt count and gallery registration remain unchanged.
    Capture screenshots and provide explicit operator acceptance.

**Stop conditions:** missing saved report, unexpected paid AI prompt,
unverified fields, changing source/requirements, mismatched C1 digest,
unreviewed ROI, unsafe/tampered session, mask mismatch, unexpected
ComfyUI call, CAP modification or a consumed attempt.

## Windows validation commands

```powershell
cd D:\VSCS\video_series_studio
git status --short
git fetch origin
git switch phase-f5.4.2-c2.1-persistent-human-review
git pull --ff-only origin phase-f5.4.2-c2.1-persistent-human-review
git rev-parse --short HEAD
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q tests/test_cap_persistent_human_review.py tests/test_cap_interactive_source_roi.py tests/test_cap_human_reviewed_mask_evidence.py tests/test_cap_spatial_visual_evidence.py tests/test_cap_governed_visual_correction_handoff.py tests/test_cap_visual_candidate_quality.py
python -m pytest -q
git diff --check
git status --short
```

C2.1 remains unaccepted until the Windows checks, restart/resume UI,
mask-version selection and non-mutation evidence are supplied. C3/C4
remain disabled regardless of this phase's outcome.
