$ErrorActionPreference = "Stop"

# Builds "VVFP VV4 Empty Sources.dll" (Fix Vanilla Bugs, The Tree of Life: no tool harvest from an empty bush) from
# native\vvfp_vv4_empty_sources.  32-bit, static CRT, like every other companion.  Afterwards
# re-pin it by SHA-256 in data/builds.json (the vv4_fix_vanilla_bugs row's companion_files).

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_vv4_empty_sources"
$outputRoot = Join-Path $projectRoot "assets\empty_sources"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
$work = Join-Path ([System.IO.Path]::GetTempPath()) ("vvfp_vv4_empty_sources_" + [guid]::NewGuid().ToString("N"))
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
        (Join-Path $nativeRoot "vvfp_vv4_empty_sources.c") `
        /link `
        /Brepro `
        ("/DEF:" + (Join-Path $nativeRoot "vvfp_vv4_empty_sources.def")) `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/OUT:" + (Join-Path $work "VVFP VV4 Empty Sources.dll")) `
        /RELEASE `
        kernel32.lib user32.lib shell32.lib
    $built = $LASTEXITCODE
    if ($built -eq 0) {
        Copy-Item -LiteralPath (Join-Path $work "VVFP VV4 Empty Sources.dll") -Destination (Join-Path $outputRoot "VVFP VV4 Empty Sources.dll") -Force
    }
} finally {
    Pop-Location
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
if ($built -ne 0) {
    throw "Native VV4 Empty Sources DLL compilation failed."
}
