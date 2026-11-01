# Builds and runs native\vvfp_unicode_text\glyph_harness.c (tests/test_unicode_text.py): the in-game
# companion's letter maker, glyphs.inc, outside the game.  32-bit, like the companion.  The work folder is
# unique per run, so concurrent runs never share files.  Arguments are passed to the harness.
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_unicode_text"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"
$work = Join-Path $env:TEMP ("vvfp_ut_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $work | Out-Null
$out = Join-Path $work "vvfp_unicode_text_harness.exe"

try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo /W4 /O2 `
        ("/Fo" + $work + "\") `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        (Join-Path $nativeRoot "glyph_harness.c") `
        /link `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        gdi32.lib advapi32.lib `
        ("/OUT:" + $out)
    if ($LASTEXITCODE -ne 0) { throw "unicode text harness failed to build" }
    & $out @args
    if ($LASTEXITCODE -ne 0) { throw "unicode text harness reported failures" }
}
finally {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
