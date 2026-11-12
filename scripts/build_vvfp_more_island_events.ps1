$ErrorActionPreference = "Stop"

# Builds "VVFP More Island Events.dll" (The Aspiring Adventurer island event: all five games) from
# native\vvfp_more_island_events.  32-bit, static CRT, like every other companion.  Re-run
# scripts\build_more_island_events.py afterwards (it runs this itself unless --no-build): the rows pin the DLL by
# SHA-256.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_more_island_events"
$outputRoot = Join-Path $projectRoot "assets\more_island_events"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
$work = Join-Path ([System.IO.Path]::GetTempPath()) ("vvfp_more_island_events_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $work | Out-Null

Push-Location $work
try {
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
        (Join-Path $nativeRoot "vvfp_more_island_events.c") `
        /link `
        /Brepro `
        ("/DEF:" + (Join-Path $nativeRoot "vvfp_more_island_events.def")) `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/OUT:" + (Join-Path $work "VVFP More Island Events.dll")) `
        /RELEASE `
        kernel32.lib
    $built = $LASTEXITCODE
    if ($built -eq 0) {
        Copy-Item -LiteralPath (Join-Path $work "VVFP More Island Events.dll") -Destination (Join-Path $outputRoot "VVFP More Island Events.dll") -Force
    }
} finally {
    Pop-Location
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
if ($built -ne 0) {
    throw "Native More Island Events DLL compilation failed."
}
