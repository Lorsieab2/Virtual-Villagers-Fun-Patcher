# Builds and runs native\vvfp_unicode_text\grapheme_harness.c (tests/test_unicode18.py): the in-game
# companions' text units (text_utf8.h, Unicode 18.0) outside the game.  32-bit, like the companions.  The work
# folder is unique per run, so concurrent runs never share files.  Arguments are passed to the harness.
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_unicode_text"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"
$work = Join-Path $env:TEMP ("vvfp_gh_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $work | Out-Null
$out = Join-Path $work "vvfp_grapheme_harness.exe"

try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo /W4 /O2 `
        ("/Fo" + $work + "\") `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        (Join-Path $nativeRoot "grapheme_harness.c") `
        /link `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/OUT:" + $out)
    if ($LASTEXITCODE -ne 0) { throw "grapheme harness failed to build" }
    & $out @args
    if ($LASTEXITCODE -ne 0) { throw "grapheme harness reported failures" }
}
finally {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
