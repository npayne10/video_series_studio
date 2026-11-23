# Governed OpenAI MASTER generation and approval — specification v1.0

**Decision:** Target workflow approved by Neill on 2026-11-23.
**Implementation:** PROPOSED, not present in the current VSCS application.
**Tracking:** [Issue #67](https://github.com/npayne10/video_series_studio/issues/67), separate from [Issue #61](https://github.com/npayne10/video_series_studio/issues/61) and its [draft PR #66](https://github.com/npayne10/video_series_studio/pull/66).
**Boundary:** No API spend, GPU job, CAP/Canon promotion, MASTER registration, derived image approval or video generation is authorised by this specification alone.

## 1. Why this workflow is necessary

VSCS must produce repeatable, distinctive asset images while preserving Story/CAP
physical identity and lowering operator effort and cost. One authoritative,
versioned MASTER is reused across Shots; category-required supplementary views
are generated from that version and individually reviewed. Generation never
equals approval. Proposed geometry must not become Story Canon by appearing in
an image, a prompt, a technical score or an AI response.

**As implemented today:** the operator creates and reviews an image separately
in ChatGPT, downloads it inside the active project, selects it in **Assets →
Add Asset / Edit Selected → Browse**, confirms that it is an approved ChatGPT
MASTER, then saves. That single Save creates/ensures the Draft CAP and registers,
approves and locks the MASTER. The origin checkbox is a human declaration, not
cryptographic proof. **Prepare Visual Identity** and local XCIC/ComfyUI can
prepare prompts or create local *Candidates*, not an approved ChatGPT MASTER.
**Generate Production References** already derives Supplementary Candidates
from a consistent locked MASTER, subject to individual approvals.

**Target:** an in-app **Generate OpenAI MASTER Candidate → Review/Correct →
Approve & Lock MASTER** workflow, requiring explicit consent and preserving
source bytes, evidence and provider identity. The approved external ChatGPT
image remains a supported manual import route.

## 2. Proposed user journey and authority boundaries

| Step | Operator experience | Persisted object | Authority granted |
| --- | --- | --- | --- |
| A | Select approved Story and identified Asset, inspect category and CAP | Read-only evidence and Draft CAP | None |
| B | Review exact Story-backed CAP geometry, materials, components, constraints and deferred attributes | Human CAP field decisions and source fingerprints | Only field decisions explicitly accepted |
| C | **Prepare MASTER Prompt (Offline)**; inspect positive and negative constraints and missing-identity blockers | Versioned prompt proposal and source mapping | None; zero provider calls |
| D | **Generate OpenAI MASTER Candidate** with visible provider, estimated/unknown cost, per-call confirmation and configured API credentials | Immutable generated Candidate, model/prompt/response provenance and file hash | None |
| E | Inspect original image against each accepted CAP field; Accept/Reject/Defer findings, request constrained edit or regeneration with fresh consent | Append-only review and attempt history; original Candidates retained | None |
| F | **Approve & Lock MASTER** after checking the *exact* selected file/hash, current CAP context and provenance | Versioned approved/locked MASTER, reviewed identity audit | MASTER authority only; CAP approval remains separate |
| G | **Generate Production References** for category-required views, preferentially through authorised local ComfyUI | MASTER-parented Supplementary Candidates | None |
| H | Independently review and Approve/Reject each derived view; reopen readiness | Individually governed Approved production views | Only the approved view; all other gates remain |
| I | Continue Camera, Lighting, Environment, Asset Resolution, Production Task and Schedule planning | Existing specialist approvals and plans | **STOP** before actual video-clip creation |

### Physical design and source evidence

- Separate **Story-grounded/accepted CAP facts**, **operator-approved design
  additions**, **AI proposals**, **deferred fields** and **negative constraints**
  in the prompt and review record.
- Require sufficient reviewed physical identity for a reproducible MASTER.
  Contradictory accepted fields are blockers. An unapproved dimensional number
  must not be guessed, persisted as Canon or silently treated as accepted.
- Do not infer an Asset exterior from an interior Shot's enclosing setting,
  or turn a cinematic camera viewpoint into a physical robot.
- Preserve provenance for every material field from approved Story/CAP sources.

### Source and version integrity

Each generated Candidate and subsequent approved MASTER should have at least:

- Project, Story, CAP asset ID/category, current source/context fingerprints;
- Origin type, provider endpoint and model identifier, API request ID if
  supplied, prompt, negative constraints, parameters, any revised prompt;
- Generation timestamp/actor, invocation approval record, response status and
  cost or usage evidence available from the provider;
- Original immutable image path, byte length, SHA-256, generation attempt ID;
- Human per-field image assessment and explicit approve/reject/defer reasons;
- Final approver, timestamp, approved source SHA, MASTER version, prior-version
  link and dependent-reference relationship.

An image generated via an **OpenAI API** is not proof that it was generated in
the **ChatGPT web app**. Add or policy-map an honest API-origin discriminator
instead of silently assigning the existing `chatgpt_master` origin. Existing
manual ChatGPT-origin images retain their distinct evidence and import route.
An API model's output, quality score or generated prompt never asserts Canon.

The final source bytes must match their approved SHA at review, registration,
reopen, derivation and replacement. A mismatch blocks further authority with
an explicit error; do not rewrite historical records to conceal it. A MASTER
replacement uses a new versioned file and refuses to strand active dependent
derived views. No in-place overwrites of locked source imagery.

## 3. Provider, cost and recovery contract

1. Offline prompt preparation, cached proposal loading, local quality review
   and reopening saved human decisions perform **zero** OpenAI image requests.
2. Each Generate/Correct/Regenerate action shows the actual provider/model,
   source image where applicable, proposed prompt, anticipated or unknown
   consumption, and a distinct affirmative operator confirmation. A past
   confirmation cannot be replayed after reopening or a source change.
3. An idempotent attempt/reservation prevents double-click and retry races.
   Timeouts, throttling, billing failures, invalid/binary responses and process
   crashes preserve an honest failed attempt without attaching a fabricated
   Candidate. Reattempt requires renewed consent.
4. No silent fallback to local ComfyUI or another paid provider when OpenAI
   fails. Alternative providers have distinct origin and cost classifications.
5. API keys are configured through normal protected provider settings; never
   recorded in CAP prompts, image metadata, logs or issue attachments.
6. Explicitly display that ChatGPT subscriptions and OpenAI API billing are
   separate; the API implementation must use the configured platform account
   and operator's spending constraints.

## 4. Review, correction and governance

- The initial result enters an isolated **MASTER Candidate** family/status,
  not an active `MASTER/LOCKED` production-library entry. Preserve every
  generated attempt and human finding even if all fields fail or are deferred.
- Compare image against the original accepted CAP excerpts: silhouette,
  proportions, geometry, materials, colours, component count/position and
  exact mechanical restrictions. Supporting scene context is never authority
  for an unseen asset.
- A correction may target only a human-reviewed ROI and defect, preserving
  unaffected regions. Multi-field correction is permitted only for an
  independently evidenced common defect, consistent with Issue #58.
- Human approval is a **distinct** action from image generation or prompt
  acceptance. The app must revalidate current CAP/story fingerprints, image
  SHA, reviewer evidence and MASTER parent/role before atomic registration.
- Derived references use category templates and parent/version provenance,
  are `Role=Supplementary` and `Lifecycle=Candidate` on creation, and only gain
  governed `Approved` through separately recorded human QC.
- CAP Canon, functional capability/constraint approval, Asset Resolution,
  specialist plans, schedule and Production each retain their own gates.

## 5. Implementation slices and test gates

| Slice | Deliverable | Acceptance evidence |
| --- | --- | --- |
| 67-A | Approved-CAP offline prompt/evidence builder | Deterministic inputs, deferred/contradictory blockers, no network |
| 67-B | Configured OpenAI image provider with explicit consent and budget guard | Mocked success, errors, retry/idempotency, no surprise calls |
| 67-C | Immutable Candidate persistence/provenance | Byte-hash and restart replay, stale-context failure, no authority mutation |
| 67-D | Human comparison and correction/rejection | Per-field evidence, source ROI, preserve historical candidates, no auto-accept |
| 67-E | Explicit MASTER approval/version/lock and revalidation | Atomic library/legacy consistency, role and origin policy, dependency protection |
| 67-F | Derived generation, independent view approval and readiness | Exact parent/version, all category-required views, fail-closed disagreements |
| 67-G | Windows operator UAT and manuals | Human screenshots, before/after hashes and authorised paid attempt ledger |

All automated tests run against fake/offline providers and disposable fixtures.
Required validation: Ruff check/format, Mypy, targeted Qt/integration and full
pytest. Perform a later controlled real API acceptance only after a separate
cost/operation authorisation. Never classify mocked outputs as a real MASTER.

## 6. Stage B pilot, then system-wide backlog

The immediate real-world pilot uses the **operator-approved ChatGPT-conversation
image for Diagnostic Console `CAP-PRP-002`**. It tests the current *manual*
import/approve/lock path first, with [exact handoff and operator instructions](Issue_61_Stage_B_Console_Reference_Handoff.md). The image is *not* in VSCS
yet. The user visually approved the image on 2026-11-23, while numeric scale
remains unresolved. Its source hash and file-transfer integrity must be
verified before import. No existing local Candidate is promoted.

**After** genuine MASTER registration, required derived-view generation,
independent human review, persistence and readiness have been demonstrably
tested, pause the feature-by-feature work. Reconcile parent [#55](https://github.com/npayne10/video_series_studio/issues/55), all unresolved
issues and new empirical defects into a **formal prioritised backlog** from
current state through full-system UAT, end-to-end approval and the first actual
video production run. Distinguish no-video planning acceptance from subsequent
provider/video execution approval, infrastructure readiness, protected evidence
and stop criteria. Do not prematurely declare whole-system production-ready.
