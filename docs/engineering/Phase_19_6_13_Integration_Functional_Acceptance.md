# Phase 19.6.13 — Integration & Functional Acceptance

## Purpose

Close Phase 19.6 by validating the complete governed production scheduling chain as one integrated capability.

This phase is an acceptance phase. It does not introduce a new production authority, scheduler, queue, runtime engine, provider adapter, or UI workflow.

## Acceptance boundary

The accepted Phase 19.6 chain is:

```text
Approved Production Authority
        ↓
ProductionTask
        ↓
Dependency / Readiness Graph
        ↓
ProductionResource Matching
        ↓
ProductionSchedule Revision
        ↓
Explicit Human Review / Approval
        ↓
ProductionQueue
        ↓
ProductionWorker + Execution Lease
        ↓
Runtime Monitoring / Recovery
        ↓
Integrated Production Readiness
```

Provider execution remains outside the acceptance boundary.

## Automated functional acceptance

Run:

```powershell
pytest tests/integration/test_phase_19_6_13_scheduling_runtime_functional_acceptance.py -v
```

The acceptance test covers:

1. Persisting an authoritative PLANNED ProductionTask.
2. Graph-derived transition to READY.
3. Capability-compatible resource registration.
4. Deterministic schedule assignment.
5. Queue compilation rejected before human approval.
6. Explicit APPROVED schedule review.
7. ProductionQueue compilation to READY.
8. Integrated readiness BLOCKED while no worker is registered.
9. Integrated readiness READY after an available capable worker is registered.
10. Worker claim and execution lease acquisition.
11. Runtime start and heartbeat.
12. Monitoring of a healthy RUNNING entry and active worker lease.
13. Runtime completion and 100% queue completion progress.
14. Expired RUNNING lease detection.
15. Retry recovery decision/event generation.
16. Recovered queue entry returned to READY under the configured retry policy.

## Static and regression validation

```powershell
ruff format --check .
ruff check .
mypy
pytest -q
```

No focused test from an earlier Phase 19.6 subphase may be removed, disabled, weakened, or bypassed to obtain acceptance.

## Manual Scheduling UI functional acceptance

Use a normal VSCS project and one compiled video-generation ProductionTask.

### A. ProductionTask readiness

1. Open **Production Planning → Production Tasks**.
2. Confirm the persisted task is visible after reopening the project.
3. If the task is PLANNED, select **Refresh Task Readiness**.
4. Confirm a dependency-free task becomes READY.

Expected: readiness is graph-derived; there is no manual force-ready control.

### B. Resource and scheduling

1. Open **Scheduling**.
2. Register:
   - Resource ID: `LOCAL-GPU-01`
   - Capabilities: `video_generation`
   - State: `Available`
3. Select **Create Schedule Revision**.
4. Confirm the READY task is assigned to `LOCAL-GPU-01`.

Expected: a schedule revision exists and remains pending human review until explicitly approved.

### C. Human governance gate

1. Before approval, confirm **Compile Approved Queue** is unavailable or rejected.
2. Enter reviewer identity and review notes.
3. Select **Approve Schedule**.
4. Confirm the current revision reports APPROVED.

Expected: approval is explicit and attributable to a human reviewer.

### D. Queue and worker readiness

1. Select **Compile Approved Queue**.
2. Confirm the queue entry is READY and has not started execution.
3. Register:
   - Worker ID: `LOCAL-WORKER-01`
   - Resource ID: `LOCAL-GPU-01`
   - Capabilities: `video_generation`
   - State: `Available`
4. Confirm resource and worker rows remain visible while navigating away and back within the same VSCS session.

Expected: queue remains provider-neutral and external execution does not start.

### E. Layout and persistence expectations

1. Resize VSCS to a smaller window.
2. Confirm the Scheduling page scrolls vertically and controls do not overlap.
3. Restart VSCS and reopen the project.
4. Confirm ProductionTasks and schedule/review data reload from persistent storage.
5. Confirm resource, worker and queue runtime data are not falsely presented as durable; re-register/recompile them for the new session.

Expected: durable and session-scoped state are clearly distinguished.

## Acceptance criteria

Phase 19.6.13 may be accepted only when all of the following are true:

- Ruff passes.
- mypy passes.
- Phase 19.6.13 integration acceptance tests pass.
- Full pytest suite passes.
- Manual Scheduling UI functional acceptance passes.
- No new provider coupling is introduced.
- No human approval authority is bypassed.
- No regression is introduced into accepted Phase 19.6.1–19.6.12 behavior.

## Known accepted limitations

The following are not Phase 19.6.13 defects:

- ProductionResource persistence/discovery is not yet durable.
- ProductionWorker persistence/discovery is not yet durable.
- ProductionQueue and execution lease state do not survive application restart.
- Runtime completion/failure is not yet reconciled into durable ProductionTask lifecycle state.
- No renderer/provider execution is started from the Scheduling UI.
- GPU/VRAM capacity telemetry is not yet part of scheduling authority.

These remain explicit follow-on architecture work rather than hidden acceptance exceptions.
