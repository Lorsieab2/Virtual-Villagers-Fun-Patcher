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
real `BM_CLICK` messages to the real button controls. The head/body
previews are owner-draw real sprite art (cropped from the stock game, not
text), so results are read directly from a synthetic villager buffer this
program owns rather than from dialog text; each preview control's
presence is still confirmed so a dialog-template regression would be
caught. Covers: both preview controls existing for the male (19-option)
and non-male (20-option) gender-dependent ranges, wraparound arithmetic
at the count boundary for both head and body fields, Cancel reverting
both fields to their original values, and OK keeping the tentative
values and returning success.

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

Last run (this branch, from the repo root, against the real-art picker):
see the commit that updated this file for the result.

## `runtime_test_vv1_esc_closes_upgrade_menus.c`

Loads the real, shipped DLL, opens the real Tech-screen ("Origins
Upgrades") and Villager Details ("Villager Upgrades") dialogs on a
background thread, and posts a real `WM_KEYDOWN`/`WM_KEYUP` for
`VK_ESCAPE` to the live window -- `PostMessage`, not `SendMessage`, since
only a queued message actually passes through the modal loop's own
`IsDialogMessage` translation the way a real keypress would. Confirms
both dialogs close and return the same result Cancel does (-1).

Both dialogs already give their Cancel button control ID 2 (`IDCANCEL`),
which is what makes the standard Windows dialog ESC-to-cancel behavior
apply automatically -- this test exists to prove that translation still
reaches the real compiled dialog (not just that the .rc template says
it should), so a future change can't silently break it (e.g. by
changing the Cancel button's ID, or by adding a custom `WM_KEYDOWN`
handler that swallows the key first).

To run: same toolchain invocation as above, substituting this file's name.
