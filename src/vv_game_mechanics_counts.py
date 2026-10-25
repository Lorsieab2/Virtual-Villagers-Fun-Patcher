"""Game Mechanics: the "Village counts" group, for all five games (src/vv_game_mechanics.py).

Every count a game or the patcher keeps for one village, read only -- never estimated, never worked back:

  * the rows of the patcher's Village Statistics log for this save ("Village Statistics v2 - Save <S>.txt",
    written by native/statistics_export/statistics_export.c after every successful save).  The counting is that
    code's, never done again here: this page only reads the log it wrote.  The rows the game itself keeps in its
    save's statistics block are also read straight from the save, at the very fields that code reads (the same
    offsets, less nothing: a FILE offset here is the manager field + 4 in the first three games and + 0x10 in the
    last two); where the save and the log disagree both are shown (the owner: contradictions are shown, never
    silently picked).  The rows only the patcher keeps (Village Elders in the later games, Villagers Buried,
    The Lost Children's Twins Birthed, Chiefs Robed, Debris Cleared, The Tree of Life's and New Believers' Food
    Gathered, Heathens Converted, the stews) are in its per-save .dat files and printed in that log, so they come
    from the log alone;
  * what else each game keeps that a player counts: A New Home's Golden Child, The Lost Children's discovered
    stew recipes and its Esteemed Elders and their totems, The Secret City's Tribal Chief, The Tree of Life's tree,
    stream, Fire Pit and stores, New Believers' Heathens;
  * and, said plainly, what is not kept anywhere ("not kept").

Heathens (New Believers) are never counted in any row unless they are in the tribe (the owner; the statistics code
counts believers only).  The Golden Mushroom is a mushroom in every row; the patcher keeps no count of its own
finds (native/vvfp_golden_mushroom keeps no record), and it is named only when its patch is in the game.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from pathlib import Path

import vv_game_mechanics as gm

COUNTS = "Village counts"
VITALS = "Vital statistics"
LOG_FOLDER = "Village Statistics"
LOG_NAME = "Village Statistics v2 - Save {slot}.txt"
GOLDEN = "vv{game}_super_secret_golden_mushroom"
DUPLICATION = "vv{game}_everyone_collects_like_vv1"
HEATHEN_MOMMY = "vv5_heathen_mommy_puzzle"

# The game's own statistics fields, as FILE offsets, by row (the statistics writer's reads,
# native/statistics_export/statistics_export.c write_vv1 / write_vv2 / write_later_game / write_vv5).
_LATER = {"Tech Points Earned": 0x04, "Babies Made": 0x08, "People Cured": 0x10, "Mushrooms Found": 0x14,
          "Highest Population": 0x18, "Oldest Villager": 0x20, "Island Events Seen": 0x24, "Twins Birthed": 0x28,
          "Triplets Birthed": 0x2C}
SAVE_ROWS: dict[int, dict[str, int]] = {
    1: {"Food Gathered": 0x9E2C, "Tech Points Earned": 0x9E24, "People Cured": 0x9E30, "Mushrooms Found": 0x9E34,
        "Highest Population": 0x9E38, "Oldest Villager": 0x9E40, "Island Events Seen": 0x9E44, "Babies Made": 0x9E28,
        "Twins Birthed": 0x9E48, "Triplets Birthed": 0x9E4C},
    2: {"Food Gathered": 0x2E508, "Tech Points Earned": 0x2E500, "People Cured": 0x2E50C, "Mushrooms Found": 0x2E510,
        "Highest Population": 0x2E514, "Village Elders": 0x2E518, "Oldest Villager": 0x2E51C,
        "Island Events Seen": 0x2E520, "Babies Made": 0x2E504, "Triplets Birthed": 0x2E528,
        "Special Stews Found": 0x2E524},
    3: {**{k: 0x4F0 + v for k, v in _LATER.items()}, "Food Gathered": 0x4F0 + 0x0C},
    4: {k: 0x860 + v for k, v in _LATER.items()},
    5: {k: 0x7C4 + v for k, v in _LATER.items()},
}
# Every row of the log, in its order (docs/village-statistics-directive.md), and the game-specific rows.
COMMON = ("Real Hours Played", "Food Gathered", "Tech Points Earned", "People Cured", "Mushrooms Found",
          "Highest Population", "Village Elders", "Oldest Villager", "Island Events Seen", "Babies Made",
          "Twins Birthed", "Triplets Birthed", "Villagers Buried", "Puzzles Solved")
EXTRA = {1: (), 2: ("Special Stews Found", "Total Stews Found"), 3: ("Chiefs Robed", "Stews Found"),
         4: ("Debris Cleared", "Stews Found"), 5: ("Heathens Converted",)}
# What each row counts, in plain words with its unit (the owner: real-life or in-game, never a bare unit).
MEANING = {
    "Real Hours Played": "real-life hours since the village was founded (the games' own formula, not the time "
                         "the game was open)",
    "Food Gathered": "food brought in",
    "Tech Points Earned": "tech points earned",
    "People Cured": "villagers cured",
    "Mushrooms Found": "mushrooms picked",
    "Highest Population": "the most villagers the village has had at once",
    "Village Elders": "villagers who ever held Master in 3 or more skills, each counted once",
    "Oldest Villager": "the oldest age a villager has reached, in villager years",
    "Island Events Seen": "island events",
    "Babies Made": "babies, counted at conception as the game counts them",
    "Twins Birthed": "twin births, +1 for each pair",
    "Triplets Birthed": "triplet births, +1 for each set",
    "Villagers Buried": "skeletons buried, each villager once (deaths with no burial are not counted)",
    "Puzzles Solved": "puzzles solved",
    "Special Stews Found": "stew recipes cooked for the first time (the game's own count, 18 recipes)",
    "Total Stews Found": "different herb combinations cooked into a stew",
    "Stews Found": "different ingredient combinations made in the cauldron",
    "Chiefs Robed": "villagers robed Tribal Chief, each once for life",
    "Debris Cleared": "units of debris cleared from the stream (the trophy is at 1,000)",
    "Heathens Converted": "Heathens brought into the tribe: the Heathen Chief and each Red, Purple, Blue or Orange "
                          "Mask +1, the Heathen Mommy +2",
}
NO_HEATHENS = {"Highest Population", "Village Elders", "Oldest Villager", "Babies Made", "Twins Birthed",
               "Triplets Birthed", "Villagers Buried", "People Cured", "Food Gathered", "Mushrooms Found"}
_ROW = re.compile(r"^([A-Za-z' ]+): (-?\d+)(?: out of (\d+))?\s*$")


@dataclass
class StatisticsLog:
    path: Path
    written: float
    rows: dict[str, tuple[int, int | None]]


def statistics_log(village: gm.Village) -> StatisticsLog | None:
    """The patcher's Village Statistics log for this save, when there is one (the slot's own folder first, then the
    older places it may still be in); None when none is found or it cannot be read."""
    import vv_save_layout as layout
    name = LOG_NAME.format(slot=village.slot)
    places = [layout.slot_log_folder(village.folder, LOG_FOLDER, village.slot)]
    places += [p for p in reversed(layout.log_folders(village.folder, LOG_FOLDER, village.slot)) if p not in places]
    for place in places:
        path = Path(place) / name
        try:
            text = path.read_text(encoding="latin-1")
            written = path.stat().st_mtime
        except OSError:
            continue
        rows: dict[str, tuple[int, int | None]] = {}
        for line in text.splitlines():
            m = _ROW.match(line.strip())
            if m:
                rows[m.group(1)] = (int(m.group(2)), int(m.group(3)) if m.group(3) else None)
        return StatisticsLog(path, written, rows)
    return None


def _i32(data: bytes, at: int) -> int | None:
    if 0 <= at <= len(data) - 4:
        return struct.unpack_from("<i", data, at)[0]
    return None


def _value(row: str, n: int, of: int | None) -> str:
    return f"{n:,} out of {of:,}" if of is not None else f"{n:,}"


def _puzzles_from_page(facts: list[gm.Fact]) -> tuple[int, int] | None:
    for f in facts:
        m = re.match(r"^Puzzles solved: (\d+) of (\d+)", f.text)
        if f.group == gm.PUZZLES and m:
            return int(m.group(1)), int(m.group(2))
    return None


def statistics_lines(village: gm.Village, facts: list[gm.Fact]) -> list[gm.Fact]:
    """Every row of the Village Statistics for this save: the game's own field from the save where it keeps one, the
    patcher's log otherwise, and both where they disagree."""
    out: list[gm.Fact] = []
    log = statistics_log(village)
    data = village.data
    fields = SAVE_ROWS[village.game]
    if log is None:
        out.append(gm.Fact(COUNTS, (
            "The patcher's Village Statistics log for this save was not found (it is written after each save by "
            "the patcher's Village Statistics patch); the rows below that only it keeps are not shown."), gm.SAVE))
    else:
        behind = ""
        try:
            if village.save.stat().st_mtime > log.written + 60:
                behind = (" The save was written after it, by a game that did not refresh it, so its rows can be "
                          "behind the save.")
        except OSError:
            pass
        out.append(gm.Fact(COUNTS, f"Village Statistics (the patcher's log {log.path.name}, last written "
                                   f"{gm.when(log.written)}; the game's own fields read from the save beside it)."
                                   + behind, gm.SAVE))
    page_puzzles = _puzzles_from_page(facts)
    for row in COMMON + EXTRA[village.game]:
        logged = log.rows.get(row) if log else None
        saved = _i32(data, fields[row]) if row in fields else None
        if row == "Puzzles Solved" and page_puzzles is not None:
            saved_words = f"{page_puzzles[0]} out of {page_puzzles[1]}"
            saved_pair = page_puzzles
        else:
            saved_words = None if saved is None else f"{saved:,}"
            saved_pair = None if saved is None else (saved, None)
        meaning = MEANING[row]
        if row == "Mushrooms Found" and village.has(GOLDEN.format(game=village.game)) is True:
            meaning += ", a Golden Mushroom counting as one"       # named only with its patch in the game
        if village.game == 5 and row in NO_HEATHENS:
            meaning += "; believers only, Heathens never count unless in the tribe"
        lead = f"{row}: "
        if saved_words is not None and logged is not None:
            same = (saved_pair[0] == logged[0]) and (saved_pair[1] is None or logged[1] is None or saved_pair[1] == logged[1])
            if same:
                text = f"{lead}{_value(row, *logged)} ({meaning}; the save and the patcher's log agree)."
            else:
                text = (f"{lead}the save holds {saved_words}; the patcher's Village Statistics log says "
                        f"{_value(row, *logged)} ({meaning}). They disagree: the log is written at each save, so "
                        "one of them is from another moment.")
        elif saved_words is not None:
            source = "the Puzzles list below, from the save" if row == "Puzzles Solved" else "the save"
            text = f"{lead}{saved_words} ({meaning}; from {source})."
        elif logged is not None:
            text = f"{lead}{_value(row, *logged)} ({meaning}; kept by the patcher, from its log)."
        else:
            text = (f"{lead}not shown: only the patcher's Village Statistics log gives it, and its log for this save "
                    + ("was not found." if log is None else "has no such row."))
        out.append(gm.Fact(COUNTS, text, gm.SAVE, sub=True))
    return out


# ---------------------------------------------------------------------------
# Game-specific counts
# ---------------------------------------------------------------------------


def _people(village: gm.Village):
    import vv_game_mechanics_life as life
    return life.people(village)


def vv1_lines(village: gm.Village) -> list[gm.Fact]:
    out: list[gm.Fact] = []
    everyone = _people(village)
    solved = village.data[0xA008 + 4] != 0                 # The Golden Child puzzle's solved byte (vv1.PUZZLES)
    golden = [p for p in (everyone or []) if p.golden]
    if golden:
        for p in golden:
            out.append(gm.Fact(COUNTS, f"The Golden Child: born; {p.name}, age 5 villager years (100 age units), as "
                                       "always: he is born at 5 and stays 5.", gm.SAVE))
    elif solved:
        out.append(gm.Fact(COUNTS, "The Golden Child: born (The Golden Child puzzle is solved), but he is not among "
                                   "the living villagers in this save.", gm.SAVE))
    else:
        out.append(gm.Fact(COUNTS, "The Golden Child: not born yet (The Golden Child puzzle is not solved).", gm.SAVE))
    out.append(gm.Fact(COUNTS, "Stews, potions, collectibles and chiefs: A New Home has none.", gm.RUNNING))
    return out


VV2_RECIPE_FLAGS = 0x2EAAC + 4                    # file offset; byte +recipe (1..18) set the first time it is cooked
VV2_RECIPES = 18


def vv2_lines(village: gm.Village) -> list[gm.Fact]:
    import vv_last_names as ln
    import vv_vv2_totems as totems
    data = village.data
    out: list[gm.Fact] = []
    found = [r for r in range(1, VV2_RECIPES + 1) if VV2_RECIPE_FLAGS + r < len(data) and data[VV2_RECIPE_FLAGS + r]]
    out.append(gm.Fact(COUNTS, (
        f"Stew recipes discovered: {len(found)} of {VV2_RECIPES}"
        + (f" (the game's recipe numbers {', '.join(map(str, found))})" if found else "")
        + ". The game gives its stews no names: it tells them apart only by what a stew does when eaten (\"This "
        "delicious stew is very filling.\", ...). The cook routine 0x425B90 sets a recipe's byte the first time it is "
        "cooked (0x4260A5, 0x4260D4) and counts Special Stews Found then."), gm.SAVE))
    # The Esteemed Elders and their totems (src/vv_vv2_totems.py, src/vv_vv2_totem_store.py).
    try:
        living = ln._entries(2, data)
        elders = [ln._cstr(data, at, totems.NAME_CAP) for at in living
                  if 0 <= at + totems.ELDER < len(data) and data[at + totems.ELDER] != 0]
    except Exception:  # noqa: BLE001 -- a villager table that cannot be read gives no elder line
        elders = None
    try:
        import vv_vv2_totem_store as store_mod
        statues = [ln._cstr(data, at, totems.NAME_CAP) for _k, at in store_mod.statues_in_save(data)]
        stored: list[str] = []
        try:
            store = store_mod.read(village.folder, village.slot)
            if store is not None and store_mod.bound(store, data):
                stored = [t.name for t in store.totems]
        except Exception:  # noqa: BLE001 -- an unreadable store is said, never guessed at
            stored = []
    except Exception:  # noqa: BLE001
        statues, stored = None, []
    if elders is not None:
        out.append(gm.Fact(COUNTS, f"Esteemed Elders living now: {len(elders)}"
                                   + (f" ({', '.join(elders)})" if elders else "") + ".", gm.SAVE))
    if statues is not None:
        names = statues + stored
        where = (f"; {len(stored)} of them kept in the patcher's ElderTotems.dat, outside the save" if stored else "")
        out.append(gm.Fact(COUNTS, f"Totems standing now: {len(names)}" + (f" ({', '.join(names)})" if names else "")
                                   + where + ".", gm.SAVE))
    out.append(gm.Fact(COUNTS, (
        "How a villager becomes an Esteemed Elder: about every 2 real-life seconds while the game runs (the world tick "
        "0x43B690 into the elder pass 0x44D4C0), any living villager who is not yet an elder and has 3 of the 5 skills "
        "at 88 or more becomes one and gets a totem (0x44D190; Village Elders +1 at 0x44D55F). No dice roll, no "
        "age condition, the same at every speed; the first totem solves The Elder Totem."), gm.RUNNING))
    has = village.has("vv2_totems_out_of_entries")
    words = (f"Normal game: at most 50 totems (0x44D4D1, 0x44D54C): with 50 standing no new elder is made, and each "
             "totem takes one of the 256 villager records.")
    if has:
        words += (f" With \"{gm.feature_name('vv2_totems_out_of_entries')}\" (in this game): totems take no record and "
                  "there is no limit.")
    out.append(gm.Fact(COUNTS, words, gm.RUNNING, sub=True))
    out.append(gm.Fact(COUNTS, "Esteemed Elders over time: the game's Village Elders field above counts every elder "
                               "made.", gm.RUNNING, sub=True))
    return out


VV3_CHIEF_NOTE = ("Tribal Chiefs over time: the patcher's Chiefs Robed row above (a villager is robed at most once and "
                  "stays chief until death).")


def vv3_lines(village: gm.Village) -> list[gm.Fact]:
    out: list[gm.Fact] = []
    everyone = _people(village)
    if everyone is not None:
        chiefs = [p.name for p in everyone if p.chief]
        out.append(gm.Fact(COUNTS, ("Tribal Chief now: " + ", ".join(chiefs) + "." if chiefs
                                    else "Tribal Chief now: none."), gm.SAVE))
    out.append(gm.Fact(COUNTS, VV3_CHIEF_NOTE, gm.OWNER, sub=True))
    out.append(gm.Fact(COUNTS, (
        "Potions and stews: the Alchemy Lab's recipe book (0x59454C) keeps one byte for each of its recipes, set by "
        "0x430510 after a brew succeeds, and the game saves it (0x430110); every successful cauldron product, a "
        "potion included, is a stew for the patcher's Stews Found above. This page does not read the book: where in "
        "the save it lies is not worked out, so no list of the recipes is shown."), False))
    out.append(gm.Fact(COUNTS, "Potions brewed, counted one by one: not kept by the game's statistics or the patcher.",
                       False))
    return out


# The Tree of Life (the coordinator's VV4 save research, 2026-10-24, FILE offsets checked on the committed saves).
VV4_TREE_PUZZLES = {1: "The Stream", 12: "Pruning", 13: "Honoring", 14: "Purify", 15: "Decorating"}
VV4_PUZZLE_ENTRIES = 0x160D4                     # (progress, solve time) per puzzle id
VV4_STREAM_BLOCKED = 0x161AC
VV4_SOAP, VV4_CLOTH, VV4_TOOLS = 0x161B1, 0x161CA, 0x161A4
VV4_TECHS = 0xBCB8
VV4_TECH_NAMES = ("Science", "Medicine", "Learning", "Construction", "Food Mastery", "Dendrology")


def vv4_lines(village: gm.Village) -> list[gm.Fact]:
    import vv_game_mechanics_vv4 as vv4
    data = village.data
    out: list[gm.Fact] = []

    def solved(pid: int) -> bool:
        progress = _i32(data, VV4_PUZZLE_ENTRIES + 8 * pid)
        return progress is not None and progress >= vv4.PUZZLE_THRESHOLDS.get(pid, 1)

    done = [name for pid, name in VV4_TREE_PUZZLES.items() if solved(pid)]
    out.append(gm.Fact(COUNTS, (
        f"The Tree of Life: stage {len(done)} of 5 -- one stage for each of The Stream, Pruning, Honoring, Purify and "
        "Decorating solved (0x41F570; the tree's art tree-state-00 to 05)"
        + (f"; solved: {', '.join(done)}." if done else "; none solved yet.")), False))
    levels = [_i32(data, VV4_TECHS + 4 * k) for k in range(6)]
    if None not in levels:
        out.append(gm.Fact(COUNTS, "Tech levels: " + "; ".join(f"{n} {v}" for n, v in zip(VV4_TECH_NAMES, levels))
                                   + " (tech points are one shared pool, not kept by area).", False))
    blocked = _i32(data, VV4_STREAM_BLOCKED)
    if blocked is not None and 0 <= blocked <= 100:
        out.append(gm.Fact(COUNTS, f"The stream: {blocked}% obstructed (the game's \"Stream obstruction percentage\").",
                           False))
    if VV4_CLOTH < len(data):
        soap, cloth, tools = data[VV4_SOAP], data[VV4_CLOTH], _i32(data, VV4_TOOLS)
        out.append(gm.Fact(COUNTS, f"On hand: {soap} soap bars, {cloth} cloth bolts, {tools} cutting tools.", False))
    out.append(gm.Fact(COUNTS, "Stews made, one by one: the patcher's Stews Found above counts the different ones "
                               "(cloth pulp and soap brews are stews too); the game's recipe book marks a recipe when it "
                               "is looked up, before the brew can still fail, so it is no count of stews made.",
                       gm.RUNNING))
    out.append(gm.Fact(COUNTS, "Barrel of Babies opened: not kept by the game or the patcher.", False))
    return out


# New Believers' Heathens (the coordinator's VV5 research, 2026-10-24; offsets from the villager's name).
VV5_ROLE, VV5_SEX, VV5_ORANGE, VV5_RED = -0x14, -0x0C, -0x1E, -0x1D
VV5_ROLES = {12: "Heathen Doctor", 13: "Heathen Chief", 14: "Heathen Master Scientist", 15: "Heathen Master Builder",
             16: "Heathen Master Farmer", 17: "Heathen Mommy"}


def vv5_lines(village: gm.Village) -> list[gm.Fact]:
    import vv_last_names as ln
    data = village.data
    out: list[gm.Fact] = []
    try:
        entries = ln._entries(5, data)
    except Exception:  # noqa: BLE001
        entries = None
    if entries is None:
        out.append(gm.Fact(COUNTS, "Heathens: the villager table could not be read.", gm.SAVE))
        return out
    heathens, retired = [], []
    for at in entries:
        if not 0x20 <= at < len(data) - 4:
            continue
        name = ln._cstr(data, at, 0x18)
        role = _i32(data, at + VV5_ROLE)
        if data[at - 0x1F] != 0:
            mask = ("purple" if role in (12, 14, 15, 16) else "chief's" if role == 13 else
                    "orange" if data[at + VV5_ORANGE] else "red" if data[at + VV5_RED] else "blue")
            heathens.append((name, VV5_ROLES.get(role, "Heathen"), mask, _i32(data, at + VV5_SEX) == 0,
                             _i32(data, at - 0x18)))
        elif role == 13:
            retired.append(name)
    out.append(gm.Fact(COUNTS, f"Heathens now: {len(heathens)} outside the tribe, never counted in the tribe's "
                               "population or in any statistics row.", gm.SAVE))
    groups: dict[str, list[str]] = {}
    for name, role, mask, _male, faith in heathens:
        label = role if role != "Heathen" else f"Heathens ({mask} mask)"
        groups.setdefault(label, []).append(f"{name} (Faith {faith})")
    for label in list(VV5_ROLES.values()) + sorted(k for k in groups if k not in VV5_ROLES.values()):
        if label in groups:
            out.append(gm.Fact(COUNTS, f"{label}: {', '.join(groups[label])}.", gm.SAVE, sub=True))
    if retired:
        out.append(gm.Fact(COUNTS, f"Retired Heathen Chief in the tribe: {', '.join(retired)}.", gm.SAVE, sub=True))
    out.append(gm.Fact(COUNTS, (
        "Converted so far: the patcher's Heathens Converted row above. The game itself keeps no count of conversions, "
        "nor of Heathens born, arrived, died or left, and no date of a conversion; a converted Heathen other than the "
        "Chief keeps no mark of it (0x466966 sets the role to 0)."), gm.RUNNING, sub=True))
    out.append(gm.Fact(COUNTS, (
        "Heathen camps: the game models none; an ordinary Heathen's role number (0 to 11, 18) is only the spot it "
        "stays at, picked at random among the unsolved puzzles' spots (0x469F20)."), gm.RUNNING, sub=True))
    out.append(gm.Fact(COUNTS, (
        "Conversion: setting a Heathen's Faith (0x467F90) converts them (0x4668B0) when it goes from 0 or less to "
        "above 0, once the story allows it (game flag +0x17E39, 0x442206); a convert below 5 is raised to 55. "
        "Preaching (0x468DA0) adds 3 Faith, 4 at Devotion 50 or more, 5 at 88 or more, after a Devotion skill roll "
        "(0x46B270), and that Heathen then waits 7,200 real-life seconds (2 real-life hours, at any speed, 0x468F2A); "
        "the Doctor, the Chief, the Masters and the Mommy cannot be preached to. The Chief's puzzle sets the Chief's "
        "Faith to 100 (0x4360E0); curing the Heathen Doctor sets 25 to 59 (0x468CF2)."), gm.RUNNING, sub=True))
    if village.has(HEATHEN_MOMMY):
        out.append(gm.Fact(COUNTS, (
            f"The Heathen Mommy (with \"{gm.feature_name(HEATHEN_MOMMY)}\", in this game): she is made with no sex "
            "given (the creator 0x46FD20 with sex -1, so 0x468534 leaves it), and the game's own villager roll "
            "decides it (0x46F5E0: the C rand value modulo 100, 49 or less is male): male 16,400 times in 32,768 (50.05%), female "
            "49.95%. A male Heathen Mommy is the game's own doing, as intended, not a fault. Her conversion counts +2 "
            "in Heathens Converted."), gm.RUNNING, sub=True))
    return out


def collectible_lines(village: gm.Village, group: str) -> list[gm.Fact]:
    """The collectibles found (the save's own counts) and, where the patcher's duplication cheat exists, what it
    changes: the normal game first."""
    import vv_game_mechanics_life as life
    out: list[gm.Fact] = []
    if group == COUNTS:
        counts = life.collectible_counts(village)
        if counts is None:
            out.append(gm.Fact(group, "Collectibles found: not read from this save by this page.", gm.SAVE))
        else:
            owned = sum(1 for c in counts if c > 0)
            out.append(gm.Fact(group, f"Collectibles found: {sum(counts):,} in all; {owned} of the 48 pieces owned.",
                               gm.SAVE))
    feature = DUPLICATION.format(game=village.game)
    name = gm.feature_name(feature)
    words = "Normal game: a mushroom or collectible is picked up by the one child dropped on it."
    if village.has(feature):
        words += (f" With \"{name}\" (in this game): several children can be dropped onto one mushroom or "
                  "collectible and it is multiplied, one for each, so the counts above can grow faster.")
    out.append(gm.Fact(group, words, False, sub=group == COUNTS))
    return out


def golden_finds(village: gm.Village) -> list[gm.Fact]:
    if village.has(GOLDEN.format(game=village.game)) is not True:
        return []
    return [gm.Fact(COUNTS, (
        "Golden Mushrooms found: not kept. The patcher's Golden Mushroom code (native/vvfp_golden_mushroom) writes no "
        "record of a find, and the game counts it only inside Mushrooms Found, as a mushroom, so neither how many "
        "nor when the first one was found can be told."), gm.RUNNING)]


GAME_LINES = {1: vv1_lines, 2: vv2_lines, 3: vv3_lines, 4: vv4_lines, 5: vv5_lines}


def facts(village: gm.Village, page: list[gm.Fact]) -> list[gm.Fact]:
    """The Village counts group (and the collectibles' duplication line in Vital statistics) for a save its game's
    module read; nothing for one it could not."""
    if village.general or not any(f.group != "Other" for f in page):
        return []
    out = statistics_lines(village, page)
    out += GAME_LINES[village.game](village)
    if village.game in (3, 4, 5) or village.game == 2:
        out += collectible_lines(village, COUNTS)
        out += collectible_lines(village, VITALS)
    out += golden_finds(village)
    out.append(gm.Fact(COUNTS, (
        "Arrivals and departures, deaths without a burial, and tech points spent: not kept by the game as counts; "
        "the patcher's Births and Conceptions and Deaths and Disappearances logs list each birth and death."), False))
    return out
