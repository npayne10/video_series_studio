# Phase 20.19.3B.5.8 — Persistent CAP proposal reuse and paid regeneration

Status: Implementation committed to GitHub; local Windows acceptance pending.

## Behavior
- Project-scoped unapproved CAP proposal cache at `production/caps/proposal_cache`, with atomic JSON writes and validation on load.
- Cache includes the structured Draft specification, evidence candidates, design suggestions, quality findings, Story fingerprint, asset fingerprint and provider identity/model fingerprint.
- Review / Generate Proposal reuses a matching existing proposal, even after restarting VSCS and reopening the Batch Review dialog. No provider request on a cache hit.
- Regenerate Using AI (Paid) asks for explicit confirmation, bypasses reuse, and updates the stored proposal only after successful generation.
- Cache entries are advisory and never approve Story Canon, images, references or video generation. Corrupted or stale cache entries are ignored.
- Save validates Story fingerprint, asset/category and CAP Draft state without calling OpenAI. Existing CAP specification excludes new review.
- Includes three focused cache acceptance tests.

## Scope and limitations
- Cache invalidation checks current Story ID/title/description, asset ID/name/category/description, provider class and configured model, and the manual design-prompt contract version. It does not fingerprint the full external Story manuscript or every mutable model/provider setting.
- Cache contains generated creative data, so it lives under the active project directory and should be handled under existing project backup/data confidentiality policies.
- Provider calls still incur charges on first generation, invalidation or explicit Regenerate.
- The cache does not replace full source-level verified provenance or immutable revision records.
- H3 live video generation remains ON HOLD; this phase does not submit images or video.

## Local tests
```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_8_persistent_cap_cache.py tests/test_phase_20_19_3b5_7_no_repeat_ai_cost.py -v
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```

## UI acceptance
Use disposable Episode Audit only. Initial Generate may be paid; after it completes Cancel the review and close/reopen the Batch Review window. Re-select same Story and asset and click Review / Generate Proposal: expect immediate cached review without a new API charge. Press Regenerate Using AI (Paid), verify cost confirmation, select No; no API call. Do not confirm paid regeneration during the cost-control acceptance. Cancel rather than saving CAP; preserve existing architecture audit.
