# W2.2 — First Governed Video: Windows Operator Acceptance

**State:** Execution safeguards implemented; **live 15-second GPU video and QC pending**.  
**Provider candidate:** `minimax-h3-ref2va-v1`, governed one-span route.  
**Governance:** The following procedure is not authorization to submit a job.

## Single focused run

1. Confirm the intended disposable Windows project, Episode, Shot, ProductionTask and scope. The proposed diagnostic-console `CAP-PRP-002` shot (`AUT-SHOT-D7FC62B73D16`) is a **starting hypothesis**, not an assertion that the persisted task is Ready. Check the camera and approximate 15-second requested duration; do not alter approved MASTER/Front references or approve synthetic Rear/Left/Right geometry to enable generation.
2. Open **Production Execution Workspace**, select the Ready video ProductionTask and its intended execution profile. Select **MiniMax H3 / `minimax-h3-ref2va-v1`**. Verify approved shot-scoped sources and any required Introduction Keyframe. **Compile Production Package**, then **Validate Provider Readiness**. Record the exact provider plan and blockers; if not READY, stop and report only those blockers.
3. Check the real ComfyUI `input`/`output` paths, locally reviewed API graph and model availability. Confirm the NVIDIA RTX 5060 Ti 16 GB has sufficient free resources; a source-enforced 15-second ceiling is **not** proof of runtime fit. Do not initiate a trial solely because the button is enabled.
4. When Neill separately authorizes the **specific one-job GPU trial**, choose **Run Automated Span Orchestration**. A **One-Use Video GPU Authorization** dialog displays the selected Task, execution profile, provider and plan. The generated phrase is in a *selectable, read-only field* for copying; paste it into the confirmation field. Only an exact match enables OK; Cancel must submit no GPU work. Each attempt generates a different phrase.
5. Allow the single H3 job to complete. Do not retry blindly on an error: the direct route records a durable launch claim and includes governed recovery for already-produced output. Capture job/plan identifiers, timestamps, provider logs, generated MP4 path and outcome.
6. Confirm video is playable; independently inspect fps, frame count, duration, image continuity, asset identity and camera movement. Confirm the MP4 appears as **GENERATED**, not APPROVED, under **Generated Media** for the correct Task/Shot; record technical-validation and human-review decisions separately. Never approve solely because an inference or frame probe succeeded.
7. Report results in this file and the MASTER backlog: **PASS** only for actual playable and reviewed output, or **BLOCKED** with observed blocker. If a 15-second direct job is infeasible, decide whether a shorter governed trial or the existing LTX-2.5 assembled ~18-second fallback is warranted. Separate authorization applies to any new GPU job.

## Non-negotiable checkpoints

- Existing approved canonical references and their hashes remain intact; unverified side geometry is not promoted to production authority.
- No paid API calls, model downloads, automatic reference approval, merge or release are implicit in W2.2.
- Provider readiness is revalidated at execution time by the backend; the operator-specific UI phrase is an additional human gate, not a substitute for governed readiness.
- The H3 monolithic execution backend registers verified output into managed **GeneratedMedia** as `GENERATED` and requires further QC. Source implementation alone is not live acceptance.
- Failure/restart: preserve claim, provenance, output and review state; use explicit governed recovery rather than submitting a duplicate job.

## Result ledger (fill only from Windows evidence)

| Check | Result |
|---|---|
| Windows persisted Project/Shot/Task Ready | **PENDING** |
| H3 provider plan and approved Introduction Keyframe | **PENDING** |
| ComfyUI workflow/models and 16 GB GPU availability | **PENDING** |
| One-use operator authorization | **NOT ISSUED** |
| One actual job, exact MP4/fps/frames/duration | **NOT RUN** |
| GeneratedMedia registration and technical/human QC | **PENDING** |

See [W2.1 source-level provider reconciliation](VSCS_W2_1_Video_Generation_Capability_Reconciliation.md) for why this route was selected and when to revisit LTX-2.5 or H3 timed multi-frame.
