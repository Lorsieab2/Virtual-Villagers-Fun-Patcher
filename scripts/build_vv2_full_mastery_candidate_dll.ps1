$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vv2_full_mastery_candidate"
$resourceSource = Join-Path $projectRoot "native\shared\origins-upgrades.rc"
$outputRoot = Join-Path $projectRoot "data\candidates"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"
$resource = Join-Path $outputRoot "vv2_full_mastery_candidate.res"
$output = Join-Path $outputRoot "VVFP VV2 Full Mastery Candidate.dll"

& (Join-Path $sdkRoot "bin\$sdkVersion\x86\rc.exe") /nologo /fo $resource `
    $resourceSource
if ($LASTEXITCODE -ne 0) { throw "Resource compilation failed." }

& (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") /nologo /LD /O2 /MT `
    /I (Join-Path $vsTools "include") `
    /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
    /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
    /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
    (Join-Path $nativeRoot "vv2_full_mastery_candidate.c") $resource `
    /link /Brepro `
    ("/DEF:" + (Join-Path $nativeRoot "vv2_full_mastery_candidate.def")) `
    ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
    ("/OUT:" + $output) user32.lib
if ($LASTEXITCODE -ne 0) { throw "Native DLL compilation failed." }

@(
    $resource,
    (Join-Path $projectRoot "vv2_full_mastery_candidate.obj"),
    (Join-Path $projectRoot "vv2_full_mastery_candidate.exp"),
    (Join-Path $projectRoot "vv2_full_mastery_candidate.lib")
) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Remove-Item -LiteralPath $_
}
