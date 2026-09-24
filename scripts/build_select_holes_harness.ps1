# Build and run the select_log_file hole harness.
#
# What select_log_file returns when a reset has left holes cannot be
# established by reading the source. This builds the layout on disk -- village
# A's files 1 and 3 deleted, village B surviving at 2 and 4 -- and asks the
# real function.
#
# VV_PARENTAGE_TESTABLE exposes the layout table and the log folder to the
# harness; the shipped DLL is built without it and is unchanged.
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\parentage_export"
$sharedRoot = Join-Path $projectRoot "native\shared"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"
$out = Join-Path $env:TEMP "vvfp_select_holes_harness.exe"

& (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
    /nologo `
    /DVV_PARENTAGE_TESTABLE `
    /I (Join-Path $vsTools "include") `
    /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
    /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
    /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
    /I $sharedRoot `
    (Join-Path $nativeRoot "select_holes_harness.c") `
    (Join-Path $nativeRoot "parentage_export.c") `
    (Join-Path $sharedRoot "village_identity.c") `
    (Join-Path $sharedRoot "save_folder.c") `
    /link `
    ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
    ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
    user32.lib `
    shell32.lib `
    ("/OUT:" + $out)
if ($LASTEXITCODE -ne 0) { throw "select-holes harness failed to build" }

& $out
if ($LASTEXITCODE -ne 0) { throw "select-holes harness reported failures" }
