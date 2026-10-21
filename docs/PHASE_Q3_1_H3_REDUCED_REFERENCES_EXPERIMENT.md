# Q3.1 Corrective Experiment — Reduced H3 Reference Conditioning

Status: candidate generator + regression test committed; local validation and rendering PENDING.

The existing 0.35 MP video rendered at 800x448, 56 frames, 24 fps, in 147.526 sec (original prompt ID 7e8a8c07-5a95-4c45-bd16-317285f7f164). A subsequent all-cached execution is not a timing benchmark.

## Hypothesis

Static five-picture conditioning may cause standalone reference imagery to appear in generated frames. The frame-zero guide depicts James, Sandra, a bridge, and a forward planet view, without Ros. To test a simpler task, the candidate retains references for James (node 137), Sandra (139), bridge (142), and original guide (145); removes Ros (141), planet (143), and compacts reference indices. It also rewrites the prompt to match the intentionally narrower two-person scene. **This changes both the reference set AND prompt**: it is a feasibility/conditioning diagnostic, NOT a controlled measurement of reference count alone. A later paired experiment isolating one variable will be required for causal attribution.

## Safe preparation

    cd D:\VSCS\video_series_studio
    python scripts/prepare_h3_q3_1_reduced_references.py --source D:\VSCS-H3-Resolution-Benchmark-Ready-v2\h3_0p35_ready_api.json --output D:\VSCS-H3-Q3-1\q3_1_0p35_reduced_api.json

Only a new workflow JSON is written. The script does not submit to ComfyUI, change approved originals, clear queues/caches, or advance production QC. It refuses to overwrite a prior candidate. Node 115 remains 0.35 MP, frame length 56, FPS 24, frame-zero guide 145, seed unchanged and output prefix distinct.

## Mandatory preflight before operator-triggered test

- Inspect generated JSON: only three active reference slots (137,139,142), no nodes 141/143 or dangling references; guide 145 at frame zero.
- Confirm ComfyUI API healthy and queue empty, input files available, no running VSCS production job, output prefix video/VSCS_H3_Q3_1_0p35_R3 absent or safely unique.
- No render without explicit operator authorization; benchmark may use nearly all 16 GB VRAM.
- Record unique prompt ID, noncached execution_start/execution_success, peak sampled VRAM, actual ffprobe data, and original output filename.
- Compare complete 56-frame sequence for portrait inserts, spatial coherence, faces, bridge stability, planetary view. Have human evaluate before calling it a quality success.
- Do not advance to 0.50 MP until continuity and runtime costs are understood.

## Checks

    python -m ruff check .
    python -m ruff format --check .
    python -m mypy src
    python -m pytest -q tests/test_h3_q3_1_reduced_references.py -v
    python -m pytest -q
    git diff --check

This is a disposable diagnostic workflow. Original Shot approvals, SHT-003 pending QC, project tasks, EP-001 assembly, picture lock and production media remain unchanged.
