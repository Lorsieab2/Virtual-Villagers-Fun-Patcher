$ErrorActionPreference = "Stop"

# Builds "VVFP Head Look.dll" (Change Appearance's head look: Auto, Young or Old, all five games) from
# native\vvfp_head_look.  32-bit, static CRT, like every other companion.  Re-run
# scripts\build_head_look_feature.py afterwards: each game's Origins row pins the DLL by SHA-256.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_head_look"
$outputRoot = Join-Path $projectRoot "assets\head_look"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null

Push-Location $projectRoot
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
        (Join-Path $nativeRoot "vvfp_head_look.c") `
        (Join-Path $projectRoot "native\shared\save_folder.c") `
        /link `
        /Brepro `
        ("/DEF:" + (Join-Path $nativeRoot "vvfp_head_look.def")) `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/OUT:" + (Join-Path $outputRoot "VVFP Head Look.dll")) `
        /RELEASE `
        kernel32.lib `
        shell32.lib
    $built = $LASTEXITCODE
} finally {
    Pop-Location
}

@(
    (Join-Path $projectRoot "vvfp_head_look.obj"),
    (Join-Path $projectRoot "save_folder.obj"),
    (Join-Path $projectRoot "vvfp_head_look.exp"),
    (Join-Path $projectRoot "vvfp_head_look.lib"),
    (Join-Path $outputRoot "VVFP Head Look.exp"),
    (Join-Path $outputRoot "VVFP Head Look.lib")
) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Remove-Item -LiteralPath $_
}
if ($built -ne 0) {
    throw "Native head look DLL compilation failed."
}
