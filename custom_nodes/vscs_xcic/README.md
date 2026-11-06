# VSCS XCIC queue loader for ComfyUI

Provides the missing **XCICQueueJobLoader** required by VSCS's existing
`XCICCoreRenderer` and `Xorix_Qwen_XCIC_Image_Creator_v1.0_api.json`.
It uses only the Python standard library.

## Install

Run from a VSCS PowerShell terminal:

```powershell
.\scripts\Install-VSCS-XCIC-ComfyNode.ps1 -ComfyUIRoot "D:\ComfyUI\ComfyUI_windows_portable\ComfyUI"
```

Restart the actual running ComfyUI server to load the new Python module. Then:

```powershell
.\scripts\Install-VSCS-XCIC-ComfyNode.ps1 -VerifyOnly
```

The checker should report `XCICQueueJobLoader : INSTALLED`. It checks the
live ComfyUI `/object_info` registry rather than merely finding files.

The existing workflow also uses `XCICSaveImage`, `ComfySwitchNode` and
primitive nodes, but these were confirmed installed in the user's active instance.
Do not replace them or create duplicate versions. If your ComfyUI runs on another
port, specify `-ComfyUIUrl`; if your installation path differs, specify
`-ComfyUIRoot`.

## Node contract

Inputs:

- `queue_file` (STRING): absolute path to the VSCS queue JSON
- `job_index` (INT): zero-based job index
- `quality_mode` (STRING): expected job mode (currently `standard`)

Outputs (positions 0–8):

```text
0 positive_prompt       STRING
1 negative_prompt       STRING
2 width                 INT
3 height                INT
4 seed                  INT
5 steps                 INT
6 cfg                   FLOAT
7 candidate_directory   STRING
8 candidate_filename    STRING
```

The loader reads schema_version 1.0, verifies job_count, index, output
directory and filename, and fails closed on malformed data. It reads the
current queue each ComfyUI execution, disabling stale node-output cache.
It does not create images or write the queue; those duties belong to the
existing provider and `XCICSaveImage` respectively.

## B.5.26 acceptance

1. Run `python -m pytest -q tests/test_xcic_queue_job_loader.py -v`.
2. Run Ruff lint, Ruff formatting, Mypy and the full regression suite.
3. Verify the live ComfyUI node registry after restart.
4. Select the already reviewed Engineering Control Room CAP, then
   `Prepare Visual Identity…` and explicitly authorise one local candidate.
5. Verify Automation Progress, a valid PNG, the candidate provenance
   and a supplementary Candidate in the existing reference gallery.

The locally rendered image is **not a ChatGPT MASTER**; no Canon,
reference or Production Approval is granted by installing this node.
