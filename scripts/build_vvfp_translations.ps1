$ErrorActionPreference = "Stop"

# Builds "VVFP Translations.dll" (the game's text in the player's language, all five games) from
# native\vvfp_translations.  32-bit, static CRT, like every other companion.  The exe literal sites come from
# native\vvfp_translations\tr_sites.inc when it is there (the generated list), else from
# tr_sites_placeholder.inc (a few stock sites, enough for the runtime tests).

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_translations"
$outputRoot = Join-Path $projectRoot "assets\translations"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null

$sitesDefine = @()
if (Test-Path -LiteralPath (Join-Path $nativeRoot "tr_sites.inc")) {
    $sitesDefine = @("/DTR_HAVE_SITES")
}

Push-Location $projectRoot
try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo `
        /LD `
        /O2 `
        /MT `
        /W4 `
        $sitesDefine `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        (Join-Path $nativeRoot "vvfp_translations.c") `
        /link `
        /Brepro `
        ("/DEF:" + (Join-Path $nativeRoot "vvfp_translations.def")) `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/OUT:" + (Join-Path $outputRoot "VVFP Translations.dll")) `
        /RELEASE `
        kernel32.lib `
        user32.lib
    $built = $LASTEXITCODE
} finally {
    Pop-Location
}

@(
    (Join-Path $projectRoot "vvfp_translations.obj"),
    (Join-Path $projectRoot "vvfp_translations.exp"),
    (Join-Path $projectRoot "vvfp_translations.lib"),
    (Join-Path $outputRoot "VVFP Translations.exp"),
    (Join-Path $outputRoot "VVFP Translations.lib")
) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Remove-Item -LiteralPath $_
}
if ($built -ne 0) {
    throw "Native translations DLL compilation failed."
}
