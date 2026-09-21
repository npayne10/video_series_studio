# Phase 20.18.2.2f — Provider Prompt & Video Workflow Rebaseline

## Status

Implementation Stage 1 committed for automated validation and Candidate A live acceptance.
The phase remains open until the owner completes the VSCS Standard Development Prompt
validation, the A/B/C provider evaluation is completed, and the owner explicitly accepts
the resulting production baseline.

## Trigger

The corrected SHT-001 LTX-2.3 run transported the intended James + Sandra identity reference,
Xorix reference and CAP-LOC-021 Iron Horizon bridge reference, but visual acceptance still
failed:

- additional ungoverned people remained visible;
- the staged action did not reliably follow Sandra at her control station noticing the reading
  and looking toward James while James remained focused forward;
- the generation drifted toward reference-image composition near the end of the Shot.

This established that reference transport alone is not sufficient. Creative prompt language
and provider workflow composition authority must be rebaselined.

## External provider findings

The official LTX project currently recommends LTX-2.5. Official ComfyUI/LTX examples expose
LTX-2.5 Image-to-Video and Ingredients workflows, with the image-to-video path explicitly
using a first frame as composition authority while the prompt describes motion.

Authoritative research sources:

- https://github.com/Lightricks/LTX-2
- https://github.com/Lightricks/ComfyUI-LTXVideo/tree/master/example_workflows/2.5
- https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_ltx2_5_i2v.json

No LTX-2.5 provider path is marked executable merely because an upstream example exists.
VSCS remains fail-closed until the local model files, ComfyUI nodes, API workflow, governed
keyframe path and acceptance tests have been validated.

## Architecture decision

The authority layers are separated explicitly:

Governed Shot / reviewed production authority
→ Universal Production Description (complete audit authority)
→ cinematic provider prompt compiler
→ governed ReferencePlan / future governed Shot Composition Keyframe
→ provider workflow candidate
→ exact payload audit
→ provider execution
→ GeneratedMedia
→ human visual acceptance

Governance metadata, CAP IDs, reference roles, file paths, checksums and provider-specific
implementation terminology are prohibited from the creative text prompt. They remain
machine-readable conditioning/audit authority.

## Cinematic prompt contract

ProductionProviderPromptCompiler now emits:

1. scene prompt — literal visual setup + chronological action + minimal camera/lighting/environment;
2. motion prompt — compact physical action for future governed-keyframe I2V candidates;
3. negative prompt — provider safeguards and governed negative constraints.

Limits:

- scene prompt: at most 150 words;
- motion prompt: at most 90 words;
- no silent truncation;
- no governance/reference prose in creative text.

For a governed two-person bridge restriction, the positive prompt explicitly states that
exactly two people are visible and that other bridge stations remain empty. Negative
safeguards continue to prohibit extra/background people and additional crew/officers.

## Runtime prompt boundary

Candidate A still uses the current LTX-2.3 Ingredients workflow, but runtime enrichment no
longer injects reference-role descriptions such as group_identity/environment_reference or
"GOVERNED REFERENCE ROLE AUTHORITY" into the text encoder prompt.

The continuity custom node passes the scene prompt unchanged for a series-entry Shot. A real
previous-shot continuity frame adds only a short natural-language continuity instruction.

## Controlled A/B/C evaluation

### Candidate A — control

- LTX-2.3 Ingredients / current governed multi-reference workflow.
- New cinematic scene prompt.
- Executable now.
- Purpose: isolate how much of SHT-001 failure was prompt overload.

### Candidate B — keyframe control

- LTX-2.3 image-to-video.
- Governed Shot Composition Keyframe controls composition.
- Motion-only prompt.
- Not executable until the dedicated governed keyframe + I2V path is installed and assured.

### Candidate C — preferred target

- LTX-2.5 image-to-video / keyframe-first production path.
- Governed Shot Composition Keyframe controls exact starting composition.
- Motion-only prompt.
- Preferred target.
- Fail-closed until local LTX-2.5 deployment, API workflow and provider assurance pass.

The existing LTX-2.3 path remains the executable A control; VSCS does not silently substitute
an unvalidated B or C workflow.

## SHT-001 visual acceptance contract

Every candidate is evaluated against the same contract:

1. exactly two visible people for all governed frames;
2. James identity stable;
3. Sandra identity stable;
4. no extra crew;
5. correct Iron Horizon bridge;
6. Xorix visible in the correct place;
7. Sandra begins at her control station;
8. Sandra notices the reading;
9. Sandra turns toward James;
10. James remains focused forward;
11. no generated dialogue;
12. no scene cut;
13. no reference-sheet collapse;
14. no location transformation;
15. governed six-second duration.

A technically valid render that violates any of these is a visual acceptance failure.

## Generated Media and retry authority

A technically completed provider execution that has been ingested as Generated Media does not by
itself make the ProductionTask complete and does not consume the remaining human-governed attempt
budget. Generated Media becomes authoritative only through explicit human review/selection and
ProductionTask completion reconciliation. Therefore a GENERATED/UNDER_REVIEW/REJECTED candidate
must not disable Start Production or retry authorization while profile attempts remain.

This is required for visual acceptance work: a technically successful but visually failed render
must remain a candidate artifact, not a lock on further governed production attempts.

## Stage 1 acceptance

Automated:

- focused Phase 20.18.2.2f tests pass;
- Phase 20.18.2.2e/provider-reference regression remains green;
- LTX workflow/package guard tests remain green;
- Ruff check/format clean;
- MyPy clean;
- full pytest regression passes or any unrelated native Qt crash is isolated and documented;
- git diff --check clean.

Functional:

1. Recompile SHT-001 Production Package.
2. Inspect provider_prompt_contract:
   - compiler = cinematic-action-v2;
   - scene prompt <= 150 words;
   - motion prompt <= 90 words;
   - no CAP IDs/reference-role/governance prose.
3. Confirm provider_video_rebaseline:
   - active_candidate = A;
   - preferred_candidate = C;
   - B/C execution_ready = false.
4. Deploy the updated vscs_multi_reference_v721.py into ComfyUI and verify matching SHA-256.
5. Run exactly one Candidate A SHT-001 attempt.
6. Evaluate all fifteen visual acceptance criteria.

If Candidate A fails visual acceptance, do not iterate prompt wording indefinitely. Proceed to
the governed Shot Composition Keyframe + Candidate B/C workflow implementation inside this
same Phase branch.

Phase closure still requires explicit owner acceptance.
