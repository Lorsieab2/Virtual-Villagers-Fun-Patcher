"""Write data/vv<N>_unicode_text_feature.json and data/vv<N>_unicode_font_feature.json, all five games.

  * "Render Unicode with In-Game Fonts" (vvN_unicode_text, on by default and in Owner's Defaults): the game's
    own two bitmap fonts draw every character -- the ones they hold, PR #670's Windows-1252 letters, and every
    other character made at run time in the font's style from the player's Windows fonts.
  * "Use Unicode Font (overrides in-game fonts)" (vvN_unicode_font, off by default and in Owner's Defaults --
    the owner, 2026-11-01): every letter drawn in a Windows typeface the player picks (Segoe UI unless chosen).
The two can never be built together (each names the other in "conflicts").

Both are one source, native/vvfp_unicode_text: "VVFP Unicode Text.dll" and, built with VVFP_FONT_OVERRIDE,
"VVFP Unicode Font.dll" (scripts/build_vvfp_unicode_text.ps1), started by VVFP Startup.dll from its second
word (native/shared/startup_companions_2.h).  Neither patches an executable byte: each detours, at run time
and only after checking every site's stock bytes, the font constructor, the SDL_TEXTINPUT case and the text
routines in native/vvfp_unicode_text/text_routines.h.

One command after the DLL's source changes: this script builds both and pins them by SHA-256 in all ten rows.
--no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_DLL = "VVFP Unicode Text.dll"
FONT_DLL = "VVFP Unicode Font.dll"
DLLS = {TEXT_DLL: ROOT / "assets" / "unicode_text" / TEXT_DLL, FONT_DLL: ROOT / "assets" / "unicode_font" / FONT_DLL}
FONT_FOLDER = ROOT / "assets" / "unicode_fonts"
FONT_DESTINATION = "Unicode Fonts"
# The open fonts bundled as the last steps of the glyph chain, and the licence texts that travel with them.
BUNDLED_FONTS = ("NotoSansCuneiform-Regular.otf", "NotoSerifTangut-Regular.otf", "unifont-18.0.01.otf",
                 "unifont_upper-18.0.01.otf", "LastResortHE-Regular.ttf")
BUNDLED_NOTICES = ("NotoSansCuneiform-OFL-1.1.txt", "NotoSerifTangut-OFL-1.1.txt", "Unifont-OFL-1.1.txt",
                   "Unifont-GPL-2.0-COPYING.txt", "LastResort-OFL-1.1.txt", "SOURCES.json")
BUNDLED_SUMMARY = (
    "**Bundles four open fonts, loaded privately by the game (never installed in Windows): GNU Unifont 18.0.01 "
    "(GPL-2.0-or-later with the font exception, or OFL-1.1) and Unifont Upper for nearly every assigned "
    "character, Noto Sans Cuneiform and Noto Serif Tangut (OFL-1.1), and Last Resort 18.000 (OFL-1.1), a "
    "placeholder block for anything still without a glyph; about 14 MB of fonts (in the patcher's files "
    "folder, in \"Unicode Fonts\", with their licence texts and sources), copied once per game folder, "
    "and not again when the folder already has identical files.**"
)
TABLES = ROOT / "data" / "font_glyph_tables.json"
ROUTINES = ROOT / "native" / "vvfp_unicode_text" / "text_routines.h"
GAMES = (1, 2, 3, 4, 5)
TEXT_NAME = "Render Unicode with In-Game Fonts"
FONT_NAME = "Use Unicode Font (overrides in-game fonts)"
# Every text box's byte limit, and the most a name can be (native/vvfp_unicode_text/long_names.inc).
SHARED_NAME_BYTES = 1200
FIELDS = {
    1: "a villager's name 27 bytes, the tribe name 31",
    2: "a villager's name 23 bytes, the tribe name 31",
    3: "a villager's name 23 bytes, the tribe name 19",
    4: "a villager's name 23 bytes, the tribe name 19",
    5: "a villager's name 23 bytes, the tribe name 19",
}

COVERAGE = {
    1: "A New Home's two fonts hold only A-Z, a-z, 0-9 and ! \" ' , . ? / ` : -",
    2: "The Lost Children's two fonts hold only A-Z, a-z, 0-9 and ! \" ' , . ? / ` : -",
    3: "The Secret City's fonts hold ASCII and the Latin-1 letters",
    4: "The Tree of Life's fonts hold ASCII and the Latin-1 letters",
    5: "New Believers' fonts hold ASCII and the Latin-1 letters",
}

NAMES_AND_TYPING = (
    "Typing: every text box -- the tribe name, villager names on the Details screen, epitaphs -- takes any "
    "character Windows sends (dead keys, Alt codes, the Windows emoji panel, an input method for Japanese or "
    "Chinese), each stored whole or not at all, and Backspace erases a whole character (a whole emoji, flag or "
    "accented letter). Long names, everywhere: every name box takes names up to " + f"{SHARED_NAME_BYTES:,}" + " bytes "
    "(up to " + f"{SHARED_NAME_BYTES:,}" + " plain letters; fewer when letters need more bytes): the tribe name, "
    "villager names on the Details screen, epitaphs; Rename Tribe takes the same. It is one limit, shared with the "
    "other Fun Patchers. Characters are counted as you see them (a letter with its accents, an emoji with its "
    "skin tone or a flag is one), and Backspace removes one whole character. A long name scrolls in its box while "
    "you type it. The save itself is not changed: a name that fits its field ({fields}) is kept there exactly as "
    "before; a longer one is kept there as its short form (its start and a mark, with a number when two would "
    "start alike) and the whole name is kept beside the save, in Virtual Villagers Fun Patcher\\Save <n>\\Data\\Long "
    "Names. The game shows the whole name wherever it shows that name. Back Up Saves, Restore Saves and Copy Player "
    "Slot carry the Long Names files with the saves. With both settings off the game still loads and plays such a "
    "save and shows the short form. Characters are stored as UTF-8 (a Western European letter keeps its one "
    "Windows-1252 byte), so every older name reads as before; the base game and older patchers show other "
    "characters as odd letters but never break. "
)


NEEDS = ("**Needs \"Full Names on the Details Screen\" (ticked with it): its Details box keeps the whole stored "
         "name, so opening a villager's Details and closing it never changes a name.**")


def text_description(game: int) -> str:
    return (
        "Lets the game draw, measure and accept ANY character -- accented letters, Greek, Cyrillic, Turkish, "
        "Chinese, Japanese, Korean, Arabic and Hebrew (joined and right to left), Indian scripts, cuneiform, "
        "symbols and colour emoji -- in the game's own two fonts (the big Burweed story font and the small "
        "Arial Bold font). " + COVERAGE[game] + "; every other Windows-1252 character is added to the fonts "
        "in their own style when the game starts (from the font's own plain letter with the accent added, or "
        "drawn by Windows in the font's own typeface: Arial Bold is part of Windows; **for Burweed, install the "
        "Burweed ICG font for the best-matching letters** -- the patcher never ships it -- otherwise Comic Sans "
        "MS stands in), and every other character is made the first time it is shown, in the font's size, "
        "baseline and weight, from the fonts Windows has (Segoe UI, Segoe UI Historic, Segoe UI Symbol, Segoe "
        "UI Emoji (in colour), the CJK fonts, Nirmala UI, Ebrima ..., Noto if installed, then the bundled open fonts: Noto Sans Cuneiform, Noto Serif Tangut, GNU Unifont and "
        "Unifont Upper, and last Last Resort, so every one of Unicode 18.0's assigned characters draws, even "
        "ones no Windows font has). Names, the Details screen, popups, dialogs and every other text use them with their "
        "real widths, so centring and line breaks stay right; Chinese and Japanese break between characters. "
        + NAMES_AND_TYPING.format(fields=FIELDS[game])
        + "**On by default and in Owner's Defaults.** **Cannot be used with \"" + FONT_NAME + "\" (ticking one "
        "unticks the other).** " + NEEDS + " **Not yet seen in a running game** (checked by "
        "emulation of each stock executable). The companion is \"" + TEXT_DLL + "\", started by VVFP "
        "Startup.dll; the game's own pictures and saves are never changed. " + BUNDLED_SUMMARY
    )


def font_description(game: int) -> str:
    return (
        "Draws ALL of the game's text in a Windows typeface instead of the game's own bitmap fonts: Segoe UI "
        "unless you choose another in the patcher (the Unicode Font box, or the Tools tab's Unicode Font... window: "
        "any installed family, or a .ttf, .otf or .ttc file; the choice is written next to the game as \"VVFP "
        "Unicode Font.txt\"), with Windows' fallback chain for every character it lacks (Segoe UI, Segoe UI "
        "Historic, Segoe UI Symbol, Segoe UI Emoji (in colour), the CJK fonts, Nirmala UI, Ebrima ..., Noto if "
        "installed, then the bundled open fonts: Noto Sans Cuneiform, Noto Serif Tangut, GNU Unifont, Unifont "
        "Upper and last Last Resort). Each of the game's two fonts keeps its line height, baseline and weight, and "
        "its size is fitted so a line is as wide as the game's own, so every screen keeps its layout; every "
        "character works, as with \"" + TEXT_NAME + "\". "
        + NAMES_AND_TYPING.format(fields=FIELDS[game])
        + "**Off by default and in Owner's Defaults.** **Cannot be used with \"" + TEXT_NAME + "\" (ticking "
        "one unticks the other).** " + NEEDS + " **Not yet seen in a running game** (checked by "
        "emulation of each stock executable). The companion is \"" + FONT_DLL + "\" (the same code as \""
        + TEXT_DLL + "\"), started by VVFP Startup.dll; the game's own pictures and saves are never changed, "
        "and no Windows font is shipped. " + BUNDLED_SUMMARY
    )


def routines() -> dict:
    """text_routines.h: each game's addresses and the stock bytes (the same in every game)."""
    text = ROUTINES.read_text(encoding="utf-8")
    fields = re.search(r"unsigned int (width[^;]+);\s*unsigned int (chartype[^;]+);", text)
    names = [n.strip() for n in (fields.group(1) + "," + fields.group(2)).split(",")]
    rows = re.findall(r"\{(0x[^}]*)\},\s*/\* (vv\d) \*/", text)
    games = {}
    for body, game in rows:
        values = [int(v.strip().rstrip("u"), 16) for v in body.split(",")]
        games[game] = dict(zip(names, values))
    stock = {m.group(1).lower(): bytes(int(b, 16) for b in m.group(2).split(","))
             for m in re.finditer(r"STOCK_(\w+)\[\d+\] = \{([^}]*)\}", text)}
    return {"games": games, "stock": stock}


ROUTINE_TEXT = {
    "width": "the text width routine (thiscall: font; text, scale)",
    "draw": "the text draw routine (thiscall: draw context; text, x, y, colour, font)",
    "linefit": "the line-fitting routine of dialogs (thiscall: font; text, line buffer, bytes, width, ...)",
    "nbyte": "the counted text draw/measure routine justified paragraphs use",
    "justify": "the justified paragraph routine",
    "ctldraw": "the text control's draw routine (an editable box cuts its text one byte at a time here)",
    "seteditable": "the text box's SetEditable (its byte limit)",
    "settext": "the text box's SetText",
    "gettext": "the text box's GetText(buffer, size)",
    "chartype": "the text box's character handler, at its message check (mov eax,[esp+4]; cmp eax,6)",
    "backspace": "the text box's Backspace (mov edx,[ecx+0x30]; mov byte [edx+eax-1],0)",
}


def detours(game: int, dll: str, tables: dict, found: dict) -> list:
    g = tables["games"][f"vv{game}"]
    text = g["text_input"]
    by = f"{dll}, VvfpStartup (started by VVFP Startup.dll, second word)"
    out = [
        {"va": g["ctor"], "stock_bytes": g["ctor_bytes"][:2 * g["ctor_len"]],
         "routine": "the LDW font constructor (thiscall: font; picture name, glyph table, spacing)", "installed_by": by},
        {"va": text["site"], "stock_bytes": text["stock_bytes"],
         "routine": "the event pump's SDL_TEXTINPUT case (lea eax, [esp + text]; lea edx, [eax + 1])", "installed_by": by},
    ]
    for key, what in ROUTINE_TEXT.items():
        va = found["games"][f"vv{game}"][key]
        if va:
            out.append({"va": f"0x{va:X}", "stock_bytes": found["stock"][key].hex().upper(), "routine": what,
                        "installed_by": by})
    return out


def behaviour(game: int, tables: dict, override: bool) -> list:
    g = tables["games"][f"vv{game}"]
    fonts = g["fonts"]
    first = (
        f"The font constructor ({g['ctor']}) runs unchanged; for the game's two fonts -- ldwBurweed27 (stock glyph "
        f"table {fonts['ldwBurweed27']['table']}) and ldwarialbold ({fonts['ldwarialbold']['table']}) -- the "
        "companion records the font's line height, baseline, capital height and pixel format"
    )
    first += (". Their own letters are not used: every letter is made from the chosen Windows typeface." if override else
              ", then adds every printable Windows-1252 character the font lacks (src/vv_font_glyphs.py, run in C by "
              "native/vvfp_unicode_text/glyphs.inc) as new rows under the loaded picture and new entries in a copy "
              "of the glyph table.")
    return [
        first,
        "Text is read by one rule (src/vv_game_text.py, native/vvfp_unicode_text/text_utf8.h): a well-formed UTF-8 "
        "sequence is its character, every other byte its Windows-1252 character, so every existing name reads as "
        "before. The width, draw, line-fitting, counted-draw and justified-paragraph routines are detoured: text "
        "without a multi-byte sequence goes to the game's own routine unchanged" + (" (with this patch, every text "
        "is drawn by the companion)" if override else "") + "; other text is cut into whole units (grapheme "
        "clusters; shaped runs of Arabic, Hebrew, Indic and other scripts) and drawn in runs by the game's own draw "
        "and width routines, from the font's own letters or from pages of letters made at run time (Uniscribe "
        "shaping, GDI glyphs, COLR colour layers for emoji) in the font's size and baseline.",
        "Each detoured text routine first offers the text to VvfpTranslateText of \"VVFP Translations.dll\" when "
        "that companion is loaded (fails open), and shows a long name's short form as the whole name.",
        "Line breaking follows UAX #14 by Windows' own icu.dll (loaded from System32 only; a built-in table where "
        "Windows has none): a text with Chinese, Japanese, Korean, Thai, Lao, Khmer, Myanmar or emoji breaks between "
        "whole characters where the rules allow (never before a closing mark or small kana, never after an opening "
        "one; Thai and the others at their words, inside a shaped run too), other text at spaces, and a word wider "
        "than the line after its longest start of whole characters that fits.",
        f"The SDL_TEXTINPUT case ({g['text_input']['site']}) posts a typed ASCII character exactly as before; any "
        "other well-formed text is handed whole to the focused text box, which stores each character whole (a "
        "Windows-1252 character as its one byte, any other as UTF-8) while it fits the box's limit. Backspace erases "
        "a whole unit. A box never cuts its text by pixels. Every box's limit is " + str(SHARED_NAME_BYTES) + " bytes; "
        "a text longer than the field GetText copies it to leaves as a short form: its longest "
        "start of whole characters, then \"...\" (\"2...\", \"3...\", the number first, when another long name has it; the older short forms ending in … "
        "stay readable), whose whole text is appended to the save's Long Names file and given back "
        "when the game puts the short form into a box.",
    ]


def bundled_files() -> list:
    """The bundled fonts, their licence texts and SOURCES.json: all five games, both rows, one pinned list."""
    return [
        {"source": f"assets/unicode_fonts/{name}", "destination": f"{FONT_DESTINATION}/{name}", "sha256": sha(FONT_FOLDER / name)}
        for name in BUNDLED_FONTS + BUNDLED_NOTICES
    ]


def row(game: int, override: bool, dll_sha: str, tables: dict, found: dict) -> dict:
    dll = FONT_DLL if override else TEXT_DLL
    folder = "unicode_font" if override else "unicode_text"
    other = f"vv{game}_unicode_text" if override else f"vv{game}_unicode_font"
    return {
        "id": f"vv{game}_{folder}",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": FONT_NAME if override else TEXT_NAME,
        "description": font_description(game) if override else text_description(game),
        "output_tag": "Unicode Font" if override else "Unicode Text",
        "conflicts": [other],
        "dependencies": [f"vv{game}_details_full_names"],
        "behavior_changes": behaviour(game, tables, override),
        "explicit_non_changes": [
            "No executable byte is patched: the companion replaces each routine's first instructions at run time, "
            "all of them or none, only after verifying their stock bytes, and installs nothing on a different build.",
            "The game's pictures (Images\\ldwBurweed27.png, Images\\ldwarialbold.png) are never changed and nothing of "
            "the game's art is shipped; letters are made in memory from the player's own Windows fonts and, for what "
            "they lack, from the bundled open fonts (Unicode Fonts folder), which are added to the game's process "
            "only (FR_PRIVATE) and never installed in Windows; a missing or unreadable font file only leaves its "
            "step out.",
            "A save's records only ever hold what fits their fields: every stock copy of a name sees the short form, "
            "never more bytes than the stock game wrote. Nothing is cut inside a character.",
            "A fault in any detour falls back to the game's own routine with the game's own text.",
        ],
        "companion_files": [
            {"source": f"assets/{folder}/{dll}", "destination": dll, "sha256": dll_sha},
            *bundled_files(),
        ],
        "patches": [],
        "runtime_detours": detours(game, dll, tables, found),
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_unicode_text.ps1")], check=True)
    tables = json.loads(TABLES.read_text(encoding="utf-8"))
    found = routines()
    for override, dll in ((False, TEXT_DLL), (True, FONT_DLL)):
        digest = sha(DLLS[dll])
        for game in GAMES:
            out = ROOT / "data" / f"vv{game}_{'unicode_font' if override else 'unicode_text'}_feature.json"
            out.write_text(json.dumps(row(game, override, digest, tables, found), indent=2) + "\n",
                           encoding="utf-8", newline="\n")
            print("wrote", out.relative_to(ROOT), digest)


if __name__ == "__main__":
    main()
