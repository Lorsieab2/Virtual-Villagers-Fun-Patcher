# Picture Studio: The Lost Children (Virtual Villagers 2)

The renderer is `src/vv_pictures_vv2.py`; its proofs are `tests/test_pictures_vv2.py`. Everything below
was read from the stock executable (SHA-256 `46C1503C...D677`) and is checked by running that code in
Unicorn; addresses are the stock game's.

## The engine's primitives

The Lost Children's sprite code is A New Home's instruction for instruction, at other addresses
(`PrimitivesAreANewHomes` compares the disassembly with only the addresses masked):

| What | A New Home | The Lost Children |
|---|---|---|
| one-sheet atlas constructor | 0x40A070 | 0x40A270 |
| atlas of sheets (`%s%d%d%s`) | 0x40A0F0 | 0x40A2F0 |
| cell cut (clamped) | 0x409F90 | 0x40A190 |
| place-scaled (centring) | 0x407ED0 | 0x408160 |
| software blitter | 0x403D70 | 0x404000 |
| cell draw | 0x4086C0 | 0x4088C0 |

So `vv_picture_image.Atlas`, `centre_offset`, `percent_scale`, `blit_piece` and `surface_alpha` hold here.
`BlitterMatchesTheGame` also runs 0x404000 itself on a test picture (Windows' 53-bit x87 precision) for
eleven scales below 1 and three cells, and requires every screen pixel to be the shared model's.

## The atlases (asset loader 0x44C232 .. 0x44C599)

| Game object slot | Sheet(s) | Grid |
|---|---|---|
| +0xE574A8 / +0xE574AC | female_heads.png / male_heads.png | 7 x 30 (40 x 65) |
| +0xE574B0 / +0xE574B4 | female_heads_old.png / male_heads_old.png | 7 x 30 |
| +0xE57498 / +0xE5749C | female_bodies / male_bodies 00..12 (2 x 3 sheets) | 32 x 30 |
| +0xE574A0 / +0xE574A4 | female_actions / male_actions 00..02 (1 x 3) | 9 x 30 |
| +0xE574CC | totems.png | 8 x 1 (40 x 100) |
| +0xE57494, +0xE574B8 | peep_shadow1.png, focus_circle.png | whole pictures |
| +0xE574BC | carrying.png | 13 x 2 |
| +0xE574C0 | collectables_images.png | 6 x 9 |
| +0xE574C4 | skelly.png | 4 x 1 |
| +0xE574C8 | ripple.png | 4 x 1 |

The tests build them with the game's own constructors (only the picture loader 0x40A730 is replaced by a
fake surface the size of the real sheet).

## The village compositor 0x445B50 (loop 0x445C1C .. 0x4478DE)

Record = game + index x 0xE48C. Fields read: +4/+8 place, +0x20 frame, +0x24 height in the air,
+0x30 in use, +0x31 selected, +0x32 held by the hand (cleared by the drop 0x42CE30), +0x38 direction,
+0x3C head column, +0x40 state (4: not drawn), +0x44 carried item (0x1A: none), +0x52C health,
+0x530 age, +0x538 sex, +0x544 litter, +0x548 head, +0x54C body, +0x550 variant, +0x558 statue.

* Shadow (0x445C75): selected, not held, alive and state not 4/8 -> shadow and focus circle at (x-13, y+19);
  otherwise, alive and state not 4/8: shadow at (x-13, y+19), or held -> shadow at alpha 0.5 at (x-13, y+39).
* Statue (+0x558, 0x445D88): shadow at (x-17, y+59), totems.png frame +0x550 mod 8 at (x, y).
* Body awaiting burial (health <= 0, 0x445E14): skelly.png frame +0x550 mod 4 at (x, y).
* Child (age < 0x118): body scale age/7 + 50 per cent, head age/14 + 80, centred by place-scaled:
  * state 1 (0x445EEF) bending: actions col = frame at (x, y+13); head col 3 at (x-2f-2, y+2f+10); item before;
  * state 2 (0x4460EF) sitting: actions col 8 at (x, y+10); head col +0x3C at (x, y+9); item after (directions 1, 2);
  * state 10 (0x446295) in the air: bodies col 7 (frame 3) or frame+4 at (x, y-h+13); head col 1 / 3 at (x, y-h+5);
  * any other state (0x4465E7): bodies col frame + 8 x direction at (x+5, y+13); head col +0x3C at (x+5, y+6);
    item before (directions 0, 3) or after (1, 2) at (x+5, y+36), collectables at item - 0x1E.
  Children always use the young heads.
* Adult: old heads (_old) from age 0x44C (1,100):
  * swimming (0x4468A6): not held, terrain 0x18 at (x+20, y+65), state not 9: ripple frame (clock & 3) at
    alpha 0.4 at (x-12, y+28), then only the head (col +0x3C) at (x, y+31);
  * states 0, 5, 9 (0x4473AD): bodies col frame + 8 x direction at (x, y+3), head col +0x3C at (x, y-9);
    state 9 with an odd +0x550 instead: actions col 8 at (x, y+3), head at (x, y-1); carried item and its
    litter copies before (directions 0, 3: y+16, x-5/y+10, y+5) or after (1, 2: y+25, x-5/y+18, y+13);
  * state 1 (0x446A7B): actions col frame at (x, y+3), head col 3 at (x-2f-2, y+2f-1);
  * state 2 (0x446C38): actions col 8, head col +0x3C at (x, y-1), items after;
  * state 3 (0x446E3C): actions col frame+4, head col 3 at (x, y-10);
  * states 8 / 10 (0x446F32 / 0x4470CC): actions / bodies col 7 (frame 3, head col 1) or frame+4 (head col 3)
    at (x, y-h+3), head at (x, y-h-10);
  * any other state draws nothing but the shadow.

The Studio's poses map onto these states: Walking (0), Bending (1), Sitting (2), Arms out (3), In the air
with action frames (8) or walking frames (10), Resting (9 with an odd variant), Swimming (0 in deep water).

## The patcher's art and changes

* **Origins heathen masks** (`vv2_enable_origins_exclusive_features`, built by
  `scripts/build_vv2_mask_stage2.py`): the adult head thunk 0x4095B0 and the child thunk 0x409600 are
  detoured into the `.vvmk` stubs. Adult: a draw from the village (callers 0x445B50..0x4478DF) whose row is
  the record's head and whose sheet is one of the four head atlases 0xE574A8..0xE574B4 (young and old, both
  sexes) draws the head then the mask atlas cell (row mask - 1, the head's column) unscaled at (x, y - 42).
  Child: a draw from one of those head atlases through the scaled thunk draws the mask at the same scale at
  (x, y - (scale x 54 >> 7)). The atlas
  (`heathen_masks.png`, 520 x 725, 8 x 5 cells of 65 x 145) is read from inside the shipped
  `assets/origins/VVFP VV2 Origins Icons.dll` (RCDATA 5000; byte-identical to
  `native/vv2_origins_icons/heathen_masks.png`). `MasksMatchThePatchedGame` builds the patched executable with
  the patcher itself and runs the compositor with every mask, stage and pose: the mask is drawn once, on the
  head, in every pose.
  Fixed in v1.35.86: the patch's sheet list used to hold `female_actions` (0xE574A0) as a fifth "head"
  sheet, so a woman whose body value equals her head value got a second mask over her action-pose body
  (bending, sitting, arms out, in the air, resting), and a girl got one over her bending or sitting body.
  `tests/test_vv2_mask_head_only.py` runs the patched compositor on those cases.
* **Head look** (`VVFP Head Look.dll`): every adult head's age check in the village follows it. The swimming
  head's compare `cmp ecx, 0x44C` (0x4469BA) is spliced; every other pose compares `cmp ecx, ebx` with EBX
  = 0x44C (set at 0x445C32), two bytes too short to splice, so the DLL splices the thirteen age loads before
  them (0x446B22 .. 0x44777A, `vvfp_head_look.c` VV2_SITES, `load` 1) and hands the compare the look's age.
  Before v1.35.86 only the swimming head followed the look. `tests/test_vv2_head_look_village.py` runs the
  compositor with the DLL loaded, in every pose, Auto / Young / Old, on the stock and the patched
  executable, and requires the Studio's plan. Children always have the young head (the compositor has no
  age check for a child's head).
* **Elder Totems** (`VVFP VV2 Totems.dll`, `native/vvfp_vv2_totems`): the patch keeps statues out of the
  villager records, in `Virtual Villagers Fun Patcher\Save <N>\Data\Elder Totems\ElderTotems.dat`, and
  draws each one with the game's own calls exactly as a statue record is drawn (`draw_one`: shadow at
  (x-17, y+59), totems.png frame Totem Type % 8). From my save lists those statues too, read from that file
  with the DLL's own checks (magic, version, game, entry size, length, FNV-1a hash); a damaged file is not
  read. A statue record's health is 0 (the totem maker 0x44D467), so the village draws only its own shadow.

## Not covered, or not proven

* The Villager Details portrait (0x445540) and the strip figure (0x445950): they draw at up to 2x, and the
  blitter's enlarging path is not the shared model's (measured at 150, 172 and 186 per cent), so they are
  not offered.
* The map overview (0x4478E0) and the cursor's own picture while a villager is held.
* Water-splash particles (0x4239D0) and the random drift of the swimming ripple: random each frame; the
  ripple frame is a picker.
* Where two sprites overlap on the transparent picture they are combined with ordinary alpha compositing;
  the game blends onto its opaque screen (divide by 256, and a fully faded pixel still darkens it by one
  level). On an opaque background the colours agree to within that rounding.
* The animation fields (state, frame, direction, head column, carried item) are not in the save: From my
  save draws the save's villager in the pose picked.

## Carried items

Every item a villager can be drawn carrying, as offered under **Carrying** on both tabs (`src/vv_pictures_carried.py`). "Unused in the game" items are drawn with the game's own carry code, which draws any number, but nothing the game runs carries them.

| Number | Name | Status | When the game carries it (or why it never does) |
|---|---|---|---|
| 0 (0x0) | Berries | unused in the game | no code stores 0 |
| 1 (0x1) | Rock | in the game | Exercising; Building small hut |
| 2 (0x2) | Feathers | unused in the game | no code stores 2 |
| 3 (0x3) | Baby | in the game | expecting (until the birth) |
| 4 (0x4) | Wood | in the game | Rebuilding broken hut; Building small hut; Fixing hut; Gathering firewood; Creating cutting tools; Building a scarecrow; Building a dam; Teaching children |
| 5 (0x5) | Laundry | in the game | Doing laundry; Teaching children |
| 6 (0x6) | Crops | in the game | Harvesting crops; Adding food to the stew; Teaching children |
| 7 (0x7) | Flowers | in the game | Honoring the Dead; Researching; Teaching children |
| 8 (0x8) | Fish | in the game | Fishing; Teaching children |
| 9 (0x9) | Crab | in the game | Fishing; Teaching children |
| 10 (0xA) | Water | in the game | Adding water to the stew; Watering crops |
| 11 (0xB) | Body | in the game | Burying the dead |
| 12 (0xC) | Algae-eating fish | in the game | Catching algae-eating fish! |
| 13 (0xD) | Brown mushroom (carrying.png) | unused in the game | no code stores 13: a carried mushroom is collectables picture 49 |
| 14 (0xE) | Red mushroom (carrying.png) | unused in the game | no code stores 14 |
| 15 (0xF) | Dry grass | in the game | Gathering dry grass |
| 16 (0x10) | Coconut | in the game | Harvesting coconuts |
| 17 (0x11) | Empty bowl | unused in the game | no code stores 17 |
| 18 (0x12) | Cutting tool | in the game | Fishing; Removing the vines; Cutting away briar thorns |
| 19 (0x13) | Cauldron | in the game | Retrieving a cauldron |
| 20 (0x14) | Pot of stew | unused in the game | no code stores 20 |
| 21 (0x15) | Herb | in the game | Adding an herb to the stew |
| 22 (0x16) | Stone blades | in the game | Creating cutting tools |
| 23 (0x17) | Gong piece | in the game | Retrieving something from the pond; Retrieving a piece of the gong |
| 24 (0x18) | Mortar | unused in the game | no code stores 24 |
| 25 (0x19) | Potion | unused in the game | no code stores 25 |
| 30 (0x1E) | Butterfly, common 1 | in the game | Collecting a new item! (children) |
| 31 (0x1F) | Butterfly, common 2 | in the game | Collecting a new item! (children) |
| 32 (0x20) | Butterfly, common 3 | in the game | Collecting a new item! (children) |
| 33 (0x21) | Butterfly, common 4 | in the game | Collecting a new item! (children) |
| 34 (0x22) | Butterfly, uncommon 1 | in the game | Collecting a new item! (children) |
| 35 (0x23) | Butterfly, uncommon 2 | in the game | Collecting a new item! (children) |
| 36 (0x24) | Butterfly, uncommon 3 | in the game | Collecting a new item! (children) |
| 37 (0x25) | Butterfly, uncommon 4 | in the game | Collecting a new item! (children) |
| 38 (0x26) | Butterfly, rare 1 | in the game | Collecting a new item! (children) |
| 39 (0x27) | Butterfly, rare 2 | in the game | Collecting a new item! (children) |
| 40 (0x28) | Butterfly, rare 3 | in the game | Collecting a new item! (children) |
| 41 (0x29) | Butterfly, rare 4 | in the game | Collecting a new item! (children) |
| 42 (0x2A) | Shell, common 1 | in the game | Collecting a new item! (children) |
| 43 (0x2B) | Shell, common 2 | in the game | Collecting a new item! (children) |
| 44 (0x2C) | Shell, common 3 | in the game | Collecting a new item! (children) |
| 45 (0x2D) | Shell, common 4 | in the game | Collecting a new item! (children) |
| 46 (0x2E) | Shell, uncommon 1 | in the game | Collecting a new item! (children) |
| 47 (0x2F) | Shell, uncommon 2 | in the game | Collecting a new item! (children) |
| 48 (0x30) | Shell, uncommon 3 | in the game | Collecting a new item! (children) |
| 49 (0x31) | Shell, uncommon 4 | in the game | Collecting a new item! (children) |
| 50 (0x32) | Shell, rare 1 | in the game | Collecting a new item! (children) |
| 51 (0x33) | Shell, rare 2 | in the game | Collecting a new item! (children) |
| 52 (0x34) | Shell, rare 3 | in the game | Collecting a new item! (children) |
| 53 (0x35) | Shell, rare 4 | in the game | Collecting a new item! (children) |
| 54 (0x36) | Beetle, common 1 | in the game | Collecting a new item! (children) |
| 55 (0x37) | Beetle, common 2 | in the game | Collecting a new item! (children) |
| 56 (0x38) | Beetle, common 3 | in the game | Collecting a new item! (children) |
| 57 (0x39) | Beetle, common 4 | in the game | Collecting a new item! (children) |
| 58 (0x3A) | Beetle, uncommon 1 | in the game | Collecting a new item! (children) |
| 59 (0x3B) | Beetle, uncommon 2 | in the game | Collecting a new item! (children) |
| 60 (0x3C) | Beetle, uncommon 3 | in the game | Collecting a new item! (children) |
| 61 (0x3D) | Beetle, uncommon 4 | in the game | Collecting a new item! (children) |
| 62 (0x3E) | Beetle, rare 1 | in the game | Collecting a new item! (children) |
| 63 (0x3F) | Beetle, rare 2 | in the game | Collecting a new item! (children) |
| 64 (0x40) | Beetle, rare 3 | in the game | Collecting a new item! (children) |
| 65 (0x41) | Beetle, rare 4 | in the game | Collecting a new item! (children) |
| 66 (0x42) | Pebble, common 1 | in the game | Collecting a new item! (children) |
| 67 (0x43) | Pebble, common 2 | in the game | Collecting a new item! (children) |
| 68 (0x44) | Pebble, common 3 | in the game | Collecting a new item! (children) |
| 69 (0x45) | Pebble, common 4 | in the game | Collecting a new item! (children) |
| 70 (0x46) | Pebble, uncommon 1 | in the game | Collecting a new item! (children) |
| 71 (0x47) | Pebble, uncommon 2 | in the game | Collecting a new item! (children) |
| 72 (0x48) | Pebble, uncommon 3 | in the game | Collecting a new item! (children) |
| 73 (0x49) | Pebble, uncommon 4 | in the game | Collecting a new item! (children) |
| 74 (0x4A) | Pebble, rare 1 | in the game | Collecting a new item! (children) |
| 75 (0x4B) | Pebble, rare 2 | in the game | Collecting a new item! (children) |
| 76 (0x4C) | Pebble, rare 3 | in the game | Collecting a new item! (children) |
| 77 (0x4D) | Pebble, rare 4 | in the game | Collecting a new item! (children) |
| 78 (0x4E) | Brown mushroom | in the game | Picking a mushroom (children) |
| 79 (0x4F) | Red mushroom | in the game | Picking a mushroom (children; 1 in 10) |
| 80 (0x50) | Golden Mushroom | patcher | Picking a mushroom (Super-Secret Golden Mushroom; the game's own picture) |
| 81 (0x51) | Collectables picture 52 | blank picture, unused | no code stores it |
| 82 (0x52) | Collectables picture 53 | blank picture, unused | no code stores it |
| 83 (0x53) | Collectables picture 54 | blank picture, unused | no code stores it |

The carry field is record +0x44 (0x1A = nothing). Every store, read from the stock exe:

- **Steps.** The villager tick 0x464CD0 runs each record's step queue (jump table 0x4653C0): opcode 0xF
  carries the step's number (`mov [rec+0x44], [rec+0x60]`, 0x464F1F), opcode 0x10 carries nothing
  (0x464F46). Steps are queued only by add_step 0x449B70; its 54 opcode-0xF calls all push a number, except
  teaching (0x44A5B3, 0x44A712: 4 + rand(6), so 4 to 9).
- **Direct stores**: the job reset 0x4492A0 (3 when +0x540 is set, else 0x1A, 0x4492E2), 0x4496E3, the
  coconut climb 0x4497FB (16), 0x44BA3C, 0x44CD87, 0x44D11F, 0x44D446, the hand's pick-up 0x44D6C8 (drops
  anything but the baby), the birth 0x43BF7A and 0x42506C.
- **Collectables**: a child sent to a collectable or a mushroom carries the ground item's kind + 0x1E
  ("Collecting a new item!" 0x45BFE4; "Picking a mushroom" 0x45BD49): 0x1E-0x4D the 48 collectables, 0x4E the
  brown mushroom, 0x4F the red one, and with the Super-Secret Golden Mushroom patch 0x50, the game's own
  golden mushroom picture (collectables cell 50). A walking child draws collectables_images.png cell
  item - 0x1E; a bending child item - 0x1A (so the mushroom picker, who bends while carrying, shows cells
  52-54, blank or clamped); an adult draws carrying.png at the item's own number -- all as the game does.
- **Unused**: 0, 2, 13, 14, 17, 20, 24 and 25 are on carrying.png but no step or store gives them.
  Numbers 0x1B-0x1D are never stored and are not offered.
- **The save** (the packer 0x44B580) keeps +0x524..+0x804, not +0x44: after loading (0x464450) the job
  reset gives the baby to a villager whose +0x540 (name - 0x24) is set. The litter +0x544 (name - 0x20) is
  saved: 2 twins (7% of conceptions), 3 triplets (a quarter of those), 0 for one baby.

**Proven** by tests/test_pictures_vv2.py `test_every_carried_item`: the game's own draw, run in
Unicorn on the stock executable, blits every item above in each of the four directions and in every pose
that draws the item (walking with twins and triplets, the work poses, a child) exactly as the plan says;
for the Golden Mushroom, the plan with the patcher's picture is the stock blits with the companion's swap
(tests/carried_golden.py, the offsets read from its source). The list itself is pinned by
tests/test_pictures_carried.py.
