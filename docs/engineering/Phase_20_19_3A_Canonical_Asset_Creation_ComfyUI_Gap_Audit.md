# Phase 20.19.3A — Canonical Asset Creation & ComfyUI Integration Gap Audit
Date: 2026-10-26
Status: Read-only architecture audit; implementation **not authorized** by this document
Scope: VSCS Story-to-ProductionTask golden-path project and existing asset/CAP/reference/XCIC infrastructure
Safety: H3 live-video hold remains active. No provider submissions, production project mutations, or schema migrations made.

## 1. Executive decision
**Extend and orchestrate existing subsystems; do not build a second asset library, duplicate CAP authority, or a parallel image-generation engine.**
Target: Story Intelligence → matched/new Draft project Asset → category-specific structured CAP proposal → human specification approval → preflighted local ComfyUI candidate generation → human visual QC and approved Master selection → existing CAP/reference/asset approvals → Shot asset-binding readiness reconciliation. Each promotion remains explicit, revisioned and auditable.

The audit is based on the user-supplied Xorix Character CAP and Location CAP documents, VSCS screens from the Golden Path, and code on branch `phase-20.18.2.3.6.3-local-r2v-provider-evaluation`. Code inspection alone does **not** demonstrate running local image compatibility.

## 2. Source CAP standards and import risks
### Character sample
Character documents include ID/category/priority/version, purpose and visual design intent, locked facial/anatomical/clothing identity, presentation defaults, permitted pose/expression/costume/camera/light/background variables, a master prompt, derived variants, dependencies, continuity and revisions. Example: Commander James Spence `CAP-CHR-001`. A source document marked LOCKED is a **document claim**, not proof of VSCS approval or image QC.

### Location sample
The Location document's `CAP-LOC-001` identifies **Commander James Spence's Apartment**: layout, wall/floor/ceiling materials, window geometry, palette, fixtures, scale, fixed spatial relationships, time/occupancy/camera/light/weather variables, master 16:9 image prompt, linked characters/props/environment, continuity and view variants. The document's `CAP-LOC-002` covers a corridor, and `CAP-LOC-003` covers an elevator with door-state variants. A Location CAP cannot be modelled simply as a Character prompt with renamed fields.

**Collision warning:** Golden Path `CAP-LOC-001` is **Engineering control room**, not the Xorix apartment. IDs have project scope; never import Xorix document records into the Golden Path project by identical IDs, overwrite an existing asset, or interpret the document's LOCKED label as a current database lifecycle state. Import requires namespace/project identity, explicit mapping and collision preview.

### Proposed shared specification contract
Stable project/asset identity; category/subcategory; source Story/proposal provenance; visual design intent; canonical invariant fields; category-specific technical attributes; allowed variables and valid values; master prompt + negative prompt + model-specific compiled prompt; dependencies; continuity constraints; reference-view requirements; revisions/checksums; review and lock evidence. Maintain a **separate** authored specification from generated prompt and produced image. Retain original DOCX attachment provenance and content hash if imported.

Category extensions:
- Character: anatomy, face/hair/skin/eyes, proportions, costumes, expression/pose states.
- Location: layout, geometry, measurements, spatial anchors, architecture/materials/fixtures, fixed sightlines, doors/windows, allowed occupancy/time/weather/view changes.
- Ship/vehicle: dimensions, silhouette, hull/markings, topology, exterior/interior relationships.
- Prop/equipment: components, geometry, user interface, operation states (e.g. indicator pulsing is a console component, not obligatorily a separate asset).
- Environment: geography/sky/terrain/atmosphere, time/weather states.
- Costume/uniform and other registered categories: category-dependent design/fit/insignia attributes.
Avoid silently generalizing beyond registered category types; inventory and test each schema.

## 3. Verified implementation inventory
| Component (repository path) | Existing evidence | Remaining gap |
|---|---|---|
| `presentation/widgets/asset_manager.py` | Asset metadata/status and MASTER image selection; Edit dialog still says approved **ChatGPT** master | Provider-neutral creation wizard and provenance-driven master selection |
| `application/caps/service.py` | `CAPService`: CAP create/get/list/update, linked to existing Asset | Structured AI draft/review path from Story Intelligence |
| `application/caps/repository.py` | `CAPRepository` persists CAP through SQLAlchemy/`DatabaseManager`; structured facts, capabilities, constraints, metadata JSON columns | Audit all schema versions, migrations and competing data ownership before new columns |
| `application/caie/engine.py` | CAIE v2 compiles canonical description, visual identity, production notes and rules into prompts | Category-aware protected invariants, variant policy and traceable source sections |
| `presentation/dialogs/canonical_asset_generation_dialog.py` | Candidate-generation dialog with prompt/negative prompt, model, seed, dimensions and variations; currently labels XCIC/Qwen | Provider registry, model discovery, guided QC and reliable operator visibility |
| `application/caps/asset_generator.py` | `CanonicalAssetGeneratorService` invokes CAIE and image provider and stores generated candidates/reference provenance | Confirm end-to-end UI wiring; clear distinction candidate vs Master; generation authorization |
| `infrastructure/ai/image_provider.py` | Provider-neutral `CanonicalImageGenerationProvider` protocol; `LocalPreviewImageProvider` produces SVG **mock previews**, not photoreal images | Separate mock/test output visibly from actual generated images |
| `infrastructure/xcic/provider.py` | `XCICImageProvider` composes `XCICCoreRenderer`, `XCICCoreClient`, queue jobs; saves PNG candidates | Read-only readiness/contract validation on current local ComfyUI before submission |
| `infrastructure/xcic/config.py` | `VSCS_XCIC_ROOT`, `VSCS_COMFYUI_URL`, workflow/mapping/profile paths; loader validation | Verify installation root, API workflow existence, node/model compatibility and Blackwell GPU support |
| `application/caps/reference_service.py` | CAP references created with imported lifecycle; explicit approval/update and lock enforcement | Candidate review/primary designation without circumventing governed approval |
| `docs/engineering/Phase_17_5_3_CAP_Canonical_Reference_Resolution.md` | CanonicalResolver uses approved CAP/reference and deterministic fingerprint | Revalidate Shot requirements after approvals and invalidate dependent planning selectively |

**Important terminology:** `CAP-LOC-001` is an **asset ID** in the Golden Path UI although a CAP profile does not yet exist. Never equate asset identifier prefix with an existing profile; query both records independently.

## 4. Current Golden Path evidence and blockers
Test project: `D:\VSCS\GOLDEN_PATH_AUDIT\RUN-001\Episode Audit`; Story `STORY-001` approved; Episode `EP-001`, Scene `EP-001-SCN-001`, Shot `EP-001-SCN-001-SHT-001` are Ready; one 45s Shot created from accepted planning proposal. Four inferred Shot asset bindings created as Draft:
- `CAP-LOC-001` Engineering control room;
- `CAP-ENV-001` Deep space;
- `CAP-SHP-001` Unmanned exploration vessel;
- `CAP-PRP-001` Diagnostic console.
Asset binding editor diagnoses: selected Location asset is not production-approved and lacks CAP. Asset Manager shows Draft, missing Master Reference. No evidence yet that approved reference exists. Do **not** mark Ready or attach a placeholder.

Independent Golden Path issues retained: proposed 45s Shot versus displayed governed maximum 15s; UI conservative 8GB hardware profile versus actual RTX 5060 Ti 16GB; Episode editor minimum 60s versus proposal 45s. These are not solved by asset generation and remain separate investigations.

## 5. Gap and risk register
| ID | Severity | Gap | Required response |
|---|---|---|---|
| AG-01 | High | Asset Manager mandates external ChatGPT Master wording | Provider-neutral review and approved-Master handoff |
| AG-02 | High | Source documents' immutable/variable category schemas not captured as first-class policy | Versioned category-specific structured specifications with explicit change rules |
| AG-03 | High | Story-approved entity → Draft Asset → CAP has no demonstrated one-click governed handoff | Proposal-only automated drafting; human approval |
| AG-04 | High | XCIC code exists but current ComfyUI model/workflow availability not live-verified | Read-only GET diagnostics; workflow/node/model contracts, file access, VRAM policy |
| AG-05 | High | Candidate and Master lifecycle could be confused | Different states/identifiers and never auto-promote |
| AG-06 | High | Approved reference and downstream Shot dependency may become stale | Deterministic fingerprints/revalidation; no silent authority overwrite |
| AG-07 | High | Xorix document Asset IDs collide with the unrelated synthetic project | Project-scoped identity and import mapping |
| AG-08 | Medium | LocalPreviewImageProvider emits SVG mock cards | Visible simulated-output labeling; cannot satisfy genuine image QC |
| AG-09 | Medium | Prompt model field can differ from actual installed workflow | Capability registry and preflight provider/workflow/model manifest |
| AG-10 | Medium | Technical controls span multiple screens, incomplete progress reporting | Guided stepper, meaningful blockers/help, cancel/retry and review panels |
| AG-11 | Medium | Multi-view/variants may drift in character or architecture | Master-derived controlled variants; human visual consistency review |
| AG-12 | Medium | Metadata database vs image file storage and legacy manifests could diverge | Reuse active SQLite/repository API, content-addressed evidence checksums, path containment, backup/restoration tests |

## 6. Proposed no-duplication architecture
1. `AssetSpecificationDraftService`: read existing Asset and Story Intelligence, draft (do not approve) category schema fields, dependencies, creation prompt and variant allowances. No external execution.
2. `CategoryCAPValidationService`: enforce category invariants, required fields, dependency checks, prompt provenance and approved revisions. Adapt existing CAP models and repositories via backward-compatible migration only if audited and justified.
3. `CanonicalImagePreflightService`: validate XCIC config, exact ComfyUI API node types and checkpoint inventory, GPU memory estimate, target size, local output root and mock-vs-real mode. **No POST /prompt during preflight.**
4. Reuse `CanonicalAssetGeneratorService` + `XCICImageProvider`; explicit human approval per **image-generation** session, independent from H3 live-video hold. Prevent writing outside disposable project and ComfyUI-approved output roots.
5. `CanonicalCandidateReview`: show candidate gallery with versioned prompt, seed/model/workflow, source hash, image SHA256 and operator QC; approve Master with existing Reference Service and Asset/CAP lifecycle services; retain rejected/old versions.
6. `AssetReadinessOrchestrator`: compute missing gates for Asset, CAP, canonical primary reference and Shot binding; notify/invalidate dependent planning according to existing fingerprints; never silently promote Shot binding Ready.
7. UI composition: **Assets → Prepare Specification → Review → Generate Candidates → Visual QC → Approve Master/Asset/CAP → Resolve Shot**; advanced manual entry and external image import remain supported.

## 7. Read-only compatibility audit required before image test
Obtain from user machine via non-submitting diagnostic:
- XCIC root, resolved API workflow, loader node, mapping/profile existence.
- ComfyUI `/system_stats` and `/object_info`, selected image model/workflow nodes, dimensions and memory expectations on RTX 5060 Ti 16 GB.
- Whether current ComfyUI setup supports the configured `XCICQueueJobLoader` and correct checkpoint (existing Qwen XCIC integration may not align with model installed).
- Project-contained output and checksum/manifest persistence.
This audit has **not** checked the user's local filesystem or ComfyUI live. Therefore no claim of current image-generation readiness is made. First execution test must be explicitly authorized, disposable, and non-H3.

## 8. Incremental implementation gates after audit
- **20.19.3B**: map existing CAP tables/models + category schemas, source import strategy, tests for locked/variable attributes, legacy backward compatibility and duplicate ID rejection.
- **20.19.3C**: safe read-only ComfyUI/XCIC preflight and one user-authorized disposable image candidate; verify actual image, dimensions, model and manifests.
- **20.19.3D**: candidate gallery, human QC, approved Master/Reference provenance, retention/revision and refusal of unauthorized replacement.
- **20.19.3E**: derived views and asset dependency/fingerprint readiness propagation, no authority bypass.
- **20.19.3F**: full Golden Path test on four Draft synthetic assets; separate controlled hold of H3 video generation remains.
- **20.19.4**: menu rationalization, guided stepper, contextual Help and dropdown examples. Preserve all existing feature entry points during migration.

## 9. Acceptance and regression contract
For each implementation phase: GitHub-only development, commit SHA, PowerShell fast-forward pull commands, Ruff lint/format, mypy, focused tests, full pytest and `git diff --check`, clean `git status --short`; operator UI steps with expected states. Negative tests: duplicate asset IDs; missing CAP; missing workflow; model mismatch; API unreachable; untrusted/cross-project file paths; rejected candidate; unapproved Master; stale SHA; retry/idempotence; H3 hold unchanged; non-disposable production project rejected by disposable test harness.

**Exit condition for Phase 20.19.3A:** Architecture/service inventory and risks documented, no model loaded/no image generated/no database mutated. Live compatibility and exact schema-field mapping are **open follow-on validation**, not passed checks.
