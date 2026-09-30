param(
    [string]$OutDir = (Join-Path $env:TEMP "vvfp_statistics_store_harness")
)

$ErrorActionPreference = "Stop"

# Builds and runs the 32-bit harness for the statistics store
# (native/statistics_export/statistics_store_harness.c): the per-slot
# Village Statistics and Stew Discoveries .dat files, the pre-save flush that
# fills them from the executable hooks' pending fields, and the rules for
# missing, corrupt, foreign and unreadable files. It compiles the same
# statistics_store.c the companion DLL is built from. Exit code 0 means every
# check passed. The executable and its scratch files stay under -OutDir and
# %TEMP%, never in the repository.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\statistics_export"
$sharedRoot = Join-Path $projectRoot "native\shared"
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
        /W3 `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        /I $sharedRoot `
        /I $nativeRoot `
        (Join-Path $nativeRoot "statistics_store_harness.c") `
        (Join-Path $nativeRoot "statistics_store.c") `
        (Join-Path $sharedRoot "save_folder.c") `
        /link `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/OUT:" + (Join-Path $OutDir "statistics_store_harness.exe")) `
        kernel32.lib `
        shell32.lib
    if ($LASTEXITCODE -ne 0) {
        throw "Statistics store harness compilation failed."
    }
    & (Join-Path $OutDir "statistics_store_harness.exe")
    if ($LASTEXITCODE -ne 0) {
        throw "Statistics store harness reported failures."
    }
} finally {
    Pop-Location
}
