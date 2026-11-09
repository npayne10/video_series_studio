# Phase B.5.26F F5 — Controlled GPU Acceptance

Date: 2026-11-09
State: **PREPARED — NOT HARDWARE ACCEPTED**
Hardware under test: Windows, RTX 5060 Ti 16 GB, local ComfyUI.
Baseline accepted before F5: Ruff and Mypy clean; 2647 passed, 1 environmental skip.

## Safety and scope

F5 is a two-gate operator workflow: (A) read-only hardware and model
readiness; (B) one deliberately authorized disposable image edit.

Do **not** use the original production source Candidate or its remaining
correction attempt 2/2 for hardware qualification. The first GPU test
must use a disposable project, a distinct Candidate and a review report
that legitimately permits controlled correction.

The new `qwen_f5_preflight.py` checks the checked-in graph, /system_stats,
node inventory and selected checkpoint/LoRA/encoder/VAE choices, and
`nvidia-smi` name/memory/driver inventory. It makes **GET requests only**,
does not load the GPU model and never reserves a correction attempt.
Its `PREFLIGHT_READY_NO_GPU_INFERENCE` state is **not F5 acceptance**.

The Qwen edit checkpoint is ~19.12 GB on disk, so actual inference on
16 GB VRAM may require offload. Available VRAM or file size alone does
not prove that a successful edit can or cannot run.

## Gate A — offline/read-only checks

In the VSCS Python venv, after pulling this branch:

```powershell
cd D:\VSCS\video_series_studio
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q tests/test_cap_qwen_f5_preflight.py tests/test_cap_managed_qwen_edit_inspection.py tests/test_cap_managed_qwen_correction_job.py tests/test_cap_managed_qwen_worker_execution.py tests/test_cap_managed_qwen_model_inventory.py
python -m pytest -q
git diff --check
git status --short
```

Start ComfyUI normally at `http://127.0.0.1:8188`, then run:

```powershell
python -m vscs.application.caps.qwen_f5_preflight
nvidia-smi
```

A return code of 0 and `PREFLIGHT_READY_NO_GPU_INFERENCE` confirm that
the read-only checks passed. Error status `BLOCKED` must stop GPU testing.
Retain the output as acceptance evidence. A system with multiple GPUs
requires the operator to ensure ComfyUI actually uses the RTX 5060 Ti.

## Gate B — one disposable hardware test

Only proceed after Gate A and full regression pass.

1. Create/open a disposable VSCS project and a disposable CAP asset.
   Create its legitimate supplementary image Candidate, failed semantic
   review and approved Draft CAP fields through existing UI paths.
2. Keep the production Candidate and its attempt 2/2 untouched.
3. Start a second PowerShell terminal to observe `nvidia-smi -l 2`;
   capture GPU memory use, maximum observed temperature and any offload
   evidence from the ComfyUI console. Stop sampling with Ctrl+C.
4. In the disposable project, open the controlled correction dialog,
   verify source Candidate ID, correction attempt, approved fields and
   visual source. Click **Generate ONE Qwen Image-Edited Candidate
   (Source Conditioned)**.
5. Review the warning. **No** means no job; **Yes** submits ONE job.
6. On success, capture the prompt ID, generated output dimensions,
   ComfyUI generation duration, observed peak GPU memory, output image
   and new supplementary Candidate ID.
7. Confirm the generated Candidate is distinct from its source and has
   the expected accepted visual edits. Review separately; no automatic
   MASTER/Canon promotion.
8. On failure, record the error and journal, inspect ComfyUI history
   before any retry. Never delete the reservation to force a repeat.

The test may be slow, offload to system RAM or fail due to model memory;
report the observed outcome rather than claiming hardware acceptance.

## Acceptance classification

- **PASS**: Node/model preflight passes, one generation completes,
  output passes PNG/provenance checks and is registered as exactly one
  supplementary Candidate, source unchanged, no MASTER/Canon changes,
  no duplicate submission, useful visual correction and memory/time
  evidence captured.
- **PARTIAL / INVESTIGATE**: Qwen generates but takes excessive time,
  visibly ignores constraints, runs only with unacceptable offloading,
  or Candidate registration/quality review cannot be confirmed.
- **BLOCKED / FAIL**: Missing node/model, CUDA OOM, transport failures,
  workflow errors, invalid/missing output, stale CAP authority, duplicate
  attempt, unsafe output or unsupported mask.
- **UNTESTED**: only the read-only check and regression tests ran.

## Evidence to send back

Read-only preflight JSON, `nvidia-smi` output, ComfyUI console log
covering generation, the VSCS completion/error dialog, new Candidate
reference ID (if any), and elapsed time. Omit sensitive absolute paths
or unrelated project data if sharing publicly.

## Important limits

The checked-in Qwen v2.1 edit graph has no validated spatial mask input.
F5 validates source-conditioned editing only. The once-only journal
is deliberately fail closed: ambiguous POST outcomes must be manually
reconciled, not automatically retried.
