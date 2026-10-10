param(
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"

# Builds and runs the 32-bit runtime harness for "VVFP Parentage Export.dll".
# The harness loads the shipped DLL, drives WriteParentageRecordWithFather for
# each of the five games over a synthetic villager array, reads back the log
# the DLL wrote, and checks every conception field.  Exit code 0 means every
# check passed.  The harness executable is left in the scratch folder given
# by -OutDir (default: the system temp folder), never in the repository.
#
# Without -OutDir each run builds into its own folder under %TEMP% and removes
# it afterwards. One shared %TEMP% folder made concurrent runs (two worktrees,
# two suites) fail with C1083/LNK1104 or run each other's executable. The
# executable keeps its basename, which names its LDW save folder and the
# harness_ldw_tree.h mutex that serialises the runs themselves. With -OutDir
# the caller owns that folder and the executable is left in it.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\population_export"
$dll = Join-Path $projectRoot "assets\population\VVFP Population Export.dll"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

$ownsOutDir = -not $OutDir
if ($ownsOutDir) {
    $OutDir = Join-Path $env:TEMP ("vvfp_population_export_harness_" + [guid]::NewGuid().ToString("N"))
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
        (Join-Path $nativeRoot "population_export_harness.c") `
        /link `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/OUT:" + (Join-Path $OutDir "population_export_harness.exe")) `
        kernel32.lib `
        shell32.lib
    if ($LASTEXITCODE -ne 0) {
        throw "Population export harness compilation failed."
    }
    # A stand-in "VVFP VV1 Parentage.dll" (vv1_parentage_stub.c), where the
    # exporter looks for the real companion: beside the harness executable,
    # in its patcher-files folder.  Never shipped; it lives only in $OutDir.
    $stubDir = Join-Path $OutDir "Virtual Villagers Fun Patcher Files"
    New-Item -ItemType Directory -Path $stubDir -Force | Out-Null
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo `
        /LD `
        ("/Fo" + $OutDir + "\") `
        /O2 `
        /MT `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        (Join-Path $nativeRoot "vv1_parentage_stub.c") `
        /link `
        ("/DEF:" + (Join-Path $nativeRoot "vv1_parentage_stub.def")) `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/IMPLIB:" + (Join-Path $OutDir "vv1_parentage_stub.lib")) `
        ("/OUT:" + (Join-Path $stubDir "VVFP VV1 Parentage.dll")) `
        kernel32.lib
    if ($LASTEXITCODE -ne 0) {
        throw "Stand-in VV1 parentage companion compilation failed."
    }
    & (Join-Path $OutDir "population_export_harness.exe") $dll
    if ($LASTEXITCODE -ne 0) {
        throw "Population export harness reported failures."
    }
} finally {
    Pop-Location
    if ($ownsOutDir) {
        Remove-Item -LiteralPath $OutDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
