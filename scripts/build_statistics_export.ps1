$ErrorActionPreference = "Stop"

# Builds "VVFP Statistics Export.dll" (the Village Statistics companion) from
# native\statistics_export, and its TEST build: the same source compiled with
# VVFP_TEST, which adds the seam the first-load reconcile's harness drives
# (statistics_export_test.def).  The test build goes to tests\test_dlls\ and
# is never shipped (tests\test_shipped_dlls_have_no_test_hooks.py).

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\statistics_export"
$sharedRoot = Join-Path $projectRoot "native\shared"
$outputRoot = Join-Path $projectRoot "assets\statistics"
$testRoot = Join-Path $projectRoot "tests\test_dlls"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
New-Item -ItemType Directory -Path $testRoot -Force | Out-Null

function Build-Statistics([string]$defines, [string]$def, [string]$out) {
    $arguments = @("/nologo", "/LD", "/O2", "/MT")
    if ($defines) { $arguments += $defines }
    $arguments += @(
        "/I", (Join-Path $vsTools "include"),
        "/I", (Join-Path $sdkRoot "Include\$sdkVersion\um"),
        "/I", (Join-Path $sdkRoot "Include\$sdkVersion\shared"),
        "/I", (Join-Path $sdkRoot "Include\$sdkVersion\ucrt"),
        "/I", $sharedRoot,
        (Join-Path $nativeRoot "statistics_export.c"),
        (Join-Path $nativeRoot "village_elders.c"),
        (Join-Path $nativeRoot "statistics_store.c"),
        (Join-Path $nativeRoot "roster_match.c"),
        (Join-Path $sharedRoot "village_identity.c"),
        (Join-Path $sharedRoot "save_folder.c"),
        "/link",
        ("/DEF:" + (Join-Path $nativeRoot $def)),
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")),
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")),
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")),
        ("/OUT:" + $out),
        "/RELEASE",
        "kernel32.lib",
        "shell32.lib"
    )
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Native statistics DLL compilation failed ($out)."
    }
}

Build-Statistics "" "statistics_export.def" (Join-Path $outputRoot "VVFP Statistics Export.dll")
Build-Statistics "/DVVFP_TEST" "statistics_export_test.def" (Join-Path $testRoot "VVFP Statistics Export.test.dll")

@(
    (Join-Path $projectRoot "statistics_export.obj"),
    (Join-Path $projectRoot "village_elders.obj"),
    (Join-Path $projectRoot "statistics_store.obj"),
    (Join-Path $projectRoot "roster_match.obj"),
    (Join-Path $projectRoot "village_identity.obj"),
    (Join-Path $projectRoot "save_folder.obj"),
    (Join-Path $projectRoot "statistics_export.exp"),
    (Join-Path $projectRoot "statistics_export.lib"),
    (Join-Path $outputRoot "VVFP Statistics Export.exp"),
    (Join-Path $outputRoot "VVFP Statistics Export.lib"),
    (Join-Path $testRoot "VVFP Statistics Export.test.exp"),
    (Join-Path $testRoot "VVFP Statistics Export.test.lib")
) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Remove-Item -LiteralPath $_
}
