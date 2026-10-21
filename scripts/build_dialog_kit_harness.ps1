# Build and run the dialog kit harness.
#
# native/shared/dialog_kit_harness.c creates every dialog template of each
# companion DLL given (loaded as a resource file only; none of its code
# runs), hidden, with native/shared/vvfp_dialog_kit.h's hook, and checks the
# resizable frame, the smallest size and the layout at the template's size,
# half as large again and maximised; then the wrapping lists and the
# villager sorting on real controls.  Nothing on disk is written.
#
# Each run builds into its own folder under %TEMP% and removes it afterwards,
# so concurrent runs never share one.
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Dlls)
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$sharedRoot = Join-Path $projectRoot "native\shared"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"
$work = Join-Path $env:TEMP ("vvfp_dialog_kit_harness_build_" + [guid]::NewGuid().ToString("N"))
$out = Join-Path $work "vvfp_dialog_kit_harness.exe"
New-Item -ItemType Directory -Path $work | Out-Null

try {
    & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
        /nologo `
        /MT `
        /W4 `
        /D_CRT_SECURE_NO_WARNINGS `
        ("/Fo" + $work + "\") `
        /I (Join-Path $vsTools "include") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
        /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
        /I $sharedRoot `
        (Join-Path $sharedRoot "dialog_kit_harness.c") `
        /link `
        ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")) `
        ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")) `
        kernel32.lib `
        user32.lib `
        gdi32.lib `
        ("/OUT:" + $out)
    if ($LASTEXITCODE -ne 0) { throw "dialog kit harness failed to build" }
    & $out @Dlls
    if ($LASTEXITCODE -ne 0) { throw "dialog kit harness reported failures" }
} finally {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
