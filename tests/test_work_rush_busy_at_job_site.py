"""The work rush's busy villagers go to the rushed job's own site (the owner, 2026-11-18; cie-v6-binary.md 42).

A villager who is not the rushed skill's worker (another job ticked, or none ticked and another skill the highest;
children never take part) goes where the job's workers go and does the busy state THERE, with no skill and no
produce: Sitting (A New Home, The Lost Children), "Working 'til he/she drops!" (The Secret City), "Needs to sit
down" (The Tree of Life, New Believers).  The site is the job's own first walk step, picked by the job's own starter
for that villager (the adapters' behave_at, story_custom.inc ce_site_pick); a spot within CE_SITE_ROOM (20) pixels
of one already taken (the workers' first, then each busy villager's) is crowded, and the busy villager is given the
nearest free spot among the job's own further picks (the first one when every pick is crowded).

Two halves:

* the companion (the test build of "VVFP Story Upgrades.dll" beside each rendered executable): the busy villagers'
  queues are the job's walk followed by the busy steps without their own walks; A New Home and The Lost Children
  with their real starters, the later games with recorded do-actions that give known steps;
* the stock executables (tests/farmers_emulation_vvN.py: the real map, frame by frame): that queue, made from each
  rushable job's real starter and the real busy action, walks the villager to the job's site and does the busy steps
  there with not one skill changed -- where the plain busy state (the control) does them somewhere else.
"""
from __future__ import annotations

import importlib
import math
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from test_story_custom_island_event import HAVE_EMULATOR, emulated, have_stock  # noqa: E402

if HAVE_EMULATOR:
    from test_traders_and_village_effects import DO_ACTION, JOB_TICKED, GameSide, pages  # noqa: E402
    from unicorn import UC_HOOK_CODE

# (queue offset, step size, steps, walk type, x offset, y offset): story_custom.inc CE_QUEUE
SHAPE = {1: (0x44, 0x18, 29, 3, 4, 8), 2: (0x4C, 0x18, 49, 3, 4, 8), 3: (0, 0x2C, 80, 3, 8, 0xC),
         4: (0, 0x58, 80, 3, 8, 0xC), 5: (0, 0x58, 80, 4, 8, 0xC)}
ROOM = 20
PEOPLE = [(0, "m", 30, "Adam", 10, False), (1, "f", 31, "Bea", 90, False), (2, "m", 40, "Cal", 50, False),
          (3, "f", 35, "Dan", 0, False), (4, "m", 8, "Kai", 0, False)]
PICKS = [(500, 500), (600, 600), (500, 505), (560, 500), (530, 505)] + [(500, 500)] * 5 + [(900, 900)]
SIT = (2, 0, 0, 15, 0, 2)                  # A New Home's / The Lost Children's Sitting step (0x439D80 / 0x44A1E0)


def queue(read, record: int, game: int) -> list[tuple]:
    off, size, cap, *_ = SHAPE[game]
    out = []
    for k in range(cap):
        step = struct.unpack(f"<{size // 4}i", read(record + off + size * k, size))
        if step[0] == 0:
            break
        out.append(step)
    return out


# -- the companion ---------------------------------------------------------------------------------------------------

@emulated
class CompanionQueues(unittest.TestCase):
    side = None

    def setUp(self):
        self.side = GameSide()

    def rush(self, game: str, setup):
        g = pages([[{"do": "group", "kind": "work", "skill": "Farming"}]], [int(game[2])])
        off, ticked = JOB_TICKED[game]

        def both(r):
            for i, value in enumerate(ticked):              # Adam Farming, Bea none, Cal Research, Dan none
                r.p.put32(r.v.record(i) + off, value & 0xFFFFFFFF)
            setup(r)

        r, _ = self.side.run_graph(game, g, both, people=PEOPLE)
        return r

    def test_old_games_busy_villagers_sit_at_the_berries_and_the_palm(self):
        """A New Home (Foraging 0x441E10: a point of one of its two berry areas) and The Lost Children (Harvesting
        coconuts 0x456F70: the palm's foot), the real starters: Cal and Dan walk there, then sit -- and in A New
        Home each takes a spot no one else has (within 20 pixels); the palm has one foot, so they share it."""
        for game in ("vv1", "vv2"):
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                r = self.rush(game, lambda r: None)
                g = int(game[2])
                qs = [queue(r.p.read, r.v.record(i), g) for i in range(4)]
                spots = [q[0][1:3] for q in qs]
                for i in (2, 3):
                    self.assertEqual(len(qs[i]), 2, "the job's walk, then the busy state")
                    self.assertEqual(qs[i][0][0], 3)
                    self.assertEqual(qs[i][1], SIT, "Sitting, nothing of the job")
                for i in (0, 1):
                    self.assertGreater(len(qs[i]), 2, "the workers keep the job")
                self.assertEqual(queue(r.p.read, r.v.record(4), g), [], "Kai (8) neither works nor sits")
                if g == 1:
                    for i in (2, 3):
                        x, y = spots[i]
                        self.assertTrue((633 <= x <= 795 and 459 <= y <= 465) or (819 <= x <= 843 and 429 <= y <= 435),
                                        f"a point of Foraging's berry areas: {spots[i]}")
                        for j in range(i):
                            self.assertGreaterEqual(math.dist(spots[i], spots[j]), ROOM, "a free spot")
                else:
                    self.assertEqual([spots[i] for i in (2, 3)], [(407, 356), (407, 356)], "the palm's one foot")

    def later(self, game: str, busy: list, stale: tuple | None = None, extra=None):
        """The rush with recorded do-actions: the job gives one walk per call (PICKS in turn), the busy action
        `busy` (and, when `stale` is given, an old step left after its end marker, as a real queue may hold)."""
        g = int(game[2])
        off, size, cap, walk, x_at, y_at = SHAPE[g]
        work, rest = {3: (0xB, 0x3A), 4: (0x63, 0x4F), 5: (0x6C, 0x55)}[g]
        calls = []

        def setup(r):
            left = list(PICKS)

            def do_action(p):
                record, action = p.reg("ecx"), p.arg(0)
                calls.append((record, action))
                steps = [(walk, 100) + left.pop(0), (7, 5)] if action == work else busy
                p.write(record, bytes(size * (len(steps) + 2)))
                for k, step in enumerate(steps):
                    p.write(record + size * k, struct.pack(f"<{len(step)}i", *step))
                if stale is not None and action != work:
                    p.write(record + size * (len(steps) + 1), struct.pack(f"<{len(stale)}i", *stale))
                return 0, 8

            r.p.stub(DO_ACTION[game], do_action)
            r.p.mu.hook_add(UC_HOOK_CODE, r.p._on_code, begin=DO_ACTION[game], end=DO_ACTION[game])
            if extra is not None:
                extra(r)

        return self.rush(game, setup), calls, work, rest

    def test_a_busy_action_with_no_walk_still_ends_its_queue(self):
        """A busy action that queued no walk of its own: the job's walk goes first and the queue still ends right
        after the busy steps (an old step left past the busy action's end marker never comes back to life)."""
        busy = {3: [(0x1F,), (2,)], 4: [(2, 2), (0x17, 2)], 5: [(3, 2), (0x18, 2)]}
        for game in ("vv3", "vv4", "vv5"):
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                g = int(game[2])
                walk = SHAPE[g][3]
                r, _calls, _work, _rest = self.later(game, busy[g], stale=(8, 77))
                q = queue(r.p.read, r.v.record(3), g)
                self.assertEqual([s[0] for s in q], [walk] + [s[0] for s in busy[g]], "walk, busy steps, the end")

    def test_carrying_and_sick_villagers_are_left_as_they_are(self):
        """The stock games never send a carrying mother (or father) or a sick villager to work: in a rush Adam
        (carrying, Farming ticked) and Cal (sick, Research ticked) neither work nor take the busy state; Bea works and
        Dan takes the busy state."""
        carrying = {"vv1": (0x358, 4), "vv2": (0x540, 4), "vv3": (0xE8C, 4), "vv4": (0x1C4C, 4), "vv5": (0x1C4C, 4)}
        sick = {"vv1": (0x354, 4), "vv2": (0x53C, 4), "vv3": (0xE89, 1), "vv4": (0x1C48, 1), "vv5": (0x1C48, 1)}

        def mark(r, game):
            for (at, n), i in ((carrying[game], 0), (sick[game], 2)):
                r.p.write(r.v.record(i) + at, (1).to_bytes(n, "little"))

        for game in ("vv1", "vv2", "vv3", "vv4", "vv5"):
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                if game in ("vv1", "vv2"):
                    starters = {"vv1": (0x441E10, 0x439D80), "vv2": (0x456F70, 0x44A1E0)}[game]

                    def setup(r, game=game, starters=starters):
                        mark(r, game)
                        r.record(starters[0], 4)
                        r.record(starters[1], 8)

                    r = self.rush(game, setup)
                    self.assertEqual([c[1] for c in r.recorded.get(starters[0], [])], [1, 3], "Bea works; Dan's site")
                    self.assertEqual([c[1] for c in r.recorded.get(starters[1], [])], [3], "Dan alone is busy")
                else:
                    r, calls, work, rest = self.later(game, [(2, 2)], extra=lambda r, game=game: mark(r, game))
                    who = [r.v.record(i) for i in range(5)]
                    self.assertEqual(sorted({c[0] for c in calls}), sorted({who[1], who[3]}), "only Bea and Dan")
                    self.assertEqual([c[1] for c in calls if c[0] == who[3]][-1], rest)

    def test_later_games_busy_steps_follow_the_jobs_walk_and_the_nearest_free_spot(self):
        """The Secret City, The Tree of Life, New Believers: the job's do-action (recorded) gives one walk per call;
        the busy action gives its own walks around its steps.  Cal's first pick is crowded (5 pixels from Adam's):
        of the job's next picks (60, 30 pixels away, then Adam's own spot again) he takes the nearest free one; Dan's
        first pick is free and is the only one asked for.  The busy steps keep their order, their walks are gone."""
        busy_steps = {3: [(3, 300, 1, 2), (0x1F,), (3, 300, 3, 4), (2,)], 4: [(3, 300, 1, 2), (2, 2), (0x17, 2)],
                      5: [(4, 300, 1, 2), (3, 2), (0x18, 2)]}
        for game in ("vv3", "vv4", "vv5"):
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                g = int(game[2])
                off, size, cap, walk, x_at, y_at = SHAPE[g]
                r, calls, work, rest = self.later(game, busy_steps[g])
                who = [r.v.record(i) for i in range(4)]
                self.assertEqual([c for c in calls if c[0] == who[2]], [(who[2], work)] * 8 + [(who[2], rest)])
                self.assertEqual([c for c in calls if c[0] == who[3]], [(who[3], work), (who[3], rest)])
                self.assertEqual([c for c in calls if c[0] == r.v.record(4)], [], "Kai (8): no job, no busy state")
                self.assertEqual(queue(r.p.read, r.v.record(4), g), [], "Kai's queue is untouched")
                keep = [s for s in busy_steps[g] if s[0] != walk]
                for i, spot in ((2, (530, 505)), (3, (900, 900))):
                    q = queue(r.p.read, who[i], g)
                    self.assertEqual(q[0][:4], (walk, 100) + spot, "the job's own walk, to the nearest free pick")
                    self.assertEqual([s[:len(k)] for s, k in zip(q[1:], keep)], keep)
                    self.assertEqual(len(q), 1 + len(keep), "the busy steps, without their walks")
                for i, spot in ((0, (500, 500)), (1, (600, 600))):
                    q = queue(r.p.read, who[i], g)
                    self.assertEqual([s[0] for s in q], [walk, 7], "the workers keep the job")
                    self.assertEqual(q[0][2:4], spot)


# -- the highest skill: the Action bar's own pick --------------------------------------------------------------------

# Each game's skill fields in the record's order and the Action bar's routine (story_graph_village.inc
# cg_highest_skill): VV1 0x43B520, VV2 0x44B4D0 (thiscall on the villager array: index, &value), VV3 0x462460,
# VV4 0x46AC20, VV5 0x4755C0 (thiscall on the skills at +0xEAC / +0x1C5C: &value).
SKILLS = {"vv1": {"parenting": 0x3BC, "building": 0x3C0, "farming": 0x3C4, "healing": 0x3C8, "research": 0x3CC},
          "vv2": {"parenting": 0x7E4, "building": 0x7E8, "farming": 0x7EC, "healing": 0x7F0, "research": 0x7F4},
          "vv3": {"farming": 0xEAC, "parenting": 0xEB0, "healing": 0xEB4, "research": 0xEB8, "building": 0xEBC},
          "vv4": {"farming": 0x1C5C, "parenting": 0x1C60, "healing": 0x1C64, "research": 0x1C68, "building": 0x1C6C},
          "vv5": {"farming": 0x1C5C, "parenting": 0x1C60, "healing": 0x1C64, "research": 0x1C68, "building": 0x1C6C,
                  "devotion": 0x1C70}}
# Bea (no job ticked) and Dan (no job ticked): their skills; whether each is Farming's worker (the Action bar's pick)
TIES = {"vv1": ({"farming": 60, "research": 60}, True, {"farming": 60, "healing": 60}, False),
        "vv2": ({"farming": 60, "research": 60}, True, {"farming": 60, "healing": 60}, False),
        "vv3": ({"farming": 60, "building": 60}, True, {"farming": 59, "parenting": 60}, False),
        "vv4": ({"farming": 40.7, "parenting": 40.0}, True, {"farming": 40.7, "parenting": 40.2}, False),
        "vv5": ({"farming": 40.7, "devotion": 40.0}, True, {"farming": 40.7, "devotion": 40.2}, False)}
ACTION_BAR = {"vv1": 0x43B520, "vv2": 0x44B4D0, "vv3": 0x462460, "vv4": 0x46AC20, "vv5": 0x4755C0}
FARMING_PICK = {"vv1": 1, "vv2": 1, "vv3": 0, "vv4": 0, "vv5": 0}     # the routine's answer for Farming


def harness(game: int):
    try:
        fe = importlib.import_module(f"farmers_emulation_vv{game}")
    except Exception as e:                 # pragma: no cover
        raise unittest.SkipTest(f"no emulator: {e}")
    data = getattr(fe, "CMAP", None) or getattr(fe, "DATA", None)
    if not fe.STOCK.is_file() or (data is not None and not Path(data).exists()):
        raise unittest.SkipTest("needs the stock executable and research/game-data")
    return fe


def action_bar_pick(game: str, skills: dict) -> int:
    """The stock Action bar routine's own answer for `skills` (the skill id it returns, its own numbering)."""
    g = int(game[2])
    fe = harness(g)
    v = fe.Village(seed=1)
    if g in (1, 2):
        v.villager(skills={k: 0 for k in SKILLS[game]})
        rec = v.rec(0)
        for name, at in SKILLS[game].items():
            v.w32(rec + at, int(skills.get(name, 0)))
        out = fe.BUF
        v.w32(out, -7)
        v.call(ACTION_BAR[game], fe.MGR, 0, out)
        return v.r32(out)
    rec = v.rec(0) if g != 5 else fe.V0
    for name, at in SKILLS[game].items():
        value = skills.get(name, 0)
        v.uc.mem_write(rec + at, struct.pack("<f", float(value)) if g >= 4 else struct.pack("<i", int(value)))
    first = SKILLS[game]["farming"]
    return v.call(ACTION_BAR[game], rec + first, 0)


@emulated
class HighestSkillIsTheActionBarsPick(unittest.TestCase):
    def test_a_clear_highest_and_a_tie(self):
        """Bea and Dan have no job ticked.  A clear highest (Farming 90 against 10s) makes Bea Farming's worker in
        every game; a tie goes the Action bar's way: the old games read Parenting, Building, Healing, Farming,
        Research (Healing beats a tied Farming, Farming beats a tied Research), The Secret City reads Farming first,
        The Tree of Life and New Believers compare each float skill to the best so far cut to a whole number (40.2
        after 40.7 wins, 40.0 does not).  Each tie is checked against the stock routine itself."""
        side = GameSide()
        for game in ("vv1", "vv2", "vv3", "vv4", "vv5"):
            if not have_stock(game):
                continue
            bea, bea_works, dan, dan_works = TIES[game]
            with self.subTest(game=game, check="the stock routine"):
                try:
                    self.assertEqual(action_bar_pick(game, bea) == FARMING_PICK[game], bea_works)
                    self.assertEqual(action_bar_pick(game, dan) == FARMING_PICK[game], dan_works)
                    self.assertEqual(action_bar_pick(game, {"farming": 90}), FARMING_PICK[game])
                except unittest.SkipTest:
                    pass
            for skills, works in (({"farming": 90}, True), (bea, bea_works), (dan, dan_works)):
                with self.subTest(game=game, skills=skills):
                    g = pages([[{"do": "group", "kind": "work", "skill": "Farming"}]], [int(game[2])])
                    off, ticked = JOB_TICKED[game]
                    seen = {}

                    def setup(r, game=game, off=off, ticked=ticked, skills=skills, seen=seen):
                        for i, value in enumerate(ticked):
                            r.p.put32(r.v.record(i) + off, value & 0xFFFFFFFF)
                        for name, at in SKILLS[game].items():
                            value = skills.get(name, 10)
                            data = (struct.pack("<f", float(value)) if game in ("vv4", "vv5")
                                    else struct.pack("<i", int(value)))
                            r.p.write(r.v.record(1) + at, data)
                        if game in DO_ACTION:
                            r.record(DO_ACTION[game], 8)
                        else:
                            r.record({"vv1": 0x441E10, "vv2": 0x456F70}[game], 4)
                            r.record({"vv1": 0x439D80, "vv2": 0x44A1E0}[game], 8)
                        seen["r"] = r

                    r, _ = side.run_graph(game, g, setup, people=PEOPLE)
                    if game in DO_ACTION:
                        rest = {"vv3": 0x3A, "vv4": 0x4F, "vv5": 0x55}[game]
                        rested = any(c[0] == r.v.record(1) and c[1] == rest for c in r.recorded[DO_ACTION[game]])
                    else:
                        rested = 1 in [c[1] for c in r.recorded.get({"vv1": 0x439D80, "vv2": 0x44A1E0}[game], [])]
                    self.assertEqual(not rested, works, "Bea works exactly when Farming is the Action bar's skill")


# -- the stock executables -------------------------------------------------------------------------------------------

def rebuild(q: bytes, size: int, cap: int, walk: int, w: bytes) -> bytes:
    """story_custom.inc ce_queue_at_site, step for step."""
    steps = [q[k * size:(k + 1) * size] for k in range(cap)]
    used = next((k for k, s in enumerate(steps) if struct.unpack_from("<i", s)[0] == 0), cap)
    kept = [s for s in steps[:used] if struct.unpack_from("<i", s)[0] != walk][:cap - 1]
    out = [w] + kept
    out += [bytes(size)] * (min(cap, max(used, len(out) + 1)) - len(out))   # the end marker, the old steps cleared
    return b"".join(out) + q[len(out) * size:]


# (game, job, its starter's arguments or do-action id); busy: (routine, argument) or action id.  Healing someone
# (A New Home 0x445580, The Lost Children 0x45D580) has no walk: it is done where the healer stands.
JOBS = {1: [("Foraging", 0x441E10, (0,)), ("Fixing hut", 0x440AD0, (0,)), ("Researching", 0x442C10, (0, 0))],
        2: [("Harvesting coconuts", 0x456F70, (0,)), ("Exercising", 0x455330, (0,)),
            ("Researching", 0x457CC0, (0, 0)), ("Telling a story", 0x449F40, (0,))],
        3: [("Fishing", 0xB, None), ("Researching", 3, None), ("Doing exercise", 0x96, None),
            ("Studying medicine", 0xBD, None), ("Telling a story", 0x5F, None)],
        4: [("Harvesting blackberries", 0x63, None), ("Doing exercise", 0x47, None), ("Researching", 2, None)],
        5: [("Harvesting noni", 0x6C, None), ("Researching", 4, None), ("Health chanting", 0x67, None)]}
BUSY = {1: (0x439D80, 15), 2: (0x44A1E0, 15), 3: 0x3A, 4: 0x4F, 5: 0x55}
STOP = {1: 0x439470, 2: 0x4492A0, 3: 0x460F70, 4: 0x468C60, 5: 0x473440}
ADDER = {1: 0x4399F0, 2: 0x449B70}
DETOUR = {1: (), 2: (26,), 3: (4,), 4: (6,), 5: (7,)}    # the walk's own detour steps (inserted while walking)
NEAR = 8                                                # pixels: where the walk stops against its target


class StockVillage:
    def __init__(self, game: int):
        self.g = game
        self.fe = fe = harness(game)
        self.v = fe.Village(seed=7)
        names = fe.SKILLS if game != 5 else fe.SKILL
        self.v.villager(skills={name: 50 for name in names})
        self.rec = self.v.rec(0) if game != 5 else fe.V0

    def read(self, at: int, n: int) -> bytes:
        return bytes(self.v.uc.mem_read(at, n))

    def skills(self) -> list:
        fe, v = self.fe, self.v
        if self.g == 5:
            return [v.rf(fe.V0 + fe.SKILLS + 4 * k) for k in fe.SKILL.values()]
        return [self.read(self.rec + off, 4) for off in fe.SKILLS.values()]

    def feet(self) -> tuple[int, int]:
        if self.g == 5:                     # New Believers' record keeps the sprite's corner: the walk aims it at
            x, y = self.v.feet()            # the target less (20, 55) (each walk above ends there)
            return x + 20, y + 55
        return self.v.pos() if self.g == 4 else self.v.feet()

    def stop(self) -> None:
        if self.g in (1, 2):
            self.v.call(STOP[self.g], self.fe.MGR, 0)
        elif self.g == 3:
            self.v.call(STOP[3], self.rec, self.rec)
        else:
            self.v.call(STOP[self.g], self.rec)

    def start(self, what, args=None) -> None:
        if self.g in (1, 2):
            if self.g == 1:
                self.v.w32(self.rec + 0x40, 0)        # the scheduler's detour count reset (0x44823B)
            self.v.call(what, self.fe.MGR, *args)
        elif self.g == 3:
            self.v.start_job(what)
        else:
            self.v.start(what)

    def trip(self, job, args, at_site: bool):
        """The busy state (at the job's site when `at_site`): (the site, the feet when the busy steps begin, the
        skills before and after)."""
        g = self.g
        off, size, cap, walk, x_at, y_at = SHAPE[g]
        self.stop()
        self.start(job, args)
        q = queue(self.read, self.rec, g)
        w = next(s for s in q if s[0] == walk)
        site = (w[x_at // 4], w[y_at // 4])
        self.stop()
        if g in (1, 2):
            if at_site:
                self.v.call(ADDER[g], self.fe.MGR, 0, w[0], w[1], w[2], w[3], 0, w[5])
            self.v.call(BUSY[g][0], self.fe.MGR, 0, BUSY[g][1])
        else:
            self.start(BUSY[g])
            if at_site:
                raw = self.read(self.rec + off, size * cap)
                self.v.uc.mem_write(self.rec + off, rebuild(raw, size, cap, walk, struct.pack(f"<{size // 4}i", *w)))
        before = self.skills()
        busy_at = None
        for _ in range(40_000):
            head = struct.unpack("<i", self.read(self.rec + off, 4))[0]
            if head == 0:
                break
            if busy_at is None and head != walk and head not in DETOUR[g]:
                busy_at = self.feet()
            self.v.step_frame()
        return site, busy_at, before, self.skills()


@emulated
class StockBusyAtTheSite(unittest.TestCase):
    def test_every_rushable_job(self):
        """Each rushable job's real starter picks the site; the busy villager walks there and does the busy steps
        there, gaining no skill.  The control: the plain busy state is done elsewhere (A New Home and The Lost
        Children: where the villager stands; the later games: the busy action's own places)."""
        for game, jobs in JOBS.items():
            for name, job, args in jobs:
                with self.subTest(game=game, job=name):
                    try:
                        site, busy_at, before, after = StockVillage(game).trip(job, args, at_site=True)
                    except unittest.SkipTest as e:
                        self.skipTest(str(e))
                    self.assertIsNotNone(busy_at, "the busy steps ran")
                    self.assertLessEqual(math.dist(site, busy_at), NEAR, f"busy at the job's site {site}: {busy_at}")
                    self.assertEqual(after, before, "no skill")
            with self.subTest(game=game, control="the plain busy state"):
                name, job, args = jobs[0]
                site, busy_at, _before, _after = StockVillage(game).trip(job, args, at_site=False)
                self.assertGreater(math.dist(site, busy_at), NEAR, "without the change the villager is elsewhere")


@emulated
class SharingASpotIsSafe(unittest.TestCase):
    def test_two_villagers_on_one_spot(self):
        """The owner (2026-11-19): villagers may share a spot when every pick is crowded, if that is safe.  Two
        villagers given the same site (the first rushable job's walk, then the busy steps) both walk there and both
        do the busy steps there: the game's walk and stand code has no lock and no clash for two on one spot (the
        stock games send several workers to one point themselves, e.g. The Lost Children's palm foot)."""
        for game, jobs in JOBS.items():
            with self.subTest(game=game):
                try:
                    s = StockVillage(game)
                except unittest.SkipTest as e:
                    self.skipTest(str(e))
                v, fe = s.v, s.fe
                off, size, cap, walk, x_at, y_at = SHAPE[game]
                _name, job, args = jobs[0]
                s.stop()
                s.start(job, args)
                w = next(x for x in queue(s.read, s.rec, game) if x[0] == walk)
                site = (w[x_at // 4], w[y_at // 4])
                s.stop()
                packed = struct.pack(f"<{size // 4}i", *w)
                if game in (1, 2):
                    v.call(ADDER[game], fe.MGR, 0, *w[:4], 0, w[5])
                    v.call(BUSY[game][0], fe.MGR, 0, BUSY[game][1])
                else:
                    s.start(BUSY[game])
                    v.uc.mem_write(s.rec + off, rebuild(s.read(s.rec + off, size * cap), size, cap, walk, packed))
                stride = 0x2F44 if game == 5 else fe.REC
                r0, r1 = s.rec, s.rec + stride
                if game == 4:                                   # a record of its own (the constructor's), same steps
                    v.villager(index=1, skills={n: 50 for n in fe.SKILLS})
                    v.call(STOP[4], r1)
                    v.start(BUSY[4], index=1)
                    v.uc.mem_write(r1 + off, rebuild(s.read(r1 + off, size * cap), size, cap, walk, packed))
                elif game == 5:                                 # the game's own maker, as for the first believer
                    v.call(fe.MAKE_VILLAGER, fe.VILLAGERS, 1, 0, 5, 0, 600)
                    v.call(STOP[5], r1)
                    v.w8(fe.FLAG, 0)
                    v.call(fe.SET_BEHAVIOUR, r1, BUSY[5], fe.FLAG)
                    v.uc.mem_write(r1 + off, rebuild(s.read(r1 + off, size * cap), size, cap, walk, packed))
                else:
                    v.uc.mem_write(r1, s.read(r0, stride))
                    if game == 1:
                        v.w32(r0 + 2 * stride, 0)               # the end of A New Home's villager list

                def pos(r, game=game, v=v, fe=fe):
                    if game == 4:
                        out = fe.HEAP + 0x1000
                        v.call(fe.POSITION, r, out)
                        return v.r32(out), v.r32(out + 4)
                    if game == 3:
                        return v.feet(r)
                    if game == 5:
                        return v.r32(r + fe.X) + 20, v.r32(r + fe.Y) + 55
                    return v.r32(r + fe.X) + 20, v.r32(r + fe.Y) + 65

                busy = [None, None]
                for _f in range(12_000):
                    heads = [struct.unpack("<i", s.read(r + off, 4))[0] for r in (r0, r1)]
                    for k, (h, r) in enumerate(zip(heads, (r0, r1))):
                        if busy[k] is None and h not in (0, walk) and h not in DETOUR[game]:
                            busy[k] = pos(r)
                    if None not in busy:
                        break
                    if game == 3:
                        v.call(fe.UPDATE, r0)
                        v.call(fe.UPDATE, r1)
                        v.t += fe.FRAME_MS / 1000.0
                    elif game == 4:
                        v.step_frame(0)
                        v.step_frame(1)
                    else:
                        v.step_frame()
                for k in (0, 1):
                    self.assertIsNotNone(busy[k], f"villager {k} reached the busy steps")
                    self.assertLessEqual(math.dist(site, busy[k]), NEAR, f"villager {k} at the shared spot")


class GameMechanicsLines(unittest.TestCase):
    """The Game Mechanics pages' work rush lines (src/vv_game_mechanics_collection.py work_rush_lines), all five games:
    plain words, and each job and busy state the companion's own tables name (story_graph_village.inc CG_WORK,
    CG_WORK_REST)."""

    def native_tables(self):
        import re
        src = (ROOT / "native" / "vvfp_story_upgrades" / "story_graph_village.inc").read_text(encoding="utf-8")
        work = src[src.index("CG_WORK[6][6] = {"):src.index("};", src.index("CG_WORK[6][6] = {"))]
        rows = {}
        for skill in ("Farming", "Building", "Research", "Healing", "Parenting", "Devotion"):
            row = work[work.index(f"/* {skill} */"):]
            row = row[:row.index("}")]
            rows[skill] = re.findall(r'"([^"]*)"', row)
        rest = src[src.index("CG_WORK_REST[6] = {"):]
        rest = re.findall(r'"([^"]*)"', rest[:rest.index("};")])
        return rows, rest

    def test_every_game(self):
        import vv_game_mechanics_collection as gmc
        rows, rest = self.native_tables()
        for game in range(1, 6):
            with self.subTest(game=game):
                text = " ".join(gmc.work_rush_lines(game))
                self.assertNotIn("0x", text, "no addresses")
                self.assertIn("Children never take part: they neither work nor stop what they are doing.", text)
                self.assertIn("Nor does anyone carrying a baby or sick", text)
                self.assertIn("ticked on the Details screen", text)
                self.assertIn("Action bar shows under \"Skill\"", text)
                self.assertIn("within 20 pixels", text)
                self.assertIn("up to 8 of the job's other spots", text)
                self.assertIn("share a spot", text)
                self.assertEqual("Healing someone has no place of its own" in text, game in (1, 2))
                self.assertIn("Birth Control is never bypassed", text)
                self.assertEqual("Parenting rush does nothing" in text, game not in (2, 3))
                for skill, labels in rows.items():
                    job = labels[game].split(" (")[0]
                    if not job:
                        self.assertNotIn(f"{skill}: ", text)
                    else:
                        self.assertIn(f"{skill}: {job}", text)
                for word in rest[game].replace("Working 'til he drops! / Working 'til she drops!",
                                                "Working 'til he drops!").split(" / "):
                    self.assertIn(word, text, "the game's own busy state")


if __name__ == "__main__":
    unittest.main()
