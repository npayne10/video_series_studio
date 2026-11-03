# Phase 20.19.3B.5.22 — Controlled disk-backed reviewed Draft CAP acceptance

**Status: IMPLEMENTED TEST FIXTURE — NOT YET ACCEPTED**  
Date: 2026-11-03  
Baseline: B.5.21C development acceptance closed at 2,398 passing tests.

## Project choice

**Use a new, isolated disposable project, not `B5_19A_ACCEPTANCE`.** That pre-existing project is a known baseline and must remain unchanged. The automated test fixture itself creates `tmp_path/B5_22_DISPOSABLE_CAP_ACCEPTANCE`, initializes a **real VSCS SQLite DatabaseManager** and actual AssetRepository, CAPRepository, AssetService, CAPService, CAPStructuredSpecificationService, StoryLifecycleService and StoryCAPBatchReviewService. Pytest removes its temporary project after execution. The test does not open or mutate any current VSCS operator project.

If a later manual desktop-UI test adds value, create a *separate* project named `B5_22_DISPOSABLE_CAP_ACCEPTANCE_UI`, not a replacement or duplicate of the operator's known-good B5_19A project. Manual UI acceptance remains an additional gate, and should only be specified once automated tests pass.

## Implemented integration tests

File: `tests/test_phase_20_19_3b5_22_disk_backed_cap_acceptance.py`.

The disposable test creates:
- A real, project-local SQLite file and one registered **Draft** location asset `CAP-LOC-001`.
- A real first-class persisted Story `STORY-001` marked Approved (disposable context only).
- A persisted Ready Episode→Scene→Shot hierarchy with production-generated contract hashes; the Shot asset binding stays Draft, so unverified Shot narrative is not promoted to Canon.
- A reviewed `CAPStructuredSpecification` with explicit field decisions, Story fingerprint and **current, locally calculated** CAP context fingerprint.

Acceptance scenarios:
1. **Successful reviewed Draft save and restart**. Invoke real StoryCAPBatchReviewService.save_reviewed, real DesignReviewPersistence, CAPService and CAPRepository. Close the DB, reopen it with a new DatabaseManager, and verify Draft status, unchanged Draft asset, no references, persisted structured specification, audit Story/context hashes, all review decisions and Canon/image approval flags false.
2. **Failure injection before metadata commit**. Make DesignReviewPersistence fail after CAP creation; the newly created empty Draft is deleted, leaving the real project SQLite repository empty.
3. **Stale-context rejection**. Modify persisted Shot text after calculating the original manifest. Verify no Draft is created.
4. **SQLite update failure recovery**. Inject a failure into the actual CAP repository update call; verify cleanup leaves no CAP.
5. **Duplicate-save safety**. A second save on an already specified Draft is rejected, preserving the original review metadata.

The fixture tests real database durability and service boundaries. It is not proof of a complete human-driven GUI save workflow, real reference image approval, Canon production readiness, or H3 live generation.

## Operator test commands

```powershell
cd D:\VSCS\video_series_studio
git status --short
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
git log -1 --oneline
python -m pytest -q tests/test_phase_20_19_3b5_22_disk_backed_cap_acceptance.py -v
python -m pytest -q tests/test_phase_20_19_3b5_21c_reviewed_draft_persistence.py -v
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```

Expected number of newly added tests: **5**. Full suite should have **2,403** tests if the previous 2,398-test baseline is unchanged. These counts are targets, not verified results. Report any failures so they can be fixed in GitHub before formal acceptance.

Preserve the user's untracked `docs/VSCS_Architecture_Workflow_Audit_2026-10-24.md`. Do not perform paid generation, modify existing acceptance projects, create real CAPs in Xorix, or change the H3 live execution hold.
