# VV3 mask positioning — static audit and player-trace handoff

The render arithmetic below is retained from the existing offscreen work. The pickup
conclusion in this document is an exact-stock static result; it is not runtime or player
acceptance. Follows `docs/head-mask-rendering.md` Parts 1–7.

## 1. The leaf draw functions — coordinate handling (disassembled)

`42E510(ecx=mgr, a1=atlas, a2=x, a3=y, a4=cell, a5=scale)`:

```
42e510  fild [esp+8]          ; a2 = x
42e518  fmul [esi+0x300c]     ; x * camera
42e51e  call 0x46ef58         ; ftol -> edi
42e523  fild [esp+0x14]       ; (after 2 pushes) = a3 = y
42e529  fmul [esi+0x300c]     ; y * camera
42e52f  call 0x46ef58         ; ftol -> eax
42e534  mov edx,[esi+0x3008]  ; scrollY
42e53a  mov ecx,[esi+0x3004]  ; scrollX
42e540  add edx,eax           ; screenY = scrollY + y*camera
42e555  add ecx,edi           ; screenX = scrollX + x*camera
```

`42E570` (whole-head draw) is structurally identical. So both leaves take
**pre-scale world coordinates** and apply `screen = scroll + world × camera`
internally. `docs/head-mask-rendering.md` rule 13 is correct as written.

## 2. The measured camera value — double-scale is a NO-OP in VV3

Read live from the running game (ReadProcessMemory, two separate sessions):

| field | value |
|---|---|
| `[mgr+0x300C]` (camera) | **1.0** |
| `[mgr+0x3004]` (scrollX) | -850 |
| `[mgr+0x3008]` (scrollY) | -500 |
| `[mgr+0x3010]` (size) | 100 |

VV3's village camera does not zoom. Therefore `offset × 1.0 = offset`: the
double-scale multiplication **cannot displace the mask**, and world-unit vs
screen-pixel offsets are numerically indistinguishable here.

Offsets are still expressed in world units — correct at any camera value, and
free at 1.0 — so the rule is satisfied regardless.

## 3. The actual cause of the detached ("floating in sand") masks

Found with a per-draw diagnostic (`g_vv3_actdbg`, published at `.vv3md+0x38`).

The action-overlay wrapper at both `0x460B48` and `0x460D10` runs for every
matching stock branch. `sub_45F7E0` no-ops when the villager has no action
frame, and the post-stock DLL export now only stashes the tuple; it never draws
there. The final world wrapper therefore emits the one mask after ownership
selection.

The final owner gates real action frames to `0..50`; `-1` is the stock no-action
state and falls through to the matching head stash. Unsupported action values
fail closed without a head fallback. Held `record+0xF12 != 0` always selects
the matching head stash and suppresses action.

## 4. Arithmetic proof that the registration is correct

Same logged frame, camera = 1.0:

```
pose cell top-left  screen = (-850+1100, -500+971) = (250, 471)
mask cell top-left  screen = (-850+1076, -500+939) = (226, 439)
head centre within pose cell (measured from art) = (20, 24) -> (270, 495)
mask face within mask cell                       = (44, 56) -> (270, 495)
```

The head centre and the mask face **coincide exactly**. The draw formula

```
x = px + posehead_px[anim] - maskface_cx[facing]
y = py + posehead_py[anim] - maskface_cy[colour]
```

lands the mask's face on the pose head's face by construction.

`posehead_px/py[51]` were measured from the action art itself (median skin-blob
centre of the top third of each 40×65 pose cell, across all 10 outfit rows of
`female_actions00/01/02.png`), because VV3 has **no engine pose-anchor table**:
VV2's byte-trace of `0x460AEF..0x460B41` shows the overlay offset is one global
float × fixed constants, identical for every pose, with no `[record+0xF20]`
read and no table indexing. The per-pose head position exists only in the art.

## 5. Deployed-bytes verification

```
0x460B48  E8 73 E5 27 00                 ; call 0x6DF0C0
0x460D10  E8 AB E3 27 00                 ; call 0x6DF0C0
0x6DF0C0  one ABI-identical wrapper: stock sub_45F7E0, then stash-only export
           ret 0xC; wrapper occupies [0x6DF0C0,0x6DF0EB), next cave 0x6DF100
```

Matches intended asm; null pointer degrades to stock behaviour.

## 6. Remaining player gates (not claimed accepted)

- **Pickup/held rendering:** stock `+0xF12` ownership, action precedence, and
  release clearing are implemented from the proven record path. The player
  must still accept held motion and on-screen placement.
- **Details portrait:** multiplier `18` is the current candidate; visual
  placement remains pending player acceptance.

## 7. `0x4341A0..0x434758` is a timed effect renderer, not held-villager state

Settled by disassembly of the exact stock VV3 executable (SHA-256
`8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503`). The two formerly
proposed patch points are calls inside one three-style timed sprite/particle object:

```
 434357  call 0x42E570             ; generic scaled-sprite draw
 4344B3  call 0x42E510             ; generic cell blit
```

At `0x434357`, the sprite argument comes from `[esi+ecx*4+0x7C]`, with `ecx` selected
from `0..2`; this is a three-entry effect sprite table, not the villager head atlas. The
same function iterates 24-byte effect entries and compares elapsed time with `0x12C` and
`0x7080`. It uses fixed anchor constants at `0x5947B8..0x5947CC`:

```
(110,160), (114,212), (75,176)
```

There is no record-stride `0x1F8C` use in this object. Therefore `0x434357` and `0x4344B3`
must remain byte-identical to stock. They do not identify the player-grab event, the held
villager record, or a cursor head.

All four references to `0x5947D0` are the same one-time-init idiom — test a
bit, skip if set, else OR it in and initialise a constant block:

| site | bit |
|---|---|
| `0x4341E3` | 1 |
| `0x43439C` | 2 |
| `0x4344D4` | 4 |
| `0x434644` | 8 |

So `0x5947D0` is a **4-bit initialization latch**, permanently `0xf` after startup, carrying
no selection or pickup information. **Never gate a mask path on it.**

### Proven normal villager path

`0x42E3F5` is the sole direct caller of `sub_4605F0`; its handler receives a villager index,
derives the record with stride `0x1F8C`, reads the head atlas holder at `record-context+0x127C1C`,
and calls `0x42E570` at `0x460A60`. That is the proven world/action render family. The mask
hooks replay the exact head tuple, stash post-stock action tuples at both action call sites,
and select one owner in the final wrapper. Generic task-1 swimming on terrain 5 remains
head-owned; fishing task-11 frames 8/9 use the action tuple. F20=42 is only the stock water
renderer exception, not a claim that generic swimming assigns action 42.

### Player trace handoff (minimal values)

Trace one mouse-down that successfully grabs a villager, several held frames, and release.
Record:

1. the earliest successful-grab callback, villager record pointer/index, and any drag-object
   pointer;
2. cursor x/y and record fields `+0xF1C`, `+0xF12`, `+0xF14`, `+0xF18`, `+0xF20` at grab,
   held, and release;
3. every `0x42E510`/`0x42E570` entry during held frames, including return address, atlas or
   sprite pointer, cell/frame, x/y, facing, and scale;
4. the release callback and the first frame where the held identity/coordinates clear.

The trace validates the player-visible result and the release timing. The implementation
remains fail-closed at the unrelated effect sites: no hook is installed at `0x434357` or
`0x4344B3`.
