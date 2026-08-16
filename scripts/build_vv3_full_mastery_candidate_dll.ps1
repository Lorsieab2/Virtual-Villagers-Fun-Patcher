$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vv3_full_mastery_candidate"
$outputRoot = Join-Path $projectRoot "data\candidates"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

& (Join-Path $sdkRoot "bin\$sdkVersion\x86\rc.exe") `
    /nologo `
    /fo (Join-Path $outputRoot "vv3_full_mastery_candidate.res") `
    (Join-Path $nativeRoot "vv3_full_mastery_candidate.rc")
if ($LASTEXITCODE -ne 0) {
    throw "Resource compilation failed."
}

& (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
    /nologo `
    /LD `
    /O2 `
    /MT `
    /I (Join-Path $vsTools "include") `
    /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
    /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
    /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
    (Join-Path $nativeRoot "vv3_full_mastery_candidate.c") `
    (Join-Path $outputRoot "vv3_full_mastery_candidate.res") `
    /link `
    /Brepro `
    ("/DEF:" + (Join-Path $nativeRoot "vv3_full_mastery_candidate.def")) `
    ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
    ("/OUT:" + (Join-Path $outputRoot "VVFP VV3 Full Mastery Candidate.dll")) `
    user32.lib `
    gdi32.lib
if ($LASTEXITCODE -ne 0) {
    throw "Native DLL compilation failed."
}

@(
    (Join-Path $outputRoot "vv3_full_mastery_candidate.res"),
    (Join-Path $projectRoot "vv3_full_mastery_candidate.obj"),
    (Join-Path $projectRoot "vv3_full_mastery_candidate.exp"),
    (Join-Path $projectRoot "vv3_full_mastery_candidate.lib")
) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Remove-Item -LiteralPath $_
}
