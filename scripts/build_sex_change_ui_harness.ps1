# Build and run the "Change sex..." button harness (native/vv4_origins_icons/sex_change_ui_harness.c) for The Secret
# City, The Tree of Life and New Believers.
#
# Each build compiles that game's Origins companion source unchanged, with its own resources (the real dialog
# templates), into a 32-bit harness executable linked fixed at 0x400000 with a zeroed block over the game's own
# addresses the companion reads.  Without -Shots it drives the real dialog procedures and chooser exports with the
# button's WM_COMMAND (nothing is shown; no file is read or written).  With -Shots <folder> it shows the real
# window, captures it and the real warning box as BMPs in that folder, answers No and closes it.  Each run builds
# into its own folder under %TEMP% and removes it afterwards.  Exit code 0 means every check passed.
param(
    [int[]]$Games = @(3, 4, 5),
    [string]$Shots = ""
)
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"
$harness = Join-Path $projectRoot "native\vv4_origins_icons\sex_change_ui_harness.c"
$resources = @{
    3 = "native\vv3_full_mastery_candidate\vv3_full_mastery_candidate.rc"
    4 = "native\vv4_origins_icons\vv4_origins_icons.rc"
    5 = "native\vv5_task9_origins\vv5_task9_origins.rc"
}
$work = Join-Path $env:TEMP ("vvfp_sex_change_ui_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $work | Out-Null

try {
    foreach ($game in $Games) {
        $res = Join-Path $work ("vv" + $game + ".res")
        $out = Join-Path $work ("sex_change_ui_harness_vv" + $game + ".exe")
        & (Join-Path $sdkRoot "bin\$sdkVersion\x86\rc.exe") /nologo /fo $res (Join-Path $projectRoot $resources[$game])
        if ($LASTEXITCODE -ne 0) { throw "Resources for VV$game failed to compile" }
        $log = & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
            /nologo /O1 /MT `
            ("/DHARNESS_GAME=" + $game) `
            ("/Fo" + $work + "\") `
            /I (Join-Path $vsTools "include") `
            /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
            /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
            /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
            $harness `
            (Join-Path $projectRoot "native\shared\save_folder.c") `
            $res `
            /link `
            ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
            ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
            ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
            user32.lib gdi32.lib shell32.lib advapi32.lib gdiplus.lib `
            /BASE:0x400000 /FIXED /DYNAMICBASE:NO `
            ("/OUT:" + $out)
        if ($LASTEXITCODE -ne 0) {
            $log | Write-Output
            throw "Change sex harness for VV$game failed to build"
        }
        if ($Shots -ne "") {
            & $out shots $Shots
        } else {
            & $out
        }
        if ($LASTEXITCODE -ne 0) { throw "Change sex harness for VV$game reported failures" }
    }
}
finally {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
