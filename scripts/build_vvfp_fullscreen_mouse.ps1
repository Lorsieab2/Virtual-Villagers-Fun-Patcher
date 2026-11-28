$ErrorActionPreference = "Stop"

# Builds "VVFP Fullscreen Mouse.dll" (native\vvfp_fullscreen_mouse), part of Fix Vanilla Bugs in all five games: in
# full screen, or a game window bigger than the game's picture, the mouse acts where the pointer is (SDL 2.0.3's
# SDL_GetMouseState is in window pixels).  Started by "VVFP Fullscreen Mouse.dll".  32-bit, static CRT, like every other companion.  The Fix Vanilla Bugs rows in
# data\builds.json pin the DLL by SHA-256: re-pin them after a rebuild.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_fullscreen_mouse"
$outputRoot = Join-Path $projectRoot "assets\fullscreen_mouse"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
# The intermediate files go to a folder of this run's own, so two builds never share them.
$work = Join-Path ([System.IO.Path]::GetTempPath()) ("vvfp_fullscreen_mouse_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $work -Force | Out-Null

function Invoke-Build([string[]]$extra, [string]$def, [string]$out) {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo `
        /LD `
        /O2 `
        /MT `
        /W4 `
        @extra `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        (Join-Path $nativeRoot "vvfp_fullscreen_mouse.c") `
        ("/Fo" + (Join-Path $work "vvfp_fullscreen_mouse.obj")) `
        /link `
        /Brepro `
        ("/DEF:" + (Join-Path $nativeRoot $def)) `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/IMPLIB:" + (Join-Path $work "vvfp_fullscreen_mouse.lib")) `
        ("/OUT:" + $out) `
        /RELEASE `
        kernel32.lib user32.lib
    if ($LASTEXITCODE -ne 0) {
        throw "Native fullscreen-mouse DLL compilation failed ($out)."
    }
}

try {
    Invoke-Build @() "vvfp_fullscreen_mouse.def" (Join-Path $outputRoot "VVFP Fullscreen Mouse.dll")

    # The TEST build: the same source compiled with VVFP_TEST, which adds the exports the harness uses
    # (vvfp_fullscreen_mouse_test.def).  It goes to tests\test_dlls\ and is never shipped: scripts\build_release.py
    # packages only the DLL above, and tests\test_shipped_dlls_have_no_test_hooks.py fails if a shipped DLL exports
    # a probe.  One script builds both, so they cannot drift apart.
    $testRoot = Join-Path $projectRoot "tests\test_dlls"
    New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
    Invoke-Build @("/DVVFP_TEST") "vvfp_fullscreen_mouse_test.def" (Join-Path $testRoot "VVFP Fullscreen Mouse.test.dll")
} finally {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
