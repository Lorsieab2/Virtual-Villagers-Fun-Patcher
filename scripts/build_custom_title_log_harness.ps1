# Build and run the custom title log harness
# (native/population_export/custom_title_log_harness.c): the population
# exporter compiled unchanged against a %TEMP% save folder (never
# Documents\LDW).  32-bit, like the companion.
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\population_export"
$sharedRoot = Join-Path $projectRoot "native\shared"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"
$work = Join-Path $env:TEMP ("vvfp_title_log_harness_build_" + $PID)
New-Item -ItemType Directory -Path $work -Force | Out-Null
$out = Join-Path $work "vvfp_custom_title_log_harness.exe"

Push-Location $work
try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        /I $sharedRoot `
        /I $nativeRoot `
        (Join-Path $nativeRoot "custom_title_log_harness.c") `
        (Join-Path $sharedRoot "village_identity.c") `
        /link `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        user32.lib `
        ("/OUT:" + $out)
    if ($LASTEXITCODE -ne 0) { throw "custom title log harness failed to build" }
    & $out
    if ($LASTEXITCODE -ne 0) { throw "custom title log harness reported failures" }
}
finally {
    Pop-Location
    Get-ChildItem -LiteralPath $env:TEMP -Filter "vvfp_title_log_harness_*" -Directory -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
