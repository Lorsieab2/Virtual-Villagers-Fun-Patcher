$ErrorActionPreference = "Stop"

# Builds "VVFP Skin Tones.dll" (per-villager skin tones, A New Home; a draft) from native\vvfp_skin_tones.
# 32-bit, static CRT, like every other companion.  Re-run scripts\build_vv1_skin_tones_feature.py
# afterwards: the row pins the DLL by SHA-256.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_skin_tones"
$outputRoot = Join-Path $projectRoot "assets\skin_tones"
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
        (Join-Path $nativeRoot "vvfp_skin_tones.c") `
        (Join-Path $projectRoot "native\shared\save_folder.c") `
        /link `
        /Brepro `
        ("/DEF:" + (Join-Path $nativeRoot "vvfp_skin_tones.def")) `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/OUT:" + (Join-Path $outputRoot "VVFP Skin Tones.dll")) `
        /RELEASE `
        kernel32.lib `
        shell32.lib `
        user32.lib `
        gdi32.lib `
        gdiplus.lib
    $built = $LASTEXITCODE
} finally {
    Pop-Location
}

@(
    (Join-Path $projectRoot "vvfp_skin_tones.obj"),
    (Join-Path $projectRoot "save_folder.obj"),
    (Join-Path $projectRoot "vvfp_skin_tones.exp"),
    (Join-Path $projectRoot "vvfp_skin_tones.lib"),
    (Join-Path $outputRoot "VVFP Skin Tones.exp"),
    (Join-Path $outputRoot "VVFP Skin Tones.lib")
) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Remove-Item -LiteralPath $_
}
if ($built -ne 0) {
    throw "Native head look DLL compilation failed."
}
