# H3-MF — MiniMax H3 Multi-Frame Reference Workflow: Assessment and Remediation Backlog

**Date:** 2026-11-17  
**Status:** ENGINEERING ASSESSMENT RECORDED; H3-MF1 DEFERRED UNTIL C4B AND THE GOVERNED IMAGE-CORRECTION LOOP ARE COMPLETED. NOT STARTED.  
**Scope:** Supplementary provider capability for Phase 20 (Provider Execution & Generated Media), not a replacement for existing H3 authority or a C4 image-correction provider.

## 1. Evidence and provenance

User-supplied ComfyUI editor workflow:
`video_minimax_h3_multiframe_reference_VSCS(1).json`
(SHA-256 `838098a6eabbb65ebc5a2dcf48daf9820d4e7750f83a8d32624db8cf6c35dcfe`).

**Independently parsed local attachment:** 41 nodes, 53 links.
This is **editor/canvas-format JSON**, not a validated ComfyUI `/prompt`
API payload. The source JSON is not modified by this assessment. Before
H3-MF1 implementation, include a separately approved immutable fixture
or original-source checksum in the offline test suite and ensure no
production graph is overwritten.

**Reference material (verify against installed ComfyUI version):**
- ComfyUI H3 multiframe documentation:
  https://github.com/Comfy-Org/docs/blob/main/tutorials/video/minimax/minimax-h3-multiframe.mdx
- H3 Reference-to-Video node:
  https://github.com/Comfy-Org/docs/blob/main/built-in-nodes/MiniMaxH3ReferenceToVideo.mdx
- H3 Add Guide node:
  https://github.com/Comfy-Org/embedded-docs/blob/main/comfyui_embedded_docs/docs/MiniMaxH3AddGuide/en.md
- Official workflow template:
  https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_minimax_h3_multiframe_reference.json

Do not treat descriptions in `MarkdownNote` nodes as live proof of
capability, file availability, GPU fit, output quality, licensing or
execution.

## 2. Actual graph structure and initial configuration

| ID(s) | ComfyUI component | Observed setting / binding |
|---|---|---|
| 136 | `MiniMaxH3ReferenceToVideo` | `ref_images.ref_image_0` from `LoadImage` 164 only; `ref_image_1` not connected; VAE and audio VAE bound; `ref_image_size=match` |
| 164 | `LoadImage` | `h3_frame_ref_1.png`: semantic `<Picture 1>`, not an Add Guide at frame 0 |
| 147, 162, 169 | Chained `MiniMaxH3AddGuide` | Images from `LoadImage` 157, 159, 167; conditioning chained 136→147→162→169→126 |
| 154/153, 160/161, 168/170 | Guide indices | 1.5 s→36; 3.0 s→72; 5.0 s→120 frames at 24 fps |
| 132→131 | Duration expression | input 5 s; `max(5,round(a*24))+(5-(max(5,round(a*24)) % 17))%17` yields 124 frames |
| 115 | `ResolutionSelector` | 16:9, 0.4 MP, multiple 32; expected ~864 × 480, not an observed rendered resolution |
| 129 | `RandomNoise` | seed initially `148096032077131`, set to randomize after generation; nondeterministic reruns |
| 123,124,141,142,145,146 | Sampling settings | `res_multistep`, `simple`, 20 steps; Turbo LoRA switch false (four-step path present but disabled) |
| 122,121,130,92 | Decode/create/save | Video + audio decode → `CreateVideo` 24 fps → `SaveVideo`; not a governed GeneratedMedia registration |

**Configured length 124 frames / 24 fps ≈ 5.17 seconds.**
The final guide at frame 120 has only four subsequent frame positions
within this configuration. A last-minute vignette with meaningful
motion and an ending hold is therefore not supported by its timing.

The prompt's `subject_definitions`, `summary`, `retention_analysis`,
`detailed_description`, `overall_soundscape` and
`non_diegetic_music` describe four separate editorial mini-scenes.
Those `[Shot N]` labels are prompt text, **not** four VSCS-approved
Production Shots.

## 3. Required source-workflow corrections and integration gates

| Priority | Finding in attachment | Required correction / verification |
|---|---|---|
| P0 | Prompt uses `<Picture 2>`, `<Picture 3>`, `<Picture 4>` but only Picture 1 is in H3 `ref_images` | Separate **semantic-reference registry** from **timed-guide registry**. Either explicitly wire images 2–4 as semantic references, in verified order and within provider capacity, **or** change prompt references to correctly describe frame guides without claiming they have `<Picture N>` binding. Verify resulting token/reference cost. |
| P0 | Picture 1 is a semantic reference but no explicit guide at frame zero | For continuity-critical Shots, evaluate an approved opening-boundary image wired to `MiniMaxH3AddGuide(frame_idx=0)` or an equivalent provider-supported first-frame authority. Do not assume prompt-only first-frame fidelity; test outcome against approved opening. |
| P0 | Final guide occurs at frame 120 in a 124-frame sample | Move last guide earlier or increase duration within validated bounds; require minimum usable post-guide frames, prevent any guide clip overrun, enforce sorted/non-conflicting guide indices, and evaluate the motion/hold after each guide. |
| P0 | Workflow is editor JSON, not safe `/prompt` API graph | Build offline import→validated API compilation, schema checks, link/type checks, exact model/node inventory, SHA-pinned graph and source references. Never submit raw editor JSON or silently replace the existing production H3 workflow. |
| P0 | Direct `SaveVideo` bypasses VSCS output authority | Compile into a **disposable**, isolated output plan. For any future approved run, enforce once-only execution claim, output integrity and ffprobe frames/fps, GeneratedMedia lineage, QC and explicit human acceptance. Do not auto-approve any media. |
| P0 | No confirmed 16 GiB VRAM or 15–20-second viability | Use non-generating model inventory and memory preflight first. Official reference node documents ~124–362-frame trained range (~5–15 seconds at 24 fps); 20 s maps to 481 frames but is **not established as reliable**. For 20-second Shots, plan governed continuation/spans until independently qualified. |
| P1 | Seed randomizes after each generation | Freeze deterministic seed for A/B benchmarks, record workflow/model hashes, sampler, steps, resolution and run settings. Restore flexible seeds only through a governed per-take decision. |
| P1 | Long fashion montage mixes cut transitions, identity, clothing, audio and four compositions | Start with a single continuous 5-second isolated scene with approved source and two timed guides, then separately test multi-cut storytelling, subjects and audio. |
| P1 | Audio VAE participates in generation | Inspect audio presence/codec, sync, unwanted speech/music and reproduction rights; no assumption that video/audio soundscape text produces production-ready tracks. |
| P1 | `match` reference sizing and optional Turbo path unqualified | Compare image sizing `match` vs `max`, 20-step baseline vs four-step LoRA only after basic continuity, quality, time, VRAM and identity fidelity are measured. |
| P1 | Guide anchor might be approximate, and reference identity may drift | Measure image-guide similarity at each frame index, temporal stability before/after anchor, person/object counts, identity, approved CAP elements, and continuity with prior/next Shot. |
| P1 | Provider input caps and file/provenance assumptions not enforced by this editor graph | Compile image/video/audio references according to installed node schema; validate counts, filenames, SHA-256, duration, frame-rate and saved CAP/reference authority. |
| P2 | Multi-frame UX requires manual ComfyUI node duplication | If benchmarks pass, provide VSCS-managed per-Shot keyframe timeline and automatic graph compilation, including safe preview and editable planning evidence. |

**Calculation:** valid H3 frame lengths use `5 + 17n` in this
workflow (e.g. 5s→124, 10s→243, 15s→362, 20s→481 frames).
Do **not** equate acceptance of the integer frame grid with acceptance
of 20-second model quality. A guide clip must fit entirely within the
output frame count; time-to-frame conversion must avoid accidental
out-of-range or unsupported guide lengths.

## 4. VSCS architecture compatibility

Preserve and reuse:
- Approved CAP and immutable canonical-reference identities,
  `ReferencePlan`, reference role/capacity resolution, source hashes.
- `GovernedShotKeyframe` / `GovernedShotBoundaryStore` and
  explicit continuity authority; a temporal guide cannot silently
  override or impersonate an approved opening/closing frame.
- Timed canonical-reference activation and provider temporal-span
  governance, including narrative beat and Shot-boundary time axes.
- Existing MiniMax H3 provider/adapter selection and GeneratedMedia
  output registration/QC; do not fork a separate approval system.
- Existing 15–20-second Shot production policy; handle a real Shot
  containing multiple guided **beats** without silently converting
  prompt `[Shot N]` text into VSCS Shot identifiers.

H3 multi-frame guidance is a candidate **Phase 20 provider capability**.
It is NOT the accepted F5.4.2 C4A masked *still-image correction*
provider and does not unlock Candidate 4's protected Attempt 2/2.

## 5. Prioritized backlog and acceptance criteria

| Task ID | Work item | Deliverable | Exit gate |
|---|---|---|---|
| **H3-MF1** | **Offline multi-frame qualification (DEFERRED)** | Immutable fixture; schema/node and capacity checks; editor→API graph compiler design/prototype; ref/guide separation; frame-index/duration/sequence validation; negative/fail-closed tests; baseline comparison to current H3 provider | Windows Ruff, Mypy, focused/full pytest; offline operator inspection; **no ComfyUI POST/GPU/cost** |
| **H3-MF2** | Explicitly consented disposable GPU A/B | Controlled fixed-seed ref-only vs multi-guide tests at 608×352, then 864×480 if safe; record system/VRAM, runtime and output hashes | Separate operator authorization; zero production-state mutation; no paid provider |
| **H3-MF3** | Continuity, guide-fidelity and audio QC | Exact guide-frame comparison and adjacent-window stability, identity/scene continuity, frame count and audio QC metrics | Human-reviewed evidence and repeatable benchmark thresholds before use |
| **H3-MF4** | Governed VSCS H3 multi-frame production mode | Reuse ProductionTask, boundary authority, provider plan, once-only claim, GeneratedMedia registration and review | End-to-end disposable Shot and failure/recovery acceptance; distinct production approval |

**Priority decision 2026-11-17:** Finish C4B isolated masked-Qwen qualification, then the remaining governed still-image correction steps and end-to-end acceptance **before** beginning H3-MF1. This preserves the existing backlog without diverting current development.

**Within the H3-MF workstream:** H3-MF1 may proceed as an isolated provider
qualification only after the image-correction priority is completed and the owner authorizes it. MF2 must NOT start
automatically after MF1, because it loads models/runs GPU jobs.
MF3 depends on MF2 outputs. MF4 depends on MF1–MF3 acceptance.
No production H3 provider default, CAP, Canon/MASTER, approved
GeneratedMedia, SHT-003 or live project state is changed.

## 6. Acceptance checklist for H3-MF1

1. Confirm the uploaded editor JSON SHA-256 above and preserve
   the baseline unmodified; compare with the official upstream
   template revision and record differences without assuming
   they are identical.
2. Parse and validate all 41 nodes / 53 links and required
   `MiniMaxH3ReferenceToVideo`, three ordered
   `MiniMaxH3AddGuide`, `BasicGuider`, video and audio
   decoding node schemas; reject malformed/missing links.
3. Explicitly produce an ordered semantic-reference map and
   independently ordered timed-guide map; reject undefined
   `<Picture N>` tags, silent reordering and conflicting
   source/guide identity.
4. Validate frame grid, FPS, output start/closing authority,
   guide index bounds and any guide clip duration; reject
   frame-120/124 placement as unsuitable for a nonzero
   closing hold under our Shot contract.
5. Check ComfyUI model/node readiness using offline artifact
   inventory or optional explicit **GET-only** capability
   inspection; never trigger inferencing or reserve a job.
6. Create deterministic API-format graph compilation
   validation against existing H3 provider behavior and
   QA/governance contracts; require no implicit
   `SaveVideo` adoption of generated media.
7. Add fail-closed Python tests for missing images, incorrect
   hashes, undefined tags, guide overrun, 20-second duration
   over trained range, missing model, incompatible nodes and
   stale reference/boundary evidence.
8. Update both VSCS User Manual documents with precise
   Windows startup, offline acceptance steps and clear
   “not production authorized” constraints; run Ruff,
   Ruff formatting, Mypy, focused/full pytest and
   `git diff --check` from the GitHub branch.

**Decision:** Keep the workflow as a research candidate until
offline H3-MF1 qualification is approved. The original supplied
workflow must not be used as a governed VSCS production graph
in its current form.
