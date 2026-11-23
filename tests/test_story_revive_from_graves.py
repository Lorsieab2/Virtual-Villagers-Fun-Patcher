"""Revive Buried/Disappeared Villagers (the owner, 2026-11-22), all five games.

The owner: an upgrade in the Tech screen's upgrades menu costing 100,000 tech points that lists every buried
villager and every villager who vanished, with what the logs and graves record; the one picked comes back as the
SAME PERSON at age 5, their grave is removed, it is refused at the village's maximum population with nothing
charged, and it can be bought again and again.

Everything here runs the shipped bytes: each game's executable as the patcher renders it (all three population
modes), with the test build of "VVFP Story Upgrades.dll" mapped beside it in the emulator (tests/story_emulator.py)
and the villagers laid out where each game keeps them (tests/story_custom_fixtures.py).  The game's creator and
room predicate are the Custom Island Event tests' stubs (tests/test_story_custom_island_event.py Story); the log
texts are handed to the list builder directly (VvfpStoryProbeReviveLoad), the graves are written where each game
keeps them (native/vvfp_story_upgrades/story_revive.inc).
"""
from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

from test_story_custom_island_event import (  # noqa: E402
    GAMES,
    HAVE_EMULATOR,
    MODES,
    Story,
    emulated,
    have_stock,
)

if HAVE_EMULATOR:
    from story_emulator import HEAP

SOURCE = ROOT / "native" / "vvfp_story_upgrades" / "story_revive.inc"
PRICE = 100000

# Where each game keeps its tech points (story_c*.inc c<N>_tech): a world offset, or a static.
TECH = {"vv1": ("world", 0xA2FC), "vv2": ("world", 0x2EADC), "vv3": ("static", 0x582644),
        "vv4": ("static", 0x4D6F88), "vv5": ("static", 0x51D5F8)}

# The graveyards (story_revive.inc rv_graveyard): first entry (world offset or static), stride, name bytes, age.
YARDS = {
    "vv1": ("world", 0xA31C, 0x2C, 0x1C, 0x24),
    "vv2": ("world", 0x2EB0C, 0x7C, 0x19, 0x74),
    "vv3": ("static", 0x5973F0 + 0x974, 0x30, 0x19, 0x1C),
    "vv4": ("static", 0x5025C8, 0x5C, 0x19, 0x1C),
    "vv5": ("static", 0x5481A8, 0x5C, 0x19, 0x1C),
}
VV3_DEAD = 0x5973F0
def _exported_skill_names():
    """The labels the Village History exporter prints (native/population_export/population_export.c), read from its
    source: A New Home's Parenting is "Breeding" there (Codex, #851)."""
    import re
    source = (ROOT / "native" / "population_export" / "population_export.c").read_text(encoding="utf-8")
    out = {}
    for n in range(1, 6):
        body = re.search(r"SKILL_NAMES_VV%d\[MAX_SKILLS\] = \{(.*?)\};" % n, source, re.S).group(1)
        out[f"vv{n}"] = [s for s in re.findall(r'"([^"]+)"', body) if not s.startswith("(")]
    return out


EXPORTED_SKILLS = _exported_skill_names()
SKILLS = {
    "vv1": ["Parenting", "Building", "Farming", "Healing", "Research"],
    "vv2": ["Parenting", "Building", "Farming", "Healing", "Research"],
    "vv3": ["Farming", "Parenting", "Healing", "Research", "Building"],
    "vv4": ["Farming", "Parenting", "Healing", "Research", "Building"],
    "vv5": ["Farming", "Parenting", "Healing", "Research", "Building", "Devotion"],
}

SCRATCH = HEAP + 0x3E00000 if HAVE_EMULATOR else 0
DEATHS_BUF = SCRATCH
HISTORY_BUF = SCRATCH + 0x8000
LINE_BUF = SCRATCH + 0x10000
DETAIL_BUF = SCRATCH + 0x11000
OUT = SCRATCH + 0x13000


def death(number, name, age, sex, head, body, likes="(none)", dislikes="(none)", grave="Master Farmer",
          cause="Old age", extra="", parents=""):
    return (f"Death {number}\n  Name: {name}\n{extra}  Age at death: {age}\n  Sex: {sex}\n"
            f"  Cause of death: {cause}\n  Grave: {grave}\n  Epitaph: Loved by all\n"
            f"  Head: {head}\n  Body: {body}\n  Likes: {likes}\n  Dislikes: {dislikes}\n{parents}\n")


def gone(name, age, sex, head, body, what="Swept away by the Tsunami", extra=""):
    return (f"Disappeared\n  Name: {name}\n{extra}  Age: {age}\n  Sex: {sex}\n  What happened: {what}\n"
            f"  Head: {head}\n  Body: {body}\n  Likes: (none)\n  Dislikes: crowds\n\n")


PARENTS = ("  Parents:\n    Father: Tano Rua\n      Head: 7\n      Body: 8\n"
           "    Mother: Mira Rua\n      Head: 9\n      Body: 10\n")


def history(game, name, age, sex, head, body, values):
    lines = [f"=== Virtual Villagers -- 2026-11-22 10:00:00 ===", "Village: Test (Save 1)", "",
             "Villager 1", f"  Name: {name}", f"  Age: {age}", f"  Sex: {sex}", f"  Head: {head}",
             f"  Body: {body}", "  Skills:"]
    lines += [f"    {skill:<10} {value}" for skill, value in zip(EXPORTED_SKILLS[game], values)]
    return "\n".join(lines) + "\n\n"


class Revive:
    """One game's process with the Story companion installed, a village and its graveyard."""

    def __init__(self, game, mode="collection_progression"):
        self.s = Story(game, mode)
        self.game = game
        self.p = self.s.proc
        self.v = self.s.village
        self.p.export("VvfpStoryProbeReviveOffered", 1)
        self.p.export("VvfpStoryProbeReviveCharges", self.s.n, 1)   # "cost Tech Points" ticked (the default)
        self.told = []
        self._watch_arrivals()
        if game == "vv3":
            for k in range(55):                       # the game's own clear (0x4549F0): no stone, no burier
                self.p.put32(VV3_DEAD + k * 0x2C, 0xFFFFFFFF)
            for k in range(55):
                self.p.put32(VV3_DEAD + 0x6734 + 4 * k, 0xFFFFFFFF)
            self.p.put32(VV3_DEAD + 0x6810, 0)
        self.set_tech(150000)

    def _watch_arrivals(self):
        p = self.p
        exports = {"VvfpCauseArrivedBy": p.alloc(0x10), "VvfpCauseArrivedParents": p.alloc(0x10)}
        p.api_handlers["GetModuleHandleA"] = lambda q: (
            0x73000000 if q.cstring(q.arg(0)) == "VVFP Cause of Death.dll" else 0, 4)
        p.api_handlers["GetProcAddress"] = lambda q: (exports.get(q.cstring(q.arg(1)), 0), 8)
        p.stub(exports["VvfpCauseArrivedBy"], lambda q: (self.told.append(
            ("how", q.arg(0), q.arg(1), q.cstring(q.arg(2)))) or 0, 12))
        p.stub(exports["VvfpCauseArrivedParents"], lambda q: (self.told.append(
            ("parents", q.arg(0), q.arg(1), q.cstring(q.arg(2)))) or 0, 12))
        p.api_handlers["GetSystemTimeAsFileTime"] = lambda q: (q.write(q.arg(0), bytes(8)) or 0, 4)

    # -- the village --------------------------------------------------------------------------------------------
    def _at(self, where, offset):
        return self.v.world + offset if where == "world" else offset

    def tech(self):
        return struct.unpack("<i", self.p.read(self._at(*TECH[self.game]), 4))[0]

    def set_tech(self, value):
        self.p.put32(self._at(*TECH[self.game]), value)

    def grave_at(self, place):
        where, first, stride, name_bytes, age = YARDS[self.game]
        return self._at(where, first) + place * stride

    def bury(self, place, name, age, head=0, body=0):
        where, first, stride, name_bytes, age_at = YARDS[self.game]
        g = self.grave_at(place)
        self.p.write(g, bytes(stride))
        self.p.write(g, name.encode() + b"\0")
        self.p.put32(g + age_at, age)
        if self.game in ("vv4", "vv5"):
            self.p.put32(g + 0x20, head)
            self.p.put32(g + 0x24, body)
            self.p.write(g + 0x38, b"Rest well " + name.encode()[:8] + b"\0")
        if self.game == "vv2":
            self.p.write(g + 0x19, b"Rest well\0")
        if self.game == "vv3" and place < 50:
            stone = VV3_DEAD + place * 0x2C
            self.p.write(stone, bytes(0x2C))
            self.p.put32(stone, place)
            self.p.put32(stone + 4, 77)
            self.p.write(stone + 8, b"Stone of " + name.encode()[:8] + b"\0")

    def grave_name(self, place):
        raw = self.p.read(self.grave_at(place), YARDS[self.game][3])
        return raw.split(b"\0")[0].decode()

    def grave_age(self, place):
        return struct.unpack("<i", self.p.read(self.grave_at(place) + YARDS[self.game][4], 4))[0]

    # -- the companion ------------------------------------------------------------------------------------------
    def load(self, deaths, history_text=None):
        self.p.write(DEATHS_BUF, deaths.encode("latin-1") + b"\0")
        if history_text is not None:
            self.p.write(HISTORY_BUF, history_text.encode("latin-1") + b"\0")
        return self.p.export("VvfpStoryProbeReviveLoad", self.s.n, DEATHS_BUF,
                             HISTORY_BUF if history_text is not None else 0)

    def row(self, k):
        who = self.p.export("VvfpStoryProbeReviveRow", k, LINE_BUF, DETAIL_BUF, 4096)
        return who, self.p.cstring(LINE_BUF), self.p.cstring(DETAIL_BUF)

    def state(self, k):
        ok = self.p.export("VvfpStoryProbeReviveState", k, OUT)
        return ok, struct.unpack("<i", self.p.read(OUT, 4))[0]

    def buy(self, k):
        answer = self.p.export("VvfpStoryProbeReviveBuy", k, OUT)
        answer = answer - (1 << 32) if answer & 0x80000000 else answer
        return answer, struct.unpack("<i", self.p.read(OUT, 4))[0]

    def rows(self):
        return [self.row(k)[1] for k in range(64) if self.row(k)[0] != 0xFFFFFFFF]



@emulated
class ListTests(unittest.TestCase):
    def _each(self, mode="collection_progression"):
        for game in GAMES:
            if have_stock(game):
                yield game, Revive(game, mode)

    def test_buried_and_vanished_villagers_are_listed_with_what_the_logs_hold(self):
        for game, r in self._each():
            r.bury(0, "Ana Rua", 1300, 5, 6)
            text = (death(1, "Ana Rua", 1300, "Female", 5, 6, likes="ants, turnips", dislikes="the ocean",
                          extra="  Custom title: The Wise\n", parents=PARENTS)
                    + gone("Kai Moana", 500, "Male", 11, 12))
            n = r.load(text, history(game, "Ana Rua", 1280, "Female", 5, 6, [40, 50, 60, 70, 80, 90]))
            with self.subTest(game=game):
                self.assertEqual(n, 2)
                who, line, details = r.row(0)          # the newest record first
                self.assertEqual(line, "Kai Moana, male, vanished at 25")
                self.assertIn("What happened: Swept away by the Tsunami", details)
                self.assertIn("Skills: unknown", details)
                self.assertEqual(r.state(0), (1, -1))
                who, line, details = r.row(1)
                self.assertEqual(line, "Ana Rua, female, died at 65 - buried")
                for want in ("Age at death: 65 years (1300 age units)", "Cause of death: Old age",
                             "Grave: Master Farmer", "Custom title: The Wise", "Head: 5", "Body: 6",
                             "Likes: ants, turnips", "Dislikes: the ocean", "Father: Tano Rua", "Mother: Mira Rua",
                             "Comes back as this same person at age 5."):
                    self.assertIn(want, details)
                for skill, value in zip(SKILLS[game], [40, 50, 60, 70, 80, 90]):
                    self.assertIn(f"    {skill} {value}", details)
                self.assertEqual(r.state(1), (1, 0))

    def test_a_villager_in_the_village_now_is_not_listed(self):
        for game, r in self._each():
            r.v.put(0, sex="f", years=30, name="Ana Rua", head=5, body=6)
            with self.subTest(game=game):
                self.assertEqual(r.load(death(1, "Ana Rua", 1300, "Female", 5, 6)), 0)
                # a namesake with other looks is someone else
                self.assertEqual(r.load(death(1, "Ana Rua", 1300, "Female", 7, 6)), 1)

    def test_one_person_twice_is_listed_once_from_their_newest_record(self):
        for game, r in self._each():
            text = death(1, "Ana Rua", 1300, "Female", 5, 6) + death(2, "Ana Rua", 400, "Female", 5, 6)
            with self.subTest(game=game):
                self.assertEqual(r.load(text), 1)
                self.assertIn("Death record: Death 2", r.row(0)[2])

    def test_records_the_game_can_not_recreate_are_listed_and_refused(self):
        for game, r in self._each():
            text = ("Death 1\n  Name: Nobody Known\n  Age at death: 300\n  Grave: Untrained\n\n"
                    + death(2, "Odd Likes", 300, "Male", 1, 1, likes="flying carpets"))
            with self.subTest(game=game):
                self.assertEqual(r.load(text), 2)
                for k in range(2):
                    self.assertEqual(r.state(k)[0], 0)
                    self.assertEqual(r.buy(k)[0], -3)
                self.assertIn("Can not come back: the log does not hold their likes and dislikes.", r.row(0)[2])
                self.assertIn("Can not come back: the log does not say who they were (name or sex).", r.row(1)[2])
                self.assertEqual(r.tech(), 150000)

    def test_special_villagers_who_can_not_come_back(self):
        cases = {
            "vv1": death(1, "Goldie", 100, "Male", 1, 1, extra="  Special villager: Golden Child\n"),
            "vv5": death(1, "Moma", 800, "Female", 1, 1, extra="  Special villager: Heathen Mommy\n"),
        }
        for game, r in self._each():
            if game not in cases:
                continue
            with self.subTest(game=game):
                self.assertEqual(r.load(cases[game]), 1)
                self.assertEqual(r.state(0)[0], 0)
                self.assertEqual(r.buy(0)[0], -3)
        for game, r in self._each():
            if game != "vv5":
                continue
            # either wording the logs use: "a Heathen", or "an Isolan" with Guardians of Isola (Codex, #851)
            for word in ("a Heathen", "an Isolan"):
                with self.subTest(left_as=word):
                    text = gone("Nobu Helaku", 266, "Male", 26, 26, what=f"Left the tribe: became {word}")
                    self.assertEqual(r.load(text), 1)
                    self.assertIn("they did not die: they live among the Heathens", r.row(0)[2])
                    self.assertEqual(r.buy(0)[0], -3)

    def test_special_villagers_who_come_back_as_ordinary_villagers(self):
        cases = {"vv2": "Esteemed Elder", "vv3": "Tribal Chief", "vv4": "Scholar", "vv5": "Former Heathen (blue mask)"}
        for game, r in self._each():
            if game not in cases:
                continue
            with self.subTest(game=game):
                r.load(death(1, "Sami", 1500, "Male", 2, 2, extra=f"  Special villager: {cases[game]}\n"))
                self.assertEqual(r.state(0)[0], 1)
                self.assertIn(f"Special villager: {cases[game]} (they come back as an ordinary villager)",
                              r.row(0)[2])


@emulated
class PurchaseTests(unittest.TestCase):
    def _each(self, modes=("collection_progression",)):
        for game in GAMES:
            if have_stock(game):
                for mode in modes:
                    yield game, mode, Revive(game, mode)

    def _ana(self, r, game):
        r.bury(0, "Ana Rua", 1300, 5, 6)
        r.bury(1, "Other Grave", 900, 3, 3)
        text = death(1, "Ana Rua", 1300, "Female", 5, 6, likes="ants, turnips", dislikes="the ocean",
                     extra="  Mask: Blue Mask\n", parents=PARENTS)
        self.assertEqual(r.load(text, history(game, "Ana Rua", 1280, "Female", 5, 6, [40, 50, 60, 70, 80, 90])), 1)

    def test_the_same_person_comes_back_at_five_and_the_grave_goes(self):
        for game, mode, r in self._each(MODES):
            with self.subTest(game=game, mode=mode):
                self._ana(r, game)
                answer, made = r.buy(0)
                self.assertEqual(answer, 1)
                L = r.v.L
                # the game's own creator made them, at age 100 (five years)
                self.assertEqual(r.s.creations, [(made, L["sex"][2], 100)])
                self.assertEqual(r.v.name(made), "Ana Rua")
                self.assertEqual((r.v.i32(made, L["head"]), r.v.i32(made, L["body"])), (5, 6))
                likes = [x for x in r.v.prefs(made, "likes") if x != -1]
                dislikes = [x for x in r.v.prefs(made, "dislikes") if x != -1]
                self.assertEqual((sorted(likes), dislikes), ([0, 5], [17]))
                for k, value in enumerate([40, 50, 60, 70, 80, 90][:L["skill_count"]]):
                    self.assertEqual(r.v.skill(made, k), value)
                self.assertEqual(r.s.host.masks.get(r.v.record(made)), 1)
                # charged once, exactly the price
                self.assertEqual(r.tech(), 150000 - PRICE)
                # logged: an Arrived record "Returned from the dead", with the parents
                self.assertIn(("how", r.s.n, made, "Returned from the dead"), r.told)
                parents = [t for t in r.told if t[0] == "parents"]
                self.assertEqual(len(parents), 1)
                self.assertIn("Father: Tano Rua\n      Head: 7\n      Body: 8", parents[0][3])
                # the grave is gone, the other grave kept
                if game in ("vv1", "vv2"):
                    self.assertEqual((r.grave_name(0), r.grave_age(0)), ("", 0))
                    self.assertEqual((r.grave_name(1), r.grave_age(1)), ("Other Grave", 900))
                else:
                    self.assertEqual((r.grave_name(0), r.grave_age(0)), ("Other Grave", 900))
                    self.assertEqual((r.grave_name(1), r.grave_age(1)), ("", 0))
                if game == "vv3":
                    self.assertEqual(r.p.u32(VV3_DEAD), 0)                       # stone 0: entry 0 ...
                    self.assertEqual(r.p.cstring(VV3_DEAD + 8), "Stone of Other Gr")   # ... with its own stone
                    self.assertEqual(r.p.u32(VV3_DEAD + 0x2C), 0xFFFFFFFF)       # stone 1: none
                # not listed again: they are in the village now
                self.assertEqual(r.buy(0)[0], -3)
                self.assertEqual(r.load(death(1, "Ana Rua", 1300, "Female", 5, 6, likes="ants, turnips",
                                              dislikes="the ocean")), 0)

    def test_refused_at_the_maximum_population_with_nothing_charged(self):
        for game, mode, r in self._each(MODES):
            with self.subTest(game=game, mode=mode):
                self._ana(r, game)
                r.s.room[0] = False
                self.assertEqual(r.p.export("VvfpStoryProbeReviveRefusal", r.s.n), 0xFFFFFFFF)   # RV_NO_ROOM
                self.assertEqual(r.buy(0), (-1, -1))
                self.assertEqual(r.s.creations, [])
                self.assertEqual(r.tech(), 150000)
                self.assertEqual(r.grave_name(0), "Ana Rua")
                self.assertIn("maximum population",
                              (SOURCE.read_text(encoding="utf-8")))

    def test_refused_without_the_price_and_never_below_zero(self):
        for game, mode, r in self._each():
            with self.subTest(game=game):
                self._ana(r, game)
                r.set_tech(PRICE - 1)
                self.assertEqual(r.buy(0), (-2, -1))
                self.assertEqual(r.tech(), PRICE - 1)
                self.assertEqual(r.s.creations, [])
                r.set_tech(PRICE)
                self.assertEqual(r.buy(0)[0], 1)
                self.assertEqual(r.tech(), 0)

    def test_it_can_be_bought_again_and_again(self):
        for game, mode, r in self._each():
            with self.subTest(game=game):
                r.set_tech(3 * PRICE)
                text = (death(1, "Ana Rua", 1300, "Female", 5, 6) + death(2, "Beni Rua", 700, "Male", 8, 9)
                        + gone("Kai Moana", 500, "Male", 11, 12))
                self.assertEqual(r.load(text), 3)
                for k in range(3):
                    self.assertEqual(r.buy(k)[0], 1)
                self.assertEqual(r.tech(), 0)
                self.assertEqual(sorted(r.v.name(i) for i, _, _ in r.s.creations),
                                 ["Ana Rua", "Beni Rua", "Kai Moana"])

    def test_a_grave_that_changed_since_the_list_is_never_removed(self):
        for game, mode, r in self._each():
            with self.subTest(game=game):
                self._ana(r, game)
                r.bury(0, "Someone Else", 1300, 5, 6)
                self.assertEqual(r.buy(0), (-4, -1))
                self.assertEqual((r.grave_name(0), r.tech()), ("Someone Else", 150000))


@emulated
class HeathenTests(unittest.TestCase):
    """New Believers: every log records the Heathens, "Faction: Heathen" / "Isolan" (the owner, 2026-11-23, PR
    #850), "so the player can decide to resurrect them with the new upgrade"; one comes back a Heathen in the camp
    (story_revive.inc RV_HEATHENS_STAY_HEATHENS), through the game's own Heathen creator 0x46FD20."""

    def test_a_dead_heathen_is_listed_and_comes_back_a_heathen(self):
        if not have_stock("vv5"):
            self.skipTest("no stock executable")
        for word in ("Heathen", "Isolan"):
            r = Revive("vv5")
            made = []

            def heathen(q):
                index = r.s._create(r.v.L["sex"][2] if q.arg(3) == 1 else r.v.L["sex"][1], q.arg(4))
                made.append((index, q.arg(3), q.arg(4), q.arg(8) - (1 << 32) if q.arg(8) & 0x80000000 else q.arg(8)))
                r.p.write(r.v.record(index) + 0x1CEC, b"\1")
                return index, 0x24
            r.p.stub(0x46FD20, heathen)
            text = (gone("Tuku Old", 1500, "Female", 4, 5, what="Died of old age",
                         extra=f"  Faction: {word}\n")
                    + death(1, "Rua Grave", 900, "Male", 6, 7, extra=f"  Faction: {word}\n"))
            with self.subTest(word=word):
                self.assertEqual(r.load(text), 2)
                self.assertIn("Faction: Heathen", r.row(0)[2])
                self.assertIn("a Heathen in the camp", r.row(0)[2])
                self.assertTrue(r.row(0)[1].endswith(" - a Heathen"))
                answer, index = r.buy(0)
                self.assertEqual(answer, 1)
                self.assertEqual(made, [(index, 0, 100, -55)])        # the newest first: Rua, male, age 100, faith -55
                self.assertEqual(r.s.creations[-1][0], index)
                self.assertEqual(r.v.name(index), "Rua Grave")
                self.assertEqual(r.tech(), 150000 - PRICE)
                # a living Heathen with that whole identity is in the village: not listed again
                self.assertEqual(r.load(text), 1)

@emulated
class PriceTests(unittest.TestCase):
    """The owner (2026-11-23): the price follows "Story / Cheat Upgrades cost Tech Points" like the other story
    upgrades -- 100,000 tech points with it ticked, free with it unticked."""

    def test_free_while_the_story_upgrades_are_free(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            r = Revive(game)
            r.p.export("VvfpStoryProbeReviveCharges", r.s.n, 0)
            r.set_tech(0)
            with self.subTest(game=game):
                self.assertEqual(r.p.export("VvfpStoryRevivePrice", r.s.n), 0)
                self.assertEqual(r.load(death(1, "Ana Rua", 1300, "Female", 5, 6)), 1)
                self.assertEqual(r.buy(0)[0], 1)
                self.assertEqual(r.tech(), 0)

    def test_100000_while_they_cost_tech_points(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            r = Revive(game)
            with self.subTest(game=game):
                self.assertEqual(r.p.export("VvfpStoryRevivePrice", r.s.n), PRICE)
                r.load(death(1, "Ana Rua", 1300, "Female", 5, 6))
                r.set_tech(PRICE - 1)
                self.assertEqual(r.buy(0), (-2, -1))
                r.set_tech(PRICE + 7)
                self.assertEqual(r.buy(0)[0], 1)
                self.assertEqual(r.tech(), 7)


@emulated
class LongLogTests(unittest.TestCase):
    """Codex (#851): a log of more than 400 records still lists the newest deaths, one entry per person."""

    def test_the_newest_records_of_a_long_log_are_listed(self):
        for game in ("vv1", "vv5"):
            if not have_stock(game):
                continue
            r = Revive(game)
            text = "".join(death(k + 1, f"P{k:04d} Rua", 300 + k, "Male" if k % 2 else "Female", k % 20, (k // 20) % 20)
                           for k in range(450))
            text += "".join(death(451 + k, "Ana Rua", 400, "Female", 5, 6) for k in range(300))
            text += death(999, "Last One", 1200, "Male", 3, 3)
            with self.subTest(game=game):
                self.assertEqual(r.load(text), 452)
                self.assertTrue(r.row(0)[1].startswith("Last One"))
                self.assertTrue(r.row(1)[1].startswith("Ana Rua"))
                self.assertIn("Death record: Death 750", r.row(1)[2])
                self.assertTrue(r.row(451)[1].startswith("P0000 Rua"))


@emulated
class ExportedSkillNamesTests(unittest.TestCase):
    def test_a_new_homes_breeding_label_is_parenting(self):
        if not have_stock("vv1"):
            self.skipTest("no stock executable")
        self.assertEqual(EXPORTED_SKILLS["vv1"][0], "Breeding")
        r = Revive("vv1")
        r.load(death(1, "Ana Rua", 1300, "Female", 5, 6), history("vv1", "Ana Rua", 1280, "Female", 5, 6,
                                                                    [40, 50, 60, 70, 80]))
        self.assertIn("    Parenting 40", r.row(0)[2])
        answer, made = r.buy(0)
        self.assertEqual(answer, 1)
        self.assertEqual(r.v.skill(made, 0), 40)


@emulated
class LongTextTests(unittest.TestCase):
    """Codex (#851): The Lost Children keeps 62 likes and 62 dislikes, a Custom Island Event can fill them, and its
    own cause words run to 4,095 characters.  The details never write past a buffer and show every word: nothing is
    dropped for length (the window's text box wraps and scrolls).  wsprintfA is answered as Windows answers it, at
    most 1,024 bytes, so a list ever formatted through it would come back cut."""

    @staticmethod
    def _vv2_words():
        import re
        source = (ROOT / "native" / "vvfp_story_upgrades" / "story_c2.inc").read_text(encoding="utf-8")
        body = source[source.index('"The Lost Children",'):]
        body = body[body.index("62, 62,") + len("62, 62,"):]
        literal = re.match(r'\s*((?:"[^"]*"\s*)+),', body).group(1)
        return "".join(re.findall(r'"([^"]*)"', literal)).split(",")

    def test_62_likes_and_dislikes_and_the_longest_texts_are_shown_whole(self):
        if not have_stock("vv2"):
            self.skipTest("no stock executable")
        r = Revive("vv2")
        p = r.p
        plain = p._api_wsprintfA

        def windows_wsprintf(q):
            value, pop = plain()
            out = q.arg(0)
            text = q.cstring(out)
            if len(text) > 1023:                 # Windows' wsprintfA writes at most 1,024 bytes, NUL included
                q.write(out + 1023, b"\0")
                value = 1023
            return value, pop
        p.api_handlers["wsprintfA"] = windows_wsprintf
        words = self._vv2_words()
        self.assertEqual(len(words), 62)
        name = "Abcdefghij Klmnopqrstuv"                  # 23 characters, the most VV2 holds
        title = "T" * 31
        epitaph = "E" * 64
        cause = ("A long cause in the event's own words. " * 105)[:4095]
        text = (f"Death 1\n  Name: {name}\n  Custom title: {title}\n  Age at death: 1300\n  Sex: Female\n"
                f"  Cause of death: {cause}\n  Grave: Master Farmer\n  Epitaph: {epitaph}\n  Head: 5\n  Body: 6\n"
                f"  Likes: {', '.join(words)}\n  Dislikes: {', '.join(words)}\n" + PARENTS + "\n")
        self.assertEqual(r.load(text), 1)
        line, details = p.alloc(0x2000), p.alloc(0x8000)
        self.assertEqual(p.export("VvfpStoryProbeReviveRow", 0, line, details, 0x8000), 0)
        shown = p.cstring(details)
        self.assertIn(f"Name: {name}\r\n", shown)
        self.assertIn(f"Custom title: {title}\r\n", shown)
        self.assertIn(f"Epitaph: {epitaph}\r\n", shown)
        self.assertIn(f"Cause of death: {cause}\r\n", shown)
        self.assertIn("Likes: " + ", ".join(words) + "\r\n", shown)
        self.assertIn("Dislikes: " + ", ".join(words) + "\r\n", shown)
        answer, made = r.buy(0)
        self.assertEqual(answer, 1)
        self.assertEqual(sorted(r.v.prefs(made, "likes")), list(range(62)))
        self.assertEqual(sorted(r.v.prefs(made, "dislikes")), list(range(62)))
        self.assertEqual(r.v.name(made), name)

@emulated
class GraveyardTests(unittest.TestCase):
    def test_the_later_games_keep_their_graves_in_one_unbroken_run(self):
        for game in ("vv3", "vv4", "vv5"):
            if not have_stock(game):
                continue
            r = Revive(game)
            for k in range(5):
                r.bury(k, f"G{k}", 100 + k)
            with self.subTest(game=game):
                self.assertEqual(r.p.export("VvfpStoryProbeReviveRemoveGrave", r.s.n, 2), 1)
                self.assertEqual([r.grave_name(k) for k in range(5)], ["G0", "G1", "G3", "G4", ""])
                self.assertEqual(r.grave_age(4), 0)
                # the game's own grave count (VV3 0x454BC0's run, VV4 0x45D670, VV5 0x464E90) sees four
                count_va, this = {"vv3": (0x454BC0, VV3_DEAD), "vv4": (0x45D670, 0x5025C8),
                                  "vv5": (0x464E90, 0x5481A8)}[game]
                self.assertEqual(r.p.call(count_va, ecx=this) & 0xFFFF, 4)

    def test_the_secret_citys_51st_grave_gets_the_writers_own_stone(self):
        if not have_stock("vv3"):
            self.skipTest("no stock executable")
        r = Revive("vv3")
        for k in range(52):
            r.bury(k, f"G{k}", 1000 + k)
        text_va = r.p.alloc(0x40)
        r.p.write(text_va, b"Epitaph from the table\0")
        table = r.p.alloc(0x10)
        ids = []
        r.p.stub(0x42F740, lambda q: (table, 0))
        r.p.stub(0x42F190, lambda q: (ids.append(q.arg(0)) or text_va, 4))
        r.p.stub(0x4032D0, lambda q: (10, 0))
        self.assertEqual(r.p.export("VvfpStoryProbeReviveRemoveGrave", 3, 0), 1)
        self.assertEqual(r.grave_name(49), "G50")
        self.assertEqual(r.p.u32(VV3_DEAD + 49 * 0x2C), 49)
        self.assertEqual(r.p.cstring(VV3_DEAD + 49 * 0x2C + 8), "Epitaph from the table")
        self.assertEqual(len(ids), 1)
        self.assertEqual(r.p.cstring(VV3_DEAD + 48 * 0x2C + 8), "Stone of G49")
        self.assertEqual(r.p.call(0x454B10, ecx=VV3_DEAD) & 0xFFFF, 50)

    def test_the_first_two_games_empty_the_grave_in_its_own_place(self):
        for game in ("vv1", "vv2"):
            if not have_stock(game):
                continue
            r = Revive(game)
            for k in range(3):
                r.bury(k, f"G{k}", 100 + k)
            with self.subTest(game=game):
                self.assertEqual(r.p.export("VvfpStoryProbeReviveRemoveGrave", r.s.n, 1), 1)
                self.assertEqual([r.grave_name(k) for k in range(3)], ["G0", "", "G2"])
                self.assertEqual(r.p.read(r.grave_at(1), YARDS[game][2]), bytes(YARDS[game][2]))


class RowTests(unittest.TestCase):
    """The patcher's side: one row per game, the flag file, the dependency and the defaults."""

    def setUp(self):
        import vv_fun_patcher as patcher
        self.patcher = patcher

    def rows(self):
        return {g: json.loads((ROOT / "data" / f"{g}_revive_from_graves_feature.json").read_text(encoding="utf-8"))
                for g in GAMES}

    def test_one_row_per_game_with_its_flag_file(self):
        import hashlib
        flag = ROOT / "assets" / "story_upgrades" / "VVFP Revive From Graves.txt"
        digest = hashlib.sha256(flag.read_bytes()).hexdigest().upper()
        for game, row in self.rows().items():
            with self.subTest(game=game):
                self.assertEqual(row["id"], f"{game}_revive_from_graves")
                self.assertEqual(row["name"], "Revive Buried/Disappeared Villagers")
                self.assertEqual(row["dependencies"], [f"{game}_story_cheat_upgrades"])
                self.assertEqual(row["patches"], [])
                self.assertEqual(row["companion_files"], [{
                    "source": "assets/story_upgrades/VVFP Revive From Graves.txt",
                    "destination": "VVFP Revive From Graves.txt", "sha256": digest}])
                self.assertIn("**Needs Story / Cheat Upgrades", row["description"])
                self.assertIn("100,000 tech points", row["description"])

    def test_off_by_default_and_on_in_owners_defaults(self):
        import vv_fun_patcher_gui as gui
        for game in GAMES:
            with self.subTest(game=game):
                self.assertIn(f"{game}_revive_from_graves", gui.DEFAULT_OFF_FUN_PATCH_IDS)
                # Owner's Defaults ticks every default-off patch it does not name (the owner, 2026-11-22: "ON in
                # Owner's Defaults").
                self.assertNotIn(f"{game}_revive_from_graves", gui.OWNERS_DEFAULT_OFF_FUN_PATCH_IDS)

    def test_the_patcher_loads_every_row(self):
        ids = {p.id for p in self.patcher.load_public_fun_patches()}
        for game in GAMES:
            self.assertIn(f"{game}_revive_from_graves", ids)

    def test_the_story_companion_looks_for_the_flag_file(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn('#define RV_FLAG_FILE "VVFP Revive From Graves.txt"', source)
        self.assertIn("#define RV_PRICE 100000", source)
        self.assertIn("#define RV_AGE 100", source)


class BridgeTests(unittest.TestCase):
    """Every Origins companion's Tech menu has the button and sends its click to the Story companion."""

    COMPANIONS = {
        "vv1": "native/vv1_origins_icons/vv1_origins_icons.c",
        "vv2": "native/vv2_origins_icons/vv2_origins_icons.c",
        "vv3": "native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c",
        "vv4": "native/vv4_origins_icons/vv4_origins_icons.c",
        "vv5": "native/vv5_task9_origins/vv5_task9_origins.c",
    }

    def test_each_tech_menu_adds_and_dispatches_the_button(self):
        bridge = (ROOT / "native/shared/story_bridge.h").read_text(encoding="utf-8")
        self.assertIn("#define VVFP_STORY_REVIVE_ID 4095", bridge)
        self.assertIn('"Revive Buried/Disappeared Villagers"', bridge)
        self.assertIn("VvfpStoryReviveFromGraves", bridge)
        for game, path in self.COMPANIONS.items():
            source = (ROOT / path).read_text(encoding="utf-8")
            with self.subTest(game=game):
                self.assertIn("vvfp_story_add_revive_button(", source)
                self.assertIn("VVFP_STORY_REVIVE_ID", source)


if __name__ == "__main__":
    unittest.main()
