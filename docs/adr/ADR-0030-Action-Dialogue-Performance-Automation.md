# ADR-0030 — Action, Dialogue & Performance Automation

## Status
Accepted for Phase 19.5.6 implementation.

## Decision
Phase 19.5.6 may semantically expand current Shot proposals into reviewable Action, Dialogue & Performance proposals. It must reuse the Phase 19.4.2 ActionPerformanceDraft contract fields: temporal narrative, spoken content, performance direction, opening state, closing state and timing notes.

AutomationProposal is the only persistence authority for Phase 19.5.6 output. The automation service must not call ActionPerformanceCompilerService.create_from_current_package(), save(), mark_ready() or compile().

AI may interpret pacing, delivery, reaction and supported dialogue, but may not invent unsupported story facts or decide camera, lighting, canonical assets, voices, renderer prompts or provider settings.

Every proposal retains Story revision provenance and parent Shot proposal lineage. A changed Story revision requires new current Shot proposals before Action/Performance automation may proceed.

Human review remains mandatory. Proposal generation is not acceptance, Ready state, compilation or production approval.
