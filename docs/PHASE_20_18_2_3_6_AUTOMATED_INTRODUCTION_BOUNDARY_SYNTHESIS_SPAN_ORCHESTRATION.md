# Phase 20.18.2.3.6 — Automated Introduction Boundary Synthesis & Span Orchestration

## Purpose

Phase 20.18.2.3.5 proved exact in-Shot asset introduction boundaries, but still required the operator to prepare the exact preceding boundary frame and the target Introduction Keyframe. That does not scale to episode production.

Phase 20.18.2.3.6 converts the same governed authority into an automated, exception-based production path. The operator owns Shot intent and production authority; VSCS performs routine boundary extraction, target-frame synthesis, provider span execution, validation and assembly. Human intervention remains a fail-closed fallback.

## Architectural rule

Timed Asset Presence remains explicit production authority. VSCS does not infer entrances, exits, reveals or appearances from prose.

Normal flow:

    Timed Asset Presence
      -> Governed Internal Render Spans
      -> Timed Canonical Reference Activation
      -> Introduction Keyframe Requirements
      -> execute SPAN-N
      -> extract exact normalized final boundary frame
      -> synthesize target Introduction Keyframe from governed references
      -> automated semantic/continuity validation
      -> register automated-validated Governed Introduction Keyframe
      -> execute next span
      -> verify and assemble normalized spans
      -> automated rendered-boundary validation
      -> Timed Span Acceptance = ACCEPTED

If synthesis, reference resolution or automated validation cannot pass, VSCS stops and returns the exact Introduction Keyframe requirement to the existing manual Phase 3.5 controls.

## Provider-neutral capability ladder

1. provider_native_timed_reference
2. synthesized_introduction_keyframe
3. manual_fallback

A future provider that can inject an approved canonical asset at an exact temporal boundary may use provider-native introduction directly. LTX-2.5 Candidate C currently uses synthesized target-frame conditioning plus first-frame I2V.

## Governance

GovernedIntroductionKeyframe remains the downstream authority. Phase 3.6 adds approval_mode = human | automated_validated and automation_record_path.

Existing human approvals remain backward compatible. An automated_validated keyframe is accepted only when its source boundary was extracted from the actual normalized preceding span, the synthesis request names current governed introduced assets/references, the output is checksum-pinned, automated semantic/continuity validation passes, and automation provenance is persisted. The actor is explicitly recorded as VSCS Automated Boundary Synthesis; this is not represented as a human approval.

## Boundary synthesis adapter

VSCS does not hard-code an unvalidated ComfyUI image-edit graph. The infrastructure adapter consumes an API-format ComfyUI image-edit workflow and semantic mapping supplied through environment variables:

    VSCS_INTRO_BOUNDARY_WORKFLOW
    VSCS_INTRO_BOUNDARY_MAPPING

The mapping must bind source_image, introduced_reference_images, positive_prompt and output_filename. It may also bind negative_prompt, width, height, seed and output_directory.

If workflow/mapping is absent, invalid, or references unavailable node types, automation fails closed to manual boundary review.

## Automated validation

The current semantic boundary validator uses the configured vision-capable OpenAI model. It receives the exact preceding normalized source frame, synthesized target frame, and each governed canonical reference for newly introduced assets.

It must positively establish: existing composition preserved; introduced governed assets present; introduced identity matches reference imagery; no unapproved assets/people introduced; camera/environment preserved. Default confidence threshold is 85. Any unsupported or failed criterion requires manual review.

## Sequential span orchestration

LTX25TimedSpanAcceptancePackageBuilder can now materialize one governed span at a time. This permits SPAN-001 to execute before the later Introduction Keyframe exists. After the exact normalized end frame is extracted and the new boundary is synthesized/validated, the next span package is materialized and executed.

Internal span submissions do not create additional ProductionTasks and do not consume or reset ProductionTask retry authority.

## Assembly and final validation

The existing Phase 3.5 GovernedSpanAssemblyRuntime remains authoritative. It verifies exact governed frame counts, identical dimensions/rate, source-boundary pixels against the actual preceding-span final frame, exact final Shot frame count, and video-only governed assembly.

After assembly, Phase 3.6 extracts the actual rendered frame immediately before and at each introduction boundary and validates the rendered transition again. Only then is the existing timed-span QC record persisted by the automation actor.

## Production Execution UI

The group is now Timed Asset / Span Production Orchestration. The primary action is Run Automated Timed Span Orchestration. It runs on a worker thread so the desktop UI remains responsive.

The existing Build Span Packages, Approve Introduction Keyframe, Verify & Assemble Span Outputs, and Record Visual QC controls remain as explicit manual recovery tools.

## Provenance

Automation artifacts are stored under:

    .vscs/automated_introduction_boundaries/<shot>/<requirement>/

including source-frame images, reference_paths.json, automation.json, and the generated target Introduction Keyframe. automation.json records source checksum, introduced assets/references, synthesis provider/job, output checksum, validator checks/findings and final automation state.

Span packages remain under .vscs/timed_span_acceptance/packages/<task>/<profile>/ and final assembly defaults to .vscs/timed_span_acceptance/assembled/<shot>.mp4.

## SHT-002 live acceptance target

SPAN-001: global 0-95, 96 governed frames, 97 provider frames normalized to 96, Ros absent.
Boundary: global 95 -> 96.
Automatic action: extract actual SPAN-001 frame 95, synthesize frame 96 with CAP-CHR-005 Major Ros Rohsgard, validate against LIVE-SECONDARY_IDENTITY-CAP-CHR-005.
SPAN-002: global 96-143, 48 governed frames, 49 provider frames normalized to 48, Ros present.
Final assembled Shot: exactly 144 frames at 24 fps.

## Failure policy

Automation fails closed for stale/missing authority, unresolved canonical references, missing synthesis workflow, provider execution failure, boundary extraction failure, validation failure, incorrect normalized frame counts, boundary-pixel mismatch, or failed final rendered-boundary validation. It never creates hidden authority.

## Deliberate exclusions

Phase 3.6 does not infer timed presence from prose, reset retries, create one ProductionTask per span, silently retry failed provider work, auto-approve failed validation, automatically promote the assembled functional-acceptance video to authoritative Generated Media, or claim provider-native timed-reference support for LTX-2.5.

## Acceptance criteria

1. Static checks and focused tests pass.
2. Existing Phase 3.1-3.5 regression tests pass.
3. A validated ComfyUI introduction-boundary image-edit workflow/mapping is configured.
4. SHT-002 runs SPAN-001 without manual boundary-image creation.
5. VSCS extracts exact global frame 95 automatically.
6. VSCS synthesizes and validates frame 96 with Ros automatically.
7. SPAN-002 executes from the resulting governed frame 96.
8. Final assembly is exactly 144 frames at 24 fps.
9. Rendered boundary validation passes or fails closed to manual review.
10. The user explicitly accepts the live functional result.
