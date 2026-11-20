$ErrorActionPreference = "Stop"

# Builds "VVFP Herb Study.dll" (native\vvfp_herb_study), part of Fix Vanilla Bugs in A New Home and The Lost
# Children: every herb study gives Healing practice (A New Home's first studies), and The Lost Children's study
# continuation re-studies herbs 3 and 4 too.  32-bit, static CRT, like every other companion.  The Fix Vanilla Bugs
# rows in data\builds.json pin the DLL by SHA-256 (their companion_files entry): re-pin them after a rebuild.
# Also builds the TEST build (VVFP_TEST: the probe export the tests drive) into tests\test_dlls\, never shipped.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_herb_study"
$outputRoot = Join-Path $projectRoot "assets\herb_study"
$testRoot = Join-Path $projectRoot "tests\test_dlls"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
$work = Join-Path ([System.IO.Path]::GetTempPath()) ("vvfp_herb_study_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $work | Out-Null
Push-Location $work
$built = 1
try {
    foreach ($variant in @(
            @{ Def = "vvfp_herb_study.def"; Out = "VVFP Herb Study.dll"; Dest = $outputRoot; Flags = @() },
            @{ Def = "vvfp_herb_study_test.def"; Out = "VVFP Herb Study.test.dll"; Dest = $testRoot; Flags = @("/DVVFP_TEST") })) {
        & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
            /nologo /LD /O2 /MT /W4 @($variant.Flags) `
            /I (Join-Path $vsTools "include") `
            /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
            /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
            /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
            (Join-Path $nativeRoot "vvfp_herb_study.c") `
            /link /Brepro `
            ("/DEF:" + (Join-Path $nativeRoot $variant.Def)) `
            ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
            ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
            ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
            ("/OUT:" + (Join-Path $work $variant.Out)) `
            /RELEASE `
            kernel32.lib
        $built = $LASTEXITCODE
        if ($built -ne 0) { break }
        Copy-Item -LiteralPath (Join-Path $work $variant.Out) -Destination (Join-Path $variant.Dest $variant.Out) -Force
    }
} finally {
    Pop-Location
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
if ($built -ne 0) {
    throw "Native herb-study DLL compilation failed."
}
