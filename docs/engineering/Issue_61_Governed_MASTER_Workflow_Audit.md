# Issue #61 — governed ChatGPT MASTER and derived-reference route

**Status (2026-11-23): Stage A Windows/operator offline UI and non-mutation
accepted; Stage B genuine MASTER import and derived-view testing pending.**
Parent #55, prerequisite #58. This audit neither creates actual
references nor approves a CAP or authorizes GPU/image/video production.

## Authority and the real UI route

The source of MASTER identity is an image **already made and explicitly approved
as ChatGPT-originated** by the operator outside this VSCS workflow. In VSCS,
**Assets → Add Asset** or **Assets → Edit Selected → Browse…** confirms that
provenance, registers the associated Asset and Draft CAP if needed, then
**immediately registers, approves and locks the MASTER in one save**. The user
must visually compare and correct/reject the image *before* giving this
confirmation; the dialog is **not an in-app staged MASTER Candidate review**.
The checkbox is a human declaration, **not** a cryptographic ChatGPT-origin
proof. Retain the originating ChatGPT conversation/result, prompt, reviewer,
approval decision, image path and SHA-256 outside the CAP's automated authority.
Do not use this control for local ComfyUI, XCIC, Qwen or supplementary candidates.

This workflow requires an image file **inside the active project** and explicit
confirmation. A successful save creates a canonical reference with legacy
`Role=Primary`, `Status=Approved`, `Locked=True`; its governed library record is
`family=MASTER`, `view=MASTER`, `origin=chatgpt_master`, `lifecycle=LOCKED`, with
reviewer/transition history. It does **not** approve the CAP or declare
Production Ready.

For an existing Asset with no governed MASTER, select it in **Assets → Edit
Selected**. Its existing `file_path` is not evidence of authority: the dialog
must show **“Asset file present — not a locked MASTER”** or **“Missing — select
a MASTER”** when no registered MASTER exists. Browse to the separately
reviewed legitimate MASTER file, check the exact origin confirmation, then
save. Selecting the same existing file explicitly is permitted only with a
fresh confirmation; unchanged path text is not consent.

For a replacement, produce a **new, separately named file/version** outside
the locked original and approve it first. **Assets → Edit Selected → Browse…**
archives the old MASTER and registers/approves/locks the new version. The
service refuses replacement while any active derived references depend on
the old MASTER; archive or resolve those dependencies first after explicit
review. **Do not overwrite the bytes at a locked MASTER's existing path.**
The current project library does not itself store a verifiable image-content
SHA for each registered MASTER; operator SHA preservation is required. Any
future automated immutability seal would be a separate scoped change.

**Canonical Profiles → Edit Selected → Canonical Reference Gallery** is not
the MASTER-promotion path. Imported/unregistered gallery images can be reviewed
and labelled, but those labels are not a governed MASTER registration.
**Supplementary local visual Candidates** (including Console Candidate 1 and
Workstation Candidate 2) remain exactly that, regardless of semantic scores.
No local Candidate may be silently assigned ChatGPT provenance or marked
MASTER/Primary. Changing gallery Primary with an active registered MASTER is
blocked.

## Derived views and independent human approvals

After confirming the active MASTER is LOCKED in both the library and its
legacy reference record, use **Canonical Profiles → select CAP → Generate
Production References**. The dialog is read-only until its Generate buttons
are explicitly activated. It shows `BLOCKED` and disables both Generate actions
if the MASTER is missing, unlocked, stale or has a missing source file.

Only derived views can be generated. The registered output is **Supplementary
Candidate**, with `origin=vscs_derived`, exact `view`, parent MASTER reference
ID, source MASTER version, provider/model/seed and associated image path.
Generated imagery is **not approved** by creation or evaluation. Opening the
generator without selecting Generate sends no request. Selecting a generation
action may execute the chosen provider and consume GPU/paid resources; obtain
separate operator consent before actual generation.

For each output, inspect the physical image against the accepted CAP design,
current MASTER and independent semantic/technical evidence. **Canonical
Profiles → Edit Selected → Gallery → Approve** for a registered derived
Candidate updates **both** legacy and governed reference statuses. The
`Governance: Production View — Approved` label is distinct from its legacy
`Status: Approved — Locked`; no score automatically triggers either change.

For older versions created before this alignment, the gallery may say legacy
Approved but governed Candidate. The new **Confirm Governed Approval** action
requires fresh human confirmation and then records an explicit governed
approval; it never silently repairs that mismatch. Gallery **Archive** also
updates both records, **Return to Candidate** removes an approval, and locked
MASTER cannot be unlocked, archived or promoted through gallery actions;
MASTER replacement and archival belong to the reviewed Assets revision route.

Category reference coverage is **not** synonymous with approval. A Candidate
view may be *present* but still blocks production readiness until its governed
approval is recorded. The new readiness check rejects a library Approved/Locked
label if its legacy reference is no longer Approved and Locked (and rejects an
improper role). No reference or quality score silently approves CAP, Canon,
structured capabilities/constraints, Asset Resolution or Production.

### Required category views (production templates)

| Category | Required views |
| --- | --- |
| Prop, Technology | MASTER, Front, Rear, Left, Right |
| Ship | MASTER, Front, Rear, Port, Starboard, Top, Bottom |
| Location, Environment | MASTER, Primary Three-Quarter |
| Character | MASTER, Full Body, Profile Left, Profile Right, Face |
| Vehicle | MASTER, Front, Rear, Left, Right, Top |
| Uniform | MASTER, Front, Rear, Profile Left, Profile Right |
| Planet | MASTER, Orbit, Surface |
| Audio, Camera, Lighting, Reference, Other | MASTER |

Recommended/optional views remain category-specific and are shown separately
in the Generate Production References dialog. A saved C1/C2 visual correction,
improved quality score or existing local supplementary image satisfies none
of these missing image/approval requirements.

## Verified code and offline acceptance matrix

1. **True MASTER state:** Asset Editor no longer infers LOCKED from a registry
   file path. Selecting a file requires affirmative provenance attestation.
2. **Source gating:** missing/unlocked/disagreeing library and legacy MASTER
   blocks both generation buttons, provider dispatch and readiness.
3. **Separate gallery and governed lifecycles:** derived Approve, Return,
   Archive and Candidate actions route to `ReferenceLibraryService` for
   registered references. Unregistered legacy references retain only their
   clearly labelled, non-production gallery path.
4. **Authority containment:** registered derived can never become Primary
   or MASTER through the gallery; MASTER lock cannot be silently removed by
   legacy Unlock or gallery Archive. Active dependent derived references block
   MASTER revision archival in Assets.
5. **Historical reconciliation:** a legacy Approved/governed Candidate mismatch
   remains non-ready until a fresh human **Confirm Governed Approval**.
6. **Readiness:** required derived views must be individually approved;
   CAP Approved, visual identity, production guidance, structured functional
   capabilities and canonical constraints still have separate gates.
7. **Zero provider calls:** synthetic offline tests use the test-only preview
   generator; no actual ComfyUI, ChatGPT or video request is executed.

Do not count this as an operator-confirmed real MASTER/derived lifecycle until
the Windows runbook in `docs/user_manual/VSCS_User_Manual.md` has captured the
necessary screenshots and source-file SHA evidence. In particular, no
legitimate ChatGPT MASTER was supplied to the original engineering audit;
physical image fidelity and protected pixels cannot be certified from offline
tests. A new ChatGPT image was subsequently generated and visually approved
by Neill on 2026-11-23, but it has **not** yet been imported or locked in VSCS;
see [the source-specific Stage B handoff](Issue_61_Stage_B_Console_Reference_Handoff.md).

## Real-world test boundary and stop conditions

**Stage 1 — offline, no writes:** Open the existing protected disposable project,
inspect Assets and CAP Readiness, open Generate Production References and
confirm blocked state, inspect existing supplementary Candidates and their
saved reports. Cancel all dialogs. Verify all protected before/after hashes.
No generation or acceptance is authorised at this stage.

**Stage 2 — separately authorised production-reference work:** Only after
Neill supplies/reviews an authentic ChatGPT-origin approved MASTER and
explicitly permits the project writes, capture the old file/directory hashes,
import via Assets, check audit/lifecycle/role, derive *only* approved view
choices with separate provider consent, inspect each Candidate and approve or
reject individually, re-run readiness and verify expected new evidence.
This stage intentionally changes `cap_reference_library.json`, the project
asset/CAP database and reference files; its before/after inventory must name
each expected change rather than require equality. Stop at every unresolved
gate. **No production video clips.**

Blocked/missing MASTER, uncertain ChatGPT origin, a changed locked image,
unexpected duplicate PRIMARY, inconsistent legacy/governed states without
human consent, missing CAP visual design, stale Story/Shot authority, or
missing candidate approvals are reasons to stop—not reasons to fabricate
reference readiness or promote a local supplementary Candidate.
