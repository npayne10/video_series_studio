# W2.1 — Video Generation Capability Reconciliation

**Date:** 2026-11-26 (Africa/Johannesburg)  
**Status:** Source-level reconciliation complete; Windows runtime and first video **not yet qualified**  
**Authority:** VSCS Master Delivery Backlog, W2.1; Draft PR #66

## Decision for the first proof

Use the existing **MiniMax H3 Ref2VA governed single-span route** as the *first W2.2 qualification candidate*, targeting **15 seconds** at the configured shot frame rate. This meets the lower bound of the 15–20-second proof target and minimizes stitching, temporal-boundary synthesis and new integration work. The operator must first confirm the persisted Shot/ProductionTask, source authority, approved Introduction Keyframe, provider workflow/models, package and readiness on Windows. This is a **selection for readiness validation**, not a claim that its model, VRAM performance, output quality or 15-second runtime has been demonstrated.

If that route is blocked or fails the first authorized trial, examine the **existing LTX-2.5 governed multi-span orchestration** for an approximately 18-second assembled shot. Do not automatically switch or generate extra candidates; document the blocker and obtain a new trial decision. Keep LTX-2.3 as an implemented legacy/backend comparison, not the selected first-shot route. Defer the separate MiniMax H3 **multi-frame timed-guide** workflow until actual video evidence shows a useful continuity benefit.

## Existing routes, as implemented

| Route | Code evidence | Real limitation / governance | W2 disposition |
|---|---|---|---|
| **MiniMax H3 Ref2VA single span** | `provider_policy_profiles.py`, `minimax_h3_span_adapter.py`, `minimax_h3_automated_execution.py`, `ltx25_keyframe_backend.py` | Direct job ceiling **15 s**; H3 `17k+5` frame planning; approved span-local Introduction Keyframe required; project-local reviewed API workflow, configured ComfyUI input/output and models must preflight. Durable execution claim blocks blind retry. Monolithic output is copied/registered to GeneratedMedia in **GENERATED**, requires review. | **Primary first trial candidate**, contingent on Windows readiness; one operator-authorized job only. |
| **LTX-2.5 Candidate C** | `provider_policy_profiles.py`, `ltx25_keyframe_backend.py`, `automated_span_orchestration.py` | Implemented governed keyframe-conditioned span provider with stitched assembly and timed-span acceptance. The 16 GB conservative hardware envelope is **7 s** per LTX shot, marked revalidation-required; a 16 s revalidation target is **not certified**. Multi-span boundaries and acceptance increase first-run complexity. Provider adoption/assembled output tracking exists; verify the final MP4 is also visible in normal GeneratedMedia review before considering the path complete. | **Fallback** for an assembled ~18 s proof, after focused readiness/registration check. |
| **LTX-2.3** | `ltx23_v721_backend.py`, `workflows/ltx23_production_v1_api.json` | Implemented ComfyUI backend, but source presence alone does not establish current model inventory, full approved-shot conditioning or viable 15–20 s production on this GPU. | Do not add a parallel qualification cycle now. |
| **MiniMax H3 multi-frame timed guides** | `PHASE_20_H3_MF_MULTIFRAME_REFERENCE_WORKFLOW_ASSESSMENT.md` | Investigated editor/canvas workflow is **not** a reviewed, bound, executable API integration; multiple image inputs do not prove multiple *timed* frame guides. Do not confuse with existing H3 Ref2VA isolated-span execution. | **Conditional W2.3**, not a W2.2 prerequisite. |

**Time semantics:** A 15 s requested shot is not proof that every renderer emits exactly 360 frames at 24 fps; each provider's native frame congruence, padding and governed output normalization must be compiled and independently checked. Never infer duration from UI text or an unvalidated workflow.

## W2.2 controlled first-shot contract

1. **Confirm live production truth** on the Windows installation, without modifying protected references: current Project, Episode, Shot, ProductionTask, Ready state and selected production profile. W0 suggested `CAP-PRP-002`, `AUT-SHOT-D7FC62B73D16`, `AUT-EPISODE-90DBBF727CE5`, and an engineering inspection-bay camera advance; these identifiers and state are **provisional until checked**.
2. **Bind only governed sources**: approved, hash-current MASTER and approved Front for `CAP-PRP-002`; use unapproved Rear/Left/Right only if the shot-specific policy permits *candidate experimentation*, never as approved production references. Confirm shot-scoped CAP requirements and approved Introduction Keyframe. Do not assert unseen Rear geometry from synthesized images.
3. **Select `minimax-h3-ref2va-v1`**, compile the current Production Package and run *Validate Provider Readiness* in Production Execution Workspace. Check reviewed project-local H3 API graph, installed node/model names, ComfyUI input/output directories, available disk and RTX 5060 Ti 16 GB capacity, provider frame count, any past adoption/launch claim, reference slots and provenance. Treat an unready status as a stop.
4. **Separate consent gate:** once the preflight returns ready, present exact job scope, provider, expected duration, resource/cost exposure and one-use approval request to Neill **before any GPU submission**. W2.1 conveys no GPU/paid-API authorization and no authority to alter protected project assets.
5. **After one authorized job:** verify actual playable MP4, precise ffprobe frame/fps/duration, camera and asset continuity, keyframe/source provenance, persistent launch/job records and recoverability. Confirm it appears in governed **GeneratedMedia** as an unapproved generated artifact. Perform technical validation, then independent human visual review; approval cannot be inferred from successful rendering.
6. **Exit criterion:** accepted 15-second (or documented provider-limited) proof clip with traceable GeneratedMedia and QC, or a precise blocker report leading to the LTX-2.5 fallback decision. Do not silently expand to multiple candidate batches, GPU tuning or the multi-frame experimental workflow.

## Source-level gaps and checkpoints

- **Windows state not observed:** no current persisted Ready task, H3 model/graph selection, ComfyUI runtime, free VRAM, or benchmark was available to this repository-only review. Run the existing in-app preflight first; record exact blocker strings rather than starting a new generic investigation.
- **Actual 15 s H3 performance unverified:** source enforces at-most-15s direct spans and deterministic native frame shape, not a measured VRAM/time guarantee. If 15 s is blocked on 16 GB, obtain a scoped choice between shorter governed proof, H3 spans or LTX-2.5 assembly.
- **GeneratedMedia route distinction:** H3 monolithic execution explicitly calls `_register_h3_monolithic_generated_media`, which ingests into managed files and registers `GeneratedMedia` with `GENERATED` state; completed provider adoption is separately recorded. LTX-2.5 multi-span orchestration records assembled output/provider adoption, but normal GeneratedMedia availability remains an **operator acceptance checkpoint**. Do not claim that status equals approval.
- **Shot conditioning:** confirm actual shot scope, keyframe requirement and compliant reference selection before planning a camera-moving diagnostic-console clip. The previous strict side-view imperfections are a known, *provisionally tolerated video experiment* limitation, not canonical geometry approval.
- **No live side effects in W2.1:** no model downloads, ComfyUI queue writes, GPU inference, protected image changes, launch claims, GeneratedMedia registration, acceptance or release.

## Evidence paths

- `src/vscs/infrastructure/production_execution/hardware_shot_capability.py`
- `src/vscs/infrastructure/production_execution/provider_policy_profiles.py`
- `src/vscs/infrastructure/production_execution/minimax_h3_span_adapter.py`
- `src/vscs/infrastructure/production_execution/minimax_h3_comfyui_provider.py`
- `src/vscs/infrastructure/production_execution/minimax_h3_automated_execution.py`
- `src/vscs/infrastructure/production_execution/minimax_h3_span_orchestration.py`
- `src/vscs/infrastructure/production_execution/ltx25_keyframe_backend.py`
- `src/vscs/infrastructure/production_execution/automated_span_orchestration.py`
- `src/vscs/application/generated_media/{ingestion,technical_validation,review}.py`
- `docs/engineering/VSCS_W0_Integrated_Delivery_Starting_Baseline_v1.md`
- `docs/PHASE_20_H3_MF_MULTIFRAME_REFERENCE_WORKFLOW_ASSESSMENT.md`

**Next:** W2.2 focused Windows H3 readiness and *separately authorized* first 15-second video. Record the observed readiness, GPU result and QC back into the MASTER backlog; then proceed to shot assembly as soon as a usable clip exists.
