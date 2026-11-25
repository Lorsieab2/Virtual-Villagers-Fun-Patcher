$ErrorActionPreference = "Stop"

# Builds and runs the 32-bit runtime harness of "VVFP Founder X Buttons.dll"
# (native/vvfp_founder_x_buttons/founder_x_harness.c: the companion's own source driven against a fake "Select 5
# villagers" screen and villager table, The Tree of Life's and New Believers' layouts, 150 and 256 records).  It
# touches no file.  Each run builds in its own folder under %TEMP% and removes it afterwards.  Exit code 0 means every
# check passed.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_founder_x_buttons"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

$OutDir = Join-Path $env:TEMP ("vvfp_founder_x_harness_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
Push-Location $OutDir
try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo `
        ("/Fo" + $OutDir + "\") `
        /O2 `
        /MT `
        /W4 `
        /D_CRT_SECURE_NO_WARNINGS `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        (Join-Path $nativeRoot "founder_x_harness.c") `
        /link `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/OUT:" + (Join-Path $OutDir "founder_x_harness.exe")) `
        kernel32.lib
    if ($LASTEXITCODE -ne 0) {
        throw "Founder X Buttons harness compilation failed."
    }
    & (Join-Path $OutDir "founder_x_harness.exe")
    if ($LASTEXITCODE -ne 0) {
        throw "Founder X Buttons harness reported failures."
    }
} finally {
    Pop-Location
    Remove-Item -LiteralPath $OutDir -Recurse -Force -ErrorAction SilentlyContinue
}
