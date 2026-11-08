# Phase B.5.26F F4 — Guided Qwen Image Editing Provider Integration

Date: 2026-11-08.
Status: **F4A fail-closed provider preflight committed. F4B live editing not implemented or approved.**

## Why this is staged

F1 established that the existing XCIC image workflow is text-to-image, not
image-editing. F2 established that ComfyUI advertises Qwen-Image-Edit-2511
FP8-mixed and matching LoRA/encoder/VAE files on a RTX 5060 Ti 16 GB.
The edit checkpoint is approximately 19.12 GB on disk, larger than available
GPU VRAM; CPU offloading and actual peak memory have not been validated.
F3 provides an immutable, non-executable source/mask/workflow contract.
No *connected Qwen editing API graph* has been delivered or inspected.

Submitting the current text-to-image workflow as an "edit" would be misleading
and consume the final attempt. F4 is therefore split into inspectable gates.

## F4A — implemented

`vscs.application.caps.guided_edit_provider_preflight`:

- Revalidates F3 sealed evidence through the existing CAP correction service.
- Restricts the chosen model checkpoint to a trusted ComfyUI models directory.
- Confirms it is a Qwen-Image-Edit-2511 safetensors file, without loading it.
- Parses API-format workflow nodes and follows upstream dependencies to check
  for source-image-to-sampler and Qwen-edit-conditioning-to-sampler links.
- Checks decode-to-output presence, fresh empty latents, optional mask node
  presence, and model filename selection in the API graph.
- Retains a permanent blocker for per-request source/mask staging, actual
  VRAM execution and human consent until F4B proves them.
- Returns `execution_authorized = False` always; no network requests,
  upload, queued prompt, model downloads, file writes, or new Candidate.

This is a *structural preflight*, not proof that a workflow will edit images
correctly: classes, image encoding, conditioning semantics, output retrieval,
VRAM and provenance still require acceptance on the actual exported workflow.

## F4B required before enabling generation

1. Operator supplies an **API-format** Qwen-Image-Edit-2511 workflow exported
   from the real ComfyUI instance, with explicit source input, optional mask,
   correct checkpoint and LoRA, image-edit text encoder and PNG output.
2. Verify node schemas with read-only `/object_info` and local checkpoint paths;
   choose tested offloading strategy for RTX 5060 Ti 16 GB.
3. Implement isolated input staging to ComfyUI's trusted input directory,
   validate mask binding and workflow parameters with strictly bounded node
   mappings. No unconditional workflow rewriting.
4. Implement one **explicitly consented** local job with output image hash,
   source/workflow/mask/checkpoint provenance, idempotence, no automatic retry,
   and a race-safe recheck before Candidate-only registration.
5. Add GUI disclosure of source image/mask/constraints, checkpoint/VRAM
   limitations and separate Yes/No approval; do not reuse the legacy
   text-to-image button for guided editing.
6. Complete mock integration regression and a separately authorized disposable
   hardware test. Preserve original, current Candidate and two-attempt ceiling.

## Validation commands

```powershell
cd D:\VSCS\video_series_studio
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q tests/test_cap_guided_edit_provider_preflight.py tests/test_cap_spatial_correction_contract.py tests/test_cap_visual_candidate_regeneration.py
python -m pytest -q
git diff --check
git status --short
```

F4A is accepted only after automated checks pass. It is **not** a green light
to start a GPU generation. The remaining Candidate 2/2 attempt is reserved.
