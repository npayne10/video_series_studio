# Phase 20.18.2.3.7.1 — Existing Assembly, Timeline & Post-Production Capability Audit

**Status:** Completed bounded repository audit; operator acceptance pending  
**Branch:** `phase-20.18.2.3.6.3-local-r2v-provider-evaluation`  
**Parent specification:** `docs/PHASE_20_18_2_3_7_EPISODE_ASSEMBLY_TIMELINE_POSTPRODUCTION_ARCHITECTURE.md`

## 1. Audit scope and confidence

Inspected selected source and engineering baseline files on the named implementation branch. GitHub code-search results cover the default branch, so absence from search alone is **not proof of absence from the implementation branch**. This is a targeted capability/integration audit, **not** an exhaustive runtime/UI inventory. Claims below distinguish *confirmed code*, *contracts only*, and *not established by inspected evidence*.

Source evidence inspected:

- `src/vscs/application/production_pipeline/models.py` — `ProductionStage.EPISODE_ASSEMBLY`, `ProductionPipeline` and dependency `ProductionNode` models.
- `src/vscs/application/rendering/lip_sync.py` — `LipSyncMode`, `LipSyncTarget`, `LipSyncRequest` and input validation.
- `src/vscs/application/rendering/voice.py` — `VoiceProfile`, timed `DialogueCue`, `VoiceGenerationRequest`.
- `src/vscs/application/rendering/outputs.py` — `RenderOutputKind.LIP_SYNC_VIDEO`, `DIALOGUE_AUDIO`, `MUSIC`, `EFFECTS` and provenance contracts.
- `src/vscs/presentation/widgets/production_task_readiness_workspace.py` — persisted task readiness UI and explicit task-completion reconciliation.
- `src/vscs/infrastructure/production_execution/ltx25_keyframe_backend.py` — governed provider readiness, H3 output registration and historical recovery.
- `src/vscs/infrastructure/production_execution/provider_production_adoption_store.py` — provider readiness and acceptance evidence.
- `docs/engineering/VSCS_Video_Production_Workflow_V2.md` — active story-driven flow and earlier lip-sync-before-timeline sequence.
- `docs/engineering/Phase_17_6_1_4_Required_VSCS_Capability_Map.md` — target assembly, audio and mastering capabilities.
- `docs/engineering/Phase_17_6_2_Functional_Gap_Analysis.md` — older baseline gap assessment; not conclusive for today's branch.

## 2. Evidence-based capability matrix

| Capability | Verified state | Reuse decision | Gap / required proof |
|---|---|---|---|
| Story → episode → scene → shot hierarchy | Documented architectural model | Reuse stable IDs, continuity and planning | Audit precise current production-structure repository/UI in follow-on implementation |
| Shot provider execution and managed output | Existing backend and governed H3 output registration | Reuse immutable Generated Media + checksums | Map approved selection to assembly-ready index |
| Human QC / ProductionTask completion | Explicit task-readiness UI and reconciliation services exist | Reuse separate human QC/completion gates | Define independent Episode Shots Complete declaration |
| Provider execution evidence | Persisted readiness, adoption, provider fingerprint | Reuse, never reinterpret as assembly approval | Historical provenance warning must propagate to assembly |
| Production pipeline graph | `EPISODE_ASSEMBLY` enum and generic nodes exist | Reuse concept for dependency graph, extend via new contracts | An enum does not constitute assembly engine or timeline |
| Timed dialogue / voice identity | `DialogueCue`, `DialogueTiming`, `VoiceProfile` exist | Reuse canonical speaker/voice contracts | Explicit timeline-frame/sample alignment and picture-lock revisions |
| Lip-sync request validation | `LipSyncRequest` supports per-shot/clip targeting | Reuse for shot-local postproduction | No end-to-end rendering/approval/timeline replacement proven by inspected contracts |
| Output provenance | `RenderOutput` models video, dialogue, music, SFX, lip-sync | Reuse provenance conventions; adopt managed-media derivative registration | No final-master export manifest established by inspected file |
| Editable assembly timeline | **Not established in inspected implementation** | Design new revisioned timeline and source selection | Need ordering/trims/transitions/overlaps, timebase, persistence/UI |
| Shots Complete operator handoff | **Not established** | New declaration object; no mutation of tasks | Gate: approved coverage; controlled reopen/revision |
| Scene/episode concatenation and review | **Not established** | Separate provisional renderer from final master | Deterministic timeline renderer + continuity review |
| Post-production job DAG | Generic pipeline nodes and media contracts exist | Extend, do not collapse into provider execution jobs | Hash-based invalidation and retry, provider modes |
| Timeline-driven audio mix/captions/colour | Contracts / target docs only in inspected sources | Future staged adapters | Actual runtime/UI integration to establish |
| Final mastered deliverable | Target docs; no proof of working master pipeline from inspected artifacts | New governed master artifact | QC, codec, loudness, checksum, approval, delivery |

**Confidence:** Strong for named code-level contracts; moderate for integration opportunities; low for any claim of comprehensive missing capabilities. Verify current branch filesystem/tree before declaring modules absent.

## 3. Workflow v2 change-control delta

Active v2 steps 17–20: Dialogue/lip-sync → audio → QC → Timeline. Approved Phase 3.7 architecture: technical/visual Shot QC → Shot-set completion declaration → editable rough-cut timeline → picture/dialogue timing lock → shot-level lip-sync derivatives → audio/finishing → mastering.

Required **explicit workflow v2.1 amendment**:
- Move *final lip-sync* after rough-cut timing lock, but allow voice/performance planning in Shot Production.
- Preserve Shot QC gate before final-use timeline; provisional preview may show unapproved assets with strong warning.
- Distinguish internal-span assembly from Episode assembly.
- Keep production approval, media approval, picture lock, postproduction acceptance and master approval as distinct signed actions.

Do not edit active v2 document until review/approval of exact amendment; parent Phase 3.7 decision is approved, but the normative documentation update must be versioned.

## 4. Module ownership and integration proposal

- **Domain/Application:** `assembly` immutable ShotSelection, AssemblyScope, TimelineRevision, frame-rate arithmetic, state transitions; `post_production` ShotDerivativeTask, dependency graph and invalidation rules.
- **Infrastructure:** project-local versioned stores, verified media resolution, FFmpeg draft assembly adapter, provider-neutral lip-sync execution adapters, restart-safe export checkpoints.
- **Presentation:** Episode Shots Complete preflight/action workspace, Shot source bin, nonlinear timeline editor, provisional preview, postproduction queue, mastering/QC.
- **Reuse:** existing Generated Media selection and QC sources, ProductionTask reconciliation, voice/dialogue and lip-sync request contracts, ProductionPipeline graph, provider profile policies. Avoid direct coupling to `ltx25_keyframe_backend.py` for editing logic.

## 5. Initial implementation backlog

**P0 — .7.2** Immutable contracts, approval gate validation, media revision/checksum pinning, timeline frame math and audit-safe JSON serialization. No UI.
**P0 — .7.3** Shot coverage snapshot + explicit Episode/Video Shots Complete declaration, revert-by-new-revision. Tests for incomplete/unapproved/recovered historical media.
**P0 — .7.4** Ordered Shot selection and editable timeline + provisional preview UI, import from existing Generated Media. Test 3-Shot SHT-001/2/3 conceptual ordering without changing actual files.
**P1 — .7.5** Picture lock, dialogue alignment, dependency fingerprints and invalidation.
**P1 — .7.6** Lip-sync Shot derivatives, canonical voices, local-first provider adapter; independent QC.
**P1 — .7.7** Audio layers, grading, captions, deterministic master/preview export.
**P1 — .7.8** Acceptance: 30-minute episode, mixed scenes, cuts, transitions, changed shots, resume, original preservation, cost.

## 6. Explicit constraints and stopping points

- SHT-003 `GM-H3-006641D56A556A97DA398A3F`: historically recovered, `GENERATED`, pending human QC. Preserve the 240-frame media and original launch claim, and mark provenance limitation in any provisional selection.
- SHT-001/SHT-002 original media and SHT-002 governed boundary unchanged.
- Do not autoapprove, rerender, concatenate, publish or render a final master as part of this audit.
- The normal ProductionTask completion button does **not** constitute Episode Shots Complete.
- Development proceeds **directly in GitHub**, with PowerShell fetch/pull commands, Ruff check/format, mypy, focused and full pytest, UI tests and expected outcomes for each implementation stage.
- No runtime tests are claimed by this audit-only commit.

## 7. Phase 3.7.1 acceptance criteria

1. Audit matrix explicitly distinguishes existing capability vs contract vs unverified gap.
2. Existing workflow v2 sequencing conflict identified and governed amendment proposed.
3. Ownership, reuse map and ordered backlog agreed.
4. No runtime changes or alterations to protected production media/evidence.
5. Next implementation phase .7.2 starts only after operator acceptance of this audit.
