param(
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"

# Builds and runs the 32-bit runtime harness for the mask-sidecar load/publish
# path shared by all five games (native/shared/sidecar_io.h, driven by
# native/shared/sidecar_io_harness.c). It works only in a scratch folder under
# %TEMP% and never touches Documents or any game's saves. Exit code 0 means
# every check passed. The harness executable is left in -OutDir, never in the
# repository.
#
# Without -OutDir each run builds into its own folder under %TEMP% and removes
# it afterwards. One shared %TEMP% folder made concurrent runs (two worktrees,
# two suites) fail with C1083/LNK1104 or run each other's executable. The
# executable keeps its basename. With -OutDir the caller owns that folder and
# the executable is left in it.

$projectRoot = Split-Path -Parent $PSScriptRoot
$sharedRoot = Join-Path $projectRoot "native\shared"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

$ownsOutDir = -not $OutDir
if ($ownsOutDir) {
    $OutDir = Join-Path $env:TEMP ("vvfp_sidecar_io_harness_" + [guid]::NewGuid().ToString("N"))
}
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
Push-Location $OutDir
try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo `
        ("/Fo" + $OutDir + "\") `
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
    if ($ownsOutDir) {
        Remove-Item -LiteralPath $OutDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
