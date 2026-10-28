$ErrorActionPreference = "Stop"

# Builds "VVFP VV1 Grey Hair.dll" (Grey Hair at 55, A New Home) from native\vv1_grey_hair, with the
# Change Appearance preview strips that scripts\build_vv1_grey_hair_art.py writes from the grey sheets.
# 32-bit, static CRT, like every other companion.  scripts\build_vv1_grey_hair_feature.py runs this
# and then pins the DLL and the sheets by SHA-256.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vv1_grey_hair"
$outputRoot = Join-Path $projectRoot "assets\vv1_grey_hair"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"
$resource = Join-Path $outputRoot "vv1_grey_hair.res"

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null

& (Join-Path $sdkRoot "bin\$sdkVersion\x86\rc.exe") `
    /nologo `
    /fo $resource `
    (Join-Path $nativeRoot "vv1_grey_hair.rc")
if ($LASTEXITCODE -ne 0) {
    throw "Resource compilation failed."
}

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
    (Join-Path $nativeRoot "vv1_grey_hair.c") `
    $resource `
    /link `
    /Brepro `
    ("/DEF:" + (Join-Path $nativeRoot "vv1_grey_hair.def")) `
    ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
    ("/OUT:" + (Join-Path $outputRoot "VVFP VV1 Grey Hair.dll")) `
    /RELEASE `
    kernel32.lib
$built = $LASTEXITCODE

@(
    $resource,
    (Join-Path $projectRoot "vv1_grey_hair.obj"),
    (Join-Path $projectRoot "vv1_grey_hair.exp"),
    (Join-Path $projectRoot "vv1_grey_hair.lib")
) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Remove-Item -LiteralPath $_
}
if ($built -ne 0) {
    throw "Native grey hair DLL compilation failed."
}
