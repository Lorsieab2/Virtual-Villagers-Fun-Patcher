"""Generate data/vv1_storytelling_feature.json and data/vv2_storytelling_feature.json.

Dropping an adult on a child tells a story, as in the later games.  In both
games the drop gives the villager under the mouse "Waiting for someone" and
the dropped villager "Embracing", whose pairing step then looks for its
partner again by proximity around the dropped villager's own (offset)
position -- so the drop often finds nobody or someone else, and the child is
never told a story (The Lost Children's own storytelling sits behind that
second search).  "VVFP Storytelling.dll" (native/vvfp_storytelling) replaces
those two calls in the drop handler, for an 18+ adult dropped on a living
child under 18: The Lost Children runs its own story routines on the pair,
A New Home the same steps in its own step types.

No executable byte is patched by either row: "VVFP Startup.dll" starts the
DLL as the game opens and it installs its detour only after verifying the
stock bytes.  The DLL is pinned by SHA-256, so re-run this after every
rebuild.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "assets" / "storytelling" / "VVFP Storytelling.dll"
NAME = "Dropping an Adult on a Child Tells a Story"

COMMON_TAIL = (
    "Only your own drop does this: villagers never start a story by themselves, and dropping an "
    "adult on an adult, a child on anyone, or a 14-17 year old on a child works exactly as before. "
    "A dead child, or a sick one (who is sent for healing, as before), gets no story. "
    "**Needs no other patch.**"
)

ROWS = {
    "vv1": {
        "description": (
            "When you drop an adult (18 or older) on a child (under 18), the adult now tells the child a "
            "story instead of trying to embrace, as in the later Virtual Villagers games. The adult and the "
            "child first walk together to the centre of the village; there the adult shows \"Telling a "
            "story\" and tells it with the researching animation (without the research sound), and each "
            "story gives the adult one ordinary Breeding practice roll (A New Home's name for Parenting), "
            "with the game's own chance and amount. The child shows \"Listening to a story\" and listens "
            "until the story is over. " + COMMON_TAIL
        ),
        "behavior_changes": [
            "In the drop handler's villager-on-villager case, where the stock game gives the villager under the mouse \"Waiting for someone\" (0x425291: 0x4454B0) and the dropped villager \"Embracing\" (0x4252B9: 0x445510), a drop of a villager aged 18 or older (age 360+) on a villager who is alive (health above 0) and under 18 (age below 360, age 0 included) tells a story instead, to that very villager; the handler then continues after its villager-on-villager case (0x4252BE).",
            "The story's spot is picked in the box the game's own \"Going to village center\" uses (0x447AD8: x 3*(rand(0x50)+0x106), y 3*(rand(0x50)+0xC8)), x narrowed to 3*(rand(0x40)+0x106) so the child's spot, 0x30 to the right, stays inside it (the owner, 2026-11-17, skill practice item 24: the child and the adult walk to the centre of the village).",
            "The child's steps are cleared and it gets the label \"Listening to a story\" (written in the game's language: English, German, Spanish or French), a walk to its spot (step 3, the game's normal speed 0x64, which the game raises for children), a turn to face the adult (step 15, 2/2), two standing waits of 10-19 and 13-22, the lengths The Lost Children's listener (0x44A0E0) waits, and one more of 15-24 while the adult, who walks more slowly, finishes.",
            "The adult's steps are cleared and it gets the game's own \"Telling a story\" label (string 0xA7), a walk to the spot (step 3, speed 0x64), a turn to face the child (step 15, 1/1) and the story told with the researching animation -- step 7, the gesture Researching (0x442C10) shows -- for the same lengths as before: gesture 3, gesture 3-10, gesture 3-5, one Breeding practice (step 6, skill 2: 0x43D440, the stock chance, amount and failure handling), gesture 3-10, gesture 3-7. Researching's sound is a step of its own (0x12, a looping emitter) and is never queued; nothing of Researching's tech points or lab accident (step 0xE) is copied.",
        ],
        "explicit_non_changes": [
            "This row changes no executable bytes: \"VVFP Startup.dll\" starts the DLL as the game opens, and it detours 0x425291 only after verifying those nine bytes and the first bytes of every routine a story calls; a different build of the game installs nothing.",
            "Every other drop keeps its stock result, refusal messages included: adult on adult (embracing, conception and every Birth Control or Manual Drop-Breeding rule), a 14-17 year old dropped on a child, a child dropped on anyone, a dead villager, and a sick one (healing).",
            "Villagers pairing up on their own, and catch-up, never pass through the drop handler.",
            "No skill other than the adult's Breeding practice roll changes, the child gains nothing, and nothing is counted or logged: no Virtual Villagers game counts or logs stories or listening.",
        ],
        "detour": {"va": "0x425291", "stock_bytes": "8B4E2057E816020200",
                   "routine": "the village input handler's drop of the held villager on another villager (0x4251FF..0x4252BE): the \"Waiting for someone\" call"},
    },
    "vv2": {
        "description": (
            "When you drop an adult (18 or older) on a child (under 18), the adult now always tells that "
            "child a story, as in the later Virtual Villagers games. The Lost Children has storytelling "
            "of its own, but its drop starts an embrace and only finds its way to the story when the "
            "embrace's own second search happens to find the same child, so dropping usually just "
            "embraced. Now the adult shows \"Telling a story\" and each story gives one ordinary "
            "Parenting practice roll; the child shows \"Listening to a story\", and a playing child "
            "nearby may join in -- all of it the game's own storytelling. As in the game's own code, an "
            "adult with Parenting 50 or more shows \"Teaching children\" instead. " + COMMON_TAIL
        ),
        "behavior_changes": [
            "In the drop handler's villager-on-villager case, where the stock game gives the villager under the mouse \"Waiting for someone\" (0x430F2D..0x430F3A: 0x4492A0, 0x45D4B0) and the dropped villager \"Embracing\" (0x430F5E: 0x45D510), a drop of a villager aged 18 or older (age 360+) on a villager who is alive (health above 0) and under 18 (age below 360, age 0 included) runs the game's own storytelling for that pair instead, exactly as its pairing step does (0x44F9B0..0x44FA7F): the child's steps are cleared and it listens (0x44A0E0, \"Listening to a story\"); the adult's steps are cleared and it tells a story (0x449F40, \"Telling a story\": one Parenting practice roll), or from Parenting 50 teaches children (0x44A4E0); after a story, the first-story tip (0x1C2) is shown once, and each other playing child under 14 has a 25% chance to listen too. The handler then continues after its villager-on-villager case (0x430F63).",
        ],
        "explicit_non_changes": [
            "This row changes no executable bytes: \"VVFP Startup.dll\" starts the DLL as the game opens, and it detours 0x430F2D only after verifying those nine bytes and the first bytes of every routine a story calls; a different build of the game installs nothing.",
            "The story, listening and teaching routines, their walks, waits, practice roll and the dislike of children are the game's own and unchanged.",
            "Every other drop keeps its stock result, refusal messages included: adult on adult (embracing, conception and every Birth Control or Manual Drop-Breeding rule), a 14-17 year old dropped on a child, a child dropped on anyone, a dead villager, and a sick one (healing).",
            "Villagers pairing up on their own, and catch-up, never pass through the drop handler.",
            "Nothing is counted or logged: no Virtual Villagers game counts or logs stories or listening.",
        ],
        "detour": {"va": "0x430F2D", "stock_bytes": "8B4E2053E86A830100",
                   "routine": "the village input handler's drop of the held villager on another villager (0x430E15..0x430F63): the target's step clear before \"Waiting for someone\""},
    },
}


def main() -> None:
    sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
    for game, row in ROWS.items():
        detour = dict(row["detour"], installed_by="VVFP Storytelling.dll, VvfpStartup")
        manifest = {
            "id": f"{game}_storytelling",
            "enabled": True,
            "catalog_enabled": True,
            "catalog_hidden": False,
            "game_id": game,
            "name": NAME,
            "description": row["description"],
            "output_tag": "Storytelling",
            "behavior_changes": row["behavior_changes"],
            "explicit_non_changes": row["explicit_non_changes"],
            "evidence_status": "static exact-build verification of the drop handler, the hit test, the pairing step's second search and the story routines; the player's drop is emulated through the game's own drop handler, step queue and routines with the companion in tests/test_storytelling.py; runtime/player confirmation pending",
            "runtime_detours": [detour],
            "companion_files": [
                {
                    "source": "assets/storytelling/VVFP Storytelling.dll",
                    "destination": "VVFP Storytelling.dll",
                    "sha256": sha,
                },
            ],
            "patches": [],
        }
        out = ROOT / "data" / f"{game}_storytelling_feature.json"
        out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote", out.relative_to(ROOT), sha)


if __name__ == "__main__":
    main()
