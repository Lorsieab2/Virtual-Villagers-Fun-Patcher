$ErrorActionPreference = "Stop"

# Builds "VVFP Cause of Death.dll" (the companion of the five Cause of Death
# rows) from native\vvfp_cause_of_death.  32-bit, static CRT, like every
# other companion.  Run scripts\build_cause_of_death_features.py afterwards:
# the five rows pin this DLL by SHA-256.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_cause_of_death"
$sharedRoot = Join-Path $projectRoot "native\shared"
$outputRoot = Join-Path $projectRoot "assets\cause_of_death"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null

function Build-Cause([string]$defines, [string]$def, [string]$out) {
    $arguments = @(
        "/nologo", "/LD", "/O2", "/MT", "/W4"
    )
    if ($defines) { $arguments += $defines }
    $arguments += @(
        "/I", (Join-Path $vsTools "include"),
        "/I", (Join-Path $sdkRoot "Include\$sdkVersion\um"),
        "/I", (Join-Path $sdkRoot "Include\$sdkVersion\shared"),
        "/I", (Join-Path $sdkRoot "Include\$sdkVersion\ucrt"),
        "/I", $sharedRoot,
        (Join-Path $nativeRoot "vvfp_cause_of_death.c"),
        (Join-Path $sharedRoot "save_folder.c"),
        "/link", "/Brepro",
        ("/DEF:" + (Join-Path $nativeRoot $def)),
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")),
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")),
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")),
        ("/OUT:" + $out),
        "/RELEASE",
        "kernel32.lib", "user32.lib", "shell32.lib"
    )
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Native cause-of-death DLL compilation failed ($out)."
    }
}

Build-Cause "" "vvfp_cause_of_death.def" (Join-Path $outputRoot "VVFP Cause of Death.dll")

# The TEST build: the same source compiled with VVFP_TEST, which adds the
# counters and the forced epitaph roll the tests drive
# (vvfp_cause_of_death_test.def).  It goes to tests\test_dlls\ and is never
# shipped: scripts\build_release.py packages only the DLL above, and
# tests\test_shipped_dlls_have_no_test_hooks.py fails if a shipped DLL
# exports a probe.
$testRoot = Join-Path $projectRoot "tests\test_dlls"
New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
Build-Cause "/DVVFP_TEST" "vvfp_cause_of_death_test.def" (Join-Path $testRoot "VVFP Cause of Death.test.dll")

@(
    (Join-Path $projectRoot "vvfp_cause_of_death.obj"),
    (Join-Path $projectRoot "save_folder.obj"),
    (Join-Path $projectRoot "vvfp_cause_of_death.exp"),
    (Join-Path $projectRoot "vvfp_cause_of_death.lib"),
    (Join-Path $outputRoot "VVFP Cause of Death.exp"),
    (Join-Path $outputRoot "VVFP Cause of Death.lib"),
    (Join-Path $testRoot "VVFP Cause of Death.test.exp"),
    (Join-Path $testRoot "VVFP Cause of Death.test.lib")
) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Remove-Item -LiteralPath $_
}
