$ErrorActionPreference = "Stop"

# Builds "VVFP Scrolling Popups.dll" (Scrolling Popups: all five games) from native\vvfp_scrolling_popups, and its
# TEST build: the same source compiled with VVFP_TEST, which adds the exports the emulation tests read
# (vvfp_scrolling_popups_test.def).  The test build goes to tests\test_dlls\ and is never shipped
# (tests\test_shipped_dlls_have_no_test_hooks.py).  32-bit, static CRT, like every other companion.  The rows
# vvN_scrolling_popups (data\vvN_scrolling_popups_feature.json) pin the shipped DLL by SHA-256:
# scripts\build_scrolling_popups_features.py runs this script and re-pins them.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_scrolling_popups"
$outputRoot = Join-Path $projectRoot "assets\scrolling_popups"
$testRoot = Join-Path $projectRoot "tests\test_dlls"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
New-Item -ItemType Directory -Path $testRoot -Force | Out-Null

function Build-ScrollingPopups([string]$defines, [string]$def, [string]$name, [string]$destination) {
    $work = Join-Path ([System.IO.Path]::GetTempPath()) ("vvfp_scrolling_popups_" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $work | Out-Null
    $arguments = @("/nologo", "/LD", "/O2", "/MT", "/W4")
    if ($defines) { $arguments += $defines }
    $arguments += @(
        "/I", (Join-Path $vsTools "include"),
        "/I", (Join-Path $sdkRoot "Include\$sdkVersion\um"),
        "/I", (Join-Path $sdkRoot "Include\$sdkVersion\shared"),
        "/I", (Join-Path $sdkRoot "Include\$sdkVersion\ucrt"),
        (Join-Path $nativeRoot "vvfp_scrolling_popups.c"),
        "/link", "/Brepro",
        ("/DEF:" + (Join-Path $nativeRoot $def)),
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")),
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")),
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")),
        ("/OUT:" + (Join-Path $work $name)),
        "/RELEASE",
        "kernel32.lib"
    )
    Push-Location $work
    try {
        & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") @arguments
        $built = $LASTEXITCODE
        if ($built -eq 0) {
            Copy-Item -LiteralPath (Join-Path $work $name) -Destination (Join-Path $destination $name) -Force
        }
    } finally {
        Pop-Location
        Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ($built -ne 0) {
        throw "Native Scrolling Popups DLL compilation failed ($name)."
    }
}

Build-ScrollingPopups "" "vvfp_scrolling_popups.def" "VVFP Scrolling Popups.dll" $outputRoot

# The TEST build: never shipped.
Build-ScrollingPopups "/DVVFP_TEST" "vvfp_scrolling_popups_test.def" "VVFP Scrolling Popups.test.dll" $testRoot
