# Phase 20.18.2.3.7.5 — Governed Timeline Playback & Assembly Preview

## Checkpoint 1 — Read-only verified assembly preview foundation

Episode Assembly now exposes **Governed Assembly Preview — Read Only**
for the currently inspected immutable revision. Its Verify button loads
the persisted selections, applies the existing real-media approval/bytes
validator, checks recorded media identities and human approval-event
fingerprints, and probes actual decoded frame count and frame rate using
the already-installed ffprobe metadata inspector.

For each selected Shot the preview displays media ID, source in/out
half-open frame interval and cumulative timeline position. It rejects
out-of-bounds source ranges and rate mismatches, rather than inventing
frames, resampling or silently accepting a truncated source. Blockers
prevent verified-readiness status. A partial Draft can have a valid
read-only preview while overall Episode completion remains blocked.

This checkpoint **does not render, concatenate, play or alter video**.
It neither changes QC/approval states nor authorizes Picture Lock,
Episode completion or ProductionTask transition. Actual video playback,
frame-boundary inspection, revision A/B comparison, audio readiness,
and optional non-destructive assembly rendering are subsequent
checkpoints, not claims of this foundation.

### Local static and regression gates

```powershell
python -m ruff check .
python -m ruff format --check .
python -m mypy src
git diff --check
python -m pytest -q tests/test_phase_20_18_2_3_7_5_preview_readiness.py -v
python -m pytest -q
```

Use `D:\\VSCS TSR2 - TEST 4B5` for UI acceptance. Select
`ASM-EP-001 / REV-002-ACCEPTANCE`, then click
**Verify Selected Revision for Playback**. Expected: two verified
segments representing SHT-001 [0,24) and SHT-002 [0,144), with cumulative
timeline ranges [0,24), [24,168), assuming source frame rates match
24 fps. If rate/byte/approval evidence disagrees, expect **BLOCKED**:
do not bypass validation. Verify the original REV-001 and production
TSR2 remain unchanged and Episode completion remains disabled.
