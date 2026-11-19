# Build and run the Change sex harness of A New Home and The Lost Children
# (native/vv1_origins_icons/sex_change_dialog_harness.c): the real Change Appearance dialog procedures and
# templates of "VVFP VV1 Origins Icons.dll" / "VVFP VV2 Origins Icons.dll", compiled from their unchanged
# source with the game's own .rc linked in.
#
# Without -Shots: the checks (scripted presses of the real dialog procedure, the templates measured hidden);
# nothing is shown and no file is written.  Exit code 0 means every check passed.
# With -Shots <folder>: the real windows are shown for a moment and captured (PrintWindow) -- the window with
# the button, the warning box (answered No), the "Head look" window -- as PNG files in that folder.
#
# It is linked fixed at 0x200000 with a large zeroed block over A New Home's mask scratch addresses
# (change_appearance_extras_harness.c's way).  Each run builds into its own folder under %TEMP% and
# removes it.
param(
    [int[]]$Games = @(1, 2),
    [string]$Shots = ""
)
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$source = Join-Path $projectRoot "native\vv1_origins_icons\sex_change_dialog_harness.c"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"
$work = Join-Path $env:TEMP ("vvfp_sex_change_origins_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $work | Out-Null

try {
    foreach ($game in $Games) {
        if ($game -eq 1) {
            $rc = Join-Path $projectRoot "native\vv1_origins_icons\vv1_origins_icons.rc"
        } else {
            $rc = Join-Path $projectRoot "native\vv2_origins_icons\vv2_origins_icons.rc"
        }
        $res = Join-Path $work ("vv" + $game + ".res")
        $log = & (Join-Path $sdkRoot "bin\$sdkVersion\x86\rc.exe") /nologo /fo $res $rc
        if ($LASTEXITCODE -ne 0) {
            $log | Write-Output
            throw "Resources for VV$game failed to compile"
        }
        $out = Join-Path $work ("sex_change_origins_harness_vv" + $game + ".exe")
        $log = & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
            /nologo /O1 /MT `
            ("/DHARNESS_GAME=" + $game) `
            ("/Fo" + $work + "\") `
            /I (Join-Path $vsTools "include") `
            /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
            /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
            /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
            $source `
            (Join-Path $projectRoot "native\shared\save_folder.c") `
            $res `
            /link `
            ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
            ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
            ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
            user32.lib gdi32.lib shell32.lib advapi32.lib gdiplus.lib comctl32.lib `
            /BASE:0x200000 /FIXED /DYNAMICBASE:NO `
            ("/OUT:" + $out)
        if ($LASTEXITCODE -ne 0) {
            $log | Write-Output
            throw "Change sex harness for VV$game failed to build"
        }
        if ($Shots -ne "") {
            New-Item -ItemType Directory -Force -Path $Shots | Out-Null
            & $out shot $work
            Add-Type -AssemblyName System.Drawing
            Get-ChildItem -LiteralPath $work -Filter ("VV" + $game + " *.bmp") | ForEach-Object {
                $image = [System.Drawing.Image]::FromFile($_.FullName)
                try {
                    $image.Save((Join-Path $Shots ($_.BaseName + ".png")), [System.Drawing.Imaging.ImageFormat]::Png)
                } finally {
                    $image.Dispose()
                }
            }
        } else {
            & $out
            if ($LASTEXITCODE -ne 0) { throw "Change sex harness for VV$game reported failures" }
        }
    }
}
finally {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
