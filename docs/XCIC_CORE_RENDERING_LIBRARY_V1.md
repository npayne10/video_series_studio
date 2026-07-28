# XCIC Core Rendering Library v1.0

XCIC Core is the single ComfyUI rendering path used by VSCS canonical image generation.
It follows the proven Xorix Studio architecture: compile an editable workflow, validate
installed node classes, write an XCIC queue, patch only the loader node, submit to
ComfyUI, monitor history, and verify the expected PNG.

## Default installation

```text
D:\VSCS\XCIC
```

Place the text-to-image loader workflow at:

```text
D:\VSCS\XCIC\Xorix_Qwen_XCIC_Image_Creator_v1.0.json
```

VSCS creates runtime files under:

```text
D:\VSCS\XCIC\compiled\qwen_xcic_text_to_image_API.json
D:\VSCS\XCIC\queues\xcic_generation_queue.json
```

Generated temporary candidates remain project-controlled:

```text
<Project>\Render Cache\XCIC\<ASSET-ID>\<JOB-ID>\
```

After verification, the CAP application service imports the PNG into:

```text
<Project>\Canonical Assets\<ASSET-ID>\Images\
```

## Loader contract

The compiled workflow must contain exactly one:

```text
XCICQueueJobLoader
```

XCIC Core patches only:

- `queue_file`
- `job_index`
- `quality_mode`

The loader supplies prompt, negative prompt, dimensions, seed, sampler values, output
directory, and filename to the remaining workflow. VSCS does not patch individual Qwen,
model, sampler, or save nodes.

## Validation

Before rendering, XCIC Core:

1. Compiles or sanitises the workflow.
2. Removes editor-only notes and utility nodes.
3. Calls ComfyUI `/object_info`.
4. Rejects missing custom node classes before submission.
5. Writes the queue atomically.
6. Submits `/prompt` and polls `/history/<prompt_id>`.
7. Verifies a non-empty PNG exists before returning success.

## Configuration overrides

```powershell
$env:VSCS_XCIC_ROOT="D:\VSCS\XCIC"
$env:VSCS_COMFYUI_URL="http://127.0.0.1:8188"
$env:VSCS_XCIC_TEXT_WORKFLOW="D:\VSCS\XCIC\Xorix_Qwen_XCIC_Image_Creator_v1.0.json"
```

## Library API

```python
from vscs.infrastructure.xcic_core import (
    XCICCoreClient,
    XCICCoreJob,
    XCICCoreRenderer,
    XCICCoreWorkflow,
)
```

The library is provider-neutral at the application boundary. Future reference-image,
environment, prop, storyboard, and video workflows can use the same renderer by supplying
a different loader class and queue contract.
