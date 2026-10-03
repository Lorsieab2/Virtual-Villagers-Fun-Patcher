param(
    [string]$OutDir = (Join-Path $env:TEMP "vvfp_death_log_harness")
)

$ErrorActionPreference = "Stop"

# Builds and runs the 32-bit runtime harness for the Deaths log
# (native/parentage_export/death_log_harness.c) against the shipped
# "VVFP Parentage Export.dll", in all five games' record geometry, on real
# files under a throwaway save folder named after the harness, which it
# empties before and removes after. The DLL reads each game's villager table
# at a fixed offset from the executable's base, so the harness is linked at a
# fixed base with free memory above it (0x30000000; the low addresses the
# games use are taken by the harness process's own heap) and places its
# tables at those offsets. Exit code 0 means every check passed. The harness executable is
# left in -OutDir, never in the repository.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\parentage_export"
$sharedRoot = Join-Path $projectRoot "native\shared"
$dll = Join-Path $projectRoot "assets\parentage\VVFP Parentage Export.dll"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
Push-Location $OutDir
try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo `
        /O2 `
        /MT `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        /I $sharedRoot `
        (Join-Path $nativeRoot "death_log_harness.c") `
        (Join-Path $sharedRoot "village_identity.c") `
        (Join-Path $sharedRoot "save_reset.c") `
        (Join-Path $sharedRoot "save_folder.c") `
        /link `
        /BASE:0x30000000 `
        /FIXED `
        /DYNAMICBASE:NO `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/OUT:" + (Join-Path $OutDir "death_log_harness.exe")) `
        kernel32.lib `
        user32.lib `
        shell32.lib
    if ($LASTEXITCODE -ne 0) {
        throw "Deaths log harness compilation failed."
    }
    & (Join-Path $OutDir "death_log_harness.exe") $dll
    if ($LASTEXITCODE -ne 0) {
        throw "Deaths log harness reported failures."
    }
} finally {
    Pop-Location
}
