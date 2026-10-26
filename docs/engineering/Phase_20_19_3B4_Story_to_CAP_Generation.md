# Phase 20.19.3B.4 — Automated Story-to-CAP Specification Generation & Human Review

Date: 2026-10-26
Status: Initial proposal-and-review integration committed; Windows regression and UI acceptance pending.

## Delivered
- `StoryCAPSpecificationService` reuses existing `CAPGeneratorService.generate_draft` instead of constructing a second AI interface. This method is advisory; it does not write to the database.
- Category-specific starting visual anchor keys: Character anatomy, Location architecture, Ship/Vehicle silhouette, Prop/Technology geometry, Environment/Planet geography, Uniform materials, other categories general identity.
- `StoryCAPProposal` contains a validated `CAPStructuredSpecification` and review warnings that inferred geometry and dimensions are **proposals** and not documented Story Canon. The reference-image prompt is only a draft and does not invoke ComfyUI.
- `StoryCAPSpecificationDialog` offers operator-editable design intent, locked canonical attributes, allowed variants, proposed reference prompt, continuity notes, and clear non-approval language. Confirmation is separate.
- Existing Canonical Profiles workspace adds `Story → CAP Draft…`, available only when the pre-existing generator is wired, and requires an existing **Draft CAP** and a selected row. It asks for an operator-supplied passage from the **approved Story**; Cancel does nothing.
- Save path rejects an existing structured CAP specification (requires a distinct revision workflow) and delegates category and Draft-status enforcement to `CAPStructuredSpecificationService.save_draft`.
- Focused tests for category coverage, empty context/provider non-call and duplicate-specification protection.

## Integration boundary and safety
This is **not yet fully automated**: the UI does not retrieve approved Story passages from the project Story Intelligence database, does not provision missing CAPs in bulk, and does not assert that provider output is entailed by the story. Do not represent a user-pasted passage as cryptographically verified approved canon. Full project-scoped story-canon provenance, asset-to-story cross-reference, proposal-confidence classification, batch creation, and category-complete structured extraction require follow-up implementation.

The first pass uses existing CAP generation provider output; no ComfyUI image/video run, H3 submission, CAP status promotion, Canonical Reference approval, or Golden Path record modification is performed.

## Local acceptance commands
```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b4_story_cap_specification.py -v
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```

## UI smoke test (safe)
1. Open **disposable Episode Audit** project and Canonical Profiles.
2. Confirm `Story → CAP Draft…` action is visible (enabled only if the generator provider exists).
3. Without selecting a CAP, click button: harmless information message.
4. Select a Draft CAP (if available), choose Story → CAP Draft, cancel the context input: no changes.
5. For a separate test project only, select a Draft CAP; paste approved fixture story passage and examine category-specific proposed fields and limitations. Cancel review and verify CAP unchanged.
6. If separately authorized, accept reviewed proposed spec in an isolated matching Draft CAP; confirm database Draft metadata only, no reference/status promotion.
7. Verify four Golden Path binding statuses remain Draft, and H3 hold remains active.

## Suggested next increment
20.19.3B.5 — Project Story Canon grounding, source-span provenance and automatic bulk proposal creation from Story Intelligence registered asset requirements. Import/doc workflow remains available as a fallback. Do not start local image generation until CAP and reference approval tests pass.
