# Phase 20.19.3B.5.3 — CAP Detail Evidence Classification (initial implementation)

Date: 2026-10-26
Status: Partial; Windows tests and operator UI acceptance pending.

## Delivered
- `application/caps/detail_expansion.py` classifies each required category field as story_candidate_unverified, design_proposal or unresolved. Verbatim model-supplied evidence must appear in the story context and claim wording must align before it can be a **candidate**. Even a candidate is **not** approved Story Canon.
- `StoryCAPSpecificationService.propose` reuses existing AI-generated CAP Draft output and attaches classification to a `StoryCAPProposal`; no second provider request.
- `StoryCAPSpecificationDialog` shows a read-only field-level evidence/uncertainty panel alongside editable Draft identity fields and completeness feedback.
- `build_review_prompt` creates deterministic reference text from a checked set of current CAP attributes without emitting details that were not reviewed.
- Three regression tests for explicit evidence, model inventions, missing category details, and prompt constraints.
- No CAP approval/reference promotion, no image or video provider execution, and no project asset mutation from reviewing the proposal.

## Required follow-up for full 20.19.3B.5.3 acceptance
- This **does not yet** automatically synthesize each missing detailed dimension/material/layout. Missing fields are shown as unresolved rather than being filled with invented canon. A distinct proposed-design generation step using the configured AI provider with structured per-field schema is still required.
- Source evidence classification currently compares existing provider fact text with operator-supplied Story context, not the verified full approved Story source spans. Verbatim overlap is only a candidate check.
- Evidence classifications remain on the proposal for display; they are not independently persisted as per-field provenance. Do not claim the CAP is authority-complete or image-ready.
- Accept/reject/edit decisions per individual proposed field, verified story spans, design-decision approvals, historical revisions and provenance-backed promotion remain future work.
- Current prompt utility is a pure function and is not yet automatically called on Save. The review dialog's Master Prompt remains editable.

## Acceptance
```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_3_detail_expansion.py -v
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```

UI: Open disposable Episode Audit → Canonical Profiles → Story → CAP Batch. Preview the Location draft. Expect Source evidence / design status to list category fields (story candidates, proposed decisions and unresolved details). Cancel without saving; verify no CAP changes. H3 live video generation remains on hold.
