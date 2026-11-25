# VSCS W0 — Integrated Delivery Starting Baseline v1.0

**Recorded:** 2026-11-25 (Africa/Johannesburg)  
**Status:** W0 repository/source reconciliation complete; Windows installation, local runtime and 18-second acceptance contract pending operator confirmation.  
**Governance:** Approved accelerated capability delivery; no new GPU/paid API/production mutation or merge authority.

## Decision: starting point

- **Repository:** [npayne10/video_series_studio](https://github.com/npayne10/video_series_studio).
- **Active development branch:** `issue-61-governed-master-workflow`, [Draft PR #66](https://github.com/npayne10/video_series_studio/pull/66). At the inspection, HEAD `bd3366f3c7ebf36eb5a7792c39f43e1065619c52` (Accelerated Completion Assessment v1.0). Do not treat `main` as feature-equivalent.
- **Release branch:** `main` HEAD observed via comparison `95c01c42ac2352526982d0bbae5b84aaacd4f9a5`. Comparison `main...issue-61-governed-master-workflow`: **ahead 4,398 commits, behind zero**. The PR UI may show a different historical base SHA; the branch comparison is the release-content check. This scale makes a direct feature-by-feature release merge unqualified.
- **CI:** [GitHub Actions run #1578](https://github.com/npayne10/video_series_studio/actions/runs/45662582025) completed **Fast Ruff lint and format: success; quality: success** for the assessment HEAD. CI does not constitute Windows/GPU acceptance.
- **Backlog:** 9 open issues (#52, #53, #54, #55, #58, #59, #60, #61, #67), 48 open Draft PRs. Historical PR ancestry inspection: 46 of 47 older PR heads already ancestors of #66; none is automatically closed/merged on that basis.

## PR #14 exception — resolved for W0

[PR #14](https://github.com/npayne10/video_series_studio/pull/14) has a divergent head with two commits not in #66's ancestry. Reviewed its four-file patch: CAP architecture assessment document, module `architecture_assessment.py`, CAP package exports, and its unit test. **The corresponding assessment module and exports are already present** in #66. Their newer `MASTER_REFERENCE_AUTHORING_POLICY` explicitly permits governed derived production references while reserving MASTER authoring for externally approved ChatGPT sources. This is a deliberate later refinement, not evidence that the two historical commits must be cherry-picked.

**Disposition:** no feature-port action for W0, no merge/close action. Administrative closure of old Draft PRs remains a separate owner-authorized cleanup and must not silently change `main`.

## Source-level production capability map (verified existence, not live success)

| Boundary | Existing source | What W0 can establish | Next required evidence |
|---|---|---|---|
| Operator launch | `src/vscs/main.py`, `src/vscs/bootstrap.py` | PySide6 application entry point and bootstrap | Actual Windows command/startup, project reopen |
| CAP MASTER/view governance | `application/caps/reference_library.py`, `multiple_angle_execution_guard.py`, `multiple_angle_runtime_readiness.py` | Governed authority, offline staging/preflight contracts | Live viewpoint-qualified execution, visual identity QC, independent approval |
| Production task/render | `application/production_execution/`, `infrastructure/production/task_execution.py`, `infrastructure/rendering/comfyui_production.py` | ProductionTask wrapper and ComfyUI production-package adapter exist | One live shot to durable reconciled output |
| Provider transport | `application/provider_execution/rendering_bridge.py`, `execution_service.py` | RenderAdapter-to-provider bridge and durable execution-job contracts | Controlled runtime provider submission, monitoring, recovery |
| Generated media | `application/generated_media/ingestion.py`, `completion_reconciliation.py`, `review.py` | Ingestion, completion reconciliation and review services | Verified generated clip registered, accepted and reopened |
| Episode assembly | `application/assembly_contracts.py`, `episode_assembly_preview.py`, `episode_assembly_playback.py` | Timeline/selection contracts, read-only verified preview and frame-to-source playback | Final timeline render and playable export (not proved by preview) |
| Audio | `application/episode_assembly_audio_readiness.py`, `rendering/lip_sync.py`, `rendering/voice.py` | Technical audio inventory and voice/lip-sync contracts | Audio generation/inclusion/mix and verified exported result |

**Critical gaps to investigate within W1/W3/W5, not another lengthy preflight programme:**
1. Runtime CameraAngle and multiple-angles LoRA compatibility with the actual 16 GB GPU, including deterministic view/identity QC.
2. Complete production task → provider → output ingestion/technical QC → governed acceptance link.
3. Actual episode timeline **file export**, audio integration and playback. The inspected assembly files provide verified preview, not export evidence. Do not equate data contracts or UI previews with an exported video.

## Frozen protection boundary for first integrated acceptance

**Existing disposable test project:** `D:\VSCS\C4B2B_DISPOSABLE_GPU_01`, asset `CAP-PRP-002` (diagnostic console). Preserve and recheck these **previously operator-confirmed** SHA-256 values before any separately approved mutation:

| Protected file | SHA-256 |
|---|---|
| `references\CAP-PRP-002_CHATGPT_MASTER_v1_20261123.png` | `C9741D39D1713E7EDDB600A15DD8D8D1B7A5C353225445CE2E4444589B9A3A38` |
| `Canonical Assets\CAP-PRP-002\Images\Derived\front.png` | `038A00EB3C502F8C352A2C9B6504D1A7F7A1AE91F0A3E8E76B44BC5D1198D915` |
| `Canonical Assets\CAP-PRP-002\Images\Derived\front_2.png` | `6D5F7250E1E3657617A59ABA192C248A2E296FC133E3A3C482316C68E40F676E` |

These are **historical operator evidence**, not hashes freshly read from the Windows filesystem in W0. Do not touch the historical candidates or approved MASTER. Last Windows evidence: 31 targeted tests, full 3033 pass/2 skipped, no `multiple_angle_*` queue files. Do not misreport old results as new.

## Proposed 18-second proof contract (needs operator sign-off before execution)

- Working target: Blue Signal / disposable isolated **18-second** scenario; episode `AUT-EPISODE-90DBBF727CE5` (`EP-001`), shot `AUT-SHOT-D7FC62B73D16` (`EP-001-SC-001-SHT-001`), console asset `CAP-PRP-002` / `AUT-ASSET-D697AA1F4A7F`, **subject to current persisted-record lookup**. These IDs came from previous operator-approved proposal evidence; do not assume local project equality or Ready status.
- Shot intent: unoccupied engineering inspection bay, advancing view of diagnostic console, quiet/practical staging, ending on a single tone. Resolve exact required visible CAPs from the current approved Story and Shot, not assumptions.
- Success: from governed approved Story/Shot and valid required CAP references, produce **real playable video**, register Generated Media, perform independent QC and provenance checks, assemble with required audio, export a final local playable proof, reopen it and verify protected hashes unchanged.
- Not success: offline-only preflight, passing unit tests, unreviewed generated candidate, unverified preview, or fake/synthetic provider output.
- Consent: distinct explicit operator approval before **any** live GPU generation, paid API use, protected project mutation, PR merge, or release. Staging only in unique governed names; failure must be reversible and audit-recorded.

## W0 disposition and next executable capability

**Repository reconciliation: COMPLETE** (branch, CI, backlog, PR #14, source integration map, protected scope).  
**Local-runtime validation: PENDING WINDOWS** (no live access to `D:\VSCS` in this GitHub-only assessment).  
**First-proof shot contract: PROPOSED, not authoritative** until persisted IDs and shot/CAP requirements are confirmed.

**Proceed into W1 integrated delivery:** complete #61 approved MASTER → governed multi-angle provider execution → source-fresh unique staging → output reconciliation → candidate QC/approval → persistence in one coherent capability, using GitHub CI continuously and one Windows acceptance. In parallel, trace W3's production-task-to-Generated-Media link and W5's real export path early so first video is not delayed by further planning stages.

No code/runtime change, file deletion, PR merge or protected project write is authorized or performed by this W0 document.
