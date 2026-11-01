# Translating the Virtual Villagers games

Anyone can translate the five Virtual Villagers games into their own language with the patcher: Japanese,
Chinese, French, Turkish, Greek, Sumerian Cuneiform, anything Unicode can spell. This guide is for
translators. The file format itself is described in [translation-file-format.md](translation-file-format.md);
the owner's side of accepting shared translations is in
[translations-for-maintainers.md](translations-for-maintainers.md).

## In short

1. In the patcher, open **Tools > Translations...** and choose the game.
2. Press **Make a translation**, pick your language, and translate in the built-in editor (or in Notepad or a
   spreadsheet: the file is plain text).
3. Choose your language in the **Language** list at the top. The game uses it from its next start; there is no
   need to patch again. Choose **English (original)** to go back.
4. To share it, press **Share on GitHub...** (see [Sharing](#sharing)).

The game must have been patched with the **Translations** patch, which is on by default.

## What can be translated

Each game's file holds every line the player can see whose words come from text, read from your own copy of
the game when the file is made (the patcher ships none of the games' words):

| Game | Game text | Where it comes from |
|---|---|---|
| A New Home | about 630 lines | the game's string table (`table/<id>` keys), plus 2 lines outside it (`exe/...`) |
| The Lost Children | about 880 lines | the game's string table (`table/<id>`), plus 7 lines outside it |
| The Secret City | about 1,200 lines | the game's string table (`sm/<name>` keys), plus 3 lines outside it |
| The Tree of Life | about 1,340 lines | `Assets\sm.xml` and the game's built-in table (`sm/<name>`), plus 3 lines outside them |
| New Believers | about 1,410 lines | `Assets\sm.xml` and the game's built-in table (`sm/<name>`), plus 3 lines outside them |

That is the menus, tips, tutorials, events and their choices, tech and job names, the Villager Details and
Statistics screens, popups and puzzles. Every file also holds the patcher's own text for that game (about 1,500
to 2,000 lines, `vvfp.<part>/...` keys): the Origins upgrades, the Story / Cheat Upgrades and the Custom Island
Event windows.

The Tree of Life's Optional Text Changes and New Believers' Guardians of Isola Rewrite change some English
lines. Make the file from the game you play (the patcher reads the patched copy first), so its English is the
English you see.

**What cannot be translated, and why:**

- **Words painted into pictures**: the title screen, button art, help and credits pages. They are images,
  not text.
- **The window's title** (the game's name in the title bar) stays English.
- **Villager names** are names, not translatable text.
- **Text the game draws for the patcher** (Cause of Death words on graves, the island event popups the
  Custom Island Event shows inside the game, Son / Daughter on A New Home's Details screen) stays English for
  now; it will follow when "Render Unicode with In-Game Fonts" draws the game's text itself. The patcher's
  own windows are translated.
- **Lists drawn by the patcher itself** in a few windows (owner-drawn lists) and lists the window sorts
  alphabetically stay English.
- **Word order glued in code.** A few screens build a sentence from pieces (for example "Completed in" +
  number + "hours", or the tech screen's cost line). Each piece is its own line; their order is fixed. Make
  each piece read well on its own.
- **Very long lines.** The game keeps some text in fixed-size boxes and buffers. A translation much longer
  than its English may be cut off, and a line of the game's own text more than three times as long as its
  English (plus 64 bytes; a Chinese or Japanese character takes 3 bytes) is not used: the English shows, so a
  fixed-size buffer in the game can never overflow. No line may be longer than 4,000 bytes. The editor warns
  when a line is much wider than its English.

## Editing the file

The editor shows English on the left and your translation on the right. **Show untranslated only** and the
search box find what is left; the bar shows how much is done. Every change is saved after a moment.

In Notepad or a spreadsheet:

- Keep the file **UTF-8** (Notepad: *Save as > Encoding: UTF-8*). A spreadsheet may save it as tab-separated
  "Unicode Text" (UTF-16); that works too. Any other encoding is refused as a whole.
- Fill **only the Translation column**. Never edit the Key or English columns: the key carries a fingerprint
  of the English, and a line whose English changed is not used.
- Line breaks are written `\n`, tabs `\t`, a backslash `\\`.
- An empty translation means "not yet": the English shows.

## Placeholders

Keep every placeholder of the English line:

- **`%d`, `%i`, `%s`, `%02d` ...** are filled in by the game. They must all stay, **in the same order** (the
  game cannot reorder them). `%%` is a percent sign in such a line.
- **No `%` in a line whose English has none**: the game may use the line as a format, and a `%` would break
  it. Write the word for "percent".
- **`{name}`, `{name2}`, `{award}`** (The Secret City, The Tree of Life, New Believers) are the villagers'
  names and a number; each must stay, in any order.
- **A New Home and The Lost Children's island events** use one-letter codes: `*` is the villager's name,
  `^` he/she, `&` He/She, `+` him/her, `=` his/her. Keep `*`; you may drop the pronoun codes and use a gender
  select instead (below); never add one the English does not have. A few event pieces also carry `|`, `~`,
  `@`, `#` or `$`: keep them exactly.

The Notes column says what each placeholder is.

## Gender and plurals

Words that change with a person's sex or with a number are written as a **select**:

```
{SUBJECT: key=text | key=text | ...}
```

- For a **person**: `m` (male), `f` (female), `o` (other: unknown, a group). French:
  `{*: m=Il est content | f=Elle est contente | o=Iel est content·e}`.
- For a **number**: the plural categories of your language (`zero`, `one`, `two`, `few`, `many`, `other`) or
  an exact number `=0`. Polish: `%d {%1: one=plik | few=pliki | many=plików}`.
- **SUBJECT** is `%1`, `%2` ... (the first, second ... placeholder of the English), a variable such as
  `name`, or `*` in A New Home's and The Lost Children's events.
- A missing branch falls back to `o` (people) or `other` (numbers). Put placeholders outside the select.

What each game can use:

| Game | People | Numbers |
|---|---|---|
| A New Home, The Lost Children | `*` in island events (the event's villager) | `%N` on a number placeholder |
| The Secret City, The Tree of Life, New Believers | `{name}` and `{name2}` (only `m` and `f`: the game itself picks) | `%N` on a number placeholder |
| every game | `%N` on a `%s` that is a villager's name (found by name; `o` when not unique) | |

The Secret City, The Tree of Life and New Believers also understand their own short form, `{male/female}` for
`{name}` and `{male/2/female}` for `{name2}`, for example `{il/elle}`.

The editor previews every variant (male, female, other, and a number for each plural category).

## Fonts and scripts

The games draw text with their own small bitmap fonts:

- **Without "Render Unicode with In-Game Fonts"**: only the characters of the game's own font show. A New
  Home has a few accented letters, The Lost Children only A-Z, a-z, digits and basic punctuation.
- **With "Render Unicode with In-Game Fonts"** (its current version): every Windows-1252 character
  (Western European letters such as é, ñ, ü, ß, œ, the euro sign) is drawn in the game's style.
- **Other scripts** (Turkish ğ ş ı, Greek, Cyrillic, Arabic, Hebrew, Chinese, Japanese, Korean, Cuneiform)
  are accepted in the file, previewed in the editor and kept, but show as "?" in the game until a later
  version of that patch draws them from the system's fonts. Windows fonts that have them: Segoe UI (Latin,
  Greek, Cyrillic), Yu Gothic / Meiryo (Japanese), Microsoft YaHei (Simplified Chinese), Microsoft JhengHei
  (Traditional Chinese), Malgun Gothic (Korean), Segoe UI Historic (Cuneiform). The patcher's own windows show
  every script already.

## Sharing

**If you want to share your translation, consider going to the Patcher's GitHub page and adding it!**
How: press Share on GitHub..., drag the file in, press Submit.

1. Press **Share on GitHub...** in the Translations window and read the question (No is the default; No does
   nothing).
2. Type the name you want to be credited as. It will be public. **Email addresses are never saved and are
   rejected from translation files.**
3. The patcher saves the file, shows it in its folder, and opens GitHub's "Share a translation" form with the
   game and language filled in. You need a GitHub account (free: <https://github.com/signup>).
4. Drag the file from the folder into the form's file box, type your credit name again, tick the licence box
   and press **Submit**.

If the owner accepts it, it ships with the next patcher release and appears in everyone's Language list as
"<Language>, by <your name>".

To install a file someone sent you, press **Add translation file...** (or drag it onto the Translations
window). It is checked first; lines with problems stay English, and a file with an email address in it is
refused.

## When the patcher is updated

Your translation keeps working: each line is found by its key. When an update adds lines, the editor shows
them as untranslated; a line whose English changed shows its old translation in the Notes for you to check and
uses the English until you translate it again.
