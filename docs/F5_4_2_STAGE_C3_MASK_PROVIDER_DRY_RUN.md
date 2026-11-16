# F5.4.2 Stage C3 — Provider Mask Compatibility and Controlled Dry-Run

**Status: OPERATOR ACCEPTED — 2026-11-16, DIAGNOSTIC ONLY.** No GPU inference, provider mask execution, corrected Candidate registration or governed attempt use has been authorized.

C3 assesses whether a C2 source-bound mask could be routed through a
mask-aware local ComfyUI workflow. **It does not perform image generation.**
C2.1 was operator accepted on 2026-11-16; C3 is a separate gate.
C4, any GPU inference, paid AI requests and Candidate 4's protected
final governed Attempt 2/2 remain unauthorized.

## Formal operator acceptance record — 2026-11-16

**Decision:** Stage C3 accepted for *read-only capability assessment and
controlled, opt-in local GET-only dry-run*. This acceptance is
**not** provider mask compatibility certification and grants **no
execution authority**.

**Windows validation:** On the C3 branch, the operator reported Ruff
lint passing, Ruff formatting passing (`1,695 files already formatted`),
Mypy passing on `711 source files`, focused regression `43 passed`,
full regression `2,862 passed, 1 skipped` (Windows directory symlink
unavailable), clean `git diff --check`, and no tracked local edits.
The only untracked paths were the pre-existing
`docs/VSCS_Architecture_Workflow_Audit_2026-10-24.md`
and `qwen_f5_preflight_result.json`, not modified by C3.

**Operator UI evidence:**
1. The existing project `B5_22_DISPOSABLE_CAP_ACCEPTANCE_UI` and
   Diagnostic Console supplementary Candidate 4 were reopened using
   **Open Saved Candidate Review…**; the stored C2.1 human session
   was restored, showing `4 of 4 fields reviewed`.
2. The `components` failed defect remained
   `protruding_instead_of_recessed`; its reviewed normalized ROI
   was `0.64798851,0.45478723,0.06178161,0.07446809`.
   Fresh C1 inspection used the previously sealed proposal SHA-256
   `76bd6349cdb3b4b399495d5d4c2144f845d155388cb7049a64d8f50f0a966cdc`.
3. Both C2 masks remained `HISTORICAL` relative to that C1 proposal.
   The operator explicitly selected the historical mask with SHA-256
   `1aa336f61f107ffe58d8331ea89caa6b60ee48ef11c15ea1bbe7d7dfa4dedd15`.
   The offline report displayed `Mask matches current proposal: False`,
   `Offline topology inspected: True`, and
   `Loopback GET probe used: False`.
   The managed Qwen graph and experimental masked graph SHA-256
   digests were reported; **no files, jobs or masks were created**.
4. After operator-controlled local ComfyUI GET-only inspection,
   the report showed `Loopback GET probe used: True` and detected
   `LoadImageMask`, `SetLatentNoiseMask` and
   `ImageCompositeMasked`. ComfyUI reported the
   `NVIDIA GeForce RTX 5060 Ti` GPU at approximately `15.9 GiB`
   **total VRAM**, not free VRAM or proven peak inference capacity.
   The current-proposal mask mismatch remained `False`; no
   masked execution was authorized. No separate screenshot evidence
   was supplied for the optional **No** cancellation branch.
5. The operator explicitly confirmed the Candidate 4 image and
   metadata, saved AI evaluation, both C2 PNGs, saved C2.1 JSON,
   accepted CAP requirements and authority, Canon/MASTER status,
   Candidate gallery registration and governed attempt counter
   remained unchanged throughout the offline and GET-only tests.
   The operator also confirmed **no image-generation job and no
   correction output were created**. This is operator-confirmed
   non-mutation rather than an independently executed filesystem audit.

**Findings and remaining blockers:**
- Existing managed XCIC Qwen correction workflow rejects a non-null
  governed mask path. The experimental F5.4.1B topology inspection
  demonstrates structural intent only.
- Historical C2 mask evidence is not compatible with the current C1
  proposal and cannot be adopted silently.
- Presence of ComfyUI mask node classes and their input schemas does
  not establish actual mask polarity, compositing semantics,
  protected-pixel fidelity or provider input compatibility.
- Live masked inference, RTX 5060 Ti 16 GiB peak VRAM fit,
  post-run protected-pixel comparison, C4 output/attempt governance
  and Candidate registration have not been tested or approved.

**Authority boundary:** C3 is closed only for inspection. No
`POST /prompt`, model load, GPU inference, paid API call, staging,
mask override, new Candidate, attempt reservation or CAP/Canon/MASTER
promotion is permitted. Candidate 4's protected final governed
Attempt 2/2 remains untouched. Any later controlled execution
requires a distinct C4 implementation, regression and explicit
operator approval.

## Existing technical baseline and findings

- The managed Qwen derived-reference graph
  `VSCS_Qwen_Derived_Reference_Workflow_API_v2.1.json`
  is an XCIC reference-conditioning workflow, not a governed C2
  candidate-mask workflow. `managed_qwen_correction_job.py` explicitly
  **rejects** `contract.mask_path is not None`, and its writer is
  `XCICSaveReferenceCandidate`, not an accepted C4 corrected Candidate.
- The separate F5.4.1B experimental mask-aware graph includes
  `LoadImageMask`, `SetLatentNoiseMask` and
  `ImageCompositeMasked`. It introduces explicit connections from
  the mask to the sampler latent and post-decode composite. This
  proves only the *intended offline topology* when unchanged;
  it does **not** prove live node schemas, correct runtime polarity,
  deterministic pixel preservation, model success, provenance,
  candidate registration, or fit on 16 GiB VRAM.
- The two existing Diagnostic Console C2 masks (5,580 and 5,225
  editable pixels) are **historical** relative to the separately
  saved C2.1 ROI `0.64798851,0.45478723,0.06178161,0.07446809`.
  **Do not silently select, rebind or submit either one.**
  A new source-bound current-proposal C2 mask would require
  its own explicit preview, operator acknowledgment and exclusive
  evidence save before current-mask compatibility can be assessed.

## New Stage C3 features

1. **Inspect C3 Offline Provider Mask Dry-Run (No Generation)**:
   no network, output files, GPU allocation, model load, input staging
   or attempts. Verifies Candidate source digest, sealed C1
   identity and selected C2 mask against the C2.1 stored-mask
   inventory. Distinguishes matching `CURRENT` masks from
   `HISTORICAL` masks. Uses the existing managed-Qwen
   topology inspector and reuses the F5.4.1B experimental
   mask-graph constructor/validator for read-only topology
   comparison. The derived graph remains entirely in memory.
2. **Probe Local ComfyUI C3 Node Schemas (GET Only)**:
   explicit Yes/No confirmation before contacting
   `http://127.0.0.1:8188`. HTTP loopback GET
   `/object_info` and `/system_stats` only; no redirect
   to other hosts. Checks the presence and declared input names
   of the three experimental mask-node classes and reads
   reported GPU device/total VRAM. It does not check actual
   GPU free headroom/peak VRAM, execute the graph or assert
   mask input correctness from names alone.
3. Both paths present a **C3 diagnostic, never a READY state**.
   The managed Qwen provider does not support this governed
   mask contract yet, and C4 contracts remain missing.
   The report always states that provider compatibility
   and outside-mask pixel preservation are **not verified**.
   No execution-authority flags are set; there is no C3
   candidate-generation action.

## Controlled Windows acceptance — F5.4.2-C3-UI-01

1. **Close VSCS first.** From the VSCS repository
   `D:\VSCS\video_series_studio`, with the existing `.venv`
   activated, use `git status --short`, fetch, switch
   to `phase-f5.4.2-c3-provider-mask-dry-run` and pull.
   Preserve the two existing untracked audit/preflight files.
2. Run Ruff lint, Ruff formatter check, Mypy, focused
   C3/C2.1/C2/C1 regressions, full pytest, diff and status
   checks as specified below. **Stop on failure**.
3. Launch `vscs`. On Dashboard verify the active project is
   `B5_22_DISPOSABLE_CAP_ACCEPTANCE_UI`.
4. Select **Canonical Profiles → Diagnostic Console → Edit
   Selected → Canonical Reference Gallery → Candidate 4**.
   Press **Open Saved Candidate Review…** (never start a new
   paid analysis). From that review click **F5.4.2 Review
   General Visual Correction (No Generation)…**.
5. Select persisted session
   `c21-4-d1aafcc27b2d4e098d835702542261c8.json`
   and click **Resume Selected Human Review**. Verify
   four saved field statuses and the original C2.1 ROI.
   Operator ROI/C2 mask acknowledgments must be unchecked.
6. Select `components`, reinspect the original source ROI,
   check **I inspected the ROI against the source image**,
   click **Inspect Stage C Governed Handoff** and compare
   C1 digest:
   `76bd6349cdb3b4b399495d5d4c2144f845d155388cb7049a64d8f50f0a966cdc`.
   Do not approve a different digest.
7. Click **Find Masks for Current C1 Proposal**. Confirm
   that two C2 masks are marked `HISTORICAL`. Select one
   explicitly, then click **Inspect C3 Offline Provider Mask
   Dry-Run (No Generation)**.
8. Expected offline report: the selected historical mask
   is **not bound** to the current C1; it includes managed
   Qwen workflow digest, derived experimental graph digest
   if inspected, explicit incompatibility and C4 blockers,
   `Loopback GET probe used: False`, with no model loading,
   no GPU work and no files created.
9. Click **Probe Local ComfyUI C3 Node Schemas (GET Only)**.
   Read the notice and choose **No** once: no network
   request or report change should follow. Repeat and choose
   **Yes** only if local ComfyUI is running and you want
   the read-only inventory. A reachable ComfyUI should
   report available mask nodes and device information;
   missing nodes or downtime should yield blockers.
   **Do not interpret available nodes as working mask
   generation support.**
10. **Non-mutation acceptance:** confirm Candidate 4 source
    SHA and metadata, saved AI review, all C2 PNG hashes,
    C2.1 session JSON, CAP accepted requirements/authority,
    Canon/MASTER, governed attempt counter and gallery
    registration remain unchanged. No `.vscs/runtime`
    ComfyUI prompt/queue or corrected Candidate may be
    created by C3.
11. Capture the offline diagnostic, optional GET-only
    diagnostic and any error message, then explicitly
    accept or reject the C3 **diagnostic-only** gate.
    This is **not** acceptance to execute a masked edit.

**Stop rules:** no use of historical mask as current C1 evidence;
no automatic creation of new mask; no ComfyUI POST,
no paid API, no input staging, no model load, no GPU inference,
no Candidate/Canon promotion and no attempt reservation.

## First Windows validation and formatting corrections — 2026-11-16

The operator's initial C3 Windows run confirmed **43 focused tests passed**,
**2,862 full-suite tests passed and 1 skipped**, and **Mypy succeeded on
711 source files**. The skip is the existing Windows symlink-availability
constraint. `git diff --check` was clean; the only untracked paths were
the pre-existing unrelated architecture audit and Qwen preflight output.

Initial static checks identified two Ruff lint warnings (`RUF001`
for an en dash in a timeout message, `SIM102` for nested conditions)
and formatting differences in three C3-touched files. These were
corrected directly on the C3 GitHub branch without changing the
read-only diagnostic intent.

**Post-correction Windows Ruff/format validation remains required.**
The initial regression results demonstrate the functional baseline
but do not substitute for a fresh static check on the new commit.
Operator UI acceptance is still outstanding.

## Windows verification commands

```powershell
cd D:\VSCS\video_series_studio
git status --short
git fetch origin
git switch phase-f5.4.2-c3-provider-mask-dry-run
git pull --ff-only origin phase-f5.4.2-c3-provider-mask-dry-run
git rev-parse --short HEAD
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q tests/test_cap_c3_mask_provider_dry_run.py tests/test_cap_persistent_human_review.py tests/test_cap_human_reviewed_mask_evidence.py tests/test_cap_governed_visual_correction_handoff.py tests/test_cap_qwen_mask_aware_qualification.py tests/test_cap_managed_qwen_correction_job.py
python -m pytest -q
git diff --check
git status --short
```

**Acceptance criteria:** robust refusal of historical/stale masks,
offline graph evidence, opt-in loopback GET inventory (or explicit
unavailability), report of unresolved runtime blockers,
and unchanged source/CAP/attempt records. C3 was operator-accepted
on 2026-11-16 for these diagnostic-only functions; the acceptance
evidence is recorded above. C4 remains separately unauthorized.
