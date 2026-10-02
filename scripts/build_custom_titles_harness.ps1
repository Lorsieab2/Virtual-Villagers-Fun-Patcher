# Build and run the custom titles harness (native/vvfp_story_upgrades/custom_titles_harness.c).
#
# The companion's own title store and the Start Over reset, compiled unchanged
# against real files in a fresh folder under %TEMP% (the harness supplies the
# save folder; it never touches Documents\LDW).  32-bit, like the companion.
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_story_upgrades"
$sharedRoot = Join-Path $projectRoot "native\shared"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"
$work = Join-Path $env:TEMP ("vvfp_titles_harness_build_" + $PID)
New-Item -ItemType Directory -Path $work -Force | Out-Null
$out = Join-Path $work "vvfp_custom_titles_harness.exe"

Push-Location $work
try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo /W4 `
        /DVV_RESET_TESTABLE `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        /I $sharedRoot `
        (Join-Path $nativeRoot "custom_titles_harness.c") `
        (Join-Path $sharedRoot "save_reset.c") `
        /link `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        user32.lib `
        ("/OUT:" + $out)
    if ($LASTEXITCODE -ne 0) { throw "custom titles harness failed to build" }
    & $out
    if ($LASTEXITCODE -ne 0) { throw "custom titles harness reported failures" }
}
finally {
    Pop-Location
    Get-ChildItem -LiteralPath $env:TEMP -Filter "vvfp_titles_harness_*" -Directory -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
