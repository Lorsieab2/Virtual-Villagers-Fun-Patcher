param(
    [string]$OutDir = (Join-Path $env:TEMP "vvfp_population_export_harness")
)

$ErrorActionPreference = "Stop"

# Builds and runs the 32-bit runtime harness for "VVFP Parentage Export.dll".
# The harness loads the shipped DLL, drives WriteParentageRecordWithFather for
# each of the five games over a synthetic villager array, reads back the log
# the DLL wrote, and checks every conception field.  Exit code 0 means every
# check passed.  The harness executable is left in the scratch folder given
# by -OutDir (default: the system temp folder), never in the repository.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\population_export"
$dll = Join-Path $projectRoot "assets\population\VVFP Population Export.dll"
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
    & (Join-Path $OutDir "population_export_harness.exe") $dll
    if ($LASTEXITCODE -ne 0) {
        throw "Population export harness reported failures."
    }
} finally {
    Pop-Location
}
