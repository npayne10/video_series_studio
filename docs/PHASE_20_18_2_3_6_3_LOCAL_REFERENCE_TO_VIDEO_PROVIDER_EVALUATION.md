# Phase 20.18.2.3.6.3 — Local Reference-to-Video Provider Evaluation

Status: IN EVALUATION  
Date: 2026-09-29

## 1. Purpose

Phase 20.18.2.3.6.3 pauses further investment in prompt-driven still-frame injection and evaluates whether a local reference-conditioned video provider can satisfy the original VSCS Story-to-Series objective more directly.

The phase is an evaluation phase. It must not make a new provider the production default until the local hardware, continuity, automation, licensing, and live-shot acceptance gates in this document are passed.

## 2. Reasserted VSCS production laws

The following are governing requirements, in priority order.

1. Automation first.
   - Story-to-Series transition must require as little routine human intervention as practical.
   - Operator review is primarily for creative intent, low-confidence exceptions, and final quality.
   - VSCS should automatically resolve references, prompts, provider strategy, retries, normalization, assembly, and technical QC.

2. Continuity and cinematic quality are non-negotiable.
   - Characters, clothing, ships, locations, props, voices, camera continuity, lighting, scale, and spatial relationships are governed assets.
   - Technically valid media that visibly exhibits AI failure modes is not acceptable production media.
   - Identity drift, duplicate people, character replacement, disappearing characters, teleportation, architecture drift, scene-card overlays, and inconsistent scale are failures.

3. Local generation is the default economic model.
   - Normal series production must prefer local execution on owned hardware.
   - Compute time and electrical consumption are acceptable operational costs.
   - Per-shot or per-second API charges must not become a required production dependency.
   - Paid providers may be retained only as optional benchmark, emergency fallback, or exceptional-quality escalation.

These laws outrank provider-specific convenience.

## 3. Problem statement

The Phase 3.6.1 and 3.6.2 experiments proved that prompt-driven character injection is not a reliable production architecture for multi-character scenes.

Observed failure classes include:

- extra or duplicated people;
- introduced character appearing centrally rather than entering;
- fully arrived / teleported first visibility;
- incorrect subject scale;
- scene-region replacement;
- generated background panels covering existing characters;
- repeated human approval/regeneration loops;
- provider-specific recovery complexity.

The key lesson is that VSCS should condition generation from canonical authority upstream, rather than generate a scene and repeatedly repair continuity downstream.

## 4. Evaluation question

Can VSCS compile its existing governed canonical references directly into a LOCAL reference-to-video provider that can generate a production-quality multi-character shot while preserving continuity and requiring materially less manual intervention?

The first live benchmark remains:

- Shot: EP-001-SCN-001-SHT-002
- Duration: 6 seconds
- Production target: 1280x720, 24 fps, 144 final frames
- Established characters: James and Sandra
- Introduced character: Ros at frame 96 / approximately four seconds
- Location: Iron Horizon bridge
- Exterior visual: Xorix

## 5. Candidate provider set

### 5.1 MiniMax H3 native R2V — PRIMARY LOCAL CANDIDATE

Current ComfyUI native H3 support provides:

- native open-weight local execution;
- Reference-to-Video conditioning;
- prompt-addressable reference images, videos, and audio;
- up to 9 reference images;
- up to 3 reference videos;
- up to 3 standalone reference audio clips;
- explicit reference tags such as `<Picture 1>`, `<Video 1>`, `<Audio 1>`;
- arbitrary frame guide anchoring through MiniMax H3 guide nodes;
- latent noise masks / video inpainting;
- native 24 fps generation;
- native reference-conditioning nodes in ComfyUI core.

Initial VSCS mapping:

| VSCS authority | H3 binding |
| --- | --- |
| CAP-CHR-001 James | <Picture 1> |
| CAP-CHR-003 Sandra | <Picture 2> |
| CAP-CHR-005 Ros | <Picture 3> |
| CAP-LOC-021 Iron Horizon Bridge | <Picture 4> |
| CAP-PLN-002 Xorix | <Picture 5> |
| governed previous-shot / opening state | reference or guide input |
| timed Ros introduction | prompt timing and, if required, guide authority |

The reference ordering must be compiled deterministically from VSCS authority. Operators must not manually assign tags during normal production.

Hardware investigation target:
- pruned INT8 ConvRot Ref2VA diffusion weights;
- Qwen3-VL quantized text encoder;
- layerwise / model offload;
- 16 GB VRAM viability;
- sufficient system RAM and disk staging;
- 720p-class test before higher-resolution evaluation.

Important: H3 native generation works on its own supported frame/resolution grid. VSCS final delivery dimensions remain governed and may require normalization after generation.

### 5.2 Wan 3.0 Reference-to-Video — BENCHMARK, NOT DEFAULT

Wan 3.0 Reference-to-Video exposes explicit `@ImageN`, `@VideoN`, and `@AudioN` roles and is conceptually aligned with VSCS canonical authority.

Current official ComfyUI Wan 3.0 R2V integration is a Partner/API node rather than the preferred zero-generation-cost local path.

Therefore:
- retain as an architecture/quality benchmark;
- do not make it the normal VSCS production provider while per-generation charging is required;
- reassess if equivalent local weights/workflows become available.

### 5.3 Wan 2.2 Animate — SPECIALIST LOCAL FALLBACK

Wan 2.2 Animate supports local reference-character animation/replacement using a reference image plus source/pose video.

Potential role:
- character replacement;
- controlled motion transfer;
- difficult single-character action;
- repair/escalation workflow.

It is not currently treated as the primary general multi-reference scene generator.

### 5.4 LTX current local provider — BASELINE

The current LTX pipeline remains the baseline for:
- local generation;
- existing VSCS integration;
- known hardware behavior;
- governed keyframe I2V;
- current span/orchestration capability.

The evaluation must determine where LTX remains the better provider and where reference-conditioned generation materially improves continuity.

## 6. MiniMax H3 licensing gate

The MiniMax H3 Community License defines an Applicable Territory as worldwide excluding the EU, UK, Republic of Korea, and USA.

For a South African local deployment, South Africa is not listed among the excluded territories. This is a technical project finding, not legal advice.

Before H3 may be frozen as a production provider, VSCS documentation must record:
- license version/date;
- applicable territory requirement;
- commercial attribution/display obligations;
- revenue-triggered authorization conditions;
- acceptable-use restrictions;
- prohibition on using H3 outputs to improve unrelated AI models.

Provider licensing is part of provider capability authority, not an informal installation note.

## 7. Hardware feasibility gate

The local feasibility experiment must record:

- GPU model and VRAM;
- system RAM available;
- pagefile / virtual memory if required;
- ComfyUI version;
- Torch/CUDA version;
- exact H3 model filenames and checksums;
- text encoder variant;
- VAE variants;
- offload mode;
- peak observed VRAM;
- peak system RAM;
- generation wall-clock time;
- output resolution;
- generated frame count;
- provider failures / OOM behavior.

PASS requires:
- execution on the owned 16 GB GPU without a paid inference provider;
- no unrecoverable OOM;
- restart-safe workflow behavior;
- acceptable unattended runtime even if slow.

Runtime speed is secondary to generation quality and monetary cost.

## 8. SHT-002 controlled experiment

### Test A — H3 R2V canonical references only

Inputs:
- James canonical image;
- Sandra canonical image;
- Ros canonical image;
- Iron Horizon bridge canonical image;
- Xorix canonical image;
- governed shot prompt;
- deterministic seed.

Purpose:
Determine whether R2V alone can preserve the established scene and introduce Ros at the intended time.

### Test B — H3 R2V plus opening-state continuity

Add:
- exact governed previous/initial visual state as a reference or guide.

Purpose:
Determine whether existing scene composition and established characters are better preserved.

### Test C — H3 R2V plus temporal guide

Add:
- explicit H3 guide authority around the intended Ros introduction point if direct timed prompting is insufficient.

Purpose:
Determine whether VSCS can govern an event near frame 96 without manually manufacturing the entire transition.

### Test D — H3 masked refinement

Only if A-C are close but fail locally around the introduction region:
- use H3 latent noise mask / inpainting;
- preserve the rest of the generated or governed video.

This is a fallback, not the desired normal path.

## 9. Prompt/reference contract prototype

The provider-neutral VSCS request should compile semantic roles, not provider syntax.

Example conceptual authority:

```text
established_character: CAP-CHR-001 James
established_character: CAP-CHR-003 Sandra
introduced_character: CAP-CHR-005 Ros
location: CAP-LOC-021 Iron Horizon Bridge
planet: CAP-PLN-002 Xorix
event: Ros ENTER at global frame 96
continuity: preserve established characters and location
```

The H3 adapter may translate this to:

```text
<Picture 1> is James identity authority.
<Picture 2> is Sandra identity authority.
<Picture 3> is Ros identity authority.
<Picture 4> is Iron Horizon Bridge environment authority.
<Picture 5> is Xorix visual authority.
...
```

No H3-specific tag may leak into the domain model.

## 10. Quality acceptance matrix

Every generated benchmark is assessed against the same provider-neutral criteria.

| Criterion | Required |
| --- | --- |
| James identity retained | PASS |
| Sandra identity retained | PASS |
| Ros identity retained | PASS |
| Correct human count | PASS |
| No duplicate Ros | PASS |
| Sandra never replaced/covered | PASS |
| Ros introduction temporally believable | PASS |
| No teleportation / sudden completed pose | PASS |
| Bridge architecture continuity | PASS |
| Xorix visual continuity | PASS |
| Clothing/uniform continuity | PASS |
| Human anatomy acceptable | PASS |
| No obvious AI surface artifacts | PASS |
| Camera/spatial continuity acceptable | PASS |
| Final normalized duration/frame count exact | PASS |

Any critical identity, human-count, replacement, or scene-continuity failure is an automatic reject.

## 11. Automation acceptance matrix

The candidate is not suitable for VSCS merely because it can make one good clip.

PASS requires that VSCS can automate:

- ReferencePlan -> provider reference-role compilation;
- model selection;
- workflow construction;
- seed governance;
- local provider submission;
- progress/telemetry;
- restart recovery;
- exact output ingestion;
- resolution/frame normalization;
- technical QC;
- continuity evidence capture;
- retry/regeneration without manual workflow editing.

Manual ComfyUI node editing is acceptable during this evaluation only. It is not acceptable as the final production workflow.

## 12. Cost acceptance

Normal local generation monetary inference cost:

```text
required target = 0 paid API credits per normal shot
```

Electricity, local compute time, local storage, and already-owned hardware are not treated as per-generation provider charges.

A paid provider can only be an optional escalation tier.

## 13. Evaluation outcome states

### ADOPT
The provider passes hardware, automation, continuity, licensing, and live-shot quality gates.

Action:
Implement a provider-neutral R2V production contract and provider adapter.

### SPECIALIST
The provider is excellent for a narrower workload but not a general production default.

Action:
Add it to the strategy resolver for those shot classes only.

### BENCHMARK_ONLY
Quality may be useful but cost/licensing/local-execution rules prevent default production use.

### REJECT
Fails continuity, automation, hardware, or licensing requirements.

## 14. Phase decomposition

### 3.6.3a — Provider capability and hardware feasibility
- verify H3 local installation requirements;
- verify model/licensing constraints;
- verify 16 GB execution strategy;
- freeze benchmark inputs and metrics.

### 3.6.3b — H3 local ComfyUI R2V spike
- install native H3 Ref2VA weights;
- run minimal low-resolution smoke test;
- capture VRAM/RAM/runtime evidence;
- run SHT-002 Test A.

### 3.6.3c — ReferencePlan-to-R2V binding prototype
- deterministic provider-neutral semantic roles;
- H3 tag compiler;
- checksums and reference order;
- reproducible workflow package.

### 3.6.3d — Continuity and temporal-control experiments
- Tests B/C/D;
- guides;
- masked refinement only if required;
- comparison against current LTX baseline.

### 3.6.3e — Model strategy decision
- classify H3, LTX, Wan 2.2 Animate, and Wan 3.0 benchmark roles;
- no single-provider assumption;
- define provider selection rules.

### 3.6.3f — VSCS integration decision
Only after evidence:
- ADOPT / SPECIALIST / BENCHMARK_ONLY / REJECT;
- approve next implementation phase;
- retire or retain 3.6.2 injection machinery accordingly.

## 15. Current preliminary finding

Based on current ComfyUI capabilities, MiniMax H3 native R2V is the strongest candidate for the first hands-on local test because it combines:

- local open-weight execution;
- explicit multi-reference conditioning;
- reference images/video/audio;
- arbitrary guide anchoring;
- masked video refinement;
- 24 fps native video;
- direct compatibility with the semantic role architecture VSCS already maintains.

Wan 3.0 remains strategically important because its reference-tag model is closely aligned with VSCS, but its current official ComfyUI R2V path conflicts with the local-first cost requirement.

No production-provider decision is made by this document.

## 16. Immediate next acceptance step

Proceed with Phase 3.6.3a only.

The first hands-on objective is not SHT-002 generation. It is:

1. inventory the local workstation;
2. update/verify ComfyUI native H3 support;
3. acquire the smallest viable H3 Ref2VA model set;
4. verify licensing acknowledgement;
5. run a low-resolution local H3 R2V smoke test;
6. measure memory and runtime;
7. only then run the governed SHT-002 benchmark.

This protects VSCS from investing architecture around a provider before proving it can operate economically on the actual production hardware.


## 17. Phase 3.6.3b.1 — Local H3 R2V smoke-test evidence

Date: 2026-09-29

### Runtime configuration

- Provider: MiniMax H3 native Reference-to-Video (ComfyUI)
- GPU: NVIDIA GeForce RTX 5060 Ti, 15.9 GiB VRAM
- PyTorch: 2.13.0+cu130
- CUDA runtime reported by PyTorch: 13.0
- Diffusion model: `minimax_h3_ref2va_pruned_int8_convrot.safetensors`
- Text encoder: `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`
- Video VAE: `minimax_h3_video_vae_fp16.safetensors`
- Audio VAE: `minimax_h3_audio_vae_fp32.safetensors`
- Reference image count: 1
- Reference authority: CAP-CHR-005 Ros
- Resolution: 608x352
- FPS: 24
- Frames: 56
- Duration: 2.333333 seconds
- Sampler: res_multistep
- Scheduler: simple
- Steps: 20
- Reference image size: match
- Turbo LoRA: not used in this baseline
- Paid inference: none

### Provider execution evidence

ComfyUI successfully:
- staged the H3 video VAE for dynamic VRAM loading;
- staged the quantized Qwen3-VL H3 text encoder for dynamic VRAM loading;
- detected mixed-precision quantization and native NVFP4 / INT8 operations;
- staged the H3 Ref2VA diffusion model for dynamic VRAM loading;
- completed all 20 sampling steps;
- staged and decoded the H3 audio VAE;
- completed the full prompt in 262.04 seconds.

Reported staged model sizes included approximately:
- H3 Video VAE: 4965 MB;
- H3 text encoder: 14956 MB;
- H3 Ref2VA diffusion model: 19995 MB;
- H3 Audio VAE: 576 MB.

This proves that the official H3 native Ref2VA stack can execute locally on the owned RTX 5060 Ti 16 GB system using ComfyUI dynamic VRAM loading/offload.

### Output verification

The generated MP4 was verified as:
- H.264 video;
- 608x352;
- 24 fps;
- 56 frames;
- duration 2.333333 seconds;
- AAC stereo audio at 32 kHz.

### Visual findings

Positive:
- Ros remained visually stable across sampled frames;
- face, hair, uniform and overall identity remained coherent;
- motion was restrained and temporally stable;
- no obvious frame-to-frame identity collapse was observed;
- the result was substantially more coherent than the prior still-image injection experiments.

Failure relative to the strict smoke-test prompt:
- additional background crew were generated even though the prompt requested exactly one person.

Interpretation:
- H3 local R2V hardware/runtime feasibility: PASS.
- Single-reference identity-conditioning feasibility: PRELIMINARY PASS.
- Exact person-count / exclusion authority from prompt alone: FAIL.
- The next experiment must test whether explicit multi-reference scene authority improves or worsens controlled multi-character composition before any VSCS provider-adoption decision.

Peak VRAM was not captured in this run and remains required evidence for the hardware characterization.

### 3.6.3b.1 status

PASS for local execution and basic reference identity conditioning.

Proceed to 3.6.3b.2 production-aligned multi-reference test only after recording a clean pre-run VRAM baseline and maintaining deterministic seed/configuration.


## 18. Phase 3.6.3b.2 — Production-aligned five-reference H3 R2V test

Date: 2026-09-29

### Test configuration

The production-aligned test used five reference images in deterministic order:

1. James canonical identity
2. Sandra canonical identity
3. Ros canonical identity
4. Iron Horizon bridge environment
5. Xorix planetary visual

Baseline generation settings remained intentionally unchanged from the successful 3.6.3b.1 local smoke test except for reference complexity:

- resolution: 608x352;
- 24 fps;
- 56 frames / 2.333333 seconds;
- sampler: res_multistep;
- scheduler: simple;
- steps: 20;
- denoise: 1.0;
- reference image size: match;
- Turbo LoRA: not used;
- local native H3 Ref2VA execution;
- zero paid inference.

### Provider execution evidence

ComfyUI successfully staged all five reference-image conditioning paths and the H3 runtime stack under dynamic VRAM loading.

Reported execution:
- MiniMax H3 Video VAE staged: approximately 4965 MB;
- MiniMax H3 text encoder staged: approximately 14956 MB;
- MiniMax H3 Ref2VA diffusion model staged: approximately 19995 MB;
- MiniMax H3 Audio VAE staged: approximately 576 MB;
- all 20 sampling steps completed;
- sampling duration: approximately 4 minutes 12 seconds;
- total prompt execution: 343.81 seconds.

The generated media was verified as:
- 608x352;
- 24 fps;
- 56 frames;
- duration 2.333333 seconds.

### Visual findings

Across sampled frames from the beginning, middle, and end of the generated video:

- exactly three human subjects are present;
- the seated right-side character remains stable and does not disappear;
- the central established character remains stable;
- the entering foreground character begins partially outside the left edge and moves progressively inward;
- no additional background crew are visible;
- no duplicate Ros is visible;
- no grey-card, rectangular patch, or pasted-background artifact appears;
- all three subjects remain integrated into the same bridge lighting/environment;
- the forward planetary visual remains present throughout;
- the bridge layout is temporally stable;
- the entry motion is continuous rather than a one-frame pop-in.

This is a material improvement over both:
1. the Phase 3.6.2 still-image injection approach, which replaced scene regions and obscured existing characters; and
2. the single-reference H3 smoke test, which generated unwanted background crew.

### Acceptance result

- Runtime / local execution: PASS
- Exact visible human count: PASS
- No duplicate entrant: PASS
- Established-character persistence: PASS
- Continuous edge-entry motion: PASS
- Environment temporal continuity: PASS
- No rectangular compositing artifact: PASS
- Multi-reference identity conditioning: PRELIMINARY PASS, subject to higher-resolution facial inspection
- Production resolution: NOT TESTED
- Exact 6-second SHT-002 timing / frame-96 event authority: NOT TESTED
- Peak VRAM evidence: still required if not separately captured

### Interpretation

Phase 3.6.3b.2 provides the first evidence that native local H3 Reference-to-Video can solve the core VSCS multi-character introduction problem as a single coherent generation task rather than through downstream still-image injection.

This does not yet authorize H3 as the production default. The next experiments must determine:
- identity fidelity at higher resolution;
- whether reference-image-size=max materially improves identity;
- whether scheduler changes improve reference fidelity;
- whether the full six-second SHT-002 timing can be governed reliably;
- whether temporal guide anchoring can control the Ros introduction near the required frame without manual asset manufacture;
- peak VRAM / system-RAM behavior.

The result is strong enough to continue the H3 evaluation before investing further in masked-compositing architecture.


## 19. Phase 3.6.3b.3 — Higher-resolution identity fidelity test

Date: 2026-09-29

### Test configuration

The five-reference production-aligned H3 Ref2VA configuration from 3.6.3b.2 was retained, with the principal change being output resolution:

- resolution increased from 608x352 to 864x480;
- 24 fps;
- 56 frames / 2.333333 seconds;
- sampler: res_multistep;
- scheduler: simple;
- steps: 20;
- denoise: 1.0;
- reference image size: match;
- Turbo LoRA: not used;
- local native H3 Ref2VA execution;
- zero paid inference.

### Provider execution evidence

ComfyUI successfully completed the higher-resolution run using dynamic VRAM loading.

Reported:
- MiniMax H3 Video VAE staged: approximately 4965 MB;
- MiniMax H3 text encoder staged: approximately 14956 MB;
- MiniMax H3 Ref2VA diffusion model staged: approximately 19995 MB;
- MiniMax H3 Audio VAE staged: approximately 576 MB;
- all 20 sampling steps completed;
- sampling duration: approximately 12 minutes 21 seconds;
- total prompt execution: 14 minutes 34 seconds.

The generated media was verified as:
- 864x480;
- 24 fps;
- 56 frames;
- duration 2.333333 seconds.

### Visual findings

Across frames sampled from the beginning, middle, and end of the video:

- exactly three people remain visible;
- the seated right-side character persists throughout;
- the established central standing character remains stable;
- the entering character begins at the left edge and moves progressively into the shot;
- no extra background crew are visible;
- no duplicate entrant is visible;
- no grey-card or rectangular patch artifact appears;
- bridge geometry and the forward planetary visual remain stable;
- the higher resolution materially improves facial, uniform, console, and environment detail relative to the 608x352 test;
- entry motion remains continuous rather than a single-frame appearance.

### Acceptance result

- Local execution at 864x480: PASS
- Exact visible human count: PASS
- Established-character persistence: PASS
- Continuous edge-entry motion: PASS
- Environment continuity: PASS
- No compositing/card artifact: PASS
- Multi-reference identity fidelity: PASS at evaluation resolution, subject to canonical close comparison before production adoption
- Runtime cost: ACCEPTABLE but materially higher than 608x352
- Paid inference: none
- Peak VRAM evidence: still required if not separately captured
- Full six-second SHT-002 timing / frame-96 event authority: NOT TESTED

### Interpretation

The higher-resolution run strengthens the evidence that H3 native Ref2VA is a viable local multi-character provider for VSCS. The increase from 608x352 to 864x480 preserved the successful composition and entry behavior while improving visible detail.

The principal trade-off is runtime. Total execution increased from 343.81 seconds in the lower-resolution five-reference test to 874 seconds in this run, approximately 2.54x longer.

The next evaluation should target temporal authority rather than immediately increasing resolution again: test a longer governed shot and determine whether Ros can be kept absent initially and introduced near the required SHT-002 event time using prompt timing and/or MiniMax H3 guide anchoring.


## 20. Phase 3.6.3b.4 — Prompt-only temporal introduction authority

Date: 2026-09-30

### Test configuration

- five-reference H3 Ref2VA production-aligned configuration;
- 608x352;
- 24 fps;
- 158 frames / approximately 6.58 seconds;
- sampler: res_multistep;
- scheduler: simple;
- steps: 20;
- ref_image_size: match;
- fixed seed;
- no Turbo LoRA;
- prompt requested James and Sandra only until approximately four seconds, then Ros entering from the right edge.

### Result

The run completed successfully, but the generated shot contained too many people.

Observed across the generated sequence:
- extra background people are already present from frame 0;
- therefore the strict two-person pre-entry state is not preserved;
- Ros does begin entering from the right edge later in the shot;
- first obvious right-edge Ros presence appears around frames 76-80, approximately 3.2-3.3 seconds;
- this is earlier than the governed frame-96 / 4.0-second target;
- Ros's entry motion itself is progressive rather than a one-frame pop-in;
- bridge and planetary continuity remain visually stable.

### Acceptance

- local execution: PASS
- long-shot runtime feasibility: PASS
- prompt-only exact person-count authority: FAIL
- prompt-only pre-entry absence authority: FAIL
- prompt-only temporal targeting: PARTIAL
- continuous Ros entry motion: PASS
- environment continuity: PASS

### Interpretation

Prompt text alone is insufficient to guarantee exact character count and temporal absence over a longer multi-character H3 Ref2VA shot.

The next experiment should use explicit MiniMax H3 guide anchoring rather than adding more prompt constraints.

A stronger VSCS-aligned test is:
- use the exact governed pre-entry source frame as a scene/composition guide before Ros appears;
- retain Ros as an explicit identity reference;
- anchor a governed guide at or near the intended introduction frame;
- reduce redundant character reference inputs where the guide already contains established characters, to avoid encouraging extra human synthesis.

This shifts temporal and composition authority from prose into explicit visual conditioning.


## 21. Phase 3.6.3b.5 — Prompt simplification control test

Date: 2026-09-30

### Purpose

This control test was run after 3.6.3b.4 produced unwanted background crew. The objective was to isolate whether that failure was inherent to H3 five-reference conditioning or was primarily induced by the later long/complex temporal prompt.

The same five semantic reference roles were retained:

1. James canonical identity
2. Sandra canonical identity
3. Ros canonical identity
4. Iron Horizon bridge environment
5. Xorix planetary visual

The prompt was reverted to the earlier, simpler five-reference wording that had succeeded in 3.6.3b.2.

### Output inspected

- File: `MiniMax_H3_00008_(2).mp4`
- Resolution: 608x352
- FPS: 24
- Frames: 175
- Duration: approximately 7.29 seconds

### Visual findings

Across opening, intermediate, and final sampled frames:

- exactly three intended people are present;
- no additional background crew are visible;
- no duplicate Ros is visible;
- the central established male character remains temporally stable;
- the seated right-side female character remains present and temporally stable;
- the entering male character remains visually stable through the sequence;
- Ros enters progressively from the left edge and moves inward continuously;
- no teleport/pop-in event was observed;
- bridge geometry remains coherent and stable;
- Xorix remains present and visually coherent in the forward view;
- no grey-card, rectangular insertion, pasted-cutout, or scene-replacement artifact is visible;
- no material temporal identity collapse was observed.

Important timing limitation:

- Ros is already partially visible at the extreme left edge from frame 0;
- therefore this result does NOT prove governed pre-entry absence;
- it also does NOT prove frame-96 introduction authority.

Canonical facial fidelity was not independently re-scored against the source reference images during this control review. This test establishes temporal stability and role consistency, while the prior higher-resolution evaluation remains the stronger identity-fidelity evidence.

### Comparison with 3.6.3b.2 and 3.6.3b.4

3.6.3b.2 used the simpler five-reference prompt and produced exactly three people with stable composition.

3.6.3b.4 retained five-reference conditioning but introduced a substantially longer and more repetitive temporal/exclusion prompt. That run produced extra background crew from frame 0 and failed exact initial human count.

3.6.3b.5 returned to the simpler prompt while retaining the five-reference concept and again produced exactly the three intended people with no background crew.

The repeated success pattern is therefore:

```text
five references + simpler prompt
-> exact intended human count

five references + long/repetitive temporal prompt
-> extra people

five references + simpler prompt again
-> exact intended human count
```

### Acceptance

- local execution: PASS
- exact visible human count: PASS
- no unwanted/background people: PASS
- established-character persistence: PASS
- entrant temporal stability: PASS
- continuous Ros entrance motion: PASS
- bridge continuity: PASS
- Xorix continuity: PASS
- no compositing/card artifact: PASS
- governed Ros absence before the event: FAIL
- exact frame-96 introduction authority: NOT PROVEN

### Conclusion

The evidence is now strong enough to conclude that the extra-people failure observed in 3.6.3b.4 was primarily associated with the structure/wording of the long temporal prompt rather than with H3 five-reference conditioning itself.

This is not evidence that prompt-only temporal governance is sufficient. The control test still exposes Ros from the opening frame, so exact timed introduction remains unresolved.

Architecturally:

- retain five-reference conditioning as a viable H3 capability;
- do not reduce canonical references merely to avoid the b.4 extra-person failure;
- treat prompt construction as a governed provider-adapter responsibility with regression-tested prompt templates;
- keep temporal event authority separate from descriptive prompt complexity;
- continue evaluation of explicit guide/temporal conditioning for frame-accurate introduction rather than attempting to solve timing by repeatedly adding prose constraints.

This control result changes the interpretation of 3.6.3b.4 but does not yet authorize H3 as the VSCS production default.


## 22. Governed H3 prompt template authority

Date: 2026-09-30

The concise five-reference prompt used successfully in 3.6.3b.2 and again in the 3.6.3b.5 prompt-simplification control is now retained as the baseline H3 prompt template for subsequent VSCS evaluation and provider-adapter design.

### Template authority

The following structure is the approved baseline pattern:

```text
<Picture 1> is the authoritative identity reference for Commander James Spence.
<Picture 2> is the authoritative identity reference for Sandra Crawford.
<Picture 3> is the authoritative identity reference for Major Ros Rohsgard.
<Picture 4> is the authoritative environment and composition reference for the Iron Horizon bridge.
<Picture 5> is the authoritative planetary reference for Xorix.

Create a short photorealistic cinematic science-fiction video set on the bridge of the Iron Horizon.

There must be exactly three people in the shot, and only these three people:
Commander James Spence, Sandra Crawford, and Major Ros Rohsgard.
Do not create any additional crew, background people, duplicate people, reflections that look like people, or partial extra bodies.

Use <Picture 4> to preserve the bridge layout, materials, lighting mood, and overall environment.
Use <Picture 5> so that Xorix is clearly visible through the forward front window or on the main forward display as an important visual element.

Character placement and action:
- James is already present near the centre of the bridge, standing and facing generally toward the front of the bridge.
- Sandra is already present at her control station on the right side of the frame, seated or working with her instruments.
- Ros enters naturally from the left edge of the frame and moves inward during the shot. He must walk into the scene; he must not teleport, pop in, fade in, or suddenly appear fully formed.

Identity preservation:
Preserve the face, age, hairstyle, uniform, insignia, body proportions, and overall appearance of each character from their respective reference image.
James must remain James.
Sandra must remain Sandra.
Ros must remain Ros.
Do not merge identities or substitute one character for another.

Shot style:
Static eye-level camera.
No cuts.
No zooms.
No pans.
Natural subtle motion only.
Ros should have clear entry motion from the left side.
James and Sandra should remain stable and believable in their positions.

Visual quality requirements:
Photorealistic, physically plausible lighting, realistic skin, realistic fabric, realistic materials, clean cinematic science-fiction look, neutral colour grading.
No compositing artifacts.
No pasted cutout look.
No grey box or background plate around Ros.
No warped faces.
No extra limbs.
No visible glitches.

The result must look like a coherent single live-action-style shot on the Iron Horizon bridge.
```

### Governance rules

- This template is the current baseline for H3 multi-reference scene generation.
- Future H3 prompts should preserve this concise structure unless a controlled experiment demonstrates a better pattern.
- New requirements must be added minimally and semantically, not by accumulating repetitive exclusions or long temporal prose.
- Temporal control should be delegated to explicit provider capabilities such as guides/anchors whenever practical rather than encoded through increasingly verbose prompt text.
- Provider-specific prompt syntax remains infrastructure-layer behavior and must not leak into the VSCS domain model.
- Prompt-template changes must be regression-tested against the successful multi-reference human-count and continuity behavior established in 3.6.3b.2 and 3.6.3b.5.
- The template is a provider-adapter baseline, not a universal prompt for every shot class. Shot-specific content may vary while preserving the successful structural pattern.

### Architectural implication

VSCS should treat prompt construction as governed, versioned provider behavior. The eventual H3 adapter should compile provider-neutral semantic authority into this stable prompt structure deterministically, with template versioning and regression evidence rather than free-form operator prompt authoring.


## 23. Phase 20.18.2.3.6.3d.1 — Governed Pre-Entry Guide Anchoring

Date: 2026-09-30  
Status: READY FOR CONTROLLED LOCAL RUN

### Objective

Determine whether explicit MiniMax H3 guide authority can enforce the governed opening state of SHT-002 without altering the successful five-reference prompt structure.

This subphase deliberately does **not** attempt to solve exact frame-96 introduction timing yet.

The first question is narrower:

> Can H3 begin from a governed visual state in which James and Sandra are present, Ros is absent, and the Iron Horizon bridge/Xorix composition is preserved?

### Controlled-variable rule

Retain unchanged:

- five reference-image roles and order;
- successful concise baseline prompt structure;
- 608x352 evaluation resolution;
- 24 fps;
- 20 steps;
- `res_multistep` sampler;
- `simple` scheduler;
- `ref_image_size=match`;
- no Turbo LoRA;
- same local Ref2VA model stack.

Introduce one major new variable only:

- one explicit `MiniMaxH3AddGuide` image guide at `frame_idx=0`.

### Guide authority

The guide image must come from existing governed continuity authority, not from a newly manufactured operator image.

Preferred source:

- exact accepted SHT-001 closing visual / inherited SHT-002 opening state;
- corresponding governed boundary authority: `GBF-36A2A8CA2E4D8452C20765FF`;
- accepted SHT-001 final-frame SHA: `c4b083314cb06b7c6884029827cd9c3eb1d784bea7f7d9f5fbddcb4e32abd3ef`.

If the exact accepted frame cannot be located, stop and recover that governed source image before running the experiment. Do not substitute a manually recreated bridge image.

### Native ComfyUI guide wiring

Use the native `MiniMaxH3AddGuide` node.

Wire:

1. `MiniMaxH3ReferenceToVideo.positive` -> `MiniMaxH3AddGuide.positive`
2. `MiniMaxH3ReferenceToVideo.latent` -> `MiniMaxH3AddGuide.latent`
3. H3 video VAE -> `MiniMaxH3AddGuide.vae`
4. governed SHT-001 accepted final frame -> `MiniMaxH3AddGuide.image`
5. `frame_idx = 0`
6. `MiniMaxH3AddGuide.positive` -> existing `BasicGuider`
7. Keep the original H3 latent path to the sampler unchanged.

Do not attach audio to the guide in this test.

Do not add a second guide in d.1.

### Prompt governance

Use the frozen five-reference baseline prompt template from Section 22.

For this test:

- retain the same reference declarations;
- retain the same exact-person-count language;
- retain the same identity-preservation block;
- retain the same camera and visual-quality blocks;
- do not add long temporal exclusions;
- do not repeat “Ros absent” throughout the prompt;
- do not add frame numbers to the prompt.

The guide is responsible for opening-state authority. Prompt prose remains descriptive rather than being used as the temporal-control mechanism.

### Expected generated duration

Use the same longer-shot duration class used for temporal evaluation so that the opening-state effect can be observed over enough time.

Target:
- approximately 6–7 seconds;
- 24 fps;
- native H3 frame-grid length as produced by the existing duration expression.

Exact frame-96 authority is explicitly out of scope for d.1.

### PASS criteria

d.1 passes only if:

- frame 0 starts from the governed bridge/opening composition;
- James is present;
- Sandra is present;
- Ros is genuinely absent at frame 0;
- no unwanted/background people are introduced at frame 0;
- James and Sandra remain visually coherent after the guide frame;
- bridge composition remains coherent;
- Xorix remains coherent;
- no guide-induced cut, card, patch, rectangle, or pasted-frame artifact appears;
- Ros, if introduced later by the model, enters continuously rather than appearing as a one-frame teleport;
- the result remains visually at least comparable to the successful 3.6.3b.2 / 3.6.3b.5 baseline.

### FAIL criteria

Automatic fail if:

- Ros is visible in the guided opening frame;
- additional people appear in the opening state;
- the guide replaces or damages the bridge composition;
- James or Sandra is lost/replaced;
- a visible discontinuity occurs immediately after the guide frame;
- the model treats the guide as a static card rather than integrated shot authority.

### Evidence to capture

Return:

- generated MP4;
- screenshot of the modified ComfyUI workflow showing the `MiniMaxH3AddGuide` node and its connections;
- screenshot or file identity of the exact governed guide image used;
- exact `frame_idx`;
- generated frame count and duration;
- seed;
- total runtime;
- any ComfyUI warnings/errors;
- sampled observations at frame 0, early motion, mid-shot, and final frames.

### Decision rule

If d.1 passes, proceed to 20.18.2.3.6.3d.2 and test temporal placement by adding/moving explicit guide authority near the governed introduction point.

If d.1 fails, do not immediately add more prompt wording. First determine whether the failure is:

- guide-strength/conditioning behavior;
- incorrect source guide;
- reference conflict;
- guide placement;
- or H3 inability to preserve a governed opening state under Ref2VA.

No provider-adoption decision is made by d.1 alone.


## 24. Phase 20.18.2.3.6.3d.1 — Governed Pre-Entry Guide Anchoring Results

Date: 2026-10-01  
Status: PASS

### Runtime configuration

- Provider: MiniMax H3 native Ref2VA
- Guide node: `MiniMaxH3AddGuide`
- Guide frame index: 0
- Governed guide source: `GBF-36A2A8CA2E4D8452C20765FF.png`
- Resolution: 608x352
- FPS: 24
- Frames: 175
- Duration: approximately 7.29 seconds
- Sampler: `res_multistep`
- Scheduler: `simple`
- Steps: 20
- Denoise: 1.0
- Ref image size: `match`
- Seed: 123456
- Turbo LoRA: not used
- Paid inference: none

### Provider execution evidence

ComfyUI reported:

- H3 Video VAE staged: approximately 4965 MB;
- H3 Ref2VA diffusion model staged: approximately 19995 MB;
- 20/20 sampling steps completed;
- sampling duration: approximately 18 minutes 24 seconds;
- H3 Audio VAE staged: approximately 576 MB;
- total prompt execution: 20 minutes 5 seconds;
- compiler graph breaks: 1;
- rogues: 0.

The run completed successfully.

### Visual findings

Frame-by-frame inspection of the generated MP4 established:

- frame 0 matches the governed opening-state composition closely;
- James is present at frame 0;
- Sandra is present at frame 0;
- Ros is absent at frame 0;
- no unwanted/background crew are visible in the governed opening state;
- bridge geometry remains coherent;
- Xorix remains present and visually coherent;
- no grey card, rectangular insert, pasted-frame artifact, or guide-card failure is visible;
- the guided frame transitions into generated motion without an obvious first-frame discontinuity;
- James and Sandra remain present and visually coherent as motion develops;
- Ros first becomes visibly detectable at approximately frame 18 (~0.75 s);
- Ros then enters progressively from the left edge rather than teleporting into a completed pose;
- no duplicate Ros or additional crew were observed through the inspected sequence;
- the shot remains temporally stable through the end of the generated clip.

### Acceptance

- governed frame-0 composition: PASS
- James present at frame 0: PASS
- Sandra present at frame 0: PASS
- Ros absent at frame 0: PASS
- no unwanted people at frame 0: PASS
- established-character persistence: PASS
- bridge continuity: PASS
- Xorix continuity: PASS
- guide integration without card/patch artifact: PASS
- continuous Ros entrance: PASS
- exact frame-96 introduction authority: NOT TESTED / NOT PROVEN

### Interpretation

Phase 20.18.2.3.6.3d.1 proves that explicit H3 guide authority can enforce a governed pre-entry opening state while preserving the successful five-reference prompt and multi-reference scene behavior.

This is materially stronger than prompt-only temporal control because the model begins from the correct two-person governed state without adding extra crew.

The remaining problem is no longer whether Ros can be absent initially. It is whether VSCS can control *when* Ros first becomes visible.

Observed first visibility in this d.1 run is approximately frame 18 (~0.75 s), far earlier than the production requirement of frame 96 (~4.0 s).

### Architectural implication

- retain the frozen concise five-reference H3 prompt template;
- retain frame-0 governed guide anchoring as valid opening-state authority;
- do not add long temporal prose;
- proceed to 20.18.2.3.6.3d.2 to test explicit temporal placement;
- d.2 should vary guide timing/authority rather than altering the successful prompt structure;
- exact frame-96 authority remains an unresolved acceptance gate.

No H3 production-default decision is authorized by d.1 alone.


## 25. Phase 20.18.2.3.6.3d.2 — Explicit Temporal Placement

Date: 2026-10-01  
Status: READY FOR GOVERNED GUIDE RECOVERY

Objective: test whether a second H3 guide anchored at frame 96 can move Ros's first visible introduction toward the governed SHT-002 target while preserving the successful d.1 opening anchor and frozen five-reference prompt.

Keep unchanged from d.1:
- five references and order;
- frozen prompt template;
- frame-0 governed guide;
- 608x352, 24 fps, ~7 s native-grid duration;
- 20 steps, res_multistep, simple scheduler, denoise 1.0;
- ref_image_size=match;
- seed 123456;
- no Turbo LoRA.

New variable only:
- chain a second MiniMaxH3AddGuide at frame_idx=96.

Guide 1:
- GBF-36A2A8CA2E4D8452C20765FF.png
- frame_idx=0.

Guide 2:
- existing governed SHT-002 introduction image showing Ros's intended first-visible entrance state;
- frame_idx=96.
- Do not manually manufacture or composite a replacement image.

Wiring:
MiniMaxH3ReferenceToVideo.positive -> Guide 1.positive
Guide 1.positive -> Guide 2.positive
MiniMaxH3ReferenceToVideo.latent -> Guide 1.latent and Guide 2.latent
Video VAE -> both guide VAE inputs
Guide 1 image = governed SHT-001 closing frame
Guide 2 image = governed SHT-002 introduction image
Guide 2.positive -> BasicGuider.conditioning
Sampler latent path remains unchanged.

Prompt rule:
Use the frozen successful prompt unchanged. Do not add frame numbers or repeated temporal exclusions.

Recover Guide 2 from governed project evidence before running. Search especially:
- .vscs/automated_introduction_boundaries/EP-001-SCN-001-SHT-002
- assets/governed_keyframes/EP-001-SCN-001-SHT-002
- .vscs/introduction_injection/EP-001-SCN-001-SHT-002

Primary timing result:
- PASS: Ros first visible at frame 96 +/- 8 frames, with all continuity gates passing.
- PARTIAL: Ros materially delayed versus d.1 but outside that range.
- FAIL: no material delay, severe early appearance, teleportation, duplication, or continuity failure.

Continuity gates remain:
James and Sandra persist; no extra people; no duplicate Ros; bridge and Xorix remain coherent; no guide-card or patch artifact; no abrupt cut at the second guide.

If d.2 passes, proceed to d.3 reproducibility/exact-production timing. If partial or fail, analyze guide placement/image/interpolation before changing prompt text.
