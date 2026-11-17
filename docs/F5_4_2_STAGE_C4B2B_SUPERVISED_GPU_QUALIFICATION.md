# VSCS F5.4.2 C4B.2B — Supervised Disposable Qwen GPU Qualification

**Status:** WINDOWS ENGINEERING VALIDATION PASSED — protected-state operator check and live GPU acceptance PENDING  
**Parent:** [C4B.2A formally accepted, 2026-11-17](F5_4_2_STAGE_C4B2_DISPOSABLE_RUNTIME_PREFLIGHT.md)  
**Branch:** `phase-f5.4.2-c4b2b-supervised-disposable-gpu-qualification`  
**Tracker:** [Issue #53](https://github.com/npayne10/video_series_studio/issues/53)

## 1. Scope and hard stop

C4B.2B adds a **separate, opt-in command-line qualification controller**
`src/vscs/application/caps/c4b2b_supervised_gpu.py`. It can launch a
standalone ComfyUI process and submit **one** masked Qwen graph *only after*
all fresh local preconditions and an exact operator confirmation phrase.
It is **not wired to the VSCS production UI**, C4 correction attempts,
Candidate registration, Canon/MASTER authority, or paid AI review.

**No GPU run has been performed or authorized by these commits.** First
complete Windows static/unit regression and review this process and the
specific disposable bundle/model inventory. An implementation commit alone
is not permission to execute `--execute` or POST to ComfyUI.

Protected Diagnostic Console `STORY-PRO-B00D168E43`, Candidate 4, the two
historical C2 masks, saved evaluation/C2.1 review, and governed attempt 2/2
are never used as input. Stage C4B.2A *requires a different disposable
project with a CURRENT C1/C2 mask* and writes a new external bundle.

## 2. Implemented supervised contract

### Read-only `--inspect`

The operator first prepares a **new** accepted C4B.2A bundle from a
disposable VSCS project/source and current C1/C2 mask. `--inspect` then:

1. Re-verifies the C4B.2A seal, source/mask, compiled API graph, current
   managed template and disjoint directory roots.
2. Refuses an existing C4B.2B reservation, failure, result or log. Input
   must contain *only* the staged source and mask; output/temp/user must
   still be empty.
3. Verifies the operator-provided local Qwen UNET, CLIP and VAE paths
   match compiled graph model names, are nonempty regular files, and
   are outside both projects and the bundle. Streams SHA-256 of each
   model without reading the full 19+ GiB weights into memory.
4. Uses accepted C4B.2A launch preview with dedicated
   `127.0.0.1:8298`, independent input/output/temp/user paths, and
   `--disable-auto-launch`; never invokes a subprocess or HTTP request.
5. Returns an exact **one-use consent phrase** bound to the bundle seal,
   command and model path/hash evidence. It does not authorize execution.

`--inspect` cannot prove model loading, performance, GPU availability,
custom-node trust, actual mask polarity, native ComfyUI permissions,
or that the selected model directories are operating-system read-only.

### Gated `--execute`

Only with a separately reviewed `--confirm-one-gpu-run` flag **and**
the full exact `--consent-phrase` can the controller:

1. Hash the same model files again, verify a protected Diagnostic Console
   asset subtree snapshot (bounded, read-only), and refuse port 8298
   collisions or any reused bundle.
2. Atomically and durably create `c4b2b_execution_reserved.json`
   **before** launching any ComfyUI process. The reservation is never
   removed automatically; any ambiguous failure consumes the bundle.
3. Launch the accepted dedicated ComfyUI command, write its stdout/stderr
   to `c4b2b_comfyui.log`, and use `psutil` to verify that **the child PID**
   owns the listener bound to `127.0.0.1:8298`.
4. Read bounded, no-redirect localhost `GET /object_info`,
   `GET /system_stats` and `GET /queue`. Re-run C4B.2A exact class,
   port-type and model dropdown compatibility. Require an idle queue,
   coherent NVIDIA memory, and at least **8 GiB reported free**.
5. Recheck bundle, model hashes, output emptiness and process ownership
   immediately before **exactly one** `POST /prompt`; no upload to port
   8188, no automatic retry, and no side effects through VSCS authority.
6. Poll the matching `GET /history/<prompt_id>` until completion or a
   bounded timeout (default 30 minutes), sampling reported free VRAM.
   Reject provider errors, missing/extra output images, unsafe file
   references, prefixes or dimensions.
7. Audit an output only inside the isolated bundle using the original
   source + binary mask, require **zero changed protected RGB pixels**
   and **at least one changed editable pixel**, and re-hash the local
   models and protected Diagnostic Console asset subtree.
8. Stop the child process, then exclusively write a result with output
   hash, prompt ID, timing and sampled free VRAM. It explicitly leaves
   `human_semantic_accepted=null` and all Candidate/CAP authority false.

If any stage fails, a durable `c4b2b_execution_failure.json` is written
where possible; the original one-use reservation remains, and the child
is stopped. Do not delete this evidence or try again with the same bundle.

**Limitations:** This is a Python/user-level process boundary, not an OS
sandbox. Custom nodes could have external side effects, and this controller
does not prove model directories are enforced read-only by Windows ACLs.
The protected-asset hash snapshot does not cover every external database
or transient file. Reported VRAM samples are **not true peak process VRAM**.
Human inspection and a separate non-mutation attestation remain mandatory.
No automatic network isolation, remote API cost guarantee, or silent
retry is claimed.

## 3. Windows engineering validation — perform BEFORE any live run

Start in PowerShell with `(.venv)` active. Close VSCS and leave the
protected Diagnostic Console unchanged. No GPU, paid API or ComfyUI
execution is triggered by any command in this section.

```powershell
cd D:\VSCS\video_series_studio
git status --short
git fetch origin
git switch phase-f5.4.2-c4b2b-supervised-disposable-gpu-qualification
git pull --ff-only origin phase-f5.4.2-c4b2b-supervised-disposable-gpu-qualification
git rev-parse --short HEAD

python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src

python -m pytest -q tests/test_cap_c4b2b_supervised_gpu.py tests/test_cap_c4b2_disposable_runtime.py tests/test_cap_c4b_isolated_mask_provider.py tests/test_cap_c4_mask_provider_contract.py tests/test_cap_c3_mask_provider_dry_run.py tests/test_cap_persistent_human_review.py tests/test_cap_visual_review_matrix_layout.py
python -m pytest -q

git diff --check
git status --short
```

The two known untracked files
`docs/VSCS_Architecture_Workflow_Audit_2026-10-24.md` and
`qwen_f5_preflight_result.json` must remain untouched. Windows symlink
tests may skip because of local privilege limitations.

### Safe UI inspection after tests

1. From activated `(.venv)` run `vscs`.
2. Dashboard: confirm active acceptance project
   `B5_22_DISPOSABLE_CAP_ACCEPTANCE_UI` (do not silently switch).
3. **Canonical Profiles → Diagnostic Console → Edit Selected →
   Canonical Reference Gallery → Candidate 4**.
4. **Open Saved Candidate Review...** (never select the action that
   charges for a fresh evaluation), then **F5.4.2 Review General Visual
   Correction (No Generation)...**. Inspect the existing C2.1 saved
   review, ROI and two **HISTORICAL** masks. Do not save/change a mask,
   click execution buttons or re-evaluate quality.
5. Confirm Candidate 4, original saved evaluations, both masks, CAP/
   Canon/MASTER/gallery, and attempt count **2/2** remain unchanged.
   Confirm no ComfyUI job, paid AI evaluation or corrected Candidate.
6. Close VSCS normally using Close/Cancel rather than Save/Apply.

**C4B.2B adds no new production UI control.** These UI steps only check
that running synthetic unit tests has not modified the protected state.

## 3A. First Windows static validation and corrective follow-up

**Operator report, 2026-11-17:** Ruff lint found two import/optional
`psutil` attribute issues; Ruff format found two line-wrapping
differences in the C4B.2B source; strict Mypy found three errors
because a filtered `vram_free` list still had type `Any | None`.
No focused/full pytest result was submitted for this first run.

**Correction committed:** Apply Ruff's precise import order and
line wraps; call the optional module's attribute directly with an
explicit `Any` annotation for dynamic import; and construct a
typed `list[int | float]` only after `isinstance` narrowing and
explicit boolean exclusion. The runtime memory gate continues to
require coherent nonnegative NVIDIA free-VRAM values and fails
closed if none are present. No GPU submission or production
Candidate/CAP behavior was changed.

**Status:** Re-pull the branch, re-run the entire Windows static,
focused, full pytest and integrity sequence in Section 3. The
operator non-mutation gate still applies; no live run is authorized.

## 3B. Windows static and automated regression — PASSED, 2026-11-17

The operator pulled the corrected C4B.2B branch and reported:

- `python -m ruff check .`: **All checks passed**.
- `python -m ruff format --check --no-cache .`: **1,710 files already formatted**.
- `python -m mypy src`: **Success, no issues in 715 source files**.
- Focused C4B.2B/C4B.2A/C4B.1/C4/C3/C2.1/matrix regression:
  **66 passed, 1 skipped**.
- Full `python -m pytest -q`: **2,914 passed, 2 skipped**.
- `git diff --check`: clean.
- `git status --short`: only the two unrelated, pre-existing untracked
  `docs/VSCS_Architecture_Workflow_Audit_2026-10-24.md`
  and `qwen_f5_preflight_result.json`; these were untouched.

Both skips reflect unavailable Windows symlink privileges, not
C4B.2B failures. **Windows engineering validation is ACCEPTED.**
These tests use fake processes/network and do **not** establish
real ComfyUI launch, GPU model loading, mask-polarity correctness,
runtime fidelity, true peak VRAM or operator non-mutation acceptance.

**Remaining gates:** (1) Safe UI inspection and explicit operator
confirmation of unchanged Candidate 4/masks/C2.1/CAP/Canon/MASTER
and protected governed Attempt 2/2; (2) a genuinely separate
disposable source + CURRENT C1/C2 mask, verified model paths and
read-only process/permission readiness; (3) a fresh one-use
operator execution consent; (4) one actual supervised GPU test
followed by human semantic and non-mutation acceptance.

**Do not use `--execute` yet.**

## 4. Future supervised live readiness — DO NOT EXECUTE YET

After all engineering checks are accepted, the operator must produce a
**different disposable project** with an actual reviewed CURRENT C1/C2
mask and stage it using the accepted C4B.2A API. The two Diagnostic
Console historical masks are invalid here. We must record:

- The exact disposable project name, source PNG, C1 proposal ID,
  current saved C2 mask SHA, and new external C4B.2A bundle path.
- The actual ComfyUI embedded `python.exe`, `ComfyUI/main.py` and
  installed UNET/CLIP/VAE file paths. These are operator-selected,
  never guessed by code.
- Installed node options on port 8298, dry-run model fingerprints,
  existing ComfyUI processes, GPU free/total memory, and Windows model
  directory ACL / custom-node trust limitations.
- The exact one-use consent phrase shown by `--inspect`, which is
  **not a reusable authorization token**. The plan changes when any
  bound path or hash changes.

Only a **fresh, explicit** operator decision after review of those
results can permit the single supervised `--execute` on the test bundle.
If the GPU test succeeds, human review must confirm *meaningful* edits
inside the white mask as well as preserved outside pixels. Capture
prompt ID, execution logs, elapsed time and true peak GPU VRAM if
measurable using independent tooling; otherwise mark it unknown.

**No automatic registration or production correction may follow.**
C4B.2B must be formally accepted in a separate operator sign-off before
proceeding to governed Stage C4 integration or H3-MF1.
