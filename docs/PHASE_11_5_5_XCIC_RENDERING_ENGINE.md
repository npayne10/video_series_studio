# Phase 11.5.5 — XCIC Rendering Engine Integration

Phase 11.5.5 replaces the Phase 11.5.4 SVG preview output with real Qwen image generation through XCIC and the ComfyUI HTTP API.

## Runtime architecture

1. The CAP editor creates a validated canonical generation request.
2. `XCICImageProvider` creates one XCIC queue job per requested variation.
3. The queue is written atomically to `<project>/XCIC/Queues/xcic_generation_queue.json`.
4. `ComfyUIClient` submits the configured API-format workflow to ComfyUI.
5. The XCIC custom loader reads the queue and the Qwen workflow creates PNG candidates.
6. VSCS waits for the candidate files, imports them into the CAP gallery, writes provenance, and marks them Candidate.

## Required ComfyUI preparation

The workflow supplied in the ComfyUI editor is a UI workflow. ComfyUI's `/prompt` endpoint requires an **API-format workflow**.

Open `Xorix_Qwen_XCIC_Image_Creator_v1.0.json` in ComfyUI and export it using **Save (API Format)**. Store the result at:

```text
<project>/XCIC/Workflows/Xorix_Qwen_XCIC_Image_Creator_v1.0_api.json
```

In that exported workflow, configure `XCICQueueJobLoader.queue_file` to:

```text
<project>/XCIC/Queues/xcic_generation_queue.json
```

The XCIC save node must use the `candidate_directory` and `candidate_filename` outputs supplied by the queue loader.

## Configuration

The defaults can be overridden with environment variables:

```text
VSCS_COMFYUI_URL=http://127.0.0.1:8188
VSCS_XCIC_TEXT_WORKFLOW=D:\Path\To\Xorix_Qwen_XCIC_Image_Creator_v1.0_api.json
```

## Required models

The supplied Qwen text-to-image workflow uses:

- `qwen_image_2512_fp8_e4m3fn.safetensors`
- `qwen_2.5_vl_7b_fp8_scaled.safetensors`
- `qwen_image_vae.safetensors`
- `Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors`

The workflow currently runs in turbo mode with four steps and CFG 1.0. The generation dialog defaults to the workflow's 16:9 Qwen resolution of 1664 × 928.

## Failure behaviour

VSCS reports a clear error when:

- ComfyUI is not running;
- the API workflow is missing or is not valid JSON;
- ComfyUI rejects or fails the prompt;
- generation times out; or
- the expected XCIC output PNG is not created.

No blank SVG fallback is silently produced. A failed real render remains a failed render.
