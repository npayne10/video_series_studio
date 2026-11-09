# B.5.26F — Live Guided Qwen Editing Integration: remaining activation gate

Date: 2026-11-09.
Status: **Execution-boundary infrastructure committed; live editing still blocked**.

## Existing acceptance baseline

- F4B2 local-output transport: 2613 tests passed, 1 Windows symlink skip.
- Ruff lint/format and mypy passed, 680 source modules.
- Latest F4B2 output retrieval guards are accepted.

## This increment

- `guided_edit_attempt_journal.py` atomically reserves one slot per original
  reference and correction number using an exclusive file create. The durable
  state remains `RESERVED_OUTCOME_UNKNOWN`; a ComfyUI timeout or ambiguous
  response must **never** trigger an automatic retry. Reservation is
  non-executable, does not submit and does not consume an actual render.
- `guided_edit_candidate_registration.py` independently revalidates the F3
  contract, output content SHA-256, decoded PNG and dimensions, exact
  workflow/contract provenance and operator confirmation before reusing
  `VisualCandidateGenerationService.persist_candidate`. It records the
  original and parent reference IDs, source/report hashes, workflow hash,
  output hash and ComfyUI prompt ID in the regeneration lineage.
- New focused tests cover duplicate reservations, invalid identities,
  registration without consent, stale output, tampered PNG, exhausted
  correction attempts and changed CAP authority.

Both APIs are deliberately **unwired** from the production UI: they are
testable integration primitives, **not** a working edit workflow.

## The decisive missing input

The operator has not yet provided a **real API-format Qwen-Image-Edit-2511
ComfyUI workflow JSON**. The current XCIC production graph is text-to-image.
The actual edit source/mask conditioning, checkpoint/LoRA/encoder/VAE node
connections, sampler inputs and approved SaveImage node ID are unknown.

Do NOT:

- infer that the F4A structural test proves image editing;
- reuse the text-to-image queue loader as a guided edit;
- enable the submit gate or add a live generation button;
- attempt image editing using a fabricated Qwen node map;
- use the final attempt 2/2 as a model-memory experiment.

The 19.12 GB edit checkpoint exceeds the nominal 15.9 GiB device memory.
Actual GPU offloading, model/LoRA compatibility and VRAM behaviour are
unverified.

## Required to finish the *live* integration

1. Export ComfyUI's **Save (API Format)** Qwen-Image-Edit-2511 workflow
   and supply the JSON to the development workflow.
2. Inspect exact node map and `/object_info` schema, validate connected
   source image and optional mask, model, LoRA and output node.
3. Introduce an explicit operator review screen with a SHA-bound,
   one-shot consent action, and block any stale approval.
4. Link the accepted node-map binder, atomic journal, staged inputs,
   ComfyUI submit/wait/output transport and GUI-thread Candidate-only
   registration into one state machine. On unknown outcomes, stop and
   reconcile rather than re-posting.
5. Run mocked integration tests first, then a **separately approved disposable
   hardware test** at low resolution with measured GPU/CPU memory.
6. Perform final full regression and operator acceptance with no automatic
   approval, MASTER promotion or second correction attempt loss.

## Validate this increment

```powershell
cd D:\VSCS\video_series_studio
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q tests/test_cap_guided_edit_candidate_registration.py tests/test_cap_guided_edit_attempt_journal.py tests/test_cap_guided_edit_live_transport.py tests/test_cap_guided_edit_workflow_binding.py tests/test_cap_guided_edit_provider_preflight.py tests/test_cap_spatial_correction_contract.py tests/test_cap_visual_candidate_regeneration.py
python -m pytest -q
git diff --check
git status --short
```

Preserve the untracked architecture audit document. Do not run a
GPU generation during the development acceptance.
