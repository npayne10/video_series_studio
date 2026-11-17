# VSCS F5.4.2 C4B.2A — Disposable GPU Runtime Preparation (No Execution)

**Status:** IMPLEMENTED CANDIDATE — Windows static/focused/full regression and operator non-mutation acceptance PENDING  
**Date:** 2026-11-17  
**Parent:** [C4B.1 acceptance](F5_4_2_STAGE_C4B_ISOLATED_MASK_PROVIDER_QUALIFICATION.md) (offline graph and GET-only inventory operator accepted 2026-11-17)  
**GitHub tracking:** [Issue #53](https://github.com/npayne10/video_series_studio/issues/53)

## 1. Intent and hard boundary

C4B.2 is divided into two separately accepted gates:

- **C4B.2A — disposable runtime preparation** (this implementation):
  source/C1/current-C2 mask validation; creation of an external,
  SHA-sealed, disposable staging directory; offline launch command
  preview; offline provider schema and model choice validation from
  externally supplied GET responses; and read-only pixel comparison
  of an external output. There is **no ComfyUI POST, process launch,
  inference, model load, approval, paid evaluation, attempt claim or
  Candidate registration** in this code.
- **C4B.2B — supervised one-shot GPU validation** (NOT IMPLEMENTED or
  authorized): standalone ComfyUI process isolation, atomic one-use
  launch/submit consent, prompt ID, execution timing and peak VRAM,
  fixed-seed image generation, original-source protected pixel audit,
  semantic quality review, abort/recovery and operator acceptance.

**Never use Diagnostic Console** \`STORY-PRO-B00D168E43\` Candidate 4
or its protected Attempt 2/2 to qualify C4B.2. Its two saved C2
masks remain historical relative to current C1 evidence.
C4B.2A does not relax C4B.1 or governed C4 restrictions.

## 2. Implemented contract

**Module:** \`src/vscs/application/caps/c4b2_disposable_runtime.py\`

\`prepare_c4b2_disposable_bundle(snapshot, proposal, *,
selected_mask_path, protected_project_root, bundle_directory,
seed=1729)\` requires:

1. The supplied source belongs to a **separate disposable VSCS
   project** marked by the file \`.c4b2_disposable_project\` containing
   the exact text \`C4B2_DISPOSABLE_PROJECT\` and a newline.
   The marker is **never created automatically** by VSCS.
2. The disposable project root and provided protected project root
   exist and are disjoint. The **new** bundle root must be external to
   and disjoint from **both** projects. All paths are absolute;
   symlinks and Windows junctions are refused.
3. The source cannot have the known protected Diagnostic Console
   asset ID. Both source and selected C2 mask must already exist
   inside the disposable project, with **CURRENT** C1 and saved C2
   digest/provenance accepted by existing
   \`prepare_c4b_isolated_blueprint\`.
4. Source/mask are ordinary equal-dimension RGB/L PNGs with a binary
   white=edit, black=protect mask containing both kinds of pixels;
   file byte and size limits apply.
5. The target is exclusively created and cannot overwrite an
   existing bundle, source, mask, manifest or graph.

Successful offline preparation exclusively writes:

\`\`\`text
<external_disposable_bundle>/
  input/
    c4b_source_<SHA-prefix>.png
    c4b_mask_<SHA-prefix>.png
  output/                      (EMPTY)
  temp/                        (EMPTY)
  user/                        (EMPTY)
  c4b2_api_graph.json
  c4b2_manifest.json
\`\`\`

The manifest contains SHA-256 of source, mask, original-C1 proposal,
C4B.1 source-bound evidence, reviewed model-template digest, graph
canonical digest and on-disk file digest; it is sealed over all
recorded identities, directory roots and explicit non-execution
flags. \`verify_c4b2_disposable_bundle\` rereads current files and
rechecks the manifest, the baseline ComfyUI graph model selection,
source/mask dimensions, names and cryptographic identities.
**A self-seal is tamper detection, not an authentication signature;
trusted operator-controlled filesystem permissions still matter.**

\`preview_c4b2_isolated_launch\` returns a **command tuple only**.
It never calls \`subprocess\`. It requires operator-selected existing
\`python.exe\` and \`ComfyUI/main.py\`, and a dedicated
**localhost 127.0.0.1 port 8298** (rejects 8188 or other ports).
The command specifies ComfyUI flags:

\`\`\`text
--listen 127.0.0.1 --port 8298
--input-directory <bundle/input>
--output-directory <bundle/output>
--temp-directory <bundle/temp>
--user-directory <bundle/user>
--disable-auto-launch
\`\`\`

These flags are documented by the ComfyUI CLI:
https://github.com/Comfy-Org/ComfyUI/blob/master/comfy/cli_args.py
This preview is **not** executable authorization, confirmation the port
is free, confirmation custom nodes are safe, or proof of models loading.
A separate future runtime must also validate model path read-only
configuration, custom-node permissions, port ownership, job queue,
output provenance and process termination before submission.

\`inspect_c4b2_offline_runtime_schemas(bundle, *,
object_info, system_stats)\` is a **pure function** interpreting
supplied GET \`/object_info\` and \`/system_stats\` snapshots:
checks all compiled graph node names/inputs, core mask-chain output
types (including \`GetImageSize\`'s two INT ports), Qwen UNET/CLIP/VAE
model dropdown selections, scale methods and mask channel choices,
and coherent GPU reported total/free memory. This is **not** actual
ComfyUI inference or 16 GiB memory sufficiency. Input snapshots
must come from an operator-controlled, clearly identified endpoint.

\`audit_c4b2_external_result(bundle, *, result_png)\` verifies a
previously existing RGB PNG *inside the disposable output root*,
preserves original C4B.2 evidence, and calculates:
- exact changed RGB pixels in the **protected black-mask region**;
- changed pixels in the **editable white-mask region**;
- source/mask/result SHA-256.

It **does not** prove ComfyUI generated that image, correctness of
the mask's latent polarity, or semantics of a correction. Even an
all-zero protected change count is only **pixel-difference evidence**.
The returned audit never grants execution, Candidate registration,
CAP authority, Canon/MASTER or corrected image approval.

## 3. Threat and failure cases to reject

- Source project is the protected/active project, or identified as
  \`STORY-PRO-B00D168E43\`.
- Missing, incorrect or symlinked disposable marker.
- Bundle inside either project; existing or relative bundle;
  symlinked/junction path ancestor; overlapping roots.
- Historical/unregistered mask; changed image/ROI/C1/C2 evidence;
  unreviewed/fake source PNG; non-binary mask.
- Staged image, manifest, graph, directories or Qwen model
  baseline changed; unexpected SaveImage sink.
- Incorrect or shared ComfyUI port, invalid executable/script.
- Missing node class/input/output type, wrong model dropdown choice,
  invalid reported GPU memory.
- Pixel audit output outside disposable output, symlinked path,
  wrong output dimensions/format, or any protected pixel changes.

All staging is **fail-closed before any ComfyUI execution**.
There is **no automatic retry** and no production registration.

## 4. Windows engineering validation

Run in the existing activated \`(.venv)\` in PowerShell:

\`\`\`powershell
cd D:\VSCS\video_series_studio
git status --short
git fetch origin
git switch phase-f5.4.2-c4b2-isolated-disposable-runtime-preflight
git pull --ff-only origin phase-f5.4.2-c4b2-isolated-disposable-runtime-preflight
git rev-parse --short HEAD

python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src

python -m pytest -q tests/test_cap_c4b2_disposable_runtime.py tests/test_cap_c4b_isolated_mask_provider.py tests/test_cap_c4_mask_provider_contract.py tests/test_cap_c3_mask_provider_dry_run.py tests/test_cap_persistent_human_review.py tests/test_cap_visual_review_matrix_layout.py
python -m pytest -q

git diff --check
git status --short
\`\`\`

The two existing untracked files
\`docs/VSCS_Architecture_Workflow_Audit_2026-10-24.md\`
and \`qwen_f5_preflight_result.json\` should remain untouched.

**Tests may create temporary synthetic PNGs and isolated bundles
using pytest \`tmp_path\`; they must not write to your real
ComfyUI input/output, production VSCS project or Candidate 4.**
A Windows symlink test may skip if privileges are unavailable.

## 5. Operator acceptance — exact VSCS startup and safe inspection

1. Close VSCS, update the branch and complete all Windows checks
   listed above. Note the tested commit and output.
2. From \`D:\VSCS\video_series_studio\` with \`(.venv)\` active,
   launch **\`vscs\`** and confirm the expected active acceptance
   project on the Dashboard. **Do not create a new mask, re-evaluate
   AI quality or run any ComfyUI job for Candidate 4.**
3. Go to **Canonical Profiles → Diagnostic Console → Edit Selected →
   Canonical Reference Gallery → Candidate 4**, and open the
   **saved** AI review if needed. The C4B.1 controls remain
   inspection/GET-only; **C4B.2A adds no production UI button**.
4. Inspect C2.1's existing saved review and two historical masks.
   Check source/ROI/evaluation and governed attempt count against
   the accepted C4B.1 baseline; do not change any record.
5. Close the dialog and VSCS normally. Run the C4B.2A
   regression tests above, which construct synthetic current
   C1/C2 evidence in pytest temporary directories, exercise
   disposable staging and simulated pixel comparisons.
6. Confirm no new ComfyUI process or \`POST /prompt\`, no paid
   AI evaluation, no corrected image, no attempt reservation,
   no Candidate/gallery registration, and no changes to Candidate 4,
   its metadata, both existing C2 PNGs, saved C2.1 review,
   CAP/Canon/MASTER authority or saved AI evaluation.
7. Provide the Windows command output and **operator
   non-mutation attestation**. This is the **C4B.2A offline
   acceptance gate**, not permission for C4B.2B inference.

Do **not** manually run the previewed ComfyUI command or submit
\`c4b2_api_graph.json\`. Its launch command and staged images are
test artifacts until a separately accepted one-shot execution
controller and explicit GPU authorization exist.

## 6. Forward C4B.2B gate — separately approved GPU inference

Still required, **not yet implemented or authorized**:
- Isolated localhost service process whose PID/port and
  input/temp/output/user directories are verified from the running
  process, with read-only model directories.
- Genuine current C1/C2 disposable source/mask and a reviewed
  single-run execution-specific consent, atomic durable job claim
  and no retry without a new approval.
- Before execution: installed graph schema and model hashes,
  GPU/system memory readiness, prompt cost/output bounds and
  cancellation/recovery route.
- One actual Qwen masked GPU edit on an explicitly disposable
  image, capturing peak VRAM, wall time, prompt ID, log errors,
  output filenames and SHA-256 provenance.
- Actual mask polarity/edit-effect evidence (not only
  static node names), zero changed RGB outside reviewed
  mask, human quality evaluation of inside-mask correction,
  and verified non-mutation of all production state.
- Explicit operator acceptance **before** any governed C4
  integration, Candidate correction attempt, paid review
  or H3-MF1 work.

**C4B.2A is not completed until Windows and operator acceptance
are recorded. C4B.2B GPU runtime is still unimplemented;
this file must not be treated as a GPU success report.**
