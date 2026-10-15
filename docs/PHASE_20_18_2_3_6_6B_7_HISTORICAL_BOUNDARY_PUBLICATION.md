# Phase 20.18.2.3.6.6b.7 — Historical Approved Media Boundary Publication

## Purpose
Allow human operators to publish a governed closing Shot Boundary from an already COMPLETED ProductionTask whose video was previously accepted. Historical publication is distinct from scheduling, READY task execution, and retry authority.

## Operator workflow
1. Open the existing VSCS project and **Production Execution** workspace.
2. Locate **Historical Approved Media — Closing Boundary**.
3. Enter the completed ProductionTask ID and click **Inspect Approved Historical Media**.
4. Confirm the Shot ID, exactly one approved production-profile Generated Media video, frame index/count, rate and SHA-256.
5. Click **Publish Historical Closing Boundary**; enter a human publishing identity and approve the separate confirmation.
6. Confirm the returned published boundary identifier, final frame and source checksum.
7. Refresh the current Shot's opening boundary; only then compile its governed package.

## Authority and safety
- Task must be COMPLETED and of VIDEO_GENERATION type, scoped to a Shot.
- Only the production execution profile is supported.
- Exactly one APPROVED, Shot-matching video from that task/profile must exist.
- A missing or mismatching persisted SHA-256 prevents publication.
- Existing GovernedShotBoundaryRuntime performs FFprobe frame enumeration, FFmpeg extraction, checksum validation and governed persistence.
- No alteration of completed task state, media authority, approved schedules, queued work, retry counters or execution jobs.
- The ordinary scheduled-task table continues to include only READY queue entries.
- UI re-inspects evidence immediately before asking the operator for human identity and confirmation.
- If a source changes during publication, runtime performs independent checksum validation.

## SHT-002 live acceptance (do not assume results)
- Task: PT-VIDEO-GENERATION-29A500F54E418255
- Media: GM-APR-A48BFA852AFE4934269E
- Expected approved video: 144 frames at 24 fps; final frame index 143
- Expected protected SHA-256:
  284CF1C4637F8E6EC448FF73EB657B43C2B3965298A5E9F0F5D65673B6556DFD
- SHT-003 remains READY under Schedule Revision 27.
- Do not publish until Ruff, mypy, full regression and UI inspection have passed.

## Help/manual context
The historical publication section is **not** the normal **Publish Closing Boundary** button associated with the selected READY scheduled Shot. Operators must never select a different Shot to force publication of earlier media.
