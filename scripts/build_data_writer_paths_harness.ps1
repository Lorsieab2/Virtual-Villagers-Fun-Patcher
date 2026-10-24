param(
    [int[]]$Writers = @(1, 2, 3, 4, 5, 6, 7, 8)
)

$ErrorActionPreference = "Stop"

# Builds and runs native/shared/data_writer_paths_harness.c once per writer:
# each build compiles that companion's real source and asks its real path
# builder where the per-save data file goes (masks in all five games, A New
# Home's parentage records, the Cause of Death graves and roster). The
# Documents folder is redirected to a scratch folder under %TEMP%, so nothing
# touches Documents\LDW or any save. Exit code 0 means every check passed.
#
# Each run builds into its own folder under %TEMP% and removes it afterwards,
# like every harness script (tests/test_harness_scripts_build_per_run.py).

$projectRoot = Split-Path -Parent $PSScriptRoot
$sharedRoot = Join-Path $projectRoot "native\shared"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.26100.0"
$vsTools = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"

$runDir = Join-Path $env:TEMP ("vvfp_dwp_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $runDir -Force | Out-Null
# The writers measure every path against MAX_PATH with room for their
# ".unreadable-..." set-aside name (VV_DATA_RESERVE, 27 with the NUL), and a
# save's own folder that would not fit is never used: the older layout's path
# is kept (native/shared/per_save.h, rule 6 of data_subfolder.h). That is the
# shipped behaviour for an over-long save folder, not what checks a. measure,
# so the scratch "Documents" folder must leave the longest writer room. The
# longest is the Unaccounted Villagers roster (writer 8): with this run's
# folder, the default %TEMP% left it 3 characters, and any longer %TEMP% (a
# private one per test run) sent it to the older layout and failed checks a.
# The scratch is therefore named by its 8.3 short form where the volume has
# one, and a scratch that still leaves too little room is refused up front
# with the reason, never reported as the writer's failure.
$scratchRoot = $runDir
try {
    $short = (New-Object -ComObject Scripting.FileSystemObject).GetFolder($runDir).ShortPath
    if ($short) {
        $scratchRoot = $short
    }
} catch {
}
$longest = (Join-Path $scratchRoot "d8") + "\LDW\data_writer_paths_harness_8\Virtual Villagers Fun Patcher" +
    "\Save 5\Data\Unaccounted Villagers\Virtual Villagers 4 Villagers at Last Save - Save 5.dat"
if ($longest.Length + 27 -gt 260) {
    Remove-Item -LiteralPath $runDir -Recurse -Force -ErrorAction SilentlyContinue
    throw ("The scratch folder " + $scratchRoot + " is too long for the writers' MAX_PATH budget (" +
        $longest.Length + " + 27 > 260) and has no 8.3 short name: set TEMP to a shorter folder.")
}
$failed = @()
Push-Location $runDir
try {
    foreach ($writer in $Writers) {
        $exe = Join-Path $runDir "data_writer_paths_harness_$writer.exe"
        $link = @(
            "/link",
            ("/LIBPATH:" + (Join-Path $vsTools "lib\x86")),
            ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\um\x86")),
            ("/LIBPATH:" + (Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x86")),
            ("/OUT:" + $exe),
            "kernel32.lib", "user32.lib", "gdi32.lib", "shell32.lib", "advapi32.lib", "gdiplus.lib"
        )
        if ($writer -eq 5) {
            # New Believers reads its save slot from the game's own scratch
            # word (0x7B1D7C): link at the game's base, not relocatable, so
            # the harness's writable block covers that address.
            $link += @("/FIXED", "/BASE:0x400000", "/DYNAMICBASE:NO")
        }
        & (Join-Path $vsTools "bin\Hostx64\x86\cl.exe") `
            /nologo /O2 /MT /W3 `
            ("/Fo" + $runDir + "\") `
            ("/DVV_WRITER=$writer") `
            /I (Join-Path $vsTools "include") `
            /I (Join-Path $sdkRoot "Include\$sdkVersion\um") `
            /I (Join-Path $sdkRoot "Include\$sdkVersion\shared") `
            /I (Join-Path $sdkRoot "Include\$sdkVersion\ucrt") `
            /I $sharedRoot `
            (Join-Path $sharedRoot "data_writer_paths_harness.c") `
            @link | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Data writer paths harness $writer compilation failed."
        }
        # A short scratch path: the writers' MAX_PATH budgets include it.
        $scratch = Join-Path $scratchRoot ("d" + $writer)
        & $exe $scratch
        if ($LASTEXITCODE -ne 0) {
            $failed += $writer
        }
    }
} finally {
    Pop-Location
    Remove-Item -LiteralPath $runDir -Recurse -Force -ErrorAction SilentlyContinue
}
if ($failed.Count -gt 0) {
    throw ("Data writer paths harness reported failures for writer(s): " + ($failed -join ", "))
}
