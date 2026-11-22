$ErrorActionPreference = "Stop"

# Builds and runs the 32-bit runtime harness of "VVFP Village Solidarity.dll"
# (native/vvfp_village_solidarity/solidarity_harness.c: the companion's own source with VVFP_TEST) against real
# files in a throwaway "Documents" under %TEMP% (never the player's Documents\LDW).  Each run builds in its own
# folder under %TEMP% and removes it afterwards.  Exit code 0 means every check passed.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_village_solidarity"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

$OutDir = Join-Path $env:TEMP ("vvfp_solidarity_harness_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
Push-Location $OutDir
try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo `
        ("/Fo" + $OutDir + "\") `
        /O2 `
        /MT `
        /W3 `
        /D_CRT_SECURE_NO_WARNINGS `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        (Join-Path $nativeRoot "solidarity_harness.c") `
        (Join-Path $projectRoot "native\shared\save_folder.c") `
        /link `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/OUT:" + (Join-Path $OutDir "solidarity_harness.exe")) `
        kernel32.lib `
        user32.lib `
        shell32.lib `
        advapi32.lib
    if ($LASTEXITCODE -ne 0) {
        throw "Village Solidarity harness compilation failed."
    }
    & (Join-Path $OutDir "solidarity_harness.exe")
    if ($LASTEXITCODE -ne 0) {
        throw "Village Solidarity harness reported failures."
    }
} finally {
    Pop-Location
    Remove-Item -LiteralPath $OutDir -Recurse -Force -ErrorAction SilentlyContinue
}
