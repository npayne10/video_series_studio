# Phase 20.18.2.3.6.6b.5 — Accepted Provider Production → Generated Media Reconciliation

## Purpose

Close the compatibility gap between provider productions that were already
technically and visually accepted under the governed MiniMax H3 functional-
acceptance path and the newer Generated Media / ProductionTask completion
authority model.

The phase must preserve accepted production. It must not rerender, silently
rebind media to another task, fabricate a durable provider execution, or bypass
normal ProductionTask completion reconciliation.

## Live acceptance case

The governing real-shot case is:

- Shot: `EP-001-SCN-001-SHT-002`
- ProductionTask: `PT-VIDEO-GENERATION-29A500F54E418255`
- Provider: `minimax-h3-ref2va`
- Governed H3 plan:
  `H3SPANPLAN-EP-001-SCN-001-SHT-002-FBFFD471DCA2`
- final frames: 144
- frame rate: 24 fps
- functional acceptance: passed
- technical acceptance: passed
- visual acceptance: passed
- human approver: Neill Payne

The accepted H3 evidence predates authoritative Generated Media ingestion for
this execution path, so ProductionTask completion currently reports
`missing-authoritative-selection`.

## Authority rules

Reconciliation is fail closed. It is eligible only when all of the following are
true:

1. the current ProductionTask is VIDEO_GENERATION and requires `video/shot`;
2. task state is READY or RUNNING for the operator action;
3. normal completion reconciliation is blocked only by
   `missing-authoritative-selection`;
4. exactly one passed provider functional-acceptance record exists under the
   exact current task identity;
5. functional acceptance and orchestration evidence agree on task, Shot, plan,
   final path, frame count and frame rate;
6. the final media remains inside the governed H3 plan directory and inside the
   VSCS project;
7. the final media still exists and a fresh media probe confirms the accepted
   frame count and frame rate;
8. persisted provider readiness exists for the exact current task and Shot;
9. no different authoritative Generated Media selection already exists.

The ProductionTask ID remains a critical authority boundary because it is
deterministically derived from the UPD authority identity, revision, authority
fingerprint, task type and governed dependencies.

## Reconciliation behavior

The compatibility bridge:

1. copies the already-accepted provider video into VSCS-managed Generated Media
   storage without modifying the original H3 artifact;
2. creates one deterministic Generated Media identity with explicit provenance:
   - `provenance_source=accepted-provider-functional-acceptance`
   - `reconciliation_phase=20.18.2.3.6.6b.5`
   - current ProductionTask `authority_fingerprint`
   - H3 plan identity/fingerprint
   - original orchestration and functional-acceptance evidence paths
   - original accepted media path
   - accepted frame count and frame rate;
3. runs standard Generated Media technical validation against the managed copy;
4. preserves the existing human functional-acceptance identity through the
   standard Generated Media review/approval lifecycle;
5. creates the authoritative Generated Media selection only when no selection
   exists for that production intent;
6. reconstructs the missing provider-production adoption audit from persisted
   provider readiness plus passed functional-acceptance evidence and records it
   as accepted;
7. leaves ProductionTask lifecycle mutation to the existing
   `ProductionTaskCompletionReconciliationService`.

The bridge never manufactures a `DurableExecutionJob`. Normal provider-output
ingestion still requires a genuinely COMPLETED durable provider execution.

## Idempotency and restart safety

The Generated Media identity is deterministic for the task, H3 plan and accepted
final artifact. Re-running reconciliation:

- does not create duplicate media;
- does not create duplicate selections;
- does not replace a different existing selection;
- resumes a partially completed reconciliation when the deterministic reconciled
  media/selection already exists but provider-adoption persistence did not finish;
- returns the already-reconciled authority when media, selection and accepted
  provider adoption are all present.

## UI governance

Production Tasks exposes:

`Reconcile Accepted Provider Production`

The action is enabled only for a selected READY/RUNNING task when:

- normal completion reconciliation reports only
  `missing-authoritative-selection`; and
- exact accepted-provider evidence passes the reconciliation assessment.

The action confirms with the operator before mutation. After reconciliation, the
operator must use the existing `Reconcile Task Completion` action. This keeps
the normal READY → RUNNING → COMPLETED lifecycle authoritative.

## Regression gates

Focused regression must prove:

- exact passed H3 acceptance creates managed approved selected Generated Media;
- reconciliation is idempotent;
- wrong task ID is rejected;
- wrong Shot ID is rejected;
- missing final media is rejected;
- failed technical acceptance is rejected;
- failed visual acceptance is rejected;
- project-path escape is rejected;
- altered frame count is rejected;
- an existing authoritative selection is never silently replaced;
- current ProductionTask authority fingerprint is persisted in Generated Media
  provenance;
- non-current/terminal incompatible task authority is rejected;
- normal Phase 20.9 provider-output Generated Media ingestion remains unchanged;
- ProductionTask completion reconciliation remains the only task-completion
  mutation path.

## Live UI acceptance

For SHT-002:

1. select the single current READY task
   `PT-VIDEO-GENERATION-29A500F54E418255`;
2. confirm `Reconcile Task Completion` still reports
   `missing-authoritative-selection` before migration;
3. confirm `Reconcile Accepted Provider Production` is enabled;
4. run the reconciliation and verify:
   - no provider execution occurs;
   - no H3 rerender occurs;
   - one new Generated Media record appears for SHT-002;
   - state is Approved;
   - technical validation is Passed;
   - Selected is Yes;
   - provenance contains the current task authority fingerprint and Phase
     20.18.2.3.6.6b.5 markers;
   - provider-production adoption is accepted;
5. run `Reconcile Task Completion` and verify SHT-002 becomes COMPLETED;
6. return to SHT-003 and run `Refresh Task Readiness`; verify the dependency
   releases and SHT-003 transitions PLANNED → READY;
7. confirm accepted SHT-001/SHT-002 media files and original H3 evidence remain
   unchanged.

## Phase state

**OPEN — IMPLEMENTED; PENDING STATIC VALIDATION, FOCUSED/FULL REGRESSION, AND
LIVE SHT-002 → SHT-003 FUNCTIONAL ACCEPTANCE.**
