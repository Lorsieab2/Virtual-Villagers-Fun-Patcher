$ErrorActionPreference = "Stop"

# Builds the two fruit-tree timing companions of The Secret City, one feature each:
#   "VVFP VV3 Trees Refill Together.dll"  (native\vvfp_vv3_trees_together)
#   "VVFP VV3 Trees Take Turns.dll"       (native\vvfp_vv3_trees_take_turns)
# Both are native\shared\vv3_fruit_timers.h with a different VV3_FRUIT_MODE.  32-bit, static
# CRT, like every other companion.  Re-run scripts\build_vv3_fruit_tree_timing_features.py
# afterwards: the rows pin the DLLs by SHA-256.

$projectRoot = Split-Path -Parent $PSScriptRoot
$outputRoot = Join-Path $projectRoot "assets\fruit_trees"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null

foreach ($companion in @(
    @{ Folder = "vvfp_vv3_trees_together"; Dll = "VVFP VV3 Trees Refill Together.dll" },
    @{ Folder = "vvfp_vv3_trees_take_turns"; Dll = "VVFP VV3 Trees Take Turns.dll" }
)) {
    $nativeRoot = Join-Path $projectRoot ("native\" + $companion.Folder)
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo `
        /LD `
        /O2 `
        /MT `
        /W4 `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        (Join-Path $nativeRoot ($companion.Folder + ".c")) `
        /link `
        /Brepro `
        ("/DEF:" + (Join-Path $nativeRoot ($companion.Folder + ".def"))) `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        ("/OUT:" + (Join-Path $outputRoot $companion.Dll)) `
        /RELEASE `
        kernel32.lib user32.lib shell32.lib
    if ($LASTEXITCODE -ne 0) {
        throw ("Native fruit-tree DLL compilation failed: " + $companion.Dll)
    }
    @(
        (Join-Path $projectRoot ($companion.Folder + ".obj")),
        (Join-Path $projectRoot ($companion.Folder + ".exp")),
        (Join-Path $projectRoot ($companion.Folder + ".lib"))
    ) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
        Remove-Item -LiteralPath $_
    }
}
