$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vv2_origins_icons"
$resourceRoot = Join-Path $projectRoot "native\vv1_origins_icons"
$outputRoot = Join-Path $projectRoot "assets\origins"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"
$resource = Join-Path $outputRoot "vv2_origins_icons.res"

& (Join-Path $sdkRoot "bin\$sdkVersion\x86\rc.exe") `
    /nologo `
    /fo $resource `
    (Join-Path $nativeRoot "vv2_origins_icons.rc")
if ($LASTEXITCODE -ne 0) { throw "Resource compilation failed." }

& (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
    /nologo /LD /O2 /MT `
    /I (Join-Path $vsTools "include") `
    /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
    /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
    /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
    (Join-Path $nativeRoot "vv2_origins_icons.c") $resource `
    /link /Brepro `
    ("/DEF:" + (Join-Path $nativeRoot "vv2_origins_icons.def")) `
    ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
    ("/OUT:" + (Join-Path $outputRoot "VVFP VV2 Origins Icons.dll")) `
    user32.lib gdi32.lib shell32.lib advapi32.lib
if ($LASTEXITCODE -ne 0) { throw "Native DLL compilation failed." }

@(
    $resource,
    (Join-Path $projectRoot "vv2_origins_icons.obj"),
    (Join-Path $projectRoot "vv2_origins_icons.exp"),
    (Join-Path $projectRoot "vv2_origins_icons.lib")
) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Remove-Item -LiteralPath $_
}
