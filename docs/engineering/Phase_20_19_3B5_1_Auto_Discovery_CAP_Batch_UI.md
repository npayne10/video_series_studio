# Phase 20.19.3B.5.1 — Asset Discovery, Missing CAP Drafts and Batch Review UI

Date: 2026-10-26
Status: Initial integrated implementation committed; Windows automated/UI validation pending.

## Implemented
- `StoryCAPBatchReviewService.discover()` reads registered Asset records and the active project's persisted `planning/asset_resolutions.json` Shot-binding ledger. Distinct bound registered assets are shown; unbound/unregistered requirements are not fabricated or silently registered.
- If a Shot binding's expected category differs from a registered Asset category, discovery fails visibly. Duplicate Asset IDs collapse into a single review candidate.
- The new **Story → CAP Batch…** control appears in Canonical Profiles whenever a project and CAP generator are configured, even with zero CAP rows.
- Choose a project Story in Approved/Locked status, **Discover Shot Assets**, select one eligible asset, **Generate Proposal for Selected Asset**, inspect/edit category-specific identity and reference prompt, and separately confirm individual Draft CAP creation.
- Review service re-checks current project Story approval and title/description fingerprint plus asset category. When CAP is missing, creates only `CAPStatus.DRAFT` with existing `CAPService.create` and persists a reviewed structured specification using the existing specification service. Existing approved/non-Draft CAPs, duplicate specifications, rejected or cancelled review do not receive new metadata or status changes.
- The read-only Story batch service is amended to permit registered Assets with **no CAP record**, which specifically resolves the observed `0 CAPs` blocker.
- Focused tests for deduplicated discovery, category mismatch, Draft creation and stale fingerprint refusal.

## Limitations that remain material
- **This implementation discovers only already-registered assets referenced by persisted Shot bindings.** It is not yet end-to-end manuscript-driven registration of new assets. Unmatched inference proposals and other asset requirements outside the governed ledger are not automatically included.
- The generation context is currently the Story record's approved **description** rather than full approved manuscript text or story-intelligence provenance spans. Fingerprint likewise covers only ID/title/description; edits elsewhere in a Story may not invalidate it.
- Review is per asset within a batch dialog, not a transactional bulk-approval queue. Subsequent proposals are reviewed one by one; one failed save need not roll back earlier accepted items.
- A provider call may be required to generate an advisory CAP proposal. This is **not** local image or H3 video generation, and should follow existing provider settings and cost policy.
- Missing CAP creation plus metadata save uses two existing service transactions with compensating deletion of a newly created empty Draft on failure. This is not yet one atomic SQL transaction; multi-user concurrent updates need better protection before a production-grade bulk workflow.
- The user must explicitly confirm each item; no automated CAP/reference or asset approval is introduced.
- No ComfyUI, provider video submissions, video task creation or revision of existing Golden Path asset approvals are authorized.

## Test and UI acceptance

```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_1_batch_review.py tests/test_phase_20_19_3b5_story_batch.py -v
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```

Operator:
1. Open disposable **Episode Audit** project → Canonical Profiles. Confirm **Story → CAP Batch…** is present even if the table says `0 CAPs`.
2. Open dialog and verify `STORY-001` is selectable only if Approved/Locked. Discover Shot Assets; expect registered bound assets where present, otherwise an explicit empty result.
3. Inspect status labels: Missing CAP vs existing Draft vs already specified.
4. Select candidate and start proposal generation, then Cancel review. Confirm **no CAP created** and four Shot bindings remain Draft.
5. Test rejection at Yes/No confirmation. No CAP created; no Master Reference approved.
6. Only with explicit authorization for this isolated test, confirm one reviewed item; expected newly created Draft CAP + Draft specification, no reference status change.
7. Verify no production system project files touched and H3 live-generation hold remains active.

Phase remains open for full Story Intelligence source-lineage integration and all-asset automated registration. Tests have not been run by this GitHub tool.
