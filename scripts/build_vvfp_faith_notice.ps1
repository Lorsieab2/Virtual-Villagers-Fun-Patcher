$ErrorActionPreference = "Stop"

# Builds "VVFP Faith Notice.dll" (Popup When Believers Become Heathens, New Believers) from
# native\vvfp_faith_notice.  32-bit, static CRT, like every other companion.  Re-run
# scripts\build_faith_notice_feature.py afterwards: the row pins the DLL by SHA-256.  The tests drive the
# shipped DLL itself (tests\test_faith_notice.py); it has no test build.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_faith_notice"
$outputRoot = Join-Path $projectRoot "assets\faith_notice"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
$work = Join-Path ([System.IO.Path]::GetTempPath()) ("vvfp_faith_notice_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $work | Out-Null

Push-Location $work
try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo `
        /LD `
        /O2 `
        /MT `
        /W4 `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        (Join-Path $nativeRoot "vvfp_faith_notice.c") `
        /link `
        /Brepro `
        ("/DEF:" + (Join-Path $nativeRoot "vvfp_faith_notice.def")) `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/OUT:" + (Join-Path $work "VVFP Faith Notice.dll")) `
        /RELEASE `
        kernel32.lib `
        shell32.lib `
        user32.lib
    $built = $LASTEXITCODE
    if ($built -eq 0) {
        Copy-Item -LiteralPath (Join-Path $work "VVFP Faith Notice.dll") -Destination (Join-Path $outputRoot "VVFP Faith Notice.dll") -Force
    }
} finally {
    Pop-Location
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
if ($built -ne 0) {
    throw "Native Faith Notice DLL compilation failed."
}
