# Phase 20.19.3B.5.15 — Governed Draft CAP Geometry Completion & Placement Workspace

Status: Initial structured editor implementation in GitHub. Automated and operator UI acceptance pending.

## Implemented
- **Edit Geometry (Structured, Draft Only)** in the existing Story CAP Draft form opens a dedicated editor.
- Operator-authored coordinate frame, x/y/z origin in mm, three positive dimensions in mm, and named 3D anchors are edited with controls rather than writing raw JSON.
- Existing typed `CAPGeometry` validation rejects missing frames, invalid values, and duplicate anchor names. The resulting typed geometry is written to the existing on-screen Draft geometry JSON field only after validation.
- **Save Review & Continue** persists the edited geometry and cross-asset dependency/anchor placement text in the project-scoped *unapproved proposal cache*, not a CAP record. Operators can reopen it through **Review Cached Proposal** without provider calls. Final CAP creation remains a separate explicit gate.
- The existing deterministic spatial-graph analysis opens its read-only report after the Story CAP Draft stage; it identifies missing parent/child geometry, invalid containment, and sibling collisions using already saved target CAP specifications.
- Offline geometry acceptance fixtures are unchanged.

## Scope limits
- No direct editor for target child CAPs from the parent report; each Draft CAP proposal is reviewed independently.
- No visual coordinate canvas, 3D scene, arbitrary rotations, interactive drag-and-drop placement or new transform table.
- Incomplete source geometry is not inferred or automatically approved. Stored target geometry is read-only during parent review.
- All operations remain Draft-only, no OpenAI regeneration, no H3 generation, no Canon approval, no Golden Path fixture mutation.

## Local verification
```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_15_geometry_editor.py -v
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```

## UI acceptance
1. Open the existing cached Engineering Control Room CAP proposal. Do **not** choose paid Generate / Regenerate.
2. Click **Edit Geometry (Structured, Draft Only)**. Enter a *deliberate, operator-chosen* frame and bounds as a temporary proposal, and a named anchor. Confirm. Inspect the generated Draft geometry JSON.
3. Click **Save Review & Continue**, review the resulting local spatial report, cancel subsequent CAP Detail Decisions. Reopen **Review Cached Proposal**; ensure the geometry and dependencies remain. Restart VSCS and recheck for persisted cache behavior.
4. Treat the entered bounds as unapproved operator proposals, not evidence-based dimensions; do not create a CAP during acceptance.
