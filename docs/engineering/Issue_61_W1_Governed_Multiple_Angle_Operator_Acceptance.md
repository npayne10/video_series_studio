# Issue #61 W1 — Governed Multiple-Angle Acceptance

**Scope:** End-to-end locked MASTER → cardinal CameraAngle qualification → uniquely reconciled output → CAP Candidate → separate human visual approval. The implementation is not automatically qualified by passing CI.

## Code and governance boundaries

- **Normal Generate Selected** retains the existing Qwen Derived Reference v2.1 workflow.
- **Qualify One View (Controlled GPU Trial)** is a distinct opt-in route and accepts **exactly one missing Front, Rear, Left or Right** view per run.
- **Camera qualification mode** defaults to **Fast** (4-step Lightning branch, CFG 1); **Detailed** selects the reviewed graph's 40-step, CFG 4 branch without Lightning. Both modes use the same pinned workflow, MASTER, model and multiple-angles LoRA. The selection affects **only** controlled multiple-angle qualification, not the normal Qwen v2.1 generator. Detailed can cost substantially more time/VRAM and is **not** a guarantee of frontal alignment or authentic unseen geometry. Mode is written into queue, manifest, submission, reconciliation and Candidate notes.
- Before staging, the dialog presents a qualification-specific phrase. No typing/no match means **no staging and no GPU execution**. Staging itself uses exclusive queue/reservation/manifest creation.
- The runtime verifies the locked MASTER digest, compatible ComfyUI node inputs and output links, required model presence, and unique destination. It reserves an immutable submission journal before calling ComfyUI; a transport failure must **not** be automatically retried.
- ComfyUI SaveImage history must indicate successful completion and return **one** output with the qualification-specific filename prefix. Image bytes are fetched through the local ComfyUI `/view` endpoint and exclusively stored under the CAP `Images/Derived` path after PNG and dimension checks.
- After a fresh MASTER check, the result is registered in the canonical reference database **and** production reference library as **Candidate**. No generated reference is automatically Approved, production-ready, or Primary.
- **Independent viewpoint/geometry gates:** approval of every cardinal `*_qualification_*.png` requires an explicit operator **PASS** on alignment with a substantive camera-review note. Rear/Left/Right additionally require a separate **VERIFIED** canonical-geometry attestation naming independently reviewed design evidence; the front-only MASTER cannot authenticate unseen rear/side mechanisms. Either failed or unverified gate leaves the image Candidate (or the operator may reject it). Both decisions are preserved in the governed approval history; neither generation mode is evidence of geometry truth. Existing approved records are not retroactively changed.
- Queue, receipt, reconciliation and Candidate audit records remain preserved on failure. Do not delete, reuse or manually modify a qualification record to force a retry; start a new qualification ID after reviewing the failure.

## Windows preparation — no GPU needed

1. Update your local `D:\VSCS\video_series_studio` branch to PR #66 and launch VSCS as usual.
2. Recheck the protected file digests from [W0 baseline](VSCS_W0_Integrated_Delivery_Starting_Baseline_v1.md), especially the approved `CAP-PRP-002` MASTER. Do not replace existing `front.png` or `front_2.png`.
3. Use the **disposable** project `D:\VSCS\C4B2B_DISPOSABLE_GPU_01`, not production. Open CAP-PRP-002 → Canonical Reference Gallery. Check the MASTER is Approved and locked, and verify missing required views.
4. Confirm ComfyUI is running on `http://127.0.0.1:8188`, the model path is `D:\ComfyUI\ComfyUI_windows_portable\ComfyUI\models`, and that the current provider `CameraAngle`, `XCICQwenReferenceJobLoader`, `ComfySwitchNode`, and Qwen model selections are present. A successful static preflight does **not** prove runtime angle correctness.

## Separate GPU acceptance — only if Neill explicitly authorizes a real trial

1. In **Generate Production References**, select exactly one missing cardinal viewpoint and set a documented seed. Choose **Fast** for a quick camera/identity probe; use **Detailed** only if the Fast result warrants additional quality comparison. Record the *same* seed and viewpoint when comparing modes; each attempt needs a fresh qualification ID.
2. Choose **Qualify One View (Controlled GPU Trial)** and confirm the model directory. In the one-use authorization dialog, click **Copy Authorization Phrase**, then paste into the confirmation field. The **Authorize One GPU Trial** button is disabled until the entire unique `AUTHORIZE GPU QUALIFICATION <32-hex-id>` phrase matches exactly. Copying alone does not authorize GPU execution.
3. Wait for the bounded GPU execution. On error, record the message and inspect immutable `multiple_angle_<id>.*` audit files. **Do not** resubmit that ID.
4. On success, confirm the gallery shows one new Front **Candidate**, never automatically approved; the original MASTER and historical candidates must have unchanged SHA-256 digests. Save the new image digest, prompt ID, execution duration and GPU VRAM evidence.
5. Compare the output against the locked MASTER: front face camera perpendicular, no visible side/top, correct control arrangement, housing, proportions, display, materials and markers. **Human visual QC is mandatory.** Reject if anything drifts; an incorrect camera frame is a qualification failure even when ComfyUI reports completion.
6. Only after explicit human acceptance should the gallery's governed **Approve** action be used. Record the **Viewpoint Acceptance** decision and camera evidence. For Rear/Left/Right, separately identify the independent geometry evidence and confirm **Canonical Geometry Verified**. If either cannot pass, Cancel and retain Candidate or reject. Verify the reference and library lifecycle agree after application restart. No CAP downstream consumption of an unapproved Candidate.

## Gates for declaring W1 usable and complete

- GitHub lint, format, strict typing and full regression pass.
- Windows UI startup and controlled one-shot GPU execution pass.
- Actual provider output matches requested cardinal angle **and** canonical MASTER identity to human QC standard. All four required cardinal views require independent verification before a complete four-view production-reference claim.
- Candidate appears in both records and remains Candidate until a human approves; rejected/archived versions and bytes are preserved.
- Protected MASTER/historical hashes and project governance remain unchanged; unique queue IDs never overwrite prior evidence.

**Current disposition:** implementation available for offline CI; real Windows/GPU and human acceptance **pending**. PR #66 remains Draft until this evidence and separate merge approval.
