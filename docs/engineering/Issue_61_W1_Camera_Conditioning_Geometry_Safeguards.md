# Issue #61 W1 — Camera Conditioning and Canonical Geometry Safeguards

**Status:** GitHub implementation; real Rear/Left/Right GPU comparison and visual acceptance pending. No additional generation or protected-file mutation is authorized by this document.

## Evidence and decision

The first qualified Front was independently approved. The subsequent Rear image failed strict perpendicular orientation and displayed rear access panels, vents and other details not verified by the approved front-biased MASTER. These are **two different** findings: camera-pose compliance and absent canonical evidence.

The reviewed Qwen API template fed the `CameraAngle` node's string output to the positive encoder but left its negative encoder prompt empty. The separately compiled queue's full canonical positive and negative text existed only as audit JSON, not as the positive/negative encoder inputs. Consequently, the submitted model was not demonstrably receiving the full CAP preservation instructions.

## Correction

1. Keep the original reviewed template and its SHA-256 unchanged; compile changes **only** into a per-qualification in-memory runtime graph.
2. Supply a literal combined positive string directly to `TextEncodeQwenImageEditPlus` (`219:151`): the LoRA `<sks>` camera phrase for the requested cardinal view **plus** the existing CAP scene-isolated canonical identity prompt and an explicit unseen-geometry caution. This avoids depending on a custom string-concatenation node absent from the known provider inventory.
3. Connect the CAP negative preservation prompt to negative encoder `219:149` instead of leaving it empty. The queue audit strings match these exact compiled encoder strings.
4. Retain the `CameraAngle` numeric node configuration as inspectable provenance of the intended azimuth; its output is no longer relied on for Qwen conditioning. The actual runtime camera control is the explicit LoRA camera phrase.
5. Qualified Rear/Left/Right Candidates are **not** eligible for governed approval without a substantive, recorded human `CANONICAL GEOMETRY REVIEW` attestation documenting what approved design source establishes newly visible surfaces. A separate gallery dialog explains this boundary. The backend enforces it before mutating either approval store. The old approved Front is unaffected.
6. Automatic or advisory AI QC cannot establish unknown hidden details as canonical. The attestation records the operator's claim; it does not independently verify the cited source. If evidence does not exist, reject or retain the view as Candidate.

## Offline acceptance

- Four cardinal views compile deterministic `<sks>` prompts and verified CAP text into positive conditioning, and negative preservation constraints into negative conditioning.
- A qualified Rear Candidate cannot be approved with an empty or minimal geometry review note; its Candidate state remains intact on refusal.
- A substantial operator attestation allows the existing governed approval/lock lifecycle; no automatic approval occurs.
- The MASTER file, reviewed API template, current approved Front and rejected historical references are untouched.

## Next controlled comparison (separate GPU authorization)

1. Confirm the prior failed Rear is rejected with the observed viewpoint and unverified-geometry reasons.
2. Confirm protected MASTER and historical file digests are unchanged.
3. Qualify **one new Rear** view in the disposable project using a new seed/ID only after distinct GPU consent. Record elapsed time, VRAM, prompt ID and output SHA.
4. Assess separately: (a) rear azimuth/perpendicular orientation, (b) exact identity and approved evidence for unknown rear components. A visually straight Rear cannot pass canonical identity by camera alignment alone.
5. Do not approve any Rear view until independent design evidence is available and documented in the new geometry review dialog. Continue with Left/Right only after reviewing the Rear outcome.

**Production boundary:** W1 is not finally accepted until Windows persistence/restart, protected-asset hashes, reference library agreement, and human visual QC pass. PR #66 remains Draft; no automatic merging or GPU execution.
