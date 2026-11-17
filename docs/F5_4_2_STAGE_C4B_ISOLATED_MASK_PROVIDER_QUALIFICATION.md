# F5.4.2 Stage C4B — Isolated Mask-Capable Provider Qualification

**Status: C4B.1 Windows/static validation and observed GET-only UI checks PASSED; final cancellation/non-mutation operator attestation pending.**
**Live C4B.2 GPU qualification has NOT been performed or authorized.**
**Date:** 2026-11-17
**Tracking issue:** [#53 — C4B isolated provider qualification](https://github.com/npayne10/video_series_studio/issues/53)

## 1. Scope and current authority

Accepted Stage C4A established a source-bound C1/C2 preparation report,
operator review-only acknowledgement, and synthetic exact protected-RGB
pixel comparison. It **did not** qualify a mask-capable Qwen runtime.
Current protected Diagnostic Console Candidate 4 retains its last
governed Attempt 2/2. Its two saved C2 mask PNGs are **HISTORICAL**
relative to the restored C2.1 reviewed C1 proposal. **Do not create
a new Candidate 4 mask, execute an edit or consume its attempt to
test C4B.**

The existing managed XCIC workflow uses:
- `XCICQwenReferenceJobLoader` node `171` for reference source,
  text prompts, mode and output identity;
- `FluxKontextImageScale` node `170:160` to prepare the model image;
- `XCICSaveReferenceCandidate` node `9` for ordinary XCIC
  derived-reference adoption.

This is **not** a governed masked-Candidate correction route. The
existing `managed_qwen_correction_job.py` continues to reject
`contract.mask_path` when present. It has **not** been weakened.

## 2. C4B.1 standalone Qwen API graph — no provider execution

File:
`src/vscs/application/caps/c4b_isolated_mask_provider.py`

`prepare_c4b_isolated_blueprint(snapshot, proposal,
selected_mask_path=..., seed=1729)`:

1. Reuses C4A's source SHA-256, accepted CAP fields,
   sealed C1 proposal, and exact saved-C2 inventory checks.
   Requires an explicitly **CURRENT** C2 mask whose bytes match
   the deterministic reviewed rectangular mask. A missing,
   HISTORICAL or stale mask blocks.
2. Clones the **inspected** managed-Qwen model/TextEncode/VAE
   graph in memory without modifying the checked-in workflow.
   Removes XCIC queue/loader/output and optional LoRA/mode
   switches. Fixes a deterministic, non-LoRA 20-step baseline;
   uses the existing reviewed-CAP-only positive prompt
   construction, never free-form operator observation text.
3. Introduces only core/image-mask graph components:
   `LoadImage`, `LoadImageMask`, `GetImageSize`,
   `MaskToImage`, `ImageScale`, `ImageToMask`,
   `SetLatentNoiseMask`, `ImageCompositeMasked`
   and `SaveImage`.
4. Routes the *scaled* source through the existing
   Qwen text encoder/VAE. Resizes the reviewed mask using
   **nearest-exact** to the processed source dimensions
   for latent noise-mask conditioning. This is a **hypothesis
   to test**, not an accepted proof of Qwen inpainting semantics.
5. Resizes decoded output to the **original source dimensions**
   and composites the result over the original unscaled source
   under the original exact C2 mask. This structural design
   aims to preserve black-mask pixels exactly, independent of
   any changes made by the model outside the editable region.
   The success of that claim requires a real output followed
   by a pixel audit.
6. Uses `SaveImage` with prefix
   `C4B_DISPOSABLE_QUALIFICATION`, **without configuring
   any execution**, and returns SHA-256-sealed in-memory
   graph **and separate full source/C1/mask/template evidence**
   with deterministic input basenames
   `c4b_source_<source hash prefix>.png` and
   `c4b_mask_<mask hash prefix>.png`.
7. `validate_c4b_api_graph` rejects XCIC nodes, stale/unsafe
   loader paths, changed source/mask/composite wiring,
   unexpected nodes, malformed edges, unreviewed sampler
   branches or any graph that differs from a fresh exact
   derivation of the trusted model template.

**No source/mask copies are staged in ComfyUI input.**
The `SaveImage` node writes to the **server-configured
ComfyUI output directory** if the graph is ever run; a prefix
does not provide filesystem isolation. **It must NEVER be
submitted to the ordinary shared ComfyUI instance**.
The only safe future runtime is a **separately launched isolated
instance** with explicitly disposable input, temp and output
directories, plus a separately reviewed once-only
execution consent. No such runtime was launched by C4B.1.

The blueprint always returns:
`execution_authorized=False`,
`input_staging_authorized=False`,
`governed_attempt_allowed=False`,
`candidate_registration_allowed=False`,
`node_schema_verified_live=False`,
`runtime_mask_polarity_verified=False`,
`runtime_vram_verified=False` and
`protected_pixel_fidelity_verified=False`.

## 3. Optional local GET-only node inventory

`inspect_c4b_local_node_inventory()` reuses the accepted C3
local GET-only transport with no redirect and loopback validation.
It reads `/object_info` and `/system_stats` only.
It checks available input names of the nine core/mask
classes needed by the isolated graph, and reports GPU
**total and free** memory if supplied.

This **does not** validate the complete Qwen model graph,
node output/typing/polarity, GPU inference or model
availability. A separate `inspect_c4b_node_schemas()`
pure backend check compares every compiled graph class
and input name against a supplied object-info inventory.
Neither inventory constitutes authorization.

## 4. Next real qualification — C4B.2 (PENDING SEPARATE CONSENT)

In a **new disposable test project**, not the protected
Diagnostic Console Candidate 4:

1. Prepare a disposable source image and a **current** sealed
   C1 operator-reviewed ROI and saved deterministic C2
   mask (exact immutable SHA-256; not a historic mask).
2. After fresh authorization, create isolated input, temp and
   output directories **outside any VSCS production project**.
   Start a **separate ComfyUI process** with `--input-directory`,
   `--temp-directory` and `--output-directory` explicitly
   restricted to these locations. Do not target the user's
   existing `http://127.0.0.1:8188` production instance;
   use a separate localhost port with output-scope checks.
3. Stage only disposable SHA-checked copies of the approved
   source and mask after explicit consent. Audit destination
   paths and file digests immediately before one controlled
   `POST /prompt` submission; never stage through the C4B.1
   inspection button.
4. Freeze model names/hashes, native node inputs, seed and
   20-step settings. Before GPU load, confirm schema/enum
   compatibility, source-mask dimensions, expected output
   dimensions and sufficient free memory and system/pagefile
   headroom. Stop on any node/schema/VRAM blocker.
5. **One disposable GPU run only**, once-only job ID,
   no automatic retry. Capture prompt ID, provider logs,
   peak VRAM, wall time, source/graph/model SHA, outputs
   and failure recovery. Verify original-source input
   and mask polarity empirically with unambiguous synthetic
   white/black quadrants.
6. Audit the **actual external RGB output**:
   exact image dimensions and hash; **zero changed RGB
   pixels anywhere outside the reviewed C2 mask**.
   Within-mask changes must be reviewed for correction
   success; no change or incorrect edit is not a
   semantic success even if protected pixels match.
7. Confirm no changes to any source Candidate, C1/C2 evidence,
   CAP, Canon/MASTER, gallery, governed attempt count,
   approved GeneratedMedia, production UI or shared
   ComfyUI queue. Record operator-approved evidence.
8. Only after successful C4B.2 and further governed C4
   integration may an execution-specific, one-use
   production consent, attempt journal, corrected-Candidate
   registration and separate CAP approval be designed.

**Not yet implemented:** dedicated isolated ComfyUI
process bootstrap, SHA-bound staging, one-use `POST`
execution, result-handoff automation and GPU memory capture.
This intentional C4B.2 stop gate must not be bypassed.
C4A `REVIEW ONLY` remains **not** generation consent.

## 5. Operator validation evidence — 2026-11-17 (partial acceptance)

The operator pulled the C4B branch to Windows, then reported:

- Ruff lint: **All checks passed**.
- Ruff formatting: **1,704 files already formatted**.
- Mypy: **Success, no issues in 713 source files**.
- Focused C4B/C4A/C3/C2.1/matrix regression:
  **51 passed** (prior run after the final test addition).
- Full regression: **2,890 passed, 1 skipped**
  (directory symlinks unavailable on Windows, prior run).
- `git diff --check`: clean. `git status --short`: only
  the two previously existing untracked
  `docs/VSCS_Architecture_Workflow_Audit_2026-10-24.md`
  and `qwen_f5_preflight_result.json`.

**Observed UI screenshots**:

1. The Stage C4B **Inspect C4B Isolated Mask Graph (No Generation)**
   action rejected the selected HISTORICAL C2 mask with the
   blocking message **"C4B rejects HISTORICAL or non-current C2 mask"**.
2. The **Probe C4B Local Mask Nodes (GET Only)** action displayed
   the explicit Yes/No confirmation and described the two
   read-only GET endpoints, lack of generation and attempt
   reservation. The No button appeared as the default.
   Whether the operator actually tested cancelling with
   **No** is **not yet attested**.
3. The accepted **GET-only inventory result** listed all nine
   expected classes:
   `GetImageSize`, `ImageCompositeMasked`, `ImageScale`,
   `ImageToMask`, `LoadImage`, `LoadImageMask`,
   `MaskToImage`, `SaveImage`, `SetLatentNoiseMask`.
   **Missing classes: none. Missing declared inputs: none.**
   GPU: NVIDIA GeForce RTX 5060 Ti (cuda:0),
   **15.9 GiB total; 14.7 GiB free** at observation.
   The report explicitly retained **"Mask polarity, full graph
   output wiring and GPU inference: NOT VERIFIED"** and
   **"Provider compatibility, protected-pixel fidelity and
   execution: BLOCKED"**.
4. The same screenshot shows the restored `components`
   discrepancy `protruding instead of recessed`,
   **4 of 4 reviewed fields**,
   normalized ROI
   `0.64798851,0.45478723,0.06178161,0.07446809`,
   C1/C2 UI inspection checkboxes checked after review, and
   the C2.1 mask version still labelled **HISTORICAL**.

**Not yet attested:** cancellation by **No** produces no
inventory report, and the final protected-state/non-mutation
check (Candidate 4 image/metadata, saved AI review, both C2
PNGs, saved C2.1 JSON, CAP/Canon/MASTER, gallery registration,
governed attempt count, and no paid evaluation/ComfyUI POST/
output/attempt reservation). The inventory report states
that it uses GET only but is not an independent audit of
the running provider's request logs.

**Acceptance boundary:** C4B.1 remains an offline,
non-executing qualification candidate until the last
operator confirmations are received. A complete node
inventory is **not** proof of Qwen mask compatibility,
mask polarity, GPU inference reliability or exact pixel
fidelity. No C4B.2 inference or governed correction has
been authorized.

## 6. Regression and operator checks for C4B.1

### Windows validation

```powershell
cd D:\VSCS\video_series_studio
git status --short
git fetch origin
git switch phase-f5.4.2-c4b-isolated-mask-provider-qualification
git pull --ff-only origin phase-f5.4.2-c4b-isolated-mask-provider-qualification
git rev-parse --short HEAD

python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src

python -m pytest -q tests/test_cap_c4b_isolated_mask_provider.py tests/test_cap_c4_mask_provider_contract.py tests/test_cap_c3_mask_provider_dry_run.py tests/test_cap_human_reviewed_mask_evidence.py tests/test_cap_persistent_human_review.py tests/test_cap_visual_review_matrix_layout.py
python -m pytest -q

git diff --check
git status --short
```

Existing pre-untracked `docs/VSCS_Architecture_Workflow_Audit_2026-10-24.md`
and `qwen_f5_preflight_result.json` must remain untouched.

### Operator test C4B-UI-01 — start VSCS from PowerShell

1. With `(.venv)` active, start **`vscs`**.
   On **Dashboard → Active Project**, confirm
   `B5_22_DISPOSABLE_CAP_ACCEPTANCE_UI`.
2. Go to **Canonical Profiles → Diagnostic Console
   (`STORY-PRO-B00D168E43`) → Edit Selected →
   Canonical Reference Gallery → Candidate 4**.
3. Click **Open Saved Candidate Review…**. **Do not**
   select the paid AI re-evaluation action.
4. Open **F5.4.2 Review General Visual Correction
   (No Generation)…**. Under C2.1 saved sessions,
   select `c21-4-d1aafcc27b2d4e098d835702542261c8.json`,
   then **Resume Selected Human Review**.
   Confirm 4/4 fields and the saved ROI
   `0.64798851,0.45478723,0.06178161,0.07446809`.
   C1/C2 checkboxes must be unchecked.
5. Select `components`, visually reinspect the
   source ROI, tick the C1 operator acknowledgement,
   then **Inspect Stage C Governed Handoff**.
   Verify C1 SHA-256
   `76bd6349cdb3b4b399495d5d4c2144f845d155388cb7049a64d8f50f0a966cdc`.
6. Under **C2.1 Existing Mask Versions**, click
   **Find Masks for Current C1 Proposal**. Confirm
   both saved masks are HISTORICAL. Select the mask
   with SHA-256 prefix `1aa336f6`.
7. In **Stage C4B — isolated Qwen provider (offline
   only)** click **Inspect C4B Isolated Mask Graph
   (No Generation)**. **Expected: BLOCKED** —
   HISTORICAL/non-current mask. There must be no
   output filename, provider job, GPU load or
   attempt reservation.
8. Click **Probe C4B Local Mask Nodes (GET Only)**.
   Test **No** first; no GET request should occur.
   If ComfyUI is running on `127.0.0.1:8188`,
   choose **Yes** on the second attempt. The read-only
   report should list required class presence/missing
   inputs and GPU inventory. It must continue to say
   provider/mask correctness and execution are blocked.
9. The positive standalone API graph path is tested only
   through `tests/test_cap_c4b_isolated_mask_provider.py`
   using synthetic/current-C1/C2 evidence. Do not
   generate or save a new mask for Candidate 4 just
   to make the UI show an eligible blueprint.
10. Confirm Candidate 4, saved AI review, both C2 PNGs,
    C2.1 JSON, CAP/Canon/MASTER, gallery and governed
    correction attempt counter remain unchanged.
    Confirm no ComfyUI `POST`, model load,
    paid evaluation, output or attempt reservation.
    Capture status/report screenshots and logs for
    formal C4B.1 operator acceptance.

**C4B.1 remains unaccepted until these Windows and UI
results are reported and approved. Actual C4B.2 GPU
qualification and real C4 correction remain separate
not-authorized future work.**
