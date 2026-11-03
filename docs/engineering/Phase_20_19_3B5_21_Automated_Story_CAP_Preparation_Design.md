# Phase 20.19.3B.5.21 — Approved Story to Automated CAP Preparation and Review

Status: **B.5.21A and B.5.21B accepted and closed — 2026-11-03. B.5.21C remains planned.**  
Date: 2026-11-03  
Predecessor: B.5.20 closed at 2,371 passing tests  
Repository: `npayne10/video_series_studio`  
Branch: `phase-20.18.2.3.6.3-local-r2v-provider-evaluation`

## Purpose and governing principles

Remove repetitive context-pasting and manual per-asset triage by extending the existing **Story → CAP Batch…** capabilities. Four project objectives remain binding: automation, cinematic identity/continuity, low cost, and ease of use. Human review and explicit production authority must remain intact. This phase prepares and persists **reviewed Draft CAPs only**.

Do **not** create another CAP generator, replace the existing Story batch workflow, alter Story/Shot approval states, silently create CAP dependencies, publish Canon, approve reference images, or permit H3 live execution.

## Verified architectural baseline (GitHub)

- `src/vscs/presentation/dialogs/story_cap_batch_dialog.py` contains `StoryCAPBatchDialog`, with `Discover Shot Assets`, `Review Cached Proposal`, paid AI confirmation, human review, cached proposal, and one-item Draft persistence.
- `src/vscs/application/caps/story_batch_review.py` contains `StoryCAPBatchReviewService.discover()`; it scans `planning/asset_resolutions.json` and registered project assets but currently has **no selected-Story parameter**.
- `src/vscs/application/caps/story_batch.py` has approved/locked Story checks and story-description fingerprinting; `preview()` currently calls the generation service for every uncached target.
- `src/vscs/application/caps/story_specification.py` builds provider-assisted advisory structured CAP proposals. Its `source_description` currently describes operator-supplied context; adapt for actual provenance when automated context is introduced.
- `src/vscs/application/caps/proposal_cache.py` has atomic project-scoped unapproved proposal caching keyed by Story, asset and provider fingerprints. Current v1 schema must remain readable for recovery, but must not be promoted to verified context.
- `src/vscs/application/caps/design_completion.py` provides field decisions (accept/edit/reject/defer), provenance classifications, review fingerprints and Draft persistence.
- `src/vscs/application/caps/governed_planning_evidence.py` has discovery-only versus verified Shot evidence separated, and `ProductionPlanningContracts` delegates to the existing Episode, Scene and Shot hash calculators.
- `StoryCAPBatchReviewService.save_reviewed` rechecks Story fingerprint, asset category, CAP state, dependencies, and persists only after explicit review.
- B.5.20 isolated positive path and actual negative path are accepted. Original operator project has four Draft assets, no CAPs and no MASTER references; none of those conditions are changed by this design.

## Phase boundaries and acceptance strategy

**B.5.21A — Story-scoped, offline CAP intake and authoritative-context manifest (P0).**
1. Extend `StoryCAPBatchReviewService` to accept the selected approved Story ID in discovery. Resolve only existing Story→Episode→Scene→Shot ownership from persisted governed records; never use ID-prefix coincidence or scan unrelated Stories as eligible.
2. Keep source levels separate: (a) approved/locked Story statements; (b) contract-verified Ready Shot evidence with approved bindings; (c) planning narrative that is visible for review but **not approved evidence**; (d) provider design proposal; (e) unresolved.
3. For the current Draft-bound Golden Path, show four assets as *associated/discovered, but Shot evidence unverified*, with explicit reasons. Approved Story text remains eligible as its own authority; never elevate Draft Shot prose to Canon.
4. Introduce a non-mutating `CAPContextManifest` (or equivalent existing-model extension): story ID; asset ID; source type; source record ID; field; excerpt/span; governance level; contract verification result; content fingerprint; asset/category fingerprint; warnings. Reuse existing authority utilities.
5. Deterministic ordering, deduplication, scope leakage checks, explicit unmatched/ambiguous identities and zero-source messages. Do not infer missing assets by text-only name matching.
6. UI: add **Prepare CAP Context (Offline)** and a provenance review for selected asset; no paid provider calls and no writes to CAP/Canon. The `Discover Shot Assets` function remains available and is reused.

**B.5.21B — Queue planning, cache-first reuse and cost gates (P0).**
1. Add an advisory queue/view in the existing batch dialog (not a second workspace) listing: eligible asset ID/name/category, missing/existing CAP, authoritative context status, cached proposal status, deferred/review state and unresolved blockers.
2. Default to reuse the existing v1 cache when its original metadata is valid; show its *legacy provenance limitations*. New v2 context fingerprints include the complete authoritative context manifest and selected workflow schema version. A v1 cache is not automatically upgraded to an approved v2 claim.
3. Offline preparation computes manifests and cache eligibility for multiple assets without provider calls.
4. Paid/provider generation is per asset (or explicit reviewed multi-selection), opt-in with provider identity and cost disclosure/budget cap where pricing is available; never claim exact costs where unavailable. A cancellation makes no CAP change. No unexpected regenerate-on-review.
5. Free/local provider routes are future adapters through existing provider abstraction, not new hardcoded model implementations in this phase. Explicitly label unavailable routes.
6. Checkpoint and resume queue safely; invalidate only affected proposals when Story, asset, verified planning context or provider configuration changes.

**B.5.21C — Reviewed Draft CAP persistence and UI acceptance (P0).**
1. Reuse `StoryCAPSpecificationDialog`, `CAPDetailReviewDialog`, `DesignReviewPackage` and `StoryCAPBatchReviewService.save_reviewed`.
2. Before persist, re-read source fingerprints and governed contracts. Refuse changed ownership, stale text, differing asset category, existing approved CAP, stale provider fingerprint or contradictory dependencies. Preserve existing revision workflow.
3. Persist **one explicitly reviewed item at a time** as Draft with provenance and decision records. No automatic approvals, canonical image generation, MASTER binding or paid call.
4. All design-only values (layouts, dimensions, materials, lighting, spatial anchors) remain proposals until separately reviewed. Never fabricate coordinates, clearances or mounts from prose.
5. Make disabled controls and failure reasons visible; confirm saved/rejected/deferred status without operator guesswork.

**Later phases — not B.5.21 acceptance:** canonical image candidate generation, MASTER selection/approval, production asset readiness, real-project positive end-to-end context UI, direct asset→CAP navigation correction, and provider performance/shot-duration policy.

## Suggested interfaces (design, not fixed API)

`discover(story_id: str) -> tuple[CAPAssetCandidate, ...]` with Story provenance/status diagnostics; retain compatibility only if it cannot bypass scoping.

`prepare_context(story_id: str, asset_id: str) -> CAPContextManifest` (offline, immutable, read-only).

`plan_queue(story_id: str, asset_ids: tuple[str, ...]) -> CAPPreparationPlan` (offline, cache-only).

`review_one(...)` and `save_reviewed(...)` continue to invoke the existing dialogs/services. Keep provider generation separate from context preparation and cache inspection.

Contract authority follows the existing `verified_governed_shot_evidence` verifier; hash shape alone is not freshness. A context manifest can report Draft-bound narrative as unverified but must never forward it through `verified_shots_to_spatial_sources`.

## Safety invariants

- No cross-Story leakage; no implicit scene ownership; no unapproved binding promotion.
- Every provider inference distinguished from source evidence; unresolved stays unresolved.
- Cache never equals Canon. Cached human edits are preserved unless operator explicitly replaces them.
- No writes to asset statuses, planning statuses, approved references or reference-image files during context preparation.
- Project provenance and source fingerprints checked again at the point of Draft persistence.
- Any unsupported source, empty context, duplicate asset ID or category mismatch yields an intelligible result without silent fallback.
- No paid request or batch expenditure without explicit consent and a clear provider selection.
- User's existing untracked architecture audit file remains untouched.
- H3 live-generation hold remains active.

## Acceptance matrix (to implement during B.5.21 development)

1. Approved Story selected; only linked registered Shot assets discovered, in stable order.
2. Two Stories and overlapping asset names: no wrong-story context leak.
3. Golden Path Draft bindings: four assets found, unverified Shot text visibly labelled and never promoted to approved evidence.
4. Contract-verified Ready bindings: evidence manifest includes source IDs and appropriate verified statuses.
5. Tampered Shot text, stale parent hashes or changed binding status: context invalidated; no persistence.
6. Cached proposal: review does not invoke paid provider; operator edits remain preserved.
7. Context, asset, Story or provider change: stale queue/cache invalidated with explanation.
8. Missing CAP and existing Draft CAP: correct queue classification and no duplicate record.
9. Unsupported dimensions/mounts/canonical identity: blocked or explicitly deferred, never guessed.
10. Explicit reviewed Draft save: correct single-asset persistence and complete provenance; cancellation: zero writes.
11. Qt tests for buttons, queue states, source status, paid confirmation, cancellation and no cross-Story bleed.
12. Ruff lint and format clean; mypy clean; targeted tests and full pytest suite pass; `git diff --check` clean.

## Operator UI test script (exact controls after implementation)

1. Open original Golden Path project → **View → Canonical Profiles** → **Story → CAP Batch…**.
2. Select **STORY-001 — The Quiet Console — Episode Audit**.
3. Click existing **Discover Shot Assets**. Expect `CAP-LOC-001`, `CAP-ENV-001`, `CAP-SHP-001`, `CAP-PRP-001`; all missing CAP; Draft bindings remain explicitly unverified.
4. Select `CAP-LOC-001` → click new **Prepare CAP Context (Offline)**. Expect verified Story source separately labelled from unverified Shot wording. No provider call or data mutation.
5. Review the batch queue and any cached proposal. Confirm the latter is marked unapproved; do not assume new generation is free.
6. Confirm that cancelling or closing leaves the original project and cached proposal unchanged.
7. For approved positive-path source forwarding use a disposable test project with real contract calculators and verified Ready binding fixture; never alter production JSON manually.
8. The actual control location and text must be checked against implementation screenshots before asking the operator to perform it.

## Local validation and development standard

Develop and commit directly to the same GitHub working branch, provide pull commands, then run target and full regression suites, Ruff lint/format, mypy, and Qt tests; correct defects in GitHub before closure. Baseline from B.5.20: **2,371 pytest passing**, **1,566 files formatted**, **662 mypy-clean source files** (baseline, not guarantee for this phase). Formal closure requires operator evidence, negative-path and positive-path acceptance, and updated phase documentation.

## Implementation order and decision gate

Implement B.5.21A first (offline read-only context manifest and Story-scoped discovery); complete its targeted/UI acceptance before B and C. This avoids paid generation while the correctness of source scope and authority is still being established. Do not change runtime behaviour solely by committing this design.

## B.5.21A implementation record — 2026-11-03

Scope implemented on the existing VSCS working branch (no parallel CAP generator):
- New `src/vscs/application/caps/context_preparation.py`: immutable read-only `CAPContextManifest` and source entries with Story and asset fingerprints, record ID, field, excerpt, source-level authority and warnings. Reuses existing governed evidence discovery, original production hash calculators and verifier.
- `StoryCAPBatchReviewService.discover(story_id)` now scopes bindings to the selected Approved/Locked Story's governed Ready Episode→Scene→Shot hierarchy, checks unique plan identity and asset category, and returns deterministic candidates. Legacy no-argument access is permitted only if exactly one approved Story exists.
- `StoryCAPBatchReviewService.prepare_context(story_id, asset_id)` validates Story authority, registered asset binding, current Story fingerprint and project root; never writes.
- New **Prepare CAP Context (Offline)** button in the existing `Approved Story → CAP Batch Review` dialog. It shows authority labels, source text and warnings. Switching Stories clears the previous asset selection to avoid stale or cross-Story actions.
- Actual Draft or missing bindings remain discovery-only context, marked `unverified_shot`; any Shot text is marked `verified_ready_shot` only when its snapshot equals the result of the real contract verifier. No Canon or image approval.
- New targeted tests: `tests/test_phase_20_19_3b5_21a_context_preparation.py` covering verified, Draft, stale, wrong-Story, duplicate ownership, Story-scoped discovery and Qt button safety.
- **Not yet executed locally**; this is *not* phase closure. No provider API calls, paid generations or source-project data mutations were performed to implement these changes.

### Exact first UI acceptance sequence after clean local tests
1. Open the test project containing **STORY-001 — The Quiet Console — Episode Audit**.
2. Select **View → Canonical Profiles**.
3. Click **Story → CAP Batch…**; verify title **Approved Story → CAP Batch Review**.
4. Select **STORY-001 — The Quiet Console — Episode Audit**.
5. Click **Discover Shot Assets**. Expected four candidates `CAP-ENV-001`, `CAP-LOC-001`, `CAP-PRP-001`, `CAP-SHP-001` (ordered by ID), assuming the same governed planning data as previously tested; all CAPs remain missing.
6. Select `CAP-LOC-001` from the candidate dropdown.
7. Click **Prepare CAP Context (Offline)**. Expected **Prepared CAP Context (Offline)** information dialog with Story, asset, manifest fingerprint, approved Story text and **unverified_shot** labels/warnings for Draft-bound Shot text.
8. Verify that the dialog says no CAP/Canon changed. Click **OK**; source summary stays visible in main batch dialog.
9. Change the Story dropdown only if another approved Story exists; the asset selection should clear and require fresh discovery.
10. Click **Close** without any generated or reviewed Draft save. Check CAP count remains zero and existing cached proposal is intact.

### Operator verification commands
```powershell
cd D:\VSCS\video_series_studio
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_21a_context_preparation.py -v
python -m pytest -q tests/test_phase_20_19_3b5_20_governed_positive_acceptance.py -v
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```

No claims of full regression/format acceptance should be made until the operator runs the above checks. Untracked `docs/VSCS_Architecture_Workflow_Audit_2026-10-24.md` remains outside this phase's commits.

### Regression correction note — 2026-11-03

Initial local validation provided by the operator: B.5.21A 7/7, B.5.20 positive acceptance 3/3, mypy clean (663 source files), full regression 2 failed / 2,376 passed. The two failures were in legacy `tests/test_phase_20_19_3b5_1_batch_review.py` tests, which did not construct an approved Story or actual governed Episode/Scene/Shot evidence after the stricter Story-scoped discovery contract was introduced. Their fixtures were migrated to real planner records and authentic contract hashes rather than introducing a bypass. Ruff import-order and formatting fixes were applied in GitHub. These corrective commits require a fresh local verification before acceptance.

## B.5.21A final acceptance record — 2026-11-03

**Development acceptance: CLOSED.** Operator validation on Windows / Python 3.13.7 / PySide6 6.11.1:
- Legacy `test_phase_20_19_3b5_1_batch_review.py`: **4 passed**.
- New `test_phase_20_19_3b5_21a_context_preparation.py`: **7 passed**.
- Full regression: **2,378 passed**.
- Ruff check clean; Ruff format check: **1,569 files already formatted**.
- Mypy: **663 source files clean**.
- `git diff --check`: clean. Existing untracked `docs/VSCS_Architecture_Workflow_Audit_2026-10-24.md` preserved.
- UI-01: Selected approved `STORY-001 — The Quiet Console — Episode Audit`; **Discover Shot Assets** returned four missing CAPs in ascending ID order: `CAP-ENV-001`, `CAP-LOC-001`, `CAP-PRP-001`, `CAP-SHP-001`.
- UI-02: Selected `CAP-LOC-001`, clicked **Prepare CAP Context (Offline)**; observed Story/asset IDs, context fingerprint, `approved_story_context` from Story description, three `unverified_shot` fields (`required_action`, `narrative_purpose`, `production_objective`) and the authority warning that Draft/missing bindings are not approved evidence.
- UI-03: Returned to Canonical Profiles; screenshot confirmed **0 CAP(s) — 0 production ready**.
- The test verifies a read-only context operation; it **does not** certify full production asset approval or CAP/reference workflow readiness. Real governed Ready-binding positive path remains isolated automated acceptance from B.5.20. No paid generation occurred in the acceptance flow.
- **Next:** B.5.21B — Cache-first Preparation Queue, reusing the existing batch dialog, cache and provider cost confirmation; no duplicate CAP generation system.

## B.5.21B implementation record — 2026-11-03

Status: **Development acceptance CLOSED — 2026-11-03.**

### Implementation
- Reused `StoryCAPBatchDialog` and added **Prepare Queue (Offline)**. After **Discover Shot Assets**, it shows a Story-scoped multi-asset queue in the existing summary panel. Queue inspection does not call the provider, write CAPs, or mutate cached proposals.
- New `src/vscs/application/caps/preparation_queue.py` uses B.5.21A `StoryCAPBatchReviewService.discover(story_id)` and `prepare_context(story_id, asset_id)` to classify `already_specified`, `context_blocked`, `cached_current`, `legacy_cached`, `stale`, `invalid`, and `missing`.
- Extended `CAPProposalCache` with read-only `inspect` and version 2 optional governed-context fingerprints. Existing v1 records remain recoverable, clearly labelled **legacy cached**; they are **not** claimed to prove verified Shot authority. A v2 record is reusable only when Story, asset, provider and current manifest fingerprints match.
- Existing **Review Cached Proposal** loads a matching persisted cache with current context. For v1, the operator receives a clear legacy advisory. For stale/missing v2, the user receives a reason rather than a paid regeneration.
- Existing **Generate / Regenerate Using AI (Paid)** remains one operator-confirmed request per asset. Its confirmation displays provider/model identifiers and explicitly says the exact price is unavailable. There is no autonomous paid batch execution.
- The current provider-generation prompt still uses the original approved Story description; the context fingerprint is a **freshness guard**, not a claim that multi-field governed context was sent to the AI provider. Grounded enriched provider input is a separately reviewed future change.
- Reviewed working proposals are saved as context-bound v2 caches; fresh context is rechecked before caching edits and again before the existing Draft CAP save gate.
- Story selection changes clear asset and queue controls; direct CAP/Canon/reference approval is not performed.

### B.5.21B targeted acceptance
- `tests/test_phase_20_19_3b5_21b_preparation_queue.py`: legacy cache recovery, v2 context and provider stale rejection, multi-asset read-only cache-first inspection, skip already-specified assets, Qt queue inspection, Story change reset and declined paid consent; invalid cache rejection; blocked-context reporting without provider calls.
- Also rerun B.5.21A targeted tests, legacy batch-review tests, existing cache tests, Ruff lint and formatter, mypy, full pytest suite, `git diff --check`, and `git status --short`.
- Baseline before implementation: **2,378 passed**, **1,569 files Ruff-formatted**, **663 mypy-clean files**.
- Do not claim acceptance until operator reports clean run and actual UI output.

### Exact operator UI acceptance (only after full green automated gates)
1. Start VSCS and open **The Quiet Console — Episode Audit**.
2. **View → Canonical Profiles → Story → CAP Batch…**.
3. Select `STORY-001`, click **Discover Shot Assets**, verify four assets and no new CAP.
4. Click **Prepare Queue (Offline)**. Expect four Story-scoped entries in main summary: previously saved Engineering Control Room (`CAP-LOC-001`) may show **legacy_cached**, others **missing**, depending on real cache validity. Each line includes context authority and reasons; Draft Shot context remains unverified.
5. Capture screenshot; do not click paid generation or save. If `CAP-LOC-001` shows stale/missing, inspect specific cache metadata and provider configuration rather than regenerating.
6. Close and confirm Canonical Profiles still displays **0 CAP(s) — 0 production ready**; existing cached proposal and untracked audit document remain untouched.

### Validation commands
```powershell
cd D:\VSCS\video_series_studio
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_21b_preparation_queue.py -v
python -m pytest -q tests/test_phase_20_19_3b5_21a_context_preparation.py -v
python -m pytest -q tests/test_phase_20_19_3b5_1_batch_review.py -v
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```

B.5.21B queue fingerprint now also includes the current persisted binding status and planning hashes (not just displayed text) so safety-relevant governance changes invalidate v2 caches. Final expected full test count if the prior 2,378 baseline is unchanged: **2,385** (seven new B.5.21B tests). Await actual operator test output before acceptance. The latest development test has not been executed in this ChatGPT environment.

## B.5.21B final acceptance — 2026-11-03
- Local operator quality gates: targeted B.5.21B **7 passed**; full pytest **2,385 passed**; Ruff check passed; Ruff format check **1,571 files already formatted**; Mypy **no issues in 664 source files**; `git diff --check` clean.
- `git status --short` shows only preserved untracked `docs/VSCS_Architecture_Workflow_Audit_2026-10-24.md`.
- Actual UI: **Approved Story → CAP Batch Review**, `STORY-001 — The Quiet Console — Episode Audit`, **Prepare Queue (Offline)**. Provider displayed `OpenAICAPGenerationProvider (gpt-5.5)`.
- Four discovered assets and statuses: `CAP-ENV-001` = missing / unverified_shot; `CAP-LOC-001` = legacy_cached / unverified_shot; `CAP-PRP-001` = missing / unverified_shot; `CAP-SHP-001` = missing / unverified_shot.
- UI explicitly reports no paid requests, CAP writes, approvals or cache modifications. Legacy proposal remains labelled as lacking governed Shot context fingerprint at generation time. No Canon or production-readiness claim is made.
- **Acceptance scope:** cache-first read-only planning, status/provenance presentation, legacy proposal preservation, cache freshness guards and separate explicit provider consent. Operator did not perform paid generation or end-to-end Draft save for this phase.
- **Next phase:** B.5.21C — Reviewed Draft persistence and source freshness at the actual commit boundary. Maintain explicit per-asset human design decisions, rollback safety and existing Canon/reference restrictions. H3 live-generation hold remains active.

## B.5.21C implementation record — 2026-11-03

Status: **Code and tests committed; local regression, Ruff/Mypy and operator acceptance PENDING. Not closed.**

### Existing architecture reused
- **StoryCAPBatchDialog** retains its existing one-asset-at-a-time sequence: cached proposal → StoryCAPSpecificationDialog → local working cache → CAPDetailReviewDialog → explicit Save confirmation → StoryCAPBatchReviewService.save_reviewed. No new CAP writer, no background process, no paid provider calls from persistence.
- **CAPDetailReviewDialog** now exposes all populated canonical attributes and all provider-proposed fields as well as the category's required fields. Each field defaults to **DEFER**, avoiding implicit acceptance of unsupported design descriptions.
- **DesignReviewPackage** now includes optional `context_fingerprint`; audit metadata `vscs.cap_design_review.v1` retains Story and context fingerprints, review decisions, reviewer, and explicit `canon_approved=false` / `image_authorized=false`. `apply_review` rejects a package lacking decisions for any already populated canonical attribute.
- **StoryCAPBatchReviewService.save_reviewed** accepts a new optional `expected_context_fingerprint`. When supplied (the operator's governed batch workflow), it requires a reviewed package with matching Story/context fingerprints and re-runs `prepare_context` **inside the service before the first CAP write**. Any stale or missing fingerprint refuses the operation without new CAP creation.
- **StoryCAPBatchDialog** passes the reviewed Story/context fingerprints to the save service and validates provider identity immediately before the commit call. It retains the B.5.21B pre/post Review freshness checks and the original separate operator confirmation.
- Existing `DesignReviewPersistence` still writes one Draft CAP metadata update. Newly created empty Draft CAPs are deleted on failed persistence only when the stored specification is absent; pre-existing Draft CAPs are not destructively rolled back. Canon and MASTER references remain unchanged.

### Explicit limitations
- The richer approved Story/Shot context is used to verify provenance and freshness, **not** automatically appended to paid provider generation prompts. Do not misrepresent Draft Shot narratives as approved Story Canon.
- Legacy direct `save_reviewed` call sites without `expected_context_fingerprint` remain supported for previous reviewed workflows; **only the governed Story → CAP Batch operator path asserts the additional B.5.21C context gate**. Consider a future migration for every other caller.
- A successful Draft CAP is **not** an approved Canon, reference image, or production-ready asset.
- This phase does not perform actual paid generation, reference production, H3 execution, or modification of the test project's four missing CAP records.

### Automated acceptance
`tests/test_phase_20_19_3b5_21c_reviewed_draft_persistence.py` covers complete field decisions and provenance audit, stale/missing Story/context rejection before writes, Draft-only persistence, rollback after write failure, refusal to overwrite an approved CAP, and Qt visibility of all populated attributes. Rerun B.5.21B, B.5.21A, legacy batch review, Ruff check/format, mypy and full pytest. Prior verified baseline: **2,385 passed**, **1,571 formatted files**, **664 mypy-clean source files**.

### UI operator acceptance after all code quality gates pass
1. Open the existing **The Quiet Console — Episode Audit** project → **View → Canonical Profiles → Story → CAP Batch…**.
2. Select `STORY-001` → **Discover Shot Assets** → **Prepare Queue (Offline)**. Expect four Draft-bound/missing CAP assets, one `legacy_cached` (`CAP-LOC-001`), three `missing`.
3. Select `CAP-LOC-001` → **Review Cached Proposal**. Expect an advisory that the legacy proposal lacks current governed Shot context verification.
4. Review the specification (do not infer geometry) and open **Review CAP Detail Decisions**. Verify all populated fields (e.g. `architecture`) appear alongside category-required fields; all begin **Defer**.
5. Click **Cancel** at the field-review dialog. Confirm no CAP was created. No accepted design details or paid generation are required for safe cancellation acceptance.
6. Verify Canonical Profiles still shows **0 CAP(s) — 0 production ready**.
7. The positive Draft-save path is covered by isolated automated tests and should be tested on a disposable governed project before any live operator persists actual creative decisions.

### Operator commands
```powershell
cd D:\VSCS\video_series_studio
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_21c_reviewed_draft_persistence.py -v
python -m pytest -q tests/test_phase_20_19_3b5_21b_preparation_queue.py -v
python -m pytest -q tests/test_phase_20_19_3b5_21a_context_preparation.py -v
python -m pytest -q tests/test_phase_20_19_3b5_1_batch_review.py -v
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```
