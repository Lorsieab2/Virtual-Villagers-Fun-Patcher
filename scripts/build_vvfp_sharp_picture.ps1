$ErrorActionPreference = "Stop"

# Builds "VVFP Sharp Picture.dll" (native\vvfp_sharp_picture), the 4K filter: the game's picture drawn sharp at the
# screen's own size by a Direct3D 9Ex device of its own.  Its shaders (sharp_picture.hlsl) are compiled first with
# the Windows SDK's fxc into headers the DLL includes (shader model 3, optimised).  32-bit, static CRT, like every
# other companion.  The row's data pins the DLL by SHA-256: re-pin it after a rebuild.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_sharp_picture"
$outputRoot = Join-Path $projectRoot "assets\sharp_picture"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"
$fxc = Join-Path $sdkRoot "bin\$sdkVersion\x86\fxc.exe"

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
# The intermediate files go to a folder of this run's own, so two builds never share them.
$work = Join-Path ([System.IO.Path]::GetTempPath()) ("vvfp_sharp_picture_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $work -Force | Out-Null

function Invoke-Shader([string]$entry, [string]$profile) {
    & $fxc /nologo /T $profile /E $entry /O3 `
        /Vn ("g_sp_" + $entry) /Fh (Join-Path $work ("sharp_picture_" + $entry + ".h")) `
        (Join-Path $nativeRoot "sharp_picture.hlsl") | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Shader compilation failed ($entry)."
    }
}

function Invoke-Build([string[]]$extra, [string]$def, [string]$out) {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo `
        /LD `
        /O2 `
        /MT `
        /W4 `
        @extra `
        /I $work `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        (Join-Path $nativeRoot "vvfp_sharp_picture.c") `
        ("/Fo" + (Join-Path $work "vvfp_sharp_picture.obj")) `
        /link `
        /Brepro `
        ("/DEF:" + (Join-Path $nativeRoot $def)) `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/IMPLIB:" + (Join-Path $work "vvfp_sharp_picture.lib")) `
        ("/OUT:" + $out) `
        /RELEASE `
        kernel32.lib user32.lib gdi32.lib
    if ($LASTEXITCODE -ne 0) {
        throw "Native sharp-picture DLL compilation failed ($out)."
    }
}

try {
    Invoke-Shader "vs_quad" "vs_3_0"
    foreach ($entry in @("ed_step1", "ed_step2", "fit_rows", "fit_columns")) {
        Invoke-Shader $entry "ps_3_0"
    }
    Invoke-Build @() "vvfp_sharp_picture.def" (Join-Path $outputRoot "VVFP Sharp Picture.dll")

    # The TEST build: the same source compiled with VVFP_TEST, which adds the exports the harness uses (the last
    # picture drawn; the mapped copy of the game).  It goes to tests\test_dlls\ and is never shipped.
    $testRoot = Join-Path $projectRoot "tests\test_dlls"
    New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
    Invoke-Build @("/DVVFP_TEST") "vvfp_sharp_picture_test.def" (Join-Path $testRoot "VVFP Sharp Picture.test.dll")
} finally {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
