# Phase F5.4.2 Stage C — Governed Visual Correction Integration

**Status: C1 implementation candidate; not operator-accepted.** Stage C is
split into gated milestones rather than immediately enabling the live
ComfyUI/managed Qwen generator. Stage B was operator-accepted on 2026-11-13.

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

- **C2 — Human-reviewed mask evidence:** from source dimensions and
  operator-reviewed ROI to an actual bounded mask with independent inspection,
  sealed mask digest, source hash, exact outside-mask preservation policy,
  and safe storage. No provider inference yet.
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

**Acceptance gates:** lint/format/type checks, targeted tests, full regression,
Windows UI smoke test, source/attempt/CAP non-mutation evidence and explicit
operator acceptance. None of these was independently executed for C1 by the
GitHub source-edit connector.
