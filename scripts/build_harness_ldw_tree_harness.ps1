# Build and run the harness for native/shared/harness_ldw_tree.h, the cleanup
# every LDW-writing harness uses. It redirects Documents to a throwaway folder
# under %TEMP% and never touches the real one. Exit code 0 means every check
# passed.
#
# Each run builds into its own folder under %TEMP% and removes it afterwards,
# never in the repository. One shared %TEMP% folder made concurrent runs (two
# worktrees, two suites) fail with C1083/LNK1104 or run each other's
# executable. The executable keeps its basename.
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$sharedRoot = Join-Path $projectRoot "native\shared"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"
$outDir = Join-Path $env:TEMP ("vvfp_harness_ldw_tree_harness_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $outDir | Out-Null
$out = Join-Path $outDir "harness_ldw_tree_harness.exe"

try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo `
        ("/Fo" + $outDir + "\") `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        (Join-Path $sharedRoot "harness_ldw_tree_harness.c") `
        /link `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        user32.lib `
        shell32.lib `
        ("/OUT:" + $out)
    if ($LASTEXITCODE -ne 0) { throw "harness_ldw_tree harness failed to build" }

    & $out
    if ($LASTEXITCODE -ne 0) { throw "harness_ldw_tree harness reported failures" }
}
finally {
    Remove-Item -LiteralPath $outDir -Recurse -Force -ErrorAction SilentlyContinue
}
