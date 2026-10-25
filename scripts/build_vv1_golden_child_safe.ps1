$ErrorActionPreference = "Stop"

# Builds "VVFP VV1 Golden Child Safe.dll" (native\vv1_golden_child_safe), part of Fix Vanilla Bugs in
# A New Home: the Golden Child is never the villager of a natural island event that could kill him or
# make him disappear.  "VVFP Speed Change Timers.dll" loads it at game start.  32-bit, static CRT, like
# every other companion.  The Fix Vanilla Bugs row in data\builds.json pins the DLL by SHA-256: re-pin
# it after a rebuild.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vv1_golden_child_safe"
$outputRoot = Join-Path $projectRoot "assets\golden_child_safe"
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
    ("/Fo" + (Join-Path $outputRoot "vv1_golden_child_safe.obj")) `
    (Join-Path $nativeRoot "vv1_golden_child_safe.c") `
    /link `
    /Brepro `
    ("/DEF:" + (Join-Path $nativeRoot "vv1_golden_child_safe.def")) `
    ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
    ("/OUT:" + (Join-Path $outputRoot "VVFP VV1 Golden Child Safe.dll")) `
    /RELEASE `
    kernel32.lib
if ($LASTEXITCODE -ne 0) {
    throw "Native VV1 Golden Child Safe DLL compilation failed."
}

@(
    (Join-Path $outputRoot "vv1_golden_child_safe.obj"),
    (Join-Path $projectRoot "vv1_golden_child_safe.exp"),
    (Join-Path $projectRoot "vv1_golden_child_safe.lib"),
    (Join-Path $outputRoot "VVFP VV1 Golden Child Safe.exp"),
    (Join-Path $outputRoot "VVFP VV1 Golden Child Safe.lib")
) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Remove-Item -LiteralPath $_
}
