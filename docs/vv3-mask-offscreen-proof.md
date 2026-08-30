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

This section records the exact-stock static boundary; it is not runtime or player acceptance.

The old candidate detoured `0x460A60 -> 0x42E570`. That is a generic fixed-resource
draw and, on the held path, uses a half-scale ground tuple. It does not consume the
record's authoritative appearance fields, so it can leave a tiny mask at the feet or
selection ring. The first stock appearance boundary is instead `0x460C7F -> 0x42E5E0`.

The repaired cave replays the six untouched stock arguments inline, then calls the
same draw with only atlas and head-row replaced. It does not stash a tuple, defer a
draw through the handler tail, or reconstruct an action pose. The stock action calls
at `0x460B48` and `0x460D10` remain byte-identical and naturally render after the
inline head layer. The stock held branch (`record+0xF12 != 0`) rejoins this same
body/head sequence, so the mask reuses its exact tuple while held. Cursor coordinate
ownership and final visual follow remain player-trace gates.

## 4. What is and is not proven

The inline tuple reuse is an ABI/path proof: stock supplies atlas, x, y, head-row,
facing, and scale to `0x42E5E0`, and the callback changes only atlas and row. It is
not a player-visible placement proof. Action seating, swimming/fishing alignment,
the held/cursor leaf, release timing, and Details placement still require a live
player trace and acceptance. No art-measured action offset is installed.

## 5. Deployed-bytes verification

The checked-in manifest redirects only the authoritative head call at `0x60C7F`
(VA `0x460C7F`) into the owned `.vv3mc` code section. The action call sites remain
stock; no handler-tail, action, timed-effect, or old `0x460A60` mask hook is emitted.
Missing DLL/exports or a failed atlas load degrades to the stock head with no mask.

## 6. Remaining player gates (not claimed accepted)

- **Pickup/held rendering:** the stock `+0xF12` branch reaches the authoritative
  head tuple, so the mask is emitted from that same tuple. Cursor-relative ownership
  and on-screen follow remain unproved; the player must provide the trace.
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

`0x42E3F5` is the sole direct caller of `sub_4605F0`; its handler derives the record with
stride `0x1F8C`. The authoritative appearance sequence loads `record+0xDF0` and
`record+0xF18`, then calls `0x42E5E0` at `0x460C7F` with the six-argument tuple. The
mask callback reuses that tuple synchronously. Generic task-1 swimming on terrain 5
remains head-owned; fishing task-11 frames 8/9 remain stock action-owned. `F20=42` is
only the stock water-renderer exception, not a claim that generic swimming assigns action
42.

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
