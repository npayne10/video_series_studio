# Phase B.5.26F F3 — Governed Spatial Correction Contract

Status: **GitHub implementation committed, local validation pending.**
Date: 2026-11-08.

## Purpose and boundaries

B.5.26F F1 verified that the current XCIC Qwen text-to-image workflow contains
no source-image, mask, or ControlNet path. F2 verified local ComfyUI GET
connectivity, RTX 5060 Ti 15.9 GiB total VRAM (14.8 GiB free after restart),
and advertised Qwen-Image-Edit-2511 FP8-mixed, Lightning LoRA, Qwen VL encoder
and VAE. The operator also confirmed the files exist locally, including a
19.12 GB edit checkpoint. **None of these facts establish executable editing
or VRAM fit.**

F3 defines a *read-only* provenance contract for a candidate edit; it does not
add a provider, prompt submission, UI execution button, API charge or GPU job.

## Evidence contract

Module: `src/vscs/application/caps/spatial_correction_contract.py`.

`prepare_spatial_contract(service, plan, ...)` calls the existing
`CandidateRegenerationService.verify_current` to reuse CAP fingerprints,
failed semantic-review evidence, exact attempt limits and lineage. It binds:

- Project-scoped source Candidate/reference, original reference and attempt.
- Source PNG SHA256 and saved semantic review SHA256.
- Reviewed CAP specification and review fingerprints and accepted fields.
- Optional 8-bit grayscale PNG mask with **exactly matching source dimensions**,
  stored only in the relevant CAP's `.metadata/spatial_masks` directory.
- A parseable API-format workflow within an explicitly trusted workflow root,
  its SHA256, workflow identity, and a model **identifier**.
- Deterministic SHA256 of the serialized evidence record to detect accidental
  or hostile modifications after contract creation.

`verify_spatial_contract` rechecks the stored evidence checksum, current
governed plan, path containment, source/report/workflow/mask content hashes,
and mask geometry. The seal is an *integrity digest*, **not a cryptographic
signature or an operator authorization token**.

Only reviewed CAP fields are copied to the contract. Untrusted semantic
evaluator prose remains advisory and is not compiled into authorized edits.

The contract explicitly returns `execution_authorized == False`. It is not
serialised to, or loaded from, production authority. F4 must add a separate
explicit user consent step, an actual validated edit graph, model checkpoint
file/identity checks, mask preview, source-preservation behaviour, and safe
single-Candidate persistence. A model identifier alone **does not** attest
the 19.12 GB checkpoint, nor does an API-format workflow prove source and
mask links are connected.

## Safety rules

- No cross-project file, symlink file, missing source, stale image or report.
- No stale CAP specification/review, unreviewed fields or attempt over the
  current two-attempt budget.
- No mask with changed pixels, incompatible geometry or wrong channel format.
- No changed workflow file after operator inspection.
- No automatic attempt consumption, image generation, cost or approval.
- No MASTER/Canon or Shot status changes.
- Preserve Candidates 1 and 2 and the remaining correction attempt (2/2).

## F3 acceptance commands

```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation

python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q tests/test_cap_spatial_correction_contract.py tests/test_cap_visual_candidate_regeneration.py tests/test_cap_spatial_candidate_guidance.py tests/test_cap_guided_edit_capability_assessment.py
python -m pytest -q
git diff --check
git status --short
```

F3 has no production UI change: acceptance consists of deterministic
positive/negative contract tests and a clean full regression suite. The next
phase, F4, can integrate a distinct consented guided-edit provider only after
actual graph, model-memory and provenance preflight acceptance.
