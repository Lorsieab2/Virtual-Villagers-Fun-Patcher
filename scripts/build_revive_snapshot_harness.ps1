param(
    [Parameter(Mandatory = $true)][string]$Docs
)

$ErrorActionPreference = "Stop"

# Builds and runs the 32-bit harness for the Revive snapshots (native/vvfp_cause_of_death/
# revive_snapshot_harness.c): every game's departure kept whole, written at the save to the slot's own file,
# and restored field for field.  The harness compiles the Cause of Death source in with the Documents folder
# redirected to -Docs, so every file it writes is under that folder, never the real Documents\LDW.  The
# executable is built in its own folder under %TEMP%, removed afterwards.  Exit code 0 means every check passed.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_cause_of_death"
$sharedRoot = Join-Path $projectRoot "native\shared"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

$outDir = Join-Path $env:TEMP ("vvfp_revive_snapshot_harness_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $outDir -Force | Out-Null
Push-Location $outDir
try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo `
        ("/Fo" + $outDir + "\") `
        /O2 `
        /MT `
        /W4 `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        /I $sharedRoot `
        /I $nativeRoot `
        (Join-Path $nativeRoot "revive_snapshot_harness.c") `
        /link `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/OUT:" + (Join-Path $outDir "revive_snapshot_harness.exe")) `
        kernel32.lib `
        user32.lib `
        shell32.lib
    if ($LASTEXITCODE -ne 0) {
        throw "Revive snapshot harness compilation failed."
    }
    New-Item -ItemType Directory -Path $Docs -Force | Out-Null
    & (Join-Path $outDir "revive_snapshot_harness.exe") $Docs
    if ($LASTEXITCODE -ne 0) {
        throw "Revive snapshot harness reported failures."
    }
} finally {
    Pop-Location
    Remove-Item -LiteralPath $outDir -Recurse -Force -ErrorAction SilentlyContinue
}
