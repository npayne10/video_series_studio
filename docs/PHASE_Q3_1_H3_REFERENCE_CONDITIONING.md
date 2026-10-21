# Phase Q3.1 — H3 Reference Conditioning & Resolution Optimization

Status: static diagnosis and tooling committed; local validation and any new render pending.

## Evidence

- 0.20 MP: 608x352, 56 frames, 24 fps, 83.190 seconds, peak sampled GPU memory 15,700 MiB.
- 0.35 MP: 800x448, 56 frames, 24 fps, 147.526 seconds, peak sampled GPU memory 15,557 MiB.
- 0.35 MP original rendering prompt: 7e8a8c07-5a95-4c45-bd16-317285f7f164. Later cached submission c46af322-05b5-4863-82e4-5c6c8ba3f5e9 took 0.016 seconds and MUST NOT be used as a render-time measurement.
- The 0.35 MP clip shows apparent isolated character/planet reference frames in the sampled visual review; detailed temporal root cause is NOT established. Comparing 56 sequential frames and guide/reference behavior is the next research step.
- Production compiler ref2va path at `minimax_h3_comfyui_provider.py` assigns 5 reference slots and a single frame-0 guide; removes nodes 146 and 147; sets exact provider length on node 136 and removes duration nodes 131 and 132. The disposable benchmark currently uses an expression in node 131 instead. Do not mistake benchmark implementation for governed production path.
- The static reference inputs in the test use historical approved assets copied under test-only filenames; original approval status is unchanged.

## Implementation in this phase

Run `python scripts/audit_h3_reference_conditioning.py --workflow-dir D:\VSCS-H3-Resolution-Benchmark-Ready-v2`.

The audit displays reference slot ordering, frame-0 guide wiring, seed, prompt digest, model length source and every differing node between 0.20/0.35 MP workflows. It is read-only and sends no generation request.

## Interpretation criteria

1. If only resolution node 115 and output prefix node 92 differ, there is no evidence of changed *static* guide/reference bindings. That **does not** prove the model's video contents should be identical.
2. Changing output resolution changes model sampling and can change composition; a fixed seed does not guarantee identical outputs at different sizes.
3. An 800x448 encoded file does not prove that the model produced high-quality coherent detail.
4. Existing 0.20 vs 0.35 MP time comparison is useful but not an exactly matched cold/warm benchmark: 0.35 execution cached 16 nodes; repeat timing needed before selecting a default.
5. Do not advance to 0.50 MP or alter the production preset pending shot-by-shot human review and reference-conditioning hypothesis.

## Next hypothesis-driven test (requires explicit authorization before rendering)

- First inspect representative frames at fixed timestamps in both clips, paying attention to transitions to portrait/planet references.
- Review image input proportions and guide frame content without altering any originals.
- Investigate controlled single-reference/group-reference alternative, if evidence justifies it. Change only one conditioning variable, isolate outputs, retain same seed/prompt/frame count.
- Measure temporal consistency and visual identity, then consider 0.35 MP repeat and subsequent 0.50 MP study.

## Governance

No production Shot regeneration, media QC, production task edit, episode completion, picture lock, or assembly publication is authorized by Q3.1. All work is read-only/source-only until human approves a disposable test job.
