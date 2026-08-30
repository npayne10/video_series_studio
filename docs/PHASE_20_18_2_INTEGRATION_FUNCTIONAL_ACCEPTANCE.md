# Phase 20.18.2 — Integration & Functional Acceptance

## Status

**v7.2.1 Production Engine integration implemented; awaiting local static/automated validation, ComfyUI custom-node deployment validation, UI-functional validation, live-provider acceptance, full regression, and explicit owner acceptance.**

## 1. Purpose

Phase 20.18.2 closes the remaining integration gap between governed production authority and real provider execution. It proves that provider-ready reference governance introduced in Phase 20.18.1 can travel through the existing VSCS ProductionTask/queue/provider infrastructure into a live LTX 2.3 ComfyUI workflow, and that returned provider outputs become authoritative Generated Media.

The primary live acceptance workflow is:

**LTX-2.3 Video Studio Production**

Workflow ID:

`ltx23_production_v1`

## 2. Architectural Boundary

The VSCS core remains provider-neutral.

VSCS owns:

- ProductionTask and approved production authority;
- compiled production package;
- governed provider-ready ReferencePlan;
- reference-role resolution and safety rules;
- universal RenderRequest;
- queue/lease execution authority;
- durable provider execution provenance;
- output retrieval and Generated Media registration.

The provider/infrastructure edge owns:

- LTX 2.3 workflow-specific input decoding;
- ComfyUI workflow compilation;
- ComfyUI transport and live lifecycle;
- provider-specific node/input constraints.

This phase does not move LTX, ComfyUI, WANGP, Wan, or model-specific concepts into the VSCS core.

## 3. Implemented End-to-End Chain

```text
Approved Shot / ProductionTask
        ↓
Compiled Production Package
        ↓
Provider-Ready ReferencePlan
        ↓
v7.2.1 Provider Package Binding
        ↓
Universal RenderRequest
        ↓
QueueProviderExecutionService
        ↓
ProductionPackageComfyUIAdapter
        ↓
LTX-2.3 Video Studio v7.2.1 workflow
        ↓
VSCSProductionPackageLoaderV720
        ↓
VSCSReferenceResolverV720
        ↓
ComfyUI execution / monitoring / output retrieval
        ↓
Durable provider execution provenance
        ↓
GeneratedMediaIngestionService
        ↓
Authoritative Generated Media
```

The universal `RenderRequest` remains provider-neutral. The compiled Production Package path is attached only at the provider-execution boundary and injected into the unique governed v7.2.1 package-loader node immediately before ComfyUI submission.

## 4. Provider-Ready Reference Gate

The execution boundary refuses a reference plan when governed production authority cannot be represented safely.

For Phase 20.18.2 acceptance:

- the ReferencePlan target dimensions must match the compiled video dimensions;
- references sent to the provider must be approved as provider-ready;
- required canonical features must be visible;
- the full required asset must be visible when the shot may reveal it;
- duplicate reference IDs are rejected;
- a scene-composition/start reference is selected explicitly from governed roles;
- supporting identity/environment/prop/furniture references remain traceable by role.

The governed start-reference priority remains:

1. `start_frame_reference`
2. `scene_composition_anchor`
3. `continuity_anchor`
4. `primary_identity`

The v7.2.1 provider resolver treats an explicit `start_frame_reference` as the temporal start frame. Other governed roles remain visual-reference authority and are resolved according to the provider's single-image IC-LoRA constraint.

## 5. v7.2.1 Governed Reference Binding

The committed LTX 2.3 workflow is package-driven. Node `107` (`VSCSProductionPackageLoaderV720`) receives the compiled Production Package path, and Node `108` (`VSCSReferenceResolverV720`) resolves the provider reference and optional start frame.

The VSCS package compiler preserves the provider-neutral governed `references` array for provenance and additionally emits a v7.2.1 `bindings` array. Each binding carries:

- governed `reference_id`, `asset_id`, and role;
- an absolute provider-usable image path;
- explicit `required` authority derived from VSCS reference priority;
- provider-ready state;
- coarse governed coverage facts and required coverage;
- canonical-source and derivative provenance;
- reference fingerprint/checksum where available.

The v7.2.1 workflow has one provider IC-LoRA image input. It therefore follows the governed fallback sequence supported by the supplied resolver:

1. provider helper when explicitly supplied;
2. governed `scene_composition_anchor`;
3. one required visual reference directly;
4. one optional visual reference when no required visual exists;
5. block multiple required visual references when no governed helper/scene anchor exists.

Multiple required references are never silently discarded. The expected blocking code for an unresolved multi-reference provider constraint is `PROVIDER_MULTI_REFERENCE_HELPER_REQUIRED`.

An explicit `start_frame_reference` is bound separately from the provider visual image and drives temporal continuity without replacing identity/reference conditioning.

## 6. Live Workflow Deployment Requirement

The supplied **Video Production Engine v7.2.1** API workflow is committed at:

`resources/workflows/workflows/ltx23_production_v1_api.json`

The associated manifest is:

`resources/workflows/manifests/ltx23_production_v1.json`

The workflow intentionally keeps Node 107's `production_package` input blank in source control. `QueueProviderExecutionService` attaches the selected compiled Production Package path to the universal request at submission, and `ProductionPackageComfyUIAdapter` injects it into Node 107 at the provider edge. Machine-specific package paths are therefore never committed to the workflow.

The deployment assurance blocks package compilation when the committed workflow is missing, invalid, has a hard-coded package path, or no longer contains exactly one semantic v7.2.1 package loader and governed reference resolver.

The local ComfyUI installation must also contain the supplied `ComfyUI-VSCS-Production-v720` custom-node package and expose:

- `VSCSProductionPackageLoaderV720`;
- `VSCSReferenceResolverV720`.

This ComfyUI deployment remains a local provider prerequisite and must be validated before live acceptance.

## 7. v7.2.1 Production Package Contract

New Phase 20.18.2 compiled packages use schema marker `7.2.1-vscs-1` while retaining the existing VSCS compilation manifest and deterministic package fingerprint.

For the v7.2.1 loader, the package also contains an `acpp` section carrying the governed execution values consumed by the supplied workflow, including:

- positive and negative prompts;
- production profile;
- width and height;
- frame count and FPS;
- CFG;
- IC-LoRA model/reference strength;
- seed;
- output filename prefix;
- governed ReferencePlan.

The existing top-level VSCS fields remain present for compatibility and provenance. The package fingerprint is recomputed after the v7.2.1 provider contract is assembled.

## 8. Generated Media Authority

Provider completion is not the end of the acceptance chain.

A completed provider execution must expose durable execution provenance and retrieved outputs. `LiveShotFunctionalAcceptanceService` then delegates those outputs to the existing `GeneratedMediaIngestionService`, preserving:

- provider identity;
- provider job/execution identity;
- ProductionTask authority;
- production/episode/scene/shot scope;
- workflow/render provenance;
- VSCS-owned media location and GeneratedMedia identity.

This preserves the project principle:

> **PROVIDERS PRODUCE OUTPUTS. VSCS OWNS GENERATED MEDIA.**

## 9. Existing UI Used for Functional Acceptance

The existing **Production Execution** workspace remains the operator-facing execution surface. It already provides:

- Profile selection;
- `Compile Production Package`;
- scheduled-work table;
- `Refresh Scheduled Work`;
- `Start Production`;
- `Refresh Execution Status`;
- governed retry control;
- Live Production Monitor with provider, ComfyUI prompt, ComfyUI health, device/VRAM, progress and status.

Generated results are reviewed through the existing **Generated Media** workspace.

Phase 20.18.2 deliberately integrates into these established surfaces rather than creating a temporary acceptance-only UI.

## 10. Automated Acceptance Coverage

Focused tests cover:

- the committed v7.2.1 workflow and manifest contract;
- the package loader path remaining blank in source control;
- presence of the governed reference resolver;
- v7.2.1 provider package generation;
- governed `source_path` → absolute provider `path` translation;
- required-priority → `required=true` translation;
- provider-ready and coverage authority preservation;
- explicit `start_frame_reference` preservation;
- package fingerprint refresh after v7.2.1 binding;
- complex multi-reference governance and fallback/blocking regression coverage;
- 1280 × 720 target preservation;
- mismatched plan/video dimensions blocked;
- incomplete/full-asset extrapolation risk blocked;
- governed request reaches provider-execution boundary;
- completed provider output is passed to Generated Media ingestion.

Phase 20.18.1 reference-role tests remain regression requirements.

## 11. Acceptance Classes

### Static Acceptance

- Ruff check passes.
- Ruff format check passes.
- Existing project static checks remain clean.

### Automated Acceptance

- Phase 20.18.2 focused unit/integration tests pass.
- Phase 20.18.1 reference-governance regression tests pass.
- relevant provider/rendering/Generated Media tests pass.

### UI-Functional Acceptance

Using a representative approved scheduled video task:

1. install/verify the v7.2.0 VSCS custom nodes in the active ComfyUI instance;
2. open **Production Execution**;
3. click **Refresh Scheduled Work**;
4. select the production video task;
5. select the **production** profile;
6. click **Compile Production Package**;
7. verify the package is executable and the correct Shot/Task/Resource are shown;
8. inspect the compiled package and confirm schema `7.2.1-vscs-1`, `acpp`, governed `reference_plan.references`, and provider `reference_plan.bindings` are present;
9. click **Start Production** only after the workflow/custom-node checks above pass;
10. verify **Live Production Monitor** shows the selected provider and a real ComfyUI prompt/job;
11. use **Refresh Execution Status** or allow automatic polling until terminal state;
12. verify successful outputs appear in **Generated Media** with provider/task provenance.

### Live Provider Acceptance

The live test must use the real LTX 2.3 provider and the deployed **LTX-2.3 Video Studio Production v7.2.1** API workflow. Mocks/dry-run execution cannot satisfy this acceptance class.

At minimum, one valid 1280 × 720 provider-ready single-character Commander James Spence I2V shot must complete successfully and register Generated Media.

A previous-final-frame continuity case and a multi-character scene-composition-anchor/helper case must then be exercised as required by the v7.2.1 acceptance suite.

### Negative Functional Acceptance

Before provider submission, demonstrate that:

- a portrait/mismatched reference plan cannot be submitted for the governed 1280 × 720 target;
- an incomplete reference that requires extrapolation of required asset content is blocked;
- multiple required visual references without a governed scene anchor/helper are blocked instead of silently reduced.

### Full Regression

The full pytest suite must pass with zero introduced regression.

## 12. No New ADR Required

No new architectural decision is introduced by this phase. The implementation realizes the already accepted governed reference-role decision and composes the existing provider-execution and Generated Media authority boundaries.

## 13. Closure Criteria

Phase 20.18.2 may close only when all of the following are true:

- Static acceptance passes locally.
- Focused automated acceptance passes locally.
- Relevant regression tests pass locally.
- The real LTX-2.3 Video Studio Production v7.2.1 API workflow is deployed.
- The supplied v7.2.0 VSCS custom nodes are installed and load cleanly in ComfyUI.
- UI-functional acceptance passes.
- At least one live LTX 2.3 Shot completes through VSCS.
- Retrieved output is registered as Generated Media.
- Negative reference-governance cases are confirmed blocked before provider execution.
- Full regression passes.
- The project owner explicitly accepts the phase.

Until then, the phase status remains **IMPLEMENTED — NOT YET ACCEPTED**.
