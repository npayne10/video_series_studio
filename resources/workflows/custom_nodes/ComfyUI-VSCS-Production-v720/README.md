# ComfyUI-VSCS-Production-v720

VSCS-owned ComfyUI custom nodes for Video Production Engine v7.2.x.

## Install

Copy this entire `ComfyUI-VSCS-Production-v720` folder into your ComfyUI `custom_nodes` directory, then restart ComfyUI.

The installation must expose these node classes:

- `VSCSProductionPackageLoaderV720`
- `VSCSReferenceResolverV720`

The checked-in `ltx23_production_v1_api.json` workflow intentionally keeps the production-package path blank. VSCS supplies the compiled package path when the provider job is submitted.

This source is retained with VSCS so the workflow/custom-node contract used by Phase 20.18.2 is reproducible and can be audited alongside the provider manifest.
