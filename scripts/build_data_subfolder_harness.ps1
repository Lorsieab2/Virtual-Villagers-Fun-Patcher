param(
    [string]$OutDir = (Join-Path $env:TEMP "vvfp_data_subfolder_harness")
)

$ErrorActionPreference = "Stop"

# Builds and runs the 32-bit runtime harness for native/shared/data_subfolder.h
# (each kind of patcher data file in its own folder, and the move of a copy an
# older build left loose). It works only in a scratch folder under %TEMP% and
# never resolves Documents, so it cannot touch Documents\LDW or any save.
# Exit code 0 means every check passed. Nothing is left in the repository.

$projectRoot = Split-Path -Parent $PSScriptRoot
$sharedRoot = Join-Path $projectRoot "native\shared"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
$scratch = Join-Path $OutDir ("run-" + [guid]::NewGuid().ToString("N"))
Push-Location $OutDir
try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo `
        /O2 `
        /MT `
        /W4 `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        (Join-Path $sharedRoot "data_subfolder_harness.c") `
        /link `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/OUT:" + (Join-Path $OutDir "data_subfolder_harness.exe")) `
        kernel32.lib `
        user32.lib
    if ($LASTEXITCODE -ne 0) {
        throw "Data subfolder harness compilation failed."
    }
    & (Join-Path $OutDir "data_subfolder_harness.exe") $scratch
    if ($LASTEXITCODE -ne 0) {
        throw "Data subfolder harness reported failures."
    }
} finally {
    if (Test-Path -LiteralPath $scratch) {
        Remove-Item -LiteralPath $scratch -Recurse -Force
    }
    Pop-Location
}
