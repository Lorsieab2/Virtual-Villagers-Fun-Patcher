# Picture Studio: Text

Picture Studio's **Text** tab (Tools tab, "Picture Studio...", all five games) draws any text in the game's
own fonts and saves it as a transparent PNG.

- `src/vv_pictures_text.py`: the fonts, the game's layout, and the renderer.
- `src/vv_pictures_text_tab.py`: the tab. `src/vv_picture_studio.py` adds it with `add_text_tab`.
- `src/vv_glyph_maker.py`: makes the characters a font lacks.
- `data/vv_font_tables.json`: the glyph tables (numbers only). `scripts/build_vv_font_tables.py` writes it.
- `tests/test_pictures_text.py` and `tests/test_glyph_maker.py`: the tests.

## The tab

- **Font.** The game's two fonts are always offered:
  - **Arial Bold (game font)**
  - **Burweed (game font)**

  When Burweed ICG is installed on the computer (for example in `%LOCALAPPDATA%\Microsoft\Windows\Fonts`),
  **Burweed ICG (installed)** is offered too, at any pixel size. The TrueType font is the player's own and is
  never shipped.
- **Colour.** Every colour the game draws text in (see "The colours" below), or a custom colour. **Opacity**
  is the colour's alpha byte; the game fades text with it.
- **Align:**
  - **Left** is the game's text draw.
  - **Centred** is the game's centred draw: the block is centred, and every line starts where the widest line
    starts.
  - **Centre each line** and **Right** are the Studio's own.
- **Outlined title.** The Tree of Life's and New Believers' title effect. Two dark teal copies of the text are
  drawn first, at (-1, -1) and (+2, +2), then the text itself.
- **The text box.** Several lines, any Unicode.
  - **Insert character...** opens a picker. It searches by name ("e acute", "smiling face", "hiragana letter
    ka") or by code point ("U+00E9", "e9", "0x1F600"). It also has the common accented letters and
    punctuation, and the combining accents, which go on the letter before the cursor.
  - The line under the box says how many bytes the text takes as a villager's name: its UTF-8 length, since
    the games keep names as UTF-8 and read invalid UTF-8 as Windows-1252. It compares that with each game's
    name field (A New Home 27, The Lost Children 23, the later three 24) and says which games it is too long
    for.
- **The preview.**
  - It is drawn at the game's size, or blown up 2x to 4x when it is small, on a background you pick.
  - **Outline the letters that are not the game's own** marks each made glyph in the preview only, never in
    the PNG: patcher-made in blue, generated in orange, emoji in purple.
  - The line under the preview counts the glyphs by source.
  - **As the unpatched game draws it** shows the text exactly as the stock game would draw those bytes: the
    text in Windows-1252, with every character the game cannot hold drawn as "?", and every byte the sheet has
    no cell for drawn as the font's first glyph.
- **Save PNG...** uses Picture Studio's own size choices (the game's size, 2x, 4x or a custom width and
  height) and its "small clear margin", and saves through the same path as every other picture.

## The fonts

Each game builds exactly two bitmap fonts. This was checked in every executable:
- the font loader has exactly two call sites, the two font wrapper constructors;
- nothing else reads a glyph table;
- the only font strings are "ldwarialbold", "ldwBurweed27" and "Font Image not found: %s";
- no Images file is a digit or number strip.

| Game | Font | Sheet (stock size) | Table | Glyphs | Line height | Letter spacing | Cell 0 (drawn for a byte with no cell) |
|---|---|---|---|---|---|---|---|
| A New Home | Arial Bold | ldwarialbold.png 728 x 40 | 0x486888 | 73 | 20 | 1 | A |
| A New Home | Burweed | ldwBurweed27.png 793 x 54 | 0x4862A0 | 73 | 27 | 0 | A |
| The Lost Children | Arial Bold | ldwarialbold.png 728 x 40 | 0x4958A8 | 73 | 20 | 1 | A |
| The Lost Children | Burweed | ldwBurweed27.png 793 x 54 | 0x4952C0 | 73 | 27 | 0 | A |
| The Secret City | Arial Bold | ldwarialbold.png 1940 x 20 | 0x4A6A80 | 190 | 20 | 0 | ! |
| The Secret City | Burweed | ldwBurweed27.png 2364 x 27 | 0x4A5B78 | 190 | 27 | 0 | ! |
| The Tree of Life | Arial Bold | ldwarialbold.png 1940 x 20 | 0x4BA140 | 190 | 20 | 0 | ! |
| The Tree of Life | Burweed | ldwBurweed27.png 2364 x 27 | 0x4BB068 | 190 | 27 | 0 | ! |
| New Believers | Arial Bold | ldwarialbold.png 1940 x 20 | 0x4C7FE0 | 190 | 20 | 0 | ! |
| New Believers | Burweed | ldwBurweed27.png 2384 x 27 | 0x4C8F08 | 190 | 27 | 0 | ! |

What each font can draw:
- **A New Home and The Lost Children:** space ``! " ' , - . / 0-9 : ? A-Z ` a-z`` only. Every other byte draws
  "A", including `# $ % & ( ) * + ; < = > @ [ \ ] ^ _ { } | ~` and every accented letter.
- **The later three:** 0x20-0x7E and 0xA1-0xFF (The Secret City also has 0x7F and lacks 0xA1), so they
  include the Windows-1252 accented letters. 0x80-0xA0 draw "!".
- New Believers' Burweed has a redrawn, wider "q", which is why its sheet is 20 pixels wider.

All the sheets are white. Their antialiased edges use 15 to 33 alpha levels, and none has an outline.

**Where the sheets come from.** They are read from the player's own game folder and copied once into
`Picture Studio Pictures\Fonts\<game>`, apart from the villagers' pictures, with the same manifest checks.
The glyph tables are compiled into the executables. They are kept, numbers only, in
`data/vv_font_tables.json`, which `scripts/build_vv_font_tables.py` reads from the stock executables. It also
checks each constructor's `push spacing; push table; push "name"` byte for byte.

## The game's text code

Every game runs the same code; only the addresses differ.

| Routine | A New Home | The Lost Children | The Secret City | The Tree of Life | New Believers |
|---|---|---|---|---|---|
| Font wrappers (Arial Bold / Burweed) | 0x412790 / 0x4126F0 | 0x413160 / 0x4130F0 | 0x424540 / 0x4244B0 | 0x41D820 / 0x41D890 | 0x41E840 / 0x41E8B0 |
| Loader | 0x402240 | 0x4024D0 | 0x402510 | 0x4027A0 | 0x402730 |
| get_glyph | 0x402430 | 0x4026C0 | 0x402700 | 0x402B50 | 0x402AE0 |
| Width | 0x402160 | 0x4021F0 | 0x402230 | 0x402430 | 0x4023E0 |
| Recolour | 0x402510 | 0x4027A0 | 0x4027E0 | 0x4029C0 | 0x402950 |
| Text draw (renderer) | 0x409160 | 0x409360 | 0x409CD0 | 0x409700 | 0x409930 |
| Centred draw | 0x4094C0 | 0x4096B0 | 0x40A070 | 0x409BE0 | 0x409EB0 |
| Box-centred draw | 0x409510 | 0x409700 | -- | -- | -- |
| Faded blit | 0x403D70 | 0x404000 | 0x404620 | 0x404CB0 | 0x404C40 |

**The loader.**
- The table is 20-byte entries {code, left, top, right, bottom}, ending at code 0.
- The line height is the first entry's height.
- It walks the entries with a running x and y shift. An entry whose right edge passes the sheet's width
  wraps to the next row: x goes back to 0 and y goes down by the line height + 1. No stock table wraps.
- Codes 0x80-0xFF are stored as negative numbers and masked to a byte.
- Each byte is indexed to the first entry with that code. A byte with none gets entry 0.

**The draw.**
- The text is bytes.
- "\n" goes back to the start x and down one line height.
- Any other byte's cell is blitted at the pen, and the pen moves by the cell's width plus the letter spacing.
  A zero-width cell is neither drawn nor advanced (no stock cell has width 0).
- The colour is 0xAABBGGRR, and alpha 0 means the default, opaque white.
- The recolour ANDs every pixel of the sheet with the colour and keeps the alpha. White leaves the sheet as
  it is.
- An alpha below 255 fades the blit through the faded blitter. In A New Home to The Secret City it is
  alpha x (float)1/255; in the later two it is (float)(alpha / 255.0). Both give the same surface-alpha byte.

**The width.** For each line, the sum of each cell's width plus the spacing; take the widest line, less one
spacing.

**Centred.** The text starts at cx - trunc(width / 2), and every line starts at the same x.

**Box-centred.** x1 + trunc((x2 - x1 - width) / 2).

**Not offered as alignments.** The later games' justified-paragraph draw and line breaker (The Secret City
0x40A0C0, The Tree of Life 0x409C30, New Believers 0x409F00) are not offered. They hang on a word wider
than the box, and drop letters from one.

## The colours

These come from every call of every text draw, and the button and label colour setters, in each executable.
Most direct draws pass a colour constant that is 0, so they draw in the default white.

| Colour | 0xAABBGGRR | Games | Where |
|---|---|---|---|
| White | FFFFFFFF | all | the default; most text, labels, some buttons |
| Black | FF000000 | all | button labels |
| Dark grey | FF555555 | all | a button label pointed at or pressed |
| Dark brown | FF002245 | all | labels |
| Dark olive | FF003333 | 2-5 | some buttons |
| Charcoal | FF222222 | 1-3 | labels |
| Dark green | FF009900 | 1 | a label |
| Light grey | FFDCDCDC | 3 | text |
| Disabled grey | 80646464 | all | drawn over a disabled button's label |
| Cream / yellow | FFD1EAF5 / ..00E6FA | 4, 5 | the pulsing message |
| Pale cream, pale grey | FFC9E9F4, FFC4CCD2 | 4, 5 | labels |
| Light cyan on dark teal | FFF5E762 over FF685113 | 4, 5 | the outlined title |
| Green | FF00FF00 | 1, 4, 5 | buttons, a label |

## Any character: where each glyph comes from

The text is cut into grapheme clusters, so a letter with its accents, an emoji with its skin tone, a ZWJ
family, a flag or a keycap stays one glyph. Each cluster is drawn from the first of these that has it:

1. **The game's own glyph.** The cluster in NFC form is one character that Windows-1252 holds as a byte the
   sheet has a cell for. So "e" plus a combining acute is New Believers' own "é". These are drawn exactly as
   the game draws them.
2. **The patcher's own glyph.** This is the letter the patched game itself draws. It comes from
   `src/vv_font_glyphs.py`, the in-game Unicode text's module, which it shares with the companion DLL so a
   letter looks the same in both.
   - The tab calls `vv_font_glyphs.glyph("vv<n>", "ldwarialbold" | "ldwBurweed27", char, images_dir)` with the
     folder that holds the font sheets (the Studio's copy).
   - It uses the returned box (one line tall, white; its width is the advance) whenever its source is not the
     game's own letter.
   - Without that module, this step finds nothing.
3. **A generated glyph** in the font's style (`src/vv_glyph_maker.py`). The preview marks each one.
   - **A letter with accents** (NFD): the longest leading part the font or the patcher has (for "ǘ", "ü" if
     there is one, else "u"), with each remaining accent generated and placed on it. Above accents sit one
     clear row above the letter, centred over it. A cedilla or an ogonek attaches at the baseline, and other
     below accents go under it. A stroke goes through the letter. So A New Home's "é" is its own "e" with an
     acute added.
   - **A compatibility character** whose parts the font has (NFKD): the parts side by side, for example
     "ﬁ" as "f" and "i", or "ǅ" as "D" and "ž".
   - **Anything else** is drawn from a Windows font through GDI (ctypes; Python and Windows only, no Pillow,
     and no font file ships):
     - **The face.** For Arial Bold, Arial in bold. For Burweed, Burweed ICG when it is installed (the face
       the sheet was drawn from), else Segoe Print. When the face lacks the character, the first of Segoe
       UI, Arial Unicode MS, Segoe UI Symbol, Nirmala UI, Microsoft YaHei, Malgun Gothic, Yu Gothic and the
       rest that has it, then Windows' own font linking.
     - **Size and place.** The face is sized so its "H" is exactly as tall as the sheet's "H", and it sits on
       the sheet's baseline.
     - **Drawing.** Text is drawn at four times the size and box-filtered down. Its coverage becomes alpha,
       rounded to the sheet's own alpha levels, in the sheet's white. So the game's colours recolour it the
       same way.
     - **Complex scripts.** They are shaped by Windows (Uniscribe). A run of right-to-left text (Arabic,
       Hebrew, with the spaces between its words) is drawn as one piece, so its letters join and read right
       to left.
   - **Emoji, in full colour.** They come from Segoe UI Emoji's colour layers: COLR/CPAL, read from the
     installed font with GetFontData, shaped by the module's own GSUB/GPOS so ZWJ sequences, skin tones,
     keycaps and tag sequences are one glyph, and each layer drawn with GetGlyphOutline. They are as tall as
     the line, are never recoloured by the text colour, and are never rounded to the sheet's alpha levels.
     - Country flags come out as their two letters, and the England flag as a plain black flag, as Windows
       draws them.
     - An emoji newer than the installed font gets the text path.
4. **Nothing.** A hollow box, and the line under the preview names the character. This is what a computer
   without Windows' GDI gets for anything the game and the patcher lack.

The made glyphs advance by their own width plus the font's letter spacing, so a line mixing game and made
glyphs is laid out by the game's own rule.

## How it is proven (`tests/test_pictures_text.py`)

- **The tables.** `data/vv_font_tables.json` equals what `scripts/build_vv_font_tables.py` reads from the
  stock executables now. Each font's glyph set, line height and spacing are pinned too.
- **The loader**, for every game and both fonts. The game's own wrapper constructor and loader run in
  Unicorn on the stock executable. Only these are stood in for:
  - operator new and delete;
  - the file check;
  - the picture object, which is an SDL surface of the stock sheet's size, every pixel white;
  - the SDL calls the recolour makes;
  - the two blits, which are recorded.

  The cells, the 256-byte index, the line height and the spacing it leaves in memory equal `GameFont`'s.
- **The draw**, for every game and both fonts. The game's own text draw runs on six sample strings at three
  places in five colours (opaque, a tint, half and quarter faded, and alpha 0). The samples include every
  byte 0x01-0xFF except the line break, several lines and a blank line. Every blit equals `game_plan`'s, more
  than 10,000 in all: the sheet cell, the place, the surface alpha byte and the recolour's AND mask.
- **The rest of the game's layout.** The game's own width equals `GameFont.width`, its centred draw starts
  where `centred_x` says, and A New Home's and The Lost Children's box-centred draw starts where the docs say.
- **The Unicode renderer.** For text the font has, it puts every glyph where the game's draw puts it (checked
  against the emulator). Its pictures equal `game_render`'s pixel for pixel, in white, a tint and half alpha.
- **Made glyphs.** They are marked and counted by source, emoji sequences stay one glyph and keep their
  colours, and generated glyphs use only the sheet's alpha levels.
- **The rest.** Alignment, the outlined title, the name counter, the character search, the palette and the
  tab itself: drawing, saving through Picture Studio, the stock-game view and the picker.
- **Skipping.** The emulated tests skip without Unicorn, pefile and the stock executables (CI). The picture
  tests skip without `research/game-images`. The glyph maker's rendering tests skip off Windows.

## Samples

`outputs\` (not tracked) holds sample renders per game and per font, made by
`python scripts/render_text_samples.py <folder>`:
- plain text;
- accented text the old games lack;
- Greek, Cyrillic, CJK, Hangul, Devanagari, Arabic and Thai;
- emoji;
- the game's colours;
- each sample with and without the made-glyph outlines.
