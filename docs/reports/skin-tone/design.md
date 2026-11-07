# Skin tones for A New Home: phase 1 design

**Status: research and design only, for the owner's approval.** Nothing in this note is built or
shipped yet. No game file and no save was changed. No game art is committed.

The previews were made from the stock sheets of a vanilla A New Home copy by
`scripts/vv1_skin_tone_preview.py`. That script writes its pictures outside the repository and
refuses to write inside it. They are in the session scratchpad, `skintone\final\`.

## What the owner decided (2026-11-06)

- **Per villager, with inheritance.** Each villager has their own tone. A baby's tone is a blend of
  its parents' tones. It is never random at birth.
- **Chosen in Change Appearance.** There are presets plus a fine control, in both windows.
- **Founders and arrivals get a random tone.** These are the starting villagers and anyone who
  joins from outside. The tone is stored the first time the patch sees them (owner, later the same
  day).
- **Pilot in A New Home.** It ships in a new version (v1.35.92). The other four games follow after
  the owner approves.

## 1. How A New Home draws a villager

All addresses below are in the stock executable, `research/stock-executables/Virtual Villagers - A
New Home.exe`. This is the same build `docs/picture-studio-vv1.md` documents.

### The sheets

The atlases are built at 0x43C08E-0x43C2EB. A single sheet comes from the constructor 0x40A070, and
a grid of sheets from 0x40A0F0. Each sheet is kept in a gameobj slot.

| gameobj slot | Files | Cells | Built at (slot store) |
|---|---|---|---|
| +0x3DFF4 / +0x3DFF8 | `female_heads.png` / `male_heads.png` | 7 x 20, 40 x 65 each (column = facing, row = head value) | 0x43C0AB / 0x43C0E3 |
| +0x3DFE4 / +0x3DFE8 | `female_bodies` / `male_bodies` `00 10 01 11` | 2 x 2 files of 16 x 10, so 32 x 20 cells (column = frame + 8 x direction, row = body value) | 0x43C11E / 0x43C19D |
| +0x3DFEC / +0x3DFF0 | `female_actions` / `male_actions` `00 01` | 1 x 2 files, 9 x 20 cells (bent over, at work, sitting) | 0x43C15E / 0x43C1DD |

A child is drawn from the same sheets, scaled down: the body at `age/7 + 50` percent and the head at
`age/14 + 80` percent. The Golden Child uses the boys' sheets. The dead (`skelly.png`) have no skin
to recolour.

### Every place a villager is drawn

I scanned the bytes for every reference to the six slots. Leaving out the constructor stores and the
teardown at 0x4371xx (which frees the sheets), every read is a 6-byte `mov r32, [esi+disp32]` in one
of four routines. These are the same four routines, with the same register set-up, that Grey Hair at
55 already relies on (`native/vv1_grey_hair/vv1_grey_hair.c`).

| Routine | Caller | Heads | Bodies | Actions |
|---|---|---|---|---|
| 0x437340 Villager Details portrait | Details draw 0x449170 | 4 (Grey Hair's) | 0x4373B8, 0x437441, 0x4374C0, 0x437513 | - |
| 0x4375F0 a dialog's villager figure | 0x4188A6, 0x42AA96 | 3 (Grey Hair's) | 0x437679, 0x4376D5, 0x437723, 0x437744 | - |
| 0x437790 the village | frame 0x4240FE | 13 (Grey Hair's) | 0x437AED, 0x437E38, 0x437F3E, 0x438723, 0x438777 | 0x437A8E, 0x437B2D, 0x437C62, 0x437D08, 0x438210, 0x438286, 0x438327, 0x43837D, 0x43853F, 0x438593 |
| 0x4388E0 the map (a quarter size) | 0x42A5F2 | 9 (Grey Hair's) | 0x438B05, 0x438B7B, 0x439170, 0x4391EA | 0x438A07, 0x438AAE, 0x438CDC, 0x438D6A, 0x438E36, 0x438EA3, 0x439002, 0x439087 |

That is **29 head reads** (already spliced by Grey Hair), **17 body reads** and **18 action reads**:
64 in all. Every one of them reaches the engine through 0x409410 (to the scaled cell draw 0x408AF0)
or 0x4093C0 (to 0x408740). Grey Hair already splices both engine entries.

### The patcher's own pictures

These must follow the tone too:

- **Change Appearance** (`native/vv1_origins_icons/vv1_origins_icons.c`). The per-villager window
  (`appearance_draw_head`, `appearance_draw_from`) and Change Appearance for All (`forall_draw_one`)
  draw from the companion's 40 x 1300 preview strips `IDB_HEAD_M/F` and `IDB_BODY_M/F`, or from
  Grey Hair's grey strips.
- **Show Parents** (`native/vv1_parentage`). `Vv1ParentageDrawPortrait` draws the parents' small
  figures (`vv1_draw_parent`) and then redraws the child (`vv1_replay_body`, `vv1_replay_draw`).
- **Picture Studio and the Family Tree** in the patcher. These are `src/vv_pictures_vv1.py` (the
  village draw, which already reads Head Looks and the masks) and `src/vv_genealogy_window.py`
  `_head` (portraits).

## 2. The skin colours in the VV1 sheets

**The art is painted, not a palette.** Its anti-aliasing and soft shading give 27,457 distinct
opaque colours in `male_heads.png` alone. So "the skin colour set" cannot be a short list. It is a
measured rule, and its proof is a mask per sheet.

**Each row is painted in its own stock skin.** I measured each row's reference skin: the front-facing
cheeks for heads, and every cell of the row for bodies.

- Most rows are a pale peach, at hue 30-40 and saturation 0.42-0.57.
- A few rows are tanned:
  - female heads 0 and 2 are about (195, 141, 64), saturation 0.67;
  - male bodies 14-16 are about (215, 156, 65), saturation 0.70.
- Female bodies are all one colour, (227, 170, 102).

So a single colour box cannot fit every row. Light-brown and blond hair (male head 2 at hue 30,
saturation 0.71-0.76) have the same colour as a tanned face. The rule is therefore the same
everywhere except for one number per row, measured from that row.

### The rule

The rule is in the docstring of `scripts/vv1_skin_tone_preview.py`, which is the authority.

1. **CAP per row.** CAP = clamp(the median saturation of the row's reference skin + 0.15, 0.55,
   0.82).
2. **Seed.** A pixel is a seed when it is not fully transparent, has R >= G >= B, and falls in one of
   three HSV boxes:

   | Box | Hue | Saturation | Value | What it covers |
   |---|---|---|---|---|
   | core | 23.5-42 degrees | 0.20 to CAP | >= 0.45 | lit skin |
   | shadow | 18-23.5 degrees | 0.20-0.55 | >= 0.45 | shaded skin; brown fur is 21-23 at 0.60-0.85, so it stays out |
   | highlight | 42-60 degrees | 0.15-0.55 | >= 0.85 | the yellow-white sheen |

   Seeds are kept only in 8-connected blobs of 5 pixels or more. This drops isolated glints on hair
   and cloth.
3. **Attached.** The seed is grown by up to 2 steps into two kinds of pixel:
   - **near-white sheen:** R >= G >= B, R - B >= 12, saturation 0.04-0.45, value >= 0.85;
   - **soft pinkish shade:** value >= 0.45, saturation <= 0.30, hue <= 30 or >= 300, R - B >= 6.

   Pure whites and greys never qualify, so **eye whites, lips, outlines, masks and clothes keep their
   colours**.

### Measured counts

| Sheet | Opaque pixels | Skin pixels | Share | Distinct skin colours |
|---|---|---|---|---|
| male_heads | 49,374 | 12,379 | 25.1% | 9,027 |
| female_heads | 54,244 | 8,091 | 14.9% | 6,890 |
| male_bodies 00 / 01 / 10 / 11 | 118,188 / 121,936 / 107,655 / 111,497 | 33,925 / 40,810 / 29,538 / 36,143 | 27-34% | 18,774 / 17,405 / 16,378 / 15,859 |
| female_bodies 00 / 01 / 10 / 11 | 113,313 / 116,193 / 104,869 / 109,715 | 28,336 / 40,536 / 28,100 / 36,377 | 25-35% | 14,984 / 18,464 / 14,730 / 16,477 |
| male_actions 00 / 01 | 62,435 / 66,983 | 13,576 / 18,075 | 22-27% | 7,633 / 8,231 |
| female_actions 00 / 01 | 60,444 / 62,154 | 13,641 / 18,908 | 23-30% | 6,365 / 8,382 |

**All 14 sheets together: 107,690 distinct skin colours.**

The proof is one mask per sheet, `skintone\final\mask_<sheet>.png`: skin in magenta, everything
else grey. The head masks are at 2x.

### Ambiguous pixels

These pixels have exactly the colour of skin, so no colour rule can separate them. They are visible
in the masks:

| Sheet | Where | What happens |
|---|---|---|
| male_heads | row 0 (gold spiky hair) | some hair tips count as skin |
| male_heads | row 4 (grey hair) | a few warm-grey specks next to the forehead |
| female_heads | row 3 (blond bob) | a few fringe pixels |
| male_bodies | row 0 (off-white vest) | edge pixels |
| male_bodies | row 1 (red and white striped top) | the cream stripes: the largest case, the same colours as skin highlights |
| male_bodies | row 2 (grey hood) | the light edge at the neck |
| male_bodies | row 3 (fur vest) | the lighter centre |

The VV2 attempt hit the same wall. It was abandoned for the owner's hand masks
(`research/vv2-skin-source/README.md`). There are two ways to settle these rows. The owner chooses
(decision D5):

- **(a)** A small per-row exception table, made of rectangles in cell coordinates. It is only
  numbers, no art.
- **(b)** The owner touches up those rows in GIMP, as for VV2.

## 3. The tone model

### Presets

There are eight presets, from very light to very dark. Each is the sRGB colour the lit mid-skin
lands on:

| Tone 1 | Tone 2 | Tone 3 | Tone 4 | Tone 5 | Tone 6 | Tone 7 | Tone 8 |
|---|---|---|---|---|---|---|---|
| 243,216,194 | 231,193,160 | 214,166,124 | 190,139,96 | 162,112,74 | 131,87,58 | 100,65,44 | 70,46,33 |

### Fine control

The fine control has **15 steps**:

- preset *p* is step 2*p* - 1;
- each even step is the CIELAB midpoint of its two neighbours, shown as "Tone 4-5".

The stock skin is closest to step 5 (Tone 3). Fifteen keeps the memory bounded (see Risks). A finer
scale is possible if memory allows.

### The recolour

The recolour uses the "centre" method with K = 0.30. This is the owner's VV2 choice, which the VV2
README says not to change without asking. Each skin pixel becomes:

> **target + K x (pixel - mean skin of its row)**

So every head and body of one tone lands on the same colour, whatever stock skin its row was painted
in, and 30% of the art's own shading is kept. `preview_shading_ladder_2x.png` shows K = 0.30, 0.60
and 1.00 and the VV2 multiply/screen method side by side, so the owner can confirm K for VV1
(decision D3).

### Inheritance

**A baby's step is the mean of its parents' steps.** A half step rounds toward the mother. There is
no randomness.

- If a parent is shown with the stock skin (D2), that parent counts as step 5.
- If both parents are stock, the baby is stock.

The father's step is captured at conception, the same moment `vv1_parentage` captures the father, so
a father who dies or leaves before the birth still counts. Twins and triplets get the same step. The
Golden Child blends like any birth.

### Founders and arrivals

Founders and arrivals get **a random preset**: one of Tone 1 to 8, each equally likely. They get it
the first time the patch sees a living villager with no tone who was not just born.

- Any way a villager joins that is not a birth counts as an arrival, so no creation path needs its
  own hook.
- The random number comes from the DLL's own generator, never the game's `rand()`, so the game's own
  random sequence (births, events) is not disturbed.

The owner chooses between "a random preset" and "any of the 15 steps" (decision D1).
`preview_random_founders_2x.png` shows eight random founders.

### Villagers already in a save

These are villagers who are in a save when the patch is first installed. The owner chooses (D2):

- **Option A (recommended), random once.** It works in two passes:
  1. villagers with no recorded parents get a random preset;
  2. then, oldest first, villagers whose parents `vv1_parentage` knows get their parents' blend.
- **Option B, stock until chosen.** These villagers keep the stock skin until the player picks a
  tone.

## 4. Storage

**File:** `Virtual Villagers Fun Patcher\Save <S>\Data\Skin Tones\Skin Tones - Save <S>.dat`

It is routed by `native/shared/per_save_data.h` and written atomically through
`native/shared/sidecar_io.h`. It never touches a record byte. It gets a row in "THE PATCHER'S OWN
FILES" of `How to Use.txt`.

The format copies Head Looks' `VHL2` (`native/vvfp_head_look/head_look_store.inc`). It is
little-endian:

```
u32 magic 'VST1', u32 game (1), u32 count (256)
u32 roster[count]          living villager identity per record when written (0 = nobody)
u32 id[count]              the identity each entry was kept for
u8  tone[count]            0 none yet, 1..15 a step, 0x80 stock chosen
u8  original[count]        the tone at birth or first sight (Reset to original), same coding
u8  father_tone[count]     on a carrying mother's record: the father's tone captured at conception,
                           0xFF none; cleared at the birth
```

That is exactly 12 + count x 11 bytes.

**It follows the villager**, with Head Looks' rules (`native/shared/mask_follow.h`,
`foreign_sidecar.h`):

- the file belongs to the village it shares a strict roster majority with;
- each tone is re-keyed by name, sex and family (+0x36C) when the game packs its records after a
  death;
- an identity two villagers share is never guessed;
- another village's file is never written over.

Start Over deletes it (`native/shared/save_reset.c`). A missing file means every tone is "none yet".
A foreign or damaged file is moved aside intact.

## 5. Hooks

- **The data DLL: "VVFP Skin Tone.dll"**, one feature in one DLL, like "VVFP Head Look.dll". It
  keeps the file, assigns founder and arrival tones, takes the birth blend, and exports:
  - `VvfpSkinToneGet(game, record)` and `...Set` / `...SetMany`;
  - `VvfpSkinToneConceived(mother, father)` and `VvfpSkinToneBorn(child, mother)`.

  The Origins companion's `Vv1Born` already forwards the child and mother to `Vv1ParentageBorn`, and
  the conception handler calls `Vv1ParentageConceived`. The skin calls sit right beside those, so
  catch-up births are covered by the same path. This must be re-proven, because catch-up is the main
  birth path.
- **The draws.** Grey Hair's DLL already owns the 29 head reads and both engine entries. A second DLL
  cannot splice the same bytes. **Recommendation (decision D4):**
  - Grey Hair's draw code becomes A New Home's one villager-sheet hook. It gains the 35 body and
    action reads, with the same 6-byte splice and the same anchors.
  - It asks "VVFP Skin Tone.dll" for the tone exactly as it asks "VVFP Head Look.dll" for the look.
  - It is shipped when Grey Hair or Skin Tone is ticked. With Grey Hair unticked it draws nothing
    grey.
  - At the engine entry, the sheet a draw gets is first the young or grey sheet (as now), then that
    sheet's tinted copy for the villager's tone.
- **The tinted sheets.** These are built on first use per (tone, sheet). The game's own constructor
  0x40A070 / 0x40A0F0 loads a fresh copy of the player's own stock PNG, and its pixels are recoloured
  in memory with the rule above. Phase 2 must confirm that the sprite holds a lockable 32-bit SDL
  surface.
  - Nothing derived from the art is written to disk or shipped.
  - Grey Hair's grey sheets get the same treatment.
  - The Origins masks keep finding head draws by the young sheet, as they do now.
- **Change Appearance previews** recolour the preview strip's cell with the same rule. Show Parents
  asks for each parent's tone. Picture Studio and the Family Tree read the same file and use the same
  rule in Python.
- **One test pins the rule.** It runs the C and Python rules on synthetic pixels, not game art.

## 6. Change Appearance additions

**The per-villager window gets a "Skin tone" row:**

- a swatch;
- a list: Stock, Tone 1 ... Tone 8;
- ◄ ► buttons that walk the 15 fine steps;
- "Random", which picks a random preset.

The preview shows the tone live. "Undo changes" and "Reset to original" include the tone. Reset puts
back the tone at birth, or the tone from the first time the patch saw the villager.

**Change Appearance for All gets a "Skin tone" row** in the Male column and in the Female column:
Leave as is, Stock, Tone 1 ... Tone 8, Random.

**Cost:** a tone-only change costs the window's normal price, like a head-look-only change.

The wording is "Skin tone" in both windows. Every new string goes through `vvfp_tr`, and the
translations get their keys.

## 7. Logging

A tone change is an **"Appearance changed"** record (`native/shared/appearance_log.h`). It gets two
lines after the mask lines, so the four look lines `relook_last_name` reads stay first:

```
Appearance changed
  Name: Ann
  Old head: 3
  Old body: 4
  New head: 3
  New body: 4
  Old skin tone: Tone 3
  New skin tone: Tone 4-5
```

A tone-only change is logged with old head and body equal to the new ones. Records written before
carry no tone lines, and every reader takes them as they are.

The owner decides whether a baby's Birth record gets a "Skin tone:" line (decision D6). Founder
tones are not logged, because they are not changes.

## 8. The other four games

Each game needs its own measured rule, because numbers are never carried across games. The sheets
are 2 x 3 grids of 32 x 30 cells, plus old heads (`_old` in VV2 and VV3; `00` / `10` in VV4 and VV5).

| Game | Extra sheets | Existing work | Draws to hook |
|---|---|---|---|
| VV2 The Lost Children | - | the owner's hand masks, `research/vv2-skin-source/` | the Head Look sites (0x445694 Details, 0x445A77 strip figure, the village 0x445B50 and the map 0x4478E0) |
| VV3 The Secret City | - | - | the village 0x4605F0, the Details portrait 0x4568E0, the figure 0x456CA0 |
| VV4 The Tree of Life | `BigHeads00/10.png` (the Details big portraits) | - | the village 0x467DA0, the figure 0x45F550, the portrait 0x45F7C0 |
| VV5 New Believers | `BigHeads00/10.png`, `vv5_heathenheads*.png` | - | the village 0x4720E0, the figure 0x466C40, the portrait 0x466EF0 |

In VV2-VV5 heads are already inherited as the average of the parents, and the tone blend sits
beside that. All four keep parents' names in the record, so the father's tone can be read at
conception.

## 9. Risks

- **Memory.** A New Home is a 32-bit program without the large-address flag, so it has 2 GB.
  - One tone's full set of tinted sheets is about 20 MB decompressed. That is 2 heads at 1.46 MB,
    8 bodies at 1.66 MB and 4 actions at 0.94 MB.
  - A village that uses all 15 steps of both sexes could reach about 300 MB.
  - Phase 2 must measure this live. If it is too much, the fallback is to cache per row: one
    villager's head, body and action rows at about 0.5 MB per (sex, head, body, tone).
- **Ambiguous pixels** (section 2). Without D5, a few hair and cloth pixels change colour with the
  skin.
- **Grey Hair's final art** is still the owner's to draw. The rule must be re-checked on it when it
  arrives.
- **Shared hooks.** Folding the body and action reads into Grey Hair's DLL changes a shipped DLL.
  Every one of its existing proofs (`GreyHairIsThePatchersOwn`, the masks over grey heads) must keep
  passing.
- **Births.** A birth that misses the hook would get a random tone, because it would look like an
  arrival. Phase 2 must prove the hook on births in play, in catch-up and in Time Warp, on the Golden
  Child, and on twins.
- **Randomness.** Founder randomness must never use the game's RNG.

## Decisions for the owner

| # | Decision | Recommendation |
|---|---|---|
| D1 | Founders and arrivals: a random **preset** (8), or any of the **15 steps**? | presets |
| D2 | Villagers already in a save: **random once** (parents' blend where parents are known), or **stock until chosen**? | random once |
| D3 | Shading kept: K = 0.30 (as VV2), 0.60, 1.00, or multiply? See `preview_shading_ladder_2x.png`. | 0.30, unless the darker tones look too flat |
| D4 | Grey Hair's DLL becomes the one VV1 villager-sheet hook and asks "VVFP Skin Tone.dll" for the tone. | yes |
| D5 | Ambiguous rows (gold and blond hair tips, the cream-striped top, the fur vest): a numbers-only exception table, or the owner's GIMP touch-ups? | exception table |
| D6 | Show the baby's tone in its Birth record? | yes, one "Skin tone:" line |
| D7 | Are the 8 preset colours and the 15-step fine control right? See `preview_presets_2x.png` and `preview_fine_steps_2x.png`. | - |
