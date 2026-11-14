"""Write the five "Children Play Tag and Build Sandcastles" rows (the owner, 2026-11-14: "children should be able to
play tag and build sandcastles in VV1-VV4."; "don't need any art for sandcastles. but the children should build
sandcastles near the ocean in each game if they don't already do that."; tag is a normal play choice like
sandcastles, and The Lost Children's and New Believers' own tag comes up as often; "all children should participate
in tag. Same rules as VV2 or whatever games have them natively. Same for making sandcastles.").

THE STOCK GAMES (research/stock-executables, capstone, 2026-11-14):
  * Each game picks a child's pastime in one routine, called from the villager's life tick for a child (age below
    0x118) with nothing to do: A New Home 0x4479B0 (0x448299), The Lost Children 0x45EE00 (0x4618C9), The Secret City
    0x45B9B0 (0x45C16A; also 0x45BDC9 and the "Whee! What a fun potion!" effect 0x4269C9), The Tree of Life 0x465260
    (0x4658D7), New Believers 0x46E3F0 (0x46F125).  Each first gives nothing 16 times in 100.
  * Tag: The Lost Children 0x455CF0 (its pick's rand(17) case 9, then rand(100) < 5: 0.84 x 1/17 x 5% = 0.25% of a
    pick); every child in use, under 14, alive, not sick and with empty hands joins, at least two; New Believers
    behaviour 0xEE -> 0x454400 (rand(14) case 11, then 5%; the recruiter 0x4710B0: 80% each, up to three in four).
    A New Home has no tag; The Secret City and The Tree of Life have only its strings (0x190/0x191, 0x1EB/0x1EC),
    never used.
  * Sandcastles: The Secret City action 0xC3 -> 0x44DE40 and The Tree of Life action 0x61 -> 0x4576F0, both on the
    beach at the ocean, one child, blocked for a child who dislikes Playing (word 0x12); A New Home and The Lost
    Children have none; New Believers registers 0x6A -> 0x45F0B0 but never starts it (and has no ocean).

THE CHANGE: "VVFP Children Play.dll" (native/vvfp_children_play) points every call of the pastime pick at its own
pick: a child who dislikes Playing (and A New Home's Golden Child) gets the stock pick; otherwise rand(15): 0 tag,
1 sandcastles where the game gets them, else the stock pick.  tests/test_children_play.py runs it by emulation.

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_children_play.ps1) and pins it
by SHA-256 in all five rows.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLL_NAME = "VVFP Children Play.dll"
DLL = ROOT / "assets" / "children_play" / DLL_NAME
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)"
STOCK = ROOT / "research" / "stock-executables"
EXE = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}

PICK = {1: 0x4479B0, 2: 0x45EE00, 3: 0x45B9B0, 4: 0x465260, 5: 0x46E3F0}
SITES = {1: (0x448299,), 2: (0x4618C9,), 3: (0x45C16A, 0x45BDC9, 0x4269C9), 4: (0x4658D7,), 5: (0x46F125,)}

NAMES = {
    1: "Children Play Tag and Build Sandcastles",
    2: "Children Build Sandcastles (and Tag More Often)",
    3: "Children Play Tag",
    4: "Children Play Tag",
    5: "Children Play Tag More Often",
}

COMMON_TAIL = (
    " **On by default.** **Needs no other patch.** **Works the same with every other patch and in every population "
    "mode.** **Children play only while the game runs, as in the stock game: nothing happens while it is closed.** "
    "**Not yet seen in a running game** (checked by emulation of the stock executable). The companion is "
    "\"VVFP Children Play.dll\", started by VVFP Startup.dll; saves are never written by it."
)
SLOT = ("Each time a child picks something to play, one roll of 1 to 15 decides: ")

DESCRIPTIONS = {
    1: ("Children play tag and build sandcastles on the beach, two new play choices taken from the later games. "
        + SLOT + "1 is tag, 2 is sandcastles, anything else the child's usual choices with their usual odds; a "
        "child playing tag or building sandcastles is 1 pick in 15 each. **Tag** (The Lost Children's own rule): "
        "every child who is not sick and has empty hands joins, the child who started is \"It\", and they run "
        "around the village centre; it needs at least two children, otherwise the child picks as usual. Running "
        "only: A New Home has no picture of a child in the air, so there are no hops. **Sandcastles** (The Secret "
        "City's own play): one child goes to the south beach at the water and bends over in the sand, six times. "
        "The words are the later games' own (Playing tag, Playing tag - \"It\", Making sandcastles) "
        "and can be translated. **The Golden Child keeps his own choices**, but he joins a game "
        "of tag like any child." + COMMON_TAIL),
    2: ("Children build sandcastles on the west beach, a new play choice taken from The Secret City, and play the "
        "game's own tag as often. " + SLOT + "1 is the game's own tag, 2 is sandcastles, anything else the "
        "child's usual choices with their usual odds; each is 1 pick in 15 (the game's own tag, about "
        "1 pick in 400 for a child who does not like playing, stays as well). **Tag** is the game's own: "
        "every child who is not sick and has empty hands joins when at least two can. **Sandcastles**: one "
        "child goes to the beach by the sea and bends over in the sand, six times, \"Making sandcastles\" (The Secret City's words, can be translated). **A child who "
        "dislikes playing never starts either one**, as the later games do for sandcastles." + COMMON_TAIL),
    3: ("Children play tag, a new play choice using the game's own unused \"Playing tag\" words. " + SLOT + "1 "
        "is tag, anything else the child's usual choices with their usual odds (sandcastles on the beach are the "
        "game's own and unchanged): tag is 1 pick in 15, also when the \"Whee! What a fun potion!\" makes a child "
        "pick at once. **The Lost Children's tag rule**: every child who is not sick, has empty hands and does not "
        "dislike playing joins, the child who started is \"It\", and they run together through the places the "
        "game's own \"Running around\" uses; it needs at least two children, otherwise the child picks as usual. "
        "**The Tribal Chief never joins.** **A child who dislikes playing never starts or joins it.** While "
        "playing, the game counts the children as \"Running around\"." + COMMON_TAIL),
    4: ("Children play tag, a new play choice using the game's own unused \"Playing tag\" words. " + SLOT + "1 "
        "is tag, anything else the child's usual choices with their usual odds (sandcastles on the beach are the "
        "game's own and unchanged): tag is 1 pick in 15. **The Lost Children's tag rule**: every child who is not "
        "sick, has empty hands and does not dislike playing joins, the child who started is \"It\", and they run "
        "together through the places the game's own \"Running around\" uses; it needs at least two children, "
        "otherwise the child picks as usual. **A child who dislikes playing never starts or joins it.** While "
        "playing, the game counts the children as \"Running around\"." + COMMON_TAIL),
    5: ("Children play the game's own tag as often as any other play choice. " + SLOT + "1 is the game's own "
        "tag, anything else the child's usual choices with their usual odds: tag is 1 pick in 15 instead "
        "of at most about 1 in 330 (the game's own chance stays too). Who joins is the game's own rule "
        "(each child 4 times in 5, up to three in four of the children, at least two). **A child who "
        "dislikes playing never starts it.** New Believers has no ocean, so it gets no sandcastles." + COMMON_TAIL),
}

BEHAVIOR = {
    1: ["The pastime pick's call (0x448299 -> 0x4479B0) goes to the companion. Unless the child is the Golden Child "
        "(+0x36C = 0xC7), rand(15) (the game's 0x402F10): 0 is tag, 1 sandcastles, else the stock pick.",
        "Tag (the port of The Lost Children's 0x455CF0): the players are every record in use (+0x28), under 0x118 "
        "(+0x348), alive (+0x344 > 0), not sick (+0x354 = 0) and with empty hands (+0x3C = 0x13), and the starter; "
        "with fewer than two the stock pick runs. Each player is stopped (0x439470) and given \"Playing tag\" (the "
        "starter 'Playing tag - \"It\" ') in +0x314, then four rounds of the queue 0x4399F0: step 3 to "
        "845..964 by 659..778 at speed 150 and step 5 for 10..13.",
        "Sandcastles (the port of The Secret City's 0x44DE40): \"Making sandcastles\" in +0x314; one of three stock "
        "\"Cleaning up the beach\" places (480..591 x 1503..1557, 600..711 x 1530..1614, 369..480 x 1452..1539); six "
        "rounds of step 3 there at speed 100, one time in five step 2 kind 0 for 5..14, and twice step 2 kind 1 "
        "(the bent-over picture, state 1) for 10..29."],
    2: ["The pastime pick's call (0x4618C9 -> 0x45EE00) goes to the companion. Unless the child dislikes Playing "
        "(word 0x12 in +0x6E8, 62 slots), rand(15) (0x4031A0): 0 the stock tag 0x455CF0 (its own players and its "
        "own fallback when fewer than two), 1 sandcastles, else the stock pick.",
        "Sandcastles (the port of The Secret City's 0x44DE40): \"Making sandcastles\" in +0x4FC; one of the three "
        "stock \"Relaxing at the beach\" places nearest the sea (217..256 x 878..917, 142..181 x 878..917, 145..184 x "
        "752..791); six rounds of queue 0x449B70 step 3 there at speed 100, one time in five step 2 kind 0, and twice "
        "step 2 kind 1 (state 1, bent over) for 10..29."],
    3: ["The pastime pick's three calls (0x45C16A, 0x45BDC9, 0x4269C9 -> 0x45B9B0) go to the companion. Unless the "
        "child dislikes Playing (0x12 in +0xFC0), rand(15) (0x4032D0): 0 tag, else the stock pick.",
        "Tag: the players are every record in use (+0xF10), alive, under 0x118, not sick (+0xE89), hands empty "
        "(+0xF20 = -1), not disliking Playing and not the Tribal Chief (+0xE80), and the starter; with fewer than "
        "two the stock pick runs. Each player: stop 0x460F70, do-action 0x455570 \"Running around\" (0x94), stop "
        "again, string 0x190 (the starter 0x191) through 0x42F190 into +0xF28 (0x46F780, 39 bytes), six walks "
        "0x4611B0 at speed 150 through the six places of \"Running around\" (0x4444B0) in one order shared by the "
        "players, its last step 0x461B50(1, 0, 1, 0), and the queue started (0x461BF0)."],
    4: ["The pastime pick's call (0x4658D7 -> 0x465260) goes to the companion. Unless the child dislikes Playing "
        "(0x12 in +0x1E6C), rand(15) (0x4036D0): 0 tag, else the stock pick.",
        "Tag: the players are every record in use (+0x1CC4), not a body (+0x1CC7), alive, under 0x118, not sick "
        "(+0x1C48), hands empty (+0x1CDC = -1) and not disliking Playing, and the starter; with fewer than two the "
        "stock pick runs. Each player: stop 0x468C60, do-action 0x45DEC0 \"Running around\" (0x46), stop again, "
        "string 0x1EB (the starter 0x1EC) through 0x44D3D0 into +0x1CE4 (0x4724E0, 39 bytes), six walks 0x469050 at "
        "speed 150 through the six places of \"Running around\" (0x450F10) in one order shared by the players, its "
        "last step 0x469EC0(1, 4, 1, 0.0), and the queue started (0x46A030)."],
    5: ["The pastime pick's call (0x46F125 -> 0x46E3F0) goes to the companion. Unless the child dislikes Playing "
        "(0x12 in +0x1F68), rand(15) (0x403660): 0 the stock tag slot without its 5% roll (0x46E705..0x46E769: the "
        "recruiter 0x4710B0(0xEE, 80, 0, 0x117, -1, &joined, 2, children x 75 / 100) on the villager manager, then "
        "behaviour 0xEE through 0x465580 when more than one joined), else the stock pick."],
}

NON_CHANGES = [
    "No executable byte is patched: the companion replaces the call(s) at run time, only after verifying every one "
    "is the stock call; all are written or none.",
    "The stock pick, its choices and their odds among themselves are unchanged; a child who dislikes Playing gets "
    "it exactly as stock.",
    "Nothing is written to a save, a file or a villager record except through the game's own stop, action, queue "
    "and string copy (and, in A New Home and The Lost Children, the Details text buffer the game's own string copy "
    "fills, bounded to it).",
]


SAVE_SAFETY = {
    3: "The action The Secret City records for a tag player (+0xF24) is the stock \"Running around\" (0x94), set by "
       "the game's own do-action; the save keeps only the record's window +0xDC4..+0xEC4 (the writer 0x45EF80), so "
       "neither the action, the tag text (+0xF28) nor the queue is ever saved.",
    4: "The action The Tree of Life records for a tag player (+0x1CE0) is the stock \"Running around\" (0x46), set "
       "by the game's own do-action; its readers (0x42EB09, 0x42F211, 0x42F266, 0x42F2D9, 0x42F330, 0x436897, "
       "0x43A5EB, 0x46788F) test only other actions. The save keeps only the record's windows (0x45DB30: +0x1B8C, "
       "+0x1C34, +0x1C5C and the likes and dislikes), so neither the action, the tag text (+0x1CE4) nor the queue is "
       "ever saved; a load resets them (0x45D8A0).",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def stock_call(game: int, va: int) -> str:
    rel = (PICK[game] - (va + 5)) & 0xFFFFFFFF
    expect = bytes([0xE8]) + struct.pack("<I", rel)
    exe = STOCK / f"Virtual Villagers - {EXE[game]}.exe"
    if exe.is_file():
        data = exe.read_bytes()
        assert data[va - 0x400000:va - 0x400000 + 5] == expect, (game, hex(va))
    return expect.hex().upper()


def row(game: int, dll_sha: str) -> dict:
    return {
        "id": f"vv{game}_children_play",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": NAMES[game],
        "description": DESCRIPTIONS[game],
        "output_tag": NAMES[game],
        "dependencies": [],
        "behavior_changes": BEHAVIOR[game],
        "explicit_non_changes": NON_CHANGES + ([SAVE_SAFETY[game]] if game in SAVE_SAFETY else []),
        "evidence_status": ("the stock pastime picks, tag and sandcastle routines traced statically; the companion's "
                            "install, its odds over many picks, who plays and where, emulated on the rendered "
                            "executable in tests/test_children_play.py; runtime/player confirmation pending"),
        "companion_files": [
            {"source": f"assets/children_play/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
        "runtime_detours": [
            {"va": f"0x{va:X}", "stock_bytes": stock_call(game, va), "written_bytes": "E8XXXXXXXX",
             "routine": f"a call of the child pastime pick 0x{PICK[game]:X} goes to the companion's pick, which adds "
                        "tag and sandcastles as normal play choices and otherwise calls it",
             "installed_by": INSTALLED_BY}
            for va in SITES[game]
        ],
    }


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_children_play.ps1")], check=True)
    dll_sha = sha(DLL)
    for game in range(1, 6):
        out = ROOT / "data" / f"vv{game}_children_play_feature.json"
        out.write_text(json.dumps(row(game, dll_sha), indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
