"""Write the island events' content controls (v1.35.97, the owner 2026-11-15), one set of rows per game:

  * vvN_island_event_content_notes  -- Content Notes for Island Events (on in Owner's Defaults, off elsewhere);
  * vvN_island_event_filter_fNN     -- the 28 content filters F01-F28 (off everywhere, Owner's Defaults too).

No executable byte and no file of their own: each row is a name in "VVFP Installed Patches.txt" (the patcher writes
every installed row there), which Story / Cheat Upgrades reads.  The new events carry what to do with each
(src/vv_event_content.py writes it into every compiled event); the game's own events are never touched.  The patcher
shows them in each game's Island Events section (src/vv_fun_patcher_gui.py).

    python scripts/build_island_event_content_features.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_event_content as content  # noqa: E402

GAMES = (1, 2, 3, 4, 5)
UNVERIFIED = "**Unverified in play: the effect has not been tested live.**"


def needs_on(game: int) -> list[dict]:
    return [{"id": f"vv{game}_isola_grand_event_collection", "for": "the new island events it acts on"}]


def row(game: int, ident: str, name: str, description: str, changes: list[str]) -> dict:
    return {
        "id": f"vv{game}_{ident}",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": name,
        "description": description,
        "output_tag": name,
        "dependencies": [],
        "needs_on": needs_on(game),
        "conflicts": [],
        "behavior_changes": changes,
        "explicit_non_changes": [
            "No executable byte, game file or save is changed: the row is only a name in the installed patches' list "
            "(\"VVFP Installed Patches.txt\") that Story / Cheat Upgrades reads.",
            "The game's own island events, their text and their chances are never changed: it acts on the added "
            "events only.",
        ],
        "evidence_status": "the compiled events' conditions and effects pinned in tests/test_event_content.py; "
                           "runtime/player confirmation pending",
        "companion_files": [],
        "patches": [],
        "runtime_detours": [],
    }


def notes_row(game: int) -> dict:
    labels = ", ".join(content.NOTE_LABELS)
    return row(game, content.NOTES_PATCH, "Content Notes for Island Events",
               "Before the main text of a new island event that may touch a sensitive subject, a short note names it, "
               "for example \"Content note: Bereavement\". It never says which outcome will come. The labels are: "
               f"{labels}. A subject the content filters below have removed from that event is left out of its note. "
               "New events only (the Isola Grand Event Collection's); the game's own events are unchanged. "
               f"Off by default; Owner's Defaults ticks it. {UNVERIFIED}",
               ["The first text of each new event that may touch a sensitive subject starts with \"Content note: "
                "<labels>\" (a variant of that text compiled into the event, shown while this row is installed)."])


def filter_row(game: int, fid: str) -> dict:
    name = f"Content Filter: {content.FILTERS[fid]}"
    return row(game, content.filter_patch(fid), name,
               f"Keeps \"{content.FILTERS[fid].lower()}\" out of the new island events. Applied before the random draw at a natural island event "
               "picks an event: an outcome with that content is dropped where the event still makes sense without it "
               "(the other outcomes keep their shares), otherwise the whole event is skipped. Filters never hide a "
               "kind of person. New events only; the game's own events are unchanged. "
               f"Off by default, Owner's Defaults too. {UNVERIFIED}",
               [f"Every new event's outcomes tagged {fid} are left out of its draw while this row is installed, and "
                "an event that cannot do without them is skipped (its requirement)."])


ANY_TIME = "island_events_any_time"


def any_time_row(game: int) -> dict:
    record = row(game, ANY_TIME, "No Safeguards for Island Events (and Additional Events too)",
                 "For masochists. All island events, the game's own included, can happen at any time: new events can replace rescue events and the two opening events, and no population limit or trouble guard applies. Only the villagers an event needs are still required. "
                 "It applies to whichever island events are on in the game. Anyone can be picked and any event can "
                 "happen at any time (nursing mothers and fathers, the Golden Child, the Tribal Chief and New "
                 "Believers' story villagers included), except when a pick would make no sense in the event -- a "
                 "child's role needs a child, an age change needs a fitting age, a pregnancy needs a villager who can "
                 "carry -- or the event is about someone the village does not have (no Chief, no event about the Chief; a "
                 "leader can be anyone). Objects "
                 "that are not living villagers, such as The Lost Children's totem statues, are never picked, and "
                 "the guards against crashes and damaged saves stay. "
                 f"Off by default, in Owner's Defaults and in Select All too. {UNVERIFIED}",
                 ["For the new events (Story / Cheat Upgrades): no 61-villager gate, rescue events and the two opening "
                  "events may be replaced, no trouble guard and no safeguards; only the villagers each event needs. "
                  "The game's own events' conditions are lifted by another companion (later). It applies to whichever "
                  "island events are on in the game."])
    record["needs_on"] = []           # it applies to whichever island events are on (the owner, 2026-11-15)
    return record


HEATHENS = "heathens_in_island_events"
# The game's own island events' sites Story / Cheat Upgrades splices with the row (story_heathen_stock.inc HV_PICKS'
# direct sites and HV_GROUPS): (the call's VA, its stock target, what it is).
_PICK = "the picker 0x471870's believer draw"
_GROUP = "the believers' group routine 0x470C60"
STOCK_SITES = (
    (0x4150D7, 0x471870, f"Mushroom Day!: {_PICK} (a Heathen child may be drawn in proportion)"),
    (0x4159B5, 0x471870, f"The Daredevil Jump's second villager: {_PICK}"),
    (0x416FD9, 0x471870, f"Innovation in Farming: {_PICK}"),
    (0x414AD1, 0x470C60, f"Isola Day Celebration: {_GROUP}, then the same behaviour for the ordinary Heathens"),
    (0x414B4E, 0x470C60, f"Blessings Day Celebration: {_GROUP}, then the ordinary Heathens"),
    (0x414DE1, 0x470C60, f"Day of Honor: {_GROUP}, then the ordinary Heathens"),
    (0x414F44, 0x470C60, f"The Especially Offensive Cloud: {_GROUP}, then the ordinary Heathens"),
    (0x414F81, 0x470C60, f"The Bottle of Spicy Juice: {_GROUP}, then the ordinary Heathens"),
    (0x415101, 0x470C60, f"Mushroom Day!: {_GROUP}, then the ordinary Heathens"),
    (0x4156DE, 0x470C60, f"The Bed Bugs (Let it go): {_GROUP}, then the ordinary Heathens"),
    (0x417092, 0x470C60, f"Innovation in Farming: {_GROUP} (children), then the ordinary Heathen children"),
)


def call_bytes(va: int, target: int) -> str:
    return "E8" + ((target - (va + 5)) & 0xFFFFFFFF).to_bytes(4, "little").hex().upper()
# The owner's exact title (2026-11-23).
HEATHENS_NAME = "Heathens can be selected in Island Events/Heathen-Exclusive Events"


def heathens_row(game: int) -> dict:
    """New Believers only (the owner, 2026-11-23; docs/event-collection/cie-v6-binary.md 45)."""
    record = row(game, HEATHENS, HEATHENS_NAME,
                 "New Believers. Heathens can be chosen for the island events, the new ones and the game's own, "
                 "and events written for the Heathens alone (Heathen-Exclusive Events) can happen. A sick Heathen is "
                 "never chosen. Heathens get the same personal outcomes as your villagers; in the game's own events "
                 "a Heathen's Faith never changes (they stay a Heathen) and the event's words are as always. The "
                 "puzzles' Heathens (the Heathen Doctor, the Heathen Chief, the Masters, the Heathen Mommy) can be in "
                 "a new event, but nothing in it ever really happens to them: its line says \"(no effect)\". A "
                 "family stays one side (a Heathen with Heathen family), and a baby is only ever two Heathens'. When only Heathens are in an event, the outcomes for the whole tribe (food, tech "
                 "points, buildings, goods, research) happen to the Heathens' village instead and change nothing in "
                 "yours: their lines end \"(no effect)\". When Heathens and villagers are in an event together, those "
                 "outcomes reach your tribe as usual. Heathens never count in the Village Statistics, and the Island "
                 "Events log marks them \"Faction: Heathen\". Heathens can die, disappear or have a baby in an event, "
                 "by the Heathens' own rules: a Heathen who dies just disappears from the camp (a Death record, no "
                 "grave) unless a skeleton row covers them, a camp Heathen is replaced as when one dies of old age "
                 "(never after The Last Heathen, never a villager who left your tribe), and a baby is only ever two "
                 "Heathens' and is born a Heathen. A Heathen is never copied or made a Heathen again. Which roles "
                 "allow Heathens is set per event (every role of the existing events, by the owner's audit). The 45 "
                 "Heathen-Exclusive Events are about the Heathens' own lives: no Heathen's Faith rises from them, nobody "
                 "dies or leaves, and a Heathen honoring the dead at the encampment goes to the old hovel when "
                 "\"Memorial Actions Can Also Occur at the Heathen Hovel\" is installed, or else sits where they are. "
                 "Off by default; Owner's Defaults ticks it. **Needs Story / Cheat Upgrades; the Heathen-Exclusive "
                 f"Events also need the Isola Grand Event Collection.** {UNVERIFIED}",
                 ["Story / Cheat Upgrades casts a Heathen (faction set, never sick, health above 0) in a new event's role "
                  "marked \"heathens\": \"allowed\", \"kin\" or \"only\" while this row is installed; a role marked "
                  "\"only\" takes no believer, and without this row nobody, so its event is not offered.  Every "
                  "villager role of the existing added events New Believers shows is \"allowed\" or \"kin\" "
                  "(data/event_collection/heathen_roles_existing.json, from the owner's approved audit), and the "
                  "Living Event Engine's and the procedural events' roles are \"allowed\".",
                  "A \"kin\" role (a family role: a kinship relation, a pregnancy's other parent) and its family are "
                  "one faction: a Heathen only beside Heathen family, a believer only beside believers.",
                  "A puzzle's Heathen (roles 12-17) may be cast in a new event, and nothing is ever made to them: "
                  "every effect naming them is told, never made (their record is only read), and the page says "
                  "\"Nothing really happens to <name>. (no effect)\"; the Island Events log has nothing of theirs.",
                  "A cast Heathen's \"believer\" words are swapped automatically: \"(friend), a believer,\" / \"(name1) "
                  "is a believer\" / a role called \"believer\" (and Guardians of Isola's \"a villager of faith\") "
                  "become \"a person of faith\".",
                  "The game's own island events (Story / Cheat Upgrades, story_heathen_stock.inc): every believer "
                  "part may draw an ordinary Heathen in proportion (the picker 0x471870 called again for Heathens: "
                  "never roles 12-17, never sick); a Heathen part never takes the same Heathen; The Vision, The Mask, "
                  "Doubt, The Spa and The Cracked Mask never change a drawn Heathen's Faith or faction (their Faith "
                  "is kept below 0 around the apply and put back); the group events Isola Day Celebration, Blessings "
                  "Day Celebration, Day of Honor, The Especially Offensive Cloud, The Bottle of Spicy Juice, Mushroom "
                  "Day!, The Bed Bugs and Innovation in Farming also start their behaviour on the ordinary Heathens "
                  "(The Allergy Season and The Salty Air already do, through the game's 0x470D60).",
                  "When every villager cast is a Heathen, the event's food, tech points, award, building damage or "
                  "repair, goods, trades, tech level and whole-village effects are made nowhere: each automatic line "
                  "says it happens to the Heathens' village (the Isolans' village with Guardians of Isola Rewrite) "
                  "and ends \"(no effect)\".",
                  "An event's death or disappearance of a cast Heathen goes through \"VVFP Heathen Aging.dll\" "
                  "(VvfpHeathenAgingEventGone): a body only with a skeleton row (the statistics' death counter put "
                  "back), else the activity stopped, the presence byte cleared and a Death record (Cause of Death's "
                  "VvfpCauseDiedAmongHeathens); then the replacement of a camp Heathen by the Heathen creator "
                  "0x46FD20, as for an old-age death.",
                  "An event's pregnancy of a cast Heathen goes through the same companion "
                  "(VvfpHeathenAgingEventPregnancy): the game's conception 0x465E00 with a Heathen father only (the "
                  "twins counters put back), the mother kept as expecting and aging until the companion's Heathen "
                  "birth 40 units later (at once for a nursing baby); none once The Last Heathen is solved.",
                  "With this row \"VVFP Heathen Aging.dll\" splices its two sites even with no aging row ticked; "
                  "then only a Heathen expecting an event's baby ages, until the birth.",
                  "More Island Events casts a Heathen only in a role its table names: The Aspiring Adventurer's adventurer "
                  "and friend.",
                  "The Heathen-Exclusive Events HE-01..HE-45 (Isola Grand Event Collection, New Believers only; "
                  "cie-v6-binary.md 47): \"at least N graves\" read from the game's own count (0x464E90 on 0x5481A8); "
                  "the encampment's honoring and reflecting started through the hovel patch's own entries (0x494B83, "
                  "0x494DF1) when its bytes are in, else \"Sitting\"; a group of every ordinary Heathen (or N at "
                  "random), never roles 12-17, never sick.",
                  "The Island Events log ends each Heathen's record with \"Faction: Heathen\" (\"Isolan\" with "
                  "Guardians of Isola Rewrite)."])
    record["needs_on"] = [{"id": f"vv{game}_story_cheat_upgrades",
                           "for": "the island-event engine that chooses the villagers"}]
    record["explicit_non_changes"] = [
        "No executable byte, game file or save is changed: the row is only a name in the installed patches' list "
        "(\"VVFP Installed Patches.txt\") that Story / Cheat Upgrades and More Island Events read.",
        "The game's own island events' texts, choices and chances are never changed; only who may be drawn.",
        "A Heathen never counts in the Village Statistics; nothing is ever made to a puzzle's Heathen.",
    ]
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_heathen_aging_features as aging  # noqa: E402  (its DLL, the flag file and the two sites)
    # (Folded since v1.35.101: its flag file is retired, so the record lists the companion only; the new row ships
    # its own files.)
    record["companion_files"] = [
        {"source": f"assets/heathen_aging/{aging.DLL_NAME}", "destination": aging.DLL_NAME,
         "sha256": aging.sha(aging.DLL)},
    ]
    record["runtime_detours"] = [
        {"va": f"0x{va:X}", "stock_bytes": stock, "written_bytes": "E9XXXXXXXX" + "90" * (len(stock) // 2 - 5),
         "routine": what, "installed_by": aging.INSTALLED_BY}
        for va, stock, what in aging.SITES]
    # The game's own events (story_heathen_stock.inc): the stock `call rel32` sites Story / Cheat Upgrades splices
    # with this row (the other believer draws are its own scope calls already).
    for va, target, what in STOCK_SITES:
        record["runtime_detours"].append({
            "va": f"0x{va:X}", "stock_bytes": call_bytes(va, target), "written_bytes": "E8XXXXXXXX",
            "routine": what, "installed_by": "VVFP Story Upgrades.dll, VvfpStoryArm (New Believers, with this row)"})
    record["explicit_non_changes"][0] = (
        "No executable byte is patched: \"VVFP Heathen Aging.dll\" splices its two sites and Story / Cheat Upgrades "
        "its game's-own-event sites at run time, after verifying their stock bytes, each all or none; the row is "
        "otherwise a name in the installed patches' list (\"VVFP Installed Patches.txt\") that Story / Cheat "
        "Upgrades and More Island Events read.")
    record["evidence_status"] = ("the casting, the flavor-only effects and the log line pinned in "
                                 "tests/test_heathens_in_island_events.py and tests/test_heathens_in_existing_events.py (emulated), "
                                 "the Heathen-Exclusive Events and their engine pieces in "
                                 "tests/test_heathen_only_events.py (emulated); runtime/player confirmation pending")
    return record


def rows(game: int) -> list[dict]:
    # heathens_row is no longer a row of its own: "Heathen Tribe Expansion and Evolution" folds it (v1.35.101;
    # scripts/build_heathen_tribe_evolution_feature.py takes its island-event parts from heathens_row(5)).
    return ([notes_row(game), any_time_row(game)]
            + [filter_row(game, f) for f in content.FILTER_IDS])


def feature_path(record: dict) -> Path:
    return ROOT / "data" / f"{record['id']}_feature.json"


def main() -> None:
    n = 0
    for game in GAMES:
        for record in rows(game):
            feature_path(record).write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            n += 1
    print(f"{n} rows written")


if __name__ == "__main__":
    main()
