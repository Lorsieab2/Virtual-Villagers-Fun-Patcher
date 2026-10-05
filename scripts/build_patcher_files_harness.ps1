$ErrorActionPreference = "Stop"

# Builds and runs the 32-bit runtime harness for native/shared/patcher_files.h
# (where every companion finds the patcher's files, and how it loads one: the
# "Virtual Villagers Fun Patcher Files" folder beside the executable, by full
# path, with the wide API). It works only in a scratch folder under %TEMP%
# (a Unicode-named game folder is made there) and loads a copy of the shipped
# VVFP Startup.dll from it. Exit code 0 means every check passed. Nothing is
# left in the repository.
#
# The executable is named without "patch" in it: Windows' installer
# detection treats an unmanifested 32-bit program named like an installer or
# patcher as needing elevation, and would wait on a prompt nobody sees.
#
# Each run builds into its own folder under %TEMP% and removes it afterwards,
# like every harness script (tests/test_harness_scripts_build_per_run.py).

$projectRoot = Split-Path -Parent $PSScriptRoot
$sharedRoot = Join-Path $projectRoot "native\shared"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

$runDir = Join-Path $env:TEMP ("vvfp_patcher_files_harness_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $runDir -Force | Out-Null
$scratch = Join-Path $runDir "scratch"
Push-Location $runDir
try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo `
        ("/Fo" + $runDir + "\") `
        /O2 `
        /MT `
        /W4 `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        (Join-Path $sharedRoot "patcher_files_harness.c") `
        /link `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/OUT:" + (Join-Path $runDir "files_folder_harness.exe")) `
        kernel32.lib
    if ($LASTEXITCODE -ne 0) {
        throw "Patcher files harness compilation failed."
    }
    & (Join-Path $runDir "files_folder_harness.exe") $scratch (Join-Path $projectRoot "assets\startup\VVFP Startup.dll")
    if ($LASTEXITCODE -ne 0) {
        throw "Patcher files harness reported failures."
    }
} finally {
    Pop-Location
    Remove-Item -LiteralPath $runDir -Recurse -Force -ErrorAction SilentlyContinue
}
