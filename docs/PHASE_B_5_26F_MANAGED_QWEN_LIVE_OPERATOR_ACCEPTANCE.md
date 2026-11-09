# Phase B.5.26F — Managed Qwen Image Editing Activation (Operator Acceptance)

Date: 2026-11-09
Status: **GitHub code committed; local regression and first GPU acceptance NOT YET completed**.

## Implementation

The repository already provides the true source-conditioned Qwen-Image-Edit
2511 graph:
`src/vscs/workflows/image/VSCS_Qwen_Derived_Reference_Workflow_API_v2.1.json`.

New dedicated CAP correction services:

- `managed_qwen_edit_inspection.py`: confirms the exact checked-in
  custom-loader/source-conditioning/model/LoRA/sampler/output node links.
- `managed_qwen_correction_job.py`: patches an in-memory copy of that graph
  with a governed queue, a supplementary source Candidate instead of MASTER,
  CAP-reviewed positive/negative prompt, and isolated output path. Masks
  are NOT supported by this managed graph and are refused.
- `managed_qwen_model_inventory.py`: compares the exact workflow
  checkpoint, Lightning LoRA, text encoder and VAE against read-only
  ComfyUI `/object_info` model choices BEFORE attempt reservation.
- `managed_qwen_worker_execution.py`: worker-safe, single local ComfyUI
  submission after source, report and graph SHA-256 checks, installed-node
  preflight, and atomic once-only reservation. It also reconstructs the
  approved API graph and queue to detect in-memory tampering before POST.
  Captures and decodes output
  PNG. Never touches CAP/SQLite or registers an output in the worker.
- `guided_edit_candidate_registration.py`: GUI-thread post-render CAP
  authority recheck, exact SHA/PNG/provenance validation, Candidate-only
  creation and correction lineage. Records the actual executed Qwen
  positive prompt rather than falsely recording the old text-to-image
  correction prompt.
- `cap_visual_candidate_regeneration.py`: new independent button
  **Generate ONE Qwen Image-Edited Candidate (Source Conditioned)**.
  It prepares the F3 contract, validates the graph, explains the VRAM
  limitation, asks explicit Yes/No, compiles the exact job on GUI thread,
  runs the worker, rechecks CAP on GUI thread, and registers a supplementary
  Candidate only after success. The legacy text-only button remains
  available but cannot start if a Qwen journal already reserved this
  correction slot.

The Qwen managed graph uses the custom `XCICQwenReferenceJobLoader` and
`XCICSaveReferenceCandidate`. It is NOT the prior text-to-image API graph
and does not use the generic `SaveImage` HTTP-history retriever.

## Model resource and runtime limitations

- Qwen-Image-Edit-2511 FP8-mixed checkpoint is approximately 19.12 GB
  on disk, larger than nominal 16 GB VRAM. No successful GPU inference
  has been demonstrated on the operator's RTX 5060 Ti.
- Model CPU/GPU offloading, current ComfyUI node inventory and runtime
  output quality must be verified on the operator's machine.
- A failed or ambiguous submission permanently reserves its correction
  number pending manual reconciliation; **never retry automatically**.
- The new path edits using source-image conditioning, not a spatial mask.
  Mask-driven editing remains blocked until a vetted graph supports it.
- A GPU output, even if visually plausible, does not approve a MASTER,
  Canon or production reference. Semantic review remains separate.

## First operator test (do not consume the final attempt accidentally)

1. Pull GitHub changes, run all static and focused/full regression checks.
2. Start local ComfyUI at `http://127.0.0.1:8188`, confirm installed
   custom XCIC Qwen loader and saver nodes and model checkpoint/LoRA.
3. In VSCS open the CAP Manager, select the intended supplementary
   Candidate that has a failed semantic quality report.
4. Open controlled corrected local Candidate review.
5. Confirm the source reference, accepted CAP constraints and attempt
   number. Inspect read-only spatial information first if desired.
6. Click **Generate ONE Qwen Image-Edited Candidate (Source Conditioned)**.
   The application first validates the source and managed workflow.
7. Read the explicit GPU VRAM/offloading and once-only reservation warning.
   Choose **No** to exit without submission. Choose **Yes** only for an
   approved real hardware test: it can submit an actual ComfyUI GPU job.
8. On success review the new supplementary Candidate; run offline
   technical and separately consented semantic review. No promotion is
   automatic.
9. On error, inspect `<project>/Canonical Assets/<asset>/.metadata/
   guided_edit_attempts/root_<id>_attempt_<n>.json`,
   `<project>/.vscs/runtime/comfyui/queues` and
   `<project>/.vscs/runtime/comfyui/jobs`. Do not repeat GPU submission
   until the uncertain state is reconciled.

## Regression

```powershell
cd D:\VSCS\video_series_studio
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q tests/test_cap_managed_qwen_edit_inspection.py tests/test_cap_managed_qwen_correction_job.py tests/test_cap_managed_qwen_live_correction.py tests/test_cap_managed_qwen_worker_execution.py tests/test_cap_managed_qwen_model_inventory.py tests/test_cap_guided_edit_candidate_registration.py tests/test_cap_guided_edit_attempt_journal.py tests/test_cap_guided_edit_live_transport.py tests/test_cap_guided_edit_workflow_binding.py tests/test_cap_guided_edit_provider_preflight.py tests/test_cap_spatial_correction_contract.py tests/test_cap_visual_candidate_regeneration.py
python -m pytest -q
git diff --check
git status --short
```

Previously accepted baseline: **2625 passed, 1 skipped**. Twenty-two
new tests are expected in the four new test modules. The count is
provisional until the actual Windows regression run.
Preserve `docs/VSCS_Architecture_Workflow_Audit_2026-10-24.md` untracked.
