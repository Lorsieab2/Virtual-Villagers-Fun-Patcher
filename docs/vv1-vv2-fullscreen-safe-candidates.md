# VV1/VV2 fullscreen-safe candidate evidence

The VV1 and VV2 fullscreen-safe records are disabled, catalog-hidden evidence
only. They support the certified Collection Progression and Immediate Fixed
parent compositions; Expanded-256 and unknown fingerprints reject before any
output. No package, launch, or save access is part of this evidence.

Each wrapper is the independently supplied 228-byte oracle blob at its final
page address. It resolves `SDL_GetWindowFlags` from the already loaded SDL2
module, masks `0x1001`, preserves the screen ABI, and performs the native
leave/enter transition with `ECX=engine`, `push bool`, and `ret 4`. The SDL
getter is cdecl (`push SDL_Window*`, indirect call, `add esp,4`). The existing
Full Mastery append page remains owned by Origins and must be removed before
Origins truncation. The legacy Cure row is structurally removed from dialog
201 (41 items remain; dialog 202 is unchanged). VV1 command 5 is rejected
before the shared price/funds path by the original no-action continuation:
`0x456A8D` changes `83 FB 08` to `83 FB 05`, and `0x456A90` changes
`0F 87 2F FF FF FF` to `0F 84 2F FF FF FF` (target `0x4569C5`). This keeps
commands 0-4 and command 7 on their certified paths and leaves the frozen
legacy Cure/deduction payload unreachable. VV2 retains its independently
audited `0x4946A5` (`83 FB 06` to `83 FB 05`) guard.

Before an Origins menu creates a dialog, the companion-side contract captures
`GetForegroundWindow`, validates `IsWindow` and same-process ownership, passes
that HWND to `DialogBoxParamA` and result `MessageBoxA` calls, and centers/clamps
the dialog in the owner monitor work area during `WM_INITDIALOG`. The current
record remains disabled pending independent proof that this owner/centering
behavior is present in the installed companion; the static wrapper bytes are
not changed to guess at HWND transport.

Candidate-owned companion replacement is atomic and restores the exact parent
`VVFP Origins Icons.dll` SHA-256
`2ED1100E7F2EA5B8E522C2DE11F6B00CA8A02B968319C251365E9EFD634BCAF9`; the
candidate resource-only transform is SHA-256
`846BA4EDF29E52689883A6E20DBF5CB92244DBB52531D7573EDAFF6C9C91543D`.
