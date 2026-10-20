$ErrorActionPreference = "Stop"

# Builds "VVFP Number Names.dll" (a baby born with a living villager's full
# name is numbered at its birth, all five games) from
# native\vvfp_number_names.  32-bit, static CRT, like every other companion.
# Re-run scripts\build_vv1_parentage_feature.py and
# scripts\build_vv<2-5>_parentage_feature.py afterwards: the parentage rows
# ship it and pin it by SHA-256.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_number_names"
$sharedRoot = Join-Path $projectRoot "native\shared"
$outputRoot = Join-Path $projectRoot "assets\number_names"
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
    /I $sharedRoot `
    (Join-Path $nativeRoot "vvfp_number_names.c") `
    /link `
    /Brepro `
    ("/DEF:" + (Join-Path $nativeRoot "vvfp_number_names.def")) `
    ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
    ("/OUT:" + (Join-Path $outputRoot "VVFP Number Names.dll")) `
    /RELEASE `
    kernel32.lib `
    shell32.lib
if ($LASTEXITCODE -ne 0) {
    throw "Native number-names DLL compilation failed."
}

@(
    (Join-Path $projectRoot "vvfp_number_names.obj"),
    (Join-Path $projectRoot "vvfp_number_names.exp"),
    (Join-Path $projectRoot "vvfp_number_names.lib")
) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Remove-Item -LiteralPath $_
}
