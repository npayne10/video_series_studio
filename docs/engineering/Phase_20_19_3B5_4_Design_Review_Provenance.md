# Phase 20.19.3B.5.4 — Design completion review and provenance

Date: 2026-10-27
Status: **Partial implementation in GitHub; Windows acceptance pending.**

## Delivered
- `application/caps/design_completion.py`: typed per-field Accept/Edit/Reject/Defer decisions, proposal origin and evidence/rationale notes. Requires every category-minimum field to have an explicit decision and current specification fingerprint.
- Human-reviewed accepted details alone enter `canonical_attributes`; rejected and deferred fields do not. A deterministic Master reference *proposal* is rebuilt from accepted values, explicitly marked not approved.
- Existing project CAP `production_metadata` now can hold both `vscs.structured_cap_specification.v1` and `vscs.cap_design_review.v1` in one CAP update. Audit contains reviewer label, story fingerprint if supplied, original/result fingerprints, detailed field decisions, and `canon_approved=false` / `image_authorized=false`.
- `CAPDetailReviewDialog` provides field-by-field edits and decisions. The existing approved-Story CAP Batch flow opens this second dialog after Story CAP review, before explicit Yes/No save.
- Previously created CAPs are not overwritten; persistence guards Draft status and existing structured specification. New CAP creation compensates a failed metadata save but is not a full transaction.
- Four focused tests cover accepting/editing/rejecting/defer, stale fingerprints, reviewed prompt and invalid actions.

## Boundaries
**This does not yet call a dedicated AI completion provider to fill missing fields.** It reviews a field-by-field category checklist using existing values plus operator entries. Source evidence text is operator supplied and not independently verified against approved Story source spans. A recorded Accept/Edit decision is a reviewed design choice, **not Story Canon approval**. The story-description digest check remains separate from full Story Intelligence provenance.
The history currently records one initial design review in existing CAP metadata; it is not a complete immutable revision ledger. No image generation or video execution.

## Tests
```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_4_design_review.py tests/test_phase_20_19_3b5_1_batch_review.py -v
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```
GUI in disposable Episode Audit: Story → CAP Batch → select location → Generate → review CAP → review field decisions → Cancel. No records should be written. To test Save, use a separate authorized disposable project, not the existing Golden Path. H3 video hold stays active.

## Completion gates
1. Provider-backed structured proposals for missing category fields, with explicit distinction between proposed values and verified Story facts.
2. Real source-span fingerprinting and authority checks, plus conflict review.
3. Persistent immutable revision history and independently verified database integration/UI acceptance.
4. Explicit canonical promotion policy and candidate image readiness; these are intentionally **not** granted here.
