$ErrorActionPreference = "Stop"

# Builds "VVFP Last Names.dll" (Villagers Have Last Names, all five games)
# from native\vvfp_last_names.  32-bit, static CRT, like every other
# companion.  Re-run scripts\build_last_names_features.py afterwards: the
# five rows pin the DLL by SHA-256.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_last_names"
$outputRoot = Join-Path $projectRoot "assets\last_names"
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
    (Join-Path $nativeRoot "vvfp_last_names.c") `
    /link `
    ("/DEF:" + (Join-Path $nativeRoot "vvfp_last_names.def")) `
    ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
    ("/OUT:" + (Join-Path $outputRoot "VVFP Last Names.dll")) `
    /RELEASE `
    kernel32.lib
if ($LASTEXITCODE -ne 0) {
    throw "Native last-names DLL compilation failed."
}

@(
    (Join-Path $projectRoot "vvfp_last_names.obj"),
    (Join-Path $projectRoot "vvfp_last_names.exp"),
    (Join-Path $projectRoot "vvfp_last_names.lib")
) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Remove-Item -LiteralPath $_
}
