# Issue #61 Stage B.2D — Provider compatibility and controlled-execution preflight

Status: **offline provider-interface investigation implemented; GPU execution NOT authorised**.
PR #66 remains Draft. This stage does not modify approved references or emit candidates.

## Boundary and evidence

The Stage B.2C compiler resolves the locked MASTER and returns an in-memory,
non-executable qualification graph. The new
`vscs.application.caps.multiple_angle_provider_preflight` module checks
the graph against a separately saved, read-only ComfyUI `/object_info`
snapshot. It checks:

- Node-class availability and provider-advertised input names.
- Upstream graph references and advertised output-port bounds.
- Type compatibility between advertised upstream outputs and downstream inputs.
- Enum/widget values, including installed checkpoint/LoRA selection names.

The result is an audit report, **not** transport acceptance. The command does
not contact ComfyUI, load weights, queue prompts, write projects or run GPUs.
The CLI supports inspecting the **reviewed API template**; it cannot prove the
compiled custom `XCICQwenReferenceJobLoader` path works in the active runtime.
The Python function can also inspect an in-memory B.2C compiled graph, which
adds the custom loader's advertised interface to the audit.

## Operator: collect and run offline evidence

On Windows, with the existing local ComfyUI service running, keep a previously
saved, dated `/object_info` snapshot in `D:\VSCS\Issue61_Audit`. If necessary,
a new GET-only snapshot may be saved:

```powershell
$auditRoot = "D:\VSCS\Issue61_Audit"
Invoke-WebRequest -Uri "http://127.0.0.1:8188/object_info" `
    -OutFile "$auditRoot\comfyui_object_info_B2D.json" -UseBasicParsing
```

Read-only template compatibility:

```powershell
python -m vscs.application.caps.multiple_angle_provider_preflight `
    --workflow "src\vscs\workflows\image\VSCS_Qwen_Multiple_Angles_Qualification_API_v1.json" `
    --object-info "D:\VSCS\Issue61_Audit\comfyui_object_info_B2D.json"
```

If the existing `comfyui_object_info.json` snapshot is used instead, supply
its actual path and record its capture date. Save the JSON report and snapshot
hash in the audit folder using the operator's approved audit procedure. Do not
submit the graph through `/prompt` or change any model paths.

## Acceptance gates

| Gate | Status or required evidence |
|---|---|
| Reviewed B.2C source/MASTER hash and locked authority | Retained; must be freshly checked before any subsequent GPU step |
| Installed ComfyUI node interfaces and model selectors | B.2D offline report; missing/mismatched fields fail closed |
| Custom MASTER job loader to CameraAngle compatibility | Unverified until controlled provider qualification |
| Camera-angle azimuth convention and identity preservation | Unverified until visual qualification |
| RTX 5060 Ti 16 GB VRAM/inference stability | Unverified; installed model files do not establish GPU fit |
| Unique staging, non-overwrite output, job lineage and failure recovery | Not yet implemented |
| GPU qualification consent | Separately required; **not granted by offline preflight** |

Do not treat zero missing node types as authorization to generate images.
Static interface compatibility does not confirm that arbitrary ComfyUI nodes
accept the actual image and prompt data at runtime.

## Automated validation

```powershell
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q `
    tests/unit/test_multiple_angle_provider_preflight.py `
    tests/unit/test_multiple_angle_binding.py `
    tests/unit/test_qwen_multi_angle_qualification.py `
    tests/integration/test_derived_reference_generation_pipeline.py
python -m pytest -q
```

Operator read-only acceptance: check MASTER approval/lock and SHA-256;
verify `front.png` and `front_2.png` preserved and not approved; separately
confirm whether `front_2.png` has been QC rejected. Compare historical audit
baseline for canonical image bytes, reference records and planning data.
Unexpected mutation is a STOP. Do not merge PR #66 or close Issue #61.
