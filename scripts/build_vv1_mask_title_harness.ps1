# Build and run the A New Home mask title-screen harness.
#
# native/vv1_origins_icons/vv1_mask_title_harness.c drives the committed
# assets/origins/VVFP VV1 Origins Icons.dll (built by
# scripts/build_vv1_origins_icons.ps1) over a fake villager array at the game's
# own addresses, so it is linked fixed at 0x400000; the DLL's Documents are
# redirected to a throwaway folder under %TEMP%.  Each run builds into its own
# folder under %TEMP%.  An optional argument names another DLL to drive (an
# older build, to show the checks fail on it).
param([string]$Companion = "")
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vv1_origins_icons"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"
if ($Companion -eq "") {
    $Companion = Join-Path $projectRoot "assets\origins\VVFP VV1 Origins Icons.dll"
}
$outDir = Join-Path $env:TEMP ("vvfp_vv1_mask_title_harness_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $outDir | Out-Null
$out = Join-Path $outDir "vvfp_vv1_mask_title_harness.exe"

try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo `
        ("/Fo" + $outDir + "\") `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        (Join-Path $nativeRoot "vv1_mask_title_harness.c") `
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
    if ($LASTEXITCODE -ne 0) { throw "vv1 mask title harness failed to build" }

    & $out $Companion
    if ($LASTEXITCODE -ne 0) { throw "vv1 mask title harness reported failures" }
}
finally {
    Remove-Item -LiteralPath $outDir -Recurse -Force -ErrorAction SilentlyContinue
}
