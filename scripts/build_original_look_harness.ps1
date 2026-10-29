# Builds and runs native\vvfp_original_look\original_look_harness.c (tests/test_original_look.py): the original looks'
# per-save file against real files in a fresh folder under %TEMP%, never the player's Documents.  32-bit,
# like the companion.  The work folder is unique per run, so concurrent runs never share files.
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_original_look"
$sharedRoot = Join-Path $projectRoot "native\shared"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"
$work = Join-Path $env:TEMP ("vvfp_ol_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $work | Out-Null
$out = Join-Path $work "vvfp_original_look_harness.exe"
$savedTemp = $env:TEMP
$savedTmp = $env:TMP

try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo /W4 `
        /DVV_RESET_TESTABLE `
        ("/Fo" + $work + "\") `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        /I $sharedRoot `
        (Join-Path $nativeRoot "original_look_harness.c") `
        (Join-Path $sharedRoot "save_reset.c") `
        /link `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        user32.lib `
        ("/OUT:" + $out)
    if ($LASTEXITCODE -ne 0) { throw "original look harness failed to build" }
    $env:TEMP = $work
    $env:TMP = $work
    & $out @args
    if ($LASTEXITCODE -ne 0) { throw "original look harness reported failures" }
}
finally {
    $env:TEMP = $savedTemp
    $env:TMP = $savedTmp
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
