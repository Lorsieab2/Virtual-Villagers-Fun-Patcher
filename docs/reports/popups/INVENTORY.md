# Popup inventory for "VVFP Scrolling Popups.dll" (v1.35.97 research)

The owner wants vertical and horizontal scrollbars on every popup in all five games ("any popup!!!").
This report lists every class that draws a text body in a framed panel or popup, per game, with the
hook points a single companion needs.

Method: static disassembly of the stock executables in `research/stock-executables` only. No game was
run. The Tree of Life (VV4) and New Believers (VV5) carry MSVC RTTI, which names 189 and 205 classes
and maps every vtable to its class. A New Home (VV1), The Lost Children (VV2) and The Secret City (VV3)
have no RTTI. Their classes were matched by structure: same base constructor, vtable layout and sizer
calls, and the strings each class uses.

Every address is the stock executable's.
- **C** = CONFIRMED: seen in the disassembly at the quoted address.
- **I** = INFERRED.

The text-routine addresses agree with `native/vvfp_unicode_text/text_routines.h`, whose addresses
`tests/test_unicode_utf8.py` checks against the stock bytes.

## 1. One engine, five builds

All five games use LDW's `ldw` framework. VV4/VV5 RTTI gives the class tree. VV1–VV3 share the same
layout (C):

- **Scenes and dialogs:** `ldwScene` < `ldwDialog` < `ldwTiledDialog` < concrete dialogs.
  - In VV4/VV5 the concrete dialogs are `CIslandEventDialog`, `theMessageBoxDlg`, `theTipDialog`,
    `theTombStoneDialog`, `theOptionsDialog`, `theChangePlayerDlg`, `theCreateNickNameDlg` and
    `theFernsaceDialog`.
  - `theFernsaceDialog` is the clothes/outfit chooser. It matches VV2/VV3's outfit dialog: width
    `+0x5C`, height 300 (I by structure).
- **Full-screen scenes:** `ldwScene` subclasses.
- **Controls:**
  - `ldwButton`.
  - `ldwTextControl`: a label or edit box whose text is a heap copy at impl+0x30.
  - `ldwHintControl`.
  - `ldwImageGrid`.

**Dialog vtable** (the same slots in all five games, C):

| Slot | Role |
|---|---|
| +0x00 | dtor |
| +0x0C | input / message handler. msg 8 = button click, id in the next argument |
| +0x18 | frame draw. Draws the tiled background, then tail-jumps to `[vt+0x30]` |
| +0x30 | DrawContent: the body |

The frame draw tail-jumps to DrawContent only once the open animation (+0x44) has reached 1.0.

**Constructor shape** (C, every dialog):
1. Base tiled-dialog constructor, called with `push 1`.
2. Vtable written to `[esi]`.
3. Buttons and text controls created.
4. **Sizer** `(tileImage, w, h)`: builds the w×h tiled background and centres the panel. The panel
   rect is at +0x14..+0x20.
5. Children added with AddControl.

**How dialogs run:** every popup is a stack object shown by a DoModal loop that calls vt+0x10 (input),
vt+0x14 (render) and presents, until vt+0x28 says it is done. The loop never runs the village.

**The body is never clipped.**
- VV1, VV3, VV4, VV5: the frame draw clips the tiles only when byte +0x34 is set.
- VV2: it clips the tiles, then clears the clip before the tail-jump.
- Native clip: set writes ctx+0x60..0x6C; clear resets to the full screen.

**Child text controls** (labels, message-box bodies) draw after DrawContent, through the control draw
routine ("ctldraw" below). They have no clip either.

**Mouse:** one dispatcher per game, called from one pump site. Wheel events are ignored today.

### Shared anchors per game

| | VV1 A New Home | VV2 The Lost Children | VV3 The Secret City | VV4 The Tree of Life | VV5 New Believers |
|---|---|---|---|---|---|
| Base tiled-dialog ctor (`push 1`) | 0x40C9E0 (11 callers) C | 0x40D470 (12) C | 0x40E100 (12) C | 0x40DD00 (10) C | 0x40E1F0 (10) C |
| Sizer (tile, w, h) | 0x40C760 C | 0x40D140 C | 0x40DDD0 C | 0x40DE20 (8 callers) C | 0x40E310 (8) C |
| Frame draw vt+0x18 / tail-jump to vt+0x30 | 0x40C8F0 / 0x40C9AD C | 0x40D2D0 / 0x40D38D C | 0x40DF60 / 0x40E01D C | 0x40DFD0 / 0x40E088 C | 0x40E4C0 / 0x40E578 C |
| DoModal | 0x401AB0 C | 0x401AD0 C | 0x401AF0 C | 0x401D40 (16 callers) C | 0x401CF0 (16; byte-identical to VV4's) C |
| Render-context getter | (ctx via `[ecx]`) | 0x408320 C | 0x408940 C | 0x408130 C | 0x4080C0 C |
| Clip set / clear (ctx+0x60..0x6C) | 0x408320 / 0x408350 | 0x4085B0 / 0x4085E0 | 0x408BF0 / 0x408C20 | 0x408450 / 0x408480 C | 0x408420 / 0x408450 C |
| Mouse dispatcher @ pump site | 0x401FE0 @ 0x403C6E | 0x402070 @ 0x403EFE | 0x4020A0 @ 0x40451E | 0x402320 @ 0x404B02 | 0x4022D0 @ 0x404A92 |
| String lookup | 0x433970(id) C | 0x441680(id) C | 0x42F190(id) C | 0x44D3D0(id) C | 0x4506D0 / 0x450D40 (I) |

### Text primitives (C; same as `text_routines.h`)

| Routine | VV1 | VV2 | VV3 | VV4 | VV5 |
|---|---|---|---|---|---|
| **Core draw** (ctx; s, x, y, colour, font) ret 0x14. `'\n'` resets x and adds a line height. Every string ends here | 0x409160 | 0x409360 | 0x409CD0 | 0x409700 | 0x409930 |
| Draw wrapper (`mov ecx,[ecx]; jmp core`) | 0x4094B0 | 0x4096A0 | 0x40A060 | 0x409BD0 | 0x409EA0 |
| Centred block (s, cx, y, colour, font) | 0x4094C0 | 0x4096B0 | 0x40A070 | 0x409BE0 | 0x409EB0 |
| Centred between edges (s, l, r, y, colour, font) | 0x409510 | 0x409700 | – | – | – |
| Width (font; s, scale): widest `'\n'` line | 0x402160 | 0x4021F0 | 0x402230 | 0x402430 | 0x4023E0 |
| Height (font; s or 0): lineH × (1 + `'\n'` count) | 0x402100 | 0x402190 | 0x4021C0 | 0x402500 | 0x4024B0 |
| Line fit / word wrap (font; src, out, max, width, *para, nlAsSpace, scale) → next | **none** | 0x4022B0 | 0x4022F0 | 0x402550 | 0x402500 |
| Wrapped height (s, width, scale) | – | 0x402440 | 0x402480 | 0x4026E0 | (I, tip ctor) |
| **Justify** (holder; s, x, y, width, colour, font, measureOnly) ret 0x1C → height. Word-wraps; at most 100 lines | **none** | **none** | 0x40A0C0 | 0x409C30 | 0x409F00 |
| ctldraw: text-control draw. An editable box first cuts its text byte by byte while it is wider than its box (+0x24) | 0x40BFE0 | 0x40C9C0 | 0x40D650 | 0x40CE20 | 0x40D310 |
| Text-control outer ctors (label / edit) | 0x40C2C0 / 0x40C380 | 0x40CCA0 / 0x40CD60 | 0x40D930 / 0x40D9F0 | 0x40D8A0 (98 callers) / 0x40D970 | 0x40DD90 (102) / 0x40DE60 |

**Text-control behaviour** (C in all five):
- A static label auto-sizes to its widest line and its height (it is multi-line through `'\n'`) and
  never truncates.
- An editable box (+0x24) has a byte limit at +0x28 (default 0x4B0, capped at 1200). It is a single
  line, and its draw cuts the buffer while the text is wider than the box.

**Wrapping:**
- VV1 has no runtime word wrap at all. All 185 multi-line strings are pre-broken with `'\n'` in the
  string table built into the exe (0x487208, 0x275 records).
- VV2 wraps only in the tip dialog. All other long texts are pre-broken with `'\n'`.

## 2. Per-game class inventory

Column meanings:
- "Overflow today": can the body leave its panel or the screen with stock code and stock or
  translated text?
- "Hook set": the smallest set for that class.
  - **S** = its sizer call site: cap w/h to the screen and remember the content size.
  - **D** = its body draw call(s): clip to the inner rect and offset x/y by the scroll position.
  - **In** = its input handler: wheel, drag, scrollbar clicks, and resetting the scroll when the text
    changes.

### VV1, A New Home

| Class (purpose) | Ctor / vtable | Input +0x0C / Draw +0x30 | Sizer site → size | Text | Body draw call sites | Buttons | Overflow today | Hook set |
|---|---|---|---|---|---|---|---|---|
| Island event, plain (storms, finds; Custom Island Events from Story Upgrades) | 0x4286B0 / 0x459AE4 C | 0x4279C0 / 0x427910 C | 0x428830: w 0x1D0 (464) fixed; h = height(text) + 2.5 × button + 0x23 C | inline +0x277F (~0x270F), built by 0x428470; pronouns substituted by vt+0x2C 0x427680 C | 0x42796D (title, cut at the first `'\n'`), 0x4279A9 (rest), both centred 0x4094C0 at y = +0x6C + 0x23 C | OK id 4 | Grows with the text and has no screen cap. Lines are pre-broken, but substituted names widen them | S 0x428830, D 0x42796D / 0x4279A9, In 0x4279C0 |
| Encounter / two-choice event (Trapped Whale …; Story two-choice custom events) | 0x41A460 / 0x459578 C | 0x41A3D0 / 0x4187E0 C | 0x41A634: w = +0x60 (0x1C2); h = height(question) + 4 × button + 0x23 C | question +0x74, result +0x2783, labels +0x4E92 / +0x4F92; +0x50 = showing the result | 0x41884C, 0x418885 (0x4094C0) C | ids 2/3 then OK 4 (0x41A42C) | **Yes.** The result (0x419380) replaces the question in a panel sized for the question, with no re-size C. Story Upgrades pads questions to the tallest result for this reason | S, D, In 0x41A3D0 (re-measure after the choice) |
| Mysterious Crate / visitor | 0x42D0E0 / 0x459BF8 C | 0x42D050 / 0x42A9D0 C | 0x42D2B4: w = +0x60; h as above C | same layout; result from 0x42B740 | 0x42AA3C, 0x42AA75 (0x4094C0) C | 2/3 then 4 | **Yes**, same mechanism | S, D, In 0x42D050 |
| Message box / confirm (delete player, restart, puzzle "Completed in", tech level) | 0x427530 (id), 0x4275B0 (char\*) → init 0x427120 / 0x459AB0 C | 0x4270C0 / 0x4270F0 (`ret`) C | 0x427378: w = max(text + 0x3C, buttons), h = text + button + 0x3C C | child label 0x40C2C0 at 0x4271F3 (heap copy, no cap) | ctldraw 0x40BFE0 → 0x4094B0 at 0x40C197 C | OK 1, Cancel 2 | Fits the panel; no screen cap in either direction | S 0x427378, D = ctldraw while the parent vtable is 0x459AB0, In 0x4270C0 |
| Tip / tutorial (ids 0x106–0x120) | 0x435EB0 / 0x481AD0 C | 0x435E90 / 0x4362C0 C | 0x436006: w = width + 0x48, h = height + 2 × button + 0x24 C | string id +0x4C (looked up at draw time) | 0x436300 (0x4094B0) C | OK 2 | Measured; no screen cap | S 0x436006, D 0x436300 |
| Tombstone / grave readout | 0x436C50 / 0x481B58 C | 0x436400 / 0x436440 C | 0x436D24: **0x140 × 0x140 fixed** C | stack 0xCC "Here Lies "+name, job, age | 0x4364D6, 0x4364FC, 0x43669A, 0x4366FB (0x4094C0, single lines) C. Cause of Death draws its cause line from the hook at 0x436700 | OK 2 | **Horizontally**, for long names, translations and long-name support (I) | D (the 4 sites plus the COD lines), In 0x436400 |
| Options | 0x429700 / 0x459B18 C | 0x4289C0 / 0x4289F0 C | 0x429892: 0x280 × 0x1C0 fixed | labels only | title 0x428A23 plus about 18 labels C | OK, radios, sliders | Only long translated labels | optional |
| Change player | 0x4135E0 / 0x4592F0 C | 0x413CB0 / 0x413460 | 0x41369F: 0x1C7 × 0x190 fixed | 5 edit boxes, max 0x20 | ctldraw | OK, Delete, slots | No body (edit boxes truncate) | none |
| Create nickname | 0x415510 / 0x459388 C | 0x415440 / `ret` | 0x415599: 0x168 × 0xC8 fixed | prompt label plus edit box, max 0x20 | ctldraw | OK 1, Cancel 2 | Prompt only by translation | optional |
| Statistics (VV1 only) | 0x431B30 / 0x45A120 C | 0x431810 / `ret` | 0x431BD0: 0x1EA × 0x15E fixed | about 54 labels | ctldraw | OK, Refresh | Only by translation | optional |
| **Status notice box** (no base ctor) | global 0x415B40 / 0x415A90, init 0x4158F0 C | – / 0x415A00 | green tiled 320×64 | string id +0x1C | 0x415A74 (0x409510), centred for ONE line | – | A `'\n'` string spills below the box (I) | D 0x415A74 |

Scenes (C):
- Intro 1/2 and the game-won pages draw one label per pre-split line.
- Help pages are images.
- Villager Detail, Tech, Puzzles, Overview, the HUD and the title screen are single-line labels.
- Tech results and puzzle completions go to the message box (0x434773, 0x42DA06).
- VV1 hover hints exist as a class (0x409870) but no code ever sets their text (I: dead).

### VV2, The Lost Children

| Class | Ctor / vtable | Input / Draw | Sizer site → size | Text | Body draw | Buttons | Overflow today | Hook set |
|---|---|---|---|---|---|---|---|---|
| Island event, plain | 0x4348E0 / 0x476DF8 C | 0x4332B0 / 0x433200 C | 0x434A6B: w = +0x60 (0x1D0), h = height(+0x277F) + 2.5 × button + 0x23 C | +0x277F (~0x270F); name `*` and pronoun `^` substituted (0x41F0F0) | 0x43325D (title), 0x433299 (rest), both 0x4096B0 C | OK 4 | No screen cap; names widen lines | S, D, In |
| Two-choice encounter (family A; Story two-choice) | 0x422380 / 0x476714 C | 0x4222F0 / 0x41F430 C | 0x42255F: w 0x1C2, h = height(question +0x7C) + 4 × button + 0x23 C | question +0x7C, outcome +0x278B, labels +0x4E9A / +0x4F9A | 0x41F49C, 0x41F4D5 (0x4096B0) C | 2/3 then 4 | **Yes.** The outcome is drawn in the question-sized panel (0x42231A), up to 16 lines | S, D, In 0x4222F0 |
| Sacks and vials two-choice (family B) | 0x439DD0 / 0x476F30 C | 0x439D40 / 0x4374A0 C | 0x439FA4: w 0x1C2, h = height(+0x74) + 4 × button + 0x23 C | +0x74 / +0x2783 / +0x4E92 / +0x4F92 | 0x43750C, 0x437545 (0x4096B0) C | 2/3 then 4 | **Yes**, the same | S, D, In 0x439D40 |
| Outfit chooser | 0x4229D0 / 0x476794 C | 0x422960 / 0x4228F0 | 0x422B54: 0x190 × 0x12C fixed | title line | 0x42292B | arrows, OK | Title width only | optional |
| Message box (delete player, clothes cost, restart, puzzle description, tech info) | 0x4330A0 (id), 0x433120 (char\*) → init 0x432C90 / 0x476DC4 C | 0x432C40 / `ret` C | 0x432EE8: measured, w = max(label + 0x3C, buttons), h = label + button + 0x3C C | label 0x40CCA0 at 0x432D63, no cap | ctldraw 0x40C9C0 → 0x4096A0 at 0x40CB77 C | OK 1, Cancel 2 | No screen cap | S, D = ctldraw for this parent, In |
| Tip / tutorial / intro story | 0x443B90 / 0x48FAC8 C | 0x443B60 / 0x444110 C | 0x443D86: normal w = width + 0x48, h = height + 2 × button + 0x24. Story ids 0x187–0x1B7: w 0x262, h = WrappedHeight(570) C | string id +0x54 | normal 0x4442DE. Story: a line loop 0x444210–0x44429F, line fit 0x444231, draw 0x44428B C | OK 2 | No screen cap | S, D (the loop), In |
| Tombstone / grave | 0x444D80 / 0x48FB48 C | 0x444420 / 0x444490 C | 0x444E5B: 0x140 × 0x140 fixed C | epitaph = editable label (0x444FCB), rect (0x20, 0x46, 0x11C, 0x5A), max 0x40 (0x44504D) | 0x444527 name, 0x44454F job, 0x444727 skill, 0x44478B age, 0x4447B8 / 0x4447DA decorations (0x4096B0) C. COD hook at 0x444790 | OK 1 | Name and job lines spill **horizontally**; the epitaph truncates | D (sites plus COD lines and epitaph ctldraw), In |
| Options | 0x435B60 / 0x476E2C C | 0x434C00 / 0x434D60 | 0x435D2B: 0x280 × 0x1FC fixed | labels | about 20 labels | | Translation only | optional |
| Change tribe / player | 0x414650 / 0x476328 C | 0x414D20 / 0x4144D0 | 0x41470F: 0x1C7 × 0x190 | 5 edit boxes | ctldraw | | No | none |
| Create nickname | 0x41AC90 / 0x47647C C | 0x41ABC0 / `ret` | 0x41AD14: 0x168 × 0xC8 | prompt plus edit box | ctldraw | | Prompt by translation | optional |
| Statistics | 0x43F860 / 0x477640 C | 0x43F540 / `ret` | 0x43F900: 0x1EA × 0x15E | about 40 labels | ctldraw | | Translation only | optional |
| Timed banner (no base ctor) | 0x41B070, made by 0x41B210 C | – | 320×64 via 0x40D050 | one string id | 0x41B1F4 (0x409700) | – | Single line | D |

Scenes (I, from the string ids):
- The HUD, villager detail (0x4663B0 / 0x4654B0), tech, collections, puzzles and overview are
  single-line labels.
- The story pages (0x427E20, 0x428470, 0x428CB0, 0x426EB0) draw one label per line.
- No hover-hint class was found.

### VV3, The Secret City

| Class | Ctor / vtable | Input / Draw | Sizer site → size | Text | Body draw | Buttons | Overflow today | Hook set |
|---|---|---|---|---|---|---|---|---|
| Island event (CIslandEventDialog; plain, two-choice, Custom, Time Skip and other notices) | 0x4192F0 / 0x47F28C C | 0x419A00 / 0x418510 C | 0x41983F: w 0x200; h = +0x854 + max of 3 justify measures (0x419611 / 0x419648 / 0x419681, or 0x4197F7) + 2.5 × button C | +0x58 char[0x7D0] (cap 2000, 0x4197A8); title char\* +0x54 | title 0x418561 (centred), **body justify 0x418591** at (+0x850 = 0x28, +0x854), width +0x858 = 0x1B0 C | OK 1 (+0x864), choices 2/3 (+0x85C / +0x860) | Measured with no screen cap. Stock fits (about 9 lines); translations and 600-byte Custom Island Events can reach the screen edge (I) | S 0x41983F, D 0x418591 (+ 0x418561), In 0x419A00 |
| Tip / notice (tutorial; puzzle solved / not done) | 0x41E520 (id), 0x41E5E0 (char\*), init 0x41DE90 / 0x47F454 C | 0x41DE40 / 0x41E290 C | 0x41DFF1: w = width + 0x48 (tutorial 0x262); h = WrappedHeight + 2 × button + 0x24 C | char\* +0x58 (caller's string) | per line: line fit 0x41E3AD, then 0x41E40C (single line) or justify 0x41E433 C | OK 1 | No screen cap | S, D (both sites), In |
| Message box / confirm (tech info 0x464C30, restart, delete, clothes, faction 0x46578C; **Both Factions' confirm text**) | 0x41C6B0 / 0x41C720 / 0x41C7A0 → init 0x41C3A0 / 0x47F3AC C | 0x41C350 / `ret` | 0x41C53F: measured, no maximum C | label created at 0x41C40D, no wrap at all | ctldraw 0x40D650 → 0x40A060 at 0x40D807 C | OK/Yes 1, Cancel/No 2 | **Most at risk**: no wrapping and no cap (tech info has 13+ lines) | S 0x41C53F, D ctldraw for this parent, In 0x41C350 |
| Tombstone (grave) | 0x41E6D0 / 0x47F498 C | 0x41E690 / `ret` | 0x41E774: 0x1E0 × 0x140 fixed C | labels: name, job, age, cause, epitaph +0x60 | ctldraw | Done 1 | Labels spill **sideways** with long names; the epitaph is a label | D = ctldraw for this parent |
| Roster of the Dead (mausoleum list) | 0x41A110 / 0x47F2C0 C | 0x41A9F0 / 0x419CE0 | 0x41A19C: 0x2D2 × 0x1A2 fixed | 10 rows × 5 labels, paged | ctldraw | Done, prev/next | Long names sideways | D (labels) |
| Options | 0x41D2C0 / 0x47F3E0 C | 0x41C830 / 0x41C990 | 0x41D3A0: 0x280 × 0x1FC | labels | about 21 draws | | Translation only | optional |
| Change player | 0x41AE60 / 0x47F2F4 C | 0x41B480 / 0x41ACC0 | 0x41AEF8: 0x1C7 × 0x190 | 5 slots | ctldraw | | No | none |
| Create nickname | 0x41BA90 / 0x47F344 C | 0x41B9C0 / `ret` | 0x41BAF3: 0x168 × 0xC8 | prompt plus edit box | ctldraw | | Prompt by translation | optional |
| Outfit chooser | 0x41C010 / 0x47F378 C | 0x41BFA0 / 0x41BE70 | 0x41C14D: +0x5C × 0x12C | title 0x41BEAB | | | No | none |

Scenes (C/I):
- The story pages (0x4143A0) draw one string id per line, centred.
- Villager detail (0x46CB50), tech, puzzles, collections, help, loading tip, HUD, menu and overview
  are single-line labels.
- There is no hover-hint class.
- Developer editors (0x42B4D0 …) are not reachable by the player.

### VV4, The Tree of Life (RTTI names, C)

| Class | Ctor / vtable | Input / Draw | Sizer site → size | Text | Body draw | Opened from | Overflow today | Hook set |
|---|---|---|---|---|---|---|---|---|
| CIslandEventDialog (plain, two-choice, Custom, notices) | 0x417790 / 0x48D2C8 C | 0x417EA0 / 0x416EC0 C | 0x417CEF: w 0x200, h = edi = measured C (justify ×3 at 0x417AC7 / 0x417B00 / 0x417B3B, or once at 0x417CA4) | +0x58 char[0x7D0] (0x417C54); title char\* +0x54 | title 0x416F1C (0x409BE0), **body justify 0x416F4C** at (+0x850 = 0x28, +0x854), width +0x858 = 0x1B0, colour +0x82C C | presenters 0x418000 / 0x418190 (own modal loop 0x401D40) | Measured with no screen cap (I as above) | S 0x417CEF, D 0x416F4C (+ 0x416F1C), In 0x417EA0 |
| theMessageBoxDlg | 0x419DE0 (id), 0x419E80 / 0x419F00 (char\*) → init 0x419A30 / 0x48D3C4 C | 0x419DB0 / 0x432380 (`ret`) C | 0x419BE0: w = max(label + 0x3C, buttons), h = label + button + 0x3C C | label 0x40D8A0 at 0x419AA7 (x 400, y 300, centred) | ctldraw 0x40CE20 | story / adoption 0x41FF4B, change player, main scene, tech 0x43E989, puzzles 0x445E98 / 0x4461D2 C | No wrap and no cap | S 0x419BE0, D ctldraw for this parent, In 0x419DB0 |
| theTipDialog | 0x41BAB0, init 0x41B340 / 0x48D47C C | 0x41B7E0 / 0x41B810 C | 0x41B4B9: w = measured width (stack), h = edi (WrappedHeight 0x4026E0 at 0x41B3C4) C | char\* +0x58 | line loop: line fit 0x41B92E, single line 0x41B989 (0x409BD0) or justify 0x41B9B0 C. Text appears progressively over time (+0x94 ticks) | tutorial queue 0x44C127 C | No screen cap | S, D (both sites), In |
| theTombStoneDialog (grave) | 0x41BBA0 / 0x48D4EC C | 0x41C2C0 / `ret` | 0x41BC53: **0x1E0 × 0x140 fixed** C | about 8 labels (0x40D8A0 at 0x41BDB3 … 0x41C1E9); the epitaph is the last one, made editable at 0x41C20D | ctldraw | CMausoleumScene 0x43D4FE C | Sideways with long names; the epitaph truncates | D = ctldraw for this parent |
| theOptionsDialog | 0x419FA0 / 0x48D42C C | 0x41A440 / 0x41A5A0 | 0x41A09A: 0x280 × 0x1FC | labels (7 centred) | | main scene | Translation only | optional |
| theChangePlayerDlg | 0x418540 / 0x48D300 C | 0x418B80 / 0x4183C0 | 0x4185E7: w 0x1C7 × h (pushed earlier; VV5 0x190) | edit boxes | ctldraw | menu 0x4444E2 | No | none |
| theCreateNickNameDlg | 0x4190B0 / 0x48D354 C | 0x4193F0 / `ret` | 0x41911E: 0x168 × 0xC8 | prompt plus edit box | ctldraw | 0x444696 | Prompt by translation | optional |
| theFernsaceDialog (outfit chooser) | 0x419710 / 0x48D38C C | 0x4196A0 / 0x419630 | 0x419854: +0x5C × 0x12C | title 0x419667 | | main scene 0x43F8E9 | No | none |

Scenes (C, RTTI):
- CMausoleumScene (vt+0x18 → 0x43CDF0) draws three centred lines (0x43CE9F / 0x43CECA / 0x43CEF2).
- CStoryScene's IPage pages (intro, mid-game, end) draw pre-split centred lines (0x44AD32).
- CAdoptionScene draws one centred line (0x43B80A).
- theVillagerScene, CTechScene, CCollectionScene, CAchievementsScene and theOverviewScene draw labels
  and numbers (0x409A00 is a scaled single-line draw).
- ldwHintControl hover hints exist (single line, I).

### VV5, New Believers (RTTI names, C)

| Class | Ctor / vtable | Input / Draw | Sizer site → size | Text | Body draw | Overflow today | Hook set |
|---|---|---|---|---|---|---|---|
| CIslandEventDialog (plain, two-choice, Custom, Time Skip / Faith notices) | 0x418020 / 0x4984D8 C | 0x418720 / 0x417660 C | 0x418573: **w 0x2C0 (704)**, h = edi measured (justify at 0x41834E / 0x418387 / 0x4183C2 / 0x41852B) C | +0x58 char[0x7D0] (0x4184DB); title +0x54 | title 0x4176B9 (0x409EB0), **body justify 0x4176E9** at (+0x850 = 0x28, +0x854), width +0x858 = **0x270 (624)** C | Measured with no screen cap (I) | S 0x418573, D 0x4176E9 (+ 0x4176B9), In 0x418720 |
| theMessageBoxDlg | 0x41A640 / 0x41A6E0 / 0x41A760 → init 0x41A2D0 / 0x4985D4 C | 0x41A610 / `ret` | 0x41A47B: measured (label + 0x3C) C | label | ctldraw 0x40D310 | No wrap and no cap | S, D ctldraw for this parent, In |
| theTipDialog | 0x41C300 / 0x49868C C | 0x41C030 / 0x41C060 C | 0x41BD13: w = width + 0x48; tutorial mode **w 0x414**, h − 0x1A C | char\* | single line 0x41C1D9 (0x409EA0) or justify 0x41C200 per wrapped line C | No screen cap | S, D, In |
| theTombStoneDialog | 0x41C3F0 / 0x4986E8 C | 0x41CB20 / `ret` | 0x41C4A1: **0x1E0 × 0x140 fixed** C | 8 labels (0x40DD90) | ctldraw | Sideways; the epitaph truncates | D = ctldraw for this parent |
| theOptionsDialog | 0x41A800 / 0x49863C C | 0x41AC90 / 0x41ADF0 | 0x41A8EC: 0x280 × … | labels | | Translation only | optional |
| theChangePlayerDlg | 0x418C70 / 0x498510 C | 0x4192A0 / 0x418AF0 | 0x418D14: 0x1C7 × 0x190 | edit boxes | ctldraw | No | none |
| theCreateNickNameDlg | 0x4197D0 / 0x498564 C | 0x419B40 / `ret` | 0x41983C: 0x168 × 0xC8 | prompt plus edit box | ctldraw | Prompt by translation | optional |
| theFernsaceDialog (outfit) | 0x419EC0 / 0x49859C C | 0x419DF0 / 0x419D80 | 0x41A02F: +0x5C × 0x12C | title 0x419DB7 | | No | none |

**Who opens VV5 dialogs** (C):
- Message boxes: story / adoption 0x425A2F / 0x425B29, change player 0x41930E, main scene 0x4424A4,
  menu 0x447770, tech 0x441329 / 0x4414AD, puzzles 0x4490E0 / 0x449458.
- Tip: 0x44EDFA.
- Tombstone: CMausoleumScene 0x43FDD9.

**Scenes:** the same set as VV4 (mausoleum three lines 0x43F76F / 0x43F79A / 0x43F7C2, story pages
0x44DB22, adoption 0x43E1EE).

## 3. Popups the patcher's companions create or fill

| Source | What appears | Where it is drawn | Covered by |
|---|---|---|---|
| Story / Cheat Upgrades: Custom Island Events, Pick Island Event (`story_custom.inc`, `story_c1..5.inc`) | title (`CE_TITLE_BYTES` 48), description (`CE_TEXT_BYTES` 600), labels (`CE_BUTTON_BYTES` 40) | delivered INTO the stock island dialogs: VV1 encounter 0x41A460, VV2 family A 0x422380, VV3/4/5 0x4192F0 / 0x417790 / 0x418020 | the island-dialog hooks. 600 bytes in VV3/VV4's 432-px body is about 13 lines |
| Time Skip closing popup (`story_time_skip.inc`, `time_skip_notice_arm` → `story_notice_arm` → `ce_arm_with`) | plain notice | the same island dialogs | the island-dialog hooks |
| Popup When Believers Become Heathens (`vvfp_faith_notice`, `story_faith_notice.inc`) | count plus reason lines, VV5 only | VV5 island dialog 0x418020 | the island-dialog hooks |
| Both Factions (`vvfp_vv3_both_factions.c:833`) | translated confirm text replacing string 0x418 | VV3 stock message box 0x41C7A0 (call 0x46578C) | the VV3 message-box hooks |
| Cause of Death (`cod_vv12.inc`, `cod_vv345.inc`, `cod_epitaph_edit.inc`) | extra cause line; epitaph edits | VV1 tombstone draw epilogue hook 0x436700, VV2 0x444790 (draws with 0x4094C0 / 0x4096B0); VV3–5 tombstone ctors 0x41E6D0 / 0x41BBA0 / 0x41C3F0 | tombstone hooks. The scroll offset must also apply to COD's own draws (I) |
| Parentage (VV1, `vv1_parentage.c`) | "Son of …" hover text | lower message bar via 0x4094C0 | single line; none needed |
| Translations (`vvfp_translations`) | every string-table text in another language | everywhere | the main reason fixed panels (tombstone, options, nickname) can overflow |
| Unicode Text / long names (`vvfp_unicode_text`) | UTF-8 text, long names | it **detours the entry points** of width, core draw, line fit, justify and ctldraw in all five games | see the coexistence rule below |
| Win32 dialogs (Story, Origins icons, Full Mastery, Time Skip boxes; `shared/vvfp_dialog_kit.h`) | Windows windows, not in-game popups | already resizable; lists wrap | out of scope for the in-game DLL. Native WS_VSCROLL / WS_HSCROLL could be added in the kit (I) |
| Island events log, game log | files only | – | none |

## 4. Special handling

1. **Two-choice result swaps.** These re-text the panel without a re-size:
   - VV1 0x41A3D0 / 0x42D050.
   - VV2 0x4222F0 / 0x439D40.
   - VV3–5 input handlers. These pre-measure all three texts, so they are safe today.

   The scroll DLL must re-measure the content and reset the offset on that input.
2. **Message boxes draw their body through a child text control**, not DrawContent. Hook ctldraw
   only while the control's parent is a message box or tombstone, or hook the control's position once
   at the sizer.
3. **Tips draw line by line** with line fit plus justify (VV2–VV5). The offset applies to each line;
   clipping hides the lines outside the panel. VV4's tip also reveals its text over time.
4. **Fixed-size panels** (tombstone, options, change player, nickname, statistics, outfit) never grow.
   Their risk is horizontal (long names, translations). Editable boxes cut their own buffer when too
   wide: a horizontal scroll there needs a change to the cutting loop (`text_routines.h` "ctldraw"),
   which Unicode Text already detours.
5. **VV1's status notice box and VV2's timed banner** are not dialogs (no base ctor). Each draws one
   centred string in a 320×64 panel.
6. **Coexistence.**
   - Unicode Text already detours the core draw, width, line fit, justify and ctldraw ENTRY points in
     all five games.
   - Cause of Death hooks VV1 0x436700 / VV2 0x444790.
   - Island Events and Story Upgrades hook the island dialogs' ctors and input handlers.

   The scroll companion should therefore hook **call sites** (the per-class sizer and body-draw
   `call`s, the frame draw's `jmp [vt+0x30]`), not routine entries. It should also expose a "current
   scroll offset and clip" that Unicode Text and Cause of Death can read, or the reverse. Which
   companion owns the offset is an owner decision.
7. **Screen size.** VV5's island panel is 704 wide and its tutorial tip 0x414 (1044) wide (C). The
   cap for each game's sizer must use that game's real screen size (I: VV1–VV4 800×600; VV5 larger).

## 5. Per-game summary

| Game | Dialog classes (base ctor callers) | Bodies that can overflow today | Body draw choke points | Minimum hook set |
|---|---|---|---|---|
| VV1 | 10 classes (11 ctors) + status notice box | encounter and crate results (in-panel, C); island, message box, tip (past the screen); tombstone (sideways) | 0x4094C0 sites, ctldraw 0x40BFE0, 0x415A74 | sizer 0x40C760 sites; DrawContent 0x427910 / 0x4187E0 / 0x42A9D0 / 0x4362C0 / 0x436440; ctldraw for message box; frame jmp 0x40C9AD; inputs 0x41A3D0 / 0x42D050; wheel at 0x403C6E |
| VV2 | 11 classes (12 ctors) + timed banner | family A and B outcomes (in-panel, C); island, message box, tip (past the screen); tombstone (sideways) | 0x4096B0 / 0x4096A0 sites, tip loop, ctldraw 0x40C9C0 | sizer 0x40D140 sites; frame jmp 0x40D38D; DrawContent 0x433200 / 0x41F430 / 0x4374A0 / 0x444110 / 0x444490; ctldraw for message box; inputs 0x4222F0 / 0x439D40; wheel at 0x403EFE |
| VV3 | 9 classes (12 ctors) | message box (most at risk: no wrap); island and tip past the screen; tombstone and roster sideways | justify 0x418591, tip 0x41E40C / 0x41E433, ctldraw 0x40D650 | sizer sites 0x41983F / 0x41DFF1 / 0x41C53F; frame jmp 0x40E01D; ctldraw for message box and tombstone; input 0x419A00 / 0x41DE40 / 0x41C350; wheel at 0x40451E |
| VV4 | 8 classes (10 ctors) | message box; island and tip past the screen; tombstone sideways | justify 0x416F4C, tip 0x41B989 / 0x41B9B0, ctldraw 0x40CE20 | sizer sites 0x417CEF / 0x41B4B9 / 0x419BE0; frame jmp 0x40E088; ctldraw for message box and tombstone; input 0x417EA0 / 0x41B7E0 / 0x419DB0; wheel at 0x404B02 |
| VV5 | 8 classes (10 ctors) | message box; island (704-px panel) and tip (1044-px tutorial) past the screen; tombstone sideways | justify 0x4176E9, tip 0x41C1D9 / 0x41C200, ctldraw 0x40D310 | sizer sites 0x418573 / 0x41BD13 / 0x41A47B; frame jmp 0x40E578; ctldraw for message box and tombstone; input 0x418720 / 0x41C030 / 0x41A610; wheel at 0x404A92 |

## 6. Recommended build order

1. **Shared core, one game first (VV3 or VV4).**
   - A wheel and scrollbar input hook at the pump's dispatcher call site.
   - A frame-draw `jmp [vt+0x30]` call-site hook that knows the open panel (`this`, rect +0x14..+0x20)
     and sets the native clip (ctx+0x60..0x6C) to the inner rect.
   - Drawn scrollbars in the game's own tile art.
   - A per-panel state (content w/h, offset), keyed by the dialog pointer and reset in its dtor
     (vt+0x00).
2. **The island-event dialog in VV3/VV4/VV5.** One design (justify body, +0x58 cap 2000), and the
   biggest carrier of patcher text (Custom Island Events, Time Skip, Faith notices): sizer cap +
   justify call-site offset + input.
3. **Message boxes in all five games.** The child-label body, measured with no cap. These are the
   highest real risk (VV3 tech info, translated confirmations, Both Factions).
4. **Tips in all five games.** Line loops in VV2–VV5, a single draw in VV1.
5. **VV1/VV2 island dialogs and the two-choice result swaps.** The only in-panel overflow in stock
   code, plus re-measuring on the choice click.
6. **Tombstones and the other fixed panels** (horizontal scroll for long names and translations).
   This needs coordination with Cause of Death's extra lines and Unicode Text's ctldraw detour.
7. **Leftovers.** VV1 status notice box, VV2 timed banner, options / nickname / statistics labels (by
   translation only), mausoleum and story-page scenes (pre-split lines, low risk).

Each step is a new call-site set per game, verified against stock bytes with
`native/shared/install_sites.h` (all or none), as the other companions do.
