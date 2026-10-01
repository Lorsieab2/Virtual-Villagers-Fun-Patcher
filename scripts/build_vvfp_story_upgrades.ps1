$ErrorActionPreference = "Stop"

# Builds "VVFP Story Upgrades.dll" (the companion of the five Story / Cheat
# Upgrades rows) from native\vvfp_story_upgrades.  32-bit, static CRT, like
# every other companion.  Run scripts\build_story_cheat_upgrades_features.py
# first (it writes story_tables.h) and again afterwards (it pins this DLL's
# SHA-256 in the five rows).

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_story_upgrades"
$outputRoot = Join-Path $projectRoot "assets\story_upgrades"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null

& (Join-Path $sdkRoot "bin\$sdkVersion\x86\rc.exe") `
    /nologo `
    /fo (Join-Path $outputRoot "vvfp_story_upgrades.res") `
    (Join-Path $nativeRoot "vvfp_story_upgrades.rc")
if ($LASTEXITCODE -ne 0) {
    throw "Resource compilation failed."
}

function Build-Story([string]$defines, [string]$def, [string]$out) {
    $arguments = @(
        "/nologo", "/LD", "/O2", "/MT", "/W4"
    )
    if ($defines) { $arguments += $defines }
    $arguments += @(
        "/I", (Join-Path $vsTools "include"),
        "/I", (Join-Path $sdkRoot "Include\$sdkVersion\um"),
        "/I", (Join-Path $sdkRoot "Include\$sdkVersion\shared"),
        "/I", (Join-Path $sdkRoot "Include\$sdkVersion\ucrt"),
        (Join-Path $nativeRoot "vvfp_story_upgrades.c"),
        (Join-Path $projectRoot "native\shared\save_folder.c"),
        (Join-Path $outputRoot "vvfp_story_upgrades.res"),
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
        throw "Native story-upgrades DLL compilation failed ($out)."
    }
}

Build-Story "" "vvfp_story_upgrades.def" (Join-Path $outputRoot "VVFP Story Upgrades.dll")

# The TEST build: the same source compiled with VVFP_TEST, which adds the
# probe exports and counters the tests drive.  It goes to tests\test_dlls\
# and is never shipped.
$testRoot = Join-Path $projectRoot "tests\test_dlls"
New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
Build-Story "/DVVFP_TEST" "vvfp_story_upgrades_test.def" (Join-Path $testRoot "VVFP Story Upgrades.test.dll")

@(
    (Join-Path $outputRoot "vvfp_story_upgrades.res"),
    (Join-Path $projectRoot "vvfp_story_upgrades.obj"),
    (Join-Path $projectRoot "save_folder.obj"),
    (Join-Path $projectRoot "vvfp_story_upgrades.exp"),
    (Join-Path $projectRoot "vvfp_story_upgrades.lib"),
    (Join-Path $outputRoot "VVFP Story Upgrades.exp"),
    (Join-Path $outputRoot "VVFP Story Upgrades.lib"),
    (Join-Path $testRoot "VVFP Story Upgrades.test.exp"),
    (Join-Path $testRoot "VVFP Story Upgrades.test.lib")
) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Remove-Item -LiteralPath $_
}
