# Phase 20.19.3B.5.21 — Approved Story to Automated CAP Preparation and Review

Status: **PROPOSED DESIGN — not implemented or accepted**  
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
