# B.5.26F F4B2 — Local ComfyUI Guided Editing Transport

Status: **partial F4B2 transport and regression tests committed; execution not enabled**.
Date: 2026-11-09.

## Accepted baseline

F4B1 validated on Windows: Ruff check clean, Ruff format 1619 files,
Mypy 679 modules, focused 59 passed/1 skipped, full regression 2599
passed/1 skipped. Symlink test skipped due to Windows privilege limitations.

## Implemented in F4B2 increment

`src/vscs/application/caps/guided_edit_live_transport.py` provides:

- Credential-free, HTTP-loopback-only output retrieval.
- Exactly one PNG from an explicitly selected SaveImage output in a
  ComfyUI history response, rejecting traversal/subfolders/alternate types.
- Strictly bounded image download, full PNG decode/verify and SHA-256
  output provenance, with source contract and workflow digests attached.
- No automatic CAP Candidate registration or status changes.
- `GuidedEditSubmissionGate` which **always refuses POST**. It must
  not be bypassed by a truthy execution_authorized property.

Regression tests mock output transport; they do not reach ComfyUI or GPU.
No additional use of the existing text-to-image XCIC renderer.

## Remaining blockers for live integration

The project still has no operator-exported Qwen-Image-Edit-2511
**API-format** graph. F4A always reports the missing staging/VRAM/consent
hold, and F4B1 does not claim its bindings match the live installation.
Therefore this F4B2 increment cannot legitimately be declared live-ready.

Before enabling submission:

1. Import the real API-format graph and validate all node types and
   edit-source conditioning against the running ComfyUI `/object_info`.
2. Freeze the source image, mask, checkpoint selection, workflow SHA,
   explicit output node ID and exact executable prompt.
3. Verify file/graph/model identity, owner/project and CAP authority
   before staging, immediately before POST and after rendering.
4. Implement one-shot operator consent scoped to the exact frozen
   request, with durable uncertain-submission handling and no retries.
5. Perform a disposable source-image edit model test, measuring
   RTX 5060 Ti 16 GB VRAM/offload behaviour (the checkpoint is 19.12 GB).
6. Validate output identity, quality and approved Candidate-only
   persistence using the existing, governed registration path.
7. Obtain separate operator approval for F5 hardware acceptance.
   No Canon or MASTER approval may occur from a provider response.

## Validation commands

```powershell
cd D:\VSCS\video_series_studio
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q tests/test_cap_guided_edit_live_transport.py tests/test_cap_guided_edit_workflow_binding.py tests/test_cap_guided_edit_provider_preflight.py tests/test_cap_spatial_correction_contract.py tests/test_cap_visual_candidate_regeneration.py
python -m pytest -q
git diff --check
git status --short
```

Preserve untracked `docs/VSCS_Architecture_Workflow_Audit_2026-10-24.md`.
The remaining correction attempt 2/2 must remain reserved.
