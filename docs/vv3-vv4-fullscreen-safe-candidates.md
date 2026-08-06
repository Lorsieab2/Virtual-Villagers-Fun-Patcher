# VV3/VV4 fullscreen-safe Origins candidates

The `vv3_fullscreen_safe_candidate` and `vv4_fullscreen_safe_candidate` records
are disabled, catalog-hidden static candidates. They are not public patch choices
and have not been player-validated.

Each candidate is bound to its exact certified Full Mastery parent pair and
companion DLL. It owns only a dedicated RX append page and the two guarded
Tech/Detail call sites. The wrapper resolves `SDL_GetWindowFlags` from the
already-loaded SDL module, masks only fullscreen-desktop bits (`0x1001`), and
uses the game's native leave/enter transition with the exact game singleton
transport. It reacquires the singleton/engine before the modal call and again
before restoration; identity or state/flag disagreement fails closed without
entering the modal route or charging.

The wrapper is a plain-return replacement for the original menu call and does
not consume handler arguments. Windows `GetModuleHandleA` and
`GetProcAddress` calls use their stdcall ABI (no caller cleanup); the SDL query
is cdecl and cleans its one argument. Windowed mode remains on the original
call path. Fullscreen mode is entered only after native leave and verified
windowed engine state, then restored only after the complete modal route.

Supported modes are `collection_progression` and `immediate_fixed` only.
Expanded-256 modes reject before output. The records remain runtime/player
pending until an independent emitted-byte audit and player test recertify them.
Full Mastery, Full Heal/Cure, Running, DLL/resource, save routing, and all
unrelated bytes are outside this candidate's ownership.
