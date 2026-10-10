$ErrorActionPreference = "Stop"

# Builds "VVFP Storytelling.dll" (Dropping an Adult on a Child Tells a
# Story, A New Home and The Lost Children) from native\vvfp_storytelling.
# 32-bit, static CRT, like every other companion.  Re-run
# scripts\build_storytelling_features.py
# afterwards: the two feature rows pin the DLL by SHA-256.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_storytelling"
$outputRoot = Join-Path $projectRoot "assets\storytelling"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null

& (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
    /nologo `
    /LD `
    /O2 `
    /MT `
    /W4 `
    /I (Join-Path $vsTools "include") `
    /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
    /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
    /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
    (Join-Path $nativeRoot "vvfp_storytelling.c") `
    /link `
    ("/DEF:" + (Join-Path $nativeRoot "vvfp_storytelling.def")) `
    ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
    ("/OUT:" + (Join-Path $outputRoot "VVFP Storytelling.dll")) `
    /RELEASE `
    kernel32.lib
if ($LASTEXITCODE -ne 0) {
    throw "Native storytelling DLL compilation failed."
}

# The TEST build: the same source compiled with VVFP_TEST, which adds the
# probe export and counters the tests drive (vvfp_storytelling_test.def).
# It goes to tests\test_dlls\ and is never shipped: scripts\build_release.py
# packages only the DLL above, no manifest names the test build, and
# tests\test_shipped_dlls_have_no_test_hooks.py fails if a shipped DLL
# exports a probe.  One script builds both, so they cannot drift apart.
$testRoot = Join-Path $projectRoot "tests\test_dlls"
New-Item -ItemType Directory -Path $testRoot -Force | Out-Null

& (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
    /nologo `
    /LD `
    /O2 `
    /MT `
    /DVVFP_TEST `
    /W4 `
    /I (Join-Path $vsTools "include") `
    /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
    /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
    /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
    (Join-Path $nativeRoot "vvfp_storytelling.c") `
    /link `
    ("/DEF:" + (Join-Path $nativeRoot "vvfp_storytelling_test.def")) `
    ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
    ("/OUT:" + (Join-Path $testRoot "VVFP Storytelling.test.dll")) `
    /RELEASE `
    kernel32.lib
if ($LASTEXITCODE -ne 0) {
    throw "Native storytelling DLL compilation failed (test build)."
}

@(
    (Join-Path $projectRoot "vvfp_storytelling.obj"),
    (Join-Path $projectRoot "vvfp_storytelling.exp"),
    (Join-Path $projectRoot "vvfp_storytelling.lib")
) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Remove-Item -LiteralPath $_
}
