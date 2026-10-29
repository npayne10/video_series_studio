# Phase 20.19.3B.5.16 — Automated Cross-Asset Dependency & Spatial Geometry Proposal Engine

Status: **Initial offline-first increment committed. Local quality gates and operator UI acceptance pending.**

## Delivered
- An evidence-bound, deterministic spatial proposal service. It reads existing structured CAP specification metadata within the current project and suggests **parent contains child** only when a stored child explicitly declares **located_in parent**. Proposals carry their exact source CAP identity and relationship as evidence.
- It reports unknown parent dimensions/frame, child geometry gaps, and missing anchor placements/clearances without inventing coordinates or geometry.
- The Story CAP Draft form exposes **Analyze Spatial Relationships (Offline)**. The operator sees proposed relations and unresolved items, explicitly confirms whether to append these relations to the editing field, and can then Save Review & Continue using the pre-existing project-scoped unapproved proposal cache.
- Already-declared relationships are not proposed again; existing text is not overwritten. Registered CAPs are scoped to the current project and unavailable Draft specifications are skipped.
- Three service regression tests for a supported inverse relationship, no evidence, and duplicate exclusion.

## Boundaries and deferred functionality
- This is **not** a free-form natural-language relationship extractor or AI-generated geometry proposal. Story narrative alone does not justify assigning exact dimensions. More explicit story/Shot evidence extraction requires a separate governed implementation.
- No synthetic dimensions, default coordinate frames or anchor pairs are inserted to make spatial checks pass.
- The optional **AI-assisted missing-field completion** mentioned in the phase vision is **not wired into this action**; any future paid call requires a separate explicitly authorised, cost-confirmed integration. The existing **Generate / Regenerate Using AI (Paid)** remains a distinct action.
- Suggestions are editable Draft review data only and never modify CAPs or approvals without the existing downstream final confirmation.
- Neither the H3 live hold nor Canon/reference authority is changed. User's untracked architecture audit file must not be modified.

## Operator review
1. Pull the branch and restart VSCS. Open **Canonical Profiles → Story → CAP Batch Review** and **Review Cached Proposal**.
2. Click **Analyze Spatial Relationships (Offline)**. If no stored child CAP explicitly declares `located_in` this parent, expect **no relationship proposals**, a clear list of missing geometry, and no changes to the dependency text.
3. Where an actual stored child CAP explicitly points to this parent, expect a source-labelled `contains` suggestion. Decline to leave the form unchanged, or accept to append an empty-clearance, empty-anchor relationship as an **unapproved proposal**.
4. **Save Review & Continue** retains any accepted edits in the existing cache. Cancel downstream CAP Detail Decisions, reopen the cached proposal, and check that the editing text survived.
5. No paid AI action or CAP save is required. Do not fabricate source relationship evidence to force a positive result in the Golden Path project.

## Verification
```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_16_spatial_proposals.py -v
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```
