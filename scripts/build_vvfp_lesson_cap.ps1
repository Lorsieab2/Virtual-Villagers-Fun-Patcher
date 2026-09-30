$ErrorActionPreference = "Stop"

# Builds "VVFP Lesson Cap.dll" (School Lessons Stop at 50, Teaching Children
# Stops at 50, Tribal Chief Lessons Stop at 50) from native\vvfp_lesson_cap.
# 32-bit, static CRT, like every other companion.  Re-run
# scripts\build_lesson_cap_features.py afterwards: all three rows pin the DLL
# by SHA-256.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_lesson_cap"
$outputRoot = Join-Path $projectRoot "assets\lesson_cap"
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
    (Join-Path $nativeRoot "vvfp_lesson_cap.c") `
    /link `
    ("/DEF:" + (Join-Path $nativeRoot "vvfp_lesson_cap.def")) `
    ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
    ("/OUT:" + (Join-Path $outputRoot "VVFP Lesson Cap.dll")) `
    /RELEASE `
    kernel32.lib
if ($LASTEXITCODE -ne 0) {
    throw "Native lesson-cap DLL compilation failed."
}

# The TEST build: the same source compiled with VVFP_TEST, which adds the
# probe exports and counters the tests drive (vvfp_lesson_cap_test.def).
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
    (Join-Path $nativeRoot "vvfp_lesson_cap.c") `
    /link `
    ("/DEF:" + (Join-Path $nativeRoot "vvfp_lesson_cap_test.def")) `
    ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
    ("/OUT:" + (Join-Path $testRoot "VVFP Lesson Cap.test.dll")) `
    /RELEASE `
    kernel32.lib
if ($LASTEXITCODE -ne 0) {
    throw "Native lesson-cap DLL compilation failed (test build)."
}

@(
    (Join-Path $projectRoot "vvfp_lesson_cap.obj"),
    (Join-Path $projectRoot "vvfp_lesson_cap.exp"),
    (Join-Path $projectRoot "vvfp_lesson_cap.lib")
) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Remove-Item -LiteralPath $_
}
