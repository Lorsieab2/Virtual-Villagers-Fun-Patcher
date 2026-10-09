$ErrorActionPreference = "Stop"

# Builds "VVFP Island Events.dll" (Write Island Events Log, all five games)
# from native\vvfp_island_events.  32-bit, static CRT, like every other
# companion.  Re-run scripts\build_island_events_features.py afterwards: the
# five rows pin the DLL by SHA-256.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_island_events"
$outputRoot = Join-Path $projectRoot "assets\island_events"
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
    (Join-Path $nativeRoot "vvfp_island_events.c") `
    /link `
    ("/DEF:" + (Join-Path $nativeRoot "vvfp_island_events.def")) `
    ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
    ("/OUT:" + (Join-Path $outputRoot "VVFP Island Events.dll")) `
    /RELEASE `
    kernel32.lib `
    shell32.lib
if ($LASTEXITCODE -ne 0) {
    throw "Native island-events DLL compilation failed."
}

@(
    (Join-Path $projectRoot "vvfp_island_events.obj"),
    (Join-Path $projectRoot "vvfp_island_events.exp"),
    (Join-Path $projectRoot "vvfp_island_events.lib")
) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Remove-Item -LiteralPath $_
}
