# Build and run the Start Over / Like and Dislike Words harness
# (native/shared/save_reset_words_harness.c), for all five games.
#
# Run by tests/test_start_over_clears_like_dislike_words.py. Like
# build_save_reset_harness.ps1, each run builds into its own %TEMP% folder, and
# the harness redirects Documents to a %TEMP% folder (harness_ldw_tree.h), so
# no real save folder is touched. VV_RESET_TESTABLE builds the reset as the
# harness build of it.
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$sharedRoot = Join-Path $projectRoot "native\shared"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"
$outDir = Join-Path $env:TEMP ("vvfp_save_reset_words_harness_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $outDir | Out-Null
$out = Join-Path $outDir "vvfp_save_reset_words_harness.exe"

try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo `
        /DVV_RESET_TESTABLE `
        ("/Fo" + $outDir + "\") `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        /I $sharedRoot `
        (Join-Path $sharedRoot "save_reset_words_harness.c") `
        (Join-Path $sharedRoot "save_reset.c") `
        (Join-Path $sharedRoot "save_folder.c") `
        /link `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        user32.lib `
        shell32.lib `
        ("/OUT:" + $out)
    if ($LASTEXITCODE -ne 0) { throw "save reset words harness failed to build" }

    & $out
    if ($LASTEXITCODE -ne 0) { throw "save reset words harness reported failures" }
}
finally {
    Remove-Item -LiteralPath $outDir -Recurse -Force -ErrorAction SilentlyContinue
}
