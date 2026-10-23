$ErrorActionPreference = "Stop"

# Builds "VVFP VV3 Both Factions.dll" (Both Factions: Nature and Magic, The
# Secret City) from native\vvfp_vv3_both_factions.  32-bit, static CRT, like
# every other companion.  Re-run scripts\build_vv3_both_factions_feature.py
# afterwards: the row pins the DLL by SHA-256.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_vv3_both_factions"
$outputRoot = Join-Path $projectRoot "assets\both_factions"
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
    (Join-Path $nativeRoot "vvfp_vv3_both_factions.c") `
    /link `
    /Brepro `
    ("/DEF:" + (Join-Path $nativeRoot "vvfp_vv3_both_factions.def")) `
    ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
    ("/OUT:" + (Join-Path $outputRoot "VVFP VV3 Both Factions.dll")) `
    /RELEASE `
    kernel32.lib user32.lib shell32.lib
if ($LASTEXITCODE -ne 0) {
    throw "Native both-factions DLL compilation failed."
}

@(
    (Join-Path $projectRoot "vvfp_vv3_both_factions.obj"),
    (Join-Path $projectRoot "vvfp_vv3_both_factions.exp"),
    (Join-Path $projectRoot "vvfp_vv3_both_factions.lib")
) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Remove-Item -LiteralPath $_
}
