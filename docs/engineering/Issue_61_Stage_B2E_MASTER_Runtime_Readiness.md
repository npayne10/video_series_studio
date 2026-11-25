# Issue #61 Stage B.2E — Governed MASTER runtime qualification readiness

Status: **readiness planner implemented; execution deliberately not implemented**.
This is an offline, non-executable design artifact on Draft PR #66.

## The actual runtime boundary

`plan_multiple_angle_runtime` builds on the Stage B.2C locked-MASTER
compiler. It:

1. Resolves the approved, locked MASTER through existing VSCS authority rules.
2. Rejects a MASTER outside the governed project and active duplicate views.
3. Captures MASTER reference ID and SHA-256.
4. Compiles the approved template with provisional camera settings in memory.
5. Re-resolves MASTER authority and re-hashes the file after compilation,
   rejecting any change.
6. Proposes random per-qualification queue and output paths within project
   storage, rejecting collisions and project-boundary escapes.
7. Replaces the unqualified queue/output placeholders in a **proposed**
   in-memory graph and job record. A supplied `/object_info` snapshot can
   be checked using the existing B.2D.1 static provider auditor.
8. Records explicit no-execution blockers. `generation_authorized` is
   permanently false; neither queue nor output is created.

Do **not** submit the proposed graph to `/prompt`. It has not been
materialized, reconciled or verified against the runtime loader. The presence
of a file path in memory does not make it executable or approved.

### Why this remains blocked

- Exact queued MASTER source loading from `XCICQwenReferenceJobLoader` into
  `CameraAngle` has not been tested as runtime image conditioning.
- Atomic queue reservation, output write protection, stale-state handling,
  cancellation, crash recovery and identity/QC registration must be built
  and reviewed before live provider execution.
- Freshness must be checked *again* immediately before an actual submission.
- The installed FP8 Mixed model, Lightning and multiple-angle LoRA have not
  demonstrated 16 GiB GPU fit or reliable inference.
- Camera azimuth convention, deterministic repeatability and canonical
  identity are not yet visually qualified.
- A separate, bounded GPU qualification consent must be obtained.

## Operator acceptance

Keep `CAP-PRP-002` MASTER, `front.png`, `front_2.png` and historical
snapshots unchanged. These files are evidence, not disposable fixtures.
All destructive testing belongs to transient pytest fixtures.

Update the PR branch then run:

```powershell
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q `
    tests/unit/test_multiple_angle_runtime_readiness.py `
    tests/unit/test_multiple_angle_binding.py `
    tests/unit/test_multiple_angle_provider_preflight.py `
    tests/unit/test_qwen_multi_angle_qualification.py `
    tests/integration/test_derived_reference_generation_pipeline.py
python -m pytest -q
git diff --check
git status --short
```

The new tests cover in-memory queue and MASTER binding, no project/runtime
writes, path collisions, invalid staging IDs and MASTER freshness changes.
Do not perform generation or approve a derived Candidate for this acceptance.
Check MASTER and candidate SHA-256 values against the saved audit snapshots,
and inspect CAP UI state read-only if needed.

**STOP at offline acceptance.** B.2E does not permit a live ComfyUI prompt,
production output, PR merge or Issue #61 closure.
