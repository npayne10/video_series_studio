# Issue #61 — Cross-View Cinematic Reference Acceptance

**Purpose:** A candidate viewpoint may be judged suitable for cinematic video without being represented as independently verified canonical geometry. This does not relax MASTER locking, CAP approval, or separate GPU authorization.

## Operator workflow

1. Open **Canonical Profiles → CAP → Canonical Reference Gallery**. Retain the approved, locked MASTER and an approved Front reference.
2. Select a Rear, Left or Right **Candidate** and choose **Accept for Cinema…**. The dialog displays the locked MASTER and available cardinal reference images together, including their actual lifecycle labels.
3. Inspect the candidate against the other visible views: silhouette, proportions, palette, recognizable components and cross-view continuity. Record specific observations and limitations (at least 30 characters). Check the human cinematic-use confirmation, then select **Accept Cinematic Use**.
4. Confirm the **cinematic-only** decision separately. The record remains a **Candidate** in strict canonical governance; the gallery will show that a cinematic-use QC decision was recorded.
5. Repeat only for other necessary candidates. Choose **Cinematic Readiness…** in the gallery to inspect the separate video-use readiness assessment and remaining CAP blockers. **No new GPU job is submitted.** Do not use the strict **Approve** button without independent geometry evidence.

## Data and authority

- Cinematic decisions are stored in the existing project-local `.vscs/cap_reference_library.json` as a separate field on the registered view. No historical image, review event or canonical approval is rewritten.
- Records store the approving operator, timestamp, review text and SHA-256 of every reference shown in the comparison, including the locked MASTER and approved Front. Recomputed hashes and lifecycle checks fail closed on missing/replaced files or stale authority.
- Strict `CAPReadinessService.evaluate()` and default `ProductionProjectionService.project()` **do not** count cinematic Candidates as canonical references. `evaluate_cinematic()` / `project_cinematic()` / `require_cinematic_ready()` are explicit, separate video-use assessments; the returned reference still carries `candidate` lifecycle.
- CAP status and other readiness dimensions remain binding, and no production task or GPU execution is automatically authorized. The video pipeline must explicitly opt into the cinematic projection before use; current strict call sites are intentionally unchanged.
- Neither another AI-generated view nor a plausible hidden component proves engineering geometry. Cinematic acceptance records *suitability for film* only, not new design canon.

**Windows acceptance:** Record one cinematic Rear decision and verify that the gallery still shows Candidate, cinematic QC recorded, strict readiness still reports unapproved Rear, and cinematic readiness recognizes the decision. Reopen the project to verify persistence. Changing a comparison image or MASTER authority must make cinematic readiness fail closed.
