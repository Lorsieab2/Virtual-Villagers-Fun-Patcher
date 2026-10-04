# Build and run the on-disk reset harness.
#
# tests/test_village_history_and_log_folders.py reads this harness as TEXT --
# it checks that the cases are written, not that they pass. The properties the
# harness asserts are about real files on a real disk, so they can only be
# established by running it, which
# tests/test_start_over_reset_without_origins.py (SaveResetHarnessRunsTests)
# does whenever the 32-bit MSVC toolchain is installed.
#
# Each run builds into its own folder under %TEMP%. One shared
# %TEMP%\vvfp_save_reset_harness.exe made concurrent runs (two worktrees, two
# suites) fail with LNK1104 or run each other's executable, and the objects
# landed in whatever the current directory was. The executable keeps its
# basename, which names its LDW save folder and the harness_ldw_tree.h mutex
# that serialises the runs themselves.
#
# VV_RESET_TESTABLE exposes the reset's internal guards to the harness.
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$sharedRoot = Join-Path $projectRoot "native\shared"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"
$outDir = Join-Path $env:TEMP ("vvfp_save_reset_harness_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $outDir | Out-Null
$out = Join-Path $outDir "vvfp_save_reset_harness.exe"

try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo `
        /DVV_RESET_TESTABLE `
        ("/Fo" + $outDir + "\") `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        /I $sharedRoot `
        (Join-Path $sharedRoot "save_reset_harness.c") `
        (Join-Path $sharedRoot "save_reset.c") `
        (Join-Path $sharedRoot "save_folder.c") `
        /link `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        user32.lib `
        shell32.lib `
        ("/OUT:" + $out)
    if ($LASTEXITCODE -ne 0) { throw "save reset harness failed to build" }

    & $out
    if ($LASTEXITCODE -ne 0) { throw "save reset harness reported failures" }
}
finally {
    Remove-Item -LiteralPath $outDir -Recurse -Force -ErrorAction SilentlyContinue
}
