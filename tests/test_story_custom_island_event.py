"""Story / Cheat Upgrades, part 2: Custom Island Event (all five games).

The owner: "Custom Island Event -- Allows the player to create and trigger a
custom Island Event for storytelling, testing, sandbox play, or cheats ...
available options must be determined separately for VV1, VV2, VV3, VV4, and
VV5 from each game's actual executable/data structures ... Unsupported
properties should be omitted or disabled rather than approximated."

Everything here runs the shipped bytes: each game's executable as the patcher
renders it (all three population modes), with the test build of "VVFP Story
Upgrades.dll" mapped beside it in an emulator (tests/story_emulator.py), and
the villagers laid out where each game keeps them
(tests/story_custom_fixtures.py).  Game routines are run for real wherever
they can run on their own; the ones that need the whole game (the creators,
the AI resets, the conversions) are replaced by stubs that check the
arguments the companion passes and do what the routine does to the record.

* every offered option, applied per game, writes exactly the fields the
  game's own code writes for it, and nothing outside the villager it names;
* the target list: the five group toggles, the list's own selection and the
  de-duplication, with each game's own adult boundary;
* delivery through each game's own island-event path (VV1 / VV2: the
  island event's chooser call; VV3-VV5: the selector's chosen object), the
  family rolls, the Origins Barrel pass-through and the shared lock;
* every refusal: the first island event, no adult, a full village (each
  game's own room predicate, in all three population modes), a changed
  villager, invalid text, out-of-range values;
* the custom title in each game's villager panel.

The .dat persistence and the Start Over reset run against real files in
native harnesses (tests/test_custom_titles_persistence.py).
"""
from __future__ import annotations

import functools
import json
import os
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402
from story_custom_fixtures import (  # noqa: E402
    KEEP,
    LAYOUTS,
    PARENTS,
    RESULT_SIZE,
    Change,
    Event,
    Spawn,
    Village,
    fnv_name,
    unpack_result,
)

try:
    import pefile  # noqa: F401
    from story_emulator import HEAP, Process

    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")
MODES = ("stock", "collection_progression", "immediate_fixed")
TEST_DLL = Path(os.environ.get(
    "VVFP_STORY_TEST_DLL", ROOT / "tests" / "test_dlls" / "VVFP Story Upgrades.test.dll"))
TEST_BUILD_ABSENT = "test builds are not in the release source archive (tests/test_dlls)"
SOURCE = ROOT / "native" / "vvfp_story_upgrades"
TEN_MINUTES = 10 * 60 * 1000

# Fixed emulator addresses the tests use for their own data.
EVENT_BUF = HEAP + 0x3E00000 if HAVE_EMULATOR else 0
RESULT_BUF = EVENT_BUF + 0x10000
TEXT_BUF = EVENT_BUF + 0x11000
SCRATCH = EVENT_BUF + 0x14000


@functools.lru_cache(maxsize=None)
def _builds():
    return {build.id: build for build in patcher.load_builds()}


def stock_path(game: str) -> Path:
    return ROOT / "inputs" / f"{game}-stock-copy" / _builds()[game].input_name


def have_stock(game: str) -> bool:
    return stock_path(game).is_file()


@functools.lru_cache(maxsize=None)
def render(game: str, mode: str) -> bytes:
    ids = [f"{game}_origins_village_wide_upgrades", f"{game}_story_cheat_upgrades"]
    data, _ = patcher.render_patched_bytes(stock_path(game), _builds()[game], mode, ids)
    return bytes(data)


@functools.lru_cache(maxsize=None)
def render_full(game: str, mode: str) -> bytes:
    """The whole public catalog (the Parentage row's hooks included) --
    except the experimental 256-slot build, whose own tests compose it."""
    ids = [p.id for p in patcher.load_public_fun_patches()
           if p.game_id == game and p.id not in patcher.EXPERIMENTAL_FUN_PATCH_IDS]
    data, _ = patcher.render_patched_bytes(stock_path(game), _builds()[game], mode, ids)
    return bytes(data)


def emulated(cls):
    return unittest.skipUnless(HAVE_EMULATOR, "capstone/unicorn/pefile not installed")(
        unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)(cls))


class Host:
    """The Origins companion's side (native/shared/story_bridge.h): its save
    slot and its mask store, as stubs the test can read."""

    def __init__(self, proc, game: int, slot: int = 1, bracket: bool = False):
        self.proc = proc
        self.masks: dict[int, int] = {}
        self.brackets: list[int] = []
        code = proc.alloc(0x100)
        proc.write(code, b"\xC3" * 0x40)
        self.table = proc.alloc(0x20)
        fns = [code, code + 0x10, code + 0x20, code + 0x30 if bracket else 0]
        proc.write(self.table, struct.pack("<5I", 20, *fns))
        self.slot = slot
        proc.stub(code, lambda p: (self.slot, 0))
        proc.stub(code + 0x10, lambda p: (self.masks.get(p.arg(0), 0), 4))

        def mask_set(p):
            self.masks[p.arg(0)] = p.arg(1)
            return 1, 8
        proc.stub(code + 0x20, mask_set)

        def bracket_fn(p):
            self.brackets.append(p.arg(0))
            return 0, 4
        if bracket:
            proc.stub(code + 0x30, bracket_fn)
        assert proc.export("VvfpStoryAttachHost", game, self.table) == 1


class Story:
    """One game's process with the companion installed and a village."""

    def __init__(self, game: str, mode: str = "collection_progression", *, full: bool = False,
                 slot: int = 1):
        self.game = game
        self.n = int(game[2:])
        self.proc = Process(render_full(game, mode) if full else render(game, mode), TEST_DLL)
        assert self.proc.export("VvfpStoryInstall", self.n) == 1
        self.village = Village(self.proc, game)
        self.host = Host(self.proc, self.n, slot, bracket=(game == "vv3"))
        self.room = [True]
        self.creations: list[tuple] = []
        self.calls: dict[int, list] = {}
        self._stub_room_and_creator()

    # -- the game routines the adapters call --------------------------------
    def record_call(self, va, pop, value=0):
        def fn(p):
            self.calls.setdefault(va, []).append(
                [p.reg("ecx")] + [p.arg(i) for i in range(pop // 4)])
            return value, pop
        self.proc.stub(va, fn)

    def room_answer(self, p):
        return (1 if self.room[0] else 0), 0

    def _create(self, sex_raw, age):
        v = self.village
        L = v.L
        for i in range(L["count"]):
            if v.byte(i, L["active"]) == 0:
                v.put(i, sex="m" if sex_raw == L["sex"][1] else "f", years=age / 20, name="Newborn")
                self.creations.append((i, sex_raw, age))
                return i
        return -1

    def _stub_room_and_creator(self):
        p = self.proc
        g = self.game
        room_va = {"vv1": 0x43A1A0, "vv2": 0x44B310, "vv3": 0x45FE30, "vv4": 0x468350,
                   "vv5": 0x472BD0}[g]
        p.stub(room_va, self.room_answer)
        creator = {"vv1": 0x43C350, "vv2": 0x44F580, "vv3": 0x45FF50, "vv4": 0x467D10,
                   "vv5": 0x471E20}[g]

        def create(proc):
            args = [proc.arg(i) for i in range(5)]
            self.calls.setdefault(creator, []).append([proc.reg("ecx")] + args)
            return self._create(args[3], args[4]) & 0xFFFFFFFF, 0x14
        p.stub(creator, create)

    # -- the engine -------------------------------------------------------
    def apply(self, event: Event):
        event.game = self.n
        self.proc.write(EVENT_BUF, event.pack())
        ok = self.proc.export("VvfpStoryProbeApply", self.n, EVENT_BUF, RESULT_BUF, TEXT_BUF, 4096)
        return ok, unpack_result(self.proc.read(RESULT_BUF, RESULT_SIZE)), self.proc.cstring(TEXT_BUF)

    def refusal(self, event: Event):
        event.game = self.n
        self.proc.write(EVENT_BUF, event.pack())
        at = self.proc.export("VvfpStoryProbeRefusal", self.n, EVENT_BUF)
        return None if at == 0 else self.proc.cstring(at)

    def change(self, i: int, **fields) -> Change:
        return Change(index=i, fingerprint=self.village.identity(i), **fields)


# ---------------------------------------------------------------------------
# The layout the tests pack is the companion's own
# ---------------------------------------------------------------------------

@emulated
class LayoutTests(unittest.TestCase):
    def test_the_event_structures_match_story_custom_h(self):
        if not have_stock("vv3"):
            self.skipTest("no stock executable")
        proc = Process(render("vv3", "stock"), TEST_DLL)
        proc.export("VvfpStoryProbeSizes", SCRATCH)
        sizes = struct.unpack("<7i", proc.read(SCRATCH, 28))
        self.assertEqual(sizes, (Event.SIZE, Event.SPAWN_SIZE, Change.SIZE, RESULT_SIZE, 680, 1800, 1804))


# ---------------------------------------------------------------------------
# The target list: group toggles, the list's selection, de-duplication
# ---------------------------------------------------------------------------

T_ADULT_WOMEN, T_ADULT_MEN, T_FEMALES, T_MALES, T_CHILDREN = 1, 2, 4, 8, 16

# (record index, sex, age in years): two adults of each sex, a child of each
# sex, one villager at exactly the adult boundary (14 years = 280 units) and
# one a unit below it, a corpse, and an empty record between them.
ROSTER = [(0, "f", 30), (1, "m", 40), (3, "f", 14), (4, "m", 13.95), (5, "f", 8),
          (6, "m", 2), (7, "m", 60), (8, "f", 70)]


def _populate(story):
    v = story.village
    for i, sex, years in ROSTER:
        v.put(i, sex=sex, years=years, name=f"V{i}")
    v.put(9, sex="m", years=30, name="Corpse", health=0)
    if story.game == "vv2":
        # A totem statue is a record too, never a villager.
        v.put(10, sex="m", years=30, name="Statue")
        story.proc.put32(v.record(10) + 0x558, 1)
    if story.game == "vv4":
        v.put(10, sex="m", years=30, name="Ghost")
        story.proc.write(v.record(10) + 0x1CC7, b"\1")
    if story.game == "vv5":
        v.put(10, sex="m", years=30, name="Spirit")
        story.proc.write(v.record(10) + 0x1CE1, b"\1")


def _targets(story, toggles, picked_indices=()):
    roster_indices = [i for i, _, _ in ROSTER]
    picked = bytes(1 if i in picked_indices else 0 for i in roster_indices) + bytes(256)
    story.proc.write(SCRATCH, picked)
    n = story.proc.export("VvfpStoryProbeTargets", story.n, SCRATCH, toggles, SCRATCH + 0x400, 256)
    return list(struct.unpack(f"<{n}i", story.proc.read(SCRATCH + 0x400, 4 * n)))


@emulated
class TargetTests(unittest.TestCase):
    def _each(self):
        for game in GAMES:
            if have_stock(game):
                story = Story(game)
                _populate(story)
                yield game, story

    def test_each_toggle_alone(self):
        expected = {
            T_ADULT_WOMEN: [0, 3, 8],      # 14 years is adult in every game
            T_ADULT_MEN: [1, 7],
            T_FEMALES: [0, 3, 5, 8],
            T_MALES: [1, 4, 6, 7],
            T_CHILDREN: [4, 5, 6],         # 13.95 years is still a child
        }
        for game, story in self._each():
            for toggle, want in expected.items():
                with self.subTest(game=game, toggle=toggle):
                    self.assertEqual(_targets(story, toggle), want)

    def test_toggles_combine_and_count_each_villager_once(self):
        for game, story in self._each():
            with self.subTest(game=game):
                # every adult woman is also a female: still once each
                self.assertEqual(_targets(story, T_ADULT_WOMEN | T_FEMALES), [0, 3, 5, 8])
                self.assertEqual(_targets(story, T_ADULT_MEN | T_CHILDREN), [1, 4, 5, 6, 7])
                self.assertEqual(_targets(story, 31), [0, 1, 3, 4, 5, 6, 7, 8])

    def test_list_selection_combines_with_toggles_without_duplicates(self):
        for game, story in self._each():
            with self.subTest(game=game):
                # picked 1 and 5 (Ctrl+click), toggle All Children also has 5
                self.assertEqual(_targets(story, T_CHILDREN, (1, 5)), [1, 4, 5, 6])
                # a Shift+click range 3..6 alone
                self.assertEqual(_targets(story, 0, (3, 4, 5, 6)), [3, 4, 5, 6])
                self.assertEqual(_targets(story, 0), [])

    def test_the_dead_and_non_villagers_are_never_targets(self):
        for game, story in self._each():
            with self.subTest(game=game):
                everyone = _targets(story, 31)
                self.assertNotIn(9, everyone)          # a corpse
                self.assertNotIn(2, everyone)          # an empty record
                self.assertNotIn(10, everyone)         # statue / ghost / spirit


# New Believers' Heathen toggles (story_targets.h).
T_HEATHENS, T_BLUE, T_RED, T_ORANGE, T_PURPLE, T_CHIEF, T_MOMMIES = (
    0x20, 0x40, 0x80, 0x100, 0x200, 0x400, 0x800)


def _role(story, i):
    kind = story.proc.export("VvfpStoryProbeRole", story.n, i, SCRATCH, 96)
    return kind, story.proc.cstring(SCRATCH)


@emulated
class RoleTests(unittest.TestCase):
    """The list shows what the game itself makes of each villager, and New
    Believers' Heathen toggles pick each Heathen type the mask draw
    0x4728C6 shows."""

    def _story(self, game):
        if not have_stock(game):
            self.skipTest("no stock executable")
        story = Story(game)
        _populate(story)
        return story

    def _vv5(self):
        story = self._story("vv5")
        v, p = story.village, story.proc
        # (index, role +0x1CFC, orange +0x1CED, red +0x1CEE): the believers
        # are 0, 1, 3 and 4 (4 the Retired Chief); the rest are Heathens.
        heathens = [(5, 0, 0, 0), (6, 0, 0, 1), (7, 0, 1, 0), (8, 12, 0, 0),
                    (11, 14, 0, 0), (12, 13, 0, 0), (13, 17, 0, 1)]
        for i, role, orange, red in heathens:
            if i > 10:
                v.put(i, sex="f", years=30, name=f"V{i}")
            p.write(v.record(i) + 0x1CEC, bytes([1, orange, red]))
            p.put32(v.record(i) + 0x1CFC, role)
        p.put32(v.record(4) + 0x1CFC, 13)
        return story

    def test_new_believers_heathen_toggles(self):
        story = self._vv5()
        expected = {
            T_HEATHENS: [5, 6, 7, 8, 11, 12, 13],
            T_BLUE: [5],
            T_RED: [6],
            T_ORANGE: [7],
            T_PURPLE: [8, 11],            # role 12 and 14-16 draw purple
            T_CHIEF: [12],
            T_MOMMIES: [13],              # role 17, whatever its colour byte
        }
        for toggle, want in expected.items():
            with self.subTest(toggle=toggle):
                self.assertEqual(_targets(story, toggle), want)
        self.assertEqual(_targets(story, T_BLUE | T_CHIEF, (0,)), [0, 5, 12])

    def test_new_believers_labels(self):
        story = self._vv5()
        want = {0: "Believer", 4: "Believer, Retired Chief", 5: "Heathen, blue",
                6: "Heathen, red", 7: "Heathen, orange", 8: "Heathen, purple",
                11: "Heathen, purple", 12: "Heathen Chief", 13: "Heathen Mommy"}
        for i, words in want.items():
            with self.subTest(index=i):
                self.assertEqual(_role(story, i)[1], words)

    def test_heathen_toggles_pick_nobody_in_the_other_games(self):
        for game in ("vv1", "vv2", "vv3", "vv4"):
            if not have_stock(game):
                continue
            story = Story(game)
            _populate(story)
            with self.subTest(game=game):
                self.assertEqual(_targets(story, 0xFE0), [])

    def test_a_new_home_golden_child(self):
        story = self._story("vv1")
        story.proc.put32(story.village.record(5) + 0x36C, 0xC7)
        self.assertEqual(_role(story, 5)[1], "Golden Child")
        self.assertEqual(_role(story, 0), (0, ""))

    def test_the_secret_city_tribal_chief(self):
        story = self._story("vv3")
        story.proc.write(story.village.record(1) + 0xE80, b"\1")
        self.assertEqual(_role(story, 1)[1], "Tribal Chief")
        self.assertEqual(_role(story, 0), (0, ""))

    def test_the_lost_children_esteemed_elder_and_totem(self):
        story = self._story("vv2")
        v, p = story.village, story.proc
        p.write(v.record(7) + 0x7FC, b"\1")
        self.assertEqual(_role(story, 7)[1], "Esteemed Elder")   # no statue found
        # The statue 0x44D190 makes: the elder's record copied, +0x558 set,
        # the art frame its +0x550 modulo 8 (9: frame 1).
        p.write(v.record(20), p.read(v.record(7), v.L["stride"]))
        p.put32(v.record(20) + 0x558, 1)
        p.put32(v.record(20) + 0x550, 9)
        self.assertEqual(_role(story, 7)[1], "Esteemed Elder, totem: green figure")
        self.assertEqual(_role(story, 0), (0, ""))

    def test_the_tree_of_life_has_no_role(self):
        story = self._story("vv4")
        self.assertEqual(_role(story, 0), (0, ""))

    def test_everyone_and_the_children_by_sex(self):
        """The owner (2026-10-05): "Everyone", "All Female Children", "All Male
        Children" in all five games."""
        EVERYONE, FEMALE_CHILDREN, MALE_CHILDREN = 0x1000, 0x2000, 0x4000
        for game in GAMES:
            if not have_stock(game):
                continue
            story = Story(game)
            _populate(story)
            with self.subTest(game=game):
                self.assertEqual(_targets(story, EVERYONE), [0, 1, 3, 4, 5, 6, 7, 8])
                self.assertEqual(_targets(story, FEMALE_CHILDREN), [5])   # 14 years is adult
                self.assertEqual(_targets(story, MALE_CHILDREN), [4, 6])
                self.assertEqual(_targets(story, FEMALE_CHILDREN | MALE_CHILDREN, (1,)), [1, 4, 5, 6])

    def test_all_nursing_and_all_skeletons(self):
        """The owner (2026-10-06): "All Nursing" (carrying or nursing, either
        sex) and "All Skeletons" (bodies awaiting burial, listed after the
        living); every other toggle is for the living only."""
        NURSING, SKELETONS, EVERYONE = 0x8000, 0x10000, 0x1000
        for game in GAMES:
            if not have_stock(game):
                continue
            story = Story(game)
            _populate(story)                       # record 9 is a body awaiting burial
            v = story.village
            story.proc.put32(v.record(1) + v.L["pregnant"], 400)   # a man carrying
            story.proc.put32(v.record(5) + v.L["pregnant"], 300)   # a girl carrying
            with self.subTest(game=game):
                self.assertEqual(_targets(story, NURSING), [1, 5])
                self.assertEqual(_targets(story, SKELETONS), [9])
                self.assertNotIn(9, _targets(story, EVERYONE))
                self.assertEqual(_targets(story, SKELETONS | NURSING), [1, 5, 9])


@emulated
class RiskAllowedTests(unittest.TestCase):
    """The owner (2026-10-06): risky changes the game survives are allowed,
    the dialog warning "Do this at your own risk"."""

    def test_a_new_home_golden_child_may_carry(self):
        if not have_stock("vv1"):
            self.skipTest("no stock executable")
        story = Story("vv1")
        v = story.village
        v.put(2, sex="f", years=20, name="Golden")
        story.proc.put32(v.record(2) + 0x36C, 0xC7)
        ok, r, _ = story.apply(Event(changes=[story.change(2, litter=1)]))
        self.assertEqual((r["conceived"], r["refused"]), (1, 0))


@emulated
class MergeTests(unittest.TestCase):
    """The changes dialog adds one entry per villager and merges later
    changes for the same villager into it."""

    def test_merge_keeps_one_entry_per_villager_and_later_values_win(self):
        if not have_stock("vv3"):
            self.skipTest("no stock executable")
        story = Story("vv3")
        p = story.proc
        p.write(EVENT_BUF, Event().pack())
        first = Change(index=0, fingerprint=0, sick=1, head=5, skills=(10, KEEP, KEEP, KEEP, KEEP, KEEP))
        second = Change(index=0, fingerprint=0, head=7, litter=2, father=4, father_fingerprint=99)
        third = Change(index=3, fingerprint=0, fate=1)
        for change, index in ((first, 0), (second, 0), (third, 3)):
            p.write(SCRATCH, change.pack())
            self.assertEqual(p.export("VvfpStoryProbeMerge", EVENT_BUF, SCRATCH, index, 0x1234), 1)
        changes_at = 4 + 48 + 600 + 4 * 7 + 8 * Event.SPAWN_SIZE   # change_count, then the changes
        count = struct.unpack("<i", p.read(EVENT_BUF + changes_at, 4))[0]
        self.assertEqual(count, 2)
        entry = p.read(EVENT_BUF + changes_at + 4, 192)
        index, fp, fate, sick, litter, father, father_fp = struct.unpack("<iIiiiiI", entry[:28])
        head, body = struct.unpack("<2i", entry[28:36])
        skills = struct.unpack("<6i", entry[52:76])
        self.assertEqual((index, fp, fate, sick, litter, father, father_fp),
                         (0, 0x1234, 0, 1, 2, 4, 99))
        self.assertEqual((head, body), (7, KEEP))
        self.assertEqual(skills[0], 10)

    def test_the_event_holds_at_most_256_villagers(self):
        if not have_stock("vv3"):
            self.skipTest("no stock executable")
        story = Story("vv3")
        p = story.proc
        p.write(EVENT_BUF, Event().pack())
        p.write(SCRATCH, Change(index=0, fingerprint=0, sick=1).pack())
        for i in range(256):
            self.assertEqual(p.export("VvfpStoryProbeMerge", EVENT_BUF, SCRATCH, i, 1), 1)
        self.assertEqual(p.export("VvfpStoryProbeMerge", EVENT_BUF, SCRATCH, 300, 1), 0)
        self.assertEqual(p.export("VvfpStoryProbeMerge", EVENT_BUF, SCRATCH, 5, 1), 1, "an existing one merges")


# ---------------------------------------------------------------------------
# Every offered option, applied per game
# ---------------------------------------------------------------------------

ADD, SUBTRACT, ZERO = 1, 2, 3
FATE_KILL, FATE_VANISH = 1, 2
TITLE_SET, TITLE_CLEAR = 1, 2


def _food_tech(story):
    """(food VA, tech VA, lifetime food VA or None, lifetime tech VA or None)."""
    w = story.village.world
    if story.game == "vv1":
        return w + 0xA2EC, w + 0xA2FC, w + 0x9E28, w + 0x9E20
    if story.game == "vv2":
        return w + 0x2EAA4, w + 0x2EADC, w + 0x2E504, w + 0x2E4FC
    return {
        "vv3": (0x582490, 0x582644, 0x5824AC, 0x5824A4),
        "vv4": (0x4D6DD0, 0x4D6F88, None, None),
        "vv5": (0x51D34C, 0x51D5F8, None, None),
    }[story.game]


FOOD_WORDS = {
    "vv1": ("Your tribe gains 500 food.", "Your tribe loses 200 food."),
    "vv2": ("Your villagers gain 500 food.", "Your villagers lose 200 food."),
    "vv3": ("Your village gains 500 food.", "Your village has lost 200 food."),
    "vv4": ("Your village gains 500 food.", "Your village has lost 200 food."),
    "vv5": ("Your village gains 500 food.", "Your village has lost 200 food."),
}


def _stories(games=GAMES, **kw):
    for game in games:
        if have_stock(game):
            yield game, Story(game, **kw)


@emulated
class VillageOptionTests(unittest.TestCase):
    def test_food_and_tech_add_subtract_and_zero(self):
        for game, story in _stories():
            food, tech, life_food, life_tech = _food_tech(story)
            p = story.proc
            with self.subTest(game=game, op="add"):
                p.put32(food, 1000)
                p.put32(tech, 3000)
                ok, r, text = story.apply(Event(food_op=ADD, food_amount=500, tech_op=ADD, tech_amount=700))
                self.assertEqual((p.u32(food), p.u32(tech)), (1500, 3700))
                self.assertEqual((r["food_before"], r["food_after"]), (1000, 1500))
                self.assertIn(FOOD_WORDS[game][0], text)
                self.assertIn("700 tech points", text)
                if life_food is not None:
                    self.assertEqual((p.u32(life_food), p.u32(life_tech)), (500, 700),
                                     "a gain counts in the lifetime totals, as the game's adders count it")
            with self.subTest(game=game, op="subtract"):
                p.put32(food, 1000)
                ok, r, text = story.apply(Event(food_op=SUBTRACT, food_amount=200, tech_op=SUBTRACT,
                                                tech_amount=999999))
                self.assertEqual((p.u32(food), p.u32(tech)), (800, 0), "never below 0")
                self.assertIn(FOOD_WORDS[game][1], text)
                if life_food is not None:
                    self.assertEqual(p.u32(life_food), 500, "a loss is not a gain")
            with self.subTest(game=game, op="zero"):
                p.put32(food, 1234)
                p.put32(tech, 99)
                story.apply(Event(food_op=ZERO, tech_op=ZERO))
                self.assertEqual((p.u32(food), p.u32(tech)), (0, 0))

    def test_refill_fills_each_games_own_stores_within_their_ceilings(self):
        for game, story in _stories():
            p = story.proc
            w = story.village.world
            with self.subTest(game=game):
                if game == "vv1":
                    p.put32(w + 0xA2F4, 10)
                    p.put32(w + 0xA2F8, 5)
                    story.apply(Event(refill=1))
                    self.assertEqual(p.u32(w + 0xA2F4), 1900)
                    self.assertEqual(p.u32(w + 0xA2F8), 5, "no crops before the farm produces")
                    p.put32(w + 0xA2E4, 2)
                    story.apply(Event(refill=1))
                    self.assertEqual(p.u32(w + 0xA2F8), 800)
                elif game == "vv2":
                    # The game's field test 0x425AC0 queues "Birds found your
                    # field" as a side effect: the refill never calls it.
                    field_test = []
                    p.stub(0x425AC0, lambda q: (field_test.append(1) or 0, 0))
                    for difficulty, start in ((0, 2200), (1, 1100), (2, 550)):
                        p.put32(w + 0x2EAEC, difficulty)
                        p.put32(w + 0x2EACC, 100)
                        p.put32(w + 0x2EAD8, 7)
                        p.put32(w + 0x2EAD0, 3)          # fish
                        p.put32(w + 0x2EAD4, 0)          # the field's protection, used up
                        p.write(w + 0x2E798, b"\0")      # the farm not planted
                        p.write(w + 0x2E7E8 - 8, b"\0" * 16)
                        story.apply(Event(refill=1))
                        self.assertEqual(p.u32(w + 0x2EACC), 1500)
                        self.assertEqual(p.u32(w + 0x2EAD0), start, "the fish: the difficulty's start")
                        self.assertEqual(p.u32(w + 0x2EAD4), 1000)
                        self.assertEqual(p.u32(w + 0x2EAD8), 7, "no crops while the farm is not planted")
                        p.write(w + 0x2E798, b"\1")
                        story.apply(Event(refill=1))
                        self.assertEqual(p.u32(w + 0x2EAD8), 800)
                        self.assertEqual(p.read(w + 0x2E7E0, 16), bytes(16),
                                         "the algae-fish puzzle's own fields are never written")
                        self.assertEqual(p.read(w + 0x2E770, 1), b"\0", "nor the scarecrow's")
                    # Above the start, nothing is taken away.
                    p.put32(w + 0x2EAD0, 5000)
                    story.apply(Event(refill=1))
                    self.assertEqual(p.u32(w + 0x2EAD0), 5000)
                    self.assertEqual(field_test, [])
                elif game == "vv3":
                    trees = 0x5947E0
                    p.put32(trees + 0x64, 2)
                    for k in range(3):
                        p.put32(trees + 0x24 + 0x18 * k + 0xC, 1)
                    story.apply(Event(refill=1))      # the game's own 0x4340A0, run
                    self.assertEqual([p.u32(trees + 0x30 + 0x18 * k) for k in range(3)], [1000, 1000, 1])
                elif game == "vv4":
                    p.put32(w + 0x170F8, 12)
                    story.apply(Event(refill=1))
                    self.assertEqual(p.u32(w + 0x170F8), 1000)
                else:
                    done = [0]
                    p.stub(0x43AE80, lambda q: (done[0], 4))
                    p.put32(w + 0x17D58, 1)
                    p.put32(w + 0x17D5C, 2)
                    story.apply(Event(refill=1))
                    self.assertEqual((p.u32(w + 0x17D58), p.u32(w + 0x17D5C)), (1000, 2))
                    done[0] = 1
                    story.apply(Event(refill=1))
                    self.assertEqual(p.u32(w + 0x17D5C), 800)

    def test_village_and_puzzle_changes_are_the_stock_events_own(self):
        if have_stock("vv1"):
            story = Story("vv1")
            story.record_call(0x4457D0, 4)
            w = story.village.world
            story.proc.write(w + 0x9FB8, b"\1")
            story.proc.put32(w + 0x9FB4, 3)
            story.apply(Event(village=0b111))
            self.assertEqual(story.calls[0x4457D0], [[story.village.array, 3], [story.village.array, 7]])
            self.assertEqual((story.proc.read(w + 0x9FB8, 1), story.proc.u32(w + 0x9FB4)), (b"\0", 0))
        if have_stock("vv4"):
            story = Story("vv4")
            story.record_call(0x46BC30, 8)
            story.apply(Event(village=0b11))
            self.assertEqual(story.calls[0x46BC30], [[0x6C461C, 2, 0], [0x6C461C, 0, 0]])


@emulated
class VillagerOptionTests(unittest.TestCase):
    def test_kill_uses_each_games_own_death(self):
        for game, story in _stories():
            v = story.village
            L = v.L
            v.put(2, sex="f", years=30, name="Doomed")
            v.put(3, sex="m", years=30, name="Bystander")
            if game == "vv4":
                story.record_call(0x468C60, 0)
            if game == "vv5":
                story.record_call(0x473440, 0)
            ok, r, _ = story.apply(Event(changes=[story.change(2, fate=FATE_KILL, sick=1)]))
            with self.subTest(game=game):
                self.assertEqual(r["died"], 1)
                self.assertEqual(v.i32(2, L["health"]), 0)
                self.assertEqual(v.byte(2, L["active"]), 1, "the body stays, for the skeleton")
                self.assertEqual(v.sick(2), 0, "a villager who dies gets no other change")
                self.assertEqual(v.i32(3, L["health"]), 90)
                if game in ("vv3", "vv4", "vv5"):
                    cause = {"vv3": 0xE7C, "vv4": 0x1C44, "vv5": 0x1C44}[game]
                    # "Unknown causes" in every game (the owner saw a ten-year-old
                    # "die of old age" from a New Believers event's Dies).
                    self.assertEqual(v.i32(2, cause), -1)
                if game in ("vv4", "vv5"):
                    stop = 0x468C60 if game == "vv4" else 0x473440
                    self.assertEqual(story.calls[stop], [[v.record(2)]])

    def test_disappear_uses_the_island_events_own_removal(self):
        for game, story in _stories(("vv1", "vv2", "vv3", "vv4")):
            v = story.village
            L = v.L
            v.put(2, sex="f", years=30, name="Gone")
            p = story.proc
            if game == "vv1":
                p.put32(v.world + 0xAD34, 2)
                p.write(v.record(2) + 0x29, b"\1")
            if game == "vv2":
                p.write(v.record(2) + 0x31, b"\1")
                p.put32(v.world + 0x304F0, 2)
            if game == "vv3":
                p.write(v.record(2) + 0xF11, b"\1")
                world = p.alloc(0x13000)
                p.stub(0x428B60, lambda q: (world, 0))
            if game == "vv4":
                story.record_call(0x468C60, 0)
            ok, r, _ = story.apply(Event(changes=[story.change(2, fate=FATE_VANISH)]))
            with self.subTest(game=game):
                self.assertEqual(r["vanished"], 1)
                self.assertEqual(v.byte(2, L["active"]), 0, "no body, no skeleton")
                if game == "vv1":
                    self.assertEqual(p.u32(v.world + 0xAD34), 0xFFFFFFFF, "the selection is cleared")
                    self.assertEqual(v.byte(2, 0x29), 0)
                if game == "vv2":
                    self.assertEqual((v.byte(2, 0x31), p.u32(v.world + 0x304F0)), (0, 0xFFFFFFFF))
                if game == "vv3":
                    self.assertEqual(v.byte(2, 0xF11), 0)
                    self.assertEqual(p.u32(world + 0x12FC0), 0xFFFFFFFF)

    def test_new_believers_disappearance_clears_the_presence_byte(self):
        """New Believers' own removal: +0x1CD4 cleared (0x420142, 0x46723E,
        0x473F8F), the activity stopped, the selection dropped only when it is
        this villager, no death and no other change."""
        if not have_stock("vv5"):
            self.skipTest("no stock executable")
        for selected in (True, False):
            story = Story("vv5")
            v = story.village
            p = story.proc
            v.put(2, sex="f", years=30, name="Gone")
            v.put(3, sex="m", years=30, name="Stays")
            world = p.alloc(0x18000)
            p.stub(0x425950, lambda q: (world, 0))
            p.put32(v.record(2) + 0x1C94, 77)
            p.put32(world + 0x17E24, 77 if selected else 78)
            story.record_call(0x473440, 0)
            ok, r, _ = story.apply(Event(changes=[story.change(2, fate=FATE_VANISH, sick=1)]))
            with self.subTest(selected=selected):
                self.assertEqual(r["vanished"], 1)
                self.assertEqual(v.byte(2, 0x1CD4), 0, "no body, no skeleton")
                self.assertEqual(v.i32(2, 0x1C40), 90, "a disappearance is not a death")
                self.assertEqual(v.sick(2), 0, "a villager who disappears gets no other change")
                self.assertEqual(story.calls[0x473440], [[v.record(2)]])
                self.assertEqual(p.u32(world + 0x17E24), 0xFFFFFFFF if selected else 78)
                self.assertEqual(v.byte(3, 0x1CD4), 1)

    def test_sickness(self):
        for game, story in _stories():
            v = story.village
            v.put(2, sex="f", years=30, name="Ill")
            story.apply(Event(changes=[story.change(2, sick=1)]))
            with self.subTest(game=game):
                self.assertEqual(v.sick(2), 1)
        if have_stock("vv5"):
            story = Story("vv5")
            story.village.put(2, sex="f", years=30, name="Heathen", faction=1)
            ok, r, _ = story.apply(Event(changes=[story.change(2, sick=1)]))
            self.assertEqual((story.village.sick(2), r["refused"]), (0, 1),
                             "the game cures a Heathen every moment")

    def test_likes_and_dislikes_add_and_remove(self):
        for game, story in _stories():
            v = story.village
            L = v.L
            v.put(2, sex="f", years=30, name="Picky")
            story.proc.put32(v.record(2) + L["likes"], 5)
            story.proc.put32(v.record(2) + L["dislikes"] + 4, 9)
            story.apply(Event(changes=[story.change(2, like_add=7, like_remove=5, dislike_add=11,
                                                    dislike_remove=9)]))
            with self.subTest(game=game):
                self.assertEqual(v.prefs(2, "likes")[:3], [7, -1, -1])
                self.assertEqual(v.prefs(2, "dislikes")[:3], [11, -1, -1])
                if game == "vv3":
                    self.assertEqual(story.host.brackets, [0, 1],
                                     "The Secret City's mask identity holds the lists: bracketed")
            # a full list refuses the addition, a word outside the game's list is ignored
            for k in range(L["slots"]):
                story.proc.put32(v.record(2) + L["likes"] + 4 * k, 0)
            ok, r, _ = story.apply(Event(changes=[story.change(2, like_add=L["prefs"] - 1),
                                                  ]))
            with self.subTest(game=game, case="full"):
                self.assertEqual(r["refused"], 1)
                self.assertNotIn(L["prefs"] - 1, v.prefs(2, "likes"))
            story.apply(Event(changes=[story.change(2, dislike_add=L["prefs"])]))
            with self.subTest(game=game, case="out of range"):
                self.assertNotIn(L["prefs"], v.prefs(2, "dislikes"))

    def test_appearance_within_each_games_own_rows(self):
        for game, story in _stories():
            v = story.village
            L = v.L
            v.put(2, sex="m", years=30, name="Looks")
            story.apply(Event(changes=[story.change(2, head=L["heads"] - 1, body=0)]))
            with self.subTest(game=game):
                self.assertEqual((v.i32(2, L["head"]), v.i32(2, L["body"])), (L["heads"] - 1, 0))
            story.apply(Event(changes=[story.change(2, head=L["heads"], body=-3)]))
            with self.subTest(game=game, case="out of range"):
                self.assertEqual((v.i32(2, L["head"]), v.i32(2, L["body"])), (L["heads"] - 1, 0))

    def test_skills_every_one_the_game_has(self):
        for game, story in _stories():
            v = story.village
            L = v.L
            v.put(2, sex="m", years=30, name="Skilled")
            skills = tuple(10 * (k + 1) if k < L["skill_count"] else KEEP for k in range(6))
            story.apply(Event(changes=[story.change(2, skills=skills)]))
            with self.subTest(game=game):
                self.assertEqual([v.skill(2, k) for k in range(L["skill_count"])],
                                 [10 * (k + 1) for k in range(L["skill_count"])])
                if L["skill_count"] == 5:
                    self.assertEqual(v.i32(2, L["skills"] + 20) if not L["floats"] else 0, 0,
                                     "nothing written past the game's own skills")
            story.apply(Event(changes=[story.change(2, skills=(150,) + (KEEP,) * 5)]))
            with self.subTest(game=game, case="clamped"):
                self.assertEqual(v.skill(2, 0), 100)

    def test_parents_on_the_childs_record(self):
        for game, story in _stories(("vv2", "vv3", "vv4", "vv5")):
            v = story.village
            fname, mname, cap, fh, fb, mh, mb = PARENTS[game]
            r = v.put(2, sex="f", years=8, name="Kid")
            story.apply(Event(changes=[story.change(2, parents_set=1, father_name="Kalani", mother_name="Moana",
                                                    father_head=4, mother_body=29)]))
            p = story.proc
            with self.subTest(game=game):
                self.assertEqual(p.read(r + fname, 7), b"Kalani\0")
                self.assertEqual(p.read(r + mname, 6), b"Moana\0")
                self.assertEqual((p.u32(r + fh), p.u32(r + mb)), (4, 29))
                self.assertEqual((p.u32(r + fb), p.u32(r + mh)), (0, 0), "blank values are left as they were")
            ok, res, _ = story.apply(Event(changes=[story.change(2, parents_set=1, father_head=30)]))
            with self.subTest(game=game, case="out of range"):
                self.assertEqual((res["refused"], p.u32(r + fh)), (1, 4))

    def test_a_new_home_keeps_parents_in_the_show_parents_sidecar(self):
        if not have_stock("vv1"):
            self.skipTest("no stock executable")
        story = Story("vv1")
        p = story.proc
        story.village.put(2, sex="f", years=8, name="Kid")
        # Without the Show Parents row there is nowhere to keep them.
        ok, r, _ = story.apply(Event(changes=[story.change(2, parents_set=1, father_name="Kalani")]))
        self.assertEqual(r["refused"], 1)
        self.assertTrue(any(name.endswith("VVFP VV1 Parentage.dll") for name in p.loaded))
        # With it: Vv1ParentageSetParents(index, father, fh, fb, mother, mh, mb).
        story = Story("vv1")
        p = story.proc
        story.village.put(2, sex="f", years=8, name="Kid")
        export = p.alloc(0x10)
        seen = []
        p.api_handlers["LoadLibraryExW"] = lambda q: (
            0x71000000 if q.wstring(q.arg(0)).endswith(
                "\\Virtual Villagers Fun Patcher Files\\VVFP VV1 Parentage.dll") else 0, 12)
        p.api_handlers["GetProcAddress"] = lambda q: (
            export if q.cstring(q.arg(1)) == "Vv1ParentageSetParents" else 0, 8)

        def set_parents(q):
            seen.append((q.arg(0), q.cstring(q.arg(1)), q.arg(2), q.arg(3), q.cstring(q.arg(4)),
                         q.arg(5), q.arg(6)))
            return 1, 28
        p.stub(export, set_parents)
        ok, r, _ = story.apply(Event(changes=[story.change(2, parents_set=1, father_name="Kalani",
                                                          mother_head=3)]))
        self.assertEqual(r["refused"], 0)
        self.assertEqual(seen, [(2, "Kalani", 0xFFFFFFFF, 0xFFFFFFFF, "", 3, 0xFFFFFFFF)])

    def test_masks_through_each_origins_companions_own_store(self):
        for game, story in _stories():
            v = story.village
            v.put(2, sex="m", years=30, name="Masked")
            story.apply(Event(changes=[story.change(2, mask=5)]))
            with self.subTest(game=game):
                self.assertEqual(story.host.masks, {v.record(2): 5})

    def test_a_villager_who_changed_since_queueing_is_left_alone(self):
        for game, story in _stories():
            v = story.village
            L = v.L
            v.put(2, sex="m", years=30, name="Before")
            stale = story.change(2, sick=1, head=1)
            v.put(2, sex="m", years=1, name="After")     # a birth reused the record
            v.put(3, sex="m", years=30, name="Dead", health=0)
            dead = story.change(3, sick=1)
            ok, r, text = story.apply(Event(changes=[stale, dead]))
            with self.subTest(game=game):
                self.assertEqual((r["skipped"], r["changed"]), (2, 0))
                self.assertEqual((v.sick(2), v.sick(3)), (0, 0))
                self.assertIn("2 of the chosen villagers were no longer here.", text.replace("\n", " "))

    def test_a_reused_record_with_the_same_name_is_left_alone(self):
        """Names come from a fixed pool: a new villager of the same name in a
        freed record is somebody else (Codex, PR #495)."""
        for game, story in _stories():
            for what, kw in (("head", {"head": 6}), ("body", {"body": 7}), ("sex", {"sex": "f"})):
                v = story.village
                v.put(2, sex="m", years=30, name="Kaimi")
                queued = story.change(2, fate=1)
                v.put(2, **{"sex": "m", "years": 30, "name": "Kaimi", **kw})
                ok, r, _ = story.apply(Event(changes=[queued]))
                with self.subTest(game=game, differs=what):
                    self.assertEqual((r["skipped"], r["changed"], r["died"]), (1, 0, 0))
                    self.assertEqual(v.name(2), "Kaimi")
            v = story.village
            v.put(2, sex="m", years=30, name="Kaimi")
            queued = story.change(2, sick=1)
            v.proc.put32(v.record(2) + v.L["likes"], 3)      # same name and looks, other likes
            ok, r, _ = story.apply(Event(changes=[queued]))
            with self.subTest(game=game, differs="likes"):
                self.assertEqual((r["skipped"], v.sick(2)), (1, 0))
            v.put(2, sex="m", years=30, name="Kaimi")
            queued = story.change(2, sick=1)
            ok, r, _ = story.apply(Event(changes=[queued]))
            with self.subTest(game=game, differs="nothing"):
                self.assertEqual((r["changed"], r["skipped"]), (1, 0))


# ---------------------------------------------------------------------------
# Pregnancy: the fields a conception writes, the room, the parentage log
# ---------------------------------------------------------------------------

def _room_until(story, limit):
    """The game's room predicate answers yes while fewer than `limit`
    babies / villagers have been added since the call."""
    v = story.village
    L = v.L
    start = [None]

    def pending():
        total = 0
        for i in range(L["count"]):
            if v.byte(i, L["active"]):
                total += 1
                if v.i32(i, L["pregnant"]):
                    litter = v.i32(i, L["litter"])
                    total += {"vv1": 1 + (litter - 1 if litter > 1 else 0),
                              "vv2": 1 + (litter - 1 if litter > 1 else 0)}.get(story.game, litter)
        return total

    def answer(p):
        if start[0] is None:
            start[0] = pending()
        return (1 if pending() - start[0] < limit else 0), 0
    story.room_answer = answer
    story._stub_room_and_creator()


class ParentageLog:
    """"VVFP Parentage Export.dll" as the companion finds it: by full path in
    the patcher's folder beside the game (native/shared/patcher_files.h)."""

    def __init__(self, proc):
        self.calls = []
        export = proc.alloc(0x10)
        proc.api_handlers["LoadLibraryExW"] = lambda q: (
            0x72000000 if q.wstring(q.arg(0)).endswith(
                "\\Virtual Villagers Fun Patcher Files\\VVFP Parentage Export.dll") else 0, 12)
        proc.api_handlers["GetProcAddress"] = lambda q: (
            export if q.cstring(q.arg(1)) == "WriteParentageRecordWithFather" else 0, 8)

        def write(q):
            self.calls.append(tuple(q.arg(i) for i in range(4)))
            return 1, 16
        proc.stub(export, write)


def _conception_stub(story):
    """VV4 0x45E7B0 / VV5 0x465E00 (forced): the fields the routine writes,
    with a rolled litter of 2 (VV4 also counts its twins)."""
    v = story.village
    L = v.L
    va = 0x45E7B0 if story.game == "vv4" else 0x465E00

    def conceive(p):
        r = p.reg("ecx")
        story.calls.setdefault(va, []).append([r] + [p.arg(i) for i in range(7)])
        p.put32(r + L["pregnant"], p.u32(r + L["processed"]))
        p.put32(r + L["litter"], 2)
        p.write(r + 0x1C10, p.read(p.arg(3), 24))
        if story.game == "vv4":
            p.put32(0x4D6E08, p.u32(0x4D6E08) + 1)
        return 0, 0x1C
    story.proc.stub(va, conceive)


@emulated
class PregnancyTests(unittest.TestCase):
    def _story(self, game, full=False):
        story = Story(game, full=full)
        v = story.village
        v.put(1, sex="m", years=30, name="Papa", head=7, body=8)
        v.put(2, sex="f", years=30, name="Mama", head=1, body=2)
        v.put(3, sex="m", years=25, name="Carrier", head=4, body=5)
        v.put(4, sex="f", years=10, name="Child")
        story.proc.put32(v.record(2) + L_PROC[game], 600)
        if game == "vv1":
            story.proc.put32(v.record(1) + 0x36C, 17)
            story.record_call(0x439470, 4)
        if game == "vv2":
            story.proc.put32(v.record(1) + 0x554, 23)
        if game == "vv3":
            story.proc.put32(v.record(1) + 0xDD0, 31)
            story.record_call(0x460F70, 4)
        if game in ("vv4", "vv5"):
            _conception_stub(story)
            story.proc.put32(v.record(1) + 0x1B98, 41)
        if game == "vv4":
            story.record_call(0x412F90, 8)
        return story

    def test_a_new_look_in_the_same_event_does_not_cancel_the_pregnancy(self):
        """Identity is decided before anything changes: the event may itself
        give the mother and father new heads, bodies and likes."""
        for game in GAMES:
            if not have_stock(game):
                continue
            story = self._story(game)
            v = story.village
            ok, r, _ = story.apply(Event(changes=[
                story.change(1, head=3, body=3, like_add=1),
                story.change(2, head=5, body=6, like_add=2, litter=2, father=1,
                             father_fingerprint=v.identity(1))]))
            with self.subTest(game=game):
                self.assertEqual((r["skipped"], r["conceived"]), (0, 2))
                self.assertEqual((v.i32(2, v.L["head"]), v.i32(2, v.L["body"])), (5, 6))
                if game in ("vv2", "vv3"):
                    off = 0x5C0 if game == "vv2" else 0xE48
                    self.assertEqual(story.proc.read(v.record(2) + off, 5), b"Papa\0",
                                     "the father was still recognised")

    def test_each_game_writes_its_own_conception_fields(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            for litter in (1, 2, 3):
                story = self._story(game)
                v = story.village
                p = story.proc
                r2 = v.record(2)
                ok, r, _ = story.apply(Event(changes=[story.change(2, litter=litter, father=1,
                                                                   father_fingerprint=v.identity(1))]))
                with self.subTest(game=game, litter=litter):
                    self.assertEqual(r["conceived"], litter)
                    self.assertEqual(v.i32(2, v.L["pregnant"]), 600, "the age at conception")
                    stored = v.i32(2, v.L["litter"])
                    if game in ("vv1", "vv2"):
                        self.assertEqual(stored, 0 if litter == 1 else litter)
                    else:
                        self.assertEqual(stored, litter)
                    if game == "vv1":
                        w = v.world
                        self.assertEqual(v.i32(2, 0x394), 17, "the father's family")
                        self.assertEqual((v.i32(2, 0x38C), v.i32(2, 0x390)), (0, 0))
                        self.assertEqual(p.u32(w + 0x9E24), litter, "Babies Made, per baby")
                        self.assertEqual((p.u32(w + 0x9E44), p.u32(w + 0x9E48)),
                                         (int(litter == 2), int(litter == 3)))
                        self.assertEqual(story.calls[0x439470], [[v.array, 2]], "the carrying pose")
                    if game == "vv2":
                        self.assertEqual(p.read(r2 + 0x5C0, 5), b"Papa\0")
                        self.assertEqual((v.i32(2, 0x5E0), v.i32(2, 0x5DC)), (7, 8))
                        self.assertEqual((v.i32(2, 0x5EC), v.i32(2, 0x44)), (23, 0x1A))
                        self.assertEqual(p.u32(v.world + 0x2E500), litter, "Babies Made, per baby")
                        self.assertEqual(p.u32(v.world + 0x2E524), int(litter == 3))
                        self.assertEqual(p.u32(v.world + 0x2E5E4), 0,
                                         "without the statistics row its twins field is never written")
                    if game == "vv3":
                        self.assertEqual(p.read(r2 + 0xE48, 5), b"Papa\0")
                        self.assertEqual((v.i32(2, 0xE68), v.i32(2, 0xE64), v.i32(2, 0xE44)), (7, 8, 31))
                        self.assertEqual(p.u32(0x5824A8), litter)
                        self.assertEqual((p.u32(0x5824C8), p.u32(0x5824CC)),
                                         (int(litter == 2), int(litter == 3)))
                        self.assertEqual(story.calls[0x460F70], [[r2, r2]])
                    if game == "vv4":
                        call = story.calls[0x45E7B0][0]
                        self.assertEqual(call[:4] + call[5:], [r2, 41, 0, 0, 7, 8, 1], "forced = 1")
                        self.assertEqual(p.cstring(call[4]), "Papa")
                        self.assertEqual(p.u32(0x4D6E08), int(litter == 2),
                                         "the rolled twins taken back, the chosen litter counted")
                        self.assertEqual(p.u32(0x4D6E0C), int(litter == 3))
                        self.assertEqual(p.u32(0x4D6DE8), litter)
                        self.assertEqual(story.calls[0x412F90], [[0x4CBB98, 0x13 + litter, 1]])
                    if game == "vv5":
                        call = story.calls[0x465E00][0]
                        self.assertEqual(call[-1], 1, "forced")
                        self.assertEqual(p.u32(0x51D360), litter)

    def test_an_unknown_father_is_unknown_with_the_carriers_looks(self):
        for game in ("vv2", "vv3", "vv4", "vv5"):
            if not have_stock(game):
                continue
            story = self._story(game)
            v = story.village
            story.apply(Event(changes=[story.change(2, litter=1)]))
            with self.subTest(game=game):
                if game == "vv2":
                    self.assertEqual(story.proc.read(v.record(2) + 0x5C0, 8), b"Unknown\0")
                    self.assertEqual((v.i32(2, 0x5E0), v.i32(2, 0x5DC)), (1, 2))
                elif game == "vv3":
                    self.assertEqual(story.proc.read(v.record(2) + 0xE48, 8), b"Unknown\0")
                    self.assertEqual((v.i32(2, 0xE68), v.i32(2, 0xE64)), (1, 2))
                else:
                    call = story.calls[0x45E7B0 if game == "vv4" else 0x465E00][0]
                    self.assertEqual(story.proc.cstring(call[4]), "Unknown")
                    self.assertEqual(call[5:7], [1, 2])

    def test_any_villager_of_either_sex_and_any_age(self):
        """The owner (2026-10-05): "remove sex restrictions on 'make pregnant'",
        and any age (a full villager of age 0 included)."""
        for game in GAMES:
            if not have_stock(game):
                continue
            story = self._story(game)
            v = story.village
            ok, r, _ = story.apply(Event(changes=[story.change(3, litter=1), story.change(4, litter=1)]))
            with self.subTest(game=game):
                self.assertEqual(r["conceived"], 2, "the man and the child both carry")
                self.assertNotEqual(v.i32(3, v.L["pregnant"]), 0)
                self.assertNotEqual(v.i32(4, v.L["pregnant"]), 0)
                self.assertEqual(r["refused"], 0)
            ok, r, _ = story.apply(Event(changes=[story.change(3, litter=2)]))
            with self.subTest(game=game, case="already pregnant: the litter changes"):
                self.assertEqual((r["conceived"], r["refused"]), (1, 0))
                self.assertEqual(v.i32(3, v.L["litter"]), 2)

    def test_a_heathen_carries_in_new_believers(self):
        """As the Heathen Mommy does: the life tick skips a Heathen, so the
        birth waits until they are a believer again (the owner)."""
        if not have_stock("vv5"):
            self.skipTest("no stock executable")
        story = self._story("vv5")
        story.village.put(5, sex="f", years=30, name="Heathen", faction=1)
        ok, r, _ = story.apply(Event(changes=[story.change(5, litter=1)]))
        self.assertEqual((r["conceived"], r["refused"]), (1, 0))
        self.assertNotEqual(story.village.i32(5, 0x1C4C), 0)

    def test_each_baby_only_while_the_village_has_room(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            story = self._story(game)
            _room_until(story, 2)
            if game in ("vv4", "vv5"):
                _conception_stub(story)
            ok, r, text = story.apply(Event(changes=[story.change(2, litter=3)]))
            with self.subTest(game=game):
                self.assertEqual((r["conceived"], r["no_room_babies"]), (2, 1))
                self.assertIn("no room for 1 of the new villagers", text.replace("\n", " "))
            story = self._story(game)
            _room_until(story, 0)
            if game in ("vv4", "vv5"):
                _conception_stub(story)
            ok, r, _ = story.apply(Event(changes=[story.change(2, litter=2)]))
            with self.subTest(game=game, case="full"):
                self.assertEqual((r["conceived"], r["no_room_babies"]), (0, 2))
                self.assertEqual(story.village.i32(2, story.village.L["pregnant"]), 600 if False else 0)

    def test_the_conception_is_logged_only_with_the_parentage_row(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            for full in (False, True):
                story = self._story(game, full=full)
                log = ParentageLog(story.proc)
                v = story.village
                story.apply(Event(changes=[story.change(2, litter=1, father=1,
                                                        father_fingerprint=v.identity(1))]))
                records = {"vv1": v.base, "vv2": v.base, "vv3": 0x59E110, "vv4": 0x50E568,
                           "vv5": 0x554148}[game]
                with self.subTest(game=game, parentage_row=full):
                    if full:
                        self.assertEqual(log.calls, [(story.n, records, v.record(2), v.record(1))])
                    else:
                        self.assertEqual(log.calls, [])


L_PROC = {g: LAYOUTS[g]["processed"] for g in LAYOUTS}


# ---------------------------------------------------------------------------
# New villagers
# ---------------------------------------------------------------------------

@emulated
class SpawnTests(unittest.TestCase):
    def test_new_villagers_through_each_games_own_creator(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            story = Story(game)
            v = story.village
            L = v.L
            v.put(0, sex="m", years=30, name="Founder")
            _room_until(story, 2)
            skills = (55,) + (KEEP,) * 5
            spawn = Spawn(count=3, sex=2, age=400, name="Hina", head=2, body=3, prefs_set=1,
                          likes=(1, 2, -1), dislikes=(4, 2, -1), skills=skills)
            ok, r, text = story.apply(Event(spawns=[spawn]))
            creator = {"vv1": 0x43C350, "vv2": 0x44F580, "vv3": 0x45FF50, "vv4": 0x467D10,
                       "vv5": 0x471E20}[game]
            with self.subTest(game=game):
                self.assertEqual((r["born"], r["no_room_spawns"]), (2, 1),
                                 "the third is refused: the game's own room predicate said no")
                calls = story.calls[creator]
                self.assertEqual(len(calls), 2)
                lineage = 1 if game == "vv5" else 0xFFFFFFFF
                self.assertEqual(calls[0][1:], [lineage, 0, 0, L["sex"][2], 400])
                for i, _, _ in story.creations:
                    self.assertEqual(v.name(i), "Hina")
                    self.assertEqual((v.i32(i, L["head"]), v.i32(i, L["body"])), (2, 3))
                    self.assertEqual(v.prefs(i, "likes")[:3], [1, 2, -1])
                    self.assertEqual(v.prefs(i, "dislikes")[:3], [4, -1, -1],
                                     "a dislike that is also a like is dropped")
                    self.assertEqual(v.skill(i, 0), 55)
                self.assertIn("no room for 1 of the new villagers", text.replace("\n", " "))

    def test_many_new_villagers_at_age_0_in_one_event(self):
        """The owner (2026-10-05): "Spawn tons of villagers at once" up to the
        village's limits, "of any age (0-whatever)" -- age 0 a full villager
        from the game's own creator, not a carried baby."""
        for game in GAMES:
            if not have_stock(game):
                continue
            story = Story(game)
            v = story.village
            L = v.L
            v.put(0, sex="m", years=30, name="Founder")
            _room_until(story, 100)
            ok, r, _ = story.apply(Event(spawns=[Spawn(count=120, sex=2, age=0)]))
            creator = {"vv1": 0x43C350, "vv2": 0x44F580, "vv3": 0x45FF50, "vv4": 0x467D10,
                       "vv5": 0x471E20}[game]
            with self.subTest(game=game):
                self.assertEqual((r["born"], r["no_room_spawns"]), (100, 20), "the village's limit holds")
                self.assertEqual({c[-1] for c in story.calls[creator]}, {0}, "made at age 0")
                for i, _, _ in story.creations:
                    self.assertEqual(v.byte(i, L["active"]), 1)
                    self.assertGreater(v.i32(i, L["health"]), 0)
                    self.assertEqual(v.i32(i, L["pregnant"]), 0)

    def test_the_games_own_choices_are_kept_when_none_are_given(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            story = Story(game)
            v = story.village
            L = v.L
            ok, r, _ = story.apply(Event(spawns=[Spawn(count=1, sex=1, age=60)]))
            i = story.creations[0][0]
            with self.subTest(game=game):
                self.assertEqual(v.name(i), "Newborn")
                self.assertEqual((v.i32(i, L["head"]), v.i32(i, L["body"])), (3, 4))


# ---------------------------------------------------------------------------
# Statuses, behaviours
# ---------------------------------------------------------------------------

@emulated
class StatusTests(unittest.TestCase):
    def test_the_lost_children_esteemed_elder_and_totem(self):
        if not have_stock("vv2"):
            self.skipTest("no stock executable")
        story = Story("vv2")
        v = story.village
        p = story.proc
        v.put(1, sex="m", years=60, name="Elder")
        p.put32(v.record(1) + 0x554, 12)
        story.record_call(0x44D190, 4, value=5)
        ok, r, _ = story.apply(Event(changes=[story.change(1, status=0)]))
        self.assertEqual(story.calls[0x44D190], [[v.base, 1]])
        self.assertEqual((p.u32(v.world + 0x2E514), r["refused"]), (1, 0), "Village Elders counted")
        # The game's routine sets +0x7FC; it is an elder now and is not made one twice.
        p.put32(v.record(1) + 0x7FC, 1)
        ok, r, _ = story.apply(Event(changes=[story.change(1, status=0)]))
        # Already an elder: nothing to change, nothing refused.
        self.assertEqual((len(story.calls[0x44D190]), r["refused"]), (1, 0))
        # The statue: what 0x44D190 copies (name, sex, lineage, parents), +0x558 set.
        statue = v.put(6, sex="m", years=60, name="Elder")
        p.put32(statue + 0x558, 1)
        p.put32(statue + 0x554, 12)
        p.put32(statue + 0x550, 43)                 # frame 3
        ok, r, _ = story.apply(Event(changes=[story.change(1, status=1 + 6)]))
        self.assertEqual(r["refused"], 0)
        value = p.u32(statue + 0x550)
        self.assertEqual(value % 8, 6)
        self.assertTrue(1 <= value <= 123)
        # Two matching statues: refused rather than guessed.
        other = v.put(7, sex="m", years=60, name="Elder")
        p.put32(other + 0x558, 1)
        p.put32(other + 0x554, 12)
        ok, r, _ = story.apply(Event(changes=[story.change(1, status=1)]))
        self.assertEqual(r["refused"], 1)
        self.assertEqual(p.u32(statue + 0x550) % 8, 6)

    def test_the_secret_city_a_child_becomes_the_tribal_chief(self):
        """The owner (2026-10-06): "children can literally be tribal chiefs
        naturally in-game" -- any age, through the game's own robing."""
        if not have_stock("vv3"):
            self.skipTest("no stock executable")
        story = Story("vv3")
        v = story.village
        v.put(1, sex="m", years=8, name="Kid")
        story.record_call(0x45FC00, 0, value=0)       # no chief lives
        story.record_call(0x45FBC0, 4)                # the robing
        story.record_call(0x435990, 4)                # the chief puzzle's advance
        ok, r, _ = story.apply(Event(changes=[story.change(1, status=1)]))
        self.assertEqual(r["refused"], 0)
        self.assertEqual(story.calls[0x45FBC0][0][1], v.record(1), "the child is robed")

    def test_new_believers_faith_is_written_as_it_is(self):
        """-100..100; the faction stays (the owner: "I could set a villager's
        faith to 0 or a heathen to 100 and they'd stay the same faction")."""
        if not have_stock("vv5"):
            self.skipTest("no stock executable")
        story = Story("vv5")
        v = story.village
        v.put(1, sex="m", years=30, name="Believer")
        v.put(2, sex="f", years=30, name="Heathen", faction=1)
        ok, r, _ = story.apply(Event(changes=[story.change(1, faith=-73), story.change(2, faith=100)]))
        self.assertEqual((v.i32(1, 0x1CF0), v.byte(1, 0x1CEC)), (-73, 0))
        self.assertEqual((v.i32(2, 0x1CF0), v.byte(2, 0x1CEC)), (100, 1))
        self.assertEqual(r["refused"], 0)

    def test_new_believers_purple_chief_and_mommy_for_anyone(self):
        """The owner: "Set heathens to be purple masks / Chief Masks / Heathen
        Mommies", a believer made a Heathen first; the dialog warns."""
        if not have_stock("vv5"):
            self.skipTest("no stock executable")
        story = Story("vv5")
        v = story.village
        p = story.proc
        p.stub(0x4669E0, lambda q: (q.write(q.reg("ecx") + 0x1CEC, b"\1"), 0)[1:] and (0, 0))
        for i, status, role in ((1, 5, 0xC), (2, 6, 0xD), (3, 7, 0x11)):
            v.put(i, sex="m", years=30, name=f"B{i}")
            p.write(v.record(i) + 0x1CED, b"\1\1")        # coloured before
            ok, r, _ = story.apply(Event(changes=[story.change(i, status=status)]))
            with self.subTest(status=status):
                self.assertEqual((v.byte(i, 0x1CEC), v.i32(i, 0x1CFC)), (1, role))
                self.assertEqual((v.byte(i, 0x1CED), v.byte(i, 0x1CEE)), (0, 0))
                self.assertEqual(r["refused"], 0)

    def test_new_believers_faction_through_the_games_conversions(self):
        if not have_stock("vv5"):
            self.skipTest("no stock executable")
        story = Story("vv5")
        v = story.village
        p = story.proc
        p.stub(0x4668B0, lambda q: (q.write(q.reg("ecx") + 0x1CEC, b"\0"), 0)[1:] and (0, 0))
        p.stub(0x4669E0, lambda q: (q.write(q.reg("ecx") + 0x1CEC, b"\1"), 0)[1:] and (0, 0))
        v.put(1, sex="m", years=30, name="Believer")
        v.put(2, sex="f", years=30, name="Heathen", faction=1)
        v.put(3, sex="f", years=30, name="Mommy", faction=1)
        p.put32(v.record(3) + 0x1CFC, 0x11)          # the Heathen Mommy's puzzle role
        ok, r, _ = story.apply(Event(changes=[story.change(1, status=1), story.change(2, status=0),
                                              story.change(3, status=0)]))
        self.assertEqual((v.byte(1, 0x1CEC), v.i32(1, 0x1CF0)), (1, -10))
        self.assertEqual((v.byte(2, 0x1CEC), v.i32(2, 0x1CF0)), (0, 55))
        self.assertEqual(v.byte(3, 0x1CEC), 0, "a puzzle's own Heathen too (the owner: at their own risk)")
        self.assertEqual(r["refused"], 0)
        p.put32(v.record(2) + 0x1C4C, 300)          # pregnant
        ok, r, _ = story.apply(Event(changes=[story.change(2, status=1)]))
        self.assertEqual((v.byte(2, 0x1CEC), r["refused"]), (1, 0), "a carrier becomes a Heathen too")
        self.assertEqual(v.i32(2, 0x1C4C), 300, "...and keeps the baby (born once a believer again)")


# Each game's stop routine and how it is called: (va, bytes popped, this).
STOPS = {"vv1": (0x439470, 4, "array"), "vv2": (0x4492A0, 4, "array"), "vv3": (0x460F70, 4, "record"),
         "vv4": (0x468C60, 0, "record"), "vv5": (0x473440, 0, "record")}
# VV3-VV5: the do-action routine every action goes through (thiscall on the
# record: id, argument pointer; ret 8).
DO_ACTION = {"vv3": 0x455570, "vv4": 0x45DEC0, "vv5": 0x465580}
ADAPTER_SOURCES = {g: SOURCE / f"story_c{g[2]}.inc" for g in GAMES}


def behaviour_table(game: str):
    """The game's offered actions as its adapter declares them:
    (label, kind, routine, arg)."""
    source = ADAPTER_SOURCES[game].read_text(encoding="utf-8")
    body = source[source.index(f"static const ce_action C{game[2]}_BEHAVIOURS[] = {{"):]
    body = body[:body.index("};")]
    rows = re.findall(r'\{ "((?:[^"\\]|\\.)*)", (ACT_[A-Z_]+), (0x[0-9A-Fa-f]+u?|0), (0x[0-9A-Fa-f]+|\d+) \}', body)
    return [(label, kind, int(routine.rstrip("u"), 16) if routine != "0" else 0, int(arg, 0))
            for label, kind, routine, arg in rows]


def stock_callers(game: str, target: int) -> int:
    """E8 calls to `target` anywhere in the stock executable's code."""
    import pefile as pe_module

    data = stock_path(game).read_bytes()
    pe = pe_module.PE(data=data, fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    n = 0
    for section in pe.sections:
        if not section.Characteristics & 0x20000000:
            continue
        raw = data[section.PointerToRawData:section.PointerToRawData + section.SizeOfRawData]
        start = base + section.VirtualAddress
        i = raw.find(b"\xE8")
        while i >= 0 and i + 5 <= len(raw):
            if start + i + 5 + struct.unpack_from("<i", raw, i + 1)[0] == target:
                n += 1
            i = raw.find(b"\xE8", i + 1)
    return n


@emulated
class BehaviourTests(unittest.TestCase):
    def test_every_offered_action_stops_first_then_starts_the_games_own_routine(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            table = behaviour_table(game)
            self.assertGreater(len(table), 1, game)
            stop_va, stop_pop, stop_this = STOPS[game]
            for k, (label, kind, routine, arg) in enumerate(table):
                story = Story(game)
                v = story.village
                v.put(2, sex="f", years=30, name="Actor")
                order = []

                def recorder(va, pop):
                    def fn(p):
                        order.append([va, p.reg("ecx")] + [p.arg(i) for i in range(pop // 4)])
                        return 0, pop
                    return fn
                story.proc.stub(stop_va, recorder(stop_va, stop_pop))
                if game in DO_ACTION:
                    story.proc.stub(DO_ACTION[game], recorder(DO_ACTION[game], 8))
                elif routine:
                    story.proc.stub(routine, recorder(routine, 8 if kind == "ACT_CALL_ARG" else 4))
                if game in ("vv3", "vv4", "vv5"):
                    health = {"vv3": 0x462670, "vv4": 0x46AF00, "vv5": 0x4758B0}[game]
                    story.proc.stub(health, recorder(health, 8))
                ok, r, _ = story.apply(Event(changes=[story.change(2, behaviour=k)]))
                this = v.base if stop_this == "array" else v.record(2)
                stop = [stop_va, this] + ([2] if stop_this == "array" else
                                          [v.record(2)] if game == "vv3" else [])
                with self.subTest(game=game, behaviour=label):
                    self.assertEqual(r["refused"], 0)
                    calls = [c for c in order if c[0] != {"vv3": 0x462670, "vv4": 0x46AF00,
                                                          "vv5": 0x4758B0}.get(game)]
                    if kind == "ACT_EFFECT":
                        self.assertEqual(calls, [[routine, this, 2]], "an effect is not stopped for")
                        continue
                    self.assertEqual(calls[0], stop, "the stop comes first")
                    if kind in ("ACT_STOP", "ACT_RECOVER"):
                        self.assertEqual(len(calls), 1)
                    elif kind == "ACT_DO":
                        self.assertEqual(len(calls), 2)
                        self.assertEqual(calls[1][:3], [DO_ACTION[game], v.record(2), arg])
                        self.assertEqual(story.proc.read(calls[1][3], 32), bytes(32),
                                         "an argument block of zeros")
                    else:
                        want = [routine, v.base, 2] + ([arg] if kind == "ACT_CALL_ARG" else [])
                        self.assertEqual(calls[1:], [want])

    def test_the_first_offered_actions_keep_their_places(self):
        """Behaviours queued before this release keep meaning the same."""
        first = {
            "vv1": [("ACT_STOP", 0x439470, 0), ("ACT_CALL_ARG", 0x443FA0, 9),
                    ("ACT_CALL_ARG", 0x444990, 1), ("ACT_CALL", 0x4410C0, 0), ("ACT_RECOVER", 0, 0)],
            "vv2": [("ACT_STOP", 0x4492A0, 0), ("ACT_CALL", 0x451690, 0), ("ACT_CALL", 0x452920, 0),
                    ("ACT_CALL", 0x454890, 0), ("ACT_EFFECT", 0x44AF20, 0), ("ACT_RECOVER", 0, 0)],
            "vv3": [("ACT_STOP", 0, 0), ("ACT_RECOVER", 0, 0)],
            "vv4": [("ACT_STOP", 0, 0), ("ACT_RECOVER", 0, 0)],
            "vv5": [("ACT_STOP", 0, 0), ("ACT_RECOVER", 0, 0)],
        }
        for game, want in first.items():
            with self.subTest(game=game):
                self.assertEqual([row[1:] for row in behaviour_table(game)[:len(want)]], want)

    def test_every_vv1_and_vv2_starter_has_a_stock_caller(self):
        """The owner's rule: an action no stock code starts is never offered."""
        for game in ("vv1", "vv2"):
            if not have_stock(game):
                continue
            for label, kind, routine, _ in behaviour_table(game):
                if routine == 0 or kind in ("ACT_STOP", "ACT_RECOVER"):
                    continue
                with self.subTest(game=game, behaviour=label):
                    self.assertGreater(stock_callers(game, routine), 0)

    def test_no_action_of_the_excluded_kinds_is_offered(self):
        banned = ("bury", "burying", "puzzle", "embrac", "clothes", "picking", "looking for", "teach",
                  "tag", "chief", "convert", "seeing the light", "guard")
        for game in GAMES:
            for label, *_ in behaviour_table(game):
                with self.subTest(game=game, behaviour=label):
                    self.assertFalse(any(word in label.lower() for word in banned), label)

    def test_recovers_fully(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            story = Story(game)
            v = story.village
            L = v.L
            v.put(2, sex="f", years=30, name="Patient", health=12)
            off, size = L["sick"]
            story.proc.write(v.record(2) + off, b"\1")
            story.record_call(STOPS[game][0], STOPS[game][1])
            recover = [row[1] for row in behaviour_table(game)].index("ACT_RECOVER")
            story.apply(Event(changes=[story.change(2, behaviour=recover)]))
            with self.subTest(game=game):
                self.assertEqual((v.sick(2), v.i32(2, L["health"])), (0, 100))


# ---------------------------------------------------------------------------
# Custom titles, set by the event and persisted
# ---------------------------------------------------------------------------

@emulated
class TitleSetTests(unittest.TestCase):
    def test_the_event_sets_and_removes_titles_and_publishes_the_dat(self):
        from story_custom_fixtures import MemoryFiles

        for game in GAMES:
            if not have_stock(game):
                continue
            story = Story(game)
            p = story.proc
            files = MemoryFiles(p)
            path = r"C:\Save\Custom Titles - Save 1.dat"
            p.write(SCRATCH, path.encode() + b"\0")
            p.export("VvfpStoryProbeTitlesLoaded", story.n, 1, SCRATCH)
            v = story.village
            v.put(2, sex="f", years=30, name="Hina")
            v.put(3, sex="m", years=30, name="Kai")
            ok, r, _ = story.apply(Event(changes=[story.change(2, title_op=1, title="Master Storyteller"),
                                                  story.change(3, title_op=1, title="Chief Fisher")],
                                         spawns=[Spawn(count=1, sex=2, age=300, name="Lani",
                                                       title="Newcomer")]))
            new = story.creations[0][0]
            with self.subTest(game=game):
                self.assertEqual(r["refused"], 0)
                game_id, entries = files.titles(path)
                self.assertEqual(game_id, story.n)
                self.assertEqual(sorted(entries), sorted([
                    (2, v.title_identity(2), "Master Storyteller"),
                    (3, v.title_identity(3), "Chief Fisher"),
                    (new, v.title_identity(new), "Newcomer")]))
                at = p.export("VvfpStoryProbeTitleOf", story.n, v.record(2))
                self.assertEqual(p.cstring(at), "Master Storyteller")
            story.apply(Event(changes=[story.change(3, title_op=2)]))
            with self.subTest(game=game, case="removed"):
                self.assertEqual(len(files.titles(path)[1]), 2)
                self.assertEqual(p.export("VvfpStoryProbeTitleOf", story.n, v.record(3)), 0)
            # A file deleted behind the table's back is Start Over: the old
            # village's titles are forgotten, never written back; the new
            # title starts the file afresh.
            files.files.clear()
            ok, r, _ = story.apply(Event(changes=[story.change(3, title_op=1, title="After")]))
            with self.subTest(game=game, case="start over"):
                self.assertEqual(r["refused"], 0)
                self.assertEqual(files.titles(path)[1], [(3, v.title_identity(3), "After")])
                self.assertEqual(p.export("VvfpStoryProbeTitleCount"), 1)

    def test_a_title_is_not_inherited_by_a_same_named_villager(self):
        """Codex, PR #495: names repeat, so the title is bound to the likes and
        dislikes as well; another Kai in the reused record shows no title."""
        from story_custom_fixtures import MemoryFiles

        for game in GAMES:
            if not have_stock(game):
                continue
            story = Story(game)
            p = story.proc
            MemoryFiles(p)
            p.write(SCRATCH, rb"C:\Save\Custom Titles - Save 1.dat" + b"\0")
            p.export("VvfpStoryProbeTitlesLoaded", story.n, 1, SCRATCH)
            v = story.village
            v.put(3, sex="m", years=30, name="Kai")
            story.apply(Event(changes=[story.change(3, title_op=1, title="Chief Fisher")]))
            v.put(3, sex="m", years=30, name="Kai")            # another Kai in the record
            p.put32(v.record(3) + v.L["likes"], 2)
            with self.subTest(game=game, case="another Kai"):
                self.assertEqual(p.export("VvfpStoryProbeTitleOf", story.n, v.record(3)), 0)
            p.put32(v.record(3) + v.L["likes"], 0xFFFFFFFF)  # the same Kai again
            with self.subTest(game=game, case="the same Kai"):
                self.assertEqual(p.cstring(p.export("VvfpStoryProbeTitleOf", story.n, v.record(3))),
                                 "Chief Fisher")

    def test_the_title_follows_its_villager_through_a_likes_change(self):
        from story_custom_fixtures import MemoryFiles

        for game in GAMES:
            if not have_stock(game):
                continue
            story = Story(game)
            p = story.proc
            files = MemoryFiles(p)
            path = r"C:\Save\Custom Titles - Save 1.dat"
            p.write(SCRATCH, path.encode() + b"\0")
            p.export("VvfpStoryProbeTitlesLoaded", story.n, 1, SCRATCH)
            v = story.village
            v.put(3, sex="m", years=30, name="Kai")
            story.apply(Event(changes=[story.change(3, title_op=1, title="Chief Fisher")]))
            ok, r, _ = story.apply(Event(changes=[story.change(3, like_add=1, dislike_add=2)]))
            with self.subTest(game=game):
                self.assertEqual(r["refused"], 0)
                self.assertEqual(p.cstring(p.export("VvfpStoryProbeTitleOf", story.n, v.record(3))),
                                 "Chief Fisher")
                self.assertEqual(files.titles(path)[1], [(3, v.title_identity(3), "Chief Fisher")])

    def test_a_spawned_villagers_title_that_cannot_be_saved_is_a_refused_change(self):
        """Codex, PR #495: a new villager's title whose file cannot be
        published (a full disk, a read-only folder) is counted as a change
        that could not be made, exactly as an existing villager's is."""
        from story_custom_fixtures import MemoryFiles

        for game in GAMES:
            if not have_stock(game):
                continue
            story = Story(game)
            p = story.proc
            files = MemoryFiles(p)
            path = r"C:\Save\Custom Titles - Save 1.dat"
            p.write(SCRATCH, path.encode() + b"\0")
            p.export("VvfpStoryProbeTitlesLoaded", story.n, 1, SCRATCH)

            def denied(q):
                files.last_error = 5            # ERROR_ACCESS_DENIED
                return 0, 12
            p.api_handlers["MoveFileExA"] = denied
            v = story.village
            v.put(2, sex="f", years=30, name="Hina")
            ok, r, _ = story.apply(Event(spawns=[Spawn(count=1, sex=2, age=300, name="Lani",
                                                       title="Newcomer")]))
            new = story.creations[0][0]
            with self.subTest(game=game):
                self.assertEqual((r["born"], r["refused"]), (1, 1))
                self.assertIsNone(files.titles(path))
                self.assertEqual(p.export("VvfpStoryProbeTitleOf", story.n, v.record(new)), 0)


# ---------------------------------------------------------------------------
# The popup text and the refusals
# ---------------------------------------------------------------------------

# (characters per line, lines, title characters, title is its own string)
PANEL = {"vv1": (51, 14, 51, False), "vv2": (46, 20, 46, False), "vv3": (48, 14, 30, True),
         "vv4": (48, 14, 30, True), "vv5": (48, 14, 30, True)}


@emulated
class TextTests(unittest.TestCase):
    def test_title_then_the_description_wrapped_to_the_games_panel(self):
        for game, (width, lines, title_width, separate) in PANEL.items():
            if not have_stock(game):
                continue
            story = Story(game)
            words = " ".join(["island"] * 30)
            ok, r, text = story.apply(Event(title="The Long Night", text=words))
            with self.subTest(game=game):
                self.assertEqual(ok, 1)
                body = text
                if not separate:
                    self.assertTrue(text.startswith("The Long Night\n\n\n\n"))
                    body = text.split("\n\n\n\n", 1)[1]
                else:
                    self.assertNotIn("The Long Night", text)
                self.assertEqual(body.replace("\n", " "), words)
                self.assertTrue(all(len(line) <= width for line in body.split("\n")))

    def test_refusals(self):
        for game, (width, lines, title_width, separate) in PANEL.items():
            if not have_stock(game):
                continue
            story = Story(game)
            story.village.put(1, sex="m", years=30, name="Adult")
            cases = [
                (Event(title="", text="x"), "Give the event a title."),
                (Event(title="100% sure", text="x"), "may use letters"),
                (Event(title="Night", text="a *star* fell"), "may use letters"),
                (Event(title="Night", text="(quiet)"), "may use letters"),
                (Event(title="Night", text="\n" * lines), "must fit"),
            ]
            if title_width < 47:            # the title field itself holds 47
                cases.append((Event(title="x" * (title_width + 1), text="x"), "must fit"))
            for event, words in cases:
                with self.subTest(game=game, title=event.title[:12], text=event.text[:12]):
                    self.assertIn(words, story.refusal(event) or "")
            with self.subTest(game=game, case="ok"):
                self.assertIsNone(story.refusal(Event(title="Night", text="All is well.")))
            story.room[0] = False
            with self.subTest(game=game, case="full village"):
                self.assertIn("no room", story.refusal(Event(spawns=[Spawn()])) or "")
                change = story.change(1, litter=1)
                self.assertIn("no room", story.refusal(Event(changes=[change])) or "")

    def test_no_adult_and_the_first_island_event(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            story = Story(game)
            story.village.put(1, sex="m", years=5, name="Kid")
            with self.subTest(game=game, case="no adult"):
                self.assertIn("living adult", story.refusal(Event()) or "")
            if game in ("vv1", "vv2"):
                story.village.put(2, sex="f", years=30, name="Adult")
                counter = story.village.world + (0x9E40 if game == "vv1" else 0x2E51C)
                story.proc.put32(counter, 0)
                with self.subTest(game=game, case="first event"):
                    self.assertIn("first island event", story.refusal(Event()) or "")


# ---------------------------------------------------------------------------
# Delivery through each game's own island-event path
# ---------------------------------------------------------------------------

def _set_custom(story, event: Event, tick=0):
    event.game = story.n
    story.proc.write(EVENT_BUF, event.pack())
    story.proc.export("VvfpStoryProbeSetCustom", story.n, EVENT_BUF, tick)
    story.proc.export("VvfpStoryProbeSetTick", tick)


# The event trigger's villager draw, per game: (call site, stock picker).
EVENT_PICK = {"vv1": (0x4237DD, 0x43BCD0), "vv2": (0x42EEED, 0x44BAE0),
              "vv3": (0x468757, 0x45C9D0), "vv4": (0x43FA70, 0x4679B0),
              "vv5": (0x44272F, 0x471870)}


@emulated
class FastDeliveryTests(unittest.TestCase):
    """A Custom Island Event arrives within seconds (the owner, 2026-10-06):
    while one is armed, the trigger's one random villager draw is asked
    again until it draws a villager the trigger accepts -- custom events
    only, all five games (native/vvfp_story_upgrades/story_fast_delivery.inc)."""

    def _pick(self, story, draws, fits, none=-1):
        buf = story.proc.alloc(8 * len(draws) + 4)
        story.proc.write(buf, struct.pack(f"<{len(draws)}i", *draws))
        story.proc.write(buf + 4 * len(draws), struct.pack(f"<{len(fits)}i", *fits))
        calls = buf + 8 * len(draws)
        drawn = story.proc.export("VvfpStoryProbeFastPick", buf, buf + 4 * len(draws),
                                  len(draws), none & 0xFFFFFFFF, calls)
        drawn = struct.unpack("<i", struct.pack("<I", drawn & 0xFFFFFFFF))[0]
        return drawn, struct.unpack("<i", story.proc.read(calls, 4))[0]

    def test_every_game_retargets_its_draw(self):
        for game, (site, stock) in EVENT_PICK.items():
            if not have_stock(game):
                continue
            story = Story(game)
            code = story.proc.read(site, 5)
            with self.subTest(game=game):
                self.assertEqual(code[0], 0xE8)
                target = (site + 5 + struct.unpack("<i", code[1:])[0]) & 0xFFFFFFFF
                self.assertNotEqual(target, stock, "the draw now goes through the wrapper")

    def test_it_draws_until_a_villager_fits(self):
        story = Story(next(g for g in GAMES if have_stock(g)))
        self.assertEqual(self._pick(story, [5, 6, 7, 8], [0, 0, 1, 0]), (7, 3))
        self.assertEqual(self._pick(story, [9], [1]), (9, 1), "a first fit is kept")

    def test_nobody_eligible_is_answered_at_once(self):
        story = Story(next(g for g in GAMES if have_stock(g)))
        self.assertEqual(self._pick(story, [-1, 3], [0, 1]), (-1, 1))
        self.assertEqual(self._pick(story, [0, 3], [0, 1], none=0), (0, 1))

    def test_a_village_where_nobody_fits_still_waits(self):
        """After 64 draws the last one goes back and the stock check fails,
        exactly as the game itself would."""
        story = Story(next(g for g in GAMES if have_stock(g)))
        self.assertEqual(self._pick(story, [4], [0]), (4, 64))


CHOOSER = {
    # game: (call site, resume, the game's chooser, text buffer size)
    "vv1": (0x428777, 0x42877C, 0x428470),
    "vv2": (0x4349B2, 0x4349B7, 0x434570),
}
BARREL_MAGNITUDE = 0x7F4B1A2C


@emulated
class ChooserDeliveryTests(unittest.TestCase):
    """A New Home and The Lost Children: the island event's chooser call."""

    def _run(self, game, magnitude=6, custom=True, between=None):
        site, resume, chooser = CHOOSER[game]
        story = Story(game)
        p = story.proc
        story.village.put(1, sex="m", years=30, name="Adult")
        story.record_call(chooser, 8)
        event_object = p.alloc(0x5100)
        if custom:
            _set_custom(story, Event(title="The Long Night", text="The stars went out.",
                                     food_op=ADD, food_amount=250,
                                     changes=[story.change(1, sick=1)]))
        if between is not None:
            between(story)
        esp = HEAP + 0x3000000
        p.put32(esp, 2)
        p.put32(esp + 4, magnitude)
        p.set_reg("esp", esp)
        p.set_reg("ecx", event_object)
        p.set_reg("ebx", 0x1111)
        p.set_reg("esi", event_object)
        p.set_reg("edi", 0x2222)
        p.set_reg("ebp", event_object + 0x277F)
        p.run(site, resume)
        return story, event_object, esp

    def test_an_armed_custom_event_is_the_event_the_game_shows(self):
        for game in CHOOSER:
            if not have_stock(game):
                continue
            story, obj, esp = self._run(game)
            p = story.proc
            with self.subTest(game=game):
                self.assertNotIn(CHOOSER[game][2], story.calls, "the game's own choice is not made")
                text = p.cstring(obj + 0x277F)
                self.assertTrue(text.startswith("The Long Night\n\n\n\nThe stars went out."), text)
                self.assertIn("250 food", text)
                self.assertEqual(story.village.sick(1), 1, "the changes are made")
                self.assertEqual(p.reg("esp"), esp + 8, "ret 8, as the chooser")
                self.assertEqual((p.reg("ebx"), p.reg("esi"), p.reg("edi"), p.reg("ebp")),
                                 (0x1111, obj, 0x2222, obj + 0x277F))
                self.assertEqual(p.export("VvfpStoryProbeCustomPending", story.n), 0, "taken once")

    def test_a_custom_event_never_reaches_another_village(self):
        """Queued in one village, then another slot loaded, Start Over or a
        tribe deleted: the game chooses its own event and nothing applies."""
        def other_slot(story):
            story.host.slot = 2

        def reset(story):
            story.proc.export("VvfpStoryVillageReset", story.n, 1)
        for game in CHOOSER:
            if not have_stock(game):
                continue
            for case, between in (("other slot", other_slot), ("start over", reset)):
                story, obj, esp = self._run(game, between=between)
                p = story.proc
                with self.subTest(game=game, case=case):
                    self.assertEqual(story.calls[CHOOSER[game][2]], [[obj, 2, 6]])
                    self.assertEqual(story.village.sick(1), 0, "nothing applies")
                    self.assertEqual(p.export("VvfpStoryProbeCustomPending", story.n), 0)
                    stats = struct.unpack("<4i", p.read(p.exports["VvfpStoryStats"], 16))
                    self.assertEqual((stats[0], stats[3]), (0, 1), "discarded, not delivered")
            with self.subTest(game=game, case="same village"):
                story, obj, esp = self._run(game, between=lambda s: setattr(s.host, "slot", 1))
                self.assertNotIn(CHOOSER[game][2], story.calls)
                self.assertEqual(story.village.sick(1), 1)

    def test_without_a_custom_event_the_game_chooses(self):
        for game in CHOOSER:
            if not have_stock(game):
                continue
            story, obj, esp = self._run(game, custom=False)
            with self.subTest(game=game):
                self.assertEqual(story.calls[CHOOSER[game][2]], [[obj, 2, 6]])
                self.assertEqual(story.proc.reg("esp"), esp + 8)

    def test_the_origins_barrel_always_reaches_the_games_chooser(self):
        for game in CHOOSER:
            if not have_stock(game):
                continue
            story, obj, esp = self._run(game, magnitude=BARREL_MAGNITUDE)
            with self.subTest(game=game):
                self.assertEqual(story.calls[CHOOSER[game][2]], [[obj, 2, BARREL_MAGNITUDE]])
                self.assertEqual(story.proc.export("VvfpStoryProbeCustomPending", story.n), 1,
                                 "still armed for the island event")

    def test_the_family_rolls_send_an_armed_custom_event_to_its_family(self):
        rolls = {"vv1": ((0x423818, 100, 99), (0x42383A, 100, 0), 0x402F10),
                 "vv2": ((0x42EF28, 100, 99), (0x42EF4A, 100, 0), 0x4031A0)}
        for game, (first, second, rand) in rolls.items():
            if not have_stock(game):
                continue
            story = Story(game)
            p = story.proc
            p.stub(rand, lambda q: (42, 0))
            esp = HEAP + 0x3000000
            for site, bound, _ in (first, second):
                p.put32(esp, bound)
                p.set_reg("esp", esp)
                p.run(site, site + 5)
                with self.subTest(game=game, site=hex(site), armed=False):
                    self.assertEqual(p.reg("eax"), 42, "no custom event: the game's own roll")
            _set_custom(story, Event())
            for site, bound, want in (first, second):
                p.put32(esp, bound)
                p.set_reg("esp", esp)
                p.run(site, site + 5)
                with self.subTest(game=game, site=hex(site), armed=True):
                    self.assertEqual(p.reg("eax"), want)


SELECT = {
    # game: (event table, site, resume, register, string lookup, string table, title id, body id)
    "vv3": (0x4B3C78, 0x419BDB, 0x419BE2, "edx", 0x42F190, 0x592730, 0x4CB, 0x4CC),
    "vv4": (0x4CCA28, 0x4180F7, 0x4180FE, "eax", 0x44D3D0, 0x4DEA20, 0x32A, 0x32B),
    "vv5": (0x4DC850, 0x41895B, 0x418962, "eax", 0x4506D0, 0x5240A8, 0x3AD, 0x3AE),
}


@emulated
class ObjectDeliveryTests(unittest.TestCase):
    """The Secret City, The Tree of Life, New Believers: the selector's
    chosen event object."""

    def _at_site(self, game, *, custom=True, barrel=False):
        table, site, resume, register, *_ = SELECT[game]
        story = Story(game)
        p = story.proc
        story.village.put(1, sex="m", years=30, name="Adult")
        stock = {}
        for slot in range(1, 58):
            obj = p.alloc(0x20)
            p.put32(table + 4 * slot, obj)
            stock[slot] = obj
        if barrel:
            for slot in range(1, 58):
                p.put32(table + 4 * slot, stock[1])
        if custom:
            _set_custom(story, Event(title="The Long Night", text="The stars went out.",
                                     tech_op=ADD, tech_amount=900,
                                     changes=[story.change(1, sick=1)]))
        p.set_reg("esi", 5)
        p.set_reg("esp", HEAP + 0x3000000)
        p.run(site, resume)
        return story, stock, p.reg("esi"), p.reg(register)

    def test_the_presenter_is_handed_the_custom_event(self):
        for game, (table, site, resume, register, lookup, strings, title_id, body_id) in SELECT.items():
            if not have_stock(game):
                continue
            story, stock, esi, obj = self._at_site(game)
            p = story.proc
            with self.subTest(game=game):
                self.assertEqual(obj, p.export("VvfpStoryProbeObject"))
                self.assertEqual(esi, 5, "the chosen slot stays valid (the selector marks it seen)")
                vtable = p.u32(obj)
                self.assertEqual((p.u32(obj + 4), p.u32(obj + 8)), (0, 0xFFFFFFFF),
                                 "no featured villager, amount -1: the body is copied as it is")
                # The object's own title and body ids, through the game's own string lookup.
                title = p.call(p.u32(vtable + 8), [], ecx=obj)
                body = p.call(p.u32(vtable + 0xC), [], ecx=obj)
                self.assertEqual((title, body), (title_id, body_id))
                self.assertEqual(p.cstring(p.call(lookup, [title])), "The Long Night")
                text = p.cstring(p.call(lookup, [body]))
                self.assertTrue(text.startswith("The stars went out."), text)
                self.assertIn("900 tech points", text)
                self.assertNotIn("The Long Night", text)
                self.assertEqual(story.village.sick(1), 1)
                # Apply on OK does nothing more (the changes are already made).
                p.call(p.u32(vtable + 0x30), [], ecx=obj)
                self.assertEqual(p.u32(obj + 8), 0xFFFFFFFF)

    def test_without_a_custom_event_the_selector_is_unchanged(self):
        for game, (table, site, resume, register, *_) in SELECT.items():
            if not have_stock(game):
                continue
            story, stock, esi, obj = self._at_site(game, custom=False)
            with self.subTest(game=game):
                self.assertEqual((esi, obj), (5, stock[5]))

    def test_the_secret_citys_barrel_never_takes_a_custom_event(self):
        if not have_stock("vv3"):
            self.skipTest("no stock executable")
        story, stock, esi, obj = self._at_site("vv3", barrel=True)
        self.assertEqual(obj, stock[1])
        self.assertEqual(story.proc.export("VvfpStoryProbeCustomPending", 3), 1)


# ---------------------------------------------------------------------------
# The lock: one pick or custom event at a time, as the Island Event row
# ---------------------------------------------------------------------------

@emulated
class CustomLockTests(unittest.TestCase):
    def _world(self, proc, game):
        import test_story_cheat_upgrades as part1

        return part1.LockTests._world(None, proc, game)

    def test_queueing_writes_exactly_what_the_island_event_purchase_writes(self):
        import test_story_cheat_upgrades as part1

        for game in GAMES:
            if not have_stock(game):
                continue
            n = int(game[2:])
            with self.subTest(game=game):
                queued = Process(render(game, "collection_progression"), TEST_DLL)
                queued_world = self._world(queued, game)
                queued.write(EVENT_BUF, Event(game=n).pack())
                self.assertEqual(queued.export("VvfpStoryProbeQueueCustom", n, EVENT_BUF, 0), 1)
                bought = Process(render(game, "collection_progression"), TEST_DLL)
                bought_world = self._world(bought, game)
                part1.LockTests._purchase(None, bought, game, bought_world)
                for (base_q, off, size), (base_b, _, _) in zip(
                        part1.LockTests.STATE[game](queued_world), part1.LockTests.STATE[game](bought_world)):
                    self.assertEqual(queued.read(base_q + off, size), bought.read(base_b + off, size), hex(off))

    def test_one_pick_or_custom_event_at_a_time(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            n = int(game[2:])
            with self.subTest(game=game, armed="custom"):
                proc = Process(render(game, "collection_progression"), TEST_DLL)
                self._world(proc, game)
                proc.write(EVENT_BUF, Event(game=n).pack())
                proc.export("VvfpStoryProbeQueueCustom", n, EVENT_BUF, 0)
                self.assertEqual(proc.export("VvfpStoryPickPending", n), 1)
                self.assertEqual(proc.export("VvfpStoryProbePending", n), 1, "the game's own pending check")
                # Neither a pick nor a second custom event reaches its dialog.
                self.assertEqual(proc.export("VvfpStoryPickIslandEvent", n, 0), 0)
                self.assertIn("already queued", proc.messages[-1])
                self.assertEqual(proc.export("VvfpStoryCustomIslandEvent", n, 0), 0)
                self.assertIn("already queued", proc.messages[-1])
            with self.subTest(game=game, armed="pick"):
                proc = Process(render(game, "collection_progression"), TEST_DLL)
                self._world(proc, game)
                proc.export("VvfpStoryProbeArm", n, 0, 0)
                self.assertEqual(proc.export("VvfpStoryCustomIslandEvent", n, 0), 0)
                self.assertIn("already queued", proc.messages[-1])

    def test_queueing_remembers_the_village_it_was_queued_in(self):
        """The purchase paths (not the probes that set state directly) bind
        the queued event to the slot and the reset generation."""
        for game in GAMES:
            if not have_stock(game):
                continue
            n = int(game[2:])
            for kind in ("custom", "pick"):
                for change in ("none", "other slot", "reset"):
                    story = Story(game, slot=3)
                    p = story.proc
                    self._world(p, game)
                    if kind == "custom":
                        p.write(EVENT_BUF, Event(game=n).pack())
                        self.assertEqual(p.export("VvfpStoryProbeQueueCustom", n, EVENT_BUF, 0), 1)
                    else:
                        self.assertGreaterEqual(p.export("VvfpStoryProbeArm", n, 0, 0), 0)
                    if change == "other slot":
                        story.host.slot = 4
                    elif change == "reset":
                        p.export("VvfpStoryVillageReset", n, 3)
                    with self.subTest(game=game, kind=kind, change=change):
                        self.assertEqual(p.export("VvfpStoryPickPending", n), 1 if change == "none" else 0)

    def test_a_custom_event_waits_however_long_it_takes(self):
        """The owner (2026-10-06): a Custom Island Event no longer lapses
        after ten minutes; it waits until the game runs an island event."""
        for game in GAMES:
            if not have_stock(game):
                continue
            story = Story(game)
            _set_custom(story, Event(), tick=1000)
            for later in (TEN_MINUTES + 1, 24 * 60 * 60 * 1000):
                story.proc.export("VvfpStoryProbeSetTick", 1000 + later)
                with self.subTest(game=game, later=later):
                    self.assertEqual(story.proc.export("VvfpStoryProbeCustomPending", story.n), 1)
            stats = struct.unpack("<3i", story.proc.read(story.proc.exports["VvfpStoryStats"], 12))
            self.assertEqual(stats[2], 0, "nothing lapsed")


# ---------------------------------------------------------------------------
# The custom title in each game's villager panel
# ---------------------------------------------------------------------------

@emulated
class TitleHookTests(unittest.TestCase):
    def _story(self, game):
        story = Story(game)
        p = story.proc
        p.write(SCRATCH, b"C:\\Save\\Custom Titles - Save 1.dat\0")
        p.export("VvfpStoryProbeTitlesLoaded", story.n, 1, SCRATCH)
        v = story.village
        v.put(2, sex="f", years=30, name="Hina")
        v.put(3, sex="m", years=30, name="Kai")
        p.write(SCRATCH + 0x100, b"Keeper of Stories\0")
        self.assertEqual(p.export("VvfpStoryProbeTitleSet", story.n, 2, SCRATCH + 0x100), 1)
        return story

    def _panel(self, story, index):
        """Run the title site as the HUD reaches it for record `index`;
        returns the text the label is given."""
        p = story.proc
        v = story.village
        game = story.game
        esp = HEAP + 0x3000000
        buffer_text = b"Master Farmer\0"
        if game == "vv1":
            p.put32(v.world + 0xAD34, index)
            p.write(esp + 0x24, buffer_text)
            p.set_reg("esp", esp)
            p.run(0x41FD75, 0x41FD7A)
            self.assertEqual(p.reg("esp"), esp - 4)
            return p.cstring(p.u32(p.reg("esp")))
        if game == "vv2":
            p.put32(v.world + 0x304F0, index)
            seen = []
            p.stub(0x40C510, lambda q: (seen.append(q.cstring(q.arg(0))) or 0, 4))
            text = p.alloc(0x40)
            p.write(text, buffer_text)
            p.put32(esp, text)
            p.set_reg("esp", esp)
            p.set_reg("ecx", 0x5555)
            p.run(0x429DE3, 0x429DE8)
            self.assertEqual(p.reg("esp"), esp + 4)
            return seen[0]
        p.set_reg("ebp", p.alloc(0x200))
        if game in ("vv3", "vv4"):
            p.put32(esp + 0x10, v.record(index))
            p.write(esp + 0x28, buffer_text)
            p.set_reg("esp", esp)
            site, resume = (0x468FC8, 0x468FCE) if game == "vv3" else (0x4404D9, 0x4404DE)
            p.run(site, resume)
            return p.cstring(esp + 0x28)
        p.set_reg("esi", v.record(index))
        p.write(esp + 0x24, buffer_text)
        p.set_reg("esp", esp)
        p.run(0x44319E, 0x4431A4)
        return p.cstring(esp + 0x24)

    def test_the_panel_shows_the_custom_title_of_that_villager_only(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            story = self._story(game)
            with self.subTest(game=game, villager="titled"):
                self.assertEqual(self._panel(story, 2), "Keeper of Stories")
            with self.subTest(game=game, villager="other"):
                self.assertEqual(self._panel(story, 3), "Master Farmer")
            # A birth reusing the record: another villager, not the title's.
            story.village.put(2, sex="f", years=0.5, name="Baby")
            with self.subTest(game=game, villager="reused record"):
                self.assertEqual(self._panel(story, 2), "Master Farmer")


# ---------------------------------------------------------------------------
# The population cap of each mode: the game's own room predicate, run
# ---------------------------------------------------------------------------

CAPS = {
    "vv1": {"stock": 90, "collection_progression": 256, "immediate_fixed": 256},
    "vv3": {"stock": 90, "collection_progression": 115, "immediate_fixed": 150},
    "vv4": {"stock": 90, "collection_progression": 125, "immediate_fixed": 150},
    "vv5": {"stock": 90, "collection_progression": 135, "immediate_fixed": 150},
    "vv2": {"stock": 90, "collection_progression": 231, "immediate_fixed": 256},
}


@emulated
class ModeParityTests(unittest.TestCase):
    def _real_room(self, story):
        """Leave the game's own room predicate to run; answer only the
        housing / building gates it asks (all built)."""
        p = story.proc
        v = story.village
        room_va = {"vv1": 0x43A1A0, "vv2": 0x44B310, "vv3": 0x45FE30, "vv4": 0x468350,
                   "vv5": 0x472BD0}[story.game]
        p.stubs.pop(room_va, None)
        if story.game == "vv1":
            for off in (0x9FE8, 0x9FF0, 0x9FF8):
                p.write(v.world + off, b"\1")
        if story.game == "vv2":
            for off in (0x2E818, 0x2E820, 0x2E828):
                p.write(v.world + off, b"\1")
            p.stub(0x426120, lambda q: (0, 4))           # no collections completed
        if story.game == "vv3":
            p.stub(0x4321F0, lambda q: (1, 4))           # buildings built
            p.stub(0x42DE40, lambda q: (0, 4))           # no population techs
            p.stub(0x426FC0, lambda q: (0, 4))
        if story.game == "vv4":
            p.stub(0x438960, lambda q: (1, 4))
        if story.game == "vv5":
            p.stub(0x43AE80, lambda q: (1, 4))

    def test_new_villagers_stop_at_each_modes_cap(self):
        for game, caps in CAPS.items():
            if not have_stock(game):
                continue
            for mode, cap in caps.items():
                story = Story(game, mode)
                self._real_room(story)
                v = story.village
                for i in range(cap - 3):
                    v.put(i, sex="m" if i % 2 else "f", years=20, name=f"V{i}")
                ok, r, _ = story.apply(Event(spawns=[Spawn(count=10, sex=1, age=400)]))
                with self.subTest(game=game, mode=mode, cap=cap):
                    self.assertEqual((r["born"], r["no_room_spawns"]), (3, 7))


@emulated
class RecordLimitTests(unittest.TestCase):
    """A corpse keeps its record until it is buried, so in the modes whose
    cap is the whole record array the game's own predicate (which counts the
    living) can say yes while no record is free; the creator must never be
    called then (A New Home's scans with no bound)."""

    def test_corpses_holding_the_last_records_refuse_new_villagers(self):
        limits = {"vv1": 256, "vv3": 150, "vv4": 150, "vv5": 150}
        for game, records in limits.items():
            if not have_stock(game):
                continue
            story = Story(game, "immediate_fixed")
            ModeParityTests._real_room(None, story)
            v = story.village
            for i in range(records - 6):
                v.put(i, sex="m" if i % 2 else "f", years=20, name=f"V{i}")
            for i in range(records - 6, records):
                v.put(i, sex="m", years=20, name=f"Dead{i}", health=0)
            ok, r, _ = story.apply(Event(spawns=[Spawn(count=3, sex=1, age=400)]))
            creator = {"vv1": 0x43C350, "vv3": 0x45FF50, "vv4": 0x467D10, "vv5": 0x471E20}[game]
            with self.subTest(game=game):
                self.assertEqual((r["born"], r["no_room_spawns"]), (0, 3))
                self.assertNotIn(creator, story.calls, "the creator is never asked without a free record")
                p = story.proc
                room_va = {"vv1": 0x43A1A0, "vv3": 0x45FE30, "vv4": 0x468350, "vv5": 0x472BD0}[game]
                this = v.base if game == "vv1" else {"vv3": 0x59E110, "vv4": 0x50E568, "vv5": 0x554148}[game]
                # The Secret City's, The Tree of Life's and New Believers'
                # predicates count the records themselves since v1.35.58
                # (scripts/build_record_guards_vv345.py); A New Home's guards
                # sit at its creators instead.
                self.assertEqual(p.call(room_va, [], ecx=this) & 0xFF, 1 if game == "vv1" else 0,
                                 "the game's own predicate alone")


@emulated
class LockStaysWhileArmedTests(unittest.TestCase):
    """Pick Island Event and Custom Island Event exclude each other for as
    long as one is armed -- even once the game's own pending state no longer
    shows it (the game rescheduled its countdown without running it)."""

    def test_the_lock_is_the_armed_event_not_only_the_games_countdown(self):
        lock = CustomLockTests()
        for game in GAMES:
            if not have_stock(game):
                continue
            n = int(game[2:])
            with self.subTest(game=game, armed="custom"):
                proc = Process(render(game, "collection_progression"), TEST_DLL)
                lock._world(proc, game)
                proc.write(EVENT_BUF, Event(game=n).pack())
                proc.export("VvfpStoryProbeQueueCustom", n, EVENT_BUF, 0)
                lock._world(proc, game)                 # the game's pending state is clear again
                self.assertEqual(proc.export("VvfpStoryProbePending", n), 0)
                self.assertEqual(proc.export("VvfpStoryPickIslandEvent", n, 0), 0)
                self.assertIn("already queued", proc.messages[-1])
            with self.subTest(game=game, armed="pick"):
                proc = Process(render(game, "collection_progression"), TEST_DLL)
                lock._world(proc, game)
                proc.export("VvfpStoryProbeArm", n, 0, 0)
                lock._world(proc, game)
                self.assertEqual(proc.export("VvfpStoryProbePending", n), 0)
                self.assertEqual(proc.export("VvfpStoryCustomIslandEvent", n, 0), 0)
                self.assertIn("already queued", proc.messages[-1])


@emulated
class RefusedChangeTextTests(unittest.TestCase):
    def test_the_popup_says_how_many_changes_the_game_did_not_allow(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            story = Story(game)
            v = story.village
            v.put(4, sex="f", years=30, name="Full")
            for k in range(v.L["slots"]):            # every likes slot taken
                story.proc.put32(v.record(4) + v.L["likes"] + 4 * k, k + 1)
            ok, r, text = story.apply(Event(changes=[story.change(4, like_add=0)]))
            with self.subTest(game=game):
                self.assertEqual(r["refused"], 1)
                flat = " ".join(text.split())
                self.assertIn("1 change could not be made", flat)
                self.assertIn("a likes or dislikes list was full", flat)


# ---------------------------------------------------------------------------
# The dialogs: every control the code drives exists in the shipped DLL
# ---------------------------------------------------------------------------

def _sz_or_ord(data, at):
    if struct.unpack_from("<H", data, at)[0] == 0xFFFF:
        return struct.unpack_from("<H", data, at + 2)[0], at + 4
    end = at
    while struct.unpack_from("<H", data, end)[0] != 0:
        end += 2
    return data[at:end].decode("utf-16-le"), end + 2


def _dialogs(dll_path):
    """{dialog id: (caption, {control id: (class, text, style)})} from the
    DLL's RT_DIALOG resources (DLGTEMPLATEEX)."""
    import pefile as pe_module

    pe = pe_module.PE(str(dll_path))
    out = {}
    for kind in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if kind.id != 5:                      # RT_DIALOG
            continue
        for entry in kind.directory.entries:
            leaf = entry.directory.entries[0].data.struct
            data = pe.get_data(leaf.OffsetToData, leaf.Size)
            version, signature = struct.unpack_from("<HH", data, 0)
            assert (version, signature) == (1, 0xFFFF)
            style = struct.unpack_from("<I", data, 12)[0]
            count = struct.unpack_from("<H", data, 16)[0]
            at = 26
            _, at = _sz_or_ord(data, at)        # menu
            _, at = _sz_or_ord(data, at)        # class
            caption, at = _sz_or_ord(data, at)
            if style & 0x40:                    # DS_SETFONT
                at += 6
                _, at = _sz_or_ord(data, at)
            controls = {}
            for _ in range(count):
                at = (at + 3) & ~3
                ctl_style = struct.unpack_from("<I", data, at + 8)[0]
                ctl_id = struct.unpack_from("<i", data, at + 20)[0]
                at += 24
                cls, at = _sz_or_ord(data, at)
                text, at = _sz_or_ord(data, at)
                extra = struct.unpack_from("<H", data, at)[0]
                at += 2 + extra
                controls[ctl_id] = (cls, text, ctl_style)
            out[entry.id] = (caption, controls)
    return out


class DialogResourceTests(unittest.TestCase):
    DLL = ROOT / "assets" / "story_upgrades" / "VVFP Story Upgrades.dll"

    def test_every_control_the_dialogs_drive_is_in_the_shipped_dialog(self):
        if not HAVE_EMULATOR:
            self.skipTest("pefile not installed")
        dialogs = _dialogs(self.DLL)
        ui = (SOURCE / "story_custom_ui.inc").read_text(encoding="utf-8")
        ids = dict(re.findall(r"(IDC_[A-Z_]+) = (\d+)", ui))
        owner = {"IDC_CE_": 302, "IDC_CH_": 303, "IDC_SP_": 304, "IDC_PA_": 305, "IDC_VA_": 306,
                 "IDC_PZ_": 307, "IDC_RV_": 308, "IDC_UB_": 309, "IDC_CC_": 310}
        for name, value in ids.items():
            dialog = next(d for prefix, d in owner.items() if name.startswith(prefix))
            span = {"IDC_CH_TOGGLE_FIRST": 5, "IDC_CH_SKILL_FIRST": 6, "IDC_CH_SKILL_LABEL_FIRST": 6,
                    "IDC_SP_LIKE_FIRST": 3, "IDC_SP_DISLIKE_FIRST": 3, "IDC_SP_SKILL_FIRST": 6,
                    "IDC_SP_SKILL_LABEL_FIRST": 6}.get(name, 2 if name.startswith("IDC_CC_")
                                                       and name.endswith("_FIRST") else 1)
            for k in range(span):
                with self.subTest(control=name, k=k):
                    self.assertIn(int(value) + k, dialogs[dialog][1])

    def test_the_target_list_and_the_toggles_are_what_the_owner_named(self):
        if not HAVE_EMULATOR:
            self.skipTest("pefile not installed")
        caption, controls = _dialogs(self.DLL)[303]
        LBS_EXTENDEDSEL = 0x0800
        self.assertTrue(controls[2001][2] & LBS_EXTENDEDSEL, "Ctrl+click / Shift+click selection")
        self.assertEqual([controls[2002 + k][1] for k in range(5)],
                         ["All Adult Women", "All Adult Men", "All Females", "All Males", "All Children"])
        self.assertEqual([controls[2100 + k][1] for k in range(7)],
                         ["All Heathens", "All Blue Heathens", "All Red Heathens", "All Orange Heathens",
                          "All Purple Heathens", "All Chief Heathens", "All Heathen Mommies"])
        self.assertEqual(_dialogs(self.DLL)[302][0], "Custom Island Event")

    def test_the_tech_menu_offers_custom_island_event(self):
        bridge = (ROOT / "native" / "shared" / "story_bridge.h").read_text(encoding="utf-8")
        # The label carries the price the Story DLL charges now (0, or 30,000
        # with Story / Cheat Upgrades cost Tech Points).
        self.assertIn('vvfp_story_label(game, "Custom Island Event"', bridge)
        self.assertIn('"%s (%d,%03d tech points)..."', bridge)
        self.assertIn("#define VVFP_STORY_CUSTOM_ID 4091", bridge)
        for game, path in {
            "vv1": ROOT / "native" / "vv1_origins_icons" / "vv1_origins_icons.c",
            "vv2": ROOT / "native" / "vv2_origins_icons" / "vv2_origins_icons.c",
            "vv3": ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.c",
            "vv4": ROOT / "native" / "vv4_origins_icons" / "vv4_origins_icons.c",
            "vv5": ROOT / "native" / "vv5_task9_origins" / "vv5_task9_origins.c",
        }.items():
            source = path.read_text(encoding="utf-8")
            with self.subTest(game=game):
                self.assertIn("command == VVFP_STORY_PICK_ID || command == VVFP_STORY_CUSTOM_ID", source)
                body = source[source.index("command == VVFP_STORY_CUSTOM_ID"):][:700]
                self.assertIn("ISLAND", body, "the custom event shares the Island Event row's lock")
                self.assertIn("vvfp_story_host_table(void)", source)
        vv3 = (ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.c").read_text(
            encoding="utf-8")
        draw = vv3[vv3.index("void __stdcall VV3WorldMaskDrawAt(void *record, int *args)\n{"):][:900]
        self.assertIn("vvfp_story_bridge(3);", draw, "The Secret City installs from its per-frame draw")

    def test_the_shipped_dll_carries_no_probe(self):
        if not HAVE_EMULATOR:
            self.skipTest("pefile not installed")
        import pefile as pe_module

        names = {e.name.decode() for e in pe_module.PE(str(self.DLL)).DIRECTORY_ENTRY_EXPORT.symbols if e.name}
        self.assertTrue({"VvfpStoryCustomIslandEvent", "VvfpStoryAttachHost"} <= names)
        self.assertFalse({n for n in names if "Probe" in n or "Stats" in n})


# ---------------------------------------------------------------------------
# Births count in the statistics exactly as a natural conception's do
# ---------------------------------------------------------------------------

# game: (the natural conception routine, the game's rand, its twins tech level
# (a stub VA, or a world offset), the counters: Babies Made, Twins Birthed,
# Triplets Birthed (VV2: the statistics row's pending twins field)).
NATURAL = {
    "vv1": dict(routine=0x43BBC0, rand=0x402F10, level=("world", 0xA2DC),
                counters=("world", (0x9E24, 0x9E44, 0x9E48))),
    "vv2": dict(routine=0x44B980, rand=0x4031A0, level=("world", 0x2EA8C),
                counters=("world", (0x2E500, 0x2E5E4, 0x2E524))),
    "vv3": dict(routine=0x455AB0, rand=0x4032D0, level=("stub", 0x426FC0, 4),
                counters=("abs", (0x5824A8, 0x5824C8, 0x5824CC))),
    "vv4": dict(routine=0x45E7B0, rand=0x4036D0, level=("stub", 0x41E1C0, 4),
                counters=("abs", (0x4D6DE8, 0x4D6E08, 0x4D6E0C))),
    "vv5": dict(routine=0x465E00, rand=0x403660, level=("stub", 0x423600, 4),
                counters=("abs", (0x51D360, 0x51D380, 0x51D384))),
}
ROLLS = {1: [99], 2: [0, 99], 3: [0, 0]}     # rand(100): < 7 twins, then < 25 triplets


@emulated
class NaturalBirthCountTests(unittest.TestCase):
    """A custom single, twin and triplet pregnancy moves Babies Made, Twins
    Birthed and Triplets Birthed exactly as the game's own conception does
    for the same litter, in each game, with the whole public catalog (the
    statistics and parentage rows' hooks) installed."""

    def _story(self, game, litter):
        story = Story(game, full=True)
        p = story.proc
        v = story.village
        cfg = NATURAL[game]
        v.put(1, sex="m", years=30, name="Papa", head=7, body=8)
        v.put(2, sex="f", years=30, name="Mama", head=1, body=2)
        rolls = list(ROLLS[litter])
        p.stub(cfg["rand"], lambda q: ((rolls.pop(0) if rolls else 99) if q.arg(0) == 100 else 0, 0))
        kind = cfg["level"][0]
        if kind == "world":
            p.put32(v.world + cfg["level"][1], 3)
            if game == "vv1":
                p.put32(v.world + 0xA090, 1)      # A New Home's triplets need this too
        else:
            p.stub(cfg["level"][1], lambda q: (3, cfg["level"][2]))
        for va, pop in {"vv3": [(0x412CD0, 4)], "vv4": [(0x412F90, 8)]}.get(game, []):
            p.stub(va, lambda q, pop=pop: (0, pop))
        return story

    def _counters(self, story):
        kind, offsets = NATURAL[story.game]["counters"]
        base = story.village.world if kind == "world" else 0
        return [story.proc.u32(base + o) for o in offsets]

    def _natural(self, story):
        p = story.proc
        v = story.village
        g = story.game
        mother, father = v.record(2), v.record(1)
        name = father + v.L["name"]
        if g == "vv1":
            p.call(0x43BBC0, [2, p.u32(father + 0x36C), 0, 0], ecx=v.base)
        elif g == "vv2":
            p.call(0x44B980, [2, p.u32(father + 0x554), 0, 0, name, 7, 8], ecx=v.base)
        elif g == "vv3":
            p.call(0x455AB0, [p.u32(father + 0xDD0), 0, 0, name, 7, 8, 0], ecx=mother)
        else:
            p.call(NATURAL[g]["routine"], [p.u32(father + 0x1B98), 0, 0, name, 7, 8, 0], ecx=mother)

    def test_custom_births_count_as_natural_ones(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            for litter in (1, 2, 3):
                natural = self._story(game, litter)
                before = self._counters(natural)
                self._natural(natural)
                v = natural.village
                self.assertEqual(v.i32(2, v.L["litter"]) in ((0, 1) if litter == 1 else (litter,)), True,
                                 (game, litter, "the rolls gave the natural litter"))
                natural_delta = [a - b for a, b in zip(self._counters(natural), before)]

                custom = self._story(game, 1)              # the game's own roll says one baby
                before = self._counters(custom)
                ok, r, _ = custom.apply(Event(changes=[custom.change(
                    2, litter=litter, father=1, father_fingerprint=custom.village.identity(1))]))
                custom_delta = [a - b for a, b in zip(self._counters(custom), before)]
                with self.subTest(game=game, litter=litter):
                    self.assertEqual(r["conceived"], litter)
                    self.assertEqual(natural_delta, [litter, int(litter == 2), int(litter == 3)],
                                     "the natural conception's own counts")
                    self.assertEqual(custom_delta, natural_delta)

    def test_a_rolled_multiple_is_not_counted_twice(self):
        """The forced conception VV4 and VV5 call rolls and counts twins or
        triplets itself; a custom single or twin must take that back."""
        for game in ("vv4", "vv5"):
            if not have_stock(game):
                continue
            for rolled, litter in ((3, 1), (2, 3), (3, 2)):
                story = self._story(game, rolled)
                before = self._counters(story)
                ok, r, _ = story.apply(Event(changes=[story.change(2, litter=litter)]))
                delta = [a - b for a, b in zip(self._counters(story), before)]
                with self.subTest(game=game, rolled=rolled, chosen=litter):
                    self.assertEqual(delta, [litter, int(litter == 2), int(litter == 3)])


# ---------------------------------------------------------------------------
# Start Over and a deleted tribe tell the story companion (Save Reset DLL)
# ---------------------------------------------------------------------------

NOTIFY_BUILD = ROOT / "scripts" / "build_story_notify_harness.ps1"
NOTIFY_CL = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC"
                 r"\14.51.36231\bin\Hostx64\x86\cl.exe")


class VillageResetNotifyTests(unittest.TestCase):
    """native/save_reset_export/story_notify_harness.c compiles the shipped
    ResetDeletedTribe with its module lookups and sweep recorded (nothing on
    disk is touched) and checks the story companion is told, in all five
    games, only when it is loaded and exports VvfpStoryVillageReset."""

    def test_both_sides_name_the_same_export(self):
        reset = (ROOT / "native/save_reset_export/save_reset_export.c").read_text(encoding="utf-8")
        self.assertIn('GetModuleHandleA("VVFP Story Upgrades.dll")', reset)
        self.assertIn('GetProcAddress(story, "VvfpStoryVillageReset")', reset)
        self.assertNotIn("LoadLibrary", reset)
        for name in ("vvfp_story_upgrades.def", "vvfp_story_upgrades_test.def"):
            with self.subTest(def_file=name):
                text = (ROOT / "native/vvfp_story_upgrades" / name).read_text(encoding="utf-8")
                self.assertIn("VvfpStoryVillageReset=_VvfpStoryVillageReset@8", text)

    @unittest.skipUnless(NOTIFY_CL.exists(), "the 32-bit MSVC toolchain is not installed")
    def test_the_reset_tells_the_story_companion(self):
        import subprocess

        run = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(NOTIFY_BUILD)],
            capture_output=True, text=True, timeout=600)
        self.assertEqual(run.returncode, 0, run.stdout[-3000:] + run.stderr[-2000:])
        self.assertIn("0 failure(s)", run.stdout)
        self.assertNotIn("[FAIL]", run.stdout)
        for game in range(1, 6):
            self.assertIn(f"THE STORY COMPANION IS TOLD THE VILLAGE IS GONE (game {game})", run.stdout)
            # The same harness covers the Cause of Death companion's graves
            # table (tests/test_cause_of_death.py pins the names).
            self.assertIn(f"THE CAUSE OF DEATH COMPANION IS TOLD THE VILLAGE IS GONE (game {game})",
                          run.stdout)
