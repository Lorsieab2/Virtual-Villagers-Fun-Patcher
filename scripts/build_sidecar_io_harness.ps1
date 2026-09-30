param(
    [string]$OutDir = (Join-Path $env:TEMP "vvfp_sidecar_io_harness")
)

$ErrorActionPreference = "Stop"

# Builds and runs the 32-bit runtime harness for the mask-sidecar load/publish
# path shared by all five games (native/shared/sidecar_io.h, driven by
# native/shared/sidecar_io_harness.c). It works only in a scratch folder under
# %TEMP% and never touches Documents or any game's saves. Exit code 0 means
# every check passed. The harness executable is left in -OutDir, never in the
# repository.

$projectRoot = Split-Path -Parent $PSScriptRoot
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
        (Join-Path $sharedRoot "sidecar_io_harness.c") `
        /link `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/OUT:" + (Join-Path $OutDir "sidecar_io_harness.exe")) `
        kernel32.lib `
        user32.lib `
        advapi32.lib
    if ($LASTEXITCODE -ne 0) {
        throw "Sidecar I/O harness compilation failed."
    }
    & (Join-Path $OutDir "sidecar_io_harness.exe")
    if ($LASTEXITCODE -ne 0) {
        throw "Sidecar I/O harness reported failures."
    }
} finally {
    Pop-Location
}
