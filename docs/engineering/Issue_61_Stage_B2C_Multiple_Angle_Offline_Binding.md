# Issue #61 Stage B.2C — Multiple-angle offline binding

Status: **offline source binding implemented; no execution authority**.

## Reviewed input

Neill exported `qwen_multiple_angles_reviewed_api.json` on 2026-11-25.
Source SHA-256:
`054F211803BFE3C382E3E98AA80E2C7241A6B6CFABD2C5B9EA20FC67B64169BC`.

The reviewed graph has 26 nodes: Qwen FP8 Mixed `219:161`, dedicated
multiple-angles LoRA `219:220`, Lightning `219:153`, `CameraAngle` `221`,
camera prompt `219:151`, and `SaveImage` `2`. The source `cyber_genesis.png`
is demonstration material, **not** canonical authority.

The checked-in qualification template
`src/vscs/workflows/image/VSCS_Qwen_Multiple_Angles_Qualification_API_v1.json`
replaces that demo source with `__VSCS_PENDING_MASTER_BINDING__` and the
generic output prefix with `__VSCS_QUALIFICATION_ONLY__`. The existing
v2.1 governed Qwen workflow remains unchanged.

## Offline compilation

`MultipleAngleOfflineCompiler` resolves the real locked MASTER using the
existing derived service's fail-closed authority check. It records the MASTER
SHA-256, its governed reference ID, and the qualification-template SHA-256.
The draft graph binds `XCICQwenReferenceJobLoader` output 0 to both camera
preview and image conditioning. This loader/camera interoperability is a
*proposal* that still needs qualification, not a proven live transport.

Provisional camera settings (not yet empirically calibrated):

| View | Horizontal | Vertical | Zoom |
|---|---:|---:|---:|
| Front | 0 | 0 | 5 |
| Right | 90 | 0 | 5 |
| Rear | 180 | 0 | 5 |
| Left | 270 | 0 | 5 |

The compiler returns a graph/queue **in memory**, with an unresolved
`__VSCS_UNQUALIFIED_QUEUE_FILE__` and output placeholders. It never submits
to ComfyUI, downloads models, writes project files, or authorises generation.

## Qualification blockers

1. Verify that camera azimuth maps to the intended physical asset face.
2. Verify the custom loader's image output works with CameraAngle.
3. Validate node/model inventory and 16 GB GPU feasibility.
4. Implement governed unique staging, output validation, prompt/job provenance,
   duplicate protection, MASTER freshness recheck and failure reconciliation.
5. Complete a separately governed live test and human identity/viewpoint QC.

## Windows validation

```powershell
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q tests/unit/test_multiple_angle_binding.py tests/unit/test_qwen_multi_angle_qualification.py tests/integration/test_derived_reference_generation_pipeline.py
python -m pytest -q
git diff --check
git status --short
```

Operator: open `C4B2B_DISPOSABLE_GPU_01` in read-only inspection mode,
verify MASTER remains Approved/Locked, and verify `front.png`/`front_2.png`
remain preserved and unapproved. Confirm the second Candidate's QC rejection
separately; it is not implied by this change. Recompare persisted SHA-256
baseline after read-only inspection. No new Candidate, MASTER, reference
library or planning-file change is expected. Unexpected mutation is FAIL.

**STOP before any GPU run.** PR #66 stays Draft; Issue #61 remains open.
