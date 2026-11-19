$ErrorActionPreference = "Stop"

# Builds "VVFP Village Solidarity.dll" (Village Solidarity: the village's score, its odds factor and the Tech screen
# counter, all five games) from native\vvfp_village_solidarity, and its TEST build (VVFP_TEST: the probe exports
# tests\test_village_solidarity.py drives) into tests\test_dlls.  32-bit, static CRT, like every other companion.
# Re-run scripts\build_village_solidarity_feature.py afterwards: the rows pin the DLL by SHA-256.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_village_solidarity"
$outputRoot = Join-Path $projectRoot "assets\village_solidarity"
$testRoot = Join-Path $projectRoot "tests\test_dlls"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
New-Item -ItemType Directory -Path $testRoot -Force | Out-Null

function Build-Solidarity([string]$defines, [string]$def, [string]$name, [string]$destination) {
    $work = Join-Path ([System.IO.Path]::GetTempPath()) ("vvfp_village_solidarity_" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $work | Out-Null
    Push-Location $work
    try {
        $arguments = @("/nologo", "/LD", "/O2", "/MT", "/W4")
        if ($defines) { $arguments += $defines }
        $arguments += @(
            "/I", (Join-Path $vsTools "include"),
            "/I", (Join-Path $sdkRoot "Include\$sdkVersion\um"),
            "/I", (Join-Path $sdkRoot "Include\$sdkVersion\shared"),
            "/I", (Join-Path $sdkRoot "Include\$sdkVersion\ucrt"),
            (Join-Path $nativeRoot "vvfp_village_solidarity.c"),
            (Join-Path $projectRoot "native\shared\save_folder.c"),
            "/link", "/Brepro",
            ("/DEF:" + (Join-Path $nativeRoot $def)),
            ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")),
            ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")),
            ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")),
            ("/OUT:" + (Join-Path $work $name)),
            "/RELEASE",
            "kernel32.lib", "user32.lib", "shell32.lib"
        )
        & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") @arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Native Village Solidarity DLL compilation failed ($name)."
        }
        Copy-Item -LiteralPath (Join-Path $work $name) -Destination $destination -Force
    } finally {
        Pop-Location
        Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Build-Solidarity "" "vvfp_village_solidarity.def" "VVFP Village Solidarity.dll" `
    (Join-Path $outputRoot "VVFP Village Solidarity.dll")
Build-Solidarity "/DVVFP_TEST" "vvfp_village_solidarity_test.def" "VVFP Village Solidarity.test.dll" `
    (Join-Path $testRoot "VVFP Village Solidarity.test.dll")
