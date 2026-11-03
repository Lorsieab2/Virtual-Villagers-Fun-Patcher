# Translation file format (version 1)

One format for every patcher in this family, so a translator learns it once. Nothing in the format
itself is specific to one game; each program only decides which strings it exports and how its runtime
finds the chosen file.

## One file per game per language

- A translation is **one plain text file** for **one game** in **one language**.
- File name: `<Game title> - <Language name>.txt`, where the language name is the language's own name
  for itself. Examples: `Virtual Villagers - The Secret City - Français.txt`,
  `Virtual Villagers - New Believers - 日本語.txt`.
- Installed translations live in the program's `Translations` folder (beside the program, one flat
  folder). The **Export translation...** action writes a copy with the same name for sharing.
- The program never ships translations. It ships only the English template, which it generates on
  demand.

## Encoding

- Written as **UTF-8 with a byte-order mark** (so old Notepad and spreadsheets detect UTF-8).
- Read as UTF-8 with or without a BOM, and also as UTF-16 LE or BE when the file starts with a UTF-16
  BOM (what a spreadsheet's "Unicode Text" save produces). Anything else is rejected as a whole (the
  game stays in English) and reported.
- Any Unicode code point is allowed in a translation, including scripts outside the Basic Multilingual
  Plane (for example Cuneiform, U+12000 onwards). Whether a script can be *drawn* depends on the fonts
  the runtime can find; see each program's translator guide.
- Line endings: CRLF or LF.

## Layout: a tab-separated table

Every line is either blank, a comment, or a row of **tab-separated** columns:

```
Key<TAB>English<TAB>Translation<TAB>Notes
```

- **Key**: the string's stable identity (below). Never edit it.
- **English**: the original text, kept beside the translation for the translator. Never edit it; the
  program compares it with the current English to notice changed text.
- **Translation**: the translated text. Empty means "not translated yet" and the English is used.
- **Notes**: optional, written by the export and ignored when reading: where the text appears, its
  placeholders, and its box width if the program knows it. Translators may write their own notes here.

The first row that is not a comment is the header row `Key	English	Translation	Notes`. Columns after
Notes are ignored, so a spreadsheet may add its own.

Opening the file in a spreadsheet as tab-separated text and saving it back as tab-separated text (UTF-8
or Unicode Text) keeps it valid. A field a spreadsheet wraps in double quotes (`"..."` with `""` for a
literal quote) is unquoted when read; the export quotes any field that itself begins with `"`.

### Comments

A line whose first character is `#` is a comment. Comments are kept by the built-in editor but carry no
meaning.

### File information rows

Rows whose key starts with `@` describe the file. The English column holds the English value and the
Translation column the file's value:

| Key | English | Translation | Meaning |
|---|---|---|---|
| `@format` | `1` | `1` | Format version. A file with a newer major version is refused. |
| `@game` | game title | (optional translated title) | Which game the file is for. A file for another game is refused. |
| `@language` | `English` | `Français` | The language's own name, shown in the language list. |
| `@code` | `en` | `fr` | BCP 47 language code (`fr`, `tr`, `ja`, `zh-Hans`, `akk`). |
| `@translator` | | free text | Optional credit. |

### Escapes inside a field

Tabs and line breaks cannot appear literally in a cell, so a field uses:

| Write | Means |
|---|---|
| `\n` | line break |
| `\t` | tab |
| `\\` | one backslash |

Any other backslash is kept as written. Spaces at the start or end of a field are kept exactly; the
validator warns when the translation's leading or trailing spaces differ from the English.

## Keys

```
<source>/<id>~<hash>
```

- `<source>`: where the text comes from, a short lowercase name chosen by the program (for example
  `exe`, `menu`, `events`, `tips`, `ui`). Letters, digits, `_`, `-` and `.` only.
- `<id>`: a stable position inside that source that never changes between program versions: an offset,
  a resource number, an element path or a name. Letters, digits, `_`, `-`, `.` and `/` only.
- `<hash>`: the first 8 hex digits (lowercase) of the SHA-256 of the English text in UTF-8, after
  escapes are decoded.

Matching when the file is read:

1. **Same key**: the translation is used.
2. **Same `<source>/<id>`, different hash**: the English has changed since the file was made. The
   translation is **not** used (the new English shows), the editor marks the line "English changed"
   and keeps the old translation beside it for review.
3. **Key the program does not know**: ignored and reported (text removed in this version).
4. **Key in the program but missing from the file**: the English is used; the editor adds the line as
   untranslated (this is how new text from a program update appears).

So a translation made for one version keeps working in later versions: only lines whose English really
changed fall back.

## Placeholders and variables

The English text's placeholders are a contract the translation must keep. Two kinds exist:

- **printf conversions**: `%d`, `%i`, `%u`, `%s`, `%c`, `%x`, `%f`, with flags, width and precision
  (`%5.1f`, `%-3d`, `%02d`), and `%%` for a literal percent sign. The translation must contain **the same
  conversions in the same order** (the program passes the values in English order and cannot reorder
  them). A width or precision may change (`%d` -> `%3d`), but a conversion never gains the space flag alone
  (`% d`).
- **A `%` is a placeholder only when the line's own English has that token.** Any other `%` is plain
  text, so French "2 %", "2 %" and "50 % de réduction" are fine. When the program passes the line
  through printf as a format, the patcher writes such a plain `%` as `%%` in the text it hands over, so
  the game shows one `%` (the extra bytes count toward the line's room). Writing `%%` yourself still works
  where the English has a conversion; in a line the program does not format it shows two signs, and the
  checker warns.
- **Named variables**: `{name}`, `{count}`, `{village}`, etc. The translation must contain **every
  variable the English has, at least once, spelled exactly**, in any order. A variable not in the
  English is an error. Write `{{` and `}}` for literal braces.

A gender or plural select (below) only chooses words by its subject; it does not replace it. Where the
English has `%s` for a name, the translation must still contain that `%s`, even if it also has
`{%1: m=Il | f=Elle}`.

Programs may declare further protected tokens (for example a colour or line-break code, or a game's own
one-character name and pronoun codes); the export lists them in the Notes column. A token the program
marks as required must stay; a token the English does not have may not be added where the program says
it has a meaning there. A game token can also be a select subject when the Notes column declares it a
person (for example `{*: m=content | f=contente}` where `*` stands for the villager's name).

A row whose placeholders do not match is an **error**: that row falls back to English and is reported.
It never crashes, and it never affects the other rows.

## Gender and plural selects

Many languages change words with the sex of a person or with a number: French *il est content* /
*elle est contente*, Spanish *el* / *la*, German *der* / *die*, Polish *1 plik* / *2 pliki* / *5 plików*.
One syntax covers both, usable anywhere in a line, any number of times:

```
{SUBJECT: key=text | key=text | ...}
```

- **SUBJECT** says what the choice depends on:
  - a named variable from the English, such as `{actor: ...}` or `{count: ...}`, or a game token the
    Notes column declares a person, such as `{*: ...}`;
  - `%1`, `%2`, ... for the 1st, 2nd, ... printf conversion of the English, counted in English order
    (`%%` does not count). `{%1: ...}` chooses by the first value.
- Whether a subject is a **person** or a **number** is fixed by the program and written in the Notes
  column of the English template, together with where the person's sex comes from, for example
  `%1 = villager name (person; sex from the villager record)` or `{count} = number`.
- **Person keys**: `m` (male), `f` (female), `o` (other: unknown sex, a group, mixed company, or no
  person). Example:
  `{%1: m=Il est content | f=Elle est contente | o=Iel est content·e}`.
- **Number keys** are the CLDR plural categories of the file's `@code` language (`zero`, `one`,
  `two`, `few`, `many`, `other`), plus exact values `=0`, `=1`, `=2`, ... which win over categories.
  Example (French): `%d {%1: one=pomme | other=pommes}`; Polish:
  `%d {%1: one=plik | few=pliki | many=plików | other=pliku}`. The categories per language are CLDR's;
  the translator guide lists them for common languages, and a language the program does not know uses
  English's (`one` for exactly 1, otherwise `other`).
- **Two people in one line**: each select names its own subject, so
  `{actor: m=Il | f=Elle | o=Iel} a soigné {target: m=son fils | f=sa fille | o=son enfant}` picks each
  word by the right person.
- **Missing branch fallback**: a person select missing `m` or `f` uses `o`; if `o` is missing too it
  uses the first branch written. A number select missing a category uses `other`; if `other` is missing
  it uses the first branch written. A select is never an error just for missing branches.
- **Inside a branch** you may use named variables (`{village}`) but not printf conversions and not
  another select; put the conversion outside: `%d {%1: one=pomme | other=pommes}`. Write `\|` for a
  literal `|` and `{{` / `}}` for literal braces inside a branch.
- **Malformed select** (no `:`, an unknown key, an unknown subject, a printf conversion inside a
  branch, a select used on a person subject with number keys or the reverse, unbalanced braces): the
  row is an error and falls back to English.
- **English uses the same syntax.** Where the program itself chooses English words by sex or number,
  the English column shows that choice as a select, for example
  `{%1: m=He | f=She | o=They} found an apple.`, so translators see every place gender or number
  applies. A row whose English has no select may still use selects in its translation, on any
  subject the Notes column declares.
- At runtime the program evaluates selects from the live data (the person's recorded sex, the actual
  number). When the program cannot tell a person's sex at that point, the `o` branch is used.

The built-in editor previews every variant (male, female, other, and one example number per plural
category) and warns about a malformed select.

## Fallback, in one list

- No language chosen ("English (original)"): the program behaves exactly as it does without
  translations.
- Empty translation, changed English, broken placeholders, a bad escape or a bad row: that one line
  shows the English.
- A file that cannot be read at all (wrong encoding, wrong game, newer major format, missing header):
  everything shows the English, and the problem is reported in the program.
- Text that cannot be drawn because no font has the glyph: the program's text renderer decides
  (typically a replacement box); the translation is still used.

## Validation report

The program's **Validate** (also run on **Add translation file...**) reports, per file:

- coverage: translated rows / total rows, as a percentage;
- errors (row falls back to English): placeholder mismatch, unknown key, bad escape, wrong column count;
- warnings (row is used): English changed, leading/trailing space differs, text wider than its box,
  glyphs no installed font can draw.

## Exporting the English template

Every program provides a **Make a translation** action (choose a language, the program writes a file
with every row's Key, English and Notes filled and the Translation column empty), and a command line
equivalent for automation. The template is regenerated from the program's own string inventory each
time, so it always matches the installed version.

## Sharing

**Export translation...** writes the file under the name above. **Share on GitHub...** exports it,
opens its folder with the file selected, and opens the program's GitHub new-issue page with a
translation issue form (title, game and language pre-filled in the address; nothing personal). The
player drags the file into the form and presses Submit (a GitHub account is needed). Accepted
translations are added to the repository's `translations/<game>/` folder, ship in the next release and
appear in every player's language list, credited from `@translator`.

## Example

```
# Virtual Villagers - The Secret City, French translation
Key	English	Translation	Notes
@format	1	1
@game	Virtual Villagers - The Secret City	Virtual Villagers - La Cité secrète
@language	English	Français
@code	en	fr
menu/main.newgame~3c2f1a9b	New Game	Nouvelle partie	Main menu button
exe/0x4a51c0~91d0e2aa	%s has learned %d new skills!	%s a appris %d nouvelles compétences !	%s = villager name, %d = number
ui/origins.title~0b7e44c1	Welcome to {village}	Bienvenue à {village}	{village} = village name
exe/0x4a6230~77ab01c2	%s found an apple.	%s a trouvé une pomme. {%1: m=Il est content | f=Elle est contente | o=Iel est content·e}.	%1 = villager name (person; sex from the villager record)
ui/stats.apples~1f2e3d4c	{count} apples	{count} {count: one=pomme | other=pommes}	{count} = number
tips/12~5ad09c3e	Drag a villager to the tree.\nThey will gather food.	Faites glisser un villageois vers l'arbre.\nIl ramassera de la nourriture.
```
