# Build and run the VV5 mask sidecar roster-identity harness.
#
# The harness drives the committed companion,
# data/candidates/VVFP VV5 Task9 Origins Icons.dll (built by
# scripts/build_vv5_task9_origins_dll.ps1), over a fake villager array at the
# game's own addresses. It needs those addresses inside its own image, so it is
# linked fixed at 0x400000 (/FIXED /DYNAMICBASE:NO /BASE:0x400000); see the
# comment above g_backing in the harness.
#
# Until this script existed the harness had no build script and nothing ran
# it, so when the companion moved its sidecar into "Virtual Villagers Fun
# Patcher Data\Village Masks - Save <n>.dat" (4c5c2c76) the harness kept
# checking the old path and failed unseen.
# tests/test_vv5_mask_identity_harness.py now runs this script whenever the
# 32-bit MSVC toolchain is installed.
#
# Each run builds into its own folder under %TEMP%, so concurrent runs never
# share an executable or object files. The executable keeps its basename,
# which names its LDW save folder and the harness_ldw_tree.h lock.
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vv5_task9_origins"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"
$companion = Join-Path $projectRoot "data\candidates\VVFP VV5 Task9 Origins Icons.dll"
$outDir = Join-Path $env:TEMP ("vvfp_vv5_mask_identity_harness_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $outDir | Out-Null
$out = Join-Path $outDir "vvfp_vv5_mask_identity_harness.exe"

try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo `
        ("/Fo" + $outDir + "\") `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        (Join-Path $nativeRoot "vv5_mask_identity_harness.c") `
        /link `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        user32.lib `
        shell32.lib `
        /FIXED `
        /DYNAMICBASE:NO `
        /BASE:0x400000 `
        ("/OUT:" + $out)
    if ($LASTEXITCODE -ne 0) { throw "vv5 mask identity harness failed to build" }

    & $out $companion
    if ($LASTEXITCODE -ne 0) { throw "vv5 mask identity harness reported failures" }
}
finally {
    Remove-Item -LiteralPath $outDir -Recurse -Force -ErrorAction SilentlyContinue
}
