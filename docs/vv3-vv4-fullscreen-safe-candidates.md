# VV3/VV4 fullscreen-safe Origins candidates

The `vv3_fullscreen_safe_candidate` and `vv4_fullscreen_safe_candidate` records
are enabled and catalog-visible for the certified Collection Progression and
Immediate Fixed modes only. Runtime/player validation remains pending; the
Expanded-256 modes remain rejected before output.

Each candidate is bound to its exact certified Full Mastery parent pair and
companion DLL. It owns only a dedicated RX append page and the two guarded
Tech/Detail call sites. The wrapper resolves `SDL_GetWindowFlags` from the
already-loaded SDL module, masks only fullscreen-desktop bits (`0x1001`), and
uses the game's native leave/enter transition with the exact game singleton
transport. It reacquires the singleton/engine before the modal call and again
before restoration; identity or state/flag disagreement fails closed without
entering the modal route or charging. Every helper is assembled at its final
page VA (Tech `section+0x100`, Detail `section+0x400`) with distinct typed
outer, engine, SDL-window, and screen locals. Once native leave is issued,
every later exit makes exactly one guarded fresh restoration attempt and
post-verifies both masked flags and engine mode `+0x1E`.

The wrapper is a plain-return replacement for the original menu call and does
not consume handler arguments. Windows `GetModuleHandleA` and
`GetProcAddress` calls use their stdcall ABI (no caller cleanup); the SDL query
is cdecl and cleans its one argument. Windowed mode remains on the original
call path. Fullscreen mode is entered only after native leave and verified
windowed engine state, then restored only after the complete modal route.
The emitted hook bytes are VV3 Tech `E86DDF2300`, Detail `E86DE12300`, and
VV4 Tech `E87A7D2B00`, Detail `E8457E2B00`; rel32 values are calculated from
the actual call VA without a second image-base addition. Companion DLL inputs
are hashed and size-checked before evidence output: VV3 Full Heal
`9F866CB6...D2F8533` (298,496 bytes) and VV4 Full Mastery
`4E1A8368...AD01E7` (282,624 bytes).

Supported modes are `collection_progression` and `immediate_fixed` only.
Expanded-256 modes reject before output. The records remain runtime/player
pending until an independent emitted-byte audit and player test recertify them.
Full Mastery, Full Heal/Cure, Running, DLL/resource, save routing, and all
unrelated bytes are outside this candidate's ownership.
