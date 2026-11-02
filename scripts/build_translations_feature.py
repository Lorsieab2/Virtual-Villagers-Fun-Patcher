"""Write data/vv<N>_translations_feature.json: Translations, all five games (the owner, 2026-11-01).

The behaviour lives in one companion, "VVFP Translations.dll" (native/vvfp_translations), started by VVFP
Startup.dll from its second word of companions.  It is inert until the player chooses a language in the
Translations window (src/vv_translations_window.py), which copies the chosen file to "Virtual Villagers Fun
Patcher Files\\Translation\\Translation.txt"; with no file there it writes nothing and the game is stock.

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_translations.ps1) and
pins it by SHA-256 in all five rows.  --no-build pins what is already built.  The detour list is read from the
stock executables (inputs/, gitignored) and the inventory (data/translations/vv<N>_strings.json).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_translations as vt  # noqa: E402

DLL_NAME = "VVFP Translations.dll"
DLL = ROOT / "assets" / "translations" / DLL_NAME
GAMES = (1, 2, 3, 4, 5)
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)"

# (va, length, what) of each code site the companion may write (native/vvfp_translations/vvfp_translations.c).
SITES = {
    1: ((0x44D9AD, 9, "the C runtime's _output (every sprintf): a translated format with gender or plural "
                      "selects on its placeholders is resolved from the values; any other format goes on unchanged"),
        (0x427690, 6, "the good / bad outcome popup's text expander: '*' selects resolved by the villager's sex"),
        (0x4184A0, 6, "the island events' text expander: '*' selects resolved by the event villager's sex"),
        (0x42A750, 6, "the crate / vial events' text expander: '*' selects resolved by the villager's sex")),
    2: ((0x46AA2D, 9, "the C runtime's _output (every sprintf): selects on placeholders resolved"),
        (0x41F0F0, 6, "the island events' text expander: '*' selects resolved by the event villager's sex"),
        (0x437220, 6, "the sack / vial events' text expander: '*' selects resolved by the villager's sex")),
    3: ((0x471CFD, 9, "the C runtime's _output (every sprintf): selects on placeholders resolved"),
        (0x42F6E5, 5, "the string table's loader call (call 0x42F4F0): after it, each translated entry's text")),
    4: ((0x477CED, 8, "the C runtime's _output (every sprintf): selects on placeholders resolved"),
        (0x44D98A, 5, "the string table's loader call (call 0x44D750, Assets\\sm.xml): after it, each translated "
                      "entry's text")),
    5: ((0x4820FE, 8, "the C runtime's _output (every sprintf): selects on placeholders resolved"),
        (0x450C9D, 5, "the string table's loader call (call 0x450A60, Assets\\sm.xml): after it, each translated "
                      "entry's text")),
}
TABLE_TEXT = {
    1: "the string table at 0x487208 (629 rows): each translated row's English pointer (+4)",
    2: "the string table at 0x496300 (876 rows): each translated row's English pointer (+4)",
    3: "the string table at 0x4AB990: each translated entry's loaded-text pointer (+0xC), after the loader",
    4: "the string table at 0x4C41F8: each translated entry's loaded-text pointer (+0xC), after the loader",
    5: "the string table at 0x4D31F0: each translated entry's loaded-text pointer (+0xC), after the loader",
}

DESCRIPTION = (
    "Plays the game in another language. Choose a language for each game in Tools > Translations... (or make "
    "your own there: the patcher writes a file with every English line of the game, its menus, events, tips, "
    "tech names and the patcher's own windows, and a built-in editor shows each line in the game's font). The "
    "game uses the chosen language from its next start, with no re-patching; lines a translation leaves out, or "
    "gets wrong, stay English. Gender and plural words follow the villager or the number (for example il / elle, "
    "1 pomme / 2 pommes). **On by default, and English until you choose a language: with English chosen the game "
    "is exactly as without this patch.** **Accented letters need \"Render Unicode with In-Game Fonts\" (the "
    "game's own font lacks most of them); letters outside Windows-1252 (for example Turkish ğ ş ı, Greek, "
    "Cyrillic, Chinese, Japanese or Cuneiform) show as \"?\" until a later version of that patch draws them.** "
    "**Words painted into pictures (buttons, the title screen, help pages) stay English.** "
    "**Text the game draws for the patcher (Cause of Death words, island event popups) stays English for now; "
    "the patcher's own windows are translated.** **Works the same with every other patch and in every population "
    "mode.** **Not yet seen in a running game.** The companion is \"" + DLL_NAME + "\", started by VVFP "
    "Startup.dll; if it cannot be loaded, or the game's text is not the version a translation was made from, "
    "those lines stay English."
)


def stock_bytes(number: int, va: int, length: int) -> str:
    exe = ROOT / "inputs" / f"vv{number}-stock-copy" / f"{vt.TITLES[number]}.exe"
    image = vt.ExeImage(exe.read_bytes())
    off = image.offset(va)
    return image.data[off:off + length].hex().upper()


def row(game: int, dll_sha: str) -> dict:
    inv = vt.load_inventory(game)
    detours = [
        {"va": f"0x{va:06X}", "stock_bytes": stock_bytes(game, va, length), "routine": what,
         "installed_by": INSTALLED_BY}
        for va, length, what in SITES[game]
    ]
    for lit in inv.get("literals", []):
        for site in lit.get("sites", []):
            va = int(site, 16)
            detours.append({
                "va": f"0x{va:06X}", "stock_bytes": stock_bytes(game, va, 5),
                "routine": f"loads the text at {lit['va']} ({lit.get('context', '')[:60]}): its address becomes "
                           "the translation's",
                "installed_by": INSTALLED_BY,
            })
    return {
        "id": f"vv{game}_translations",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": "Translations",
        "description": DESCRIPTION,
        "output_tag": "Translations",
        "dependencies": [],
        "behavior_changes": [
            "At game start the companion reads \"Virtual Villagers Fun Patcher Files\\Translation\\Translation.txt\" "
            "(written by the patcher's Translations window; docs/translation-file-format.md). With no such file it "
            "returns at once and writes nothing.",
            "Each translated line replaces the English where the game looks it up: " + TABLE_TEXT[game] + "; the "
            "visible literals outside the table by the address their loading instruction pushes "
            "(data/translations/vv%d_strings.json).  A line is used only when the English it was made from is the "
            "English this game shows (the key's SHA-256), its placeholders match and its selects are well formed."
            % game,
            "The patcher's own windows (Origins, Story / Cheat Upgrades, Custom Island Event) are translated as they "
            "open (a WH_CALLWNDPROCRET hook on the game's own thread, only when the file translates any of them).",
            "Without \"Render Unicode with In-Game Fonts\" or \"Use Unicode Font (overrides in-game fonts)\" "
            "(their companion's VvfpGlyphsUtf8; Use Unicode Font's, which starts later, is loaded and started on "
            "first use), translations are given to the game in Windows-1252, '?' for what it cannot write.",
        ],
        "explicit_non_changes": [
            "This row changes no executable bytes: the companion checks each site's stock bytes and writes them at "
            "run time through the shared all-or-none writer, and writes only the ones the chosen file needs; if "
            "any check fails it writes nothing, not even a table pointer, and the game stays English.",
            "No save, record or game file is written; the game's own English text stays in memory unchanged.",
            "With English chosen (no Translation.txt), nothing at all is written.",
        ],
        "companion_files": [
            {"source": f"assets/translations/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
        "runtime_detours": detours,
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_translations.ps1")], check=True)
    digest = sha(DLL)
    for game in GAMES:
        out = ROOT / "data" / f"vv{game}_translations_feature.json"
        out.write_text(json.dumps(row(game, digest), indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
                       newline="\n")
        print("wrote", out.relative_to(ROOT), digest)


if __name__ == "__main__":
    main()
