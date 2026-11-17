# F5.4.2 Review Matrix — UI Layout Refinement

**Status: OPERATOR ACCEPTED — 2026-11-17, UI/PRESENTATION ONLY.**

The F5.4.2 advisory dialog previously stacked independent full-width
buttons below the output panel, separating selections from the operations
they controlled. The new UI groups **the same controls and callbacks** in
named Qt `QGroupBox` / `QGridLayout` matrices in workflow order.

| Group | Selection / context | Nearby actions |
|---|---|---|
| Finding | Accepted CAP field, defect type, concise observation | Classify and Inspect |
| Stage B | Operator status, read-only source ROI, 4-field progress | Select ROI, Inspect B |
| Stage C1 | ROI reviewed acknowledgement | Inspect governed handoff |
| Stage C2 | Source overlay, mask-preview acknowledgement | Preview, Inspect mask, Save mask |
| C2.1 Sessions | Saved human review dropdown | Refresh, Save, Resume |
| C2.1 Masks | Existing C2 mask dropdown | Find, Inspect selected |
| C3 | Current shared selected mask from C2.1 | Offline dry-run, GET-only probe |
| C4A | Shared selected mask; inline Review phrase | Inspect contract, review-only acknowledgement with visible status |

The result assessment panel remains read-only, and the overall dialog
remains scrollable. The default dialog width is increased to 1050 px
and the free-form observation editor uses a compact height so
selection/action rows are visible sooner. No controls were renamed;
existing `objectName` values and signal callbacks remain intact.

**Safety and authority:** This change is strictly presentation only.
The C1/C2 checkboxes still require fresh explicit review; C2
evidence saving remains exclusive; C2.1 session persistence remains
explicit; C3 GET-only consent remains opt-in; C4A `REVIEW ONLY`
acknowledgement is not generation consent. No provider, GPU,
candidate/Canon promotion, output registration, attempt reservation,
or paid AI operation is added. Candidate 4 protected Attempt 2/2
remains untouched.

## Formal layout acceptance — 2026-11-17

**Decision: ACCEPTED for the F5.4.2 matrix layout, without
changing correction authority.**

The operator supplied full-dialog screenshots showing the
Finding/Classification, Stage B, C1, C2, C2.1 Sessions,
C2.1 Mask Versions, C3 and C4A grouped layouts. The CAP
field/defect/observation inputs, status/ROI selection, saved
session/mask dropdowns and their actions were aligned in
their corresponding groups. The scrollable results panel
and all lower-stage buttons were visible and accessible.

The operator then resumed the previously saved C2.1 human
review in the redesigned dialog. The UI restored **4 of 4
reviewed fields**, component failure, original observation
and exact normalized ROI while C1/C2 acknowledgements
remained unchecked. C1 handoff and C4A provider-contract
inspection succeeded with the historical C2 mask correctly
shown as not bound to the current C1 proposal.

An original C4A acknowledgement popup was not visible to
the operator; a subsequent corrective UI commit placed
the typed `REVIEW ONLY` field and BLOCKED/ACKNOWLEDGED
feedback inside the C4A matrix. Operator screenshots showed
both invalid-phrase rejection and successful
`REVIEW ACKNOWLEDGED — NO GENERATION` feedback.

**Windows results:** Ruff lint clean; Ruff formatting
`1,700 files already formatted`; Mypy clean in `712`
source files; focused matrix/C4A regression `9 passed`;
full regression `2,871 passed, 1 skipped` (Windows
directory symlink limitation); `git diff --check`
clean. Only two unrelated pre-existing untracked files
remained.

The operator expressly confirmed no Candidate 4 image,
metadata, saved AI review, C2 PNG, C2.1 session, CAP,
Canon/MASTER, gallery or attempt mutation and no ComfyUI
job, corrected output, paid AI evaluation or attempt
reservation. These are operator-attested findings.

The layout acceptance covers the tested normal-size
dialog and workflow controls. It is not independent
evidence of every possible display scaling or window
size. C4A remains preparation-only, and live masked
GPU correction remains forbidden.

## Windows validation

```powershell
cd D:\VSCS\video_series_studio
git status --short
git fetch origin
git switch phase-f5.4.2-c4a-review-matrix-layout
git pull --ff-only origin phase-f5.4.2-c4a-review-matrix-layout
git rev-parse --short HEAD

python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src

python -m pytest -q tests/test_cap_visual_review_matrix_layout.py tests/test_cap_visual_candidate_quality.py tests/test_cap_persistent_human_review.py tests/test_cap_c3_mask_provider_dry_run.py tests/test_cap_c4_mask_provider_contract.py
python -m pytest -q

git diff --check
git status --short
```

## Controlled UI acceptance — F5.4.2-MATRIX-UI-01

1. Close VSCS before pulling the branch. After successful lint,
   type checks and pytest, start with `vscs` from the active venv
   in `D:\VSCS\video_series_studio`.
2. On **Dashboard → Active Project**, confirm the disposable
   `B5_22_DISPOSABLE_CAP_ACCEPTANCE_UI` project.
3. Open **Canonical Profiles → Diagnostic Console →
   Edit Selected → Canonical Reference Gallery**.
   Select supplementary Candidate 4 and press
   **Open Saved Candidate Review…** to avoid a paid re-review.
4. Click **F5.4.2 Review General Visual Correction (No
   Generation)…**. Confirm the stage groups appear in this
   order: Finding, B, C1, C2, C2.1 Saved Sessions, C2.1
   Masks, C3, C4A. The stage content must remain reachable
   by scrolling; no buttons may be clipped horizontally.
5. In the Finding group, verify field, defect and observation
   can be entered without changing any accepted CAP wording.
   In the Stage B group, verify the status dropdown sits
   beside its label and ROI selector sits immediately next
   to the read-only ROI field. Do not save new Stage B
   evidence just to test layout.
6. In **C2.1 Sessions**, select the existing
   `c21-4-d1aafcc27b2d4e098d835702542261c8.json`
   then click **Resume Selected Human Review** in the
   same group. Confirm 4/4 fields and the original
   normalized ROI
   `0.64798851,0.45478723,0.06178161,0.07446809`.
   C1 ROI and C2 preview confirmations should be unchecked.
7. Reinspect the actual source ROI, check the C1 acknowledgement
   and inspect the C1 handoff. Verify the previously accepted
   proposal SHA-256
   `76bd6349cdb3b4b399495d5d4c2144f845d155388cb7049a64d8f50f0a966cdc`.
8. In **C2.1 Masks**, click **Find Masks** and verify both
   previously saved C2 masks remain labelled HISTORICAL
   for the current ROI. Select a mask and click
   **Inspect Selected Existing Mask** beside the dropdown.
   No mask may be silently promoted to CURRENT or executed.
9. Verify the **C3** offline/GET-only buttons and
   **C4A** contract/review-only button are grouped
   and visible. C4A must also display a **Review phrase**
   entry and a status label directly beside/below the
   acknowledgement action. Enter an invalid phrase and
   check BLOCKED feedback, then enter `REVIEW ONLY`
   and check **REVIEW ACKNOWLEDGED — NO GENERATION**.
   Do not run generation. Optionally
   inspect C3 offline or C4A contract using the
   historical mask and confirm the same blockers.
   If testing GET-only probe, retain the existing
   explicit Yes/No consent.
10. Resize the dialog narrower and wider; verify text remains
    legible, selected mask/session is not confused with another
    operation, and all controls remain reachable by scrolling.
    Capture screenshots of the upper and lower matrix sections.
11. Confirm no Candidate 4 source/metadata, saved AI report,
    C2 masks, C2.1 JSON, CAP/Canon/MASTER, gallery
    registration or attempt counter changed. There should
    be no GPU inference, ComfyUI prompt or output.
    Only after these checks may the presentation refactor
    be accepted.

**Known limitation:** A single shared C2 mask selector in its own
group is used by C3 and C4A. The two provider groups are immediately
below that selector, rather than introducing duplicated selectors
that can disagree. This design intentionally keeps one source
of truth for the selected mask.
