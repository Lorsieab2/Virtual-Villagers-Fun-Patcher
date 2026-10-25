"""Game Mechanics: the "Death and graves" group, for all five games (src/vv_game_mechanics.py).

Every way a villager dies or leaves the village, the trigger and the chance; how the grave's Age at Death, Cause of
Death, epitaph and skill line are chosen; the grave limit; when bodies are buried or removed; the patches in the game
that change any of it (the stock value first); and, from the save, the village's graves, its unburied bodies and the
patcher's Deaths log counts.  Each game's module adds these lines with one call:

    out.extend(death.facts(village, ...))

The rules are read from each stock executable (inputs\\vvN-stock-copy); the addresses are given beside each game's
lines.  A line read from the game's own reachable code is marked gm.CODE; one the owner confirmed gm.OWNER; one
read from the save gm.SAVE; anything else carries UNCONFIRMED.  Island-event odds are left to the Island events
group, sickness and starvation rates to the lines already on the page (Other, Hidden villager stats).

Nothing here writes anything.
"""
from __future__ import annotations

import re
import struct
from collections import Counter

import vv_game_mechanics as gm

DEATH = gm.DEATH
CODE = gm.CODE
YEAR = 20                                       # age units a villager year


def _i32(data: bytes, at: int) -> int:
    return struct.unpack_from("<i", data, at)[0]


def _counts(counter: Counter, order: list[str] | None = None) -> str:
    keys = [k for k in (order or []) if counter.get(k)] + sorted(k for k in counter if k not in (order or []))
    return ", ".join(f"{k} {counter[k]}" for k in keys)


# ---------------------------------------------------------------------------
# What every game shares: the save's graves, its bodies, the Deaths log
# ---------------------------------------------------------------------------

CAUSE_ORDER = ["Old age", "Disease", "Starvation", "Work accident", "Act of Nature", "Unknown causes",
               "Died in a custom island event"]


def grave_lines(village: gm.Village, limit: int, by_cause: bool) -> list[gm.Fact]:
    """The graves in this save (src/vv_graves.read_graves, the game's own grave table) and, where the grave keeps
    one (VV3-VV5) or the patcher's Graves file does (VV1, VV2), their causes."""
    if village.general:
        return []
    import vv_graves
    try:
        graves = vv_graves.read_graves(village.game, village.data)
    except Exception:  # noqa: BLE001 -- a save without a readable grave table gives no grave lines
        return [gm.Fact(DEATH, "The graves in this save could not be read.", gm.SAVE)]
    if village.game <= 2:
        try:
            vv_graves._load_sidecar(village.folder, village.game, village.slot, graves)
        except Exception:  # noqa: BLE001 -- no Graves file: no causes
            pass
    out = [gm.Fact(DEATH, f"Graves in this village: {len(graves)} of {limit}.", gm.SAVE)]
    if not graves:
        return out
    causes = Counter((g.values.get("cause") if by_cause else g.sidecar.get("cause")) or "not recorded"
                     for g in graves)
    where = "as the graves keep them" if by_cause else "as the patcher's Graves file keeps them"
    out.append(gm.Fact(DEATH, f"Graves by cause of death, {where}: {_counts(causes, CAUSE_ORDER)}.", gm.SAVE,
                       sub=True))
    epitaphs = Counter(g.values.get("epitaph") or g.sidecar.get("epitaph") or "" for g in graves)
    epitaphs.pop("", None)
    if epitaphs:
        out.append(gm.Fact(DEATH, f"Graves by epitaph: {_counts(epitaphs)}.", gm.SAVE, sub=True))
    oldest = max(graves, key=lambda g: g.age)
    out.append(gm.Fact(DEATH, f"The oldest at death: {oldest.name}, {oldest.age // YEAR} years ({oldest.age} age "
                              "units).", gm.SAVE, sub=True))
    return out


def log_lines(village: gm.Village) -> list[gm.Fact]:
    """The patcher's Deaths log for this slot (the Log Every Death patch's records): Death records by cause, how
    many had no grave, and Disappeared records."""
    if village.general:
        return []
    import vv_graves
    try:
        blocks = vv_graves._all_blocks(village.folder, village.game, village.slot)
    except Exception:  # noqa: BLE001 -- no logs, or none readable: nothing to count
        return []
    deaths = [b for b in blocks if vv_graves._is_death(b)]
    gone = [b for b in blocks if re.match(r"^Disappeared( \d+)?$", b.heading or "")]
    if not deaths and not gone:
        return []
    causes = Counter((b.value("Cause of death") or "not recorded") for b in deaths)
    unburied = sum(1 for b in deaths if not vv_graves._buried(b))
    text = (f"The patcher's Deaths log for this village: {len(deaths)} Death record"
            f"{'' if len(deaths) == 1 else 's'}" + (f" ({_counts(causes, CAUSE_ORDER)})" if deaths else "")
            + f", {unburied} of them with no grave; {len(gone)} Disappeared record{'' if len(gone) == 1 else 's'}.")
    return [gm.Fact(DEATH, text, gm.SAVE)]


def bodies(village: gm.Village) -> list[tuple[str, int]]:
    """The save's unburied bodies: (name, name offset) of every villager the game loads with health 0 or less."""
    try:
        import vv_last_names as ln
        import vv_game_mechanics_life as life
        lay = life.LAYOUTS[village.game]
        return [(ln._cstr(village.data, at, ln.FIELDS[village.game].name_cap), at)
                for at in ln._entries(village.game, village.data, bodies=True)
                if _i32(village.data, at + lay.health) <= 0]
    except Exception:  # noqa: BLE001 -- an unreadable villager table gives no body lines
        return []


# ---------------------------------------------------------------------------
# New Believers (VV5)
# ---------------------------------------------------------------------------
#
# Health is record +0x1C40 (0 to 100) and the cause +0x1C44, written only through two setters: 0x4758F0 (add)
# and 0x4758B0 (set).  Both clamp at 100; when health reaches 0 or less they store 0 and the cause passed in,
# otherwise the cause goes back to -1 -- so a grave's cause is the cause of the loss that took health to 0.
# Every caller (the whole .text scanned for calls to the two setters):
#   life tick 0x472C90 (believers only: a Heathen's processed age is set to its age at 0x472CB7 and nothing else
#     runs): 0x472D97 food 500 or less, -1 on 15% of age units, cause 1 Starvation; 0x472E4B no food, cause 1;
#     0x472ED1 sick, -1 on 61% of age units (19% at 20 health or less), cause 0 Disease; 0x473043 old age, set
#     to 0, cause 2 Old age; the rest add health (cause -1);
#   research 0x46DC91: 2% of tries (rand(100) < 2, 0x46DC71) lose rand(10) = 0 to 9, cause 3 Work accident;
#   island events, cause -1 (each outcome is the event's vtable slot 11; its choice A = 0, B = 1):
#     The Bed Bugs 0x4156A0: "Let it go" -15 (0x4156C5); "Search for the bugs all night" -5 only above 6 health
#       (0x4156EF) and sick;
#     You're Doing It Wrong! 0x416020: "Teach them to reduce explosions." when it explodes, -(10 + rand(20));
#     The Missing Kids 0x416120: "Yell for help", both children -5 and sick;
#     The Cracked Mask 0x416BB0: "Attempt to fix the mask", -(20 + rand(11));
#     The Stinging Wasps 0x415160 (condition 0x415B10 always false: never in the stock game): every villager
#       50% (0x470BF0 with 50, 10, 10) to lose 10 + rand(10), cause 0 Disease;
#     Innovation in Farming (slot 51, 0x416EF0) and The Child in the Tree (0x417270) take 75 or more health but
#       share that never-true condition and no patch offers them;
#   Revive 0x41FFBC sets health 100; a new villager's slot is set to 0 before it is filled (0x46FE66).
# Cause 4 (Act of Nature) has no caller.
#
# Old age (0x472FC6): at each whole year of the processed age (age % 20 == 0) past 1,100 + 160 x (Medicine - 1)
# age units, rand(100) < 10 x (years - threshold years) sets health 0, cause 2.
#
# Bodies.  The villager AI 0x46F070 (believers; Heathens go to 0x46E9E0): on 34% of choices (rand(100) > 65,
# 0x46F0D9), a believer not sick (+0x1C48), not carrying (+0x1C4C) and 14 or older (280, 0x46F117) reaches
# 0x46F130: with The Buried Mausoleum (puzzle 6) solved and a body lying (0x470940: the lowest slot with health 0 or
# less), they go to bury it -- "Burying the dead", behaviour 0x30 -- at once 25% of the time (rand(100) < 25), else,
# with Healing (skill 2) 50 or more, 70% of the time.  Behaviour 0x30 is started only there.  Its step 0x473F50
# clears the body's presence (0x473F8F) and calls the Roster of the Dead writer 0x464C70.
# Removal: the age credit 0x46FE90 removes (0x46FF12) a body whose stamp +0x1C38 -- updated only while health is
# above 0 -- is (real now - stamp) / 60 / the speed value >= 240 (0x46FEE9): 240 age units of real time at the
# current speed, paused time and closed time included; while paused the speed value is 999 more, so none is due.
#
# The writer 0x464C70: the first of 500 entries whose age is 0 (500 x 0x5C); none: returns with nothing written.
# Name +0, age +0x1C (record +0x1B8C: the age shown; it stops at death, as the age credit and life tick skip
# bodies), head +0x20, body +0x24, job +0x28 (0x4755C0: the highest of the six skills, strictly higher wins, so a
# tie goes to the first; -1 with every skill 0), its value +0x2C, Esteemed Elder +0x31 (0x475610: three or more
# skills at 88 or more), child +0x32 (under 280), male +0x33, cause +0x34, epitaph +0x38 (char[0x20]).
# Epitaph (0x464D27): under 360 age units rand(100) >= 50 -> 0x311 "Loving and Special", else 0x310 "Curious and
# Playful"; an Esteemed Elder: 0xD3 "Retired Chief" when puzzle 16 (The Heathen Chief) is solved and the role
# +0x1CFC is 13 (the Retired Chief), else 0x312 "Esteemed Elder"; else by job (table 0x464E5C), rand(100) >= 50
# the second: 0 Farmer 0x306/0x307, 1 Parent 0x30A/0x30B, 2 Doctor 0x30C/0x30D, 3 Scientist 0x308/0x309, 4 Builder
# 0x30E/0x30F; a Devotee (5) or no skill keeps 0x305 "Respected Citizen".  (tests/test_vv5_devoted_soul_epitaph.py
# runs the stock block for every job and every rand(100) value.)  The grave dialog 0x41C3F0 shows "Here Lies",
# the job's skill line ("Untrained" below 20, "Trainee " below 50, "Adept " below 88, "Master ") and the cause
# (0x314 + cause); Done copies its text box over the epitaph (0x41CB33), 31 characters at most.


# ---------------------------------------------------------------------------
# The Tree of Life (VV4)
# ---------------------------------------------------------------------------
#
# The same health and cause fields and setters as New Believers: 0x46AF40 (add), 0x46AF00 (set).  Life tick (every
# villager): 0x4684C1 food 500 or less -1 on 15% of age units, cause 1; 0x468567 no food, cause 1; 0x468600 sick, -1
# on 61% (19% at 20 health or less), cause 0; 0x46877F old age, set 0, cause 2 (threshold 1,100 + 160 x (Medicine -
# 1) at 0x468729).  Research 0x464BDB: 2% (0x464BBA) lose rand(10), cause 3.
# Island events (outcome = vtable slot 11; choice A 0, B 1), cause -1 unless said:
#   The Arc of Brilliant Colors 0x415090: "Run to the right side" ([esp+8] 1) when its roll [+0x10] is 0,
#     -(25 + rand(20));
#   The Phosphorescent Fungi 0x4153B0: "Throw it into the ocean": sick, -(15 + rand(5)); at 0 or less the cause is
#     set to 3 Work accident (0x415429); "Admire it from afar": each villager 30% sick (0x466F40, 30, no damage);
#   The Pink Shell 0x415760: "Pick it up and listen inside" -(5 + rand(6));
#   The Climber 0x4158E0: "Try to find a way down" -50;
#   The Sealed Box 0x415D60: "Swim back with the box" when its roll [+0x10] is not 0: health set to 0;
#   The Lie 0x415FA0: "Lie" -(25 + rand(26));
#   The Aspiring Doctor: sea water 0x4161E0 "Drink sea water" sick, -15; forbidden mushrooms 0x416360 "Eat a bit"
#     -(15 + rand(20)); bark 0x416430 "Eat a bit" +25 (heals); fasting 0x4164F0 "Fast" -(20 + rand(11)); cut leg
#     0x4165C0 either choice -(10 + rand(6));
#   The Aspiring Scientist 0x4166C0: "Try the salts" -(35 + rand(41));
#   Innovation in Construction 0x4167F0 / Innovation in Farming 0x416920: "Try the technique" / "Try standing on
#     fruit" when its roll [+0x10] is not 0: -(75 + rand(75));
#   Tough Lessons 0x416A50: "Climb the Tree", the adult -75;
#   The Stinging Wasps 0x414C50 (slot 12): every villager 50% (0x467040 with 50, 10, 10) -(10 + rand(10)), cause 0;
#   The State of the Tree (glum) 0x414EB0: every villager 10% -(5 + rand(10)), cause 0, then each 20% sick.
#   The Medical Emergency 0x415500 sets health 0 but its condition 0x4146E0 is always false and no patch offers it.
# Bodies: the villager AI 0x465840: 34% of picks (0x465889), not sick, not carrying, 14 or older, a body lying
# (0x466CE0): 25% (0x4658FD), else Healing 50 or more (0x461910, 50.0 at 0x4AA900) 70% (0x465923) -> behaviour
# 0x29 "Burying the dead" (0x453E50, registered at 0x45CC35); no puzzle is needed.  The burial step clears the
# presence (0x46A977) and calls the writer 0x45D470 (500 entries; job by 0x46AC20 over five skills; Scholar flag
# +0x31 by 0x46AC70: all five skills at 88 or more).  Epitaph 0x45D527: under 360, 0x313 "Curious and Playful" /
# 0x314 "Loving and Special" 50%; Scholar 0x315 "Scholar"; job table 0x45D638: Farmer 0x309/0x30A, Parent
# 0x30D/0x30E, Doctor 0x30F/0x310, Scientist 0x30B/0x30C, Builder 0x311/0x312; otherwise 0x308 "Respected
# Citizen".  The game's own words are its Assets\sm.xml's, the same as the exe's (Farmer's first: "Child Of the
# Earth").  Removal: 0x4664AD, the same 240 age units at the speed (manager +0x17110).
# Ghosts (0x414110, called with 1 by the mausoleum timer 0x43FE4B): when the roster holds graves (0x45D670 counts
# them up to the first empty), one is picked at random (rand(count), 0x414221) and a ghost record is made
# (0x466370: the ghost byte +0x1CC7, no name) with that grave's sex (+0x33), age at death (+0x1C), head (+0x20) and
# body (+0x24); it carries the collectible.  With no graves no ghost is made.  The step at 0x46A7CC calls the same
# spawn with 0 and never makes a ghost.


# ---------------------------------------------------------------------------
# The Secret City (VV3)
# ---------------------------------------------------------------------------
#
# Health record +0xE78, cause +0xE7C (the object +0xE6C): set 0x462670, add 0x4626B0, the same clamp and cause rule.
# Life tick 0x460030 (the same rules; old age at 0x4602E3, Medicine 0 to 3: 940 + 160 x Medicine age units, set 0 at
# 0x46033C, cause 2).  Research 0x459191: 2% (0x459177) lose rand(10), cause 3.  Island events (outcome slot 11,
# vtable start = its address - 0x2C), cause -1:
#   The Ant Hill 0x416AC0 "Poke the ant hill with a stick" -(5 + rand(10)); Bed Bugs 0x416E20 "Swat it" sick,
#   -(5 + rand(5)); The Mysterious Crate 0x417B00 "Open the crate" with its roll [+0x10] 1, -(10 + rand(20));
#   Vanity and the Bee 0x417D50 "Run to the water" -(15 + rand(10)); The Daredevil 0x4190C0 "He swims with sharks"
#   with its roll 1, -(5 + rand(6)); The Medical Emergency 0x417260 "Attempt the procedure" with its roll not 0,
#   health set to 0 (0x4172E6);
#   The Stinging Jellyfish 0x415220: every villager 50% (0x45D920 with 50, 10, 10) -(10 + rand(10)), cause 0;
#   The Tsunami 0x414B30 -> 0x45D990(15, -1): every living villager 15% has the presence byte cleared -- gone, no
#   body, no grave.
#   Two other losses never kill: 0x426C9F -(35 + rand(35)) but never below 2; 0x430C3E -(30 + rand(40)), then 1 at 0.
# Bodies: the AI 0x45C0BA: 34% of picks (rand(100) > 65), or always for the Tribal Chief (+0xE80); not sick (+0xE89),
# not carrying (+0xE8C); the Chief goes to bury a body (0x45C950) whenever one lies (0x45C13D); others 14 or older:
# 25% (0x45C191), else Healing (+0xEB4) 50 or more, 70% (0x45C1A9) -> behaviour 0x51 "Burying the dead" (0x4491F0,
# registered at 0x454106).  The burial clears the presence (0x462293) and calls the writer 0x454FF0: 500 entries x
# 0x30 (name, age +0x1C, job +0x20 by 0x462460 over five integer skills, strictly higher wins; Tribal Chief +0x28
# from record +0xE80; Esteemed Elder +0x29 by 0x462570, three or more skills at 88 or more; cause +0x2C); only an
# entry under 50 (0x455072) gets its gravestone (0x2C each: its place, the best value, the epitaph char[0x20]).
# Epitaph 0x4550AC: under 360 0x2E1 "Curious and Playful" / 0x2E2 "Loving and Special" 50%; the Tribal Chief 0x2E4
# "Wise and Beloved Chief"; an Esteemed Elder 0x2E3 "Esteemed Elder"; job table 0x4551E4: Farmer 0x2D7/0x2D8, Parent
# 0x2DB/0x2DC, Doctor 0x2DD/0x2DE, Scientist 0x2D9/0x2DA, Builder 0x2DF/0x2E0; else 0x2D6 "Respected Citizen".
# Removal 0x45F437: the same 240 age units (the stamp is health - 8, as in VV4 and VV5; the speed at +0x12F20; the
# wall clock 0x403330 counts real seconds from the save's epoch).

VV_STAMP = 0x9C                                 # VV3-VV5: the body's stamp, from the name (save record +0xBC)
ROSTER = 500
MORTALITY_VV3 = "vv3_nature_level_three_alters_mortality"

LATER = {
    5: dict(
        who="believer", whom="believers",
        causes="Old age, Disease, Starvation, Work accident or Unknown causes",
        game="New Believers",
        events=("Island events that can kill, all \"Unknown causes\" (their chances are under Island events): The "
                "Bed Bugs (\"Let it go\": 15 health), You're Doing It Wrong! (\"Teach them to reduce explosions.\" "
                "when it explodes: 10 to 29), The Missing Kids (\"Yell for help\": both children lose 5 and fall sick) "
                "and The Cracked Mask (\"Attempt to fix the mask\": 20 to 30). The Bed Bugs' \"Search for the bugs "
                "all night\" takes 5 only above 6 health, so it never kills, but it makes them sick."),
        burial_needs="Nobody buries anyone before The Buried Mausoleum is solved. After that, when",
        buriers=" Heathens never bury.",
        skills="Farming, Parenting, Healing, Research, Building, Devotion",
        jobs="Farmer, Parent, Doctor, Scientist, Builder or Devotee", apprentice="",
        elder=("with three or more skills at 88 or more, \"Esteemed Elder\" (the Retired Chief gets \"Retired "
               "Chief\" once The Heathen Chief is solved)"),
        farmer="Child of the Earth", default="a Devotee or a villager with no skill, \"Respected Citizen\"",
    ),
    4: dict(
        who="villager", whom="villagers",
        causes="Old age, Disease, Starvation, Work accident or Unknown causes",
        game="The Tree of Life",
        events=("Island events that can kill (their chances are under Island events), \"Unknown causes\" unless "
                "said: The Arc of Brilliant Colors (\"Run to the right side\" when it goes badly: 25 to 44 health), "
                "The Phosphorescent Fungi (\"Throw it into the ocean\": sick and 15 to 19; a death from it is "
                "\"Work accident\"), The Pink Shell (\"Pick it up and listen inside\": 5 to 10), The Climber (\"Try "
                "to find a way down\": 50), The Sealed Box (\"Swim back with the box\" when it goes badly: health "
                "to 0, always fatal), The Lie (\"Lie\": 25 to 50), The Aspiring Doctor (\"Drink sea water\": sick "
                "and 15; the forbidden mushrooms' \"Eat a bit\": 15 to 34; \"Fast\": 20 to 30; the cut leg, either "
                "choice: 10 to 15; the bark's \"Eat a bit\" heals 25 instead), The Aspiring Scientist (\"Try the "
                "salts\": 35 to 75), Innovation in Construction (\"Try the technique\") and Innovation in Farming "
                "(\"Try standing on fruit\") when they go badly: 75 to 149, Tough Lessons (\"Climb the Tree\": the "
                "adult loses 75), and, \"Disease\", The Stinging Wasps (each villager 50%: 10 to 19) and The State "
                "of the Tree when the villagers are glum (each villager 10%: 5 to 14, and 20% fall sick)."),
        burial_needs="When",
        buriers="",
        skills="Farming, Parenting, Healing, Research, Building",
        jobs="Farmer, Parent, Doctor, Scientist or Builder",
        apprentice=" (under 14 years, \"Apprentice\" instead of the rank)",
        elder="with all five skills at 88 or more, \"Scholar\"",
        farmer="Child Of the Earth", default="a villager with no skill, \"Respected Citizen\"",
    ),
    3: dict(
        who="villager", whom="villagers",
        causes="Old age, Disease, Starvation, Work accident or Unknown causes",
        game="The Secret City",
        events=("Island events that can kill, \"Unknown causes\" unless said (their chances are under Island "
                "events): The Ant Hill (\"Poke the ant hill with a stick\": 5 to 14 health), Bed Bugs (\"Swat it\": "
                "sick and 5 to 9), The Mysterious Crate (\"Open the crate\" when it goes badly: 10 to 29), Vanity and "
                "the Bee (\"Run to the water\": 15 to 24), The Daredevil (\"He swims with sharks\" when the crab "
                "bites: 5 to 10), The Medical Emergency (\"Attempt the procedure\" when it fails: health to 0, always "
                "fatal) and, \"Disease\", The Stinging Jellyfish (each villager 50%: 10 to 19)."),
        burial_needs=("The Tribal Chief, whenever he is not sick and picks something to do, goes to bury a body if "
                      "one lies. When any other"),
        buriers="",
        skills="Farming, Parenting, Healing, Research, Building",
        jobs="Farmer, Parent, Doctor, Scientist or Builder", apprentice="",
        elder=("the Tribal Chief, \"Wise and Beloved Chief\"; with three or more skills at 88 or more, \"Esteemed "
               "Elder\""),
        farmer="Child Of the Earth", default="a villager with no skill, \"Respected Citizen\"",
    ),
}


def _later(village: gm.Village, medicine: int | None, speed_value: int, base: int,
           nature: int = 0) -> list[gm.Fact]:
    """The Secret City's, The Tree of Life's and New Believers' lines (the addresses above); `nature`: The Secret
    City's Nature level (its patch moves the old-age rolls)."""
    c = LATER[village.game]
    game = village.game
    out: list[gm.Fact] = []

    def add(text: str, ok: bool | str = CODE, **kw) -> None:
        out.append(gm.Fact(DEATH, text, ok, **kw))

    speed = gm.speed_base(speed_value)
    on = gm.speed_name(speed)
    who, whom = c["who"], c["whom"]
    add(f"A {who} dies when their health (0 to 100) reaches 0. The grave's Cause of Death is the cause of the loss "
        f"that took it to 0, in the game's words: {c['causes']}."
        # The Secret City (the owner, 2026-10-25: a rule inherited from an earlier game that can never happen is never
        # listed): its unused Act of Nature cause is left out.
        + ("" if game == 3 else " The game also has the words Act of Nature, but nothing in this game ever gives "
                                "that cause."))
    if medicine in ((0, 1, 2, 3) if game == 3 else (1, 2, 3)):
        start = 55 + 8 * (medicine - 1)
        later = ""
        if game == 3 and nature >= 3 and village.has(MORTALITY_VV3):
            start += 7
            later = " and Nature level 3 with the patcher's mortality patch"
        add(f"Old age in this village (Medicine level {medicine}{later}): the first roll is at {start + 1} years "
            f"(10%), and at {start + 10} years it is 100%; cause \"Old age\".", gm.SAVE)
    add(f"Disease: a sick {who} loses 1 health on 61% of age units (19% at 20 health or less); dying of it gives "
        f"\"Disease\". How often {whom} fall sick is under Other.")
    add(f"Starvation: with 500 food or less a {who} loses 1 health on 15% of age units; with no food at all, by "
        "their hidden number (Hidden villager stats). Dying of it gives \"Starvation\".")
    # The 2% roll runs while catching up too: the catch-up flag skips only the 10% lab accident (VV5 0x46DB80 ->
    # 0x46DC67, VV4 0x464C3E -> 0x464BB0); The Secret City's roll has no test at all (0x45916D).
    add("Work accident: 2% of successful research tries cost the researcher 0 to 9 health, in play and while the "
        "game catches up; dying of it gives \"Work accident\".")
    add(c["events"])
    if game == 5:
        add("Heathens never age, eat or fall sick (the game runs none of that for them), so none of these reach "
            "them; a Heathen grave is never made.", gm.OWNER)
    if game == 3:
        add("Leaving without dying: The Tsunami sweeps away every living villager with a 15% chance each: they "
            "vanish, with no body and no grave (its chance is under Island events).")
    add("A mother who dies while nursing takes her babies with her: they were never villagers, so they leave no "
        "body and no grave.", gm.OWNER)
    if game == 5:
        add("Leaving without dying: a believer whose Faith falls to 0 becomes a Heathen and leaves the tribe (see "
            "the Faith lines). The God Power Revive (\"bring a fallen believer back!\") raises a body before it is "
            "buried or removed, and the Time Warp and Grant Youth God Powers change villagers' ages, and so when "
            "their old-age rolls come (see God Powers).")
    # Bodies
    add(f"A body lies where the villager died until a {who} buries it (\"Burying the dead\") or the game removes it. "
        f"{c['burial_needs']}{' a' if game != 3 else ''} {who} of 14 or more who is not sick or carrying picks something to do, 34% of the "
        "picks look for a body: they go to bury the lowest-numbered one 25% of the time, or 77.5% of the time with "
        f"Healing 50 or more.{c['buriers']}")
    add("A body nobody buries is removed with no grave once 240 age units (12 villager years) of real time have "
        "passed since the death at the game's speed then: 12 real-life hours on Fast, 24 on Normal, 40 on Slow. "
        "Time paused and time with the game closed count, so a body left when the game was closed can be gone as "
        "soon as it is next played; while paused, none is removed.")
    if not village.general:
        found = bodies(village)
        if not found:
            add("Unburied bodies in this save: none.", gm.SAVE)
        for name, at in found:
            due = base + _i32(village.data, at + VV_STAMP) + 240 * 60 * speed
            if speed_value >= gm.PAUSED:
                add(f"{name}'s body is unburied; saved paused, it is removed with no grave 240 age units after the "
                    "death once unpaused, unless buried first.", gm.SAVE)
            elif due <= village.now:
                add(f"{name}'s body is unburied and its 240 age units have passed: it is removed with no grave when "
                    "the village is next played.", gm.SAVE)
            else:
                add(f"{name}'s body is unburied: removed with no grave {gm.DUE} on {on} speed, unless buried "
                    "first.", gm.SAVE, due=float(due), due_kind="due")
    # Graves
    add("A burial writes the villager into the Roster of the Dead, 500 places. With all 500 used, a burial still "
        "takes the body but writes nothing: no grave. Nothing in the game ever removes a grave.")
    if game == 3:
        add("Only the first 50 graves of the Roster of the Dead get a gravestone, and only a gravestone has an "
            "epitaph: graves 51 to 500 have none.")
    add("Age at Death: the age the villager showed when they died (ages stop at death). It can be higher than "
        "the hidden processed age the old-age roll follows, after time away.")
    add("Cause of Death: the game's own, kept from the moment health reached 0 (above), shown on the grave in "
        "those words.")
    add(f"Job: the villager's highest skill (on a tie the first of {c['skills']}), shown \"Untrained\" below 20 or "
        "with every skill at 0, else \"Trainee\" below 50, \"Adept\" below 88, \"Master\" from 88"
        f"{c['apprentice']}, with {c['jobs']}.")
    add("Epitaph, chosen once at the burial: under 18 years, \"Curious and Playful\" or \"Loving and Special\" (50% "
        f"each); {c['elder']}; otherwise by the Job, 50% each: Farmer \"{c['farmer']}\" or \"Nature's Friend\", "
        "Parent \"Parent, Teacher, Friend\" or \"Dedicated to Children\", Doctor \"Guardian of Health\" or "
        "\"Dedicated to Others\", Scientist \"Dedicated Student\" or \"Inspired Inventor\", Builder \"Inspired "
        f"Architect\" or \"Strong Arms, Big Heart\"; {c['default']}. The player can type a new one (31 characters "
        "at most) on the grave.")
    if game == 4:
        add("The mausoleum's ghosts are not the dead coming back: each ghost visit makes a new ghost with no name and "
            "the sex, age at death, head and body of one grave picked at random from the Roster of the Dead (every "
            "grave equally, the same one can come again). With no graves, no ghost is made. When the visits come "
            "is under Collectibles.")
    # Patches
    if game == 5:
        soul = "vv5_devoted_soul_epitaph"
        if village.has(soul) is not False:
            # (The patch's own epitaph is named through the patch, never as a quoted text: no code here holds an
            # epitaph's words to check a grave by -- tests/test_vv5_devoted_soul_epitaph.py.)
            add("A Devotee's epitaph: normally always \"Respected Citizen\". "
                + gm.patch_words(village, soul, "\"Respected Citizen\" or the patch's own Charitable Soul, 50% each"))
        isola = "vv5_guardians_of_isola_rewrite"
        if village.has(isola) is not False:
            add(gm.patch_words(village, isola, "\"Respected Citizen\" reads \"Respected Devotee\" and \"Retired "
                                               "Chief\" reads \"Respected Chief\" on new graves (the words only)"))
    story = f"vv{game}_story_cheat_upgrades"
    if village.has(story):                      # only when it is known to be in: The Stinging Wasps is otherwise
        # never named for New Believers (tests/test_game_mechanics.py)
        extra = ("; Pick Island Event can choose The Stinging Wasps, never in the stock game, where every villager "
                 "has a 50% chance to lose 10 to 19 health, cause \"Disease\"") if game == 5 else ""
        add(gm.patch_words(village, story, "the Custom Island Event can make a villager die (the grave says "
                                           "\"Unknown causes\", the Deaths log \"Died in a custom island event\") or "
                                           "disappear (no body, no grave) and can revive bodies" + extra))
    cod = f"vv{game}_cause_of_death"
    if village.has(cod) is not False:
        add(gm.patch_words(village, cod, "every death is written to the Deaths log when the body is buried or "
                                         "removed, and a disappearance to a Disappeared record; the game itself "
                                         "is unchanged"))
    out += grave_lines(village, ROSTER, by_cause=True)
    out += log_lines(village)
    return out


# ---------------------------------------------------------------------------
# A New Home (VV1) and The Lost Children (VV2)
# ---------------------------------------------------------------------------
#
# Neither game keeps a cause: health only (VV1 record +0x344, VV2 +0x52C, 0 to 100).  The patcher's Cause of Death
# companion (native/vvfp_cause_of_death/cod_vv12.inc) records one at each site below, in New Believers' words.
# VV1 aging step 0x42E900: food 200 or less (0x42EC94) -1 on 50% of age units (0x42ECB2, rand(100) >= 50); no food
# (0x42ED0C) -1 unless rand(100) > 75 and not Hard (76%; always on Hard); sick (+0x354) -1 when rand(100) <= 70
# (71%), at 20 health or less also rand(100) <= 30 (22% in all); old age 0x42EE8A: Medicine (world +0xA2D4) gives
# 1,100 + 160 x (Medicine - 1) age units, rand(100) < 10 x years over sets 0 (0x42EF05).  Work injuries: 2% of job
# steps, rand(15) building, rand(10) research (0x43A5B4 ... 0x43B393).
# VV2 aging step 0x43B690: food 150 or less (0x43BAB2) -1 on 15% (50% x 30%); no food 76% unless the hidden number
# spares them (0x43BB45 ... 0x43BB79, as the later games); sick (+0x53C) 61%, 19% at 20 or less (0x43BC0E); old age
# the same rule (0x43BD89, set 0 at 0x43BDEE).  Work injuries: building steps rand(15) at 2% (one at 1%, 0x462981),
# research and the restorations rand(10) at 2% (0x46299C ... 0x4641B3).
# Bodies.  VV1 AI 0x448221: 34% of picks (0x448266), not sick, 14 or older (0x44828A), not carrying (0x4482A5); with
# The Cemetery solved (world +0xA000, 0x448307) and a body (0x43A200), always "Burying the dead" (0x443890, string
# 0xBA).  VV2 AI 0x461850: 34% of picks (0x461896), not sick (+0x53C), 14 or older (+0x530), not carrying (+0x540);
# a body (0x44B400): 25% (0x461994), else Healing (+0x7F0) 50 or more 70% (0x4619AC) -> 0x459290 ("Burying the
# dead", string 0x108).  Removal: VV1 0x42E9A2, VV2 0x43B76C: (real now - stamp) / 60 / the speed >= 240 (the stamp
# is health - 4: VV1 +0x340, VV2 +0x528).
# Graves: 50 each.  VV1 0x448F70: the first grave whose age is 0 (name, best value +0x1C, job +0x20 by 0x43B520,
# age +0x24); none: no grave.  VV2 0x465042: the same over 50 x 0x7C, and the epitaph into +0x19 (0x4650D4): under
# 360 string 0x1EE "Curious And Playful" / 0x1EF "Loving And Special" (rand(100) < 50 the first); a villager with a
# totem (+0x7FC, set by the totem maker 0x44D4A2) 0x1F0 "Esteemed Elder"; else the highest skill, starting from
# Parenting (+0x7E4), then Building (+0x7E8), Healing (+0x7F0), Farming (+0x7EC), Research (+0x7F4), each taking the
# place only when strictly higher; by its table 0x46542C: Farming 0x1E4/0x1E5, Parenting 0x1E8/0x1E9, Healing
# 0x1EA/0x1EB, Research 0x1E6/0x1E7, Building 0x1EC/0x1ED, 50% each (the string table 0x496300).

EARLY_STAMP = {1: -0x30, 2: -0x3C}             # the body's stamp, from the name
GRAVES_EARLY = 50
MAGIC_FRUIT = "vv1_magic_fruit_alters_mortality"


def _bodies_lines(village: gm.Village, add, base: int, speed_value: int, stamp: int) -> None:
    speed = gm.speed_base(speed_value)
    if village.general:
        return
    found = bodies(village)
    if not found:
        add("Unburied bodies in this save: none.", gm.SAVE)
    for name, at in found:
        due = base + _i32(village.data, at + stamp) + 240 * 60 * speed
        if speed_value >= gm.PAUSED:
            add(f"{name}'s body is unburied; saved paused, it is removed with no grave 240 age units after the "
                "death once unpaused, unless buried first.", gm.SAVE)
        elif due <= village.now:
            add(f"{name}'s body is unburied and its 240 age units have passed: it is removed with no grave when "
                "the village is next played.", gm.SAVE)
        else:
            add(f"{name}'s body is unburied: removed with no grave {gm.DUE} on {gm.speed_name(speed)} speed, unless "
                "buried first.", gm.SAVE, due=float(due), due_kind="due")


REMOVAL = ("A body nobody buries is removed with no grave once 240 age units (12 villager years) of real time have "
           "passed since the death at the game's speed then: 12 real-life hours on Fast, 24 on Normal, 40 on Slow. "
           "Time paused and time with the game closed count, so a body left when the game was closed can be gone as "
           "soon as it is next played; while paused, none is removed.")


def _early(village: gm.Village, medicine: int | None, speed_value: int, base: int,
           magic_fruit: bool = False) -> list[gm.Fact]:
    """A New Home's and The Lost Children's lines (the addresses above)."""
    game = village.game
    out: list[gm.Fact] = []

    def add(text: str, ok: bool | str = CODE, **kw) -> None:
        out.append(gm.Fact(DEATH, text, ok, **kw))

    cod = f"vv{game}_cause_of_death"
    add("A villager dies when their health (0 to 100) reaches 0. The game itself keeps no cause of death; the "
        "patcher's Cause of Death patch records one at that moment, in New Believers' words: Old age, Disease, "
        "Starvation, Work accident, or Unknown causes for anything else (island events).")
    if medicine in (1, 2, 3):
        start = 55 + 8 * (medicine - 1)
        later = ""
        if game == 1 and magic_fruit and village.has(MAGIC_FRUIT):
            start += 7
            later = " and the Magic Fruit of Life with the patcher's mortality patch"
        add(f"Old age in this village (Medicine level {medicine}{later}): the first roll is at {start + 1} years "
            f"(10%), and at {start + 10} years it is 100%.", gm.SAVE)
    if game == 1:
        add("Disease: a sick villager loses 1 health on 71% of age units (22% at 20 health or less).")
        add("Starvation: with 200 food or less a villager loses 1 health on 50% of age units; with no food at all on "
            "76% (every one on Hard).")
        add("Work accident: 2% of building steps cost 0 to 14 health, 2% of research steps 0 to 9.")
        add("Island events that can kill or remove a villager (from the patcher's island-event research; their "
            "chances are under Island events): The Strange Berries (one result of tasting them: the villager dies), "
            "The Wild Mushroom (poisoned: sick and 25 to 49 health), A Mysterious Crate of rotting fruit (rats bite "
            "20%, 30% or 45% of villagers: sick and 10, 15 or 20) and of old fruit (spiders: the finder loses 40, 70 "
            "or 110); The Mysterious Face (\"take a closer look\": the villager can be never seen again) and The Book "
            "(reading it: the villager can vanish) leave no body and no grave.", False)
        add("The Golden Child never starves, falls sick or dies of old age; how island events can still kill him "
            "or make him vanish, and the patches that change it, is under Golden Child.")
    else:
        add("Disease: a sick villager loses 1 health on 61% of age units (19% at 20 health or less).")
        add("Starvation: with 150 food or less a villager loses 1 health on 15% of age units; with no food at all, "
            "by their hidden number (Hidden villager stats).")
        add("Work accident: 2% of building steps cost 0 to 14 health (1% for one of them), 2% of research and "
            "restoration steps 0 to 9.")
        add("Island events that can kill (from the patcher's island-event research; their chances are under Island "
            "events): Rats! (each bitten villager falls sick and loses 60 health), A Bump On The Head (bonking: "
            "10), A Mysterious Sack of thick canvas (the finder falls sick and loses 15; mice bite 20%, 30% or 45% "
            "of villagers for 10, 15 or 20) and of heavy burlap (fire ants: the finder loses 40, 70 or 110).", False)
        add("An Esteemed Elder's totem is not a death: the game makes it as a separate record copied from the elder, "
            "who lives on (see the Esteemed Elders line).")
    add("A mother who dies while nursing takes her babies with her: they were never villagers, so they leave no "
        "body and no grave.", gm.OWNER)
    if game == 1:
        add("A body lies where the villager died until a villager buries it (\"Burying the dead\") or the game "
            "removes it. Nobody buries anyone before The Cemetery is solved. After that, when a villager of 14 or more "
            "who is not sick or carrying picks something to do, 34% of the picks look for a body, and then they "
            "always go to bury it.")
    else:
        add("A body lies where the villager died until a villager buries it (\"Burying the dead\") or the game "
            "removes it. When a villager of 14 or more who is not sick or carrying picks something to do, 34% of the "
            "picks look for a body: they go to bury it 25% of the time, or 77.5% of the time with Healing 50 or "
            "more.")
    add(REMOVAL)
    _bodies_lines(village, add, base, speed_value, EARLY_STAMP[game])
    add("A burial takes the first free grave of 50; with all 50 used it still takes the body but makes no grave. "
        "The game treats a grave whose age is 0 as free, so a villager buried at age 0 loses their grave to the "
        "next burial. Nothing else removes a grave.")
    add("Age at Death: the age the villager showed when they died (ages stop at death). It can be higher than "
        "the hidden processed age the old-age roll follows, after time away.")
    master = 90 if game == 1 else 88
    jobs = "Farmer, Parent, Scientist, Builder or Doctor" if game == 1 else "Farmer, Parent, Doctor, Scientist or Builder"
    add(f"Job: the villager's best skill, shown \"Untrained\" below 20, else \"Trainee\" below 50, \"Adept\" below "
        f"{master}, \"Master\" from {master}, with {jobs}.")
    if game == 1:
        add("Epitaph: the game has none.")
    else:
        add("Epitaph, chosen once at the burial: under 18 years, \"Curious And Playful\" or \"Loving And Special\" "
            "(50% each); a villager whose totem stands, \"Esteemed Elder\"; otherwise by their highest skill (on a "
            "tie the first of Parenting, Building, Healing, Farming, Research), 50% each: Farming \"Child Of The "
            "Earth\" or \"Nature's Friend\", Parenting \"Parent, Teacher, Friend\" or \"Dedicated To Children\", "
            "Healing \"Guardian Of Health\" or \"Dedicated To Others\", Research \"Dedicated Student\" or \"Inspired "
            "Inventor\", Building \"Inspired Architect\" or \"Strong Arms, Big Heart\". With every skill at 0 that is "
            "Parenting's pair; there is no other. The player can type a new one (64 characters at most) on the "
            "grave.")
    if village.has(cod) is not False:
        extra = ("; it also gives each new grave an epitaph by New Believers' rule (under 18 years \"Curious and "
                 "Playful\" or \"Loving and Special\", otherwise the pair for the grave's job, \"Respected Citizen\" "
                 "with no skill; each pair 50% either way), which the player can retype (31 characters at most)") if game == 1 else ""
        add(gm.patch_words(village, cod, "the grave shows the recorded cause, a child's grave (under 14 years) says "
                                         "\"Apprentice\" instead of the rank, and every death goes into the Deaths "
                                         "log" + extra))
    if game == 2:
        fix = "vv2_fix_vanilla_bugs"
        if village.has(fix) is not False:
            add("Normally the game can bury an Esteemed Elder's totem as if it were a body, making a grave for an "
                "elder who still lives. " + gm.patch_words(village, fix, "a totem is never buried"))
    story = f"vv{game}_story_cheat_upgrades"
    if village.has(story):
        add(gm.patch_words(village, story, "the Custom Island Event can make a villager die (the patcher records "
                                           "\"Died in a custom island event\") or disappear (no body, no grave) and "
                                           "can revive bodies"))
    out += grave_lines(village, GRAVES_EARLY, by_cause=False)
    out += log_lines(village)
    return out


def facts(village: gm.Village, **kw) -> list[gm.Fact]:
    """The Death and graves lines for `village`'s game: every game takes medicine, speed_value and base (the save's
    clock base, Unix seconds); The Secret City also nature, A New Home magic_fruit (the Magic Fruit of Life solved)."""
    if village.game in LATER:
        return _later(village, kw.get("medicine"), kw["speed_value"], kw["base"], kw.get("nature", 0))
    return _early(village, kw.get("medicine"), kw["speed_value"], kw["base"], kw.get("magic_fruit", False))
