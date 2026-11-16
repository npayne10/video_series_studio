# Phase F5.4.2 Stage C — Governed Visual Correction Integration

**Status: Stage C1 accepted 2026-11-13; Stage C2 accepted 2026-11-15;
Stage C2.1 and diagnostic-only Stage C3 accepted 2026-11-16.**
Stage C4 remains unimplemented and unauthorized. Stage C3 does not
authorize provider mask generation, GPU inference, attempt reservation
or Candidate registration. Stage C is split into
gated milestones rather than immediately enabling the live ComfyUI/managed
Qwen generator. Stage B was operator-accepted on 2026-11-13.
See [formal C2 acceptance record](F5_4_2_STAGE_C2_HUMAN_REVIEWED_MASK_EVIDENCE.md#formal-operator-acceptance-record--2026-11-15).

## Stage C4A preparation — implementation candidate

C4A has a separate, **non-executable** provider preparation
contract. It checks the exact source/CAP/C1/C2 evidence,
reviews the proposed F5.4.1B mask-to-latent and
post-decode source compositing graph only in memory,
and emits SHA-sealed blockers. It does not repair the
existing XCIC Qwen mask incompatibility or establish
live masked generation on RTX 5060 Ti 16 GiB.

The C4A dialog contains explicit offline inspection and
a typed **REVIEW ONLY** operator acknowledgement.
This acknowledgement is *not* generation consent and
cannot schedule, reserve, retry, produce or register
a Candidate. An optional backend can inspect existing
external disposable PNG output for exact protected RGB
pixel differences, without writing or claiming
provider correctness. The protected final Candidate 4
Attempt 2/2 remains untouched.

See [C4A technical contract and operator test](F5_4_2_STAGE_C4A_MASK_PROVIDER_CONTRACT.md).
**C4A is pending Windows/UI acceptance; actual C4
GPU inference and Candidate registration remain unauthorized.**

## Stage C3 diagnostic-only acceptance — 2026-11-16

Stage C3 operator acceptance is recorded in
[F5.4.2 Stage C3 evidence](F5_4_2_STAGE_C3_MASK_PROVIDER_DRY_RUN.md#formal-operator-acceptance-record--2026-11-16).
Ruff lint/format, Mypy and all focused/full regressions passed.
The read-only offline graph check found the derived experimental
mask topology; the opt-in loopback GET-only ComfyUI probe
detected `LoadImageMask`, `SetLatentNoiseMask` and
`ImageCompositeMasked` and reported RTX 5060 Ti ~15.9 GiB
**total** GPU memory. The two saved C2 masks were correctly
classified `HISTORICAL` for the current C1 proposal.

The operator expressly confirmed no changes to Candidate 4, saved
AI review, C2 PNGs, C2.1 JSON, CAP/Canon authority, gallery
registration or attempt counter, and no job or image output.
This acceptance establishes **diagnostic capability only**.
The existing managed Qwen provider does not accept governed C2 masks;
live masked inference, mask polarity, protected-pixel fidelity,
peak VRAM and C4 production governance remain unverified.
Candidate 4's protected final governed Attempt 2/2 remains locked.

## Stage C2.1 acceptance — 2026-11-16

The Stage C2.1 persistent human-review session feature has been
operator-accepted. The controlled workflow saved a sealed
source/CAP-bound JSON record, closed and restarted VSCS, and restored
all four operator-reviewed fields and ROI without a new paid AI
review. The original sealed C1 proposal SHA-256 reproduced after
fresh ROI acknowledgement. Both existing C2 masks were correctly
listed as historical, inspected only, and not adopted for execution.

Windows validation: Ruff lint/format clean, Mypy on 710 source files,
73 focused tests passed, and 2,857 full-suite tests passed with
one Windows symlink skip. The operator expressly confirmed no
Candidate 4 / saved AI review / CAP authority / Canon/MASTER /
gallery / governed-attempt mutation.

See [C2.1 formal acceptance record](F5_4_2_STAGE_C2_1_PERSISTENT_HUMAN_REVIEW.md#formal-operator-acceptance-record--2026-11-16).
Persisted review evidence grants **no** producer execution authority;
C3/C4 and the protected final Candidate 4 governed Attempt 2/2
remain locked.

## Stage C1 acceptance record — 2026-11-13

**Decision:** Stage C1 accepted based on completed Windows static checks,
previously reported focused/full regression, visible non-executable handoff,
and the operator's explicit confirmation of Candidate 4 non-mutation.

- Ruff lint: all checks passed. Ruff formatting: 1,683 files formatted.
  Mypy: no issues found in 706 source files.
- Regression: 83 focused tests passed; 2,820 full-suite tests passed,
  1 skipped because directory symlinks are unavailable. These test counts
  precede the final formatting-only commits; no newer full regression
  was separately supplied.
- UI: the operator inspected all four accepted fields and generated an
  F5.4.2 Stage C1 governed correction proposal for Candidate 3, asset
  `STORY-PRO-B00D16E843`, targeting `components` / `missing_component`
  with an operator-acknowledged normalized ROI `0.1,0.2,0.3,0.4`.
  The display showed source SHA-256, accepted CAP requirement, observed
  failure, `reconstruct_component -> verify_design`, proposal digest,
  and explicit no-mask/no-provider-execution notices.
- The operator separately confirmed that the C1 inspection did **not**
  modify Candidate 4, its saved evaluation, CAP authority or governed
  attempt counter. This is operator-confirmed non-mutation, not an
  independent filesystem diff.
- The C1 UI currently does not restore field-specific form values when
  the selected CAP field changes. The underlying session review was
  correct, but the visible status/observation controls may display
  values entered for the previously selected field. Track this as a
  C2-era UI consistency improvement, without changing C1 acceptance.
- **Governance:** C1 acceptance grants no authority to generate, derive
  an approved mask, consume an attempt, register a Candidate, or promote
  CAP/Canon/MASTER. Candidate 4's final governed Attempt 2/2 stays
  protected. Next: Stage C2 — human-reviewed mask evidence, subject to
  its own tests and explicit approval.

## Governing implementation decision

An accepted field-specific ROI is *not* an edit mask. The current
`managed_qwen_correction_job.py` explicitly rejects masked jobs because the
inspected managed Qwen graph has **no validated mask input**. Existing
`spatial_correction_contract.py` governs explicit image/mask/workflow hashes
for a separate Candidate regeneration plan; it does not authorize an
operator-proposed Stage B ROI to become a provider mask.

Therefore the safe initial integration is **C1: a fully reviewed,
source-bound, sealed, non-executable correction proposal**. No attempt
reservation, GPU request, ComfyUI POST, filesystem write, Candidate registration,
CAP promotion or Canon approval is added.

## Stage C1 contract

- Start from the in-memory `SpatialEvidenceReview` produced in Stage B.
- All accepted CAP fields must have explicit operator findings. No `UNKNOWN`
  accepted fields can proceed to C1.
- Exactly **one** field may be `FAILED` as the correction target; the other
  fields must be `VERIFIED_BY_OPERATOR`. Multiple failed fields require an
  explicitly designed future multi-defect policy.
- The failed field must have a typed defect, 12–2000-character observation,
  reviewed accepted requirement, an in-bounds normalized ROI and the
  deterministically mapped correction stages.
- The operator must explicitly acknowledge inspecting the ROI against the
  source image. This acknowledgement is not consent to generate and does not
  prove that the ROI bounds are technically correct.
- The source Candidate identity and SHA-256 must match the current bound
  evidence. The proposal has a deterministic SHA-256 seal of its authoritative
  fields and non-authority switches.
- A Stage C1 proposal is immutable in memory and permits **no generation**.
  It cannot reserve or release Candidate 4 governed Attempt 2/2.
- Closing the dialog discards the proposal. Persisted governed review journals,
  source-image mask construction and provider jobs are NOT C1 features.

## Operator review steps

1. Open an existing Candidate semantic quality review. Use the Stage B
   **Review General Visual Correction** dialog (no new paid request).
2. For each accepted CAP field, enter a specific observation and select
   `FAILED` with defect and ROI for the single intended target, or
   `VERIFIED_BY_OPERATOR` for verified non-target fields. Press
   **Inspect Stage B Evidence / ROI (No Generation)** for each field.
3. Re-select the failed target field, then check
   **I inspected the ROI against the source image...** after actual inspection.
4. Press **Inspect Stage C Governed Handoff (No Generation)**.
5. Confirm the source hash, accepted requirement, target defect, ROI,
   deterministic stages, proposal seal and NO GENERATION notice.
6. Repeat with an `UNKNOWN` field, a missing ROI and unchecked operator
   acknowledgement. Each must block without writes or network calls.

**Candidate 4 stop rule:** The earlier dial-specific GPU trials are closed.
The governed final Attempt 2/2 must remain protected. Reuse the saved visual
Candidate report only for advisory review; do not initiate new inference.

## Follow-on stages (require separate review and approval)

- **C2 — Human-reviewed mask evidence (accepted 2026-11-15):** native-resolution
  interactive ROI, source SHA-256 binding, inspected grayscale PNG,
  verified saved mask hashes, exclusive no-overwrite storage and explicit
  operator-confirmed Candidate/CAP/attempt non-mutation. This is **not**
  an actual post-edit outside-mask pixel preservation proof. No provider
  inference is authorized.
- **C3 — Provider capability and dry-run:** verify a real local ComfyUI
  workflow's mask inputs and model/VRAM fit; compare the Qwen edit graph and
  alternatives without asserting mask support that has not been observed.
  Explicit consent, attempt budgets and immutable parent lineage must be
  wired to existing production governance before any execution.
- **C4 — Controlled corrected-Candidate production:** only after C2/C3
  acceptance. Require independent source and mask checks before execution,
  post-run protected-pixel comparison, per-field semantic verification,
  manual Candidate registration and no automatic Canon/MASTER promotion.

## Windows validation

```powershell
cd D:\VSCS\video_series_studio
git status --short
git fetch origin
git switch phase-f5.4.2-stage-c-governed-visual-correction
git pull --ff-only origin phase-f5.4.2-stage-c-governed-visual-correction
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q tests/test_cap_spatial_visual_evidence.py tests/test_cap_governed_visual_correction_handoff.py tests/test_cap_general_visual_correction_triage.py tests/test_cap_geometry_correction_policy.py tests/test_cap_visual_candidate_regeneration.py
python -m pytest -q
git diff --check
git status --short
```

**Acceptance gates:** fulfilled for C1, C2, C2.1 and
**diagnostic-only** C3 based on operator evidence and Windows tests.
C4 still requires separate implementation, regression,
independent controlled execution evidence and explicit operator
approval. Source-edit connectivity does not run Windows tests.
