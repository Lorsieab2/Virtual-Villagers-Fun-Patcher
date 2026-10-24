$ErrorActionPreference = "Stop"

# Builds "VVFP Speed Change Timers.dll" (native\vvfp_speed_timers), part of Fix Vanilla Bugs in The
# Secret City and The Tree of Life: unpausing at another speed rescales the clock's timers as every
# other speed change does.  32-bit, static CRT, like every other companion.  The Fix Vanilla Bugs
# rows in data\builds.json pin the DLL by SHA-256: re-pin them after a rebuild.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_speed_timers"
$outputRoot = Join-Path $projectRoot "assets\speed_timers"
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
    (Join-Path $nativeRoot "vvfp_speed_timers.c") `
    /link `
    /Brepro `
    ("/DEF:" + (Join-Path $nativeRoot "vvfp_speed_timers.def")) `
    ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
    ("/OUT:" + (Join-Path $outputRoot "VVFP Speed Change Timers.dll")) `
    /RELEASE `
    kernel32.lib
if ($LASTEXITCODE -ne 0) {
    throw "Native speed-change timers DLL compilation failed."
}

@(
    (Join-Path $projectRoot "vvfp_speed_timers.obj"),
    (Join-Path $projectRoot "vvfp_speed_timers.exp"),
    (Join-Path $projectRoot "vvfp_speed_timers.lib")
) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Remove-Item -LiteralPath $_
}
