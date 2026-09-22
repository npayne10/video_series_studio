# Phase 20.18.2.2h — Governed Provider Audio Policy

## Purpose

Phase 20.18.2.2h prevents a joint audio/video generation provider from silently
becoming the authoritative source of dialogue or final soundtrack.

Candidate C may internally generate audio, but VSCS now resolves an explicit provider
audio policy from governed Shot authority and applies that policy before Generated Media
ingestion.

## Policy modes

- `silent_visual` — provider audio is discarded; VSCS owns all later audio.
- `canonical_dialogue` — provider audio is discarded; canonical dialogue remains in the
  VSCS voice/audio pipeline.
- `post_dub` — provider audio is discarded because dialogue is applied later.
- `generated_ambience` — provider audio may be retained only as a non-final source for
  the VSCS mix.
- `fixed_audio_conditioning` — supplied fixed audio remains authoritative conditioning.

If no explicit policy is present, Shots with governed dialogue resolve to
`canonical_dialogue`; Shots without governed dialogue resolve to `silent_visual`.

## Production-package authority

Candidate C Production Packages now contain a schema-versioned
`provider_audio_policy` block. The package is invalid for Phase 20.18.2.2h if that
authority is missing or malformed.

## Completion boundary

Audio governance occurs after provider completion but before Generated Media ingestion.

For discard policies VSCS:

1. keeps the original provider output immutable;
2. removes embedded audio with FFmpeg using video stream copy (`-c:v copy -an`);
3. discards separate provider audio outputs;
4. verifies the governed video contains zero audio streams with FFprobe;
5. stages the governed video under
   `.vscs/provider_executions/audio_governance/<execution-id>/`;
6. ingests the staged video as authoritative Generated Media;
7. records the policy, action, original provider path and stream-copy fact in Generated
   Media provenance.

The same governance hook is used for current-session completion and restart recovery.

## SHT-001 acceptance target

SHT-001 has no governed spoken content, so its default policy is:

```text
mode                       silent_visual
provider_audio_action      discard
authoritative_audio_source vscs_audio_pipeline
```

A Phase 20.18.2.2h acceptance render passes audio governance only when the registered
Generated Media video has no audio stream while its visual bitstream is passed through
without re-encoding.

## Runtime requirements

FFmpeg and FFprobe must be available on PATH, or configured with:

- `VSCS_FFMPEG_EXE`
- `VSCS_FFPROBE_EXE`

Missing or failed audio governance is fail-closed: provider completion does not become
successful authoritative Generated Media.
