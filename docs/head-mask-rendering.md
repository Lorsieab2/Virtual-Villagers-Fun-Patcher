# Head Positioning & Heathen-Mask Rendering — Cross-Game Reference

Consolidated RE for how the Virtual Villagers engine positions/orients a villager's
head, and how to draw a cosmetic mask that tracks it in **every** state (walk, bend,
sit, fish, swim, turn, pickup, Details portrait). Addresses are per-game; the
**mechanism and mask rules are universal**.

Engine age order (features accumulate forward; **evidence from a later game does not
transfer backward**): **VV1** A New Home → **VV2** The Lost Children → **VV3** The
Secret City → **VV4** The Tree of Life → **VV5** New Believers. VV5 is the most
sophisticated and the only one with a **native** heathen-mask system; VV1–VV4 build
masks from scratch. **VV5 is the sole behavioral reference for this project.** The
other games must reproduce its mask positioning, render ordering, head tracking,
screen-specific facing, action behavior, and pickup behavior while adapting the
mechanism to each executable's own architecture. Earlier-game evidence is useful for
mapping that architecture, but it does not redefine the target behavior.

---

## Part 1 — How the engine resolves the HEAD (the foundation)

Every frame the engine computes the head's final **position, scale, orientation** and
passes them to the head-draw call **as arguments**. That is the entire reason
"replay the head's own draw args" makes a mask track everything for free.

### 1a. POSITION (x, y) — two stages
1. **World → screen:** the villager's island/world coordinates are converted to
   screen coordinates via the camera/scroll offset. This is the base *body* anchor.
2. **Per-pose / per-facing HEAD ANCHOR OFFSET:** the engine looks up a table indexed
   by **animation × frame × facing** and adds a `(dx,dy)` head offset to the body
   anchor. In VV5 (`sub_451D00`):
   ```
   record = tableBase + anim*0x7A4 + (frameLo + frameHi*2)*0x1E8 + 0x7258
   head sprite id      = [record]
   base frame          = [record + 4]
   per-facing (dx,dy)  = [record + facing*8 + 0xF8]
   ```
   This offset is what makes the head **bob** while walking, **drop** when
   bending/fishing, and **sink** when swimming. Each pose+frame carries its own head
   anchor. Skip this and compute from raw world coords → the head/mask lands at the
   feet or hip.

### 1b. SCALE — per-villager, age-derived
VV5 (`sub_466240`): `if age([rec+0x1B8C]) < 0x118: scale = (age/DIV + BASE) * [rec+0x1CCC]`
else full size. Children draw smaller because their age yields a smaller factor.
`0x118` (280) is the full-grown threshold. The head sprite is drawn at this scale.

### 1c. ORIENTATION (facing)
A single facing index does two jobs: (a) selects the directional **column** of the
head atlas (which way the face points); (b) indexes the per-facing anchor above
(`[record + facing*8 + 0xF8]`) — a left-facing head sits at a slightly different x
than a right-facing one. The facing is derived from movement direction / state and
stored on the record; the head sprite frame may get an age/variant offset on top.

---

## Part 2 — MASK RULES (what you actually have to get right)

1. **Replay, don't recompute.** Hook the head-draw call, replay its exact args, swap
   only the atlas pointer + frame. The mask inherits position + pose-bob + facing +
   scale + pickup for free. **Recomputing position from the record's raw world coords
   — dropping the per-pose anchor offset — is what puts the mask at the feet/hip.**

2. **Mask atlas layout = FACING columns × COLOR rows.** VV5's native village atlas is
   8 cols (facings) × 5 rows (Blue/Orange/Red/Purple/Chief), cell 65×145. Its active
   custom Details atlas is separately registered as sprite `0x155`, 3 portrait-facing
   cols × 5 color rows. **Column = the current screen's facing. Row = color.**

3. **Select the mask column EXPLICITLY — never reuse the head's frame index.** The head
   atlas and mask atlas have *different* column layouts, so the head's frame maps to
   the *wrong* mask column (turned/profile mask). Map facing→mask-column yourself, or
   for a fixed-facing portrait hardcode the front column.

4. **FRAME-INDEX OFF-BY-ONE (this burned VV5 for hours):** the owner counts frames
   **1-based** (leftmost = frame 1). Owner "frames 5/6/7" (right/front/left) =
   **0-based columns 4/5/6**. Front alone = owner frame 6 = **0-based col 5**. Reading
   them 0-based grabs the wrong (profile) frame.

5. **Row = mask COLOR from your side-table** (color−1 for 0-based). Not head-derived.

6. **Facing SOURCE differs by screen.** Village = the villager's real 8-way facing.
   **Details portrait = a portrait-only facing field** (VV5 `record+0x2F3C mod 3`),
   NOT the head-draw frame (which carries an **age offset** that breaks aged
   villagers). A fixed-facing portrait needs no facing at all — just the front column.

7. **Anchor on the FACE, never the sprite top — and validate by RENDERING, never a proxy
   metric.** Headdress/feather tops vary wildly by color (VV5: 23px spread), so never
   anchor by the top. For the face anchor itself, **the right metric is art-dependent and
   no proxy is universally safe:**
   - A **skin/opaque centroid** is safe *only if the back of the head is hair* (then the
     skin region is effectively the face). If skin is visible at the back — bald/shaved
     variants, an exposed nape, a low ponytail — the centroid is dragged toward it and
     diverges most on **profile** facings (VV3 measured up to 8px, anti-correlated).
   - An **eye-line** detector fixes that case — but it can *itself* be fooled: on a profile
     head, dark hair in the upper-face band reads as "eyes" on the side *opposite* the
     face, producing the exact same anti-correlation (VV2 saw 6.3px this way). The tell
     that a detector is lying: the face moves only ~3.5px across facings while the "eyes"
     move ~9px the *other* way — real eyes move *with* the face.
   - **So don't trust either proxy blind. The unambiguous check is to RENDER the actual
     baked mask atlas over the actual head atlas, at every facing × color × a few head
     variants, drawn exactly as the exe does (`cell at (x, y−LIFT×scale)`), and eyeball
     whether the mask sits on the face.** Two games confirmed their seating this way and
     it agreed with in-game; the proxy metric was the odd one out. This is an instance of
     Part 5.6: *a proxy can fail the same way the thing it checks fails.*
   Reference numbers (measure your own per art): VV5 chin-based per-facing content
   center-x `[42,40,31,30,36,36,34,33]`, per-color chin `70/68/69/63/70`; VV3 eye-based
   per-facing eye-x `{17.5,17.5,25,25,19.5,21.5,23.5,16}` (its heads expose nape skin, so
   eye-line was right there); VV2 skin-centroid holds (its heads are hair-backed).

8. **Scale + LIFT must scale together.** Draw at the head's own scale arg (× an
   art-size bump if you reuse the village atlas — VV5 bighead ×1.5, VV4 ×2.6). The lift
   that lands the face is `cornerY = headFaceY − scale × maskFaceY_within_cell`; a raw
   constant won't hold across scales/ages. **Trust a MEASURED correction over a
   formula** — anchor conventions vary per engine (VV4's verified `maskX = headX −
   29×scale` contradicted the naive `+` formula because its engine anchors near the
   head *center*, not the corner).

9. **Pickup:** the mask rides the head draw wherever it goes. Gate any cursor-redirect
   on the **drag object being active**, NOT a selection flag — selection ≠ pickup, and
   keying on selection drops the mask to the floor when you merely click a villager.

10. **Map/overview is a separate surface until proven otherwise.** A village-render
    hook does not establish map coverage. Identify the map/overview compositor and
    replay its own head arguments, or prove that it reaches the already-covered head
    path. If neither is shown, map status is **unknown**, not inherited.

11. **Alpha is inherited, and that's correct.** A faded mask on a submerged/swimming
    villager is right — the head is faded too; don't force full alpha. If children come
    out translucent, your mask went through a different (unscaled) blit than the head —
    route it through the **same scaled path**.

12. **Registration is engine-specific: convert, don't copy.** VV5's art encodes VV5's
    head proportions (cell coincidence → zero offset). Another game's heads differ, so
    it needs a scale/offset exactly where VV5 needs none. And the *drawn* head size ≠
    the head *cell* size (VV4's 40×65 cell draws a ~27px head — do not scale VV5's 65px
    art down to the cell; match the drawn size).

13. **Watch for DOUBLE-SCALING (the detached-mask trap).** Some draw functions
    multiply their x/y *internally* by a manager scale field (VV3: both `42E510` and
    `42E570` multiply x/y by `[mgr+0x300C]`). If you take those pre-scale world coords
    and add your own *screen-pixel* offset before the call, the engine scales your
    offset too → the mask flies off (detaches into open ground), independent of any
    anchor tuning. Fix: add offsets in the SAME space the fn expects — either add them
    *after* the internal scale (post-transform screen space) or divide your pixel offset
    by the scale factor before adding to pre-scale coords. Credit: VV2 found this in
    VV3's binary; it's the kind of thing only reading the draw fn reveals.
    **CAVEAT — measure the camera before blaming it.** The multiply only matters if the
    camera actually zooms. VV3 measured `[mgr+0x300C] = 1.0` at runtime (its village
    doesn't zoom), so the double-scale was a NO-OP there and could NOT have detached the
    masks. Express offsets in world units anyway (correct at any camera, free at 1.0),
    but if masks detach at camera=1.0, the cause is a double-**DRAW**, not double-scale —
    see rule 14.

14. **An UNGATED hook draws a phantom second mask.** If your hook sits on a call that runs
    for every villager while the underlying painter no-ops for some of them, your added draw
    must use the same ownership condition. VV3's repaired world hook is the real appearance
    head call (`0x460C7F -> 0x42E5E0`), so the mask is emitted inline only after a stock head
    draw and later full-body action rendering can cover it. The former action wrappers and
    deferred handler-tail draw are removed. **Corollary — never give the mask a RECOMPUTE
    FALLBACK (VV3's feet-mask cause):** when a carried villager has no proven cursor-leaf
    tuple, the candidate fails closed instead of painting at an abandoned ground anchor.

---

## Part 3 — Per-game appendix (comprehensive)

### VV1 — "A New Home" (earliest; NO native mask → from-scratch)
- **Head atlas ctor:** `0x40A070(this, "male_heads.png", 7, 0x14)` → **7 facings × 20
  variants**. Globals: male `[gameobj+0x3DFF8]`, female `[gameobj+0x3DFF4]`.
- **Adult head atlas** `[gameobj+0x3E008]` = **4 cols × 1 row** (adults use 4 facings,
  1 variant).
- **THREE head-draw paths — different arg semantics, hook all three:**
  - child-walk `0x409410 → 0x408AF0` — 7 args, `ret 0x1C`, **separate row/col**.
  - adult `0x4093E0 → 0x408840` — 5 args, `ret 0x14`, **LINEAR packed frame** (the fn
    `cdq/idiv`s arg4 into row,col). Args: `arg1=sprite, arg2=x, arg3=y, arg4=facing,
    arg5=0.4f scale`. `0x402F70` is `ret 0` and the `0.4f` survives (caller never
    cleans it) → arg5.
  - child-swim/action `0x4093C0 → 0x408740` — 5 args, **separate row/col**.
- **Age split:** `cmp [rec+0x348], 0x118`.
- **Facings = 7 ⇒ drop the mask atlas's 8th column.**
- **Linear-frame packing (adult path):** `maskArg4 = colorRow * MASK_COLS + facing`,
  where MASK_COLS = your mask sprite's *registered* column count.
- **Details exact-argument wrapper:** all four head calls (`0x43741B`, `0x4374A4`,
  `0x437503`, `0x437556`) remain five-byte CALLs and route through one
  ABI-compatible wrapper at `0x490720`. It duplicates and replays the untouched seven
  native arguments, then changes only atlas/color row and the scale-aware mask lift.
  VV1 applies `y = args[2] - (scale >> 3) - 15` and `x = args[1] + 1` for this Details-only overlay
  (screen Y grows downward, so the trailing term lifts the mask 15 pixels, and
  the X term moves it one pixel right); the village renderer keeps its existing
  registration. VV2 overrides BOTH nudges before inclusion -- Y to `+3`, which
  seats its Details masks three pixels LOWER rather than lifting them, and X to
  `+4`, the horizontal registration it was tuned to. It does not reconstruct X/Y
  from age buckets or facing from a global.
- **Map/overview:** the village caller gate intentionally excludes UI/map clusters.
  No map compositor has yet been bound to a villager record and exact head tuple, so
  map coverage is unknown and must not be claimed from the village hook.
- **Pickup boundary (static):** the exact chain `0x4392D0 → 0x439410` has the
  `0x4392D0` hit-test called at `0x425226`, and the `0x439410` drag updater called at
  `0x425937`/`0x423FD1`. The frame path `0x424090` then calls compositor `0x437790`,
  whose two record loops are `0x437790`/`0x4388E0`; the related Details head calls are
  `0x43741B`, `0x4374A4`, `0x437503`, and `0x437556`. This proves where ordinary records
  re-enter rendering, but held-mask visibility remains runtime-unverified and requires
  player acceptance.
- **Sidecar/slot-reuse hardening:** the shared getter rejects corrupt mask nibbles
  above the supported `0..5` range before atlas-row use. At the exact stock
  newborn/allocation boundary `0x43C393`, the patch-owned nibble is cleared before
  record reuse, marked dirty, and persisted through retryable sidecar writes; the dirty
  marker is cleared only after both writes succeed. This is static protection and does
  not constitute player/runtime acceptance.
- **Transactional sidecar publication:** VV1 writes the unchanged magic-plus-table
  payload to a separately bounded `<final>.tmp`, checks both writes and exact byte
  counts, flushes and closes it, and only then publishes through
  `MoveFileExA(REPLACE_EXISTING|WRITE_THROUGH)`. A write, flush, close, or publish
  failure removes only that temp path, preserves the last valid final sidecar, and
  leaves the existing dirty retry behavior intact.

### VV2 — "The Lost Children" (NO native mask → from-scratch)
- **7 facings** (drop the 8th mask column). Four head atlases incl. elder variants:
  male `[esi+0xE574AC]`, female `[esi+0xE574A8]`; push-imm32 sites `0x44C34D` /
  `0x44C25D`. Head cell 40×65. Villager index table `0xE57090`.
- **Mask emitted *inside* the head draw** (replays the head's stack args, atlas swapped)
  → facing + scale come free on both village and portrait. Caller-range gate covers
  **all** head-draw sites `0x445540..0x449060` (68 head-atlas call sites total; the
  **pose renderers** — swim/sit/lie/bend — are a contiguous band ABOVE the walk loop,
  `0x447ADD..0x449049`; miss them and the mask vanishes the moment a villager leaves
  the walking pose).
- **Adult stub record deref:** `esi + [esi+edi*4+0xE57090]*0xE48C` (valid only where
  `edi` is the loop index).
- **Packaging:** atlas embedded as **RCDATA in the DLL** + self-extracted at startup
  (atomic `.tmp`→`MoveFile`), so a loose file can't go missing.
- **Sidecar validation:** restore sanitizes every table byte to the closed range
  `0..5` before copying it into the render table, and both adult and scaled
  consumers repeat that range check before subtracting one for the atlas row.
  This is fail-closed for malformed or hand-edited sidecars.
- **Slot reuse boundary:** the compositor sweep clears a masked slot only after
  observing it active and then free. The exact VV2 birth/allocation routine is
  known as `sub_44C600`, but this checkout has no reviewed call-boundary proof
  that it is exclusive to newborn creation rather than load/initialization, and
  VV2 has no established stable identity field. Therefore the narrower
  free→newborn transition that occurs entirely between two sweeps remains
  runtime/evidence blocked; no guessed birth detour or invented record offset is
  installed. A player trace or reviewed exact-build birth boundary is required
  before adding that final guard.
- **First-frame receiver preservation:** the sweep enters through `0x445B50`
  with the compositor receiver in `ECX`, then may call the companion's
  `Vv2MaskRestore`. That stdcall may clobber volatile `ECX`. The shipped sweep
  incorrectly reused the live register and the 2026-08-29 Windows crash record
  landed on its first `record+0x30` read at generated RVA `0xB437C`. The sweep
  now reloads the entry receiver saved by `pushad` at `[esp+0x18]` before the
  scan. Generated-byte tests pin that reload before the first record read;
  player confirmation that startup now completes remains pending.

### VV3 — "The Secret City" (NO native mask → from-scratch)
Confirmed in the exact stock executable (`Virtual Villagers - The Secret City.exe`, SHA-256
`8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503`):

- The normal villager handler is `sub_4605F0`; `0x42E3F5` is its sole direct caller.
- The handler derives a villager record from its index using stride `0x1F8C`. The old
  `0x460A60 -> 0x42E570` hook is a generic fixed-resource draw and is not an appearance
  tuple. The authoritative stock head draw is `0x460C7F -> 0x42E5E0`; stock loads
  record `+0xDF0`/`+0xF18` and supplies `(atlas,x,y,head-row,facing,scale)`.
- The action overlay is `sub_45F7E0`, reached at the proven action call sites
  `0x460B48` and `0x460D10`; both remain byte-identical to stock.
- The mask patch's Details and inline world-head hooks use the owned `.vv3mc` (R-X) /
  `.vv3md` (R/W) sections. No action wrapper or handler-tail mask draw is installed.
- **World ownership:** the cave at `0x460C7F` replays all six stock head arguments, then
  synchronously calls `0x42E5E0` with only mask atlas and row replaced. The stock held
  `record+0xF12 != 0` branch rejoins this same body/head sequence, so held masks reuse
  the authoritative tuple; cursor coordinate ownership and visual follow remain runtime
  acceptance gates. Stock action poses remain their own full-body renderer; no guessed
  mask seating is emitted. Generic task-1 swimming and task-11 fishing remain runtime
  acceptance gates.
- **Sidecar/identity validation:** every loaded mask byte is sanitized to the supported
  `0..5` range before it can enter the DLL table or reach a renderer. An individual
  getter/setter requires exactly one active/living record and one stored owner for its
  gender+Likes+Dislikes fingerprint. The whole-village dialog has one narrower collision
  exception: it first plans every active/living villager, gives every simultaneous owner
  of one fingerprint the same mask, and stores exactly one identical copy per live owner.
  Rendering accepts that group only while live-owner count, stored-copy count, and mask
  value all still agree. Incomplete or mixed groups fail closed. Equal, Random, and
  VV5-style proportions may therefore be adjusted at collision-group granularity instead
  of preserving exact global counts. Individual chooser commits remain unique-only.
  Grant Running likewise retags only a fingerprint unique in immutable live and stored
  preimages. A later replacement/newborn with the exact same fingerprint after
  the old villager is gone remains indistinguishable:
  no stable name, identity, or allocation-generation field is proven in the current
  exact-build evidence.
- **Transactional sidecar publication:** VV3 writes the unchanged `MSK3` payload to a
  separately bounded `<final>.tmp`, verifies all three writes and exact byte counts,
  flushes and closes it, and only then atomically replaces the final with write-through.
  The village-wide path publishes its complete shadow sidecar before any head/body or
  live mask-table mutation; any path/create/write/flush/close/replace failure returns with
  no appearance change and no 450,000-point charge. Any failure deletes only the temp
  path and preserves the prior final sidecar.
- `0x4341A0..0x434758` is one three-style timed sprite/particle effect object. It iterates
  24-byte entries, compares elapsed time to `0x12C`/`0x7080`, and uses three fixed anchors
  `(110,160)`, `(114,212)`, `(75,176)` from `0x5947B8..0x5947CC`.
- `0x434357` calls the generic scaled-sprite draw `0x42E570` with a sprite selected from a
  three-entry effect table. `0x4344B3` calls the generic cell blit `0x42E510` in the same
  effect object. Neither call has a villager record or held identity.
- The pickup drag object is `0x5947E0` (cursor coordinates `+0x10`/`+0x14`; sprite
  handles `+0x68..0x84`), but it carries no direct villager index or record pointer.
- `0x5947D0` is a four-bit initialization latch, not selection, pickup, or villager state.
  It is written by test/skip/OR initialization idioms and must never gate mask rendering.

Therefore `0x434357` and `0x4344B3` remain byte-identical to stock; they are not pickup
hooks. The known normal-handler/head tuple is also reached while `record+0xF12` is set,
so the candidate reuses it for held rendering. Cursor coordinate ownership and final
visual follow still require a player trace. Record base is `0x59E124`, stride `0x1F8C`.

### VV4 — "The Tree of Life" (NO native mask → from-scratch)
- **Confirmed Details call chain:** `0x447D30` → `0x460BF0` → `0x45F550`; the body
  draw is at `0x45F653` and the head draw is at `0x45F702`. The previously claimed
  `0x45F965` site is disproven and must not be used as a hook target.
- **Confirmed central live renderer:** type-7 world records reach `0x467DA0` and
  issue the exact head call at `0x468263`; the dead branch returns without drawing.
  These are confirmed static boundaries for ordinary village/action rendering, not
  proof of held/cursor ownership.
- **Current detour boundary:** the reviewed mask work targets the proven Details head
  boundary at `0x45F702` and the central live type-7 world head boundary at `0x468263`.
  The Details replay preserves the live seven-argument X/Y/scale tuple, derives its
  three-way portrait column from `record+0x2E38 mod 3`, and uses a dedicated 3x5 atlas
  byte-identical to VV5's approved bighead atlas at 1.5x native head scale. It also ports
  VV5's per-facing X, per-row Y, base lift, and young-villager corrections; Purple includes
  the current player-requested +5px adjustment. Static coverage still does not prove
  held/cursor ownership, cursor coordinates, final player-visible Details seating, or
  pickup behavior; those remain runtime/player acceptance gates.
  No older `0x43CFDE`/`0x45F965`/fixed-facing portrait theory substitutes for that evidence.
- **Identity guard:** the companion side-table is keyed by record index but stores a
  stable gender+name fingerprint with each nonzero mask. `Vv4MaskGetForRecord` compares
  that fingerprint against the current live record before returning a mask, so a newborn
  reusing an occupied slot cannot inherit the deceased villager's mask. If the first load
  frame exposes a record before its name is initialized, the lookup still returns no mask
  for a mismatch but defers destructive invalidation until a prior completed present-path
  sweep has promoted that slot to identity-ready; a confirmed mismatch then clears the
  entry and persists the current save's sidecar. No villager-record bytes are written, and
  mutable head/body/preferences are deliberately excluded from the identity.
- **Transactional sidecar publication:** VV4 writes the unchanged `VVMK` payload to a
  separately bounded `<final>.tmp`, checks all four `WriteFile` calls and exact byte
  counts, flushes and closes it, and only then atomically publishes with
  `MoveFileExA(REPLACE_EXISTING|WRITE_THROUGH)`. Any failure removes only that exact
  temporary path, preserving an existing final sidecar; a missing final is published
  normally after the same complete-success gate.

### VV5 — "New Believers" (latest; HAS native heathen masks)
- **Native mask atlas** `vv5_heathenheads.png` — sprite id **`0x101`, 8 cols × 5 rows**,
  cell 65×145. Village masks = **native faction-flip** (set the heathen fields, the
  engine draws the mask as part of the native head render).
- **Details compositor `sub_466C40`.** Head draw `call 0x409CA0` at `0x466E05`.
  **Native portrait mask block `0x466E0A..0x466ED8`:** gate `[esi+0x1C4C]`; head anchor
  via `call 0x466350`; draw `0x409D00`; per-villager offsets `[esi+0x1C98]`(x)/`[esi+0x1C9C]`(y);
  fixed frame 3; scale `0xC8`; layers `[esi+0x1C50]` (extra draws at Y−8 / Y−0xD).
- **Portrait facing:** `record+0x2F3C mod 3` (→ cols, the compositor draws the head
  with `(2F3C mod 3)+8`). NOT the age-offset draw frame.
- **Scale:** `sub_466240` (age `[rec+0x1B8C]`, threshold `0x118`, per-villager scale
  `[rec+0x1CCC]`). **Anchor table:** `sub_451D00` (`[record+facing*8+0xF8]`).
- **Record:** base `0x554190`, stride `0x2F44`, 150 slots. Fields: active `+0x1CD4`,
  sex `+0x1B90`, age `+0x1B8C`, head `+0x1BB8`, body `+0x1BBC`, faction `+0x1CEC`,
  mask colors `+0x1CED`(orange)/`+0x1CEE`(red)/`+0x1CFC`(rank: 12=purple,13=chief).
  Cosmetic-mask side-table `0x7B1D20` (nibble-packed by index). Save-slot builder
  `sub_403600`. Draw context `[esi+0x2F2C]`.
- **Custom Details bighead:** separate atlas `bigheads_masks.png`, registered as
  sprite id **`0x155`, 3 cols × 5 rows**, using owner frames 5/6/7 of
  `vv5_heathenheads.png` (owner-1-based, so source cols 4/5/6). The wrapper
  replay-then-reissues the head draw with the mask sprite; scale ×1.5; live-tuned
  per-facing/per-color offset tables + child offset (age<0x118).
- **Current evidence boundary:** the Task9 source statically proves the village
  bracket and Details wrapper. It does not yet map a distinct map/overview route or
  prove active pickup/held/release ownership. Those surfaces remain unknown even in
  the reference implementation until traced and accepted by the player.

---

## Part 4 — Field-finding recipes (for anything unknown above)

- **Head atlas + draw sites:** find the `"…heads.png"` string VA → scan `.text` for
  `push imm32` of it → the `mov [reg+disp],eax` after the ctor `call` is the atlas
  global; the `push`es before the ctor are `cols(facings) × rows(variants)`. Then
  enumerate **every** caller of the shared head-draw thunk that pushes a head atlas —
  walk / adult / swim / action are often separate callers with different arg layouts.
- **Data-driven atlas loaders (the push-imm32 recipe FAILS here — VV3/VV4).** If the
  filename strings have ZERO `.text` references, the atlases are loaded by a **table walk**
  (a filename table iterated in a loop), so there's no `push imm32` to anchor on. Fallbacks:
  (a) find the READ site of the atlas holder instead — a `mov edx,[reg+disp]` feeding a
  head-draw push (VV3's authoritative appearance tuple is read at `0x460C7F`; the
  older `0x460A60` generic draw is not a head-appearance boundary);
  (b) **runtime caller-capture** — probe the low-level blit's entry, log the return address
  + atlas pointer, and capture what fires *per frame* on the screen you care about. The
  caller that repeats while (e.g.) a Details portrait head is animating is your hook. Static
  search can't find an animated/portrait draw that a data-driven loader hides; the runtime
  probe finds it in one capture.
- **Facing field:** the record dword read to pick the head column at the draw site. It's
  a small int; the **portrait** facing is usually a *different* field than the world
  facing (one animates the idle turn; the other reads 0 on that screen).
- **Age / scale threshold:** the `cmp [rec+off], <threshold>` guarding a "draw smaller"
  branch — `off` = age, threshold = full-grown (`0x118` in VV1 & VV5).
- **Pickup discriminator:** live-diff candidate globals in two states — villager
  *selected & standing* vs *held at cursor*. The dword that **differs** is your pickup
  signal; one identical in both is not it → use the drag object. **First, rule out a
  LATCH:** if a candidate "state" global is only ever touched by `test`/`or` idioms and
  is **never cleared**, it's a one-time-init latch (permanently set after startup), not a
  state — VV3's `0x5947D0` is exactly this (`0xF` forever). Gating on a latch runs (or
  skips) the path for *every* villager forever — a silent, total failure. Cheap to check,
  and the failure mode looks like "the feature never works."
- **Separate-index vs linear-frame draw fn:** if the draw fn `cdq/idiv`s an arg, it's a
  **linear packed frame** (`row*cols+col`); if two args go straight to the cell selector
  with no idiv, they're **separate row/col**. Detect per-fn and pack accordingly.

---

## Part 5 — Verification checklist (before reporting anything fixed)

1. **Hash** every deployed artifact (exe page, loose atlas, DLL) against its repo source
   — hashes, not timestamps.
0. **Check that the patcher APPLY actually SUCCEEDED.** A cave/section collision between
   two patches makes the apply FAIL, so the exe is never rewritten — and every subsequent
   "fix" silently changes nothing in the running game. VV4 lost a WEEK to this: diagnostic
   caves collided in `.shr` (overlap at 0xCC220 with another feature), the apply failed
   every time, and all week's observations were of a stale exe. Verify the apply result
   itself, then the hashes. (This is Part 7's cave-collision warning happening for real.)
2. If multi-stage, confirm the **final stage's input** was regenerated after your last
   source change (stale intermediate is the #1 cause of "I fixed it, nothing changed").
3. Verify the **shipped exe contains your change** (marker byte at the patched address).
4. Confirm **embedded copies match loose copies** (RCDATA vs shipped file).
5. Confirm the **running process started AFTER the exe was written**.
6. **Verify offscreen** (render the cell / dump final draw values), then have a peer
   sanity-check, **then** relaunch. Do not report fixed until seen in the running game.
   **Validate the ANCHOR, not just the arithmetic (VV3).** A marked-composite eyeball
   proves your formula matches your *measured* anchors — but if a measurement is wrong the
   arithmetic is still self-consistent and you'd never know. So measure each anchor by
   **≥2 independent features and require agreement** (e.g. eye-median vs opaque-bbox vs
   skin-centroid). Specifically: a skin/opaque centroid is anti-correlated with the face on
   profile facings — if your three measures disagree there, trust the **eye-line** (rule 7).
   Note: there is usually **no** confirmed-from-code source for "where the face sits inside
   the head cell" (the engine just blits the cell), so multi-feature art measurement is the
   only ground truth for that quantity — and cross-checking it against the engine's
   body→cell *anchor* table proves nothing (different quantity).

---

## Part 6 — THE VV5 STANDARD (acceptance criteria)

A game's mask feature is done only when **all** of these pass. Static evidence
(disassembly, source audit, and hash-checked deploy) is necessary but does not replace
launching the exact deployed build and obtaining player/runtime acceptance. **VV5 is
the sole behavioral reference.** VV2 can corroborate an architectural technique, but
it cannot lower or alter the VV5 behavior required of any game.

1. **VILLAGE** — mask emitted *inside* the head's own draw, replaying its args with only
   atlas+frame swapped. Position, pose-bob, facing, scale inherited — never recomputed
   from record world coords.
2. **MAP/OVERVIEW** — every villager shown there has the same mask identity, facing,
   scale, and head registration as that surface's own head. Prove whether the map uses
   the village renderer or a separate compositor; do not infer it.
3. **ACTIONS/POSES** (sit, bend, fish, swim) — every pose covered. Prove it with the
   **call-site audit**: enumerate every `call` to your head-draw thunk(s) and confirm
   each is inside your gate (VV2 is 100/100). A pose drawn from an ungated site is a
   silent failure.
4. **SELECTION** — clicking a villager does not move or drop the mask. Selection is
   **not** pickup; never gate on a selection flag.
5. **PICKUP** — the mask rides the head to the cursor. Gate on the **drag object being
   active**. No skip-when-held.
6. **DETAILS PORTRAIT** — correct facing source (portrait-only or fixed-facing, *not*
   the head-draw frame with its age offset), and lift/offsets that **scale with the
   portrait's own scale arg**, not fixed constants.
7. **IMMEDIATE LOAD** — saved masks visible on the **first village frame**, no menu
   opened. Test with **several different colours** (a single-colour test passes even
   with a broken index mapping).
8. **DEPLOY VERIFIED** — exe/DLL/atlas hash-matched repo↔deployed, and the process
   started *after* the exe was written.
9. **COMMITTED AND PUSHED** — the repo is the only memory that survives session restarts.

---

## Part 7 — Where patch code and data must live (credit VV2)

**The OWNER'S requirement (verbatim in substance):** *"Do not touch the actual saves or
game files. Put all changes in DLLs or separate files. Don't squeeze stuff in code
caves."* That is the mandate: no cave-squeezing, no save/stock-file edits, changes live
in DLLs or separate files.

**Appending your own PE sections is the RATIFIED TECHNIQUE for meeting it — not the
owner's wording.** It is the engineering approach the existing VV2/VV5 implementations use, ratified
indirectly by the owner's ruling *"Make the safest changes for ALL patches and mods to
work with ZERO RISK of corruption, collision or bugs."* If a game can satisfy the
owner's actual requirement another zero-risk way, that is permissible; and **any fresh
interpretation from the player outranks anything any chat inferred** (credit: the FPT
chat for the attribution catch).

Why caves are banned: code or data placed in `.text` padding, alignment gaps, or an
unused payload region *collides* — two patches wanting the same region silently corrupt
each other ("the payload block was full" is that collision already happening, and a
collision made VV4's patcher apply fail for a week).

**The self-audit (one line):** dump your patched exe's section table. **If your code or
data is not in a section you added, you are in a cave and must move it.**

**Shape:** one **R-X** section for code, one **R/W** section for data. Never R/W/X — a
writable+executable section reads as self-modifying code to AV (Malwarebytes flags it)
and is a quarantine risk if anything writes there at runtime.
- VV2: `.vvmk` R-X (render stubs) + `.mtab` R/W (mask table, seen-alive latch, atlas ptr).
- VV5: `.vv5t9` R-X (all mask render code) + tail of stock `.data` R/W (scratch, nibble
  side-table).

Different arrangements, identical principle: **W^X separation**. Note both existing
implementations keep the per-draw **render stub as exe-side asm in the appended R-X
section**, not in the DLL — that's the hot path (runs every head draw every frame), so a
per-draw DLL round-trip is real cost for no gain. "Out of caves" is satisfied by the
appended section; moving render logic *into* the DLL is a separate, explicit choice.

**Appending, mechanically:** extend the section table; set VirtualAddress to the next
aligned VA past the last section; set characteristics (`0x60000020` = R-X for code; R/W
for data); append the raw bytes; fix `SizeOfImage`; recompute the PE checksum. **Size
generously** (0x1000 even for small use) — growing a section later means relocating
everything after it. **NEVER** extend an existing section's VirtualSize to reach the next
section's base — that crashes at launch. The `.text` edits stay minimal: detours
(jmp/call) into your appended section, nothing more.

**DLL owns the higher-level logic:** init, atlas registration, sidecar persistence, and
any dialogs live in the companion DLL; the exe stub just calls in / reissues the draw.

**Persistence & assets:**
- Mask choice → a **sidecar file** next to the `.ldw` (e.g. `vvfp_masks_<slot>.dat`).
  Never read/write the save, never patch save code. A record byte is allowed only if
  proven unused (4-part proof); a sidecar avoids the question.
- **Key the sidecar PER SLOT, and reload on slot change — or a 2nd village bleeds the
  1st's masks (and overwriting the sidecar destroys the 1st's choices).** Recipe (VS5's,
  ports to any `"%s%d.ldw"` builder): hook the **save-path builder itself** (VS5
  `sub_403600`; VV2 `0x474400`); capture the slot arg, stash **only when slot != 0** (0 =
  meta, never a village). When the captured slot **differs** from the last, **clear a
  `loaded` flag** — do NOT read the sidecar here: the path builder fires DURING load,
  *before* the records are in memory. Do the actual `ReadMaskSidecar` at the **first
  village render frame** (records present by then), gated by that flag. Never-seen slot →
  the per-slot file is absent → **zero the table** (no masks beats wrong masks). Make the
  restore fn **re-callable**, not once-from-init. A newborn reusing a dead masked slot:
  clear its nibble at birth, or use a **seen-alive latch** (clear a slot's mask only after
  it was observed ACTIVE and *then* went free — also avoids wiping restored masks on load
  frames where slots momentarily read empty).
- **Fail open on `MAX_PATH`:** before any unbounded Win32 string append, budget the
  complete `<Documents>\\LDW\\<exe-basename>\\vvfp_masks_<slot>.dat` path including
  its terminating NUL. If it cannot fit, skip sidecar persistence; never truncate the
  basename, change the save-slot namespace, or risk overwriting the caller's stack.
  Apply the same complete-path budget to the executable-directory atlas load;
  an overlong install path must fail open before appending `Images\\vvfp_mask_atlas.png`.
- Atlas/art → **new companion files only**, never an edit to stock art. Prefer
  **RCDATA-embedded in the DLL, self-extracted to `Images/…` only if absent** (exe-dir
  absolute path, `CREATE_NEW`) so a clean install can't get a sprite pointer with no art
  and replacement art is respected.

**Known inherited issues (shared Origins patch stack, NOT the mask feature — flag, don't
diverge locally):** (1) a small **RWX `.shr`** section (VV2 + VV5). (2) **RWX `.rdata`**
(`0xE0000040`) — the Origins build marks `.rdata` executable to host caves there (VV3
found it deployed; same class). Both are W^X violations in the shipped artifact owned by
the shared patcher; a future tidy-up, not a per-game fix.

**Crash exposure — absolute address in a patch-added section touched from the DLL (VV2).**
If your DLL reads/writes an absolute address that lives in a section the *mask patch* adds
(`.mtab`/`.vvmk`/appended page), a **patcher build that ships the DLL + UI without that
section applied** hits an unmapped access on the first mask op = crash. VV2 hit this at
`0x004B3000` (one byte past the stock image). Fix: `VirtualQuery`-probe the address once,
cache it, and gate every path (no section → masks read as none, writes drop, sidecar
skipped). **Any game whose DLL touches a patch-section absolute address has this shape —
check it.** (VS5: its side-table sits in stock `.data`, always mapped — verify yours does
too, or add the probe.)
