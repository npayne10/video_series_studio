# B.5.26F F2 — ComfyUI Guided-Editing Capability and Hardware Assessment

Date: 2026-11-08
Status: GitHub implementation committed; local Ruff/Mypy/pytest and Windows assessment pending.

## Evidence and decision

F1 operator inspection successfully read:
`D:\VSCS\XCIC\Xorix_Qwen_XCIC_Image_Creator_v1.0_api.json`.
It found exactly one XCIC queue loader, but **no** source-image edit,
mask/inpaint, or spatial-control node in the configured text-to-image workflow.
F1 did not consume the remaining controlled correction attempt.

F2 adds a separate diagnostic that checks which nodes, advertised model
options and GPU resources **the currently running ComfyUI reports**. It
does not assume that the user's installed ComfyUI matches reference
documentation or that a model is compatible merely because it is named.

## Implementation

`python -m vscs.application.caps.guided_edit_capability_assessment`

Uses **only** loopback `GET /system_stats` and `GET /object_info` with a
bounded timeout, and refuses non-loopback HTTP or redirects. Extracts total
and free VRAM when present, relevant editing/image/control node names,
and model-choice hints supplied by node schemas. The text report explicitly
states that guided execution is NOT ready. No `POST /prompt`, model downloads,
external websites, GPU jobs, reference writes, or attempts are involved.

Environment configuration is resolved through the existing
`XCICConfiguration.load()`, including `VSCS_COMFYUI_URL`.

The F2 diagnostic is independent of the F1 no-generation UI control.
Do not claim that the optional reference path in `XCICCoreJob` supplies
actual image-to-image conditioning: connectivity and edit-specific workflow
graph still require verification.

## Local operator commands

```powershell
cd D:\VSCS\video_series_studio
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q tests/test_cap_guided_edit_capability_assessment.py tests/test_cap_spatial_candidate_guidance.py
python -m pytest -q
python -m vscs.application.caps.guided_edit_capability_assessment
git diff --check
git status --short
```

Run ComfyUI normally before executing the assessment. Copy the text
report to the development conversation. Any saved report is operator-owned:
the diagnostic itself does not persist files.

## F2 evidence required for a model recommendation

1. GPU name and available/total memory as reported by ComfyUI, plus
   observed inference memory for the proposed workflow later.
2. Local installed node names and advertised model options.
3. A separately exported API-format *image editing* graph showing connected
   source-image path, optional mask/ControlNet control and output.
4. Exact model checkpoint size/precision, memory strategy, model licensing,
   and Windows/RTX 5060 Ti 16 GB compatibility.
5. An explicit fail-closed path from immutable source Candidate to edited
   non-authoritative Candidate, without changing the existing two-attempt budget.

**No guided-model or spatial-correction execution is authorized by F2.**
No image quality improvement has been established.

## Next decision

After reviewing the Windows evidence, select a suitable local editing
model/workflow (Qwen-Image-Edit or another compatible option) or explicitly
record that none is suitable. Only then proceed to F3 provenance, mask/layout
and operator-consent contracts. F4 implements execution separately.
