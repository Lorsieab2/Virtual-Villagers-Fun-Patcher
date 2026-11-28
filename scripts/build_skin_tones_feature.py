"""Write the "Skin Tones" rows: data/vv3_skin_tones_feature.json, vv4_..., vv5_... (the owner, 2026-11-06 and
2026-11-26: "implement the skin tone mod in all 5 games!! with inheritance and mixing").

The row ships "VVFP Skin Tones.dll" (native/vvfp_skin_tones), started by VVFP More Companions.dll from the third word
of companions (native/shared/startup_companions_3.h).  The DLL keeps each villager's tone in the save's own Skin
Tones file, hands it down by the games' head rule, and draws each villager from that tone's copy of the head and
body sheets.  Those copies are made at patch time from the player's own pictures (src/vv_skin_tone_art.py,
vv_fun_patcher._write_skin_tone_sheets): the game's art is never shipped.

A New Home and The Lost Children have no row yet: the DLL keeps their tones but does not draw them, and the owner
wants all five games, so the feature is not for release until they draw too.  Off in every set of defaults until the
owner decides.

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_skin_tones.ps1) and pins it by
SHA-256 in the rows.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_skin_tones  # noqa: E402

NAME = "Skin Tones"
DLL_NAME = "VVFP Skin Tones.dll"
DLL = ROOT / "assets" / "skin_tones" / DLL_NAME
SOURCE = ROOT / "native" / "vvfp_skin_tones" / "vvfp_skin_tones.c"
GAMES = (3, 4, 5)
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP More Companions.dll, third word)"
STOCK = {3: "Virtual Villagers - The Secret City.exe", 4: "Virtual Villagers - The Tree of Life.exe",
         5: "Virtual Villagers - New Believers.exe"}


# The owner's note on the head rule's 1-in-20 "any tone" (2026-11-28: "handwave it as real-life genetics; perhaps the
# parents had an ancestor with different genes. no real life offense/controversy intended (put that message)").
ANCESTOR_NOTE = (
    "Now and then (about 1 baby in 20) a baby's skin tone is quite different from both parents', just as in real "
    "life, where a family may carry genes from an ancestor long ago. This is only for fun and variety; no real-life "
    "offense or controversy is intended.")


def row_id(game: int) -> str:
    return f"vv{game}_skin_tones"


def _stock_bytes(game: int, va: int, count: int) -> str:
    """The stock executable's bytes at a site (research/stock-executables; the DLL checks the same bytes)."""
    import pefile
    pe = pefile.PE(str(ROOT / "research" / "stock-executables" / STOCK[game]), fast_load=True)
    return pe.get_data(va - pe.OPTIONAL_HEADER.ImageBase, count).hex().upper()


def sites(game: int) -> list[tuple[int, int, str]]:
    """(va, bytes replaced, what it is) of each site, read from the DLL's own tables."""
    text = SOURCE.read_text(encoding="utf-8")
    if game == 3:
        entry = int(re.search(r"#define VV3_VILLAGE_DRAW 0x([0-9A-F]+)u", text).group(1), 16)
        thunk = int(re.search(r"#define VV3_DRAW_THUNK 0x([0-9A-F]+)u", text).group(1), 16)
        return [(entry, 5, "the entry of the village's draw of a villager's head or body (the sheet is its first "
                           "argument)"),
                (thunk, 7, "the entry of the draw thunk the Villager Details portrait and an island event's figure "
                           "call (the sheet is its first argument)")]
    body = text[text.index(f"static const st_draws VV{game}_DRAWS = {{"):]
    body = body[:body.index("};")]
    heads, bodies = re.findall(r"\{ (0x[0-9A-F]+u, 0x[0-9A-F]+u, 0x[0-9A-F]+u) \}", body)
    where = ("the village's draw", "the small figure", "the Villager Details big figure")
    out = []
    for part, group in (("head", heads), ("body", bodies)):
        for place, va in zip(where, group.split(", ")):
            out.append((int(va[:-1], 16), 5, f"the call of the {part} sheet fetcher in {place}"))
    return out


def description() -> str:
    tones = ", ".join(vv_skin_tones.tone_name(n) for n in range(1, vv_skin_tones.TONE_COUNT + 1))
    return (
        f"Gives every villager one of ten skin tones ({tones}) and draws them with it in the village, on Villager "
        "Details and in island event pictures. **Babies inherit their tone the way they inherit their heads** (the "
        "owner, 2026-11-28: \"like head inheritance\"): about 19 babies in 20 get a tone between the two parents' "
        "tones (their average, give or take one step); twins and triplets copy the first baby; with only one parent "
        "known, that parent's tone counts for both. " + ANCESTOR_NOTE + " Founders and arrivals get any tone, and so "
        "does everyone already in a village the first time it is loaded with this patch. The tone a baby will have "
        "is decided from the parents named in its record. The tones are made when you patch, from your own game's pictures: ten copies "
        "of each head and body sheet are added to the patched game's Images folder (files named vvfp_skin_...), "
        "which takes a few minutes the first time. The game's own pictures are never changed, hair, eyes, clothes "
        "and masks keep the game's own colours, and patching without this patch leaves the copies out. Each "
        "villager's tone is kept in the save's own Skin Tones file and follows them through deaths, reloads and "
        "renames; Back Up Saves copies it and Start Over clears it. **Not there yet:** choosing a tone in Change "
        "Appearance; and the memorial list's figures, the parents' small figures on Villager Details and the baby a "
        "parent holds keep the game's own art. **Off by default, in Owner's Defaults and in Select All.** **Works "
        "the same with every other patch and in every population mode.** **Not yet seen in a running game** (checked "
        f"by emulation of each game's own draw code). The companion is \"{DLL_NAME}\", started by VVFP More "
        "Companions.dll; nothing is written into a save or a villager record."
    )


def row(game: int, dll_sha: str) -> dict:
    return {
        "id": row_id(game),
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": NAME,
        "description": description(),
        "output_tag": "Skin Tones",
        "dependencies": [],
        "behavior_changes": [
            f"\"{DLL_NAME}\" keeps one tone (1..{vv_skin_tones.TONE_COUNT}, or {vv_skin_tones.TONE_GAMES_OWN}: the "
            "game's own art chosen) and one birth tone for every held villager in \"Virtual Villagers Fun Patcher\\"
            "Save <S>\\Data\\Skin Tones\\Skin Tones - Save <S>.dat\" (the Head Looks' store, magic 'VST2', two bytes "
            "a villager), following each villager by identity.",
            "Whenever the village on screen is known, every held villager with no tone is given one, the oldest "
            "first: with a parent named in the record, the games' head rule on the tone numbers (rand(100) >= 5 and "
            "a parent known: (father + mother) / 2 + rand(3) - 1, kept within 1..10; else any tone), a missing "
            "parent counting as the other; a second baby of the same pregnancy copies the first; anyone else any "
            "tone. Every roll is the companion's own generator: the game's rand() sequence is not disturbed.",
            "At each site below the sheet about to be drawn from is changed to the villager's tone's copy of it "
            "(\"vvfp_skin_<NN>_<the game's own file name>\" in Images), loaded the first time it is needed and only "
            "when every file of it is there; otherwise the game's own sheet is drawn.",
            "At patch time the patcher makes those copies from the pictures in the patched game's own Images folder "
            "(src/vv_skin_tone_art.py): each skin pixel takes the tone's hue and its own shading; every pixel "
            "outside the skin is byte for byte the game's. \"vvfp-skin-tones.json\" there records what they were "
            "made from, so patching again does not make them again.",
        ],
        "explicit_non_changes": [
            "No executable byte is patched: the companion splices its sites at run time, only after verifying every "
            "one holds its stock bytes; all are written or none (a different build installs none, and then every "
            "villager is drawn with the game's own art).",
            "No picture of the game is changed or replaced, and none is shipped: only new files are added.",
            "The villager record and the save are never written. Nothing depends on a villager's sex.",
            "Masks, skeletons and every sheet that is not a villager's head or body sheet are never changed.",
        ],
        "evidence_status": "each game's draw routines read statically; the splices emulated on the stock "
                           "executables in tests/test_skin_tone_draws.py and the inheritance in "
                           "tests/test_skin_tones.py; runtime/player confirmation pending",
        "companion_files": [
            {"source": f"assets/skin_tones/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
        "runtime_detours": [
            {"va": f"0x{va:06X}", "stock_bytes": _stock_bytes(game, va, count), "routine": what,
             "installed_by": INSTALLED_BY}
            for va, count, what in sites(game)
        ],
    }


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_skin_tones.ps1")], check=True)
    dll_sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
    for game in GAMES:
        out = ROOT / "data" / f"{row_id(game)}_feature.json"
        out.write_text(json.dumps(row(game, dll_sha), indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
                       newline="\n")
        print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
