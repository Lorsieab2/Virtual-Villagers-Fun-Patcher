$ErrorActionPreference = "Stop"

# Builds "VVFP Text Fixes.dll" (native\vvfp_text_fixes), the game-text part of Fix Vanilla Bugs in all five games:
# the owner's approved typo fixes (data\vanilla_text_fixes.json, compiled in as tf_fixes.inc -- run
# scripts\build_text_fixes_table.py first when the data changes) and The Tree of Life's and New Believers' Food
# Mastery line.  32-bit, static CRT, like every other companion.  The Fix Vanilla Bugs rows in data\builds.json pin
# the DLL by SHA-256 (their companion_files entry): re-pin them after a rebuild.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_text_fixes"
$outputRoot = Join-Path $projectRoot "assets\text_fixes"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
$work = Join-Path ([System.IO.Path]::GetTempPath()) ("vvfp_text_fixes_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $work | Out-Null
Push-Location $work
try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo /LD /O2 /MT /W4 `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        (Join-Path $nativeRoot "vvfp_text_fixes.c") `
        /link /Brepro `
        ("/DEF:" + (Join-Path $nativeRoot "vvfp_text_fixes.def")) `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/OUT:" + (Join-Path $work "VVFP Text Fixes.dll")) `
        /RELEASE `
        kernel32.lib
    $built = $LASTEXITCODE
    if ($built -eq 0) {
        Copy-Item -LiteralPath (Join-Path $work "VVFP Text Fixes.dll") -Destination (Join-Path $outputRoot "VVFP Text Fixes.dll") -Force
    }
} finally {
    Pop-Location
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
if ($built -ne 0) {
    throw "Native text fixes DLL compilation failed."
}
