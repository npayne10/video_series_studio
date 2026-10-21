# Phase Q3.1.2 — Progressive Ros Reference Reintroduction

Status: source preparation tool and tests committed. Local validation and generation pending.

## Objective

Determine whether the improved 0.35 MP, 56-frame Q3.1 reduced-reference continuity persists when Ros's identity reference is restored. The verified earlier three-reference execution was 124.49 seconds, 800x448 at 24 fps, peak sampled VRAM 15,550 MiB, with 14 cached nodes. Human observation: continuous bridge and no isolated object-image inserts.

## Controlled candidate

- Start from the successful disposable Q3.1 R3 API JSON, not governed TSR2 Shot execution.
- Restore original benchmark node 141 (Ros) as reference slot 3.
- Preserve slots 0 James, 1 Sandra, 2 bridge; retain the frame-zero guide and **do not restore** standalone Xorix reference (node 143).
- Keep 0.35 MP, 56 frames, 24 fps, seed 123456, scheduler and model selections unchanged.
- Prompt now invites Ros to enter the bridge background while maintaining the original frame-zero composition; **prompt and reference set both change**, so this is progressive feasibility testing, not single-variable causal attribution.
- Distinct output prefix: `video/VSCS_H3_Q3_1_2_0p35_R4`.

## Local preparation

    python scripts/prepare_h3_q3_1_2_ros_reintroduction.py --source D:\VSCS-H3-Q3-1\q3_1_0p35_reduced_api.json --original D:\VSCS-H3-Resolution-Benchmark-Ready-v2\h3_0p35_ready_api.json --output D:\VSCS-H3-Q3-1\q3_1_2_0p35_ros_api.json

The script creates a new JSON with exclusive creation, never overwrites, never queues ComfyUI and never modifies the sources. Validate before any explicit generation.

## Validation

    python -m ruff check .
    python -m ruff format --check .
    python -m mypy src
    python -m pytest -q tests/test_h3_q3_1_2_ros_reintroduction.py -v
    python -m pytest -q
    git diff --check

Preflight: all referenced ComfyUI images exist; three original refs + Ros, 4 slots only; node 145 frame-zero; node 143 absent; queue empty; output destination unique; no VSCS production execution active. Render only following an operator's conscious submission.

## Human QC criteria

Observe every frame: single continuous Iron Horizon bridge, James/Sandra stable, Ros's identity/entry credible if depicted, no portraits or planet inserts, no scene changes; compare technical parameters and noncached execution time with Q3.1 R3. Do not auto-approve production. An absence of Ros should not be presented as satisfying the three-character production requirement.

## Governance

No governed TSR2 assets, SHT-003 human QC, ProductionTask, episode state, assembly, or Picture Lock will be changed.
