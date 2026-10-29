# Build and run the Change Appearance extras harness (native/shared/change_appearance_extras_harness.c:
# Undo changes, Reset to original, the Random buttons and the For All look rows) once for each of the five games.
#
# Each build compiles that game's Origins companion source unchanged into a 32-bit harness executable
# that drives its real Change Appearance dialog procedures and exports (native/shared/appearance_extras.h).
# Nothing is shown on screen and no file is read or written.  Each run builds into its own folder under
# %TEMP% and removes it afterwards.  Exit code 0 means every check passed.
param(
    [int[]]$Games = @(1, 2, 3, 4, 5)
)
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$sharedRoot = Join-Path $projectRoot "native\shared"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"
$work = Join-Path $env:TEMP ("vvfp_change_appearance_extras_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $work | Out-Null

try {
    foreach ($game in $Games) {
        $out = Join-Path $work ("change_appearance_extras_harness_vv" + $game + ".exe")
        $log = & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
            /nologo /O1 /MT `
            ("/DHARNESS_GAME=" + $game) `
            ("/Fo" + $work + "\") `
            /I (Join-Path $vsTools "include") `
            /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
            /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
            /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
            (Join-Path $sharedRoot "change_appearance_extras_harness.c") `
            (Join-Path $sharedRoot "save_folder.c") `
            /link `
            ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
            ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
            ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
            user32.lib gdi32.lib shell32.lib advapi32.lib gdiplus.lib `
            ("/OUT:" + $out)
        if ($LASTEXITCODE -ne 0) {
            $log | Write-Output
            throw "Change Appearance extras harness for VV$game failed to build"
        }
        & $out
        if ($LASTEXITCODE -ne 0) { throw "Change Appearance extras harness for VV$game reported failures" }
    }
}
finally {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
