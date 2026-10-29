$ErrorActionPreference = "Stop"

# Builds "VVFP Original Look.dll" (the originals behind Change Appearance's Reset to original, all five games) from
# native\vvfp_original_look.  32-bit, static CRT, like every other companion.  Re-run
# scripts\build_original_look_feature.py afterwards: each game's Original Looks row pins the DLL by SHA-256.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_original_look"
$outputRoot = Join-Path $projectRoot "assets\original_look"
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
        (Join-Path $nativeRoot "vvfp_original_look.c") `
        (Join-Path $projectRoot "native\shared\save_folder.c") `
        /link `
        /Brepro `
        ("/DEF:" + (Join-Path $nativeRoot "vvfp_original_look.def")) `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/OUT:" + (Join-Path $outputRoot "VVFP Original Look.dll")) `
        /RELEASE `
        kernel32.lib `
        shell32.lib `
        user32.lib
    $built = $LASTEXITCODE
} finally {
    Pop-Location
}

@(
    (Join-Path $projectRoot "vvfp_original_look.obj"),
    (Join-Path $projectRoot "save_folder.obj"),
    (Join-Path $projectRoot "vvfp_original_look.exp"),
    (Join-Path $projectRoot "vvfp_original_look.lib"),
    (Join-Path $outputRoot "VVFP Original Look.exp"),
    (Join-Path $outputRoot "VVFP Original Look.lib")
) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Remove-Item -LiteralPath $_
}
if ($built -ne 0) {
    throw "Native original look DLL compilation failed."
}
