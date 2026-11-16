# F5.4.2 Stage C4A — Mask-Capable Provider Contract Preparation

**Status: IMPLEMENTATION CANDIDATE — Windows regression and operator acceptance pending.**
This is **C4 preparation only**, not C4 image generation, a trusted
mask-capable provider, or permission to consume a governed attempt.

## Engineering decision

The accepted C3 GET-only audit found local ComfyUI nodes
`LoadImageMask`, `SetLatentNoiseMask` and
`ImageCompositeMasked` on the RTX 5060 Ti 15.9 GiB GPU. This
does not prove working masked inference. The trusted managed XCIC
Qwen correction builder still explicitly rejects `mask_path`
and uses an XCIC derived-reference writer rather than a
governed corrected-Candidate writer.

**Therefore C4A must not repurpose the current managed graph as if it
were a validated masked provider.** It prepares a sealed, non-executable
contract around the existing F5.4.1B *experimental* masked Qwen
graph, and a separate inspection-only result-pixel comparison.

### Source and mask contract

- Bind the current canonical supplementary Candidate image SHA-256,
  selected accepted CAP requirement set, C1 proposal SHA-256,
  target defect and normalized ROI. Reject stale source image or
  changed accepted CAP fields.
- Select an existing **CURRENT** C2 PNG mask only if its exact
  bytes match the current C1 source-bound rectangular mask. A
  `HISTORICAL` mask is reported as a blocker and is never rebound
  implicitly. The two existing saved Candidate 4 C2 masks
  (`19564b7f...` and `1aa336f6...`) are historical relative
  to the accepted C2.1 ROI
  `0.64798851,0.45478723,0.06178161,0.07446809`.
  Do not create a new C2 mask solely for C4A acceptance.
- Inspect the managed Qwen workflow SHA-256; construct and check
  the derived masked graph **in memory**. Verify connections from
  mask loader to latent noise mask, sampler and post-decode
  protective composite, with the original source feeding the
  composite destination. **No ComfyUI inputs are staged or bound.**
- Seal the preparation report using SHA-256 of its identity,
  graph digests and blockers. The seal detects change, but is not
  a separate cryptographic authentication of a provider run.
  Preparation always returns `execution_authorized=False`,
  `attempt_reservation_allowed=False`,
  `candidate_registration_allowed=False` and
  `mask_provider_compatibility_verified=False`.

### Operator consent separation

The F5.4.2 review dialog adds:

- **Inspect C4A Mask Provider Contract (No Generation)**:
  creates an in-memory preparation report only, including all
  unresolved blockers.
- **Acknowledge C4A Preparation Review (Not Execution Consent)**:
  requires the operator to type the exact phrase
  `REVIEW ONLY`. It revalidates that the selected
  mask, source image and graph have not changed.
  This creates a **memory-only review acknowledgement**,
  not permanent authorization, execution consent or an attempt
  journal. Closing VSCS never implies consent.

**Future C4 execution consent** must be separately implemented
with provider/model, cost, source/mask/graph digests, one-use
disposable job ID, target editable pixel bounds and affected
reviewed CAP field displayed to the operator. A fresh
explicit confirmation may only be sought *after* provider-specific
input validation, GPU feasibility and governance checks. It
must not reuse the C4A `REVIEW ONLY` acknowledgement.

### Protected-pixel verification design

`audit_external_masked_result(...)` can inspect an **already
existing, external, disposable** RGB PNG result, never a Candidate
output inside the active project. It rechecks current C1/C2
source-mask provenance, requires the same dimensions as the
RGB Candidate source and binary L mask, and counts exact RGB
differences on every protected (black-mask) pixel. It performs
**no image creation or filesystem writes**.

An audit with `changed_protected_pixels == 0` demonstrates
only exact equality of compared protected RGB pixels; it does
**not** validate semantic correction, masked provider execution,
alpha/color-management behavior, GPU memory usage or authorization
to register the output. Conversely, even **one** protected
pixel mismatch fails the pixel-fidelity criterion. Verify source
color mode assumptions before generalizing to non-RGB Candidates.
Synthetic fixtures exercise one changed editable pixel and one
changed protected pixel without using ComfyUI or Candidate 4.

### C4 production prerequisites not implemented by C4A

1. A reviewed, actual mask-aware ComfyUI API export with
   explicit source and mask file inputs and validated loader
   semantics, and exact source/mask/graph SHA binding.
2. Isolated disposable provider environment and external output;
   prove input-polarity, composition outside mask and whether
   protected pixels survive byte-exact RGB comparison.
3. Quantified GPU tests on RTX 5060 Ti 16 GiB including peak
   VRAM, model unload behavior, context/runtime settings and
   controlled failure/timeout recovery.
4. Fresh one-use **generation-specific** operator consent that
   exposes provider, model, cost, source, C1/C2 digests and
   target ROI, independent of C4A review acknowledgement.
5. Only after explicit release approval: durable
   once-only governed attempt reservation; no automatic retry
   after uncertain result. Preserve Candidate 4 final Attempt
   2/2 unless separately reviewed and authorized.
6. External generated-result verification with no protected
   pixel modifications, independently reviewed semantics and
   design consistency. Only then optional manual Candidate
   registration via separate CAP authority. No automatic
   Canon/MASTER promotion.

## Controlled Windows acceptance: C4A-UI-01

1. **Close VSCS first**. From activated `(.venv)` in
   `D:\VSCS\video_series_studio`, fetch and switch to
   `phase-f5.4.2-c4a-mask-provider-contract-preparation`,
   pull, then run Ruff lint, Ruff formatter check, Mypy,
   focused C4A/C3/C2.1/C2/C1 tests, full pytest,
   git diff and status checks (commands below).
   Leave unrelated pre-existing untracked audit/preflight
   files untouched.
2. Run `vscs`. Verify **Dashboard → Active Project** is
   `B5_22_DISPOSABLE_CAP_ACCEPTANCE_UI`.
3. Open **Canonical Profiles → Diagnostic Console →
   Edit Selected → Canonical Reference Gallery**, select
   supplementary **Candidate 4** and click
   **Open Saved Candidate Review…**. **Never**
   click the consented, paid **Review Visual Candidate…**
   action for this test.
4. Open **F5.4.2 Review General Visual Correction
   (No Generation)…**. Select saved C2.1 session
   `c21-4-d1aafcc27b2d4e098d835702542261c8.json`;
   click **Resume Selected Human Review**. Verify
   four fields, saved ROI and unchecked C1/C2 acknowledgments.
5. Select `components` and inspect the source/ROI.
   Check the ROI acknowledgement and click
   **Inspect Stage C Governed Handoff**. Verify
   C1 SHA-256
   `76bd6349cdb3b4b399495d5d4c2144f845d155388cb7049a64d8f50f0a966cdc`.
6. Click **Find Masks for Current C1 Proposal**.
   Confirm both existing C2 masks are `HISTORICAL`.
   Select one explicitly. Click
   **Inspect C4A Mask Provider Contract (No Generation)**.
   Expected: verified C1/source identity, historical mask
   flagged, derived offline masked graph SHA-256 when available,
   managed-Qwen incompatibility and other C4 blockers,
   all authorization properties False.
7. Click **Acknowledge C4A Preparation Review (Not
   Execution Consent)**. Verify the clear non-execution
   warning; enter an incorrect phrase first and confirm
   it blocks. Repeat and enter exactly `REVIEW ONLY`.
   Expected: a memory-only receipt, with **no
   generation authorization or attempt reservation**.
8. Review the contract report and confirm **no local
   ComfyUI GET/POST request**, new mask, file staging,
   output, Candidate registration, AI evaluation or
   attempt reservation occurred.
9. Use the isolated Python regression fixtures, **not**
   the real Candidate 4, to validate that a disposable
   external output with one changed protected RGB pixel
   is detected, while changing only a masked editable
   pixel retains protected-region equality.
10. Operator confirms unchanged Candidate 4 source and
    metadata, saved AI report, both original C2 PNGs,
    persisted C2.1 review JSON, CAP/Canon/MASTER,
    Candidate gallery and governed attempt counter.
    Capture C4A report, review-acknowledgement result
    and relevant PowerShell command output before
    accepting this **preparation-only** phase.

**Stop on** any unexpected request to ComfyUI or paid AI,
new GPU work, stale source/cap, silent historical mask
adoption, filesystem mutation, misleading generation
permission, altered attempts or Candidate 4 modification.

## Windows regression commands

```powershell
cd D:\VSCS\video_series_studio
git status --short
git fetch origin
git switch phase-f5.4.2-c4a-mask-provider-contract-preparation
git pull --ff-only origin phase-f5.4.2-c4a-mask-provider-contract-preparation
git rev-parse --short HEAD
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q tests/test_cap_c4_mask_provider_contract.py tests/test_cap_c3_mask_provider_dry_run.py tests/test_cap_persistent_human_review.py tests/test_cap_human_reviewed_mask_evidence.py tests/test_cap_governed_visual_correction_handoff.py tests/test_cap_qwen_mask_aware_qualification.py
python -m pytest -q
git diff --check
git status --short
```

**C4A is an implementation candidate**, not proof of a
genuinely mask-compatible execution provider. A future
provider-integration and isolated generation phase requires
independent implementation, validation and explicit operator
approval. This must not be recorded as completed C4.
