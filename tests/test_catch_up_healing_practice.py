"""Fix Vanilla Bugs (A New Home, The Lost Children): healers learn Healing in
catch-up as they do in live play.

Live play completes a practice step (step 6) with one call of the game's
practice routine for every skill (A New Home 0x448846 -> 0x43D440, The Lost
Children 0x464F15 -> 0x44E170).  The catch-up step runner (0x446C70 /
0x464680) instead turns a Healing practice step into a cure roll,
rand(1500) < Healing: when it passes, and the first-sickness hint is clear, it
practises once for every living villager it checks for a patient; it never
makes the plain call for Healing.  So a healer -- and a healer studying a
plant, whose study queues exactly this step -- learned almost no Healing
while the game was closed, and nothing at Healing 0.

The fix makes the plain call whenever the cure roll's loop has not practised
(the roll failed, or the hint is pending) and never adds a second one after
it has (a cure, or the loop's end).

Everything here is EMULATED FROM THE RUNNER'S ENTRY in the executable the
patcher renders, with the game's REAL practice routine; only the leaf
routines are scripted (the RNG, the queue clear / advance, the "shaking head"
queue, the speech queue, the trait tests, the village count), and each
stand-in pops exactly what its real routine pops (checked below).
"""
from __future__ import annotations

import random
import struct
import unittest

from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ECX, UC_X86_REG_ESP

from test_builders_decision_roll import (
    HALT, INDEX, STATE, STOCK, STOCK_ABSENT, STOCK_PRESENT, VILLAGE, Leaf, Machine, rendered,
)

ROW = "fix_vanilla_bugs"
MODES = ("stock", "collection_progression", "immediate_fixed")

# Per game: the runner, the practice routine, live play's step-6 practice
# call, the record layout the runner and the practice routine read, and the
# leaf routines with the bytes each pops.
G = {
    "vv1": dict(
        runner=0x446C70, practice=0x43D440, live_call=0x448846, stride=0x3D8, healing=5,
        skill_field=0x3C8, step=0x44, done=0x50, skill=0x58, exists=0x28, selected=0x29,
        sick=0x354, age=0x348, ids=(0x368, 0x36C), state=0x3E010, hint=0x149, force_cure=0xABEC,
        cured=0x9E2C, rand=0x402F10, advance=0x445C50, count=0x41CF90,
        leaves={0x439470: (1, "clear queue"), 0x43A040: (1, "shake head"), 0x43A130: (1, "say"),
                0x41CF90: (0, "count"), 0x445C50: (1, "advance")},
        # practice skill numbers -> record field (Parenting, Building, Farming,
        # Healing, Research are +0x3BC..+0x3CC)
        fields={1: 0x3C4, 2: 0x3BC, 3: 0x3CC, 4: 0x3C0, 5: 0x3C8},
    ),
    "vv2": dict(
        runner=0x464680, practice=0x44E170, live_call=0x464F15, stride=0xE48C, healing=3,
        skill_field=0x7F0, step=0x4C, done=0x58, skill=0x60, exists=0x30, selected=0x31,
        sick=0x53C, age=None, ids=None, state=0xE574D4, hint=0x1D4, force_cure=0x30380,
        cured=0x2E508, rand=0x4031A0, advance=0x449380, count=0x425860,
        leaves={0x4492A0: (1, "clear queue"), 0x44B1B0: (1, "shake head"), 0x44B2A0: (1, "say"),
                0x4454E0: (2, "trait"), 0x445510: (2, "trait"), 0x425860: (0, "count"),
                0x449380: (1, "advance")},
        fields={1: 0x7EC, 2: 0x7E4, 3: 0x7F0, 4: 0x7F4, 5: 0x7E8},
    ),
}
GAMES = tuple(G)
PRACTICE = "practice"

# The rows Fix Vanilla Bugs adds, as (file offset, stock bytes, patched bytes):
# the hint test leaves the loop for the join; the loop's end and a cure finish
# the step past the join; the join no longer skips Healing.
HEALING_PRACTICE_FIXES = {
    "vv1": (
        (0x46D0A, "7550", "757E"),
        (0x46D6B, "EB1D", "EB37"),
        (0x46D6D, "69DBD8030000C7843354030000000000008B8610E00300FF802C9E0000",
         "69DBD8030000C707000000008B8610E00300FF802C9E0000EB1D0F1F00"),
        (0x46D92, "83F805740D", "0F1F440000"),
    ),
    "vv2": (
        (0x64718, "7538", "7566"),
        (0x64761, "EB1D", "EB37"),
        (0x64763, "69DB8CE40000C784333C050000000000008B86D474E500FF8008E50200",
         "69DB8CE40000C74500000000008B86D474E500FF8008E50200EB1C6690"),
        (0x64788, "83F803740D", "0F1F440000"),
    ),
}


def healing_practice_fixes(game: str) -> tuple:
    return tuple((off, bytes.fromhex(b), bytes.fromhex(a)) for off, b, a in HEALING_PRACTICE_FIXES[game])


class Draws:
    """The game's rand(n), one stream per n per step: the cure roll (1500) and
    the practice rolls (100) come from separate streams, so a patched step's
    plain practice draws exactly what live play's call draws for that step."""

    def __init__(self, step: int = 0, cure: int | None = None):
        self.step, self.cure = step, cure
        self._streams: dict[int, random.Random] = {}
        self.cure_rolls: list[int] = []

    def reset(self, step: int, cure: int | None = None) -> None:
        self.step, self.cure, self._streams, self.cure_rolls = step, cure, {}, []

    def __call__(self, m, args, ecx, ret):
        n = max(1, args[0])
        if n == 1500 and self.cure is not None:
            value = self.cure
        else:
            value = self._streams.setdefault(n, random.Random(self.step * 7919 + n)).randrange(n)
        if n == 1500:
            self.cure_rolls.append(value)
        return value


def _exe(game: str, mode: str, patched: bool) -> bytes:
    if not patched:
        return STOCK[game].read_bytes()
    if mode == "stock":
        return rendered(game, (f"{game}_{ROW}",))
    import vv_fun_patcher as vfp
    build = next(b for b in vfp.load_builds() if b.id == game)
    return bytes(vfp.render_patched_bytes(STOCK[game], build, mode, [f"{game}_{ROW}"])[0])


_EXES: dict[tuple, bytes] = {}


def exe(game: str, mode: str = "stock", patched: bool = True) -> bytes:
    key = (game, mode, patched)
    if key not in _EXES:
        _EXES[key] = _exe(game, mode, patched)
    return _EXES[key]


class Village:
    """One emulated game process, reused for every scenario (each machine maps
    some 20 MB; one per executable keeps the run small)."""

    def __init__(self, game: str, image: bytes):
        self.game, self.g = game, G[game]
        g = self.g
        self.draws = Draws()
        self.m = m = Machine(game, image, modules=())
        m.real.add(g["practice"])
        m.leaves[g["rand"]] = Leaf(1, self.draws, cdecl=True, name="rand")
        for va, (nargs, name) in g["leaves"].items():
            m.leaves[va] = Leaf(nargs, lambda m, a, c, r: 0, name=name)
        m.leaves[g["advance"]] = Leaf(1, self._advance, name="advance")

        # The practice routine runs for real; record each call on entry.
        def note(mu, address, size, user):
            _, index, which = struct.unpack("<3I", mu.mem_read(mu.reg_read(UC_X86_REG_ESP), 12))
            self.m.calls.append((PRACTICE, (index, which), 0))
        m.mu.hook_add(UC_HOOK_CODE, note, begin=g["practice"], end=g["practice"])
        m.w32(VILLAGE + g["state"], STATE)

    def configure(self, *, healing=0, skill=None, others=9, sick=None, hint=0) -> "Village":
        """The healer at INDEX with a practice step queued, `others` more
        living villagers, optionally one sick; the first-sickness hint."""
        g, m = self.g, self.m
        for j in range(256):
            rec = self.rec(j)
            m.w8(rec + g["exists"], 0)
            m.w8(rec + g["selected"], 0)
            m.w32(rec + g["sick"], 0)
        m.w8(STATE + g["hint"], hint)
        m.w8(STATE + g["force_cure"], 1)          # a patient found is cured
        m.w32(STATE + g["cured"], 0)
        for j in [INDEX] + [j for j in range(256) if j != INDEX][:others]:
            rec = self.rec(j)
            m.w8(rec + g["exists"], 1)
            if g["age"] is not None:
                m.w32(rec + g["age"], 0x200)
                m.w32(rec + g["ids"][0], 1000 + j)
                m.w32(rec + g["ids"][1], 2000 + j)
        if sick is not None:
            m.w32(self.rec(sick) + g["sick"], 1)
        self.healing = healing
        self.which = g["healing"] if skill is None else skill
        return self

    def rec(self, j: int) -> int:
        return VILLAGE + j * self.g["stride"]

    def _advance(self, m, args, ecx, ret):
        m.w32(self.rec(args[0]) + self.g["step"], 0)     # the queue is empty after this step
        return 0

    def set_skill(self, value: int) -> None:
        self.m.w32(self.rec(INDEX) + self.g["fields"][self.which], value)

    def skill_value(self) -> int:
        return self.m.u32(self.rec(INDEX) + self.g["fields"][self.which])

    def step(self, step_no: int = 0, cure: int | None = None) -> int:
        """One catch-up practice step; returns the skill's change."""
        g, m = self.g, self.m
        self.draws.reset(step_no, cure)
        rec = self.rec(INDEX)
        m.w32(rec + g["step"], 6)
        m.w32(rec + g["skill"], self.which)
        m.w32(rec + g["done"], 0)
        self.set_skill(self.healing)
        m.calls = []
        m.run(g["runner"], HALT, {UC_X86_REG_ECX: VILLAGE}, stack=(HALT, INDEX))
        return self.skill_value() - self.healing

    def live(self, step_no: int = 0) -> int:
        """Live play's step-6 completion: one practice call."""
        g, m = self.g, self.m
        self.draws.reset(step_no)
        self.set_skill(self.healing)
        m.calls = []
        m.run(g["practice"], HALT, {UC_X86_REG_ECX: VILLAGE}, stack=(HALT, INDEX, self.which))
        return self.skill_value() - self.healing

    def practices(self) -> list[tuple]:
        return [c[1] for c in self.m.calls if c[0] == PRACTICE]

    def effects(self) -> list[tuple]:
        return [c[:2] for c in self.m.calls]

    def cured(self) -> int:
        return self.m.u32(STATE + self.g["cured"])

    def sick(self, j: int) -> int:
        return self.m.u32(self.rec(j) + self.g["sick"])


_VILLAGES: dict[tuple, Village] = {}


def village(game: str, kind: str = "patched", mode: str = "stock", **kw) -> Village:
    """kind: "patched" (Fix Vanilla Bugs), "stock", or "live" (the stock
    executable, used only for live play's one practice call)."""
    key = (game, kind, mode)
    if key not in _VILLAGES:
        _VILLAGES[key] = Village(game, exe(game, mode, patched=kind == "patched"))
    return _VILLAGES[key].configure(**kw)


def pair(game: str, mode: str = "stock", **kw) -> tuple[Village, Village]:
    return village(game, "stock", mode, **kw), village(game, "patched", mode, **kw)


# Where each routine whose pops are checked ends: its own jump table follows
# the practice routine, so the scan stops there.
_ENDS = {("vv1", 0x43D440): 0x43DA10, ("vv2", 0x44E170): 0x44E88C}


def _rets(game: str, va: int) -> set[int]:
    """The `ret` immediates of the routine at va (to its first padding)."""
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    import pefile
    data = STOCK[game].read_bytes()
    pe = pefile.PE(data=data, fast_load=True)
    off = pe.get_offset_from_rva(va - 0x400000)
    end = _ENDS.get((game, va), va + 0x3000)
    out: set[int] = set()
    for ins in Cs(CS_ARCH_X86, CS_MODE_32).disasm(data[off:off + (end - va)], va):
        if ins.mnemonic == "ret":
            out.add(int(ins.op_str, 0) if ins.op_str else 0)
        elif ins.mnemonic == "int3" or (ins.mnemonic == "nop" and ins.size == 1 and out):
            break
    return out


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class StandIns(unittest.TestCase):
    """A stand-in that pops the wrong number of bytes corrupts the caller's
    stack (a recent crash came from exactly that): every one here pops what
    the real routine pops."""

    def test_each_stand_in_pops_what_the_real_routine_pops(self):
        for game, g in G.items():
            for va, (nargs, name) in g["leaves"].items():
                with self.subTest(game=game, routine=hex(va), name=name):
                    self.assertEqual(_rets(game, va), {4 * nargs})
            with self.subTest(game=game, routine="rand"):
                self.assertEqual(_rets(game, g["rand"]), {0})        # cdecl
            with self.subTest(game=game, routine="practice"):
                self.assertEqual(_rets(game, g["practice"]), {8})    # (index, skill)
            with self.subTest(game=game, routine="runner"):
                self.assertEqual(_rets(game, g["runner"]), {4})      # (index)

    def test_live_play_calls_the_practice_routine(self):
        """Live play's step-6 completion is a call of the practice routine."""
        from capstone import CS_ARCH_X86, CS_MODE_32, Cs
        import pefile
        for game, g in G.items():
            with self.subTest(game=game):
                data = STOCK[game].read_bytes()
                pe = pefile.PE(data=data, fast_load=True)
                off = pe.get_offset_from_rva(g["live_call"] - 0x400000)
                ins = next(Cs(CS_ARCH_X86, CS_MODE_32).disasm(data[off:off + 5], g["live_call"]))
                self.assertEqual(ins.mnemonic, "call")
                self.assertEqual(int(ins.op_str, 0), g["practice"])


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class CatchUpHealingPractice(unittest.TestCase):
    """Stock vs patched, the real runner and the real practice routine."""

    def test_failed_cure_roll_practises_once_as_live_play_does(self):
        for game in GAMES:
            for healing in (0, 10, 30, 50, 99):
                with self.subTest(game=game, healing=healing):
                    stock, patched = pair(game, healing=healing)
                    live = village(game, "live", healing=healing)
                    for n in range(12):
                        # rand(1500) equal to the Healing value fails (it needs <)
                        self.assertEqual(stock.step(n, cure=healing), 0)
                        self.assertEqual(stock.practices(), [])
                        gain = patched.step(n, cure=healing)
                        self.assertEqual(patched.practices(), [(INDEX, G[game]["healing"])])
                        self.assertEqual(gain, live.live(n))
                        self.assertEqual(patched.cured(), 0)

    def test_healing_zero_learns(self):
        """At Healing 0 the cure roll can never pass: stock catch-up never
        practises Healing at all; patched, it does on every step."""
        for game in GAMES:
            with self.subTest(game=game):
                stock, patched = pair(game, healing=0)
                self.assertEqual(sum(stock.step(n) for n in range(40)), 0)
                self.assertGreater(sum(patched.step(n) for n in range(40)), 0)

    def test_passed_cure_roll_is_the_stock_step(self):
        """The cure roll passes: the loop practises once per villager it
        checks; nothing is added (no second practice), with or without a
        patient."""
        for game in GAMES:
            for sick in (None, 3):
                with self.subTest(game=game, sick=sick):
                    stock, patched = pair(game, healing=40, sick=sick)
                    for n in range(6):
                        a = stock.step(n, cure=0)
                        b = patched.step(n, cure=0)
                        self.assertEqual(stock.effects(), patched.effects())
                        self.assertEqual(a, b)
                        self.assertEqual(stock.cured(), patched.cured())
                        if n == 0:
                            practised = len(patched.practices())
                            self.assertGreater(practised, 1 if sick is None else 0)
                    if sick is not None:
                        self.assertEqual(patched.sick(sick), 0)
                        self.assertEqual(patched.cured(), 1)

    def test_pending_hint_practises_once(self):
        """Before anyone has been sick the hint flag is set and the cure loop
        practises nobody: stock nothing, patched the plain practice."""
        for game in GAMES:
            with self.subTest(game=game):
                stock, patched = pair(game, healing=40, hint=1)
                live = village(game, "live", healing=40)
                for n in range(8):
                    self.assertEqual(stock.step(n, cure=0), 0)
                    self.assertEqual(stock.practices(), [])
                    gain = patched.step(n, cure=0)
                    self.assertEqual(patched.practices(), [(INDEX, G[game]["healing"])])
                    self.assertEqual(gain, live.live(n))
                    self.assertEqual(patched.cured(), 0)

    def test_other_skills_are_the_stock_step(self):
        for game in GAMES:
            for which in (1, 2, 3, 4, 5):
                if which == G[game]["healing"]:
                    continue
                with self.subTest(game=game, skill=which):
                    stock, patched = pair(game, healing=20, skill=which)
                    for n in range(6):
                        self.assertEqual(stock.step(n), patched.step(n))
                        self.assertEqual(stock.effects(), patched.effects())
                    # Parenting (2) is left out of plain practice in both, as before.
                    self.assertEqual(patched.practices(), [] if which == 2 else [(INDEX, which)])

    def test_every_population_mode(self):
        for mode in MODES:
            for game in GAMES:
                with self.subTest(mode=mode, game=game):
                    stock, patched = pair(game, mode, healing=0)
                    live = village(game, "live", healing=0)
                    for n in range(6):
                        self.assertEqual(stock.step(n, cure=0), 0)
                        self.assertEqual(patched.step(n, cure=0), live.live(n))
                        self.assertEqual(patched.practices(), [(INDEX, G[game]["healing"])])
                    stock, patched = pair(game, mode, healing=40, hint=1)
                    self.assertEqual(stock.step(0, cure=0), 0)
                    patched.step(0, cure=0)
                    self.assertEqual(patched.practices(), [(INDEX, G[game]["healing"])])
                    stock, patched = pair(game, mode, healing=40, sick=3)
                    for n in range(6):
                        self.assertEqual(stock.step(n, cure=0), patched.step(n, cure=0))
                        self.assertEqual(stock.effects(), patched.effects())
                    self.assertEqual((stock.cured(), patched.cured()), (1, 1))


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class GainPerStep(unittest.TestCase):
    """The average Healing gained per catch-up practice step (10 living
    villagers, nobody sick, hint clear), stock vs patched vs live play's one
    call: patched is live play's except on the steps whose cure roll passes,
    where it is the stock step."""

    N = 300

    def test_patched_matches_live_play(self):
        for game in GAMES:
            for healing in (0, 20, 45, 80):
                with self.subTest(game=game, healing=healing):
                    stock, patched = pair(game, healing=healing)
                    live = village(game, "live", healing=healing)
                    totals = {"stock": 0, "patched": 0, "live": 0}
                    for n in range(self.N):
                        s = stock.step(n)
                        passed = stock.draws.cure_rolls[0] < healing
                        p = patched.step(n)
                        lv = live.live(n)
                        self.assertEqual(p, s if passed else lv)
                        totals["stock"] += s
                        totals["patched"] += p
                        totals["live"] += lv
                    print(f"catch-up Healing gain per step {game} at {healing}: "
                          + ", ".join(f"{k} {v / self.N:.3f}" for k, v in totals.items()))


if __name__ == "__main__":
    unittest.main()

