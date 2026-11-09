# B.5.26F F5.1 — Dual Workflow Inspection and Hardware Acceptance UI

Date: 2026-11-09
Status: **Committed for local regression / Qt UI acceptance, not GPU accepted**

## User-visible change

The controlled Candidate correction dialog now has two distinct read-only
controls and retains the two original generation methods:

1. **Inspect Both Workflows (No Generation)** — identifies the externally
   configured legacy XCIC text-to-image API graph and independently validates
   the checked-in managed Qwen-Image-Edit-2511 source-conditioned API graph.
   Their findings are separated. Legacy lack of a source-image path does
   **not** mean the Qwen edit graph lacks one. The managed graph's
   reference-conditioning is verified; mask/inpainting is not.
2. **Check Qwen F5 Hardware Readiness (No Generation)** — runs the existing
   read-only F5 preflight against the configured local ComfyUI loopback URL
   and `nvidia-smi` through the established non-cancellable progress
   runner. It displays ComfyUI health, model/node inventory, GPU name,
   reported total/free memory, driver version, workflow SHA-256 and
   any blockers. A visible status line reports **NOT CHECKED**,
   **PREFLIGHT READY**, **BLOCKED**, or **ERROR**.
3. **Generate ONE Text-Only Candidate (No Spatial Control)** remains a
   separate operation with its existing confirmation and persistence rules.
4. **Generate ONE Qwen Image-Edited Candidate (Source Conditioned)** now
   refuses the attempt until the same dialog has a successful F5 preflight,
   its workflow SHA still matches the sealed F3 graph, and the user
   separately confirms the GPU submission.

For a Candidate at attempt **2/2**, a separate unchecked acknowledgment
warns that this is the final correction attempt and recommends a fresh
disposable Candidate lineage for F5 hardware testing. The box must be
checked before proceeding to the normal Yes/No GPU confirmation.

The preflight **does not** load a model, reserve an attempt, generate an
image, contact paid providers, or approve Canon. Even after preflight,
successfully generating and registering a Candidate is not equivalent to
hardware acceptance until image quality, timing and resource usage are
reviewed.

## Acceptance procedure

1. Pull changes to the development branch and run static checks, focused
   tests, full regression and repository checks.
2. Open the disposable project `B5_22_DISPOSABLE_CAP_ACCEPTANCE_UI` and
   its controlled correction dialog. This project's selected Candidate 2
   is at correction attempt **2/2**; do **not** use it for the first
   hardware test unless intentionally consuming its final attempt.
3. Click **Inspect Both Workflows (No Generation)**. The dialog should
   show a *legacy text-to-image* section with its lack of guided control,
   followed by a *managed Qwen image-edit* section with verified connected
   source conditioning and an explicit no-mask limitation.
4. Click **Check Qwen F5 Hardware Readiness (No Generation)**.
   The status label should change to **PREFLIGHT READY** if ComfyUI
   and installed models remain available, or show **BLOCKED/ERROR** with
   cause. The result must still state **NO GPU INFERENCE**.
5. Verify that cancelling/closing the dialog has generated no ComfyUI
   prompt and no new `guided_edit_attempts` journal file.
6. For the first real GPU inference, prepare a **fresh disposable**
   Candidate and legitimately failed semantic review. Repeat preflight
   in that dialog. Only then explicitly acknowledge any final-attempt
   warning and opt in at the separate Yes/No generation confirmation.
7. Record actual ComfyUI console output, observed VRAM/offloading,
   generation duration, source and resulting Candidate IDs, output PNG,
   visual changes and preserved Canon status.

## Windows validation

```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q tests/test_cap_qwen_f5_dual_inspection.py tests/test_cap_qwen_f51_ui.py tests/test_cap_qwen_f5_preflight.py tests/test_cap_visual_candidate_regeneration.py tests/test_cap_managed_qwen_edit_inspection.py tests/test_cap_managed_qwen_worker_execution.py
python -m pytest -q
git diff --check
git status --short
```

Previously accepted baseline: **2,655 passed, 1 Windows symlink skip**.
F5.1 adds four dual-inspection tests and six Qt UI checks. The expected
new total is **2,665 passed, 1 skip**, subject to Windows confirmation.

Do not modify the untracked
`docs/VSCS_Architecture_Workflow_Audit_2026-10-24.md`.
