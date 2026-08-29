# VV4 Details portrait mask — open state / handoff

Status as of 2026-08-29. Honest, verified facts only — no interpretation.

## What works (do NOT touch)
- **Village masks** are owner-approved and correct on every in-village render path
  (walk/bend/sit/swim/pickup). World hook `0x468263` inside compositor
  `FUN_00467da0` reissues the head blit `FUN_0044C790` with the mask atlas,
  replaying the head's own x/y/scale; facing from record `+0x1CD4 & 7`.
- The mask machinery is sound: `Vv4MaskGetForRecord` (DLL export @ordinal 114),
  `vv_get_mask`, and both atlases load. Confirmed in the LIVE patched process:
  village mask atlas slot `0x728D70`=nonzero, bighead atlas slot `0x728A3C`
  =nonzero (loaded 40x90, 3 cols x 5 rows), `GET_PTR` `0x728D68` resolved.

## The failing bug: Details portrait shows NO mask
The "Villager Detail" screen portrait is a **FULL-BODY live villager** in a garden
scene (NOT an enlarged bighead). Owner set a mask on the shown villager; the
portrait showed nothing.

### PROVEN root cause (not a guess)
The Details cave was wired to `0x45F965` (`call 0x409A70`, bighead selector `0x30`),
byte-verified present in the live process (`0x45F965 -> cave 0x7287A1`). **But that
cave NEVER FIRES when the Detail screen is open:**
- DLL Details-probe file `vvfp_detail_probe.txt` never appears.
- The cave's scale slot `D_A6` (`0x728A1C`) stays `0` (bighead-dbg confirms
  `arg6@728A1C=0`).

Therefore `0x45F965` is a different screen's element; the Details **full-body
preview is drawn by an as-yet-unidentified path** that hits neither `0x45F965`
NOR the world cave `0x468263` (village renders behind, but the preview villager
is a separate element — masking the world does not reach it).

### RE leads for the successor (verified addresses)
- `0x45F965` lives in villager-draw fn **`0x45F7C0`**. Its only 2 DIRECT callers:
  - `0x416EF5` — caller object via `esi+0x83c/0x840/0x844`, pushes `arg+0x19`.
  - `0x43B7E6` — `mov ecx,0x50e568; call 0x466040` then draws (villager array
    base is `0x50E5AC`).
  Neither drove the `0x30` path on the Detail screen in testing.
- Draw internals (all byte-verified): thunk `0x409A70` = `mov ecx,[ecx]; jmp
  0x408C40`. `0x408C40` is stdcall `ret 0x1c` (7 args: atlas,X,Y,arg4,arg5,
  scale,0). It calls cell-resolver `0x40A990`, which for a plain atlas
  (`[atlas+0x30]==0`) decodes **arg4=ROW, arg5=COL** clamped to the atlas's own
  `[atlas+8]=cols` / `[atlas+0xc]=rows`. Cols getter = `0x421570` (`mov eax,
  [ecx+8]; ret`). So to draw a specific cell: pass row=colour-1, col=facing;
  do NOT pass a bighead's linear out-params to a different-width atlas.
- Record fields at any villager draw: `+0x1B8C` age (child <0x118; the portrait
  fn uses 0x44c), `+0x1B90` sex, `+0x1BB8` head, `+0x1BBC` body, `+0x1CD4` clean
  facing `&7`, `+0x1CC7` dead, `+0x1C40` health, `+0x1BC0` name (24 bytes).

### Next step (recommended)
Find the Detail-screen paint's villager-preview draw. Candidate approach: hook the
head-draw function itself from the **DLL** (VirtualProtect + inline hook — owner
wants DLL, not `.shr` caves), log the caller ONLY while a Detail-screen flag is
set, open a masked villager's Detail, read the caller. Then reissue the mask on
that exact draw with row=colour-1, col=facing, replaying its x/y/scale. VV2/VV5
solved their Details masks — ask them what element the Detail portrait is and the
analogous draw.

### Ancillary: failed-apply lesson (root of the week-long "nothing changes")
An 8-thunk diagnostic caller-capture placed `.shr` caves that COLLIDED with
existing features (overlap `0xCC220` / `0xCCBD8`). A failed `apply` silently
leaves the modded exe UNCHANGED, so every observation was of a stale exe. Always
confirm `apply` SUCCEEDED before trusting any hash or screenshot. Diagnostic is
disabled (`CALLER_CAPTURE_ENABLED=False`).

### Diagnostics still present (strip when the feature is done)
`vvfp_detail_probe.txt` logic (DLL), `vvfp_bighead_dbg.txt` (one-shot), and the
caller-ring dump `vvfp_callers.txt` (DLL present-hook; ring disabled so it is
empty).
