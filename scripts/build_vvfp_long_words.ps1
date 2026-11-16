$ErrorActionPreference = "Stop"

# Builds "VVFP Long Words.dll" (native\vvfp_long_words), part of Fix Vanilla Bugs in The Lost Children, The Secret
# City, The Tree of Life and New Believers: a word wider than its box no longer hangs the game's line layout.
# 32-bit, static CRT, like every other companion.  The Fix Vanilla Bugs rows in data\builds.json pin the DLL by
# SHA-256 (their companion_files entry): re-pin them after a rebuild.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_long_words"
$outputRoot = Join-Path $projectRoot "assets\long_words"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
$work = Join-Path ([System.IO.Path]::GetTempPath()) ("vvfp_long_words_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $work | Out-Null
Push-Location $work
try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo /LD /O2 /MT /W4 `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        (Join-Path $nativeRoot "vvfp_long_words.c") `
        /link /Brepro `
        ("/DEF:" + (Join-Path $nativeRoot "vvfp_long_words.def")) `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/OUT:" + (Join-Path $work "VVFP Long Words.dll")) `
        /RELEASE `
        kernel32.lib
    $built = $LASTEXITCODE
    if ($built -eq 0) {
        Copy-Item -LiteralPath (Join-Path $work "VVFP Long Words.dll") -Destination (Join-Path $outputRoot "VVFP Long Words.dll") -Force
    }
} finally {
    Pop-Location
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
if ($built -ne 0) {
    throw "Native long-words DLL compilation failed."
}
