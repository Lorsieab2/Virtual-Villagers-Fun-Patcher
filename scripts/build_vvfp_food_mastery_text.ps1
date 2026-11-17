$ErrorActionPreference = "Stop"

# Builds "VVFP Food Mastery Text.dll" (native\vvfp_food_mastery_text), part of Fix Vanilla Bugs in The Tree of Life
# and New Believers: the Food Mastery tech's description says what its Level 2 bonus is for.
# 32-bit, static CRT, like every other companion.  The Fix Vanilla Bugs rows in data\builds.json pin the DLL by
# SHA-256 (their companion_files entry): re-pin them after a rebuild.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_food_mastery_text"
$outputRoot = Join-Path $projectRoot "assets\food_mastery_text"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
$work = Join-Path ([System.IO.Path]::GetTempPath()) ("vvfp_food_mastery_text_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $work | Out-Null
Push-Location $work
try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo /LD /O2 /MT /W4 `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        (Join-Path $nativeRoot "vvfp_food_mastery_text.c") `
        /link /Brepro `
        ("/DEF:" + (Join-Path $nativeRoot "vvfp_food_mastery_text.def")) `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/OUT:" + (Join-Path $work "VVFP Food Mastery Text.dll")) `
        /RELEASE `
        kernel32.lib
    $built = $LASTEXITCODE
    if ($built -eq 0) {
        Copy-Item -LiteralPath (Join-Path $work "VVFP Food Mastery Text.dll") -Destination (Join-Path $outputRoot "VVFP Food Mastery Text.dll") -Force
    }
} finally {
    Pop-Location
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
if ($built -ne 0) {
    throw "Native Food Mastery text DLL compilation failed."
}
