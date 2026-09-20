$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\population_export"
$sharedRoot = Join-Path $projectRoot "native\shared"
$outputRoot = Join-Path $projectRoot "assets\population"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null

& (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
    /nologo `
    /LD `
    /O2 `
    /MT `
    /I (Join-Path $vsTools "include") `
    /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
    /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
    /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
    /I $sharedRoot `
    (Join-Path $nativeRoot "population_export.c") `
    (Join-Path $sharedRoot "village_identity.c") `
    (Join-Path $sharedRoot "save_folder.c") `
    /link `
    ("/DEF:" + (Join-Path $nativeRoot "population_export.def")) `
    ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
    ("/OUT:" + (Join-Path $outputRoot "VVFP Population Export.dll")) `
    /RELEASE `
    kernel32.lib `
    shell32.lib
if ($LASTEXITCODE -ne 0) {
    throw "Native population DLL compilation failed."
}

@(
    (Join-Path $projectRoot "population_export.obj"),
    (Join-Path $projectRoot "village_identity.obj"),
    (Join-Path $projectRoot "save_folder.obj"),
    (Join-Path $projectRoot "population_export.exp"),
    (Join-Path $projectRoot "population_export.lib")
) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Remove-Item -LiteralPath $_
}
