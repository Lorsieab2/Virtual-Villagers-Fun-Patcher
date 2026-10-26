$ErrorActionPreference = "Stop"

# Builds "VVFP Appearance Rolls.dll" (native\vvfp_appearance_rolls), part of Fix Vanilla Bugs in The
# Lost Children, The Tree of Life and New Believers: the random head and body rolls that left out the
# last row now reach it.  32-bit, static CRT, like every other companion.  The Fix Vanilla Bugs rows
# in data\builds.json pin the DLL by SHA-256: re-pin them after a rebuild.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_appearance_rolls"
$outputRoot = Join-Path $projectRoot "assets\appearance_rolls"
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
    (Join-Path $nativeRoot "vvfp_appearance_rolls.c") `
    /link `
    /Brepro `
    ("/DEF:" + (Join-Path $nativeRoot "vvfp_appearance_rolls.def")) `
    ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
    ("/OUT:" + (Join-Path $outputRoot "VVFP Appearance Rolls.dll")) `
    /RELEASE `
    kernel32.lib
if ($LASTEXITCODE -ne 0) {
    throw "Native appearance rolls DLL compilation failed."
}

@(
    (Join-Path $projectRoot "vvfp_appearance_rolls.obj"),
    (Join-Path $projectRoot "vvfp_appearance_rolls.exp"),
    (Join-Path $projectRoot "vvfp_appearance_rolls.lib")
) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Remove-Item -LiteralPath $_
}
