# MiniMax H3 Resolution Versus Render-Time Benchmark — governed experiment

Status: CONFIGURATION PREPARATION IMPLEMENTED; execution, metrics and production default selection PENDING.

Purpose: Identify the best quality-versus-time operating point on the RTX 5060 Ti 16 GB without generating/replacing any approved project Shot.

## Evidence

- Historical SHT-002 H3 accepted spans: 608x352, 24 fps; both normalized and final video preserved native-sized frames.
- Historical raw ComfyUI outputs are unavailable; cannot prove whether acceptance processing originally rescaled them.
- Repository H3 baseline ResolutionSelector node 115: aspect_ratio 16:9, megapixels 0.2, multiple 32.
- The H3 compiler includes resolution settings in the model configuration fingerprint. Existing media fingerprints/approvals must not be rewritten.

## Controlled candidates

| Phase | Megapixels requested | Rationale |
|---|---:|---|
| Baseline | 0.2 | Current workflow and known low visual quality |
| A | 0.35 | Low-cost improvement |
| B | 0.5 | Mid-range candidate |
| C | 0.8 | Higher-quality test if VRAM permits |
| D | 1.0 | High-res trial only after lower levels succeed |

The node selects actual dimensions on 32-pixel multiples, so ffprobe must measure delivered width/height. Values are requests, not promises of realized resolution. Maintain fixed 24 fps, same prompt, references, guide, duration, seed, model and scheduler throughout. Run at least two repeats per candidate when practical; first repeat may incur model-loading overhead.

## Prepare files (NO execution)

    cd D:\VSCS\video_series_studio
    python scripts/prepare_h3_resolution_benchmark.py --output D:\VSCS-H3-Resolution-Benchmark

Output directory must be new or empty and outside source. This generates test-only workflow JSON variants; it does NOT submit ComfyUI jobs, automatically bind/stage governed reference images, test VRAM, or bypass VSCS approvals. Do not import these variants as governed production jobs. Use the isolated acceptance project and an independently authorized disposable test package to execute them safely after workflow wiring review.

## Stop conditions

- CUDA out-of-memory, fatal VAE failure, invalid frame count, reference identity loss, flicker, silent resizing, unexpected provider fallback or project output collision.
- Do not reduce source clip duration between configurations when recording comparable times. For initial budget safety, use a short disposable test clip of identical frame count across all candidates.
- Do not call a lower quality result production-ready just because it renders faster. No changes to original SHT-001/002 approval, SHT-003 QC, ProductionTasks, Episode assembly or Picture Lock.

## Record measured results

| MP requested | Actual W x H | Frames | GPU peak MB | Warm render sec | sec / frame | Identity /10 | Detail /10 | Temporal stability /10 | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 0.2 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 0.35 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 0.5 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 0.8 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 1.0 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

Measure GPU allocated/used via nvidia-smi or the generation log; note that system GPU usage and PyTorch allocation differ. Timings must separate cold model loading from warm inference when possible. Human-review identity, environment geometry, motion and faces, not just pixel count. Flag any mismatch in aspect ratio from target 2.39:1; 16:9 current workflow is not a cinematic framing guarantee.

## Selection rule

Select the lowest-cost configuration meeting an operator-approved minimum perceptual quality, stable 16 GB runtime and temporal continuity. Plot measured detail/quality against seconds per frame and reject dominated choices. If none qualify, test a post-upscale comparison from a good lower-resolution candidate, but preserve the native result and its provenance. Never infer 1080p/4K native image detail from container dimensions.

## Validation

    python -m ruff check .
    python -m ruff format --check .
    python -m mypy src
    python -m pytest -q tests/test_h3_resolution_benchmark_preparation.py -v
    python -m pytest -q
    git diff --check

Update this table only with actual local benchmarks and explicit operator quality judgment.