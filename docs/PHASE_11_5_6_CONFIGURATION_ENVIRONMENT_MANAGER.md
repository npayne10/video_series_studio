# Phase 11.5.6 — VSCS Configuration & Environment Manager

VSCS now owns its runtime configuration instead of relying on manually maintained Windows environment variables.

## Default locations

- Workspace: `D:\VSCS`
- Settings: `D:\VSCS\config\settings.yaml`
- XCIC: `D:\VSCS\XCIC`
- Projects: `D:\VSCS\Projects`
- Logs: `D:\VSCS\Logs`
- Cache: `D:\VSCS\Cache`
- ComfyUI: `http://127.0.0.1:8188`
- Text-to-image workflow: `D:\VSCS\XCIC\Xorix_Qwen_XCIC_Image_Creator_v1.0_api.json`

## Startup behaviour

At application startup VSCS:

1. Loads and validates `settings.yaml`.
2. Creates required workspace folders.
3. Publishes the configured values into the current process environment.
4. Overwrites stale inherited XCIC variables for the current process.
5. Validates the XCIC folder and loader-based API workflow.
6. Shows an actionable warning when rendering configuration is incomplete.
7. Registers the Environment Manager as an application service.

The environment variables are process-local. VSCS does not modify the user's permanent Windows environment.

## Configuration schema

The `environment` section supports:

```yaml
environment:
  workspace_root: D:\VSCS
  config_root: D:\VSCS\config
  projects_root: D:\VSCS\Projects
  logs_root: D:\VSCS\Logs
  cache_root: D:\VSCS\Cache
  xcic_root: D:\VSCS\XCIC
  comfyui_url: http://127.0.0.1:8188
  xcic_text_workflow: Xorix_Qwen_XCIC_Image_Creator_v1.0_api.json
  xcic_reference_workflow: null
  validate_on_startup: true
  developer_mode: false
```

Paths stored relative to `xcic_root` are resolved automatically. Absolute paths remain supported.

## Compatibility overrides

Development or deployment scripts may still use:

- `VSCS_SETTINGS_FILE`
- `VSCS_XCIC_ROOT`
- `VSCS_COMFYUI_URL`
- `VSCS_XCIC_TEXT_WORKFLOW`

After settings load, application-owned values become authoritative for the running VSCS process.
