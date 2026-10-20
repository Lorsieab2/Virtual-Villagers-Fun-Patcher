$ErrorActionPreference = "Stop"

# Builds "VVFP VV2 Totems.dll" (Esteemed Elders' Totems Use No Villager
# Records, The Lost Children) from native\vvfp_vv2_totems.  32-bit, static
# CRT, like every other companion.  Re-run scripts\build_vv2_totems_feature.py
# afterwards: the row pins the DLL by SHA-256.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_vv2_totems"
$sharedRoot = Join-Path $projectRoot "native\shared"
$outputRoot = Join-Path $projectRoot "assets\vv2_totems"
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
    (Join-Path $nativeRoot "vvfp_vv2_totems.c") `
    (Join-Path $sharedRoot "save_folder.c") `
    /link `
    /Brepro `
    ("/DEF:" + (Join-Path $nativeRoot "vvfp_vv2_totems.def")) `
    ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
    ("/OUT:" + (Join-Path $outputRoot "VVFP VV2 Totems.dll")) `
    /RELEASE `
    kernel32.lib `
    shell32.lib `
    user32.lib
if ($LASTEXITCODE -ne 0) {
    throw "Native VV2 totems DLL compilation failed."
}

@(
    (Join-Path $projectRoot "vvfp_vv2_totems.obj"),
    (Join-Path $projectRoot "save_folder.obj"),
    (Join-Path $projectRoot "vvfp_vv2_totems.exp"),
    (Join-Path $projectRoot "vvfp_vv2_totems.lib"),
    (Join-Path $outputRoot "VVFP VV2 Totems.exp"),
    (Join-Path $outputRoot "VVFP VV2 Totems.lib")
) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Remove-Item -LiteralPath $_
}
