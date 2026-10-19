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

## Checkpoint 2 — Continuous sequential Qt playback (operator preview)

The verified preview enables an embedded Qt Multimedia QVideoWidget and
QMediaPlayer with Play, Pause, Stop, frame-indexed seek slider and active
Shot/media indicator. `map_timeline_frame` maps cumulative timeline
frames to approved source positions. Each new Shot is opened from its
original project file (no intermediates or source writes); when playback
reaches the exclusive source-out boundary it switches to the next verified
Shot. Playback stops at the last segment. All controls are disabled until
the complete preview is verified; changing the selected persisted
revision invalidates the playback plan and stops the player.

Important: Qt media decoder seeking and file switching are asynchronous.
This is operator-grade approximate real-time preview, **not frame-exact
playback**. Decoder latency or missing codec support can introduce gaps;
frame-accurate first/last-frame boundary review follows in Checkpoint 3.
No Picture Lock, Shot QC or Episode completion is authorized by playback.

### Local acceptance (isolated project only)

1. Run static Ruff/mypy checks and full regressions.
2. Open `D:\\VSCS TSR2 - TEST 4B5` (never production TSR2).
3. Select `ASM-EP-001 / REV-002-ACCEPTANCE`, inspect and verify playback
   readiness. Expect 2 Shots, source ranges [0,24) and [0,144).
4. Confirm video and seek controls enable only after successful validation.
5. Play and observe SHT-001 then SHT-002. Verify Shot identity changes.
6. Pause/resume, seek within each Shot and across the boundary, then Stop.
7. Select a different persisted revision: old playback must stop and require
   a new Verify action. Confirm completion stays disabled.
8. If Qt decoder cannot play media, report the exact error; do not weaken
   checksum/approval validation or copy media outside the project.

Focus:
```powershell
python -m pytest -q tests/test_phase_20_18_2_3_7_5_checkpoint2_playback.py -v
python -m pytest -q tests/test_phase_20_18_2_3_7_5_preview_readiness.py -v
python -m pytest -q
```

## Checkpoint 3 — Boundary & Continuity Inspection

Under the verified preview player, the **Boundary & Continuity Inspection —
Read Only** panel lists adjacent approved Shot pairs. After **Verify Selected
Revision for Playback** completes successfully, select a boundary and press
**Inspect Verified Boundary Frames** to inspect the exact last included
frame (source-out exclusive minus one) alongside the next Shot's first
included source frame.

The service uses installed FFmpeg to select one numbered decoded frame
per approved source and return PNG data in memory. It does not concatenate,
render an assembly, edit source media, change QC approval, or authorize
Picture Lock. Invalid frame ranges, non-adjacent Shot positions, or failed
decoding display **BLOCKED** and clear displayed images. Only a fully verified
assembly preview may expose boundary inspection.

The operator can enter continuity observations; these are **session-only
notes**, keyed by revision fingerprint and boundary. They are not yet a
persisted governed review record and are not used for automatic continuity
approval. Persisting review findings requires a separately specified audit
workflow; do not treat notes as Shot QC.

### Controlled acceptance

- Use `D:\\VSCS TSR2 - TEST 4B5`, never production TSR2.
- Inspect `ASM-EP-001 / REV-002-ACCEPTANCE` and verify source integrity.
- Select SHT-001 → SHT-002; inspect outgoing source frame **23** and
  incoming source frame **0**; verify both images display.
- Type an observation and switch to a different revision; controls must
  block until it is separately verified. Neither revision nor media approval
  may be modified.
- Verify Episode completion and Picture Lock remain disabled.
- Run focused and full pytest after Ruff/mypy validation.

```powershell
python -m ruff check .
python -m ruff format --check .
python -m mypy src
git diff --check
python -m pytest -q tests/test_phase_20_18_2_3_7_5_checkpoint3_boundaries.py -v
python -m pytest -q
```

## Checkpoint 4 — Persisted Revision A/B Comparison (read-only)

Episode Assembly includes independent Revision A and Revision B selectors
populated from the validated persisted timeline repository. Click
**Compare Revisions — Read Only** to display per-Shot ADDED, REMOVED,
UNCHANGED, ORDER, RANGE, and MEDIA/EVIDENCE changes, original source
in/out frame ranges, Generated Media IDs and sequence indexes.
The summary reports immutable revision fingerprints, total frames, durations
and signed differences. The algorithm rejects comparisons across different
assemblies, authoritative scopes or frame rates, and rejects identical
revision fingerprints. It does **not** modify the currently inspected
revision or playback plan; it does not verify either revision for playback.
Video source visualization remains within the separately governed Preview
and Boundary Inspector controls and is not implicit in comparison.

**Acceptance:** in isolated project `D:\\VSCS TSR2 - TEST 4B5`,
discover revisions, choose A `REV-001`, B `REV-002-ACCEPTANCE`,
then compare. Expect SHT-001 source range changes (A → B), and SHT-002
unchanged. Do not assume A's frame range or total duration without
inspecting the persisted immutable records. Confirm comparison keeps
the inspected revision and all Shot/QC/Picture Lock states unchanged.
Select the same revision twice and expect BLOCKED. Swap A and B to check
signed duration difference reverses.

Run:
```powershell
python -m ruff check .
python -m ruff format --check .
python -m mypy src
git diff --check
python -m pytest -q tests/test_phase_20_18_2_3_7_5_checkpoint4_comparison.py -v
python -m pytest -q
```
