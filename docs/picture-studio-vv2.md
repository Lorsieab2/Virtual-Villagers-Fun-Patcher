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
  the record's head and whose sheet is one of 0xE574A0 (female_actions), the four head sheets, draws the head
  then the mask atlas cell (row mask - 1, the head's column) unscaled at (x, y - 42). Child: any such draw
  through the scaled thunk draws the mask at the same scale at (x, y - (scale x 54 >> 7)). The atlas
  (`heathen_masks.png`, 520 x 725, 8 x 5 cells of 65 x 145) is read from inside the shipped
  `assets/origins/VVFP VV2 Origins Icons.dll` (RCDATA 5000; byte-identical to
  `native/vv2_origins_icons/heathen_masks.png`). `MasksMatchThePatchedGame` builds the patched executable with
  the patcher itself and runs the compositor with every mask, stage and pose.
  Faithfully reproduced patch behaviour: because the patch's sheet list holds `female_actions` (0xE574A0),
  a woman whose body value equals her head value gets a second mask over her action-pose body (bending,
  sitting, arms out, in the air, resting), and a girl gets one over her bending or sitting body.
* **Head look** (`VVFP Head Look.dll`): of the village compositor's age compares only the swimming head's
  (0x4469BA) is spliced (`vvfp_head_look.c` VV2_SITES; the DLL is run on it by `tests/test_head_look.py`).
  Every other village head uses the age, so the Studio applies the look to swimming only.
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
