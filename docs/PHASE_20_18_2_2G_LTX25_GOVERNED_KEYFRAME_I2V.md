# Phase 20.18.2.2g — LTX-2.5 Governed-Keyframe I2V

## Status

Application authority, manual Candidate C workflow, provider API workflow, custom package loader,
deployment assurance, and the fail-closed Candidate C backend are now implemented on the dedicated
Phase 20.18.2.2g branch. Automated/local ComfyUI acceptance is still required before the phase can
be closed.

Candidate A (LTX-2.3 Ingredients multi-reference) is retained only as the historical control.
Its clean-prompt manual test improved stability but still produced an additional person and failed
the governed SHT-001 story staging. Candidate C is therefore the preferred production target.

## Architecture decision

The final video generator no longer receives James, Sandra, Xorix and the bridge as independent
video-stage Ingredients references.

Instead:

canonical visual authority
→ governed Shot Composition Keyframe
→ explicit human keyframe approval
→ checksum-pinned keyframe authority
→ LTX-2.5 image-to-video
→ short motion-only prompt
→ governed output normalization
→ Generated Media
→ human visual acceptance

This deliberately tests the concern that the combined James+Sandra reference contributed to
Candidate A cast duplication. Candidate C's video stage receives one approved composition image,
not the combined identity reference or three independent IC-LoRA Ingredients guides.

## Governed keyframe authority

The persisted keyframe record is stored at:

`.vscs/governed_keyframes.json`

The approved image is checksum-pinned. Execution must fail closed if the image changes or if the
human approval does not cover every required keyframe criterion:

- exactly two visible people;
- James identity present;
- Sandra identity present;
- no extra crew;
- correct Iron Horizon bridge;
- Xorix visible in the correct place;
- Sandra at her control station;
- James at the forward display;
- wide static eye-level composition.

## Manual Candidate C workflow

The checked-in manual workflow is derived from the official Lightricks LTX-2.5 single-stage
T2V/I2V distilled workflow at upstream commit:

`dfb2786749af36f200ea023388dc729a3e106b42`

Source:

`example_workflows/2.5/LTX-2.5_T2V_I2V_Single_Stage_Distilled.json`

VSCS changes only the operator-facing I2V settings and prompts:

- use image input: ON;
- prompt enhancement: OFF;
- governed keyframe: `VSCS_SHT001_Governed_Keyframe.png`;
- 1280×720;
- 24 fps;
- 6 seconds;
- image strength 0.90;
- CFG 1.0;
- fixed JavaScript-safe manual seed `2360325115660865`;
- motion-only prompt;
- explicit no-extra-people/no-dialogue negative prompt.

## SHT-001 motion prompt

Continue this exact shot. Keep the same two people, the same Iron Horizon bridge composition, and Xorix visible on the forward display. Sandra remains at her control station, notices the unusual reading, pauses, then near the end turns her head and attention toward James. James remains steady and focused on the forward display. Keep the camera completely static. Silent. No additional people.

## Negative prompt

extra people, background crew, third person, additional bridge crew, additional officers, crowd, duplicate people, duplicated character, identity swap, merged identity, changing faces, changing uniforms, speaking, dialogue, generated speech, mouth talking, scene cut, camera movement, zoom, pan, close-up, insert shot, split screen, contact sheet, tiled references

## Acceptance

Phase 20.18.2.2g does not close merely because LTX-2.5 executes. The resulting video must satisfy
the existing fifteen SHT-001 visual acceptance criteria. The governed keyframe itself must first
pass all nine keyframe criteria above.

The production provider path remains fail-closed until:

1. the local LTX-2.5 model files are installed;
2. the ComfyUI-LTXVideo version exposes the required 2.5 nodes;
3. the governed keyframe is human-approved and checksum-pinned;
4. the checked-in provider API workflow passes deployment assurance;
5. the exact provider payload is audited before submission.

## Provider integration

The checked-in provider workflow is:

`resources/workflows/workflows/ltx25_i2v_keyframe_v1_api.json`

The manifest is:

`resources/workflows/manifests/ltx25_i2v_keyframe_v1.json`

The ComfyUI package loader is:

`resources/workflows/custom_nodes/vscs_ltx25_keyframe_v1.py`

The Phase 20.18.2.2g infrastructure composition now selects the Candidate C backend. Production
Package compilation therefore fails closed until an approved governed keyframe is registered.

The provider API graph uses the lower-memory LTX-2.5 convolutional video VAE plus the Comfy
INT8 ConvRot distilled transformer and text encoder. This is the Phase 20.18.2.2g execution
profile for the target RTX 5060 Ti 16GB system. Prompt enhancement remains disabled, but the
matching INT8 ConvRot enhancer model is selected in the manual workflow so the graph remains
internally coherent if enhancement is explicitly enabled during diagnostics.

Measured local readiness on 2026-09-22:
- GPU: NVIDIA GeForce RTX 5060 Ti, 16GB VRAM;
- idle VRAM usage after reboot/cleanup: approximately 1.5GB;
- system RAM: 31.1GB;
- free system RAM before testing: approximately 15.27GB;
- CUDA UMD: 13.4;
- required INT8 ConvRot transformer and text encoders are present.

Because this hardware is below the standard BF16 memory envelope, production acceptance requires
a low-cost smoke test before a full 1280×720 / 6-second render.

The current ComfyUI installation stores the LTX-2.5 models in `ltx2.5` subfolders. The
checked-in manual and provider workflows therefore reference these exact relative model names:

- `diffusion_models/ltx2.5/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors`
- `vae/ltx2.5/ltx-2.5-audio-vae-bf16.safetensors`
- `vae/ltx2.5/ltx-2.5-video-vae-conv-bf16.safetensors`
- `text_encoders/ltx2.5/gemma4_e2b_it_int8_convrot.safetensors`
- `text_encoders/ltx2.5/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors`

### 16GB readiness smoke test

Open:

`resources/workflows/manual/ltx25_candidate_c_lowvram_smoke_ui.json`

This workflow uses the same Candidate C architecture and INT8 ConvRot models, but reduces the
diagnostic render to 960×544 and two seconds (49 provider frames at 24fps). It is not a production
acceptance render. A PASS means model loading, I2V conditioning, sampling, VAE decode, and video
save all complete without CUDA OOM or node failure. After this passes, restore the full manual
workflow for the governed 1280×720 / six-second SHT-001 test.

