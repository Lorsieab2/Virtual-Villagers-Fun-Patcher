# Build and run the custom titles harness (native/vvfp_story_upgrades/custom_titles_harness.c).
#
# The companion's own title store and the Start Over reset, compiled unchanged
# against real files in a fresh folder under %TEMP% (the harness supplies the
# save folder; it never touches Documents\LDW).  32-bit, like the companion.
#
# Each run builds into its own folder under %TEMP% and removes it afterwards.
# The harness is run with TEMP and TMP pointing into that folder, so the save
# folder it makes (<temp>\vvfp_titles_harness_<pid>) is removed with it. This
# script used to delete every %TEMP%\vvfp_titles_harness_* folder instead,
# which deleted a concurrent run's save folder from under it. The executable
# keeps its basename.
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_story_upgrades"
$sharedRoot = Join-Path $projectRoot "native\shared"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"
$work = Join-Path $env:TEMP ("vvfp_titles_harness_build_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $work | Out-Null
$out = Join-Path $work "vvfp_custom_titles_harness.exe"
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
        (Join-Path $nativeRoot "custom_titles_harness.c") `
        (Join-Path $sharedRoot "save_reset.c") `
        /link `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        user32.lib `
        ("/OUT:" + $out)
    if ($LASTEXITCODE -ne 0) { throw "custom titles harness failed to build" }
    $env:TEMP = $work
    $env:TMP = $work
    & $out
    if ($LASTEXITCODE -ne 0) { throw "custom titles harness reported failures" }
}
finally {
    $env:TEMP = $savedTemp
    $env:TMP = $savedTmp
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
