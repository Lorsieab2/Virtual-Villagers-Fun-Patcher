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
KINDS = {"enum": 1, "amount": 2, "loop": 3, "victim": 4, "ringer": 5}
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
def render(game: str, mode: str, extra: tuple[str, ...] = ()) -> bytes:
    ids = [f"{game}_origins_village_wide_upgrades", f"{game}_story_cheat_upgrades", *extra]
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
    if c["kind"] == "ringer":
        return []                     # no roll: the search's calls are scope calls
    if c["kind"] == "enum":
        return sorted({va for o in c["options"] for va, _ in o["force"]})
    return sorted({c["site"], *c.get("sites", [])})


class Game:
    """One game's process: the companion installed, the rand stubbed, a village."""

    def __init__(self, game: str, mode: str = "collection_progression", extra: tuple[str, ...] = ()):
        self.game = game
        self.n = int(game[2:])
        self.proc = Process(render(game, mode, extra), TEST_DLL)
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
                        elif c["kind"] == "ringer":
                            self.assertEqual((out[4], out[5]), (0, 0), c["id"])
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
class NameSettingTests(unittest.TestCase):
    """The Secret City's name settings (the Mysterious Vial's copy, the barrel's babies) name a
    list entry.  The stock game reaches it as roll + 1 (0x45C683 inc eax); Fix Vanilla Bugs makes
    that inc a nop so every default name can be chosen, and the answer then carries the + 1."""

    def test_the_chosen_entry_with_and_without_fix_vanilla_bugs(self):
        if not have_stock("vv3"):
            self.skipTest("stock executables not present")
        named = [(slot, ci, c) for slot in events_of("vv3") for ci, c in enumerate(controls_of("vv3", slot))
                 if c["kind"] == "amount" and c["site"] == 0x45C67B]
        self.assertEqual(len(named), 4)
        for extra, bound, offset in (((), 123, 0), (("vv3_fix_vanilla_bugs",), 125, 1)):
            g = Game("vv3", extra=extra)
            self.assertEqual(g.proc.read(0x45C683, 1), b"\x90" if extra else b"\x40")
            for slot, ci, c in named:
                for value in (0, 61, 122):
                    with self.subTest(fix=bool(extra), control=c["id"], value=value):
                        g.arm(slot, {ci: value})
                        _ready(g, c)
                        for _ in range(c.get("occurrence", 1) - 1):
                            g.roll(0x45C67B, bound)
                        got, forced = g.forced_roll(0x45C67B, bound)
                        self.assertTrue(forced)
                        # the entry the game names: the roll, plus the game's own + 1 when it has one
                        self.assertEqual(got + (1 - offset), value + 1)
                        g.force(IDLE)


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
                    elif c["kind"] in ("victim", "ringer"):
                        continue                      # needs its candidates / its search (SettingTests, GongRingTests)
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


# The Gong of Wonder's routine 0x44E8A0: each tier's jump table (entries) and
# the call whose roll picks the entry.
GONG_TIER_TABLES = {0x44E8CF: (0x44F450, 6), 0x44EBE5: (0x44F468, 9), 0x44EFE4: (0x44F48C, 9)}
GONG_SKILL_OFFSETS = (0x7E4, 0x7E8, 0x7F0, 0x7F4, 0x7EC)    # the order of the skill tables 0x44F4B0 / 0x44F4C4
GONG_NOW = 50000
RINGING = b"Ringing the Gong\0"


class _Ring:
    """The Lost Children with a village of six adults (V0-V5); V3's task is
    ringing the Gong.  The routine's helpers that draw, show text, keep the
    clock and add food / tech are stubbed and recorded; everything else --
    the tier gates, the jump tables, the ringer search 0x44B440, the records
    written -- is the game's own code."""

    def __init__(self, mode: str = "collection_progression", tiers: int = 0, ringer: int | None = 3,
                 extra: tuple[str, ...] = ()):
        from unicorn import UC_HOOK_CODE
        g = self.g = Game("vv2", mode, extra)
        p = g.proc
        self.w = g.village.world
        p.write(self.w + 0x2E910, bytes([tiers]))
        p.write(self.w + 0x2E7F0, b"\1")                      # the Gong is whole
        text = p.alloc(0x40)
        p.write(text, RINGING)
        p.stub(0x441680, lambda q: (text, 4))                 # the string table: id 0x10C
        if ringer is not None:
            p.write(g.village.record(ringer) + 0x4FC, RINGING)
        self.messages, self.food, self.tech, self.rests = [], [], [], []
        p.stub(0x4239D0, lambda q: (0, 0x1C))                 # sparkles
        p.stub(0x44B2A0, lambda q: (self.messages.append(q.arg(0)) or 0, 4))
        p.stub(0x4257A0, lambda q: (0, 8))                    # "rests about a full day"
        p.stub(0x403200, lambda q: (GONG_NOW, 0))             # the game's clock
        p.stub(0x4262B0, lambda q: (self.food.append(q.arg(0)) or 0, 4))
        p.stub(0x426290, lambda q: (self.tech.append(q.arg(0)) or 0, 4))
        self.entries = {}
        for site, (table, count) in GONG_TIER_TABLES.items():
            for k in range(count):
                self.entries[p.u32(table + 4 * k)] = (site, k)
        self.hit = []
        for va in self.entries:
            p.mu.hook_add(UC_HOOK_CODE, lambda mu, a, s, u: self.hit.append(self.entries[a]), begin=va, end=va)
        p.export("VvfpStoryProbeSetTick", 0)

    def arm(self, choices: dict[str, int], who: dict[str, list[int]] | None = None) -> int:
        ids = {c["id"]: i for i, c in enumerate(controls_of("vv2", GONG_SLOT))}
        return self.g.arm(GONG_SLOT, {ids[k]: v for k, v in choices.items()},
                          who={ids[k]: v for k, v in (who or {}).items()})

    def ring(self) -> list:
        """One use: the call 0x461B8E, as the action's completion makes it."""
        self.hit.clear()
        p = self.g.proc
        p.set_reg("ecx", self.g.village.base)
        p.set_reg("esi", self.g.village.base)
        p.set_reg("esp", STACK)
        p.run(0x461B8E, 0x461B93)
        assert p.reg("esi") == self.g.village.base, "the caller's ESI comes back as it was"
        assert p.reg("esp") == STACK, "the stack comes back balanced"
        return list(self.hit)

    def strike(self, until: int = 0x461B93) -> list:
        """The action's completion from its case 0x461B32: the rest test, the
        rest, then the use."""
        self.hit.clear()
        p = self.g.proc
        for reg, value in (("esi", self.g.village.base), ("ebx", 0), ("esp", STACK)):
            p.set_reg(reg, value)
        p.run(0x461B32, until)
        return list(self.hit)

    def gong(self) -> tuple:
        self.g.proc.export("VvfpStoryProbeGongState", SCRATCH + 0x2800)
        return struct.unpack("<4i", self.g.proc.read(SCRATCH + 0x2800, 16))

    def tiers(self) -> int:
        return self.g.proc.read(self.w + 0x2E910, 1)[0]

    def rest(self) -> int:
        return self.g.proc.u32(self.w + 0x2EAC8)


def _option(label_part: str) -> int:
    _, c = _control("vv2", GONG_SLOT, "result")
    found = [k for k, o in enumerate(c["options"]) if label_part in o["label"]]
    assert len(found) == 1, (label_part, found)
    return found[0]


def _entry(k: int) -> tuple[int, int]:
    """The tier call and jump-table entry result option k forces."""
    _, c = _control("vv2", GONG_SLOT, "result")
    return [(va, v) for va, v in c["options"][k]["force"] if va in GONG_TIER_TABLES][0]


@emulated
class GongRingTests(unittest.TestCase):
    """The owner (2026-10-20): "there are way more Gong of Wonder options ...
    I want ALL of them."  The Gong's routine 0x44E8A0 run for real: each of
    its 23 results, chosen, is the jump-table entry the routine takes -- also
    the tier A and B ones on a village whose tier lock is still closed, which
    is put back afterwards -- each amount and skill reaches the game's own
    code, and Random is the game's own roll."""

    def setUp(self):
        if not have_stock("vv2"):
            self.skipTest("stock executables not present")

    def test_every_result_takes_its_own_branch_before_and_after_the_first_ring(self):
        _, c = _control("vv2", GONG_SLOT, "result")
        for tiers in (0, 1):
            for k, o in enumerate(c["options"]):
                with self.subTest(tiers=tiers, option=o["label"]):
                    r = _Ring(tiers=tiers)
                    self.assertEqual(r.arm({"result": k}), ARMED)
                    self.assertEqual(r.ring(), [_entry(k)])
                    tier_c = _entry(k)[0] == 0x44EFE4
                    # tier C results open the lock themselves (0x44EFDB, stock); A and B leave it as it was
                    self.assertEqual(r.tiers(), 1 if tier_c else tiers)
                    self.assertEqual(r.gong()[0], IDLE, "one use")
                    self.assertEqual(r.gong()[3], 0)

    def test_random_is_the_games_own_roll(self):
        for tiers in (0, 1):
            with self.subTest(tiers=tiers):
                r = _Ring(tiers=tiers)
                # the stubbed rand: 63 of 100 (not tier A), 63 of 100 (not tier B), 5 of 9 (C entry 5)
                self.assertEqual(r.ring(), [(0x44EFE4, stock_value(9))])
                self.assertEqual(r.tiers(), 1)
                self.assertEqual(r.g.rand_calls[:3], [100, 100, 9])

    def test_a_chosen_result_with_random_amount_and_after_it_the_game_again(self):
        r = _Ring()
        r.arm({"result": _option("Grants luck")})
        self.assertEqual(r.ring(), [(0x44EBE5, 1)])
        self.assertEqual(r.g.proc.u32(r.w + 0x2EAE0), GONG_NOW + 60, "the luck timer, as the game sets it")
        self.assertEqual(r.tiers(), 0, "the lock is closed again")
        self.assertEqual(r.ring(), [(0x44EFE4, stock_value(9))], "the next ring is the game's own")

    def test_every_amount_reaches_the_games_own_code(self):
        cases = (("tech_big", "+20000..59999", "tech"), ("tech_medium", "+10000..29999", "tech"),
                 ("tech_small", "+3000..12999", "tech"), ("food_big", "+1000..2999", "food"),
                 ("food_small", "+200..999", "food"), ("tech_lost", "Takes technology", "lost"))
        for cid, label, where in cases:
            _, c = _control("vv2", GONG_SLOT, cid)
            for value in sorted({0, c["bound"] // 2, c["bound"] - 1}):
                with self.subTest(control=cid, value=value):
                    r = _Ring()
                    r.g.proc.put32(r.w + 0x2EADC, 100000)
                    r.arm({"result": _option(label), cid: value})
                    r.ring()
                    amount = c["base"] + c["step"] * value
                    if where == "lost":
                        self.assertEqual(r.g.proc.u32(r.w + 0x2EADC), 100000 - amount)
                    else:
                        self.assertEqual(getattr(r, where), [amount])

    def test_every_skill_of_grants_wisdom(self):
        _, c = _control("vv2", GONG_SLOT, "skill")
        for k, o in enumerate(c["options"]):
            with self.subTest(skill=o["label"]):
                r = _Ring()
                r.arm({"result": _option("Grants wisdom"), "skill": k})
                r.ring()
                for j, off in enumerate(GONG_SKILL_OFFSETS):
                    self.assertEqual(r.g.village.i32(3, off) == 100, j == k, (o["label"], hex(off)))


@emulated
class GongRingerTests(unittest.TestCase):
    """The owner (2026-10-20): for a Gong outcome that acts on a villager,
    the player chooses which villager; one no longer valid at the ring falls
    back to the game's own choice (and the picker says so)."""

    def setUp(self):
        if not have_stock("vv2"):
            self.skipTest("stock executables not present")

    RESULTS = (("Takes life", 0x52C, lambda before: 0),
               ("loses 90 health", 0x52C, lambda before: max(before - 90, 0)),
               ("Grants wisdom", 0x7EC, lambda before: 100))

    def _ring(self, label, ringer=3, chosen=None, spoil=None, mode="collection_progression"):
        r = _Ring(mode=mode, ringer=ringer)
        for i in range(6):
            r.g.proc.put32(r.g.village.record(i) + 0x52C, 95)
        choices = {"result": _option(label)}
        if label == "Grants wisdom":
            choices["skill"] = 4                                 # Farming (+0x7EC)
        if chosen is not None:
            choices["ringer"] = chosen
        r.arm(choices)
        if spoil is not None:
            spoil(r)
        r.ring()
        return r

    def _changed(self, r, off):
        base = 95 if off == 0x52C else 0
        return [i for i in range(6) if r.g.village.i32(i, off) != base]

    def test_the_chosen_villager_is_the_one_acted_on(self):
        for label, off, want in self.RESULTS:
            with self.subTest(result=label):
                r = self._ring(label, chosen=4)
                self.assertEqual(self._changed(r, off), [4])
                self.assertEqual(r.g.village.i32(4, off), want(95))
                self.assertEqual(r.gong()[2], 0, "the chosen villager was used")

    def test_random_is_the_villager_who_rang_it(self):
        for label, off, want in self.RESULTS:
            with self.subTest(result=label):
                r = self._ring(label)
                self.assertEqual(self._changed(r, off), [3])
                self.assertEqual(r.g.village.i32(3, off), want(95))

    def test_a_chosen_villager_acts_when_a_child_or_nobody_rang_it(self):
        for label, off, _ in self.RESULTS:
            with self.subTest(result=label):
                self.assertEqual(self._changed(self._ring(label, ringer=None), off), [], "stock: nothing")
                self.assertEqual(self._changed(self._ring(label, ringer=None, chosen=1), off), [1])

    def test_a_chosen_villager_no_longer_valid_falls_back_to_the_games_choice(self):
        def died(r):
            r.g.proc.put32(r.g.village.record(4) + 0x52C, 0)

        def gone(r):
            r.g.proc.write(r.g.village.record(4) + 0x30, b"\0")

        def someone_else(r):                                      # the record now holds another villager
            r.g.village.put(4, sex="f", years=30, name="Newcomer", health=95)

        def a_child_again(r):
            r.g.proc.put32(r.g.village.record(4) + 0x530, 0x118)

        def a_totem(r):
            r.g.proc.write(r.g.village.record(4) + 0x558, b"\1")

        for spoil in (died, gone, someone_else, a_child_again, a_totem):
            for label, off, want in self.RESULTS:
                with self.subTest(case=spoil.__name__, result=label):
                    r = self._ring(label, chosen=4, spoil=spoil)
                    self.assertIn(3, self._changed(r, off))
                    self.assertEqual(r.g.village.i32(3, off), want(95), "the game's own ringer")
                    self.assertEqual(r.gong()[2], 1, "the miss is recorded")

    YOUTH = (("Takes youth", 6, 0x3E9), ("Grants youth", 15, 0x64))

    def _ages(self, r):
        return {i: (r.g.village.i32(i, 0x530), r.g.village.i32(i, 0x534)) for i in (0, 1, 2, 3, 4, 5, 6, 15)}

    def _youth_writes(self, r, before):
        after = self._ages(r)
        return {i: after[i] for i in after if after[i] != before[i]}

    def test_the_youth_results_write_the_chosen_villager(self):
        """'Takes youth' / 'Grants youth' test that a ringer exists, then the
        game's own stores write the age (+0x530) and its processed copy
        (+0x534) of the fixed record 6 / 15 (stock).  A chosen villager gets
        them instead; Random is records 6 and 15."""
        for label, record, value in self.YOUTH:
            for chosen, ringer in ((4, 3), (1, None), (None, 3)):
                with self.subTest(result=label, chosen=chosen, ringer=ringer):
                    r = _Ring(ringer=ringer)
                    before = self._ages(r)
                    choices = {"result": _option(label)}
                    if chosen is not None:
                        choices["ringer"] = chosen
                    r.arm(choices)
                    r.ring()
                    target = record if chosen is None else chosen
                    self.assertEqual(self._youth_writes(r, before), {target: (value, value)})
                    self.assertEqual(r.gong()[2], 0)

    def test_the_youth_results_fall_back_to_the_games_records(self):
        def died(r):
            r.g.proc.put32(r.g.village.record(4) + 0x52C, 0)

        def a_totem(r):
            r.g.proc.write(r.g.village.record(4) + 0x558, b"\1")

        def carrying_a_baby(r):
            r.g.proc.put32(r.g.village.record(4) + 0x540, 1)

        def someone_else(r):
            r.g.village.put(4, sex="f", years=30, name="Newcomer", health=95)

        for spoil in (died, a_totem, carrying_a_baby, someone_else):
            for label, record, value in self.YOUTH:
                with self.subTest(case=spoil.__name__, result=label):
                    r = _Ring()
                    r.arm({"result": _option(label), "ringer": 4})
                    spoil(r)
                    before = self._ages(r)
                    r.ring()
                    self.assertEqual(self._youth_writes(r, before), {record: (value, value)})
                    self.assertEqual(r.gong()[2], 1, "the miss is recorded")

    def test_every_mode(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                r = self._ring("Takes life", chosen=2, mode=mode)
                self.assertEqual(self._changed(r, 0x52C), [2])
                r = _Ring(mode=mode)
                r.arm({"result": _option("Grants vision")})
                self.assertEqual(r.ring(), [(0x44E8CF, 0)])
                self.assertEqual(r.tiers(), 0)

    def test_who_falls_sick_falls_back_when_every_chosen_villager_is_gone(self):
        for spoiled in (False, True):
            with self.subTest(spoiled=spoiled):
                r = _Ring()
                r.arm({"result": _option("may fall sick (15%"), "sick_c": CHOOSE}, who={"sick_c": [4]})
                if spoiled:
                    r.g.proc.put32(r.g.village.record(4) + 0x52C, 0)
                r.g.rand_calls.clear()
                r.ring()
                sick = [r.g.village.i32(i, 0x53C) for i in range(6)]
                if spoiled:
                    self.assertEqual(r.g.rand_calls.count(100), 5, "the game's own roll for each living villager")
                    self.assertEqual(r.gong()[2], 1)
                else:
                    self.assertEqual(r.g.rand_calls.count(100), 0, "every roll answered")
                    self.assertEqual(sick, [0, 0, 0, 0, 1, 0])
                    self.assertEqual(r.gong()[2], 0)


@emulated
class GongPurchaseTests(unittest.TestCase):
    """The owner (2026-10-20): buying the pick makes the Gong ready to ring at
    once -- the game's own "ready" (village +0x2EAC8 = 1, as its restoration
    writes it) -- only when the Gong is whole; otherwise nothing is written or
    spent.  A ring afterwards rests the Gong as the game does."""

    def setUp(self):
        if not have_stock("vv2"):
            self.skipTest("stock executables not present")

    def test_buying_makes_a_resting_gong_ready_and_the_ring_rests_it_again(self):
        r = _Ring()
        r.g.proc.put32(r.w + 0x2EAC8, GONG_NOW + 40000)          # rung a few hours ago
        r.g.proc.write(SCRATCH + 0x5000, struct.pack("<i", _option("Grants luck")))
        self.assertEqual(r.g.proc.export("VvfpStoryProbeGongBuy", SCRATCH + 0x5000, 1), 1)
        self.assertEqual(r.rest(), 1)
        self.assertEqual(r.gong()[0], ARMED)
        self.assertEqual(r.strike(), [(0x44EBE5, 1)], "the ring is not refused, and gives the pick")
        self.assertEqual(r.rest(), GONG_NOW + 86400, "the game's own rest after the ring")
        self.assertEqual(r.gong()[0], IDLE)
        r.strike(until=0x4642E9)                                   # straight away again: resting, no use
        self.assertEqual(r.hit, [])

    def test_a_ready_gong_is_left_as_it_is(self):
        r = _Ring()
        r.g.proc.put32(r.w + 0x2EAC8, GONG_NOW - 5)
        r.g.proc.write(SCRATCH + 0x5000, struct.pack("<i", 0))
        self.assertEqual(r.g.proc.export("VvfpStoryProbeGongBuy", SCRATCH + 0x5000, 1), 1)
        self.assertEqual(r.rest(), GONG_NOW - 5)

    def test_no_whole_gong_writes_nothing(self):
        r = _Ring()
        r.g.proc.write(r.w + 0x2E7F0, b"\0")
        r.g.proc.put32(r.w + 0x2EAC8, GONG_NOW + 40000)
        before = r.g.proc.read(r.w, 0x31000)
        r.g.proc.write(SCRATCH + 0x5000, struct.pack("<i", 0))
        self.assertEqual(r.g.proc.export("VvfpStoryProbeGongBuy", SCRATCH + 0x5000, 1), 0)
        self.assertEqual(r.g.proc.read(r.w, 0x31000), before)
        self.assertEqual(r.gong()[0], IDLE)

    def test_the_purchase_is_refused_and_nothing_charged_without_a_whole_gong(self):
        proc = Process(render("vv2", "collection_progression"), TEST_DLL)
        proc.export("VvfpStoryCharge", 2)
        self.assertEqual(proc.export("VvfpStoryInstall", 2), 1)
        village = Village(proc, "vv2")
        village.put(0, sex="f", years=20, name="V0")
        proc.put32(village.world + 0x2EADC, 100000)
        self.assertEqual(proc.export("VvfpStoryEventPrice", 2), 30000)
        self.assertEqual(proc.export("VvfpStoryPickGongOutcome", 2, 0), 0)
        self.assertEqual(proc.u32(village.world + 0x2EADC), 100000, "nothing spent")
        self.assertIn("not whole", proc.messages[-1])
        self.assertNotIn("DialogBoxParamA", proc.api_calls, "the picker is not opened")


@emulated
class BirthGateTests(unittest.TestCase):
    """The owner (2026-10-20): every outcome, not only after a stock unlock.
    Twins and triplets the game rolls only once the village has mastered them
    -- The Lost Children: [world+0x2EA8C] == 3 in the conception routine
    0x44B980 (the Gong's 'Grants life' and the poet's note); The Tree of
    Life: Parenting mastery 0x41E1C0(1) == 3 (The Abandoned Infants) -- come
    when chosen, and the gate is as it was afterwards."""

    def _gong_life(self, babies, level):
        r = _Ring()
        p = r.g.proc
        p.put32(r.w + 0x2EA8C, level)
        p.stub(0x44B310, lambda q: (1, 0))                     # room in the village
        p.stub(0x4682BD, lambda q: (0, 0))                     # the father's name copy
        choices = {"result": _option("Grants life")}
        if babies is not None:
            _, c = _control("vv2", GONG_SLOT, "babies")
            choices["babies"] = [k for k, o in enumerate(c["options"]) if o["label"] == babies][0]
        r.arm(choices)
        r.ring()
        women = [0, 2, 4]                                      # V0, V2, V4 (18-49, not carrying)
        return [r.g.village.i32(i, 0x544) for i in women], p.u32(r.w + 0x2EA8C), r

    def test_the_gongs_twins_and_triplets_before_breeding_is_mastered(self):
        for level in (0, 1, 3):
            for babies, want in (("Twins", 2), ("Triplets", 3), ("One baby", 0), (None, 0)):
                with self.subTest(level=level, babies=babies):
                    litters, after, r = self._gong_life(babies, level)
                    if babies is None and level == 3:
                        want = 0                               # the stub's 63 of 100: no twins (stock)
                    self.assertEqual(litters, [want] * 3)
                    self.assertEqual(after, level, "the breeding level is put back")
                    if babies is None and level != 3:
                        self.assertNotIn(100, r.g.rand_calls[3:], "Random: no twins roll, as the game")

    def test_the_poets_note_twins_before_breeding_is_mastered(self):
        """The Lost Children's poet (slot 83, 'hide to catch the poet'): its
        conception call 0x422006, run as the event's resolve runs it."""
        ci, c = _control("vv2", 83, "litter")
        for level in (0, 3):
            for k, o in enumerate(c["options"]):
                with self.subTest(level=level, litter=o["label"]):
                    g = Game("vv2")
                    p = g.proc
                    p.put32(g.village.world + 0x2EA8C, level)
                    p.stub(0x44B310, lambda q: (1, 0))
                    p.stub(0x4682BD, lambda q: (0, 0))
                    g.arm(83, {ci: k})
                    g.force(DELIVERED, 1, in_apply=1)
                    self.assertGreaterEqual(g.scope(0x422006, 0), 0)
                    for n, value in enumerate([2, 7, 0, 0, 0, 0, 0]):   # mother V2, then the father's details
                        p.put32(STACK + 4 * n, value)
                    p.set_reg("ecx", g.village.base)
                    p.set_reg("esp", STACK)
                    p.run(0x422006, 0x42200B)
                    want = {"One baby": 0, "Twins": 2, "Triplets": 3}[o["label"]]
                    self.assertEqual(g.village.i32(2, 0x544), want)
                    self.assertEqual(p.u32(g.village.world + 0x2EA8C), level)
                    g.force(IDLE)

    def test_the_abandoned_infants_twins_before_parenting_is_mastered(self):
        """The Tree of Life's Abandoned Infants (slot 28): with Parenting not
        mastered (0x41E1C0 answers 0) every mother has one baby; with
        'Which mothers have more than one baby' at everyone they have twins
        (+0x1C50 = 2), or triplets (3) with the triplets setting too."""
        if not have_stock("vv4"):
            self.skipTest("stock executables not present")
        cases = ((None, None, 1), (EVERYONE, None, 2), (EVERYONE, EVERYONE, 3), (NOBODY, None, 1))
        for multiple, triplets, want in cases:
            with self.subTest(multiple=multiple, triplets=triplets):
                g = Game("vv4")
                stubs = {0x41E1C0: (0, 4), 0x468350: (1, 0), 0x412F90: (0, 8), 0x4724E0: (0, 0),
                         0x468C60: (0, 0)}
                for va, (value, pop) in stubs.items():
                    g.proc.stub(va, lambda q, value=value, pop=pop: (value, pop))
                choices = {}
                if multiple is not None:
                    choices[_control("vv4", 28, "multiple")[0]] = multiple
                if triplets is not None:
                    choices[_control("vv4", 28, "triplets")[0]] = triplets
                g.arm(28, choices)
                _ready(g, _control("vv4", 28, "multiple")[1])
                g.proc.call(0x467B00, [0xFFFFFFFF, 6, 1, 0xFFFFFFFF, 0, 0], ecx=0x50E568)
                mothers = [i for i in range(6) if g.village.i32(i, 0x1C4C) != 0]
                self.assertTrue(mothers, "the event's own conceptions ran")
                self.assertEqual({g.village.i32(i, 0x1C50) for i in mothers}, {want})


@emulated
class GongCoconutsFixTests(unittest.TestCase):
    """The patch "Gong of Wonder Coconuts Fix" (vv2_gong_of_wonder_coconuts_fix)
    turns the two coconut stores 0x44E9A9 / 0x44F18C from = 30 into += 30.  A
    picked coconut outcome runs those very instructions of the executable,
    so it follows the fix exactly when the fix is in the game."""

    def setUp(self):
        if not have_stock("vv2"):
            self.skipTest("stock executables not present")

    def test_both_coconut_outcomes_with_and_without_the_fix(self):
        stock = Game("vv2").proc.read(0x44E9A9, 10)
        for extra, want in (((), 30), (("vv2_gong_of_wonder_coconuts_fix",), 42)):
            for label in ("plant store = 800, coconut trees = 30", "Grants food: coconut trees set to 30"):
                with self.subTest(fix=bool(extra), outcome=label):
                    r = _Ring(extra=extra)
                    self.assertEqual(r.g.proc.read(0x44E9A9, 10) != stock, bool(extra), "the fix is in the executable")
                    r.g.proc.put32(r.w + 0x2EACC, 12)
                    r.arm({"result": _option(label)})
                    self.assertEqual(len(r.ring()), 1)
                    self.assertEqual(r.g.proc.u32(r.w + 0x2EACC), want)


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

    def test_every_gong_result_can_be_bought_before_the_first_ring(self):
        """The owner (2026-10-20): every outcome.  The results the game keeps
        for after a village's first ring (its tier lock, village +0x2E910 = 0)
        are offered and bought like the others."""
        g, n = self._open("vv2", gong=True)
        self.assertEqual(n, 1)
        self.assertEqual(g.proc.read(g.village.world + 0x2E910, 1), b"\0")
        ci, c = _control("vv2", GONG_SLOT, "result")
        self.assertEqual(len(c["options"]), 23)
        for k, o in enumerate(c["options"]):
            with self.subTest(option=o["label"]):
                self.assertNotIn("cond", o)
                self._set(g, 0, ci, k)
                self.assertEqual(self._text(g, 0, 2)[1], "")
                self.assertIn(o["label"].split(" (")[0], self._text(g, 0, 4 + ci)[1])

    def test_the_ringer_row_names_the_chosen_villager(self):
        g, _ = self._open("vv2", gong=True)
        ci, c = _control("vv2", GONG_SLOT, "ringer")
        self.assertEqual(self._text(g, 0, 4 + ci)[1], "The villager who rang it: Random (original game)")
        self._set(g, 0, ci, 4)
        self.assertEqual(self._text(g, 0, 4 + ci)[1], "The villager who rang it: V4")
        self.assertIn("The villager who rang it: V4", self._text(g, 0, 1)[1])
        self.assertEqual(self._text(g, 0, 2)[1], "")


@emulated
class FixVanillaBugsTests(unittest.TestCase):
    """The Secret City's "Fix Vanilla Bugs" moves the Royal Jelly's cure from
    the clear vial (choice 0) to the dark vial (choice 1).  The Healing setting
    is tied to no button: its roll is reached only in the curing branch, so it
    answers whichever vial cures in the running executable."""

    def test_vv3_royal_jelly_healing_answers_whichever_vial_cures(self):
        if not have_stock("vv3"):
            self.skipTest("no stock VV3")
        g = Game("vv3")
        cs = controls_of("vv3", 45)
        ci, c = next((i, c) for i, c in enumerate(cs) if c["id"] == "healing")
        self.assertIsNone(c["branch"])
        self.assertEqual(c["site"], 0x418109)
        for branch in (0, 1):
            with self.subTest(branch=branch):
                g.arm(45, {ci: 9})
                g.force(DELIVERED, branch, in_apply=1)
                self.assertEqual(g.forced_roll(0x418109, 15), (9, True))
                g.force(IDLE)


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
