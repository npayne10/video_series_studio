# Phase 20.19.3B.5.7 — CAP paid API call reduction

Status: Committed; local Windows automated/UI acceptance pending.

## Costs addressed
Each new proposal currently uses the OpenAI CAP fact-extraction, canon-analysis, draft, and design-expansion stages (up to four charged calls). The old save path called batch.preview again and repeated those stages just to validate Story status and fingerprint.

- `StoryCAPBatchService.current_story_fingerprint` checks current project Story Approved/Locked status, nonempty description and unchanged SHA256 without a provider call.
- `StoryCAPBatchReviewService.save_reviewed` now checks this fingerprint, existing specification, asset category and Draft state directly, no paid proposal regeneration on Save.
- `StoryCAPBatchDialog` reuses in-memory proposals by story ID, asset ID and Story fingerprint while the Batch Review window remains open. Cancel and reopen **in that same window** does not regenerate. A successful save clears the cache.
- Story status/description changes invalidate a cached proposal. Existing CAP status and category are checked before persistence.

## Boundaries
This is **not a persistent disk cache**. Closing and reopening the Batch dialog, restarting VSCS or switching project may require another paid generation. In-memory proposal cache should be cleared when the window closes and is not a source of canonical authority.
No automatic provider request is started from discovery, review, edits or save. Explicit Generate remains the cost-bearing action.
Story fingerprint currently hashes Story ID/title/description; this is not a fingerprint of the complete approved manuscript or its source file. Future provenance enhancement required.
No image generation, H3 execution or approval-state changes.

## Local acceptance
```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_1_batch_review.py tests/test_phase_20_19_3b5_7_no_repeat_ai_cost.py -v
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```
UI: In disposable Episode Audit, generate CAP-LOC-001, Cancel review, select same asset and Generate again *without closing Batch Review*. Expected second open uses in-memory proposal, no second provider API call. Do not save. H3 hold remains active.
