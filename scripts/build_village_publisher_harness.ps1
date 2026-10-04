param(
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"

# Builds and runs the 32-bit runtime harness for the logs' village header
# without Village Statistics (native/parentage_export/village_publisher_harness.c)
# against the shipped "VVFP Parentage Export.dll" and the TEST build of
# "VVFP Cause of Death.dll", in all five games' record geometry, on real files
# under a throwaway save folder named after the harness, which it empties
# before and removes after. Like the Deaths log harness it is linked at a
# fixed base with free memory above it (0x30000000) so it can place each
# game's villager table where the DLL reads it. Exit code 0 means every
# check passed. The harness executable is left in -OutDir, never in the
# repository.
#
# Without -OutDir each run builds into its own folder under %TEMP% and removes
# it afterwards. One shared %TEMP% folder made concurrent runs (two worktrees,
# two suites) fail with C1083/LNK1104 or run each other's executable. The
# executable keeps its basename, which names its LDW save folder and the
# harness_ldw_tree.h mutex that serialises the runs themselves. With -OutDir
# the caller owns that folder and the executable is left in it.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\parentage_export"
$sharedRoot = Join-Path $projectRoot "native\shared"
$dll = Join-Path $projectRoot "assets\parentage\VVFP Parentage Export.dll"
$causeTest = Join-Path $projectRoot "tests\test_dlls\VVFP Cause of Death.test.dll"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

$ownsOutDir = -not $OutDir
if ($ownsOutDir) {
    $OutDir = Join-Path $env:TEMP ("vvfp_village_publisher_harness_" + [guid]::NewGuid().ToString("N"))
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
        (Join-Path $nativeRoot "village_publisher_harness.c") `
        (Join-Path $sharedRoot "village_identity.c") `
        /link `
        /BASE:0x30000000 `
        /FIXED `
        /DYNAMICBASE:NO `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/OUT:" + (Join-Path $OutDir "village_publisher_harness.exe")) `
        kernel32.lib `
        user32.lib `
        shell32.lib
    if ($LASTEXITCODE -ne 0) {
        throw "Village publisher harness compilation failed."
    }
    & (Join-Path $OutDir "village_publisher_harness.exe") $dll $causeTest
    if ($LASTEXITCODE -ne 0) {
        throw "Village publisher harness reported failures."
    }
} finally {
    Pop-Location
    if ($ownsOutDir) {
        Remove-Item -LiteralPath $OutDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
