"""Generate the two "Difficulty Settings" rows (The Tree of Life, New Believers).

A New Home, The Lost Children and The Secret City let the player choose
Easy, Normal or Hard on the Options dialog's Difficulty row.  The Tree of
Life and New Believers still play by the same difficulty -- one saved
game-state field (VV4 +0x170F4, VV5 +0x17D54; 0 Easy, 1 Normal, 2 Hard,
Normal for every village) that The Secret City's rules read -- but their
Options dialog no longer draws the row, and its three click areas lie under
the Game Speed buttons.  These rows put the row back, in The Secret City's
place: directly above Game Speed, which moves down one row.

The behaviour lives in one companion, "VVFP Difficulty.dll"
(native/vvfp_difficulty), started by VVFP Startup.dll, which verifies every
stock byte and rewrites them at run time; the rows patch no executable byte.
The DLL is pinned by SHA-256, so re-run this after every rebuild
(scripts/build_vvfp_difficulty.ps1).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLL_NAME = "VVFP Difficulty.dll"
DLL = ROOT / "assets" / "difficulty" / DLL_NAME
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup"

# What each level changes: the stock rules of The Tree of Life and New
# Believers, read from the executables (the same as The Secret City's).
LEVELS = (
    "Easy: a new village starts with 300 more food; villagers never eat the extra food the other "
    "levels take; a fed, healthy villager tries to regain health on every check instead of about "
    "half of them; and villagers fall sick about a quarter as often.",
    "Normal (a village's level until you change it): above 8,000 food each villager's meal "
    "takes 2 more food three times in four; a starving villager loses health on about three "
    "checks in four.",
    "Hard: a new village starts with 99 less food; each villager's meal takes 2 more food three "
    "times in four at any food level; a starving villager loses health on every check.",
)

GAMES = {
    "vv4": {
        "title": "The Tree of Life",
        "field": "+0x170F4",
        "draw": "0x41A5A0",
        "click": "0x41AD60",
        "height": "0x23C, so its frame is one 64-pixel tile taller (576 pixels on the 800 x 600 screen)",
        "move": "0x40 (64 pixels, the one tile the frame grows by; Difficulty sits 0x48 below Fullscreen and Game Speed 0x48 below Difficulty, as the stock 0x50 spacing does not fit the 600-pixel screen)",
        "row_y": "y+0x145",
        "speed_y": "y+0x18D",
        "strings": "0x534 Difficulty, 0x535 Easy, 0x53A Normal (Game Speed's own), 0x537 Hard",
        "rules": "starting food 0x41F3A3; food use, starvation and healing 0x4684E5..0x4686B0; "
                 "sickness 0x4686B0 and 0x45E938",
        "writes": "0x41B159 / 0x41B187 / 0x41B1B9",
        "hook": ("0x41A906", "8B0D08CB4C00",
                 "the Options drawing (0x41A5A0) where its Game Speed radio buttons are done and "
                 "its heading begins (mov ecx, [0x4CCB08]): the Difficulty row is drawn, then the "
                 "stolen instruction runs and the drawing goes on at 0x41A90C"),
        "sites": [
            ("0x41A07D", "68FC010000", "683C020000", "the dialog's frame (0x419FA0): its height 0x1FC -> 0x23C"),
            ("0x41A109", "2DFC010000", "2D3C020000", "the dialog's vertical centring: its height 0x1FC -> 0x23C"),
            *[(va, "81C14D010000", "81C18D010000", "a Game Speed radio button's top y+0x14D -> y+0x18D")
              for va in ("0x41A747", "0x41A770", "0x41A799", "0x41A7D2", "0x41A80B",
                         "0x41A834", "0x41A871", "0x41A89A", "0x41A8C3", "0x41A8EC")],
            ("0x41A91E", "81C252010000", "81C292010000", "the Game Speed heading y+0x152 -> y+0x192"),
            ("0x41A954", "81C27F010000", "81C2BF010000", "a Game Speed label y+0x17F -> y+0x1BF"),
            ("0x41A984", "81C17F010000", "81C1BF010000", "a Game Speed label y+0x17F -> y+0x1BF"),
            ("0x41A9C1", "057F010000", "05BF010000", "a Game Speed label y+0x17F -> y+0x1BF"),
            ("0x41A9F7", "81C27F010000", "81C2BF010000", "a Game Speed label y+0x17F -> y+0x1BF"),
            ("0x41AD83", "8D9050010000", "8D904F010000",
             "the click handler (0x41AD60): the Difficulty areas' top y+0x150 -> y+0x14F"),
            ("0x41ADCB", "8D9075010000", "8D9074010000",
             "the click handler: the Hard area's bottom y+0x175 -> y+0x174"),
            ("0x41ADE0", "8DB875010000", "8DB874010000",
             "the click handler: the Easy and Normal areas' bottom y+0x175 -> y+0x174"),
            ("0x41ADF1", "8D9057010000", "8D9097010000",
             "the click handler: the Game Speed areas' top y+0x157 -> y+0x197"),
            ("0x41AE2C", "8DB87C010000", "8DB8BC010000",
             "the click handler: the Game Speed areas' bottom y+0x17C -> y+0x1BC"),
        ],
    },
    "vv5": {
        "title": "New Believers",
        "field": "+0x17D54",
        "draw": "0x41ADF0",
        "click": "0x41B5C0",
        "height": "0x27C, so its frame is two 64-pixel tiles taller (640 pixels on the 1024 x 768 screen)",
        "move": "0x64 (100 pixels, the dialog's own spacing between its Fullscreen and Game Speed rows)",
        "row_y": "y+0x161",
        "speed_y": "y+0x1C5",
        "strings": "0x57E Difficulty, 0x57F Easy, 0x584 Normal (Game Speed's own), 0x581 Hard",
        "rules": "starting food 0x4248EB; food use, starvation and healing 0x472DBB..0x472F81; "
                 "sickness 0x472F81 and 0x465F58",
        "writes": "0x41B9B9 / 0x41B9E7 / 0x41BA19",
        "hook": ("0x41B156", "8B0D48C94D00",
                 "the Options drawing (0x41ADF0) where its Game Speed radio buttons are done and "
                 "its heading begins (mov ecx, [0x4DC948]): the Difficulty row is drawn, then the "
                 "stolen instruction runs and the drawing goes on at 0x41B15C"),
        "sites": [
            ("0x41A8D1", "68FC010000", "687C020000", "the dialog's frame (0x41A800): its height 0x1FC -> 0x27C"),
            ("0x41A95B", "2DFC010000", "2D7C020000", "the dialog's vertical centring: its height 0x1FC -> 0x27C"),
            *[(va, "81C161010000", "81C1C5010000", "a Game Speed radio button's top y+0x161 -> y+0x1C5")
              for va in ("0x41AF97", "0x41AFC0", "0x41AFE9", "0x41B022", "0x41B05B",
                         "0x41B084", "0x41B0C1", "0x41B0EA", "0x41B113", "0x41B13C")],
            ("0x41B16E", "81C272010000", "81C2D6010000", "the Game Speed heading y+0x172 -> y+0x1D6"),
            ("0x41B1A4", "81C294010000", "81C2F8010000", "a Game Speed label y+0x194 -> y+0x1F8"),
            ("0x41B1D4", "81C194010000", "81C1F8010000", "a Game Speed label y+0x194 -> y+0x1F8"),
            ("0x41B211", "0594010000", "05F8010000", "a Game Speed label y+0x194 -> y+0x1F8"),
            ("0x41B247", "81C294010000", "81C2F8010000", "a Game Speed label y+0x194 -> y+0x1F8"),
            ("0x41B5E3", "8D9050010000", "8D906B010000",
             "the click handler (0x41B5C0): the Difficulty areas' top y+0x150 -> y+0x16B"),
            ("0x41B62B", "8D9075010000", "8D9090010000",
             "the click handler: the Hard area's bottom y+0x175 -> y+0x190"),
            ("0x41B640", "8DB875010000", "8DB890010000",
             "the click handler: the Easy and Normal areas' bottom y+0x175 -> y+0x190"),
            ("0x41B651", "8D906B010000", "8D90CF010000",
             "the click handler: the Game Speed areas' top y+0x16B -> y+0x1CF"),
            ("0x41B68C", "8DB890010000", "8DB8F4010000",
             "the click handler: the Game Speed areas' bottom y+0x190 -> y+0x1F4"),
            ("0x41AA82", "83E80F", "83E823",
             "the Done button (the constructor): its gap above the frame's bottom 0x0F -> 0x23, The Tree of "
             "Life's own, so it sits clear of the frame's bottom bar"),
        ],
        "done": "The Done button sits 20 pixels higher than in the stock dialog, clear of the frame's "
                "bottom bar as in The Tree of Life (not yet checked in a live game). ",
    },
}


def description(game: dict) -> str:
    return (
        "Puts back the Options dialog's Difficulty choice -- Easy, Normal or Hard -- as A New Home, "
        "The Lost Children and The Secret City have it. " + game["title"] + " already plays by a "
        "difficulty level, saved with each village (a village starts on Normal), and its rules are The "
        "Secret City's, but its Options dialog never shows the choice. With this patch the Difficulty "
        "row is drawn where The Secret City has it, directly above Game Speed, with the game's own "
        "radio buttons, words and font; Game Speed moves down a row and the dialog's frame grows by "
        "whole tiles, so the whole dialog stays on the screen with everything in it where it was. "
        "The choice is saved with the village. "
        + game.get("done", "")
        + " ".join(LEVELS) + " "
        "**The starting food only changes for a village made after you pick the level; the other "
        "rules follow the level at once.** "
        "**Needs no other patch; it works the same with every other patch and in every population "
        "mode.** "
        "**Checked in a live game, windowed: the row's layout, every button, and the chosen level after "
        "a save and reload. Clicks in fullscreen have not been tried in a live game.** "
        "It is on by default; untick it to keep the stock dialog (a village then keeps the level it "
        "has). The companion is \"" + DLL_NAME + "\", started by VVFP Startup.dll; if the DLL "
        "cannot be loaded, the stock dialog is shown."
    )


def row(game_id: str, sha: str) -> dict:
    game = GAMES[game_id]
    hook_va, hook_stock, hook_routine = game["hook"]
    return {
        "id": f"{game_id}_difficulty_settings",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": game_id,
        "name": "Difficulty Settings",
        "description": description(game),
        "output_tag": "Difficulty",
        "dependencies": [],
        "behavior_changes": [
            f"The Options dialog (drawing {game['draw']}, clicks {game['click']}) shows a Difficulty "
            f"row at {game['row_y']}: the heading and three radio buttons with Easy, Normal and Hard "
            f"(strings {game['strings']}), the selected one the village's level (game-state field "
            f"{game['field']}).",
            f"Game Speed's buttons, heading, labels and click areas move down {game['move']}, to "
            f"{game['speed_y']}; the dialog's height becomes {game['height']}; the frame, the Done "
            "button and the Music Tracks checkboxes are placed by the game from the frame, and the "
            "rows from the frame's top + 2 as in the stock dialog, so nothing else moves against them.",
            f"The stock handler's own three Difficulty click areas ({game['writes']} write 0, 1, 2) "
            "move onto the new row's buttons, with the Game Speed buttons' insets; no click near Game "
            "Speed changes the level any more.",
            f"The level's effects are the stock game's own ({game['rules']}): " + " ".join(LEVELS),
        ],
        "explicit_non_changes": [
            f"This row changes no executable bytes: {DLL_NAME} verifies every stock byte it rewrites "
            "and writes them at run time; a different build of the game installs nothing.",
            "No save byte, file or villager is written by the companion: the level is the stock "
            "field, written only by the game's own click handler and saved by the game's own save.",
            "What each level does is unchanged: these are the stock rules, which already run on "
            "Normal in every village.",
            "Every other row of the dialog (sound, music, voiceovers, music tracks, fullscreen) is "
            "drawn and clicked exactly as before.",
        ],
        "companion_files": [
            {
                "source": f"assets/difficulty/{DLL_NAME}",
                "destination": DLL_NAME,
                "sha256": sha,
            },
        ],
        "patches": [],
        "runtime_detours": [
            *[
                {
                    "va": va,
                    "stock_bytes": stock,
                    "written_bytes": written,
                    "routine": routine,
                    "installed_by": INSTALLED_BY,
                }
                for va, stock, written, routine in game["sites"]
            ],
            {
                "va": hook_va,
                "stock_bytes": hook_stock,
                "written_bytes": "E9XXXXXXXX90",
                "routine": hook_routine,
                "installed_by": INSTALLED_BY,
            },
        ],
    }


def main() -> None:
    sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
    for game_id in GAMES:
        out = ROOT / "data" / f"{game_id}_difficulty_settings_feature.json"
        out.write_text(json.dumps(row(game_id, sha), indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote", out.relative_to(ROOT), sha)


if __name__ == "__main__":
    main()
