# Phase 20.19.3B.5 — Project Story Canon Grounding and Multi-Asset CAP Generation

Date: 2026-10-26
Status: **Partial implementation**. Story approval gating and read-only batch service committed; operator UI, full Story Intelligence provenance and Draft CAP creation are **not yet implemented**.

## Verified repository surfaces
- `StoryLifecycleService.story(story_id)`: reads story identities and persisted lifecycle status from the active project.
- `StoryStatus.APPROVED` and `StoryStatus.LOCKED` are eligible review states. Draft, Imported, Analysed, Archived and missing stories cannot be used as the approved basis for this batch proposal.
- `StoryCAPSpecificationService.propose` reuses the earlier category-aware generation adapter; `CAPStructuredSpecificationService.get` provides duplicate detection.
- Screenshot supplied on 26 October shows **0 CAPs** in the Canonical Profiles workspace. An operator-facing batch workflow cannot assume precreated CAP rows.

## Implemented non-destructive backend
- `StoryCAPBatchService.preview(story_id, asset_ids)` reads one project Story from its existing lifecycle repository, requires Approved/Locked state and a nonblank Story description.
- Determines a SHA256 fingerprint of Story ID, title and description; the digest represents **only these fields**, not full manuscript, approvals or Story Intelligence snapshots.
- Deduplicates asset IDs; checks existing structured specs; generates advisory Story-to-CAP proposals for eligible registered assets and returns explicit skip reasons per asset.
- Does not create assets, CAPs, approved references, Master images or ProductionTasks. No image/video provider execution or H3 submission.
- Focused tests cover approval denial, missing/empty Story, duplicate asset IDs, already specified CAPs and Locked Story. **Local Windows tests pending.**

## Important unresolved acceptance gates
1. Approved Story **description** is not the full approved manuscript or Story Intelligence breakdown. Do not call the current proposal fully canon-grounded. The next implementation must fetch persisted source spans/approved analysis with lineage and check the fingerprint at save.
2. Asset IDs are currently supplied by the caller. The next integration must enumerate Story Intelligence and Shot Asset Resolver requirements and map them to registered assets with human approval.
3. Registered Assets may have **no CAP record**. Add deliberate operator-reviewed creation of missing Draft CAPs before structured spec save; never silently create or approve them.
4. Add batch UI in Story/Canonical Profiles: select approved Story, inspect found requirements, preview proposals, accept/reject each, create missing Draft CAPs through existing services, persist reviewed specifications with conflict detection.
5. Add UI and real temporary SQLite integration tests, project switching/collision tests, atomic revision protection, cancelled batch = zero writes, unsupported category/missing evidence diagnostics.
6. Preserve Xorix vs Golden Path `CAP-LOC-001` namespace separation. Do not import the Xorix apartment into Golden Path's engineering-room slot.
7. H3 live generation remains on hold; ComfyUI image generation is not authorized by this phase.

## Local acceptance
```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_story_batch.py -v
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```

Expected new test count: 4; previous baseline 2238. Do not mark 20.19.3B.5 accepted until all gates and UI flow are implemented and exercised.
