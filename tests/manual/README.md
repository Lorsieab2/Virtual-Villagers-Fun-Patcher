# Manual/native runtime verification

These are not part of the `pytest` suite and never run in CI: they need a
real interactive Windows desktop (they drive a real GUI window) and the
project's own MSVC/Windows SDK toolchain (the same one
`scripts/build_vv1_origins_icons.ps1` uses), not just a Python
environment. They exist because some things — does the *compiled* DLL's
real dialog actually behave correctly when driven with real Win32
messages — can't be verified by disassembly or by the automated suite
alone, and are too fragile/environment-specific to wire into CI.

## `runtime_test_vv1_appearance_dialog.c`

Loads the real, shipped `VVFP VV1 Origins Icons.dll`, calls the real
exported `ShowOriginsAppearancePicker` on a background thread (it blocks
on the dialog's own message loop, exactly as it does when called from the
game), finds the live window from the main thread, and drives it with
real `BM_CLICK` messages to the real button controls. It reads results
back both from the dialog's own label text and directly from a synthetic
villager buffer it owns, so a bug that updates the label but not the real
memory field (or vice versa) would be caught. Covers: initial label text
for both the male (19-option) and non-male (20-option) gender-dependent
ranges, wraparound arithmetic at the count boundary for both head and
body fields, Cancel reverting both fields to their original values, and
OK keeping the tentative values and returning success.

To run:

```powershell
$env:INCLUDE = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\<version>\include;C:\Program Files (x86)\Windows Kits\10\Include\<sdk>\um;C:\Program Files (x86)\Windows Kits\10\Include\<sdk>\shared;C:\Program Files (x86)\Windows Kits\10\Include\<sdk>\ucrt"
$env:LIB = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\<version>\lib\x86;C:\Program Files (x86)\Windows Kits\10\Lib\<sdk>\um\x86;C:\Program Files (x86)\Windows Kits\10\Lib\<sdk>\ucrt\x86"
cl.exe /nologo /O2 tests\manual\runtime_test_vv1_appearance_dialog.c /link user32.lib /OUT:runtime_test_vv1_appearance_dialog.exe
.\runtime_test_vv1_appearance_dialog.exe
```

Run it from the repository root (it defaults to the checkout-relative
`assets\origins\VVFP VV1 Origins Icons.dll`), or pass an explicit path as
the first argument if you built the `.exe` somewhere else:
`.\runtime_test_vv1_appearance_dialog.exe "C:\path\to\VVFP VV1 Origins Icons.dll"`.

Last run (this branch, HEAD `3975edc`, from the repo root): all checks passed.
