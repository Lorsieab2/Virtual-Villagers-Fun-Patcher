"""Story / Cheat Upgrades: Pick Island Event outcomes, strength, unlocks and the Gong.

The owner: "In general I want all possible outcomes for events that have them
to be possible."  Each offered event's settings (scripts/story_island_outcomes.py,
traced per game in scripts/story_outcomes_vv1..5.py) name the game's own rand
calls that decide them and the value each must return.

Everything here runs the shipped bytes in the emulator (tests/story_emulator.py):
each game's executable as the patcher renders it, with the test build of
"VVFP Story Upgrades.dll" installed beside it.

* The compiled tables are the data, every site and scope call is installed.
* Every setting of every event: the rewritten `call rand` at each of its
  sites returns exactly the chosen value -- in its phase, for its branch,
  inside its scope call, for its baby -- and the game's own rand otherwise
  ("Random" is stock; another event's settings never touch it).
* The armed outcome's life: delivered with the pick, opened by the event's
  own apply (the popup's OK, the resolve call, the island chooser call, the
  Gong's use) and ended when it returns; refused, lapsed and stale picks end
  it; a natural event afterwards is stock.
* The game's own pickers and per-villager loops run for real with a village:
  the chosen villager is the one picked, the chosen villagers are the ones
  hit (The Secret City's tsunami: nobody, everyone, a chosen few).
* Strength (A New Home, The Lost Children), unlocked and developer-dead
  picks, and the three population modes.
"""
from __future__ import annotations

import functools
import os
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402
import story_island_events  # noqa: E402
import story_island_outcomes as outcomes  # noqa: E402

try:
    import pefile  # noqa: F401
    from story_emulator import HEAP, Process
    from story_custom_fixtures import Village

    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")
MODES = ("stock", "collection_progression", "immediate_fixed")
TEST_DLL = Path(os.environ.get(
    "VVFP_STORY_TEST_DLL", ROOT / "tests" / "test_dlls" / "VVFP Story Upgrades.test.dll"))
TEST_BUILD_ABSENT = "test builds are not in the release source archive (tests/test_dlls)"
RAND = {"vv1": 0x402F10, "vv2": 0x4031A0, "vv3": 0x4032D0, "vv4": 0x4036D0, "vv5": 0x403660}
KINDS = {"enum": 1, "amount": 2, "loop": 3, "victim": 4}
PHASES = {"select": 1, "build": 2, "apply": 3}
IDLE, ARMED, DELIVERED = 0, 1, 2
GONG_SLOT = 1000
NOBODY, EVERYONE, CHOOSE = 0, 1, 2
SCRATCH = (HEAP + 0x3E00000) if HAVE_EMULATOR else 0
STACK = (HEAP + 0x3000000) if HAVE_EMULATOR else 0


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


def emulated(cls):
    return unittest.skipUnless(HAVE_EMULATOR, "capstone/unicorn/pefile not installed")(
        unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)(cls))


def stock_value(bound: int) -> int:
    """What the stubbed game rand returns: fixed, so a pass-through is seen."""
    return (bound * 7) // 11 if bound > 1 else 0


def controls_of(game: str, slot: int) -> list[dict]:
    if slot == GONG_SLOT:
        return outcomes.GONG_CONTROLS[game]
    return outcomes.CONTROLS[game].get(slot, [])


def events_of(game: str):
    for slot in outcomes.CONTROLS[game]:
        yield slot
    if game in outcomes.GONG_CONTROLS:
        yield GONG_SLOT


def control_sites(c: dict) -> list[int]:
    if c["kind"] == "enum":
        return sorted({va for o in c["options"] for va, _ in o["force"]})
    return sorted({c["site"], *c.get("sites", [])})


class Game:
    """One game's process: the companion installed, the rand stubbed, a village."""

    def __init__(self, game: str, mode: str = "collection_progression"):
        self.game = game
        self.n = int(game[2:])
        self.proc = Process(render(game, mode), TEST_DLL)
        assert self.proc.export("VvfpStoryInstall", self.n) == 1
        self.rand_calls = []

        def rand(p):
            bound = p.arg(0)
            self.rand_calls.append(bound)
            return stock_value(bound), 0
        self.proc.stub(RAND[game], rand)
        self.village = Village(self.proc, game)
        for i in range(6):
            self.village.put(i, sex="m" if i % 2 else "f", years=20 + i, name=f"V{i}")
        fields = SCRATCH + 0x8000
        self.proc.export("VvfpStoryProbeOutcomeFields", fields)
        self.fields = struct.unpack("<5I", self.proc.read(fields, 20))

    # -- arming ------------------------------------------------------------
    def arm(self, slot: int, choices: dict[int, int], who: dict[int, list[int]] | None = None,
            strength: int = 0, unlocked: int = 0) -> int:
        count = max(len(controls_of(self.game, slot)), 1)
        values = [choices.get(i, -1) for i in range(count)]
        self.proc.write(SCRATCH, struct.pack(f"<{count}i", *values))
        bitmap = bytearray(32 * count)
        for ci, indices in (who or {}).items():
            for index in indices:
                bitmap[32 * ci + index // 8] |= 1 << (index % 8)
        self.proc.write(SCRATCH + 0x1000, bytes(bitmap))
        return self.proc.export("VvfpStoryProbeOutcomeArm", self.n, slot, SCRATCH, count,
                                SCRATCH + 0x1000, strength, unlocked)

    def force(self, state: int, branch: int = -1, in_apply: int = 0, obj: int = 0, gong=False):
        if gong:
            self.proc.export("VvfpStoryProbeGongForce", state, in_apply)
        else:
            self.proc.export("VvfpStoryProbeOutcomeForce", state, branch & 0xFFFFFFFF, in_apply, obj)

    def scope(self, va: int, depth: int) -> int:
        index = self.proc.export("VvfpStoryProbeOutcomeScope", self.n, va, depth)
        return index - (1 << 32) if index & 0x80000000 else index

    def state(self) -> tuple:
        self.proc.export("VvfpStoryProbeOutcomeState", SCRATCH + 0x2000)
        return struct.unpack("<7i", self.proc.read(SCRATCH + 0x2000, 28))

    def stats(self) -> tuple:
        return struct.unpack("<4i", self.proc.read(self.proc.exports["VvfpStoryOutcomeStats"], 16))

    # -- a roll --------------------------------------------------------------
    def roll(self, site: int, bound: int, regs: dict | None = None, stack: dict | None = None) -> int:
        """Run the rewritten `call` at `site` as the game does (bound pushed)."""
        proc = self.proc
        proc.put32(STACK, bound)
        for off, value in (stack or {}).items():
            proc.put32(STACK + off, value)
        for reg, value in (regs or {}).items():
            proc.set_reg(reg, value)
        proc.set_reg("esp", STACK)
        proc.run(site, site + 5)
        value = proc.reg("eax")
        return value - (1 << 32) if value & 0x80000000 else value

    def forced_roll(self, site: int, bound: int, **kw) -> tuple[int, bool]:
        before = self.stats()[0]
        value = self.roll(site, bound, **kw)
        return value, self.stats()[0] == before + 1


def _ready(g: Game, c: dict, *, gong: bool = False, branch=None):
    """Put the armed outcome where control `c` answers."""
    phase = c["phase"]
    state = ARMED if phase == "select" else DELIVERED
    if branch is None:
        branch = -1 if c["branch"] is None else c["branch"]
    g.force(state, branch, in_apply=1 if phase == "apply" else 0, gong=gong)
    if c.get("scope_call") is not None:
        assert g.scope(c["scope_call"], 1) >= 0, hex(c["scope_call"])


def _record_regs(g: Game, where: dict, index: int) -> tuple[dict, dict]:
    """Registers / stack that make `where` (a record expression) name record `index`."""
    base = g.village.record(index)
    if "reg" in where:
        reg = where["reg"]
        assert reg != "esp", "a record is never the stack"
        return {reg: base - where["disp"]}, {}
    reg, off = where["mem"]
    assert reg == "esp", "a record behind another register is not used by any control"
    return {}, {off: base - where["disp"]}


# ---------------------------------------------------------------------------
# The compiled tables are the data
# ---------------------------------------------------------------------------

@emulated
class TableTests(unittest.TestCase):
    def test_every_event_and_control_is_compiled_as_traced(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            g = Game(game)
            compiled = {}
            i = 0
            while g.proc.export("VvfpStoryProbeOutcomeEvent", g.n, i, SCRATCH) == 1:
                slot, count, strength, unlock = struct.unpack("<4i", g.proc.read(SCRATCH, 16))
                compiled[slot] = (i, count, strength, unlock)
                i += 1
            for slot in events_of(game):
                cs = controls_of(game, slot)
                with self.subTest(game=game, slot=slot):
                    self.assertIn(slot, compiled)
                    index, count, strength, _ = compiled[slot]
                    self.assertEqual(count, len(cs))
                    want = {None: 0, "linear": 1, "barrel": 2}[outcomes.STRENGTH.get(game, {}).get(slot)]
                    self.assertEqual(strength, want)
                    for ci, c in enumerate(cs):
                        self.assertEqual(g.proc.export("VvfpStoryProbeOutcomeControl", g.n, index, ci,
                                                       SCRATCH), 1)
                        out = struct.unpack("<114i", g.proc.read(SCRATCH, 456))
                        self.assertEqual(out[0], KINDS[c["kind"]], c["id"])
                        self.assertEqual(out[1], PHASES[c["phase"]], c["id"])
                        self.assertEqual(out[2], -1 if c["branch"] is None else c["branch"], c["id"])
                        self.assertEqual(out[3] & 0xFFFFFFFF, c.get("scope_call") or 0, c["id"])
                        if c["kind"] == "enum":
                            self.assertEqual(out[5], len(c["options"]), c["id"])
                            for k, o in enumerate(c["options"][:32]):
                                self.assertEqual(out[18 + 3 * k], len(o["force"]))
                                self.assertEqual((out[19 + 3 * k], out[20 + 3 * k]),
                                                 tuple(o["force"][0]), (c["id"], o["label"]))
                        else:
                            self.assertEqual(out[4], c["site"], c["id"])
                            bound = c.get("bound")
                            self.assertEqual(out[6], bound if isinstance(bound, int) else 0, c["id"])
                        if c["kind"] == "amount":
                            self.assertEqual((out[7], out[8]), (c["base"], c["step"]), c["id"])
                        if c["kind"] == "loop":
                            self.assertEqual((out[9], out[10]),
                                             (-1 if c["everyone"] is None else c["everyone"],
                                              -1 if c["nobody"] is None else c["nobody"]), c["id"])

    def test_every_option_and_value_is_within_the_rolls_bound(self):
        for game in GAMES:
            for slot in events_of(game):
                for c in controls_of(game, slot):
                    with self.subTest(game=game, slot=slot, control=c["id"]):
                        if c["kind"] in ("amount", "loop"):
                            self.assertIsInstance(c["bound"], int)
                            self.assertGreaterEqual(c["bound"], 2)
                        if c["kind"] == "loop":
                            for v in (c["everyone"], c["nobody"]):
                                if v is not None and isinstance(c["bound"], int):
                                    self.assertTrue(0 <= v < c["bound"])
                        if c["kind"] == "enum":
                            self.assertGreaterEqual(len(c["options"]), 2)
                            for o in c["options"]:
                                for _, value in o["force"]:
                                    self.assertGreaterEqual(value, 0)


# ---------------------------------------------------------------------------
# Every setting: its rolls answer exactly the chosen value, only where it applies
# ---------------------------------------------------------------------------

def _bound_for(c: dict, value: int) -> int:
    b = c.get("bound")
    return b if isinstance(b, int) and b > value else value + 1


@emulated
class SettingTests(unittest.TestCase):
    """Each control of each event: chosen -> forced at every site of it."""

    def _each(self, kinds):
        for game in GAMES:
            if not have_stock(game):
                continue
            g = Game(game)
            for slot in events_of(game):
                for ci, c in enumerate(controls_of(game, slot)):
                    if c["kind"] in kinds:
                        yield g, game, slot, ci, c

    def test_every_result_option(self):
        for g, game, slot, ci, c in self._each(("enum",)):
            gong = slot == GONG_SLOT
            for k, o in enumerate(c["options"]):
                with self.subTest(game=game, slot=slot, control=c["id"], option=o["label"]):
                    g.arm(slot, {ci: k})
                    for va, value in o["force"]:
                        _ready(g, c, gong=gong)
                        for _ in range(c.get("occurrence", 1) - 1):
                            g.roll(va, value + 1)       # the earlier babies' calls
                        got, forced = g.forced_roll(va, value + 1)
                        self.assertEqual((got, forced), (value, True), hex(va))
                    g.proc.export("VvfpStoryProbeOutcomeDisarm")
                    g.force(IDLE, gong=gong)

    def test_every_amount_value(self):
        for g, game, slot, ci, c in self._each(("amount",)):
            gong = slot == GONG_SLOT
            samples = sorted({0, c["bound"] // 2, c["bound"] - 1})
            for value in samples:
                for va in control_sites(c):
                    with self.subTest(game=game, slot=slot, control=c["id"], value=value, site=hex(va)):
                        g.arm(slot, {ci: value})
                        _ready(g, c, gong=gong)
                        for _ in range(c.get("occurrence", 1) - 1):
                            g.roll(va, c["bound"])
                        self.assertEqual(g.forced_roll(va, c["bound"]), (value, True))
                        g.force(IDLE, gong=gong)

    def test_every_loop_nobody_everyone_and_chosen(self):
        for g, game, slot, ci, c in self._each(("loop",)):
            gong = slot == GONG_SLOT
            for setting, want in ((NOBODY, c["nobody"]), (EVERYONE, c["everyone"])):
                if want is None:
                    continue
                with self.subTest(game=game, slot=slot, control=c["id"], setting=setting):
                    g.arm(slot, {ci: setting})
                    _ready(g, c, gong=gong)
                    for _ in range(3):           # every villager the loop visits
                        self.assertEqual(g.forced_roll(c["site"], c["bound"]), (want, True))
                    g.force(IDLE, gong=gong)
            if c.get("record") is None or c["nobody"] is None or c["everyone"] is None:
                continue
            with self.subTest(game=game, slot=slot, control=c["id"], setting="choose"):
                g.arm(slot, {ci: CHOOSE}, who={ci: [1, 4]})
                _ready(g, c, gong=gong)
                for index in range(6):
                    regs, stack = _record_regs(g, c["record"], index)
                    want = c["everyone"] if index in (1, 4) else c["nobody"]
                    self.assertEqual(g.forced_roll(c["site"], c["bound"], regs=regs, stack=stack),
                                     (want, True), index)
                g.force(IDLE, gong=gong)

    def test_every_victim(self):
        for g, game, slot, ci, c in self._each(("victim",)):
            cand = c["candidates"]
            if "reg" not in cand["base"] or cand["base"]["reg"] != "esp":
                self.fail(f"{game} {slot} {c['id']}: candidates not on the stack")
            base = cand["base"]["disp"]
            listed = [0, 2, 3, 5]
            elems = [i if cand["elem"] == "index" else g.village.record(i) - cand.get("elem_disp", 0)
                     for i in listed]
            stack = {base + cand["size"] * k: e for k, e in enumerate(elems)}
            for position, index in enumerate(listed):
                with self.subTest(game=game, slot=slot, control=c["id"], villager=index):
                    g.arm(slot, {ci: index})
                    _ready(g, c)
                    self.assertEqual(g.forced_roll(c["site"], len(listed), stack=stack),
                                     (position, True))
                    g.force(IDLE)
            with self.subTest(game=game, slot=slot, control=c["id"], villager="not a candidate"):
                g.arm(slot, {ci: 4})
                _ready(g, c)
                self.assertEqual(g.forced_roll(c["site"], len(listed), stack=stack),
                                 (stock_value(len(listed)), False))
                self.assertEqual(g.state()[5], 1, "the miss is recorded")
                g.force(IDLE)


@emulated
class GateTests(unittest.TestCase):
    """A setting answers only in its phase, branch, scope and baby; Random
    and every other event's settings leave each roll to the game."""

    def test_wrong_phase_branch_scope_or_baby_is_stock(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            g = Game(game)
            for slot in events_of(game):
                gong = slot == GONG_SLOT
                for ci, c in enumerate(controls_of(game, slot)):
                    if c["kind"] == "enum":
                        choice, va, value = 0, *c["options"][0]["force"][0]
                    elif c["kind"] == "loop":
                        choice = EVERYONE if c["everyone"] is not None else NOBODY
                        va, value = c["site"], c["everyone"] if c["everyone"] is not None else c["nobody"]
                    elif c["kind"] == "victim":
                        continue                      # needs its candidates (SettingTests)
                    else:
                        choice, va, value = c["bound"] - 1, c["site"], c["bound"] - 1
                    bound = _bound_for(c, value)
                    cases = []
                    if c["phase"] == "build":
                        cases.append(("armed, not yet delivered", ARMED, 0))
                    if c["phase"] == "apply":
                        cases.append(("delivered, apply not running", DELIVERED, 0))
                    for name, state, in_apply in cases:
                        with self.subTest(game=game, slot=slot, control=c["id"], case=name):
                            g.arm(slot, {ci: choice})
                            g.force(state, -1, in_apply, gong=gong)
                            if c.get("scope_call") is not None:
                                g.scope(c["scope_call"], 1)
                            self.assertFalse(g.forced_roll(va, bound)[1])
                    if c["branch"] is not None and not gong:
                        with self.subTest(game=game, slot=slot, control=c["id"], case="other branch"):
                            g.arm(slot, {ci: choice})
                            _ready(g, c, branch=1 - c["branch"])
                            self.assertFalse(g.forced_roll(va, bound)[1])
                    if c.get("scope_call") is not None:
                        with self.subTest(game=game, slot=slot, control=c["id"], case="outside its call"):
                            g.arm(slot, {ci: choice})
                            _ready(g, c, gong=gong)
                            g.scope(c["scope_call"], 0)
                            if c.get("scope_call_alt") is not None:
                                g.scope(c["scope_call_alt"], 0)
                            self.assertEqual(g.forced_roll(va, bound), (stock_value(bound), False))
                    if c.get("occurrence", 0) > 1:
                        with self.subTest(game=game, slot=slot, control=c["id"], case="another baby"):
                            g.arm(slot, {ci: choice})
                            _ready(g, c, gong=gong)
                            self.assertFalse(g.forced_roll(va, bound)[1], "the first call")
                    with self.subTest(game=game, slot=slot, control=c["id"], case="random"):
                        g.arm(slot, {})
                        _ready(g, c, gong=gong)
                        self.assertEqual(g.forced_roll(va, bound), (stock_value(bound), False))
                    g.force(IDLE, gong=gong)
                    g.force(IDLE)

    def test_another_events_settings_never_touch_a_roll(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            g = Game(game)
            slots = list(events_of(game))
            sites = {s: {va for c in controls_of(game, s) for va in control_sites(c)} for s in slots}
            for slot in slots:
                cs = controls_of(game, slot)
                if not cs or slot == GONG_SLOT:
                    continue
                choices = {}
                for ci, c in enumerate(cs):
                    choices[ci] = 0 if c["kind"] in ("enum", "amount") else (
                        EVERYONE if c["kind"] == "loop" else 0)
                g.arm(slot, choices)
                g.force(DELIVERED, -1, 1)
                for va in sorted(set().union(*(sites[s] for s in slots if s != slot)) - sites[slot]):
                    with self.subTest(game=game, armed=slot, site=hex(va)):
                        self.assertEqual(g.forced_roll(va, 50), (stock_value(50), False))
                g.proc.export("VvfpStoryProbeOutcomeDisarm")


# ---------------------------------------------------------------------------
# The game's own code, run for real with a village
# ---------------------------------------------------------------------------

def _control(game: str, slot: int, cid: str) -> tuple[int, dict]:
    for ci, c in enumerate(controls_of(game, slot)):
        if c["id"] == cid:
            return ci, c
    raise KeyError((game, slot, cid))


@emulated
class TsunamiTests(unittest.TestCase):
    """The Secret City's tsunami: its apply 0x414B30 calls the sweep 0x45D990,
    which rolls rand(100) < 15 for every villager (present byte +0xF10)."""

    def _sweep(self, choice, who=(), slot=1, cid="victims"):
        g = Game("vv3")
        for i in range(6, 10):
            g.village.put(i, sex="f", years=10 + i, name=f"W{i}")
        ci, c = _control("vv3", slot, cid)
        g.arm(slot, {} if choice is None else {ci: choice}, who={ci: list(who)})
        g.force(DELIVERED, -1, 1)
        g.proc.call(0x414B30, ecx=0, until=0x414B3E)
        return [g.village.byte(i, 0xF10) for i in range(10)], g

    def test_nobody_everyone_and_the_chosen(self):
        present, _ = self._sweep(NOBODY)
        self.assertEqual(present, [1] * 10)
        present, _ = self._sweep(EVERYONE)
        self.assertEqual(present, [0] * 10)
        present, _ = self._sweep(CHOOSE, who=(2, 5, 9))
        self.assertEqual(present, [0 if i in (2, 5, 9) else 1 for i in range(10)])

    def test_random_is_the_games_own_roll(self):
        present, g = self._sweep(None)
        self.assertEqual(present, [1] * 10)            # the stub's 63 is never below 15
        self.assertEqual(g.rand_calls.count(100), 10, "one roll per villager, as stock")

    def test_the_low_tides_setting_never_reaches_the_tsunamis_sweep(self):
        """Both events share the sweep; each setting answers only under its own call."""
        g = Game("vv3")
        ci, _ = _control("vv3", 23, "swept")
        g.arm(23, {ci: EVERYONE})
        g.force(DELIVERED, -1, 1)
        g.proc.call(0x414B30, ecx=0, until=0x414B3E)
        self.assertEqual([g.village.byte(i, 0xF10) for i in range(6)], [1] * 6)


@emulated
class BabyTests(unittest.TestCase):
    """The Secret City's barrel (0x415320): each baby's sex, skill and level
    reach the game's own creator 0x45FF50 exactly as chosen."""

    def test_each_babys_rolls_reach_the_creator(self):
        g = Game("vv3")
        made = []

        def create(p):
            made.append([p.arg(i) for i in range(5)])
            return len(made), 0x14
        g.proc.stub(0x45FF50, create)
        g.proc.stub(0x45FE30, lambda p: (1, 0))
        cs = controls_of("vv3", 57)
        ids = {c["id"]: ci for ci, c in enumerate(cs)}
        want = [(1, 2, 7), (0, 4, 9), (1, 0, 5)]       # (sex, skill, level)
        choices = {}
        for k, (sex, skill, level) in enumerate(want, 1):
            choices[ids[f"baby{k}_sex"]] = sex
            choices[ids[f"baby{k}_skill"]] = skill
            choices[ids[f"baby{k}_level"]] = level - 5
        g.arm(57, choices)
        g.force(DELIVERED, -1, 1)
        g.proc.call(0x415320, ecx=0)
        self.assertEqual([(m[3], m[1], m[2]) for m in made], want)
        self.assertEqual([m[4] for m in made], [200] * 3)


# The game's own villager pickers: (game, slot, control, how to call it).
PICKERS = {
    # thiscall on the records, adults_only = 0: any living villager
    "vv1": (65, "subject", lambda g: g.proc.call(0x43BCD0, [0], ecx=g.village.base)),
    "vv2": (131, "finder", lambda g: g.proc.call(0x44BAE0, [0], ecx=g.village.base)),
    # the event's own condition method: its picker call stores the subject at [obj+4]
    "vv3": (15, "subject", "m1:0x415420:0x415436"),
    "vv4": (12, "subject", "m1:0x415E00:0x415E21"),
    "vv5": (5, "subject", "m1:0x414B90:0x414BB9"),
}


@emulated
class PickerTests(unittest.TestCase):
    """Each game's own picker, with the chosen villager among its candidates,
    picks that villager; one it would not pick leaves the choice to the game."""

    def _pick(self, game, chosen):
        g = Game(game)
        slot, cid, how = PICKERS[game]
        ci, c = _control(game, slot, cid)
        g.arm(slot, {ci: chosen})
        _ready(g, c)
        if callable(how):
            value = how(g)
            return (value - (1 << 32) if value & 0x80000000 else value), g
        _, start, until = how.split(":")
        obj = g.proc.alloc(0x40)
        g.proc.call(int(start, 16), ecx=obj, regs={"esi": 0}, until=int(until, 16))
        record = g.proc.reg("eax")
        return (g.village.L and story_index(g, record)), g

    def test_the_chosen_villager_is_picked(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            for chosen in (1, 5):        # men: The Daredevil picks a man
                with self.subTest(game=game, chosen=chosen):
                    got, g = self._pick(game, chosen)
                    self.assertEqual(got, chosen)
                    self.assertEqual(g.state()[5], 0, "found among the candidates")

    def test_a_villager_the_game_would_not_pick_is_left_to_the_game(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                got, g = self._pick(game, 120)       # no such villager
                self.assertIn(got, range(6))
                self.assertEqual(g.state()[5], 1)


# Every per-villager loop: the game's own helper, called as the event's own
# code calls it (its arguments and ECX), with a village.  "obj" is an event
# object whose record pointers (+0x50A8 / +0x50AC A New Home, +0x50B0 The
# Lost Children) name the village's records.
LOOP_CALLS = {
    ("vv1", 68, "sick"): (0x4188B0, [0x4B], "obj"),
    ("vv1", 130, "sick"): (0x42AAA0, [20, 0, 0], "obj"),
    ("vv1", 131, "bitten"): (0x42AAA0, [30, 1, 15], "obj"),
    ("vv2", 11, "sick"): (0x4332F0, [0x50, 0, 0], "obj"),
    ("vv2", 14, "bitten"): (0x4332F0, [0x28, 1, 0x3C], "obj"),
    ("vv2", 27, "learns"): (0x4333B0, [0x23, 2, 7, 0xB, 1], "obj"),
    ("vv2", 75, "sick"): (0x41F500, [0x14], "obj"),
    ("vv2", 81, "snakes"): (0x41F500, [0x28], "obj"),
    ("vv2", 130, "sick"): (0x437570, [20, 0, 0], "obj"),
    ("vv2", 131, "bitten"): (0x437570, [30, 1, 15], "obj"),
    ("vv3", 1, "victims"): (0x45D990, [15, -1], 0x59E110),
    ("vv3", 3, "winners"): (0x45DC40, [0x32, 3, 0xA, 0xA, 1], 0x59E110),
    ("vv3", 19, "sick"): (0x45D760, [0x1E, 0, 0], 0x59E110),
    ("vv3", 22, "display_gain"): (0x45DC40, [0x14, 3, 0xA, 0x19, 0], 0x59E110),
    ("vv3", 23, "swept"): (0x45D990, [0x14, -1], 0x59E110),
    ("vv3", 23, "frightened"): (0x45D9F0, [0x14, 0x11], 0x59E110),
    ("vv3", 53, "stung"): (0x45D920, [0x32, 0xA, 0xA], 0x59E110),
    ("vv4", 14, "healers"): (0x467110, [0x50, 2, 5, 5, 0], 0x50E568),
    ("vv4", 15, "sick"): (0x466F40, [0x1E, 0, 0], 0x50E568),
    ("vv4", 21, "stung"): (0x467040, [0x32, 0xA, 0xA], 0x50E568),
    ("vv4", 26, "hurt"): (0x467040, [0xA, 5, 0xA], 0x50E568),
    ("vv4", 26, "sick"): (0x466F40, [0x14, 0, 0], 0x50E568),
    ("vv4", 32, "sick"): (0x466F40, [0x19, 0, 0], 0x50E568),
    # The Abandoned Infants: the first six women conceive (0x45E7B0); the
    # twins / triplets rolls exist only at Parenting mastery 3 (0x41E1C0(1)).
    ("vv4", 28, "multiple"): (0x467B00, [-1, 6, 1, -1, 0, 0], 0x50E568,
                              {0x41E1C0: (3, 4), 0x468350: (1, 0), 0x412F90: (0, 8), 0x4724E0: (0, 0),
                               0x468C60: (0, 0)}, {}),
    ("vv4", 28, "triplets"): (0x467B00, [-1, 6, 1, -1, 0, 0], 0x50E568,
                              {0x41E1C0: (3, 4), 0x468350: (1, 0), 0x412F90: (0, 8), 0x4724E0: (0, 0),
                               0x468C60: (0, 0)},
                              {"multiple": EVERYONE}),
}


@emulated
class LoopTests(unittest.TestCase):
    """Nobody / everyone / the chosen: the villagers the game's own loop
    changes are exactly those the setting names (records compared byte for
    byte against the same loop with "nobody")."""

    def _run(self, key, choice, who=()):
        game, slot, cid = key
        target, args, ecx, stubs, also = (LOOP_CALLS[key] + ({}, {}))[:5]
        g = Game(game)
        for va, (value, pop) in stubs.items():
            g.proc.stub(va, lambda p, value=value, pop=pop: (value, pop))
        for i in (6, 7):
            g.village.put(i, sex="f" if i == 6 else "m", years=6 + i - 6, name=f"C{i}")
        ci, c = _control(game, slot, cid)
        choices = {ci: choice}
        for other, value in also.items():
            choices[_control(game, slot, other)[0]] = value
        g.arm(slot, choices, who={ci: list(who)})
        _ready(g, c)
        if ecx == "obj":
            obj = g.proc.alloc(0x6000)
            for off in (0x50A8, 0x50AC, 0x50B0):
                g.proc.put32(obj + off, g.village.base)
            ecx = obj
        g.proc.call(target, [a & 0xFFFFFFFF for a in args], ecx=ecx)
        stride = g.village.L["stride"]
        return [g.proc.read(g.village.record(i), stride) for i in range(8)]

    def test_every_loop(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            keys = [(game, s, c["id"]) for s, cs in outcomes.CONTROLS[game].items() for c in cs
                    if c["kind"] == "loop" and c.get("record") is not None]
            for key in keys:
                with self.subTest(loop=key):
                    self.assertIn(key, LOOP_CALLS, "every loop with a villager is run here")
                    nobody = self._run(key, NOBODY)
                    everyone = self._run(key, EVERYONE)
                    hit = [i for i in range(8) if everyone[i] != nobody[i]]
                    self.assertGreaterEqual(len(hit), 2, "the loop changes the villagers it hits")
                    chosen = (hit[0], hit[-1])
                    some = self._run(key, CHOOSE, who=chosen)
                    self.assertEqual([i for i in range(8) if some[i] != nobody[i]], list(chosen))


# ---------------------------------------------------------------------------
# The armed outcome's life
# ---------------------------------------------------------------------------

# The popup's OK handler: (game, two-choice start, end, single-result start, end,
# vtable offsets).  ESI is the dialog (+0x830 the clicked choice), ECX the event.
OK_PATHS = {
    "vv3": (0x419A29, 0x419A35, 0x419A41, 0x419A46),
    "vv4": (0x417EC9, 0x417ED9, 0x417EE5, 0x417EEE),
    "vv5": (0x418749, 0x418759, 0x418765, 0x41876E),
}
TABLES = {"vv3": 0x4B3C78, "vv4": 0x4CCA28, "vv5": 0x4DC850}
PICK_SITES = {"vv3": (0x419BDB, 0x419BE2), "vv4": (0x4180F7, 0x4180FE), "vv5": (0x41895B, 0x418962)}


@functools.lru_cache(maxsize=None)
def _image(game: str):
    return pefile.PE(data=render(game, "collection_progression"), fast_load=True)


def stock_target(game: str, va: int) -> int:
    """The callee of the `E8 rel32` at `va` as the render holds it (the
    companion rewrites it at install)."""
    pe = _image(game)
    raw = pe.get_data(va - pe.OPTIONAL_HEADER.ImageBase, 5)
    assert raw[0] == 0xE8, hex(va)
    return (va + 5 + struct.unpack("<i", raw[1:])[0]) & 0xFFFFFFFF


def _first_slot(game: str, kind: str = "any") -> tuple[int, int, dict]:
    for slot, cs in outcomes.CONTROLS[game].items():
        for ci, c in enumerate(cs):
            if kind == "any" or c["phase"] == kind:
                return slot, ci, c
    raise KeyError(game)


class _Event:
    """A stand-in event object whose apply methods are Python stubs that see
    the armed outcome's fields while they run."""

    def __init__(self, g: Game, slot: int):
        self.g = g
        self.obj = g.proc.alloc(0x40)
        self.vtable = g.proc.alloc(0x40)
        self.code = g.proc.alloc(0x40)
        g.proc.write(self.code, b"\xC3" * 0x20)
        g.proc.put32(self.obj, self.vtable)
        for i in range(16):
            g.proc.put32(self.vtable + 4 * i, self.code + i)
        self.seen = []
        state, in_apply, branch = g.fields[0], g.fields[1], g.fields[2]

        def apply(pop):
            def fn(p):
                self.seen.append((p.u32(state), p.u32(in_apply), p.u32(branch) - (1 << 32)
                                  if p.u32(branch) & 0x80000000 else p.u32(branch)))
                return 0, pop
            return fn
        g.proc.stub(self.code + 11, apply(4))     # +0x2C applyChoice(choice)
        g.proc.stub(self.code + 12, apply(0))     # +0x30 apply()
        g.proc.put32(TABLES[g.game] + 4 * slot, self.obj)


@emulated
class LifeTests(unittest.TestCase):
    def _ok(self, g: Game, event: _Event, choice: int | None):
        start, end, s_start, s_end = OK_PATHS[g.game]
        dlg = g.proc.alloc(0x900)
        g.proc.put32(dlg + 0x830, 0 if choice is None else choice)
        g.proc.set_reg("esi", dlg)
        g.proc.set_reg("ecx", event.obj)
        g.proc.set_reg("edx", event.vtable)
        g.proc.set_reg("esp", STACK)
        if choice is None:
            g.proc.run(s_start, s_end)
        else:
            g.proc.run(start, end)

    def test_vv3_vv5_the_popups_ok_applies_the_delivered_event_then_ends_it(self):
        for game in OK_PATHS:
            if not have_stock(game):
                continue
            slot, ci, c = _first_slot(game)
            for choice in (None, 0, 1):
                with self.subTest(game=game, choice=choice):
                    g = Game(game)
                    event = _Event(g, slot)
                    g.arm(slot, {ci: 0})
                    self.assertEqual(g.state()[0], ARMED)
                    g.force(DELIVERED, -1, 0, event.obj)
                    self._ok(g, event, choice)
                    self.assertEqual(event.seen, [(DELIVERED, 1, -1 if choice is None else choice)])
                    self.assertEqual(g.state()[0], IDLE, "ended when its apply returned")

    def test_the_same_event_happening_naturally_afterwards_is_stock(self):
        for game in OK_PATHS:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                slot, ci, c = _first_slot(game, "apply")
                g = Game(game)
                event = _Event(g, slot)
                g.arm(slot, {ci: 0})
                g.force(DELIVERED, -1, 0, event.obj)
                self._ok(g, event, None if c["branch"] is None else c["branch"])
                self.assertEqual(g.state()[0], IDLE)
                # The event again, chosen by the game itself: its rolls are the game's.
                va = control_sites(c)[0]
                self.assertEqual(g.forced_roll(va, 100), (stock_value(100), False))

    def test_vv3_vv5_another_objects_apply_is_not_the_events(self):
        """A custom event or the Origins barrel shown by the same popup."""
        for game in OK_PATHS:
            if not have_stock(game):
                continue
            slot, ci, c = _first_slot(game)
            g = Game(game)
            event = _Event(g, slot)
            other = _Event(g, slot)
            g.arm(slot, {ci: 0})
            g.force(DELIVERED, -1, 0, event.obj)
            self._ok(g, other, 0)
            self.assertEqual(other.seen, [(DELIVERED, 0, -1)])
            self.assertEqual(g.state()[0], DELIVERED, "still waiting for its own apply")

    def test_vv3_vv5_delivery_refusal_lapse_and_a_new_choice(self):
        for game in PICK_SITES:
            if not have_stock(game):
                continue
            slot, ci, c = _first_slot(game)
            position = [e["slot"] for e in story_island_events.EVENTS[game]].index(slot)
            site, resume = PICK_SITES[game]
            for case in ("delivered", "refused", "lapsed", "stale"):
                with self.subTest(game=game, case=case):
                    g = Game(game)
                    event = _Event(g, slot)
                    g.proc.stub(event.code + 1, lambda p, ok=(case != "refused"): (1 if ok else 0, 0))
                    g.proc.export("VvfpStoryProbeSetPick", g.n, position, 0)
                    g.arm(slot, {ci: 0})
                    g.proc.export("VvfpStoryProbeSetTick", 11 * 60 * 1000 if case == "lapsed" else 0)
                    if case == "stale":
                        g.force(DELIVERED, -1, 0, event.obj)
                        g.proc.export("VvfpStoryProbeSetPick", g.n, 0xFFFFFFFF, 0)
                    g.proc.set_reg("esi", 1)
                    g.proc.set_reg("esp", STACK)
                    g.proc.run(site, resume)
                    want = {"delivered": (DELIVERED, event.obj), "refused": (IDLE, 0),
                            "lapsed": (IDLE, 0), "stale": (IDLE, 0)}[case]
                    st = g.state()
                    self.assertEqual((st[0], st[6] & 0xFFFFFFFF), want)

    def test_vv1_vv2_the_resolve_call_applies_the_event_with_its_clicked_choice(self):
        resolves = {"vv1": [(0x41A444, 0x509C), (0x42D0C4, 0x509C)],
                    "vv2": [(0x422364, 0x50A4), (0x439DB4, 0x509C)]}
        for game, calls in resolves.items():
            if not have_stock(game):
                continue
            slot, ci, c = _first_slot(game)
            for va, field in calls:
                for clicked in (1, 2):
                    with self.subTest(game=game, call=hex(va), clicked=clicked):
                        g = Game(game)
                        target = stock_target(game, va)
                        seen = []
                        state, in_apply, branch = g.fields[:3]
                        g.proc.stub(target, lambda p: (seen.append(
                            (p.u32(state), p.u32(in_apply), p.u32(branch))) or 0, 0))
                        obj = g.proc.alloc(0x6000)
                        g.proc.put32(obj + field, clicked)
                        g.arm(slot, {ci: 0})
                        g.force(DELIVERED)
                        g.proc.set_reg("ecx", obj)
                        g.proc.set_reg("esp", STACK)
                        g.proc.run(va, va + 5)
                        self.assertEqual(seen, [(DELIVERED, 1, clicked - 1)])
                        self.assertEqual(g.state()[0], IDLE)

    def test_vv2_family_c_body_runs_with_the_chosen_strength(self):
        for slot, kind in outcomes.STRENGTH["vv2"].items():
            values = range(1, 11) if kind == "linear" else (1, 5, 8)
            for strength in values:
                with self.subTest(slot=slot, strength=strength):
                    g = Game("vv2")
                    seen = []
                    g.proc.stub(stock_target("vv2", 0x43483D),
                                lambda p: (seen.append((p.arg(0), p.arg(1), p.u32(g.fields[1]))) or 0, 8))
                    g.arm(slot, {}, strength=strength)
                    g.force(DELIVERED)
                    g.proc.put32(STACK, slot)
                    g.proc.put32(STACK + 4, 6)            # the population's own magnitude
                    g.proc.set_reg("esp", STACK)
                    g.proc.run(0x43483D, 0x434842)
                    self.assertEqual(seen, [(slot, strength, 1)])
                    self.assertEqual(g.state()[0], IDLE)
        with self.subTest(case="without a pick the population's magnitude stands"):
            g = Game("vv2")
            seen = []
            g.proc.stub(stock_target("vv2", 0x43483D),
                        lambda p: (seen.append((p.arg(0), p.arg(1))) or 0, 8))
            g.proc.put32(STACK, 5)
            g.proc.put32(STACK + 4, 6)
            g.proc.set_reg("esp", STACK)
            g.proc.run(0x43483D, 0x434842)
            self.assertEqual(seen, [(5, 6)])


def _position(game: str, slot: int) -> int:
    return [e["slot"] for e in story_island_events.EVENTS[game]].index(slot)


@emulated
class IslandWindowTests(unittest.TestCase):
    """A New Home's single-result island events run inside the island
    chooser call 0x428777 (story_c1.inc c1_choose): the outcome is applied
    there, with the chosen strength."""

    def _choose(self, *, slot=None, strength=0, magnitude=6):
        g = Game("vv1")
        seen = []
        g.proc.stub(0x428470, lambda p: (seen.append((p.arg(1), p.u32(g.fields[1]))) or 0, 8))
        g.proc.export("VvfpStoryProbeSetTick", 0)
        if slot is not None:
            g.proc.export("VvfpStoryProbeSetPick", 1, _position("vv1", slot), 0)
            g.arm(slot, {}, strength=strength)
        event = g.proc.alloc(0x6000)
        g.proc.put32(STACK, 2)
        g.proc.put32(STACK + 4, magnitude)
        g.proc.set_reg("ecx", event)
        g.proc.set_reg("esp", STACK)
        g.proc.run(0x428777, 0x42877C)
        return seen, g

    def test_each_strength_reaches_the_events_body(self):
        for slot, kind in outcomes.STRENGTH["vv1"].items():
            for strength in (range(1, 11) if kind == "linear" else (1, 5, 8)):
                with self.subTest(slot=slot, strength=strength):
                    seen, g = self._choose(slot=slot, strength=strength)
                    self.assertEqual(seen, [(strength, 1)])
                    self.assertEqual(g.state()[4], 0, "the window closes with the call")

    def test_normal_strength_and_other_picks_keep_the_populations(self):
        seen, _ = self._choose(slot=0, strength=0)
        self.assertEqual(seen, [(6, 0)], "nothing armed: no window, the game's magnitude")
        seen, _ = self._choose()
        self.assertEqual(seen, [(6, 0)])
        seen, _ = self._choose(slot=(1 << 6) | 2, strength=0)
        self.assertEqual(seen, [(6, 0)])

    def test_the_origins_barrel_never_takes_a_picks_strength(self):
        seen, _ = self._choose(slot=12, strength=1, magnitude=0x7F4B1A2C)
        self.assertEqual(seen, [(0x7F4B1A2C, 0)])


@emulated
class GongTests(unittest.TestCase):
    """The Lost Children's Gong of Wonder: one use is the call 0x461B8E."""

    def _ring(self, g: Game):
        seen = []
        g.proc.stub(0x44E8A0, lambda p: (seen.append((p.u32(g.fields[3]), p.u32(g.fields[4]))) or 0, 0))
        g.proc.set_reg("ecx", g.proc.alloc(0x100))
        g.proc.set_reg("esp", STACK)
        g.proc.run(0x461B8E, 0x461B93)
        return seen

    def _gong(self, tick=0):
        g = Game("vv2")
        ci, c = _control("vv2", GONG_SLOT, "result")
        g.proc.export("VvfpStoryProbeSetTick", 0)
        g.arm(GONG_SLOT, {ci: len(c["options"]) - 1})
        g.proc.export("VvfpStoryProbeSetTick", tick)
        return g

    def test_one_use_then_the_game_again(self):
        g = self._gong()
        self.assertEqual(self._ring(g), [(DELIVERED, 1)])
        self.assertEqual(self._ring(g), [(IDLE, 0)], "one use")

    def test_a_choice_older_than_ten_minutes_is_not_used(self):
        g = self._gong(tick=10 * 60 * 1000 + 1)
        self.assertEqual(self._ring(g), [(ARMED, 0)])

    def test_the_gongs_own_code_makes_the_chosen_villagers_sick(self):
        """The Gong's routine 0x44E8A0 run for real: 'Takes health' of tier B
        (30%) and tier C (15%), with the chosen villagers -- only they fall
        sick (+0x53C).  Tier B needs the tiers unlocked (village +0x2E910)."""
        cs = controls_of("vv2", GONG_SLOT)
        ids = {c["id"]: i for i, c in enumerate(cs)}
        result = cs[ids["result"]]
        for loop, pct in (("sick_b", "30%"), ("sick_c", "15%")):
            with self.subTest(loop=loop):
                g = Game("vv2")
                g.proc.write(g.village.world + 0x2E910, b"\1")
                k = [i for i, o in enumerate(result["options"]) if pct in o["label"]][0]
                g.proc.export("VvfpStoryProbeSetTick", 0)
                g.arm(GONG_SLOT, {ids["result"]: k, ids[loop]: CHOOSE}, who={ids[loop]: [1, 4]})
                g.proc.stub(0x4239D0, lambda p: (0, 0x1C))      # sparkles
                g.proc.stub(0x4257A0, lambda p: (0, 8))         # the message
                g.proc.set_reg("ecx", g.village.base)
                g.proc.set_reg("esp", STACK)
                g.proc.run(0x461B8E, 0x461B93)
                self.assertEqual([g.village.i32(i, 0x53C) for i in range(6)], [0, 1, 0, 0, 1, 0])

    def test_the_gongs_choice_never_answers_an_island_event_and_back(self):
        g = self._gong()
        g.force(DELIVERED, -1, 1)                    # an island event's apply running
        ci, c = _control("vv2", GONG_SLOT, "result")
        va, value = c["options"][-1]["force"][-1]
        self.assertEqual(g.forced_roll(va, 10), (stock_value(10), False), "not inside the gong's use")


def _script(values):
    values = list(values)

    def rand(p):
        bound = p.arg(0)
        value = values.pop(0) if values else 0
        assert 0 <= value < bound, (value, bound)
        return value, 0
    return rand


@emulated
class UnlockTests(unittest.TestCase):
    """A pick unlocked past its timing condition (or a developer-dead event
    proven to work) is delivered by the game's own chooser, once; without the
    unlock the chooser is stock (it rolls again)."""

    def _vv1(self, slot, unlocked, rands=(13,)):
        g = Game("vv1")
        g.proc.stub(0x402F10, _script(rands))
        g.proc.export("VvfpStoryProbeSetTick", 0)
        g.proc.export("VvfpStoryProbeSetPick", 1, _position("vv1", slot), 0)
        g.arm(slot, {}, unlocked=unlocked)
        event = g.proc.alloc(0x6000)
        g.proc.put32(event + 0x50A4, g.village.world)     # the beach is not clean
        g.proc.put32(event + 0x50A8, g.village.base)
        return g, event

    def test_vv1_island_events(self):
        for slot in (9, 1):                    # The Big Wave (beach), A Mighty Storm (dead)
            for unlocked in (1, 0):
                with self.subTest(slot=slot, unlocked=unlocked):
                    g, event = self._vv1(slot, unlocked)
                    seen = []
                    g.proc.stub(0x427CA0, lambda p: (seen.append((p.arg(0), p.arg(1))) or 0, 8))
                    g.proc.call(0x428470, [2, 6], ecx=event)
                    self.assertEqual(seen, [(slot if unlocked else 13, 6)])

    def test_vv1_the_pass_is_used_once(self):
        g, event = self._vv1(9, 1, rands=(9, 13))
        seen = []
        g.proc.stub(0x427CA0, lambda p: (seen.append(p.arg(0)) or 0, 8))
        g.proc.call(0x428470, [2, 6], ecx=event)
        g.proc.call(0x428470, [2, 6], ecx=event)       # the next island event: no pick
        self.assertEqual(seen, [9, 13], "the condition is the game's own again (9 rolled, re-rolled)")

    def test_vv1_vv2_a_delivered_outcome_ends_when_the_game_rolls_again(self):
        """The delivered event's own condition failed and the game rolls
        another: the outcome must not reach that other event."""
        for game, site, slot, bound in (("vv1", 0x418932, (1 << 6) | 3, 16),
                                        ("vv2", 0x41F59D, (1 << 6) | 9, 22)):
            with self.subTest(game=game):
                g = Game(game)
                g.proc.export("VvfpStoryProbeSetTick", 0)
                g.proc.export("VvfpStoryProbeSetPick", g.n, _position(game, slot), 0)
                g.arm(slot, {0: 0})
                self.assertEqual(g.roll(site, bound), slot & 0x3F)
                self.assertEqual(g.state()[0], DELIVERED)
                g.roll(site, bound)
                self.assertEqual(g.state()[0], IDLE)

    def test_vv1_encounters(self):
        g, event = self._vv1((1 << 6) | 5, 1, rands=(2,))           # The Furry Food (dead)
        self.assertEqual(g.proc.call(0x418920, [], ecx=event), 5)
        g, event = self._vv1((1 << 6) | 5, 0, rands=(2,))
        self.assertEqual(g.proc.call(0x418920, [], ecx=event), 2)
        for i in range(10):                    # no child: The Suspicious Monkey
            g.village.put(i, sex="m", years=30, name=f"A{i}")
        g, event = self._vv1((1 << 6) | 9, 1, rands=(2,))
        self.assertEqual(g.proc.call(0x418920, [], ecx=event), 9)

    def test_vv2_single_result_events(self):
        for slot in (8, 11, 14, 17, 18, 20, 26):
            # Without the unlock: the dead cases' never-valid entry rolls again
            # (the others' own checks read the whole village, run elsewhere).
            for unlocked in ((1, 0) if slot in (18, 20, 26) else (1,)):
                with self.subTest(slot=slot, unlocked=unlocked):
                    g = Game("vv2")
                    g.proc.stub(0x4031A0, _script((22,)))
                    g.proc.export("VvfpStoryProbeSetTick", 0)
                    g.proc.export("VvfpStoryProbeSetPick", 2, _position("vv2", slot), 0)
                    g.arm(slot, {}, unlocked=unlocked)
                    seen = []
                    g.proc.stub(stock_target("vv2", 0x43483D),
                                lambda p: (seen.append((p.arg(0), p.arg(1))) or 0, 8))
                    event = g.proc.alloc(0x6000)
                    g.proc.call(0x434570, [2, 7], ecx=event)
                    self.assertEqual(seen, [(slot if unlocked else 22, 7)])

    def test_vv2_two_choice_event(self):
        """The Silver Mirror with one villager: the family-A chooser returns it."""
        g = Game("vv2")
        g.proc.stub(0x4031A0, _script((3,)))
        g.proc.export("VvfpStoryProbeSetTick", 0)
        slot = (1 << 6) | 14
        g.proc.export("VvfpStoryProbeSetPick", 2, _position("vv2", slot), 0)
        g.arm(slot, {}, unlocked=1)
        event = g.proc.alloc(0x6000)
        self.assertEqual(g.proc.call(0x41F570, [], ecx=event), 14)

    def test_vv3_vv5_the_needed_villager_must_have_been_picked(self):
        """Its condition fails; it is delivered only if that condition picked
        the villager(s) it needs THIS time (a value left from an earlier pass
        never counts) and, for an event that makes villagers, there is room."""
        rooms = {"vv3": 0x45FE30, "vv4": 0x468350, "vv5": 0x472BD0}
        for game in ("vv3", "vv4", "vv5"):
            site, resume = PICK_SITES[game]
            for slot, entry in outcomes.UNLOCKED[game].items():
                fields = [off for off in entry["needs"] if off != "room"]
                cases = [("picked now", True, True), ("left from before", False, True)]
                if "room" in entry["needs"]:
                    cases.append(("no room", True, False))
                for case, picks, room in cases:
                    with self.subTest(game=game, slot=slot, case=case):
                        g = Game(game)
                        g.proc.stub(rooms[game], lambda p, room=room: (1 if room else 0, 0))
                        for other in range(1, 58):            # every other slot: its own object
                            g.proc.put32(TABLES[game] + 4 * other, g.proc.alloc(0x40))
                        event = _Event(g, slot)
                        record = g.village.record(1)

                        def condition(p, picks=picks):        # fails, after picking (or not)
                            for off in fields:
                                if picks:
                                    p.put32(p.reg("ecx") + off, record)
                            return 0, 0
                        g.proc.stub(event.code + 1, condition)
                        for off in fields:
                            g.proc.put32(event.obj + off, record)     # an earlier pass's villager
                        g.proc.export("VvfpStoryProbeSetTick", 0)
                        g.proc.export("VvfpStoryProbeSetPick", g.n, _position(game, slot), 0)
                        g.arm(slot, {}, unlocked=1)
                        other = 2 if slot != 2 else 3
                        g.proc.set_reg("esi", other)
                        g.proc.set_reg("esp", STACK)
                        g.proc.run(site, resume)
                        delivered = (picks or not fields) and room
                        self.assertEqual(g.proc.reg("esi"), slot if delivered else other)


@emulated
class ChooserTests(unittest.TestCase):
    """The dialog's own logic (story_outcomes_ui.inc) without its window:
    what each row says, what is refused, the tribe-ending warning, and which
    events can be picked."""

    def _open(self, game, ok=None, gong=False):
        g = Game(game)
        if game in TABLES:
            for slot in range(1, 58):
                event = _Event(g, slot)
                answer = 1 if ok is None else ok(slot)
                g.proc.stub(event.code + 1, lambda p, answer=answer: (answer, 0))
        n = g.proc.export("VvfpStoryProbeChooserOpen", g.n, 1 if gong else 0)
        return g, n

    def _text(self, g, index, what):
        result = g.proc.export("VvfpStoryProbeChooserText", index, what, SCRATCH + 0x3000, 1200)
        return result, g.proc.cstring(SCRATCH + 0x3000)

    def _set(self, g, index, ci, value, who=()):
        g.proc.write(SCRATCH + 0x4000, struct.pack(f"<{max(len(who), 1)}i", *(list(who) or [0])))
        g.proc.export("VvfpStoryProbeChooserSet", index, ci & 0xFFFFFFFF, value & 0xFFFFFFFF,
                      SCRATCH + 0x4000, len(who))

    def test_the_tsunami_warns_before_everyone_is_swept_away(self):
        g, _ = self._open("vv3")
        index = _position("vv3", 1)
        ci, c = _control("vv3", 1, "victims")
        self.assertEqual(self._text(g, index, 3)[1], "", "Random: no warning")
        self._set(g, index, ci, EVERYONE)
        self.assertEqual(self._text(g, index, 3)[1], c["warn_everyone"])
        self._set(g, index, ci, CHOOSE, who=range(6))
        self.assertEqual(self._text(g, index, 3)[1], c["warn_everyone"], "choosing everyone is everyone")
        self._set(g, index, ci, CHOOSE, who=(1, 3))
        self.assertEqual(self._text(g, index, 3)[1], "")
        self.assertIn("The chosen villagers (2)", self._text(g, index, 4 + ci)[1])
        self._set(g, index, ci, CHOOSE, who=())
        self.assertIn("choose at least one villager", self._text(g, index, 2)[1])
        self._set(g, index, ci, NOBODY)
        self.assertEqual(self._text(g, index, 2)[1], "")
        self.assertIn("Who is swept away: Nobody", self._text(g, index, 1)[1])

    def test_an_option_whose_condition_fails_can_not_be_bought(self):
        g, _ = self._open("vv1")
        index = _position("vv1", 67)
        ci, c = _control("vv1", 67, "result")
        k = [i for i, o in enumerate(c["options"]) if o.get("cond") == "room"][0]
        self._set(g, index, ci, k)
        g.proc.stub(0x43A1A0, lambda p: (0, 0))            # the village is full
        self.assertIn("not possible right now", self._text(g, index, 2)[1])
        g.proc.stub(0x43A1A0, lambda p: (1, 0))
        self.assertEqual(self._text(g, index, 2)[1], "")

    def test_rows_amounts_and_strength(self):
        g, _ = self._open("vv1")
        index = _position("vv1", 0)
        rows = len(controls_of("vv1", 0))
        self.assertEqual(self._text(g, index, 4 + rows)[1], "Strength: Normal (from the population)")
        self._set(g, index, -1, 7)
        self.assertEqual(self._text(g, index, 4 + rows)[1], "Strength: 7")
        self.assertIn("Strength: 7", self._text(g, index, 1)[1])
        index = _position("vv1", 12)
        self._set(g, index, -1, 5)
        self.assertIn("5-7 (two babies)", self._text(g, index, 1)[1])
        ci, c = _control("vv1", (1 << 6) | 10, "food")
        index = _position("vv1", (1 << 6) | 10)
        self._set(g, index, ci, c["bound"] - 1)
        self.assertIn(f"{c['base'] + c['bound'] - 1}", self._text(g, index, 4 + ci)[1])
        self._set(g, index, ci, -3)                         # a typed number out of range
        self.assertIn("type a whole number", self._text(g, index, 2)[1])

    def test_which_events_can_be_picked(self):
        unlockable = {s for s, e in outcomes.UNLOCKED["vv3"].items() if not e["needs"]}
        slot = sorted(unlockable)[0]
        g, _ = self._open("vv3", ok=lambda s: 0 if s in (slot, 47) else 1)
        self.assertEqual(self._text(g, _position("vv3", slot), 0)[0], 2, "normally not possible")
        self.assertEqual(self._text(g, _position("vv3", 47), 0)[0], 0, "a chief is needed: locked")
        self.assertEqual(self._text(g, _position("vv3", 2), 0)[0], 1)

    def test_the_gongs_tiers_need_the_tiers_open(self):
        g, n = self._open("vv2", gong=True)
        self.assertEqual(n, 1)
        ci, c = _control("vv2", GONG_SLOT, "result")
        k = [i for i, o in enumerate(c["options"]) if o.get("cond") == "vv2_gong_tiers"][0]
        self._set(g, 0, ci, k)
        self.assertIn("not possible right now", self._text(g, 0, 2)[1])
        g.proc.write(g.village.world + 0x2E910, b"\1")
        self.assertEqual(self._text(g, 0, 2)[1], "")


@emulated
class ModeParityTests(unittest.TestCase):
    """All three population modes: every outcome site is installed and every
    event's first setting forces exactly the same values; the tsunami's
    chosen villagers are the ones swept away in each mode."""

    def test_every_mode(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    g = Game(game, mode)
                    for slot in events_of(game):
                        cs = controls_of(game, slot)
                        if not cs:
                            continue
                        c = cs[0]
                        gong = slot == GONG_SLOT
                        if c["kind"] == "enum":
                            choice, (va, value) = 0, c["options"][0]["force"][0]
                        elif c["kind"] == "amount":
                            choice, va, value = c["bound"] - 1, c["site"], c["bound"] - 1
                        elif c["kind"] == "loop":
                            choice, va, value = NOBODY, c["site"], c["nobody"]
                        else:
                            continue
                        g.arm(slot, {0: choice})
                        _ready(g, c, gong=gong)
                        for _ in range(c.get("occurrence", 1) - 1):
                            g.roll(va, _bound_for(c, value))
                        self.assertEqual(g.forced_roll(va, _bound_for(c, value)), (value, True),
                                         (slot, c["id"]))
                        g.force(IDLE, gong=gong)
                        g.force(IDLE)
        for mode in MODES:
            with self.subTest(game="vv3", mode=mode, case="tsunami"):
                g = Game("vv3", mode)
                ci, _ = _control("vv3", 1, "victims")
                g.arm(1, {ci: CHOOSE}, who={ci: [0, 5]})
                g.force(DELIVERED, -1, 1)
                g.proc.call(0x414B30, ecx=0, until=0x414B3E)
                self.assertEqual([g.village.byte(i, 0xF10) for i in range(6)], [0, 1, 1, 1, 1, 0])


class DocAndCompanionTests(unittest.TestCase):
    def test_the_settings_document_is_generated_from_the_tables(self):
        import build_story_outcomes_doc as doc

        self.assertEqual((ROOT / "docs" / "story-island-outcomes.md").read_text(encoding="utf-8"),
                         doc.build())

    def test_the_lost_childrens_tech_menu_offers_the_gong(self):
        source = (ROOT / "native" / "vv2_origins_icons" / "vv2_origins_icons.c").read_text(encoding="utf-8")
        self.assertIn('GetProcAddress(module, "VvfpStoryPickGongOutcome")', source)
        self.assertIn("vv2_story_add_gong_button(window);", source)
        body = source[source.index("command == VV2_STORY_GONG_ID"):][:300]
        self.assertIn("vv2_story_gong_clicked(window)", body)
        self.assertNotIn("ISLAND", body, "no island lock")
        bridge = (ROOT / "native" / "shared" / "story_bridge.h").read_text(encoding="utf-8")
        self.assertNotIn("Gong", bridge, "the shared bridge (all five companions) is unchanged")
        binary = (ROOT / "assets" / "origins" / "VVFP VV2 Origins Icons.dll").read_bytes()
        self.assertIn(b"VvfpStoryPickGongOutcome", binary)
        shipped = (ROOT / "native" / "vvfp_story_upgrades" / "vvfp_story_upgrades.def").read_text()
        self.assertIn("VvfpStoryPickGongOutcome=_VvfpStoryPickGongOutcome@8", shipped)

    def test_player_facing_texts_carry_no_code(self):
        tables = (ROOT / "native" / "vvfp_story_upgrades" / "story_tables.h").read_text(encoding="utf-8")
        import re
        for text in re.findall(r'"((?:[^"\\]|\\.)*)"', tables):
            self.assertNotRegex(text, r"0x[0-9A-Fa-f]|\+0x", text)


def story_index(g: Game, record: int) -> int:
    if record == 0:
        return -1
    offset = record - g.village.base
    stride = g.village.L["stride"]
    return offset // stride if offset % stride == 0 else -2


if __name__ == "__main__":
    unittest.main()
