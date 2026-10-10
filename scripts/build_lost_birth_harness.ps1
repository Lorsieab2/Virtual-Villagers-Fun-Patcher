param(
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"

# Builds and runs the 32-bit runtime harness for the babies lost with their
# mother (native/vvfp_cause_of_death/lost_birth_harness.c) against the TEST
# build of "VVFP Cause of Death.dll", in all five games' record geometry. It
# writes no file: the harness hands the companion its own record writer.
# Exit code 0 means every check passed. The harness executable is left in
# -OutDir, never in the repository; without -OutDir each run builds into its
# own folder under %TEMP% and removes it afterwards.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_cause_of_death"
$dll = Join-Path $projectRoot "tests\test_dlls\VVFP Cause of Death.test.dll"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

$ownsOutDir = -not $OutDir
if ($ownsOutDir) {
    $OutDir = Join-Path $env:TEMP ("vvfp_lost_birth_harness_" + [guid]::NewGuid().ToString("N"))
}
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
Push-Location $OutDir
try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo `
        ("/Fo" + $OutDir + "\") `
        /O2 `
        /MT `
        /W4 `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        (Join-Path $nativeRoot "lost_birth_harness.c") `
        /link `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/OUT:" + (Join-Path $OutDir "lost_birth_harness.exe")) `
        kernel32.lib `
        user32.lib
    if ($LASTEXITCODE -ne 0) {
        throw "Lost before birth harness compilation failed."
    }
    & (Join-Path $OutDir "lost_birth_harness.exe") $dll
    if ($LASTEXITCODE -ne 0) {
        throw "Lost before birth harness reported failures."
    }
} finally {
    Pop-Location
    if ($ownsOutDir) {
        Remove-Item -LiteralPath $OutDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
