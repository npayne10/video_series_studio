<#
.SYNOPSIS
Install the VSCS XCICQueueJobLoader custom node into an existing ComfyUI installation.
.DESCRIPTION
Installs only the version-controlled VSCS loader into custom_nodes/vscs_xcic.
ComfyUI must be restarted after installation. -VerifyOnly checks the live node registry.
#>
[CmdletBinding()]
param(
    [string]$ComfyUIRoot = "D:\ComfyUI\ComfyUI_windows_portable\ComfyUI",
    [string]$ComfyUIUrl = "http://127.0.0.1:8188",
    [switch]$VerifyOnly
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$source = Join-Path $repoRoot "custom_nodes\vscs_xcic"
$target = Join-Path $ComfyUIRoot "custom_nodes\vscs_xcic"

if (-not $VerifyOnly) {
    if (-not (Test-Path -LiteralPath (Join-Path $ComfyUIRoot "nodes.py"))) {
        throw "ComfyUI root is invalid: $ComfyUIRoot. Specify -ComfyUIRoot explicitly."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $source "xcic_queue_loader.py"))) {
        throw "VSCS custom node source not found: $source"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $source "__init__.py"))) {
        throw "VSCS custom node registration not found: $source"
    }

    New-Item -ItemType Directory -Path $target -Force | Out-Null
    foreach ($name in @("__init__.py", "xcic_queue_loader.py")) {
        Copy-Item -LiteralPath (Join-Path $source $name) -Destination (Join-Path $target $name) -Force
    }

    Write-Host "Installed VSCS XCIC loader at $target" -ForegroundColor Green
    Write-Host "RESTART the running ComfyUI process to load the custom node." -ForegroundColor Yellow
    Write-Host "After restart, run this script again with -VerifyOnly."
    exit 0
}

try {
    $nodes = Invoke-RestMethod -Uri "$($ComfyUIUrl.TrimEnd('/'))/object_info" -TimeoutSec 15
} catch {
    throw "Cannot reach ComfyUI at $ComfyUIUrl. Start ComfyUI and retry: $_"
}
$installed = $nodes.PSObject.Properties.Name
foreach ($name in @(
    "XCICQueueJobLoader",
    "XCICSaveImage",
    "ComfySwitchNode",
    "PrimitiveInt",
    "PrimitiveFloat",
    "PrimitiveBoolean"
)) {
    $status = if ($installed -contains $name) { "INSTALLED" } else { "MISSING" }
    Write-Host "$name : $status"
}
if ($installed -notcontains "XCICQueueJobLoader") {
    throw "XCICQueueJobLoader is still missing. Confirm the ComfyUI startup log loaded $target."
}
Write-Host "VSCS XCIC queue loader is registered successfully." -ForegroundColor Green
