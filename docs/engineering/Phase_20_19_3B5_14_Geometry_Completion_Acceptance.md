# Phase 20.19.3B.5.14 — Spatial Geometry Completion & Multi-Asset Validation Acceptance

Status: Initial implementation committed; local Windows test run and UI acceptance pending.

## Delivered
- Completely in-memory, isolated acceptance fixtures in `src/vscs/application/caps/spatial_acceptance.py`. The fixtures never open, update, or save VSCS projects, CAPs, Stories, or image assets and make no model/provider calls.
- Three reproducible two-sibling scenarios using proposed millimetre AABB geometry in one frame: `valid`, `collision`, and `missing_geometry`.
- `run_spatial_acceptance` reuses the production `assess_spatial_graph` and `build_spatial_review_report` validators. No special bypass or alternate geometric algorithm.
- A separate **Spatial Geometry Acceptance (Offline)** button and scenario selector in the existing Approved Story → CAP Batch Review dialog. It runs independently of CAP discovery or an eligible cached proposal.
- Results open in the existing resizable, read-only Spatial Continuity Review dialog and carry statuses `verified_within_model`, `conflict`, and `unverified`. Synthetic assets are named `TEST-LOC-001`, `TEST-PRP-001`, and `TEST-PRP-002`.
- Tests assert both resolved siblings in the valid scenario, a named pairwise sibling collision in the conflict scenario, one unresolved sibling in the missing geometry scenario, deterministic replay, and availability of the UI control without a paid proposal.

## Governance and limitations
- This phase is an **acceptance harness**, not a persistent geometry editing or completion mechanism for live CAPs. It makes the existing physical validator demonstrable without polluting the Golden Path audit. Do not treat synthetic acceptance values as story evidence or approved geometry.
- Within-model AABB fit is not physical certification; rotations, complex occupied shapes, physics, movement, door clearance, and real installation constraints remain unsupported.
- No OpenAI calls, approval changes, H3 execution, image generation, project writes, or user audit modifications. H3 live execution hold remains ON HOLD.

## Operator acceptance
1. Pull latest GitHub changes and restart VSCS.
2. Open disposable Episode Audit project, then **Canonical Profiles → Story → CAP Batch Review**.
3. At the bottom of the Batch dialog, select **Valid**, then click **Spatial Geometry Acceptance (Offline)**. The report should read `VERIFIED_WITHIN_MODEL`, two resolved siblings, zero findings.
4. Close and choose **Collision**, repeat. Expect `CONFLICT` and the pair `TEST-PRP-001` / `TEST-PRP-002`.
5. Close and choose **Missing Geometry**, repeat. Expect `UNVERIFIED` and `missing_child_geometry`. No CAP is created in any scenario.
6. Do not use Generate / Regenerate Using AI (Paid).

## Local test commands
```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_14_spatial_acceptance.py tests/test_phase_20_19_3b5_14_spatial_acceptance_dialog.py -v
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```
