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

VV5_STAMP = 0x9C                                # the body's stamp, from the name (save record +0xBC)
VV5_ROSTER = 500
VV5_CAUSES = ("Old age", "Disease", "Starvation", "Work accident", "Unknown causes", "Act of Nature")


def _vv5(village: gm.Village, medicine: int | None, speed_value: int, base: int) -> list[gm.Fact]:
    add_to: list[gm.Fact] = []

    def add(text: str, ok: bool | str = CODE, **kw) -> None:
        add_to.append(gm.Fact(DEATH, text, ok, **kw))

    speed = gm.speed_base(speed_value)
    on = gm.speed_name(speed)
    add("A believer dies when their health (0 to 100) reaches 0. The grave's Cause of Death is the cause of the "
        "loss that took it to 0, in the game's words: Old age, Disease, Starvation, Work accident or Unknown causes. "
        "The game also has the words Act of Nature, but nothing in New Believers ever gives that cause.")
    if medicine in (1, 2, 3):
        start = 55 + 8 * (medicine - 1)
        add(f"Old age in this village (Medicine level {medicine}): the first roll is at {start + 1} years "
            f"(10%), and at {start + 10} years it is 100%; cause \"Old age\".", gm.SAVE)
    add("Disease: a sick believer loses 1 health on 61% of age units (19% at 20 health or less); dying of it gives "
        "\"Disease\". How often believers fall sick is under Other.")
    add("Starvation: with 500 food or less a believer loses 1 health on 15% of age units; with no food at all, by "
        "their hidden number (Hidden villager stats). Dying of it gives \"Starvation\".")
    add("Work accident: 2% of research tries in play cost the researcher 0 to 9 health (never while the game "
        "catches up); dying of it gives \"Work accident\".")
    add("Island events that can kill, all \"Unknown causes\" (their chances are under Island events): The Bed Bugs "
        "(\"Let it go\": 15 health), You're Doing It Wrong! (\"Teach them to reduce explosions.\" when it explodes: 10 "
        "to 29), The Missing Kids (\"Yell for help\": both children lose 5 and fall sick) and The Cracked Mask "
        "(\"Attempt to fix the mask\": 20 to 30). The Bed Bugs' \"Search for the bugs all night\" takes 5 only above "
        "6 health, so it never kills, but it makes them sick.")
    add("Heathens never age, eat or fall sick (the game runs none of that for them), so none of these reach them; "
        "a Heathen grave is never made.", gm.OWNER)
    add("A mother who dies while nursing takes her babies with her: they were never villagers, so they leave no "
        "body and no grave.", gm.OWNER)
    add("Leaving without dying: a believer whose Faith falls to 0 becomes a Heathen and leaves the tribe (see the "
        "Faith lines). The God Power Revive (\"bring a fallen believer back!\") raises a body before it is buried or "
        "removed, and the Time Warp and Grant Youth God Powers change villagers' ages, and so when their old-age "
        "rolls come (see God Powers).")
    # Bodies
    add("A body lies where the villager died until a believer buries it (\"Burying the dead\") or the game removes "
        "it. Nobody buries anyone before The Buried Mausoleum is solved. After that, when a believer of 14 or more "
        "who is not sick or carrying picks something to do, 34% of the picks look for a body: they go to bury the "
        "lowest-numbered one 25% of the time, or 77.5% of the time with Healing 50 or more. Heathens never bury.")
    add(f"A body nobody buries is removed with no grave once 240 age units (12 villager years) of real time have "
        f"passed since the death at the game's speed then: 12 real-life hours on Fast, 24 on Normal, 40 on Slow. "
        f"Time paused and time with the game closed count, so a body left when the game was closed can be gone as "
        f"soon as it is next played; while paused, none is removed.")
    if not village.general:
        found = bodies(village)
        if not found:
            add("Unburied bodies in this save: none.", gm.SAVE)
        for name, at in found:
            stamp = _i32(village.data, at + VV5_STAMP)
            due = base + stamp + 240 * 60 * speed
            if speed_value >= gm.PAUSED:
                add(f"{name}'s body is unburied; saved paused, it is removed with no grave 240 age units after the "
                    f"death once unpaused, unless buried first.", gm.SAVE)
            elif due <= village.now:
                add(f"{name}'s body is unburied and its 240 age units have passed: it is removed with no grave when "
                    "the village is next played.", gm.SAVE)
            else:
                add(f"{name}'s body is unburied: removed with no grave {gm.DUE} on {on} speed, unless buried "
                    "first.", gm.SAVE, due=float(due), due_kind="due")
    # Graves
    add("A burial writes the villager into the Roster of the Dead, 500 places. With all 500 used, a burial still "
        "takes the body but writes nothing: no grave. Nothing in the game ever removes a grave.")
    add("Age at Death: the age the villager showed when they died (ages stop at death). It can be higher than "
        "the hidden processed age the old-age roll follows, after time away.")
    add("Cause of Death: the game's own, kept from the moment health reached 0 (above), shown on the grave in "
        "those words.")
    add("Job: the villager's highest skill (on a tie the first of Farming, Parenting, Healing, Research, Building, "
        "Devotion), shown \"Untrained\" below 20 or with every skill at 0, else \"Trainee\" below 50, \"Adept\" below "
        "88, \"Master\" from 88, with Farmer, Parent, Doctor, Scientist, Builder or Devotee.")
    add("Epitaph, chosen once at the burial: under 18 years, \"Curious and Playful\" or \"Loving and Special\" (50% "
        "each); with three or more skills at 88 or more, \"Esteemed Elder\" (the Retired Chief gets \"Retired "
        "Chief\" once The Heathen Chief is solved); otherwise by the Job, 50% each: Farmer \"Child of the Earth\" or "
        "\"Nature's Friend\", Parent \"Parent, Teacher, Friend\" or \"Dedicated to Children\", Doctor \"Guardian of "
        "Health\" or \"Dedicated to Others\", Scientist \"Dedicated Student\" or \"Inspired Inventor\", Builder "
        "\"Inspired Architect\" or \"Strong Arms, Big Heart\"; a Devotee or a villager with no skill, \"Respected "
        "Citizen\". The player can type a new one (31 characters at most) on the grave.")
    # Patches
    soul = "vv5_devoted_soul_epitaph"
    if village.has(soul) is not False:
        # (The patch's own epitaph is named through the patch, never as a quoted text: no code here holds an
        # epitaph's words to check a grave by -- tests/test_vv5_devoted_soul_epitaph.py.)
        add("A Devotee's epitaph: normally always \"Respected Citizen\". "
            + gm.patch_words(village, soul, "\"Respected Citizen\" or the patch's own Charitable Soul, 50% each"))
    isola = "vv5_guardians_of_isola_rewrite"
    if village.has(isola) is not False:
        add(gm.patch_words(village, isola, "\"Respected Citizen\" reads \"Respected Devotee\" and \"Retired Chief\" "
                                           "reads \"Respected Chief\" on new graves (the words only)"))
    story = "vv5_story_cheat_upgrades"
    if village.has(story):                      # only when it is known to be in: The Stinging Wasps is otherwise
                                                # never named for New Believers (tests/test_game_mechanics.py)
        add(gm.patch_words(village, story, "the Custom Island Event can make a villager die (the grave says "
                                           "\"Unknown causes\", the Deaths log \"Died in a custom island event\") or "
                                           "disappear (no body, no grave) and can revive bodies; Pick Island Event "
                                           "can choose The Stinging Wasps, never in the stock game, where every "
                                           "villager has a 50% chance to lose 10 to 19 health, cause \"Disease\""))
    cod = "vv5_cause_of_death"
    if village.has(cod) is not False:
        add(gm.patch_words(village, cod, "every death is written to the Deaths log when the body is buried or "
                                         "removed, and a disappearance to a Disappeared record; the game itself "
                                         "is unchanged"))
    add_to += grave_lines(village, VV5_ROSTER, by_cause=True)
    add_to += log_lines(village)
    return add_to


def facts(village: gm.Village, **kw) -> list[gm.Fact]:
    """The Death and graves lines for `village`'s game (see each game's helper for the keywords it takes)."""
    if village.game == 5:
        return _vv5(village, kw.get("medicine"), kw["speed_value"], kw["base"])
    return []
