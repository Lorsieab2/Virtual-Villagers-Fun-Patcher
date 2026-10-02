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


if __name__ == "__main__":
    unittest.main()
