param(
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"

# Builds and runs the 32-bit runtime harness for the first-load reconcile of
# the Village Elders and Village Statistics files
# (native/statistics_export/reconcile_harness.c) against the TEST build of
# "VVFP Statistics Export.dll" and the shipped "VVFP Save Reset.dll", which
# the harness copies into "Virtual Villagers Fun Patcher Files" beside itself
# (as in a patched game) under their shipped names, in all five
# games' geometry, on real files under a throwaway save folder named after the
# harness (harness_ldw_tree.h leaves Documents\LDW as it found it).  Linked at
# a fixed base with free memory above it (0x30000000) so it can place each
# game's villager table and memorial where the DLL reads them.  Exit code 0
# means every check passed.  Without -OutDir each run builds into its own
# folder under %TEMP% and removes it afterwards.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\statistics_export"
$sharedRoot = Join-Path $projectRoot "native\shared"
$statisticsTest = Join-Path $projectRoot "tests\test_dlls\VVFP Statistics Export.test.dll"
$saveReset = Join-Path $projectRoot "assets\save_reset\VVFP Save Reset.dll"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

$ownsOutDir = -not $OutDir
if ($ownsOutDir) {
    $OutDir = Join-Path $env:TEMP ("vvfp_reconcile_harness_" + [guid]::NewGuid().ToString("N"))
}
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
Push-Location $OutDir
try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo `
        ("/Fo" + $OutDir + "\") `
        /O2 `
        /MT `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        /I $sharedRoot `
        (Join-Path $nativeRoot "reconcile_harness.c") `
        (Join-Path $sharedRoot "village_identity.c") `
        (Join-Path $sharedRoot "save_folder.c") `
        /link `
        /BASE:0x30000000 `
        /FIXED `
        /DYNAMICBASE:NO `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/OUT:" + (Join-Path $OutDir "reconcile_harness.exe")) `
        kernel32.lib `
        user32.lib `
        shell32.lib
    if ($LASTEXITCODE -ne 0) {
        throw "Reconcile harness compilation failed."
    }
    & (Join-Path $OutDir "reconcile_harness.exe") $statisticsTest $saveReset
    if ($LASTEXITCODE -ne 0) {
        throw "Reconcile harness reported failures."
    }
} finally {
    Pop-Location
    if ($ownsOutDir) {
        Remove-Item -LiteralPath $OutDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
