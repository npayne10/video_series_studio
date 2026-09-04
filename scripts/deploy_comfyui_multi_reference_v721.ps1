param(
    [string]$ComfyUIRoot = "D:\ComfyUI1\ComfyUI_windows_portable\ComfyUI"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$source = Join-Path $repoRoot "resources\workflows\custom_nodes\vscs_multi_reference_v721.py"
$targetDir = Join-Path $ComfyUIRoot "custom_nodes"
$target = Join-Path $targetDir "vscs_multi_reference_v721.py"

if (-not (Test-Path $source -PathType Leaf)) {
    throw "VSCS multi-reference custom node source is missing: $source"
}
if (-not (Test-Path $ComfyUIRoot -PathType Container)) {
    throw "ComfyUI root does not exist: $ComfyUIRoot"
}

New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
Copy-Item -Force $source $target

Write-Host "Installed VSCSMultiReferenceResolverV721:"
Write-Host "  $target"
Write-Host ""
Write-Host "Restart ComfyUI before live production validation."
