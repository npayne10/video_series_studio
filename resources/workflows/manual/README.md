# Phase 20.18.2.2f Candidate A — Manual ComfyUI Bench

These workflows are human-editable ComfyUI UI graphs for diagnosing SHT-001 outside the VSCS
Production Execution UI.

They deliberately remove:

- VSCSProductionPackageLoaderV720;
- VSCSContinuityPromptV721;
- VSCSMultiReferenceResolverV721;
- ReferencePlan JSON as an input authority.

They retain the Candidate A generation architecture:

- LTX-2.3 22B distilled 1.1;
- LTX-2.3 Ingredients IC-LoRA;
- three attention-only IC-LoRA guides with frame_idx = -1;
- fixed VSCS seed;
- 1280×720;
- 145 provider frames;
- 144 governed output frames;
- 24 fps;
- Candidate A sampler / sigma schedule.

## Workflow files

1. `ltx23_candidate_a_manual_ui_vscs_prompt.json`
   - exact Phase 20.18.2.2f VSCS positive/negative prompts from the accepted SHT-001 package.
2. `ltx23_candidate_a_manual_ui_benchmark_prompt.json`
   - identical graph and seed, but with the clean benchmark prompt.
   - this is the controlled prompt-only comparison.

## Reference image names expected in ComfyUI/input

- `VSCS_SHT001_James_Sandra.png`
- `VSCS_SHT001_Xorix.png`
- `VSCS_SHT001_Iron_Horizon_Bridge.png`

The default direct guide strengths reproduce the current provider reference weights when no
previous-shot continuity frame exists:

- James + Sandra: 0.90
- Xorix: 0.25
- Iron Horizon bridge: 0.25

The old 0.495 / 0.1375 / 0.1375 figures are not used here; the accepted package has
reference_guide_strength = 1.0 and the resolver therefore passes the reference weights above.

## Controlled test rule

For Test 1 vs Test 2, do not change:

- model files;
- reference images;
- guide strengths;
- seed;
- width/height;
- provider/governed frame counts;
- fps;
- sampler;
- sigmas.

Only the positive and negative prompt text differs.

If the benchmark prompt materially improves SHT-001, prompt compilation remains a major factor.
If it does not, Candidate A should be treated as an architecture limitation and Phase 20.18.2.2f
should proceed to governed-keyframe I2V Candidates B/C.
