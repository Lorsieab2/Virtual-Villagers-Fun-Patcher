# Head Positioning & Heathen-Mask Rendering — Cross-Game Reference

Consolidated RE for how the Virtual Villagers engine positions/orients a villager's
head, and how to draw a cosmetic mask that tracks it in **every** state (walk, bend,
sit, fish, swim, turn, pickup, Details portrait). Addresses are per-game; the
**mechanism and mask rules are universal**.

Engine age order (features accumulate forward; **evidence from a later game does not
transfer backward**): **VV1** A New Home → **VV2** The Lost Children → **VV3** The
Secret City → **VV4** The Tree of Life → **VV5** New Believers. VV5 is the most
sophisticated and the only one with a **native** heathen-mask system; VV1–VV4 build
masks from scratch.

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

2. **Mask atlas layout = FACING columns × COLOR rows.** VV5: 8 cols (facings) × 5 rows
   (Blue/Orange/Red/Purple/Chief), cell 65×145. **Column = facing. Row = color.**

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

7. **Anchor by the CHIN, not the sprite top or centroid.** Headdress/feather tops vary
   wildly by color (VV5: 23px spread across colors) while chins are stable (7px). Use a
   per-facing X nudge + per-color Y nudge; a full-sprite centroid drifts per color and
   the **chief breaks first**. VV5 reference numbers: per-facing content center-x
   `[42,40,31,30,36,36,34,33]` (13px turn swing), per-color chin
   `blue70/orange68/red69/purple63/chief70`.

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

10. **Alpha is inherited, and that's correct.** A faded mask on a submerged/swimming
    villager is right — the head is faded too; don't force full alpha. If children come
    out translucent, your mask went through a different (unscaled) blit than the head —
    route it through the **same scaled path**.

11. **Registration is engine-specific: convert, don't copy.** VV5's art encodes VV5's
    head proportions (cell coincidence → zero offset). Another game's heads differ, so
    it needs a scale/offset exactly where VV5 needs none. And the *drawn* head size ≠
    the head *cell* size (VV4's 40×65 cell draws a ~27px head — do not scale VV5's 65px
    art down to the cell; match the drawn size).

12. **Watch for DOUBLE-SCALING (the detached-mask trap).** Some draw functions
    multiply their x/y *internally* by a manager scale field (VV3: both `42E510` and
    `42E570` multiply x/y by `[mgr+0x300C]`). If you take those pre-scale world coords
    and add your own *screen-pixel* offset before the call, the engine scales your
    offset too → the mask flies off (detaches into open ground), independent of any
    anchor tuning. Fix: add offsets in the SAME space the fn expects — either add them
    *after* the internal scale (post-transform screen space) or divide your pixel offset
    by the scale factor before adding to pre-scale coords. Credit: VV2 found this in
    VV3's binary; it's the kind of thing only reading the draw fn reveals.

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

### VV3 — "The Secret City" (NO native mask → from-scratch)
- **Head atlas: sprite id `0x88`, 8 cols × 30 rows** (8 facings, `male_heads.png`).
- **Pickup:** drag object `0x5947E0` — cursor coords `+0x10`(x)/`+0x14`(y); 8 sprite
  handles `+0x68..0x84`; **no direct villager index/record ptr in it** (it holds draw
  specs, not identity). Held global `0x5947D0` reads **0xf on BOTH selection AND
  pickup** — useless for distinguishing them; gate pickup on the drag object instead.
- **Selection ≠ pickup:** the world loop *does* emit the dragged villager (record in
  ESI) but at the ground; a separate cursor renderer draws the visible copy at the
  cursor. Removing the skip puts the mask at the feet ("feet bug"). Fix: selection is a
  no-op (replay head-Y); redirect to cursor coords only when the drag object is active.
- **Action-pose overlay `sub_45F7E0`** (wrap point `0x460B48`): VV3 bakes the head into
  full-body pose sprites, so fishing/sit/swim heads sit at the hip until you hook the
  action draw and reuse *its* x/y. Verified dx/dy: per-facing dx (head_cx − mask_cx)
  `{-27,-21,-7,-4,-16,-14,-12,-15}`, head center-x `{17.5,19.2,23.8,25,20,21.2,22,18.5}`,
  per-color chin dy vs head_chinY=32 `{blue38,orange36,red37,purple31,chief38}`.
- Record base `0x59E124`, stride `0x1F8C`.

### VV4 — "The Tree of Life" (NO native mask → from-scratch)
- **Head via resolver `FUN_0044E960`.** Details compositor `FUN_0043CDF0`; head draw
  `FUN_00409A70` (`ecx` = drawmgr `0x4E00E0`) at `0x43CFDE`, body at `0x43D040`.
- **Facing field `+0x1CD4`.** **Portrait is FIXED-facing** (resolver output, no facing
  input) → hardcode the front column; no per-facing needed on Details.
- **Drawn head ≈ 27px** though the cell is 40×65 (mostly padding) → do **not** scale
  VV5's 65px art down; it already matches the drawn size.
- **Verified bighead values** (owner-confirmed recipe): mask **column 5** (0-based,
  front), `maskX = headX − 29×scale`, `scale = headScale × 2.6`, `maskY = headY −
  110×scale`, row = color−1. (Its engine anchors near the head center, hence the `−`.)

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
- **Custom Details bighead** (separate atlas `bigheads_masks.png` = frames 5/6/7 of
  `vv5_heathenheads.png` = owner-1-based, so 0-based cols 4/5/6): replay-then-reissue
  the head draw with the mask sprite; scale ×1.5; live-tuned per-facing/per-color
  offset tables + child offset (age<0x118).

---

## Part 4 — Field-finding recipes (for anything unknown above)

- **Head atlas + draw sites:** find the `"…heads.png"` string VA → scan `.text` for
  `push imm32` of it → the `mov [reg+disp],eax` after the ctor `call` is the atlas
  global; the `push`es before the ctor are `cols(facings) × rows(variants)`. Then
  enumerate **every** caller of the shared head-draw thunk that pushes a head atlas —
  walk / adult / swim / action are often separate callers with different arg layouts.
- **Facing field:** the record dword read to pick the head column at the draw site. It's
  a small int; the **portrait** facing is usually a *different* field than the world
  facing (one animates the idle turn; the other reads 0 on that screen).
- **Age / scale threshold:** the `cmp [rec+off], <threshold>` guarding a "draw smaller"
  branch — `off` = age, threshold = full-grown (`0x118` in VV1 & VV5).
- **Pickup discriminator:** live-diff candidate globals in two states — villager
  *selected & standing* vs *held at cursor*. The dword that **differs** is your pickup
  signal; one identical in both (VV3's `0x5947D0=0xf`) is selection-level → use the
  drag object.
- **Separate-index vs linear-frame draw fn:** if the draw fn `cdq/idiv`s an arg, it's a
  **linear packed frame** (`row*cols+col`); if two args go straight to the cell selector
  with no idiv, they're **separate row/col**. Detect per-fn and pack accordingly.

---

## Part 5 — Verification checklist (before reporting anything fixed)

1. **Hash** every deployed artifact (exe page, loose atlas, DLL) against its repo source
   — hashes, not timestamps.
2. If multi-stage, confirm the **final stage's input** was regenerated after your last
   source change (stale intermediate is the #1 cause of "I fixed it, nothing changed").
3. Verify the **shipped exe contains your change** (marker byte at the patched address).
4. Confirm **embedded copies match loose copies** (RCDATA vs shipped file).
5. Confirm the **running process started AFTER the exe was written**.
6. **Verify offscreen** (render the cell / dump final draw values), then have a peer
   sanity-check, **then** relaunch. Do not report fixed until seen in the running game.

---

## Part 6 — THE STANDARD (acceptance criteria; credit VV2)

A game's mask feature is done only when **all** of these pass — verified offscreen
(disassembly, static audit, hash-checked deploy), not by launching and looking. VV2 and
VV5 are the reference implementations.

1. **VILLAGE** — mask emitted *inside* the head's own draw, replaying its args with only
   atlas+frame swapped. Position, pose-bob, facing, scale inherited — never recomputed
   from record world coords.
2. **ACTIONS/POSES** (sit, bend, fish, swim) — every pose covered. Prove it with the
   **call-site audit**: enumerate every `call` to your head-draw thunk(s) and confirm
   each is inside your gate (VV2 is 100/100). A pose drawn from an ungated site is a
   silent failure.
3. **SELECTION** — clicking a villager does not move or drop the mask. Selection is
   **not** pickup; never gate on a selection flag.
4. **PICKUP** — the mask rides the head to the cursor. Gate on the **drag object being
   active**. No skip-when-held.
5. **DETAILS PORTRAIT** — correct facing source (portrait-only or fixed-facing, *not*
   the head-draw frame with its age offset), and lift/offsets that **scale with the
   portrait's own scale arg**, not fixed constants.
6. **IMMEDIATE LOAD** — saved masks visible on the **first village frame**, no menu
   opened. Test with **several different colours** (a single-colour test passes even
   with a broken index mapping).
7. **DEPLOY VERIFIED** — exe/DLL/atlas hash-matched repo↔deployed, and the process
   started *after* the exe was written.
8. **COMMITTED AND PUSHED** — the repo is the only memory that survives session restarts.
