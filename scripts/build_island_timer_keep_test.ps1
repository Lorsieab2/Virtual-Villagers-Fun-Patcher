$ErrorActionPreference = "Stop"

# Builds the TEST build of native\shared\island_timer_keep.h -- the keeper
# every Origins companion compiles so that bought island events leave the
# game's own island-event timer as it was -- with all five games' sites and
# stubs, for tests\test_bought_events_keep_natural_timer.py.  32-bit, static
# CRT.  Goes to tests\test_dlls\ and is never shipped (the companions that
# ship this code are rebuilt by their own scripts).

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\shared"
$testRoot = Join-Path $projectRoot "tests\test_dlls"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"
$work = Join-Path $env:TEMP ("vvfp_island_timer_" + [guid]::NewGuid().ToString("N"))

New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
New-Item -ItemType Directory -Path $work -Force | Out-Null
try {
    $arguments = @(
        "/nologo", "/LD", "/O2", "/MT", "/W4", "/DVVFP_TEST",
        "/I", (Join-Path $vsTools "include"),
        "/I", (Join-Path $sdkRoot "Include\$sdkVersion\um"),
        "/I", (Join-Path $sdkRoot "Include\$sdkVersion\shared"),
        "/I", (Join-Path $sdkRoot "Include\$sdkVersion\ucrt"),
        ("/Fo" + $work + "\"),
        (Join-Path $nativeRoot "island_timer_keep_test.c"),
        "/link", "/Brepro",
        ("/DEF:" + (Join-Path $nativeRoot "island_timer_keep_test.def")),
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")),
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")),
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")),
        ("/IMPLIB:" + (Join-Path $work "island_timer_keep_test.lib")),
        ("/OUT:" + (Join-Path $testRoot "VVFP Island Event Timer.test.dll")),
        "/RELEASE",
        "kernel32.lib"
    )
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Island event timer test DLL compilation failed."
    }
} finally {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
