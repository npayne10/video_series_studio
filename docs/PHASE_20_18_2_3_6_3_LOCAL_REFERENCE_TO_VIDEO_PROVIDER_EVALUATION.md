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
