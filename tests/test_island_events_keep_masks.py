"""Island events keep the masks villagers wear (the owner, 2026-11-25: "island events should keep masks on the
villager if they have them!!!!!!!!!!").

Every path that took or changed a mask the villager had, emulated with a villager in the orange, red and blue mask:

1. THE SECRET CITY'S OWN EVENTS.  Many of its island events change the Likes or Dislikes of the villager they are
   about -- the outcomes' calls of the likes adder 0x454890 and the dislikes remover 0x454780 (0x415B8F..0x415BA2:
   likes.add(3), dislikes.remove(3); 0x416B66..0x416B96 ...) -- and The Secret City keeps a mask under a fingerprint
   that holds them.  The real "VVFP Origins Icons.dll" (native/vv3_full_mastery_candidate) runs in
   tests/story_emulator.py on the stock executable; the stock routines themselves change the records; the mask is
   the one VvfpMaskOf answers (the render getter VV3_GetMaskForRecord) -- it stays, the file names the new
   fingerprint, and a reload finds it.  Never a guess: a newborn in the record, a twin with the new likes, or a
   change not seen happening (a look long after, a load) carries nothing.
2. A CHANGE OF THE IDENTITY THE MASKS ARE KEPT BY.  The Lost Children's, The Tree of Life's and New Believers'
   masks are kept by name, sex and the parents' names.  A Custom Island Event's "Parents", a branching event's new
   name, lost name or mind swap changed them on a villager who stays; the real Origins DLLs (and the Masks Worn
   store of "VVFP Heathens Keep Masks.dll") are told through VvfpVillagerSexChanged with the record before and
   after (story_common.inc story_identity_before / after) and keep each mask on its own villager.  The control:
   not told, the companion's own sync drops it.
3. THE STORY / CHEAT UPGRADES TELL THEM.  The test build of "VVFP Story Upgrades.dll" runs the Custom Island Event's
   Parents and a branching event's change_name, lose_name and body_swap: every mask store loaded is told once per
   changed villager, with the record as it was and as it is, and The Secret City's preferences bracket
   (VV3RunningMaskBoundary) is opened before and closed after.
4. NEW BELIEVERS' "OUTREACH?".  "Offer a tour" (0x416310, choice 0) clears the envoy's orange byte (0x41632F): in the
   stock game the orange mask turned blue.  With Heathens Keep Their Masks When Converted the orange mask is kept in
   the Origins store and drawn (the companion's VvfpHeathensKeepMasksLook), the byte still cleared (a blue Heathen's
   behaviour); joining the tribe through the tour's Faith, the convert keeps it.  Red and blue envoys and puzzle
   Heathens are untouched; the row off is the stock game; other bytes at the site refuse the install; with every
   other New Believers row, in all three modes, it installs.
"""
from __future__ import annotations

import copy
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

ORANGE, RED, BLUE = 2, 3, 1
MASKS = {0: ORANGE, 1: RED, 2: BLUE}

try:
    from test_sex_change_vv3_origins import DISLIKES, HEALTH, LIKES, Vv3Game  # noqa: E402
    from test_sex_change_vv4_origins import FATHER, FEMALE, MALE, Vv4Game, have  # noqa: E402
    from test_sex_change_vv5_origins import Vv5Game  # noqa: E402
    HAVE_ORIGINS = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_ORIGINS = False

    def have(game: int) -> bool:
        return False

try:
    import test_sex_change_vv1_origins as v1  # noqa: E402
    from sex_change_origins_emulation import GAMES as VV12  # noqa: E402
    HAVE_VV2 = v1.hl.HAVE_EMULATOR and v1.hl.stock_path(2).is_file() and VV12[2]["dll"].is_file()
except (ImportError, AttributeError):  # pragma: no cover - environment dependent
    HAVE_VV2 = False

try:
    from test_story_custom_island_event import KEEP, PARENTS, Event, Story, emulated, have_stock  # noqa: E402
    from test_story_cie_graph_runtime_v6 import V6, compiled  # noqa: E402
    HAVE_STORY = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_STORY = False

    def emulated(cls):
        return unittest.skip("the Story / Cheat Upgrades emulation is missing")(cls)

try:
    import test_vv5_heathens_keep_masks as km  # noqa: E402
    from test_companion_installs_all_or_none import render, whole_catalog, with_requirements  # noqa: E402
    import vv_fun_patcher as patcher  # noqa: E402
    HAVE_KEEP = km._skip() is None
except ImportError:  # pragma: no cover - environment dependent
    HAVE_KEEP = False


# ---- 1. The Secret City's own events: a Likes or Dislikes change in place ---------------------------------------
ADD_LIKE, REMOVE_DISLIKE = 0x454890, 0x454780     # the outcomes' own list routines (thiscall on the list, ret 4)
LAUNDRY = 3                                      # 0x415B8D push 3 (likes) / 0x415B9A push 3 (dislikes)
LEARNING = 0x27                                  # 0x415BDB push 0x27
VV3_AGE = 0xDC4


@unittest.skipUnless(HAVE_ORIGINS and have(3), "unicorn/pefile, the stock VV3 or the DLL is missing")
class SecretCityEventsKeepTheMask(unittest.TestCase):
    def masked(self, extra=()) -> "Vv3Game":
        g = Vv3Game().village(names=("Kai", "Lani", "Moku", "Nalu") + tuple(n for n, _ in extra),
                              sexes=(MALE, FEMALE, MALE, FEMALE) + tuple(s for _, s in extra))
        g.p.put32(g.record(1) + DISLIKES, LAUNDRY)    # Lani dislikes laundry: the event removes it
        for i, m in MASKS.items():
            self.assertEqual(g.put_mask(i, m), 1)
        for i, m in MASKS.items():
            self.assertEqual(g.mask(i), m, "the first look sees every villager")
        return g

    def outcome(self, g: "Vv3Game", i: int, like: int = LAUNDRY) -> None:
        """What the outcome at 0x415B8A does to its villager's lists: likes.add(like), dislikes.remove(like)."""
        r = g.record(i)
        g.p.call(ADD_LIKE, [like], ecx=r + LIKES)
        g.p.call(REMOVE_DISLIKE, [like], ecx=r + DISLIKES)

    def test_every_mask_stays_through_the_events_own_likes_change(self):
        g = self.masked()
        before = {i: g.identity(i) for i in MASKS}
        for i in MASKS:
            self.outcome(g, i)
            self.assertNotEqual(g.identity(i), before[i], "the event changed the fingerprint")
        for i, m in MASKS.items():
            self.assertEqual(g.mask(i), m, f"villager {i} still wears mask {m}")
        self.assertEqual(g.mask(3), 0, "the unmasked villager is still unmasked")
        ids = g.file_ids(g.masks_file())
        for i in MASKS:
            self.assertIn(g.identity(i), ids, "the file names the new fingerprint")
            self.assertNotIn(before[i], ids)
        # A reload with the likes the save now holds finds every mask.
        later = Vv3Game(disk_from=g).village()
        later.p.put32(later.record(1) + DISLIKES, LAUNDRY)
        for i in MASKS:
            self.outcome(later, i)
        for i, m in MASKS.items():
            self.assertEqual(later.mask(i), m)

    def test_a_second_event_later_keeps_it_too(self):
        g = self.masked()
        for like in (LAUNDRY, LEARNING):
            for i in MASKS:
                self.outcome(g, i, like)
            for i, m in MASKS.items():
                self.assertEqual(g.mask(i), m, f"after the likes change to {like:#x}")

    def test_a_change_not_seen_happening_is_not_guessed(self):
        """The stock loss, where the follow cannot know it is the same villager: the likes changed and the next
        look is long after (a load, the menus) -- nothing is carried."""
        g = self.masked()
        for i in MASKS:
            self.outcome(g, i)
        g.p.tick += 10_000
        for i in MASKS:
            self.assertEqual(g.mask(i), 0)

    def test_a_newborn_in_the_record_never_inherits_it(self):
        g = self.masked()
        r = g.record(1)
        g.p.put32(r + HEALTH, 0)                       # Lani dies ...
        self.assertEqual(g.mask(1), 0)
        g.villager(1, "Lani", FEMALE)                   # ... and a newborn of her name and sex takes the record
        g.p.put32(r + VV3_AGE, 0)
        g.p.call(ADD_LIKE, [LEARNING], ecx=r + LIKES)
        self.assertEqual(g.mask(1), 0, "a new villager is not the one who wore the mask")
        self.assertEqual(g.mask(0), ORANGE)

    def test_a_twin_with_the_new_likes_is_never_given_it(self):
        """Another living Lani, female, who already likes laundry: after the event Lani's new fingerprint is hers too,
        so the mask is never moved to it (it would be drawn on both)."""
        g = self.masked(extra=(("Lani", FEMALE),))
        g.p.call(ADD_LIKE, [LAUNDRY], ecx=g.record(4) + LIKES)
        self.assertEqual(g.mask(4), 0)
        self.outcome(g, 1)
        self.assertEqual(g.mask(4), 0, "the twin never gets it")
        self.assertEqual(g.mask(0), ORANGE)
        self.assertEqual(g.mask(2), BLUE)


# ---- 2. A change of the identity the masks are kept by ----------------------------------------------------------
def _copy(p, record: int, stride: int) -> int:
    before = p.alloc(stride)
    p.write(before, p.read(record, stride))
    return before


@unittest.skipUnless(HAVE_ORIGINS and have(4), "unicorn/pefile, the stock VV4 or the DLL is missing")
class TreeOfLifeMasksFollowTheVillager(unittest.TestCase):
    def masked(self) -> "Vv4Game":
        g = Vv4Game().village()
        g.write_masks(dict(MASKS))
        g.settle()
        for i, m in MASKS.items():
            self.assertEqual(g.mask(i), m)
        return g

    def parents(self, g, i: int, tell: bool) -> None:
        r = g.record(i)
        before = _copy(g.p, r, g.g["stride"])
        g.p.write(r + FATHER, b"Kalani".ljust(25, b"\0"))
        if tell:
            self.assertEqual(g.p.export("VvfpVillagerSexChanged", 4, 1, r, before), 1)

    def swap(self, g, a: int, b: int, tell: bool) -> None:
        ra, rb = g.record(a), g.record(b)
        ba, bb = _copy(g.p, ra, g.g["stride"]), _copy(g.p, rb, g.g["stride"])
        na, nb = g.p.read(ra + g.g["name"], 25), g.p.read(rb + g.g["name"], 25)
        g.p.write(ra + g.g["name"], nb)
        g.p.write(rb + g.g["name"], na)
        if tell:
            g.p.export("VvfpVillagerSexChanged", 4, 1, ra, ba)
            g.p.export("VvfpVillagerSexChanged", 4, 1, rb, bb)

    def test_a_parents_change_keeps_every_mask(self):
        g = self.masked()
        for i in MASKS:
            self.parents(g, i, tell=True)
        g.settle()
        for i, m in MASKS.items():
            self.assertEqual(g.mask(i), m)
        later = Vv4Game(disk_from=g).village()
        for i in MASKS:
            later.p.write(later.record(i) + FATHER, b"Kalani".ljust(25, b"\0"))
        later.settle()
        for i, m in MASKS.items():
            self.assertEqual(later.mask(i), m, "the file names the identity the save now holds")

    def test_without_the_word_the_sync_drops_it(self):
        g = self.masked()
        self.parents(g, 1, tell=False)
        g.settle()
        self.assertEqual(g.mask(1), 0, "the control: the stock-patcher loss this release fixes")

    def test_a_mind_swap_keeps_each_mask_on_its_own_head(self):
        g = self.masked()
        self.swap(g, 0, 1, tell=True)
        g.settle()
        self.assertEqual((g.mask(0), g.mask(1), g.mask(2)), (ORANGE, RED, BLUE))
        h = self.masked()
        self.swap(h, 0, 1, tell=False)
        h.settle()
        self.assertEqual((h.mask(0), h.mask(1)), (0, 0), "the control: two renames at once were never told apart")


@unittest.skipUnless(HAVE_ORIGINS and have(5), "unicorn/pefile, the stock VV5 or the DLL is missing")
class NewBelieversMasksFollowTheVillager(unittest.TestCase):
    def masked(self) -> "Vv5Game":
        g = Vv5Game().village()
        g.settle()
        for i, m in MASKS.items():
            g.put_mask(i, m)
        for i, m in MASKS.items():
            self.assertEqual(g.mask(i), m)
        return g

    def test_a_parents_change_keeps_every_mask(self):
        g = self.masked()
        for i in MASKS:
            r = g.record(i)
            before = _copy(g.p, r, g.g["stride"])
            g.p.write(r + FATHER, b"Kalani".ljust(25, b"\0"))
            self.assertEqual(g.p.export("VvfpVillagerSexChanged", 5, 1, r, before), 1)
        g.settle()
        for i, m in MASKS.items():
            self.assertEqual(g.mask(i), m)

    def test_without_the_word_the_sync_drops_it(self):
        g = self.masked()
        g.p.write(g.record(1) + FATHER, b"Kalani".ljust(25, b"\0"))
        g.settle()
        self.assertEqual(g.mask(1), 0)


@unittest.skipUnless(HAVE_VV2, "unicorn/pefile, the stock The Lost Children or its DLL is missing")
class LostChildrenMasksFollowTheVillager(unittest.TestCase):
    def village(self):
        v = v1.Village(2, v1.hl.stock_exe(2))
        for i, (name, sex) in enumerate(zip(("Kai", "Lani", "Moku", "Nalu"), (1, 2, 1, 2))):
            v.villager(i, name, sex, parents=(f"Pa{i}", f"Ma{i}"))
        v.load()
        for i, m in MASKS.items():
            v.put_mask(i, m)
        v.frame()
        for i, m in MASKS.items():
            self.assertEqual(v.mask(i), m)
        return v

    def test_a_parents_change_keeps_every_mask(self):
        v = self.village()
        for i in MASKS:
            r = v.record(i)
            before = _copy(v.p, r, v.g["stride"])
            v.p.write(r + v.g["father"], b"Kalani\0")
            self.assertEqual(v.p.export("VvfpVillagerSexChanged", 2, 1, r, before), 1)
        v.frame()
        for i, m in MASKS.items():
            self.assertEqual(v.mask(i), m)

    def test_without_the_word_the_sync_drops_it(self):
        v = self.village()
        v.p.write(v.record(1) + v.g["father"], b"Kalani\0")
        v.frame()
        self.assertEqual(v.mask(1), 0)


# ---- 3. The Story / Cheat Upgrades tell the mask stores -------------------------------------------------------
OWNERS = ("VVFP Origins Icons.dll", "VVFP VV1 Origins Icons.dll", "VVFP VV2 Origins Icons.dll",
          "VVFP VV4 Origins Icons.dll", "VVFP Heathens Keep Masks.dll", "VVFP Original Look.dll")
OWNER_BASE = 0x71000000


class Told:
    """Every mask store answered by GetModuleHandleA, its VvfpVillagerSexChanged recording what it is told."""

    def __init__(self, p, stride: int, fields: dict[str, tuple[int, int]], *, hooked: bool = False):
        self.p = p
        self.calls: list[tuple[str, int, int, int, dict, dict]] = []
        export = p.alloc(0x10 * len(OWNERS))

        def module(q):
            name = q.cstring(q.arg(0))
            return (OWNER_BASE + 0x10000 * OWNERS.index(name) if name in OWNERS else 0), 4

        def proc(q):
            base = q.arg(0)
            if OWNER_BASE <= base < OWNER_BASE + 0x10000 * len(OWNERS):
                k = (base - OWNER_BASE) // 0x10000
                return (export + 0x10 * k if q.cstring(q.arg(1)) == "VvfpVillagerSexChanged" else 0), 8
            return 0, 8                                 # no other companion is loaded here

        def told(k):
            def fn(q):
                record, before = q.arg(2), q.arg(3)
                self.calls.append((OWNERS[k], q.arg(0), q.arg(1), record,
                                   {n: q.read(before + o, s) for n, (o, s) in fields.items()},
                                   {n: q.read(record + o, s) for n, (o, s) in fields.items()}))
                return 1, 16
            return fn
        for k in range(len(OWNERS)):
            p.stub(export + 0x10 * k, told(k))
            if hooked:
                # A run (tests/test_story_cie_graph_runtime.py Run) hooks only the stubs it knew of.
                from unicorn import UC_HOOK_CODE
                p.mu.hook_add(UC_HOOK_CODE, p._on_code, begin=export + 0x10 * k, end=export + 0x10 * k)
        p.api_handlers["GetModuleHandleA"] = module
        p.api_handlers["GetProcAddress"] = proc

    def records(self) -> list[int]:
        return [c[3] for c in self.calls]


def _text(raw: bytes) -> bytes:
    return raw.split(b"\0", 1)[0]


@emulated
class StoryTellsTheMaskStores(unittest.TestCase):
    def test_a_parents_change_tells_every_store_once(self):
        for game in ("vv2", "vv3", "vv4", "vv5"):
            if not have_stock(game):
                continue
            story = Story(game)
            v, p = story.village, story.proc
            fname, mname = PARENTS[game][0], PARENTS[game][1]
            r = v.put(2, sex="f", years=30, name="Lani")
            told = Told(p, 0, {"father": (fname, 8), "mother": (mname, 8)})
            ok, res, _ = story.apply(Event(changes=[story.change(2, parents_set=1, father_name="Kalani",
                                                                 mother_name="Moana")]))
            with self.subTest(game=game):
                self.assertEqual(res["refused"], 0)
                self.assertEqual(sorted(c[0] for c in told.calls), sorted(OWNERS), "each store once")
                for name, g, slot, record, was, now in told.calls:
                    self.assertEqual((g, slot, record), (story.n, 1, r))
                    self.assertEqual(_text(was["father"]), b"", "told the record as it was")
                    self.assertEqual(_text(now["father"]), b"Kalani", "and as it is")
                if game == "vv3":
                    self.assertEqual(story.host.brackets[-2:], [0, 1], "The Secret City's bracket around it")
            told.calls.clear()
            story.apply(Event(changes=[story.change(2, skills=(40,) + (KEEP,) * 5)]))
            with self.subTest(game=game, case="no identity change"):
                self.assertEqual(told.calls, [], "a change no mask is kept by tells nobody")

    GRAPH = {"format": "vvfp-cie-graph", "version": 6, "title": "The Masks Stay", "games": [1, 2, 3, 4, 5],
             "roles": {"subject": {"kind": "villager", "min_age": 14},
                       "other": {"kind": "villager", "min_age": 14}},
             "start": "p", "nodes": {"p": {"text": "(Name) wakes up changed.", "effects": []}}}

    def run_effect(self, game: str, effect: dict):
        graph = copy.deepcopy(self.GRAPH)
        graph["nodes"]["p"]["effects"] = [effect]
        r = V6(game, [(0, "m", 30, "Kai", 0, False), (1, "f", 31, "Lani", 0, False)])
        told = Told(r.p, r.v.L["stride"], {"name": (r.v.L["name"], 12)}, hooked=True)
        names = {i: _text(r.p.read(r.v.record(i) + r.v.L["name"], 12)) for i in (0, 1)}
        r.rolls([1] * 40)
        self.assertIsNone(r.queue6(compiled(graph), strict=True, origin=2))
        brackets = len(r.story.host.brackets) if game == "vv3" else 0
        r.walk_through()
        return r, told, names, brackets

    def test_a_new_name_a_lost_name_and_a_mind_swap_tell_every_store(self):
        cases = (("change_name", {"do": "change_name", "role": "subject", "name": "Kona"}, 1),
                 ("lose_name", {"do": "lose_name", "role": "subject"}, 1),
                 ("body_swap", {"do": "body_swap", "role": "subject", "with": "other"}, 2))
        for game in ("vv1", "vv2", "vv3", "vv4", "vv5"):
            if not have_stock(game):
                continue
            for what, effect, villagers in cases:
                with self.subTest(game=game, effect=what):
                    r, told, names, brackets = self.run_effect(game, effect)
                    self.assertEqual(len(told.calls), villagers * len(OWNERS),
                                     "every store told once for each villager changed")
                    changed = {c[3] for c in told.calls}
                    self.assertEqual(len(changed), villagers)
                    for _name, g, slot, record, was, now in told.calls:
                        self.assertEqual((g, slot), (int(game[2]), 1))
                        self.assertNotEqual(was["name"], now["name"], "the name as it was and as it is")
                        index = (record - r.v.record(0)) // r.v.L["stride"]
                        self.assertEqual(_text(was["name"]), names[index])
                    if game == "vv3":
                        self.assertEqual(r.story.host.brackets[brackets:brackets + 2], [0, 1],
                                         "The Secret City's bracket opened before and closed after")


# ---- 4. New Believers' Outreach? ------------------------------------------------------------------------------
OUTREACH, OUTREACH_SITE = 0x416310, 0x41632F
FAITH = 0x1CF0


@unittest.skipUnless(HAVE_KEEP, "unicorn/pefile, the stock VV5 or the Keep Masks DLL is missing")
class OutreachKeepsTheOrangeMask(unittest.TestCase):
    def village(self, mode="collection_progression", *, start=True, exe: bytes | None = None, ids=None):
        v = km.Village(exe or render(5, ids or with_requirements(5, [km.ROW]), mode))
        if start:
            v.export("VvfpStartup", 5, 0)
        world = v.alloc(0x18000)
        v.write(world + 0x17E39, b"\x01")               # SetFaith 0x467F90 converts only while this is set
        v.stub(0x425950, lambda p: (world, 0))          # the game object SetFaith asks for
        for va, pop in ((0x470920, 4), (0x473440, 0), (0x4662C0, 4), (0x4662D0, 4), (0x475730, 8),
                        (0x41EB40, 4), (0x4237B0, 4)):
            v.stub(va, lambda p, pop=pop: (0, pop))     # the walk, the activity, Devotion, food and tech
        v.stub(0x403660, lambda p: (0, 0))              # rand (cdecl)
        return v

    def tour(self, v, envoy: int, guide: int) -> None:
        event = v.alloc(0x20)
        v.put32(event + 4, envoy)
        v.put32(event + 12, guide)
        v.call(OUTREACH, [0], ecx=event)               # "Offer a tour"

    def envoy(self, v, role=0, orange=1, red=0, faith=-60):
        record = v.heathen(7, role, orange, red)
        v.put32(record + FAITH, faith)
        guide = v.record(3)
        v.write(guide + km.ACTIVE, b"\x01")
        return record, guide

    def test_the_orange_mask_stays_and_the_envoy_is_calmed_in_every_mode(self):
        for mode in km.MODES:
            with self.subTest(mode=mode):
                v = self.village(mode)
                self.assertEqual(v.export("VvfpHeathensKeepMasksInstalled"), 1)
                record, guide = self.envoy(v)
                self.tour(v, record, guide)
                self.assertEqual(v.read(record + km.ORANGE, 1), b"\0", "the byte cleared: a blue Heathen's behaviour")
                self.assertEqual(v.read(record + km.FACTION, 1), b"\1", "still a Heathen (Faith 0 or below)")
                self.assertEqual(v.keeps, [(record, ORANGE)], "the orange mask kept in the Origins store")
                self.assertEqual(v.export("VvfpHeathensKeepMasksLook", record), 1, "drawn in the orange mask")

    def test_joining_through_the_tour_keeps_the_orange_mask(self):
        v = self.village()
        record, guide = self.envoy(v, faith=-10)
        self.tour(v, record, guide)
        self.assertEqual(v.read(record + km.FACTION, 1), b"\0", "the tour's Faith +20 converted them")
        self.assertEqual(v.mask_get(record), ORANGE, "the convert keeps the orange mask")

    def test_red_and_blue_envoys_and_puzzle_heathens_are_untouched(self):
        for name, (role, orange, red) in {"red": (0, 0, 1), "blue": (0, 0, 0), "purple Master": (14, 1, 0)}.items():
            with self.subTest(envoy=name):
                v = self.village()
                record, guide = self.envoy(v, role=role, orange=orange, red=red)
                self.tour(v, record, guide)
                self.assertEqual(v.keeps, [], "nothing put in the store")
                self.assertEqual(v.read(record + km.RED, 1), bytes([red]), "a red envoy stays red")
                self.assertEqual(v.u32(record + km.ROLE), role)

    def test_the_row_off_is_the_stock_game(self):
        v = self.village(start=False)
        record, guide = self.envoy(v)
        self.tour(v, record, guide)
        self.assertEqual(v.read(record + km.ORANGE, 1), b"\0")
        self.assertEqual(v.keeps, [], "the stock game: the orange mask turns blue")
        self.assertEqual(v.read(OUTREACH_SITE, 7), bytes.fromhex("C681ED1C000000"))

    def test_other_bytes_at_the_site_refuse_the_whole_install(self):
        exe = bytearray(render(5, with_requirements(5, [km.ROW]), "collection_progression"))
        exe[OUTREACH_SITE - 0x400000 + 6] = 0x01        # mov byte [ecx+0x1CED], 1
        v = self.village(exe=bytes(exe))
        self.assertEqual(v.export("VvfpHeathensKeepMasksInstalled"), 0)
        self.assertEqual(v.read(0x466966, 7), bytes.fromhex("83BEFC1C00000D"), "no site is written")

    def test_with_every_other_row_in_every_mode_it_installs(self):
        by_id = {p.id: p for p in patcher.load_public_fun_patches()}
        conflicts = set(patcher.conflict_ids(by_id[km.ROW]))
        ids = tuple(patcher.resolve_fun_patch_ids(
            list(dict.fromkeys([i for i in whole_catalog(5) if i not in conflicts] + [km.ROW])), game_id="vv5"))
        for mode in km.MODES:
            with self.subTest(mode=mode):
                exe = render(5, ids, mode)
                self.assertEqual(exe[OUTREACH_SITE - 0x400000:OUTREACH_SITE - 0x400000 + 7],
                                 bytes.fromhex("C681ED1C000000"), "no other row writes the site")
                v = self.village(exe=exe)
                self.assertEqual(v.export("VvfpHeathensKeepMasksInstalled"), 1)
                record, guide = self.envoy(v)
                self.tour(v, record, guide)
                self.assertEqual(v.keeps, [(record, ORANGE)])


if __name__ == "__main__":
    unittest.main()
