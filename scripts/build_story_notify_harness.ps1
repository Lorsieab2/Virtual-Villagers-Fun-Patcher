# Build and run the story-notify harness.
#
# native/save_reset_export/story_notify_harness.c includes the SHIPPED
# save_reset_export.c with the module lookups, the save folder and the sweep
# replaced by recorders, and checks that deleting a tribe or starting over
# tells "VVFP Story Upgrades.dll" (VvfpStoryVillageReset) when it is loaded.
# Nothing on disk is read or deleted.
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$nativeRoot = Join-Path $projectRoot "native\save_reset_export"
$sharedRoot = Join-Path $projectRoot "native\shared"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"
$work = Join-Path $env:TEMP ("vvfp_story_notify_harness_build_" + $PID)
$out = Join-Path $work "vvfp_story_notify_harness.exe"
New-Item -ItemType Directory -Path $work -Force | Out-Null

try {
    Push-Location $work
    try {
        & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
            /nologo `
            /MT `
            /I (Join-Path $vsTools "include") `
            /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
            /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
            /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
            /I $sharedRoot `
            /I $nativeRoot `
            (Join-Path $nativeRoot "story_notify_harness.c") `
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
        if ($LASTEXITCODE -ne 0) { throw "story notify harness failed to build" }
    } finally {
        Pop-Location
    }
    & $out
    if ($LASTEXITCODE -ne 0) { throw "story notify harness reported failures" }
} finally {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
