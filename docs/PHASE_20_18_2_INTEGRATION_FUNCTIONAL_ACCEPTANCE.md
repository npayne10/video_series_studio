# Phase 20.18.2 — Integration & Functional Acceptance

## Status

**Implementation complete; awaiting local static/automated validation, UI-functional validation, live-provider acceptance, full regression, and explicit owner acceptance.**

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
ReferencePlanRenderRequestBinder
        ↓
Universal RenderRequest
        ↓
LTX-2.3 Video Studio provider-edge input resolution
        ↓
QueueProviderExecutionService
        ↓
Live ComfyUI provider adapter
        ↓
ComfyUI execution / monitoring / output retrieval
        ↓
Durable provider execution provenance
        ↓
GeneratedMediaIngestionService
        ↓
Authoritative Generated Media
```

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

The start-reference priority is:

1. `start_frame_reference`
2. `scene_composition_anchor`
3. `continuity_anchor`
4. `primary_identity`

This supports both a simple one-character I2V shot and a complex multi-character scene where a frame-zero scene composition is the primary conditioning image and character/environment references provide supporting authority.

## 5. Multi-Reference LTX 2.3 Binding

The LTX 2.3 manifest already declares `reference_images` and `multiple_reference_images` capability. Phase 20.18.2 adds provider-edge decoding of the governed reference list so the manifest compiler receives a typed list of image paths rather than an opaque metadata string.

For a representative James/Cheryl/Ros scene, the expected conceptual mapping is:

```text
scene_composition_anchor → start_frame
James primary_identity   → reference_images[]
Cheryl secondary_identity → reference_images[]
Ros secondary_identity   → reference_images[]
room environment_reference → reference_images[] when supported/required
```

The complete role manifest remains attached to the universal request metadata for traceability.

## 6. Live Workflow Deployment Requirement

The repository intentionally does **not** fabricate or substitute a placeholder ComfyUI graph for the production workflow.

Before live acceptance, the exact production workflow that has been proven interactively in ComfyUI must be exported in **ComfyUI API workflow format** and installed at:

`resources/workflows/workflows/ltx23_production_v1_api.json`

The deployment validator blocks/reports live readiness when this file is missing, invalid JSON, empty, or outside the governed workflow root.

This ensures the live acceptance test evaluates the real **LTX-2.3 Video Studio Production** workflow rather than a synthetic test graph.

## 7. Generated Media Authority

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

## 8. Existing UI Used for Functional Acceptance

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

## 9. Automated Acceptance Coverage

Focused tests cover:

- complex multi-reference plan → LTX RenderRequest binding;
- 1280 × 720 target preservation;
- composition-anchor selection as start frame;
- supporting James/Cheryl/Ros identity-reference preservation;
- mismatched plan/video dimensions blocked;
- incomplete/full-asset extrapolation risk blocked;
- LTX multi-reference metadata decoded into typed workflow inputs;
- missing real Video Studio API workflow detected;
- governed request reaches provider-execution boundary;
- completed provider output is passed to Generated Media ingestion.

Phase 20.18.1 reference-role tests remain regression requirements.

## 10. Acceptance Classes

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

1. open **Production Execution**;
2. click **Refresh Scheduled Work**;
3. select the production video task;
4. select the **production** profile;
5. click **Compile Production Package**;
6. verify the package is executable and the correct Shot/Task/Resource are shown;
7. click **Start Production**;
8. verify **Live Production Monitor** shows the selected provider and a real ComfyUI prompt/job;
9. use **Refresh Execution Status** or allow automatic polling until terminal state;
10. verify successful outputs appear in **Generated Media** with provider/task provenance.

### Live Provider Acceptance

The live test must use the real LTX 2.3 provider and the deployed **LTX-2.3 Video Studio Production** API workflow. Mocks/dry-run execution cannot satisfy this acceptance class.

At minimum, one valid 1280 × 720 provider-ready single-character I2V shot must complete successfully and register Generated Media.

A multi-reference shot should then be exercised where the deployed workflow supports the declared multiple-reference input.

### Negative Functional Acceptance

Before provider submission, demonstrate that:

- a portrait/mismatched reference plan cannot be submitted for the governed 1280 × 720 target;
- an incomplete reference that requires extrapolation of required asset content is blocked.

### Full Regression

The full pytest suite must pass with zero introduced regression.

## 11. No New ADR Required

No new architectural decision is introduced by this phase. The implementation realizes the already accepted governed reference-role decision and composes the existing provider-execution and Generated Media authority boundaries.

## 12. Closure Criteria

Phase 20.18.2 may close only when all of the following are true:

- Static acceptance passes locally.
- Focused automated acceptance passes locally.
- Relevant regression tests pass locally.
- The real LTX-2.3 Video Studio Production API workflow is deployed.
- UI-functional acceptance passes.
- At least one live LTX 2.3 Shot completes through VSCS.
- Retrieved output is registered as Generated Media.
- Negative reference-governance cases are confirmed blocked before provider execution.
- Full regression passes.
- The project owner explicitly accepts the phase.

Until then, the phase status remains **IMPLEMENTED — NOT YET ACCEPTED**.
