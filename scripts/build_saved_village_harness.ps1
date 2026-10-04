# Build and run the saved-village harness.
#
# native/save_reset_export/saved_village_harness.c includes the SHIPPED
# save_reset_export.c and checks that the reset reads the erased village from
# the slot's own .ldw and builds the exporters' exact header, against synthetic
# saves in a throwaway %TEMP% folder. Pass a real save folder to only READ it
# and print what the reset would identify there.
#
# Each run builds into its own folder under %TEMP% and removes it afterwards.
# One shared %TEMP%\vvfp_saved_village_harness_build made concurrent runs (two
# worktrees, two suites) fail with C1083/LNK1104 or run each other's
# executable, and it was never removed. The executable keeps its basename.
param([string]$ReadFolder = "")
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\save_reset_export"
$sharedRoot = Join-Path $projectRoot "native\shared"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"
$work = Join-Path $env:TEMP ("vvfp_saved_village_harness_build_" + [guid]::NewGuid().ToString("N"))
$out = Join-Path $work "vvfp_saved_village_harness.exe"
New-Item -ItemType Directory -Path $work | Out-Null

try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo `
        /MT `
        ("/Fo" + $work + "\") `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        /I $sharedRoot `
        /I $nativeRoot `
        (Join-Path $nativeRoot "saved_village_harness.c") `
        (Join-Path $sharedRoot "save_reset.c") `
        (Join-Path $sharedRoot "village_identity.c") `
        (Join-Path $sharedRoot "save_folder.c") `
        /link `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        kernel32.lib `
        user32.lib `
        shell32.lib `
        ("/OUT:" + $out)
    if ($LASTEXITCODE -ne 0) { throw "saved village harness failed to build" }

    if ($ReadFolder) {
        & $out $ReadFolder
    } else {
        & $out
    }
    if ($LASTEXITCODE -ne 0) { throw "saved village harness reported failures" }
} finally {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
