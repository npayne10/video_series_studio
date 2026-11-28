# Issue #61 Stage B.2F — governed multiple-angle execution safeguards

Status: **offline guarded staging implemented; no GPU submission or candidate promotion**.
PR #66 stays Draft and Issue #61 stays open.

## What is implemented

`multiple_angle_execution_guard` operates on a B.2E
`MultipleAngleRuntimeReadiness` plan. Offline staging is **disabled by
default**. Only the explicitly opted-in
`stage_offline_qualification(..., allow_offline_staging=True)` API may
materialize a qualification's audit artifacts; this API is not connected to
the CAP UI or ComfyUI transport.

In an isolated disposable test fixture, the API:

1. Re-resolves approved/locked MASTER identity and checks its SHA-256,
   path containment and current active-view coverage immediately before
   staging. Stale or conflicting authority is rejected.
2. Checks exact planned queue, MASTER source and destination binding.
3. Checks project containment, and rejects pre-existing queue, manifest,
   reservation or target output paths.
4. Creates a unique output reservation record, queue JSON and immutable
   provenance manifest with atomic exclusive file creation. Files are
   fsynced. Partial failures roll back only files created by that attempt.
5. Records queue SHA-256 and qualification ID so a restart can detect
   missing files, modified queues, path mismatches or an unexpected output.
6. Supports an append-only cancellation marker; it never deletes a historical
   queue or changes a CAP production reference.

The staging API writes files **only** when expressly opted into on a
disposable fixture. Its report always has `generation_authorized=False`.
No provider POST, GPU work, image output or CAP record mutation is implemented.

## Still blocked

This is a preparation safety contract, not live provider qualification.
Required future implementation/authorisation includes:

- Actual ComfyUI loader-to-CameraAngle runtime compatibility and model fit.
- Truly atomic submission-time MASTER freshness checks and GPU job leases.
- Explicit job dispatch, cancellation and completion reconciliation.
- Safe output validation (file signature, contents, path, identity, dimensions),
  CAP Candidate registration, human QC and durable prompt/job provenance.
- Proving correct Front/Rear/Left/Right orientations and no identity drift.
- Separate operator approval for a bounded GPU qualification trial.

**Do not call `stage_offline_qualification` on
`C4B2B_DISPOSABLE_GPU_01` during this acceptance.** The real project
contains protected historical evidence. All staging-write tests run on
disposable pytest fixture directories.

## GitHub and Windows acceptance

GitHub CI runs a fast pinned Ruff lint/format gate before full mypy/pytest.
Wait for both jobs to pass on PR #66 before Windows operator acceptance.

```powershell
git switch issue-61-governed-master-workflow
git pull --ff-only
python -m pytest -q `
    tests/unit/test_multiple_angle_execution_guard.py `
    tests/unit/test_multiple_angle_runtime_readiness.py `
    tests/unit/test_multiple_angle_binding.py `
    tests/unit/test_multiple_angle_provider_preflight.py
python -m pytest -q
```

Review approved locked MASTER and both Front historical candidates without
editing them. Recheck known protected hashes. Existing CAP-PRP-002
`front_2.png` is formally governed Rejected, despite legacy Candidate
status. No new `multiple_angle_*.json` files should be produced by these
tests in the real project.

STOP: Do not merge or authorise generation from this Stage B.2F result.
