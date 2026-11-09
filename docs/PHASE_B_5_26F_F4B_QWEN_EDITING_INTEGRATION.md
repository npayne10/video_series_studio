# Phase B.5.26F F4B — Qwen Guided-Editing Integration

Status: **F4B1 offline workflow binding and input staging implemented in GitHub; local validation and live F4B2 pending**.
Baseline before F4B1: 2,587 passing tests, Ruff/Mypy clean.

## Architectural evidence

- F3 governs image, review report, approved CAP fields, optional PNG mask,
  workflow identity, checked hashes, original reference and retry ceiling.
- F4A performs read-only Qwen image-edit model/graph structural preflight
  but deliberately refuses any execution.
- XCIC Core is a text-to-image queue-loader renderer and must never be
  repurposed as if it consumed source image edit conditioning.
- Real ComfyUI Qwen-Image-Edit-2511 API-format export has **not** yet been
  provided. Exact node IDs and schema cannot be invented safely.

## F4B1 implemented

Module `src/vscs/application/caps/guided_edit_workflow_binding.py`:

1. `GuidedEditNodeMap` explicitly names source image loader and Qwen edit
   prompt inputs plus optional mask inputs. No heuristic guessing of node IDs.
2. `bind_guided_edit_workflow` revalidates the F3 contract, checks the
   source workflow digest, copies the graph into memory, and binds only
   safe staging filenames and reviewed CAP values. Untrusted vision report
   prose cannot become an edit instruction.
3. `stage_guided_edit_inputs` revalidates F3, requires the actual trusted
   ComfyUI `input` folder, rejects symlinked input root, copies immutable
   PNG bytes under unique non-overwriting names, verifies SHA-256 and
   leaves project images and masks unchanged.
4. `GuidedEditStagedInputs.cleanup` removes only staged files whose bytes
   still match the expected source/mask digests.
5. `GuidedEditBoundWorkflow.execution_authorized` always returns False.
   No ComfyUI POST, no provider activation, no image output, no new
   Candidate, no attempt consumption and no Canon/MASTER promotion.

`tests/test_cap_guided_edit_workflow_binding.py` tests source and mask
binding, pure graph copying, stale hashes, unsafe staging names, incorrect
input directory, cross-file modifications and symlink protection.

## Required to complete F4B2

**Operator input required:** export a real Qwen-Image-Edit-2511 ComfyUI
workflow in **API Format** and attach the JSON. The workflow must show
actual links between selected edit checkpoint, source image, Qwen edit
conditioning, Lightning 4-step LoRA, sampler, VAE and SaveImage; include
mask path if spatial inpainting is intended.

Once available, implement and test against actual node schemas:

- real input/output node IDs, dynamic prompt and image binding and
  complete source-to-sampler validation;
- checkpoint, encoder, LoRA, VAE and workflow inventory, memory/offload
  strategy for RTX 5060 Ti 16 GB; no guaranteed 16 GB fit;
- local-only ComfyUI transport with explicit preview and operator
  consent, once-only submission and output/PNG/hash verification;
- source-preserving supplementary Candidate persistence, post-render
  authority recheck, historical correction lineage and bounded retries;
- disposable, operator-authorized hardware acceptance under F5.

F4B1 is not evidence of working image-edit inference. The final
correction attempt (2/2) remains reserved.

## Local validation

```powershell
cd D:\VSCS\video_series_studio
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q tests/test_cap_guided_edit_workflow_binding.py tests/test_cap_guided_edit_provider_preflight.py tests/test_cap_spatial_correction_contract.py tests/test_cap_visual_candidate_regeneration.py
python -m pytest -q
git diff --check
git status --short
```

Preserve existing untracked
`docs/VSCS_Architecture_Workflow_Audit_2026-10-24.md`.
