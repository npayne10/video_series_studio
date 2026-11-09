# Phase B.5.26F — Qwen editing activation feasibility

Date: 2026-11-09.
Status: **Managed image-edit graph found and inspected structurally. CAP correction execution remains blocked.**

## New finding

The development branch already contains an image-conditioned Qwen Image Edit
2511 workflow, separate from the older XCIC text-to-image creator:

`src/vscs/workflows/image/VSCS_Qwen_Derived_Reference_Workflow_API_v2.1.json`

It is registered as `qwen.derived-reference.v2.1` and driven by
`ComfyUIDerivedReferenceProvider`. Its existing UI targets generation of
derived views from an approved **locked MASTER**, not repair of an
unapproved supplementary Candidate.

Confirmed nodes in its API-format graph:

| Role | Node ID and type |
|---|---|
| Source queue | `171` `XCICQwenReferenceJobLoader` |
| Source image scale | `170:160` `FluxKontextImageScale` |
| Qwen edit conditioning | `170:149` and `170:151` `TextEncodeQwenImageEditPlus` |
| Source latent | `170:156` `VAEEncode` |
| Model checkpoint | `170:161` `UNETLoader` |
| Lightning LoRA | `170:153` `LoraLoaderModelOnly` |
| Sampling | `170:169` `KSampler` |
| Decode | `170:158` `VAEDecode` |
| Output | `9` `XCICSaveReferenceCandidate` |

`managed_qwen_edit_inspection.py` checks these actual node IDs and selected
links and rejects modifications, including a disconnected source path, model
mismatch and unreviewed output. Tests use the real checked-in graph.

## Why simply enabling the existing provider is unsafe

1. The provider requires a **locked MASTER**, whereas B.5.26F corrects
   a supplementary visual Candidate under a failed semantic CAP review.
2. Its custom queue and output node use the derived-reference job schema;
   F4B1 currently binds `LoadImage` and literal edit prompt inputs,
   which are **not** the nodes in this graph.
3. The F4B2 result retriever expects a `SaveImage` history output.
   The actual graph instead uses a custom filesystem writer.
4. F3 hash/attempt verification, current CAP authority, operator consent,
   persistent once-only submission and Candidate-only registration have
   not been connected to this loader.
5. The RTX 5060 Ti 16 GiB has not yet demonstrated the 19.12 GB edit
   checkpoint with necessary offload memory.

Therefore no new submit button or GPU job was activated. The final
correction attempt 2/2 remains reserved.

## Candidate-correction queue adapter (implemented offline)

`src/vscs/application/caps/managed_qwen_correction_job.py` prepares
the real custom-loader queue and patched API graph from the F3 contract,
without writing a queue or submitting a prompt. It maps the governed
supplementary source to `reference_inputs[0]`, accepted CAP constraints
to `positive_prompt`, the reviewed correction negative prompt, the
seed, and a unique isolated output path. It checks the immutable
workflow hash and refuses mask-based corrections because this graph
has no accepted mask input. Five regression tests exercise the checked-in
graph, safe binding, path isolation, drift and duplicate outputs.

This **does not** yet activate live execution. The existing derived-reference
provider remains MASTER-only. The offline correction adapter must
be connected to a new explicit operator-consent dialog and a submission/
reconciliation state machine. No existing CAP generation button is
repurposed as an image-edit request.

## Required next implementation

Build a **dedicated candidate-correction adapter** for the managed graph,
not the derived MASTER provider. It must validate and patch only the
XCIC queue `reference_inputs[0]` to the F3-authorized source image,
and `positive_prompt` / `negative_prompt` from reviewed CAP values;
use isolated output paths, exact file/PNG/hash checks and propagate
F3/source/workflow/job provenance. It must never accept free-form semantic
findings as canonical instructions.

Complete the consent dialog and once-only journal/submit/reconcile state
machine; prove custom loader/output node installation through local
`/object_info`, confirm VRAM feasibility through a disposable test,
and register only one supplementary Candidate after a post-render
CAP authority check. No automatic retry or MASTER promotion.

## Validate current discovery increment

```powershell
cd D:\VSCS\video_series_studio
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q tests/test_cap_managed_qwen_correction_job.py tests/test_cap_managed_qwen_edit_inspection.py tests/test_cap_guided_edit_candidate_registration.py tests/test_cap_guided_edit_attempt_journal.py tests/test_cap_guided_edit_live_transport.py tests/test_cap_guided_edit_workflow_binding.py tests/test_cap_guided_edit_provider_preflight.py tests/test_cap_spatial_correction_contract.py tests/test_cap_visual_candidate_regeneration.py
python -m pytest -q
git diff --check
git status --short
```

Accepted previous baseline: **2625 passed, 1 skipped**. This increment
adds five new tests, so expect 2630 passed/1 skipped if no other tests changed.
