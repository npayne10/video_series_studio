# Issue #61 Stage B.2 — Viewpoint-control qualification

Status: implementation and offline evaluation only; **no GPU generation authority**.

## Evidence and failure classification

Real attempt 2: `CAP-PRP-002` Front, Qwen v2.1, seed 1, ComfyUI prompt
`3499ebff-8c37-42e6-94f0-de72c3d1a751`, runtime job
`db6a0768-05c2-4839-9677-49ab7f00bff9`.

`front_2.png` operator-supplied SHA-256:
`6D5F7250E1E3657617A59ABA192C248A2E296FC133E3A3C482316C68E40F676E`.

Visual QC: **FAIL** — oblique Front with left side/top visible and separate
maintenance workstation in the frame. The replacement remains Candidate;
rejection is not considered persisted until separately verified.

The runtime queue confirms an approved MASTER source and a prompt containing
`beside, but physically separate from, the maintenance workstation`.
The current managed Qwen workflow uses image-conditioned editing and image
latents but no explicit camera-angle composition node or multiple-angle LoRA.
The source-conditioned camera angle is therefore not reliably overridden by
ordinary text instructions. Qwen's generation is probabilistic; no fixed
camera-geometry accuracy is implied by a multiple-angle LoRA either.

## B.2A — Isolated prompt policy

The derived generator excludes *recognized external scene relationships* from
the provider prompt, while retaining the persisted CAP Canon unchanged.
Excluded sentences are recorded in the new Candidate's notes, not sent to
Qwen (including not in its negative prompt). Internal component relationships
such as buttons beside a dial remain eligible. This is a deliberately bounded
deterministic filter, **not** a universal natural-language scene parser.
Anything not confidently classified as external remains subject to human QC.

For this test's exact description, the workstation relationship is excluded
while the housing/display sentence remains. Regression tests cover both this
case and an internal component relationship to avoid silent geometric loss.

## B.2B — Multiple-angle capability audit

ComfyUI's official **Generate Multiple Angles with 3D Camera Node** template
documents a camera-angle composition control and a dedicated Qwen Image Edit
2511 multiple-angles LoRA. It is an alternative **candidate** provider, not
an approved replacement for `qwen.derived-reference.v2.1` yet.

The offline auditor is
`vscs.application.caps.qwen_multi_angle_qualification`. It reads only:

1. A manually exported, reviewed ComfyUI API-format workflow JSON.
2. A saved `/object_info` JSON snapshot.
3. The installed ComfyUI `models` directory.

It reports the workflow SHA, camera-angle nodes, absent node classes, and
the presence of model and multiple-angle LoRA files. It always reports
`generation_authorized=false`, even if those checks are satisfied. VRAM fit,
source integrity, exact view mapping, identity preservation, unique outputs,
governed approval, and per-view QC require a separate provider qualification.

### Operator — offline only

From the project virtual environment:

```powershell
python -m vscs.application.caps.qwen_multi_angle_qualification `
  --workflow "D:\VSCS\Issue61_Audit\qwen_multiple_angles_reviewed_api.json" `
  --object-info "D:\VSCS\Issue61_Audit\comfyui_object_info.json" `
  --model-root "D:\ComfyUI\ComfyUI_windows_portable\ComfyUI\models"
```

Export the workflow from the installed ComfyUI template only after reviewing
its source and dependencies. Capture `/object_info` through a **GET** request,
not through workflow submission. The supplied paths must actually exist;
the audit returns blockers if they do not. The tool makes no HTTP calls and
does not download models, modify project data, or start ComfyUI jobs.

**STOP** before installing custom nodes, downloading a LoRA, modifying the
managed Qwen graph, or generating another Candidate. Review the audit and
obtain the next implementation/qualification decision first.

## Protected acceptance boundary

Do not modify either rejected/pending-rejection Front image, approved MASTER,
original human reviews or historical reference library to force readiness.
No video generation. PR #66 remains Draft; Issue #61 remains open until
real-world derived-view and persistence acceptance.
