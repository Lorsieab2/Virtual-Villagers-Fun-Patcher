# Skip All on the intro story -- A New Home and The Lost Children

The owner asked for The Secret City's stone "Skip All" button on the intro story of A New Home (VV1) and
The Lost Children (VV2): the pages shown after the tribe is named. Clicking it ends the story at once and
asks the game's own help question; Yes and No must do exactly what they do at the normal end of the story.

Everything below was read from the stock executables (`inputs/vv<N>-stock-copy/`). Addresses are VAs.

## 1. The Secret City (reference only, nothing changes there)

The story overlay is a singleton (`0x6C5D88`, built by `0x4643D0`, fetched by `0x464610`). Its constructor
makes three buttons with the game's button art (`0x42E8A0(0x10, ...)`):

| id | where (left, top) | label (sm text id) |
|----|-------------------|--------------------|
| 0  | (640, 540)        | `0x89` eSaySkipIntro "Skip All" |
| 1  | (228, 550)        | `0x87` (Yes) |
| 2  | (428, 550)        | `0x88` eSayNo "No" |

Its button handler `0x464700` (message 8, through `0x464820`): button 0 -- Skip All -- asks the modal
two-button box `0x41C6B0`/`0x401AF0` with text `0x24C` (eIntroPage5Line3, "Do you need help?") when the
tutorial has not yet been decided (`[0x4B37B8] == 0`), then takes the same Yes/No branch the story's last
page (page 5, `0x412FF0`, whose third line is the same `0x24C`) takes. So in The Secret City the help
question is the last page's own question, and Skip All jumps straight to it.

## 2. A New Home and The Lost Children: the stock story

Both games use the same older engine. A page is a screen object; the screen manager (VV1 `0x41B370`,
second copy `0x41B9C6`; VV2 `0x423D70`, second copy `0x424440`) switches on the game state
(VV1 `[game+0xACB4]`, VV2 `[game+0x30470]`), builds every story page the first time the first page's
state is reached, activates the page of the current state (`activate(1)`: VV1 `0x40AE10`, VV2
`0x40B7F0`) and calls its update.

| | A New Home | The Lost Children |
|---|---|---|
| page 1 | state `0x15`, class vtable `0x4597F4`, built by `0x41E600` (`intro1_bg.png`) | state `0x16`, vtable `0x476AC4`, `0x427E20` (`intro1_bg.jpg`) |
| page 2 | state `0x16`, vtable `0x45982C`, `0x41ED00` (`intro2_bg.png`) -- **the last page** | state `0x17`, vtable `0x476AFC`, `0x428470` (`intro2_bg.jpg`) |
| page 3 | -- | state `0x18`, vtable `0x476B34`, `0x428CB0` (`intro3_bg.jpg`) -- **the last page** |
| who enters page 1 | `0x426FF3` (state `0x15`) | `0x432B7F` (state `0x16`) |

**A story page (not the last).** Its event slot (vtable slot 1: VV1 `0x41E5D0`; VV2 `0x427DF0`,
`0x428430`) takes event 2 -- a mouse press anywhere ("Click anywhere to continue.") -- and marks the page
done (VV1/VV2 page 1: `[page+0x78] = clock + 1; [page+0x28] = 1`; VV2 page 2: `[+0x1D4]`, `[+0x1A0]`).
Its update (slot 8: VV1 `0x41EA20`; VV2 `0x428240`, `0x428910`) fades the page in, and once it is done
fades it out over 50 frames (25 in fast mode), deactivates it and sets the next state (VV1 `0x41EB0E`:
`0x16`; VV2 `0x42832E`: `0x17`, `0x428A39`: `0x18`). Its button slot (slot 3) is the do-nothing stub
(VV1 `0x41F640`, VV2 `0x401190`: `xor al, al; ret 8`): these pages have no buttons.

**The last page -- the help question.** Its text ends with the question (VV1 table id `0xFD` "Would you
like HELP the first time?", VV2 `0x17D` "Would you like tutorial tips turned on?") and it has two buttons
built with the game's own button art (VV1 `main_wide_button2.png` at (228, 560) and (428, 560); VV2
`popup_button1.png` at (228, 550) and (428, 550)), ids 1 (Yes) and 2 (No). The update (VV1 `0x41F310`,
VV2 `0x4292C0`) counts frames in `[+0x25C]` (VV1) / `[+0x19C]` (VV2) and, when the count reaches 50
(25 fast) and the page is not fading out, adds both buttons (`0x40AB80` / `0x40B560`). The button slot
(VV1 `0x41EC40`, VV2 `0x428B30`), message 8:

* **Yes** (VV1): `[game+0x9E1C] = clock`, sound `0x44`. (VV2): the tutorial-tip flags `[game+0x31+i]`
  cleared for all 0x1E3 and set from 0x186, the help flags `+0x1F4..+0x1F7, +0x1FA, +0x1FB` set,
  `[game+0x2E4F8] = clock`, sound `0x4A`.
* **No** (VV1): the tip flags `[game+0x31+0x105..0x137]` cleared, `[game+0x151] = 1`, `[game+0x9E1C] =
  clock`, sound `0x43`. (VV2): as Yes, then tips `0x186..0x1BE` cleared, `[game+0x1D8] = 1`, sound `0x49`.
* Both remove the two buttons and set the fade-out flag (`[+0x260]` / `[+0x1A0]`); the update then fades
  out, deactivates the page and sets state 1 -- the village.

So the question VV1 and VV2 ask at the end of the story is the last page's own question and buttons, as in
The Secret City. **Skip All reuses that exact code path: it ends the story and takes the player to the last
page with its Yes/No already shown; the answer runs the stock button slot above, untouched.**

## 3. The approach: one companion, vtable slots only

"VVFP Skip Intro.dll" (`native/vvfp_skip_intro`), one feature, on by default, A New Home and The Lost
Children. It patches no executable byte. At start (`VvfpStartup`, called by VVFP Startup.dll from its second
word of companions) it checks every vtable slot below holds its stock pointer and writes them all through
`native/shared/install_sites.h` (all or none). Any other build of the game: nothing is installed.

| game | slot replaced | stock | becomes |
|---|---|---|---|
| VV1 | page 1 slot 0 (dtor) `0x4597F4` | `0x41EA00` | our button freed, then stock |
| VV1 | page 1 slot 3 (buttons) `0x459800` | `0x41F640` | Skip All handler, else stock |
| VV1 | page 1 slot 9 (activate) `0x459818` | `0x41E5C0` | stock, then our button attached / detached |
| VV1 | page 2 slot 8 (update) `0x45984C` | `0x41F310` | "skipped here": buttons at once, then stock |
| VV2 | page 1 slots 0 / 3 / 8 / 9 `0x476AC4 / 0x476AD0 / 0x476AE4 / 0x476AE8` | `0x428220 / 0x401190 / 0x428240 / 0x427DB0` | as VV1 page 1; slot 8: stock, then "skipped: go to page 3" |
| VV2 | page 2 slots 0 / 3 / 9 `0x476AFC / 0x476B08 / 0x476B20` | `0x4288F0 / 0x401190 / 0x43A2B0` | as page 1 |
| VV2 | page 3 slot 8 (update) `0x476B54` | `0x4292C0` | "skipped here": buttons at once, then stock |

**The button.** When a non-last page is activated, the companion builds (once per page object) a button
exactly as the last page builds its Yes button -- the game's allocator (VV1 `0x44AF03`, VV2 `0x467F83`),
the game's button constructor (VV1 `0x4019B0`, VV2 `0x4019D0`) with the game's own art name pointer (VV1
`0x459340` `main_wide_button2.png`, VV2 `0x476378` `popup_button1.png`), the game's label call (VV1
`0x4015B0`, VV2 `0x4015D0`) with the Yes button's own colours -- at (640, 560) in A New Home and (640, 550)
in The Lost Children (The Secret City's Skip All column, on the row of the game's own Yes/No), id
`0x5C1A`, and adds it to the page (`0x40AB80` / `0x40B560`). The label is "Skip All", asked of VVFP
Translations.dll by key (`native/shared/vvfp_translate.h`), so it is translatable. No art or font ships:
the game draws its own button image with its own font. When the page is deactivated the button is taken off
(`0x40ABC0` / `0x40B5A0`); when the page object is destroyed the button is freed by its own destructor first.

**Click.** The button reports message 8 with its id to the page's slot 3, as every game button does. For
`0x5C1A` the companion sets "skip pending" and calls the page's own event slot with event 2 -- the stock
"page done" code a click anywhere runs -- so the page fades out exactly as it always does. Any other message
goes to the stock slot.

**Landing on the question.** VV2 page 1's update is followed: when it has just set state `0x17` while skip
is pending, the state becomes `0x18` (page 3, built with page 1). When the last page's update runs its first
frame while skip is pending, the companion first puts the stock frame count at its end (`[+0x25C]` /
`[+0x19C]` = 1000), so the stock update adds the Yes/No buttons and clears the fade on that same frame; skip
pending is then cleared. It is also cleared whenever page 1 is activated (a new story). Nothing else of the
last page changes: its text and its question are the game's, and Yes/No are its own buttons and handler.

**Without a click on Skip All** every replaced slot calls the stock one with the same arguments and adds only
the button on the non-last pages: the story pages, their timing, the question and the answer are stock.

## 4. Risks and how they are handled

* **A different build of the game** -- every slot is checked for its stock pointer before anything is written;
  one mismatch installs nothing.
* **Click-through** -- if the press on Skip All also reaches the page's own "click anywhere" event, the page
  is marked done twice by the same stock code (idempotent); skip pending is set on the release, during the
  page's 50-frame fade-out, so the skip still lands. Holding the button longer than the fade-out leaves the
  story stock (the release never reaches the button): a missed skip, never a broken one.
* **Freeing the button** -- only through the game's own remove-child and the button's own scalar deleting
  destructor, before the page's own destructor; the page never frees it (its destructor frees only its own
  fields), so it is freed once.
* **Fault** -- every companion entry runs under structured exception handling and falls back to the stock
  slot; a fault while building the button leaves the page without a button.
* **The F1 shortcut** (jumps to the village with no question) and the typed-character page turn are stock.
* **Saves** -- nothing is written to a save, villager record or file; only the game's own help flags, by the
  game's own Yes/No code.
* **Live game not yet seen** -- the emulation below runs the game's own code with the companion installed;
  the button's look, its exact position next to the page's text, and the translated label are still to be
  seen in a running game.

## 5. What the emulation tests prove (tests/test_skip_intro.py)

For both games, on a published build started as the game starts (tests/startup_emulation.py):

1. the companion installs exactly the vtable slots above, after checking their stock values, and nothing in
   a stock build of another game;
2. activating a story page builds the button through the game's own constructor: its rectangle is the
   game's art at (640, 560/550), its label is "Skip All", it is in the page's child list (what the page's
   draw walks) and the game's own hit test (the button's event slot, VV1 `0x401760`) takes a press and
   release inside it and reports message 8 with its id; a press outside it does not;
3. that click marks the page done through the stock code; the stock update then fades out and moves on
   (VV2: straight to page 3);
4. the last page's first update adds its Yes/No buttons at once (the help question is up);
5. Yes and No through the stock button slot write exactly the flags a normal end of the story writes
   (compared with the same run on the stock executable);
6. with no Skip All click the story runs exactly as stock: page 1 done by a click anywhere, the last page's
   buttons after 50 frames, the same flags.
