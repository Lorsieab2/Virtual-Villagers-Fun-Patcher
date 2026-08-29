# VV4 Details portrait mask — open state / handoff

Status as of 2026-08-29. Honest, verified facts only — no interpretation.

## What works (do NOT touch)
- **Village masks** are owner-approved and correct on every in-village render path
  (walk/bend/sit/swim/pickup). World hook `0x468263` inside compositor
  `FUN_00467da0` reissues the head blit `FUN_0044C790` with the mask atlas,
  replaying the head's own x/y/scale; facing from record `+0x1CD4 & 7`.
- The mask machinery is sound: `Vv4MaskGetForRecord` (DLL export @ordinal 114),
  `vv_get_mask`, and the shared render atlas load. The lookup now validates the
  current stable gender+name fingerprint before returning a stored mask; after
  a prior completed present sweep has promoted a slot to identity-ready, a mismatch
  clears and persists the stale entry. The first load frame still returns no mask for
  a mismatch but cannot erase the sidecar before record/name initialization finishes.
  The separate chooser preview
  sheet ships as data. Confirmed in the LIVE patched process:
  village mask atlas slot `0x728D70`=nonzero and `GET_PTR` `0x728D68`
  resolved. The obsolete dedicated bighead atlas is no longer shipped or
  loaded; Details uses the same stock full-body head draw and shared atlas.

## The failing bug: Details portrait shows NO mask
The "Villager Detail" screen portrait is a **FULL-BODY live villager** in a garden
scene (NOT an enlarged bighead). Owner set a mask on the shown villager; the
portrait showed nothing.

### PROVEN root cause (not a guess)
The pre-repair Details cave was wired to `0x45F965` (`call 0x409A70`, bighead
selector `0x30`), byte-verified present in the live process (`0x45F965 -> cave
0x7287A1`). **But that
cave NEVER FIRES when the Detail screen is open:**
- DLL Details-probe file `vvfp_detail_probe.txt` never appears.
- The cave's scale slot `D_A6` (`0x728A1C`) stays `0` (bighead-dbg confirms
  `arg6@728A1C=0`).

Therefore `0x45F965` is a different screen's element. It must not be redirected
or used as a Details mask hook. The world cave `0x468263` is also unrelated to
the preview (the village renders behind it, but the preview villager is a
separate element).

### Confirmed Details full-body path (exact stock static trace)
The Details screen's vtable at `0x48EFFC`, entry 6, points to `0x447D30`.
That draw selects the record and calls `0x460BF0(record, 0)` at `0x447D8E`.
`0x460BF0` enters `0x45F550`, the ordinary full-body villager renderer:

- `0x45F653` draws the body using `record+0x1BBC`.
- `0x45F702` draws the head using `record+0x1BB8`.

Both calls use the stock `0x409A70` draw thunk. The generated mask head cave
already redirects `0x45F702`; its replay swaps stack arg1 to the shared mask
atlas while preserving the stock draw-manager wrapper in ECX. Its mask column
uses `record+0x1CD4 & 7`, not the age-adjusted native animation frame, and its Y
position applies the shared `MASK_DY_TABLE` (34 native units × native integer
scale percent ÷ 100) so the tall mask cell is seated at every
portrait scale. The separate
`0x45F965` redirect/cave and dedicated bighead atlas are removed. The
player-approved world hook `0x468263` is unchanged.

The nearby `0x45F9CA` call is also left stock. Static caller tracing binds its
sole direct caller (`0x416EF5`, method `0x416EC0`) to the Island Event dialog
vtable (`0x48D2C8`, RTTI `CIslandEventDialog`), not the Details chain. It is
therefore not part of this repair. The owner previously approved pickup through
the unchanged world hook (`0x468263`); this isolated static caller trace neither
proves nor overturns that player observation. Do not add a separate pickup hook
unless a new player-visible failure and exact trace identify one.

### Historical false-route RE leads (verified addresses)
- `0x45F965` lives in villager-draw fn **`0x45F7C0`**. Its only 2 DIRECT callers:
  - `0x416EF5` — caller object via `esi+0x83c/0x840/0x844`, pushes `arg+0x19`.
  - `0x43B7E6` — `mov ecx,0x50e568; call 0x466040` then draws (villager array
    base is `0x50E5AC`).
  Neither drove the `0x30` path on the Detail screen in testing.
- Draw internals (all byte-verified): thunk `0x409A70` = `mov ecx,[ecx]; jmp
  0x408C40`. `0x408C40` is stdcall `ret 0x1c` (7 args: atlas,X,Y,arg4,arg5,
  scale,0). The dereferenced ECX is the render target/context; stack arg1 is
  the atlas passed to cell-resolver `0x40A990`. For a plain atlas
  (`[atlas+0x30]==0`), arg4=ROW and arg5=COL are clamped to that atlas's own
  `[atlas+8]=cols` / `[atlas+0xc]=rows`. This follows the VV5 contract (also
  corroborated by VV2):
  preserve the draw context, pass the mask atlas as arg1, and replay the native
  draw. Do not put the atlas in ECX or pass a bighead's linear out-params to a
  different-width atlas.
- Record fields at any villager draw: `+0x1B8C` age (child <0x118; the portrait
  fn uses 0x44c), `+0x1B90` sex, `+0x1BB8` head, `+0x1BBC` body, `+0x1CD4` clean
  facing `&7`, `+0x1CC7` dead, `+0x1C40` health, `+0x1BC0` name (24 bytes).

### Runtime proof still required
Static tracing now identifies the call path and the patch is limited to the
confirmed `0x45F702` head site. The player must still open Villager Detail with
a masked villager and confirm that the mask is visible, correctly seated, and
does not change the approved village render. No screenshot or static patch hash
is player/runtime proof.

### Ancillary: failed-apply lesson (root of the week-long "nothing changes")
An 8-thunk diagnostic caller-capture placed `.shr` caves that COLLIDED with
existing features (overlap `0xCC220` / `0xCCBD8`). A failed `apply` silently
leaves the modded exe UNCHANGED, so every observation was of a stale exe. Always
confirm `apply` SUCCEEDED before trusting any hash or screenshot. That obsolete
diagnostic is no longer generated.

### Diagnostics
The prior `vvfp_detail_probe.txt`, `vvfp_bighead_dbg.txt`, and disabled
`vvfp_callers.txt` diagnostics are not part of the corrected generated patch.
