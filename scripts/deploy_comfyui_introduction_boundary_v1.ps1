param(
    [string]$ComfyUIRoot = "D:\ComfyUI1\ComfyUI_windows_portable\ComfyUI"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$source = Join-Path $repoRoot "resources\workflows\custom_nodes\vscs_qwen_introduction_boundary_v1.py"
$targetDir = Join-Path $ComfyUIRoot "custom_nodes"
$target = Join-Path $targetDir "vscs_qwen_introduction_boundary_v1.py"

if (-not (Test-Path $source -PathType Leaf)) {
    throw "VSCS automated introduction-boundary custom node source is missing: $source"
}
if (-not (Test-Path $ComfyUIRoot -PathType Container)) {
    throw "ComfyUI root does not exist: $ComfyUIRoot"
}

New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
Copy-Item -Force $source $target

$requiredClasses = @(
    "VSCSIntroductionBoundaryPackageLoaderV1"
)
$installed = Get-Content $target -Raw
foreach ($className in $requiredClasses) {
    if ($installed -notmatch [regex]::Escape($className)) {
        throw "Deployed VSCS custom node is missing required class: $className"
    }
}

Write-Host "Installed Phase 20.18.2.3.6 automated introduction-boundary node:"
foreach ($className in $requiredClasses) {
    Write-Host "  $className"
}
Write-Host "Target:"
Write-Host "  $target"
Write-Host ""
Write-Host "Restart ComfyUI before live automated span validation."
