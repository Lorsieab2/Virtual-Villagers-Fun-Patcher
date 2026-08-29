# VV3 mask positioning — offscreen proof (no launching)

Verified by disassembly + ReadProcessMemory logging + arithmetic. Follows
`docs/head-mask-rendering.md` Parts 1–7.

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
internally. `docs/head-mask-rendering.md` rule 12 is correct as written.

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

Found with a per-draw diagnostic (`g_vv3_actdbg`, published at `0x6C7A38`).

The action-overlay wrap at `0x460B48` runs for **every** villager.
`sub_45F7E0` itself no-ops when the villager has no action frame, but the DLL
function did not — so for standing/walking villagers it drew a **second mask at
the action/body anchor**, detached from the head.

Logged proof (one frame): `actdbg [px,py,anim,facing,x,y] =
[1100, 971, -1, 0, 1076, 939]` — `anim == -1` is idle/walk, which must not
reach this path.

**Fix:** gate the action path to real action frames only (`anim` in `0..50`);
the world path owns `anim == -1`. Plus the world path skips `anim != -1`, so
exactly one path draws per villager, with no overlap.

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
0x460B48  call 0x47B360
0x47B360  push [esp+0xc] ; push [esp+0xc] ; push [esp+0xc]
          call 0x45F7E0                  ; original overlay
          mov eax,[0x6C7A30] ; test eax,eax ; je +
          push [esp+0xc] x3 ; call eax    ; DLL mask fn (null-guarded)
          ret 0xC
```

Matches intended asm; null pointer degrades to stock behaviour.

## 6. Known remaining gaps (not claimed fixed)

- The cave at `0x47B360` is `.text` tail padding — a **Part 7 violation**. Must
  move to an appended R-X section (the patcher already supports this via
  `pe_append_transaction`, used by `vv3_expanded_time_warp`).
- **Pickup**: identity is genuinely unavailable at `0x434357` — see §7. Grab-time
  capture is the only remaining route. Not yet implemented.
- **Details portrait**: facing source not yet verified against rule 6.

## 7. `0x5947D0` is an INIT LATCH, not a state flag (and `[ebp+0x10]` is a 3-way selector)

Settled statically, no launching. Top of the drag renderer:

```
4341e3  test byte [0x5947D0], 1     ; already initialised?
4341ea  jne  0x43422f               ; yes -> skip
4341ec  or   dword [0x5947D0], 1    ; no -> mark done
4341f3  mov  [0x5947B8], 0x6e   ; 110    entry 0 (x)
4341fd  mov  [0x5947BC], 0xa0   ; 160    entry 0 (y)
434207  mov  [0x5947C0], 0x72   ; 114    entry 1 (x)
434211  mov  [0x5947C4], 0xd4   ; 212    entry 1 (y)
43421b  mov  [0x5947C8], 0x4b   ;  75    entry 2 (x)
434225  mov  [0x5947CC], 0xb0   ; 176    entry 2 (y)
```

**The table has exactly 3 entries of constants** — it stops at `0x5947CC`
because the next 8-byte slot *is* `0x5947D0`. Therefore the index used at
`0x434312` (`mov ebp,[ebp+0x10]; shl ebp,3`) is **0..2**: a 3-way anchor/style
selector. It is **not** villager identity (100 slots needed) and **not** facing
(8 needed). Pickup identity is genuinely absent at `0x434357`; grab-time
capture is the only route.

All four references to `0x5947D0` are the same one-time-init idiom — test a
bit, skip if set, else OR it in and initialise a constant block:

| site | bit |
|---|---|
| `0x4341E3` | 1 |
| `0x43439C` | 2 |
| `0x4344D4` | 4 |
| `0x434644` | 8 |

So `0x5947D0` is a **4-bit initialisation latch**, permanently `0xf` after
startup, carrying no selection or pickup information. **Never gate on it.**

This mechanically explains the historic "masks drop to the floor" symptom: a
gate of the form `if (0x5947D0 & 1) return;` is true for *every villager on
every frame forever*, so the position path was always skipped.

`docs/head-mask-rendering.md` Part 3's VV3 entry describes this global as a
state that "reads 0xf on BOTH selection AND pickup" — that should be corrected;
it is not a state at all.
