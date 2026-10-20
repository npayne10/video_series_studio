# VSCS Production Recovery Audit — 20 October 2026

Status: OPEN — GitHub architecture reviewed; actual production project evidence awaiting collection.
Production project: D:\VSCS TSR2 — READ ONLY.
Isolated acceptance project: D:\VSCS TSR2 - TEST 4B5.
Accepted reference baseline: Phase 20.18.2.3.7.5, 2,093 tests passing.

## Safety and scope

Never rerender, retry, approve or replace SHT-003 Generated Media without explicit authorization. Do not publish production revisions, advance tasks, mark Episode complete, or authorize Picture Lock. All source changes are via GitHub and validated in the isolated project first.

## Earlier production state — must be refreshed

- EP-001 had 57 required Shots, 54 planning blocked, 54 without generated media, 1 QC pending and 55 absent from assembly timeline. These are historical, not audited current counts.
- SHT-001 approved record: GM-F95B257D70A88B0B6A769295.
- SHT-002 approved record: GM-APR-A48BFA852AFE4934269E.
- SHT-003 pending QC: GM-H3-006641D56A556A97DA398A3F.
- Original immutable ASM-EP-001 / REV-001 is protected.

## Workstreams

| Priority | Evidence needed | Result |
|---|---|---|
| P0 | Live SHT-003 QC state and operator blockers | Find next human-approved action; no automatic QC |
| P1 | Episode coverage/readiness and Shot blockers | Classify planning data vs software defects |
| P2 | Provider / model route, capacity, generation logs | Identify executable low-cost routes |
| P3 | References and continuity boundaries | Identify missing evidence vs resolver defects |
| P4 | ProductionTask / schedule state | Determine next authorized work item |
| P5 | Timeline and completion blockers | Avoid premature Episode completion |
| Q1 | Real media dimensions, fps, codecs, bitrate | Confirm effective generated quality |
| Q2 | Representative frames and temporal motion | Evaluate blur, softness, identity and flicker |
| Q3 | Actual active provider preset, native decode resolution and upscale stage | Find whether quality intent reaches output |

## Confirmed GitHub code quality settings

src/vscs/application/rendering/quality_profiles.py defines PREVIEW 960x400/24fps sampling effort 1, reference strength 0.8, upscale false; PRODUCTION 1920x800/24fps sampling effort 3, reference strength 1.0, upscale true. These are DECLARED profiles, not evidence that providers used these settings. Assess actual produced media and provider execution before changing them.

## Read-only PowerShell collection

Run outside VSCS; share the output; these commands do not modify the project:

    $project = 'D:\VSCS TSR2'
    Test-Path $project
    Get-ChildItem "$project\.vscs\generated_media" -File -Recurse | Select-Object FullName,Length,LastWriteTime | Select-Object -First 30
    Get-ChildItem "$project\production\scheduling\tasks" -File -Recurse | Measure-Object
    Get-Command ffprobe -ErrorAction SilentlyContinue | Select-Object Name,Source

Obtain the EXACT video path from the QC UI, then inspect individually without modifying source:

    ffprobe -v error -select_streams v:0 -show_entries stream=width,height,avg_frame_rate,nb_frames,codec_name,pix_fmt,bit_rate -show_entries format=duration,bit_rate -of json '<exact-video-path>'

Collect screenshot of EP-001 coverage and task blockers, SHT-003 QC screen (do not approve), selected provider configuration and representative frames. Avoid posting private tokens or large internal databases.

## Quality improvement evaluation proposal (not authorized to run)

On test-only media, compare current generated output against a provider-supported higher native generation resolution, temporal-consistent upscaling, and separately tuned encoding. Evaluate detail, faces, identity continuity, motion artifacts, flicker, VRAM and runtime. Maintain 2.39:1 at 24fps, target credible 1080p-class master and optional 4K output only when real detail supports it. Planning GPU: RTX 5060 Ti 16GB. Merely resizing to 4K does not add native detail.

## Acceptance gate

Audit is complete only when current project state and real media measurements are evidenced, issues are triaged, and user approves the next production action. No previous media approvals or planning decisions are changed by this audit.