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

The provider API graph uses the lower-memory LTX-2.5 convolutional video VAE by default while
retaining the official LTX-2.5 distilled transformer, LTX-2.5 audio VAE, and LTX-2.5 text encoder.
Local hardware/model availability remains an acceptance gate rather than an assumption.

The current ComfyUI installation stores the LTX-2.5 models in `ltx2.5` subfolders. The
checked-in manual and provider workflows therefore reference these exact relative model names:

- `diffusion_models/ltx2.5/ltx-2.5-22b-distilled-transformer-bf16.safetensors`
- `vae/ltx2.5/ltx-2.5-audio-vae-bf16.safetensors`
- `vae/ltx2.5/ltx-2.5-video-vae-conv-bf16.safetensors`
- `text_encoders/ltx2.5/gemma4_e2b_it_bf16.safetensors`
- `text_encoders/ltx2.5/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors`

