# Phase B.5.26F F5.2 — Operator-Controlled ComfyUI GPU Cache Release

Date: 2026-11-10
Status: **Implemented in GitHub — local acceptance and regression pending**

## Why

The operator observed that ComfyUI retained approximately 13 GiB of
GPU memory after using models. Manually calling
`POST http://127.0.0.1:8188/free` with
`{"unload_models": true, "free_memory": true}` succeeded.
A subsequent RTX 5060 Ti `nvidia-smi` snapshot showed
**1,841 MiB used of 16,311 MiB**, or approximately **14,470 MiB free**.
A successful HTTP response does not guarantee that all GPU allocations
are reclaimed: desktop applications, CUDA contexts and other processes
continue to use memory.

## User interface

The controlled Candidate correction dialog now includes:

**Release ComfyUI GPU Memory (Idle Queue Only)**

- Not automatic. Requires a separate **Yes/No** operator confirmation.
- Checks `GET /queue` immediately before the release. A running or
  pending job prevents the POST. Unknown queue schemas also block.
- Sends exactly one local `POST /free` with model unload and cache
  release flags, with bounded network timeouts and redirects disabled.
- Does not submit to `/prompt`, reserve a correction attempt, mutate CAP
  evidence, register a Candidate, or approve a MASTER.
- Disables the cache-release action while it is in progress, and
  invalidates the prior F5 readiness snapshot regardless of success.
- On completion, informs the operator that only request acceptance was
  confirmed; click **Check Qwen F5 Hardware Readiness (No Generation)**
  to measure the remaining VRAM and redo node/model readiness validation.
- Fails safely on a busy queue, unreachable ComfyUI, invalid response,
  unsupported endpoint or uncertain outcome.

**Important concurrency caveat:** `GET /queue` followed by `POST /free`
is not a cross-client atomic transaction. A different client may enqueue
work between the two HTTP requests. Operators must still use this button
when ComfyUI is idle and avoid other clients submitting work concurrently.
For strict cross-client coordination, a server-side lock or queue-drain
control would be required.

## Acceptance tests

New `test_cap_comfyui_memory_release.py` covers consent, an empty queue,
running/pending queues, invalid queue responses, remote address
rejection, redirects, failure responses, malformed JSON and timeout.
Additional Qt tests in `test_cap_qwen_f51_ui.py` cover operator
decline, successful request with readiness reset and busy-queue errors.

## Windows validation

```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q tests/test_cap_comfyui_memory_release.py tests/test_cap_qwen_f51_ui.py tests/test_cap_qwen_f5_preflight.py tests/test_cap_visual_candidate_regeneration.py
python -m pytest -q
git diff --check
git status --short
```

Baseline before F5.2: **2,665 passed, 1 skipped**. The 12 backend
tests and 3 new Qt tests would bring the full count to **2,680 passed,
1 skipped** if all pass and no other tests changed. This is a
provisional expectation, not a validated outcome.

Keep the operator-owned untracked architecture audit and prior
`qwen_f5_preflight_result.json` untouched.

## Manual UI checks

1. Start ComfyUI and open the controlled Candidate regeneration dialog.
2. Click **Release ComfyUI GPU Memory (Idle Queue Only)** and choose
   **No**. Verify no `/free` request was sent.
3. Click again and choose **Yes** while the ComfyUI queue is empty.
   Verify an accepted request message; no generated image or CAP change.
4. Verify the F5 readiness label says **RECHECK REQUIRED**.
5. Click **Check Qwen F5 Hardware Readiness (No Generation)**.
   Record free VRAM and readiness. A successful release cannot prove
   a 19.12 GB edit checkpoint will run inside the 16 GiB GPU.
6. Test the busy-queue refusal only with a disposable, controlled
   workload; never cancel a production queue for this test.
