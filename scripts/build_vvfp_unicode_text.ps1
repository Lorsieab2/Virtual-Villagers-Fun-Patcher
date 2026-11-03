$ErrorActionPreference = "Stop"

# Builds the two companions made from native\vvfp_unicode_text, 32-bit, static CRT, like every other:
#   "VVFP Unicode Text.dll"  -- Render Unicode with In-Game Fonts (assets\unicode_text)
#   "VVFP Unicode Font.dll"  -- Use Unicode Font (overrides in-game fonts): the same source built with
#                               VVFP_FONT_OVERRIDE (assets\unicode_font)
# Re-run scripts\build_unicode_text_feature.py afterwards: each game's rows pin the DLLs by SHA-256.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_unicode_text"
$sharedRoot = Join-Path $projectRoot "native\shared"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

function Build-Companion([string]$dllName, [string]$defName, [string]$outFolder, [string[]]$defines) {
    $outputRoot = Join-Path $projectRoot $outFolder
    New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
    $work = Join-Path ([System.IO.Path]::GetTempPath()) ("vvfp_unicode_text_" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $work | Out-Null
    Push-Location $work
    try {
        & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
            /nologo `
            /LD `
            /O2 `
            /MT `
            /W4 `
            $defines `
            /I (Join-Path $vsTools "include") `
            /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
            /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
            /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
            (Join-Path $nativeRoot "vvfp_unicode_text.c") `
            (Join-Path $sharedRoot "save_folder.c") `
            /link `
            /Brepro `
            ("/DEF:" + (Join-Path $nativeRoot $defName)) `
            ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
            ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
            ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
            ("/OUT:" + (Join-Path $work $dllName)) `
            /RELEASE `
            kernel32.lib `
            user32.lib `
            gdi32.lib `
            advapi32.lib `
            shell32.lib `
            usp10.lib
        $built = $LASTEXITCODE
        if ($built -eq 0) {
            Copy-Item -LiteralPath (Join-Path $work $dllName) -Destination (Join-Path $outputRoot $dllName) -Force
        }
    } finally {
        Pop-Location
        Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ($built -ne 0) {
        throw "Native $dllName compilation failed."
    }
}

Build-Companion "VVFP Unicode Text.dll" "vvfp_unicode_text.def" "assets\unicode_text" @()
Build-Companion "VVFP Unicode Font.dll" "vvfp_unicode_font.def" "assets\unicode_font" @("/DVVFP_FONT_OVERRIDE")
