# Build and run the header/slot harness
# (native/save_reset_export/header_slot_harness.c).
#
# Each run builds into its own folder under %TEMP% and removes it afterwards.
# One shared %TEMP%\vvfp_header_slot_harness.exe made concurrent runs (two
# worktrees, two suites) fail with LNK1104 or run each other's executable, and
# the object file landed in whatever the current directory was. The executable
# keeps its basename.
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\save_reset_export"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"
$outDir = Join-Path $env:TEMP ("vvfp_header_slot_harness_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $outDir | Out-Null
$out = Join-Path $outDir "vvfp_header_slot_harness.exe"

try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo `
        ("/Fo" + $outDir + "\") `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        (Join-Path $nativeRoot "header_slot_harness.c") `
        /link `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        user32.lib `
        ("/OUT:" + $out)
    if ($LASTEXITCODE -ne 0) { throw "header/slot harness failed to build" }

    & $out
    if ($LASTEXITCODE -ne 0) { throw "header/slot harness reported failures" }
}
finally {
    Remove-Item -LiteralPath $outDir -Recurse -Force -ErrorAction SilentlyContinue
}
