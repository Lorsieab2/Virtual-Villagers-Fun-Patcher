param(
    [Parameter(Mandatory = $true)][string]$Docs
)

$ErrorActionPreference = "Stop"

# Builds and runs the 32-bit harness for a death recorded in a session whose
# village was made in that session (native/vvfp_cause_of_death/
# save_slot_harness.c).  The harness compiles the Cause of Death source in
# with the Documents folder redirected to -Docs, so every file it writes is
# under that folder, never the real Documents\LDW.  Each game and host mode
# runs as two processes -- two game sessions -- in a fresh folder of its own.
# The executable is built in its own folder under %TEMP%, removed afterwards.
# Exit code 0 means every check passed.

$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\vvfp_cause_of_death"
$sharedRoot = Join-Path $projectRoot "native\shared"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

$outDir = Join-Path $env:TEMP ("vvfp_cause_save_slot_harness_" + [guid]::NewGuid().ToString("N"))
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
        (Join-Path $nativeRoot "save_slot_harness.c") `
        /link `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/OUT:" + (Join-Path $outDir "save_slot_harness.exe")) `
        kernel32.lib `
        user32.lib `
        shell32.lib
    if ($LASTEXITCODE -ne 0) {
        throw "Cause of Death save-slot harness compilation failed."
    }
    $failed = $false
    foreach ($game in @("1", "2")) {
        foreach ($mode in @("host", "zero")) {
            $folder = Join-Path $Docs ("game" + $game + "_" + $mode)
            New-Item -ItemType Directory -Path $folder -Force | Out-Null
            foreach ($phase in @("write", "read")) {
                & (Join-Path $outDir "save_slot_harness.exe") $phase $folder $game $mode
                if ($LASTEXITCODE -ne 0) {
                    $failed = $true
                }
            }
        }
    }
    if ($failed) {
        throw "Cause of Death save-slot harness reported failures."
    }
} finally {
    Pop-Location
    Remove-Item -LiteralPath $outDir -Recurse -Force -ErrorAction SilentlyContinue
}
