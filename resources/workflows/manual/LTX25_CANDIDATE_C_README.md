# LTX-2.5 Candidate C — Governed-Keyframe I2V Manual Test

Open:

`ltx25_candidate_c_governed_keyframe_i2v_manual.json`

This is based on the official Lightricks single-stage LTX-2.5 T2V/I2V distilled workflow pinned to
commit `dfb2786749af36f200ea023388dc729a3e106b42`.

Place the approved keyframe in ComfyUI/input as:

`VSCS_SHT001_Governed_Keyframe.png`

The video-stage workflow intentionally does **not** load the James+Sandra combined identity image,
the Xorix reference, or the Iron Horizon bridge reference independently. Those authorities must
already be resolved in the approved keyframe.

Keep the default settings for the first controlled test. Edit only the keyframe if it has not yet
passed human keyframe acceptance.
