# Issue #61 W2.4 — Automated CAP Visual Identity and Production Guidance Completion

## Scope and authority

Extends **Prepare from Reviewed CAP (Offline)…** in the CAP Production Contract editor. The existing saved, human-reviewed specification is the only source. No image analysis, provider/GPU call, MASTER approval, asset approval or automatic CAP status transition occurs.

The proposal displays:

- Approved-field Facts, Capabilities and Constraints, as before;
- a reviewable **Visual Identity** summary of accepted/edited design attributes;
- reviewable **Production Notes** preserving accepted attributes and, only where no design field is deferred or rejected, the saved continuity rules;
- the names of deferred/rejected fields and explicit warnings when dependent continuity prose is withheld.

Existing Visual Identity or Production Notes are **never overwritten**. Both proposed text fields can be reviewed and edited in the proposal dialog when the corresponding CAP editor field is empty. **Accept Reviewed Entries** merges into the open editor only. **Save** is still required for persistence; **Cancel** preserves existing saved state.

The proposal cannot validate an unregistered visual candidate as a MASTER. In CAP-PRP-001, the existing workstation image was a **supplementary unregistered Candidate**, not a governed MASTER. Establish and approve/lock a real ChatGPT MASTER through the existing Asset/CAP workflow separately after design review.

## Windows operator acceptance — repeat for CAP-PRP-001 and CAP-LOC-001

1. Open the active project, **Canonical Profiles**, select the CAP and **Edit Selected**.
2. Check **Reviewed CAP Specification & Decisions**. If a field such as geometry is **Defer**, return to its saved design-review workflow to resolve it only when independent source evidence exists. Do not guess geometry from the candidate image.
3. Scroll to **Structured Production Knowledge**. Choose **Prepare from Reviewed CAP (Offline)…**.
4. In **Structured CAP Knowledge Proposal**, inspect the Facts/Capabilities/Constraints and the new **Visual Identity** and **Production Notes / Continuity** panels. Note all deferred/rejected fields. Edit proposed wording as necessary, and click **Accept Reviewed Entries** only if accurate.
5. In the CAP editor verify **Visual Identity** and **Production Notes** are now populated where previously empty. Previously entered text must remain unchanged.
6. Leave CAP **Draft** until its distinct asset, reference and design readiness checks pass. Click **Save**, reopen the CAP, and verify both fields persist.
7. Continue with separate governed MASTER establishment, derived references, cinematic qualification, CAP/Asset approvals and Episode Planner Asset Resolver. Do not create a second MASTER if a governed one already exists.

## Negative checks

- Missing/stale human-reviewed specification: offline proposal refuses and makes no provider call.
- Cancel proposal: no editor changes or persistence.
- Defer/reject: never becomes a Fact or definitive Visual Identity; continuity text that could contain it is withheld.
- Existing nonempty Visual Identity or Production Notes: never replaced.
- Accept without CAP Save: changes are still confined to the editor.
