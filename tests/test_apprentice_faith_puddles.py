"""Children's Graves Say Apprentice (A New Home, The Lost Children, The Secret City, New Believers), Faith Loss is
Doubled/Gains Halved and Puddle Play Moves to the Lake Shore (New Believers), and New Believers' Fix Vanilla Bugs
lake-bed spots.  The traces and the rules are in scripts/build_apprentice_faith_puddles_features.py.

Each patch is run, stock and patched, in unicorn from the executable the patcher renders:
  * the grave dialog's rank pick, for every age edge, best skill edge and job (none included): the string id it
    fetches and the stack and buffer it hands the copy call;
  * New Believers' Faith drift 0x468040, every roll's threshold found by forcing the game's rand(100) at that roll,
    and Faith Loss's 3-in-10 rule for a fall to 0 made of a food or sickness loss;
  * New Believers' Faith setter 0x467F90 turning a believer Heathen, stock and with New Heathens Get a Heathen's
    Faith;
  * the puddle play's choosers and walk, and the area-point picker, on the game's real map (tests/
    farmers_emulation_vv5.py; skipped without research/game-data/vv5).
Tests that need the stock executables skip when they are absent.
"""
from __future__ import annotations

import importlib.util
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402
from vv_fun_patcher_gui import default_fun_patch_selection  # noqa: E402

try:
    import pefile
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
    from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX,
                                   UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP)
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

_spec = importlib.util.spec_from_file_location("build_apprentice_faith_puddles_features",
                                               ROOT / "scripts" / "build_apprentice_faith_puddles_features.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

STOCK_DIR = ROOT / "research" / "stock-executables"
APPRENTICE = {g: gen.apprentice_id(g) for g in (1, 2, 3, 5)}
FAITH, PUDDLES, NEW_HEATHEN = gen.FAITH_ID, gen.PUDDLES_ID, gen.NEW_HEATHEN_ID
NEW_IDS = tuple(APPRENTICE.values()) + (FAITH, PUDDLES, NEW_HEATHEN)


def build(game: int):
    return next(b for b in patcher.load_builds() if b.id == f"vv{game}")


def stock_path(game: int) -> Path:
    path = STOCK_DIR / build(game).input_name
    if not path.is_file():
        raise unittest.SkipTest(f"stock vv{game} exe not present in this checkout")
    return path


_RENDERS: dict = {}


def rendered(game: int, ids: tuple) -> bytes:
    key = (game, ids)
    if key not in _RENDERS:
        path = stock_path(game)
        _RENDERS[key] = path.read_bytes() if not ids else bytes(
            patcher.render_patched_bytes(path, build(game), patcher.DEFAULT_PATCH_MODE, list(ids))[0])
    return _RENDERS[key]


class Machine:
    """An executable's image in unicorn, with a stack, a scratch page and a return trap."""
    STACK, SCRATCH, RET = 0x20000000, 0x30000000, 0x2FFF0000

    def __init__(self, exe: bytes):
        pe = pefile.PE(data=exe, fast_load=True)
        base = pe.OPTIONAL_HEADER.ImageBase
        size = (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFFF) & ~0xFFFF
        self.uc = Uc(UC_ARCH_X86, UC_MODE_32)
        self.uc.mem_map(base, size)
        self.uc.mem_write(base, pe.get_memory_mapped_image()[:size])
        self.uc.mem_map(self.STACK, 0x100000)
        self.uc.mem_map(self.SCRATCH, 0x100000)
        self.uc.mem_map(self.RET & ~0xFFFF, 0x10000)

    def w32(self, at: int, value: int) -> None:
        self.uc.mem_write(at, struct.pack("<i", value))

    def r32(self, at: int) -> int:
        return struct.unpack("<I", bytes(self.uc.mem_read(at, 4)))[0]

    def stub(self, at: int, fn, pop: int) -> None:
        """Replace the routine at `at`: fn(machine) gives eax; return popping `pop` argument bytes."""
        def hook(uc, _a, _s, _d):
            uc.reg_write(UC_X86_REG_EAX, fn(self) & 0xFFFFFFFF)
            sp = uc.reg_read(UC_X86_REG_ESP)
            uc.reg_write(UC_X86_REG_EIP, self.r32(sp))
            uc.reg_write(UC_X86_REG_ESP, sp + 4 + pop)
        self.uc.hook_add(UC_HOOK_CODE, hook, begin=at, end=at)


# ---------------------------------------------------------------------------
# Children's Graves Say Apprentice
# ---------------------------------------------------------------------------

# game: (start of the job test, register holding the dialog, its slot / owner fields, grave stride, skill / job /
#        age offsets in the grave from the owner, the no-job value)
GRAVE_RUN = {
    1: dict(start=0x436501, this=UC_X86_REG_EBX, master=90),
    2: dict(start=0x444554, this=UC_X86_REG_EBP, master=88),
    3: dict(start=0x41E931, this=None, master=88),
    5: dict(start=0x41C673, this=None, master=88),
}
AGES = (40, 279, 280, 281, 1300)
VALUES = (0, 19, 20, 49, 50, 87, 88, 89, 90, 100)


def expected_id(game: int, age: int, job_named: bool, value: int, apprentice: bool) -> int:
    untrained, app, trainee, master = (gen.GRAVES[game][3], gen.GRAVES[game][4], gen.GRAVES[game][5],
                                       gen.GRAVES[game][6])
    if not job_named or value < 20:
        return untrained
    if apprentice and age < 280:
        return app
    return trainee if value < 50 else trainee + 1 if value < master else trainee + 2


def run_rank(exe: bytes, game: int, age: int, job: int, value: int) -> tuple[int, tuple]:
    """Run the grave dialog from its job test to the copy call: the string id fetched, and (esp, [esp], [esp+4])
    at the copy call."""
    m = Machine(exe)
    lo, hi = gen.GRAVES[game][0], gen.GRAVES[game][1]
    string_fn = gen.GRAVES[game][10]
    fetched = []
    m.stub(string_fn, lambda mm: (fetched.append(mm.r32(mm.uc.reg_read(UC_X86_REG_ESP) + 4)), 0x31000000)[1], 4)
    m.uc.mem_map(0x31000000, 0x1000)
    S = m.SCRATCH
    sp = m.STACK + 0x80000
    dialog, table = S, S + 0x800
    if game == 1:
        manager = S + 0x1000
        m.w32(dialog + 0x60, 0)
        m.w32(dialog + 0x74, manager)
        m.w32(dialog + 0x7C, table)
        m.w32(manager + 0xA338, value)
        m.w32(manager + 0xA33C, job)
        m.w32(manager + 0xA340, age)
        m.uc.reg_write(UC_X86_REG_EBX, dialog)
    elif game == 2:
        world = S + 0x1000
        m.w32(dialog + 0x60, 0)
        m.w32(dialog + 0x78, world)
        m.w32(dialog + 0x80, table)
        m.w32(world + 0x2EB78, value)
        m.w32(world + 0x2EB7C, job)
        m.w32(world + 0x2EB80, age)
        m.uc.reg_write(UC_X86_REG_EBP, dialog)
    else:
        entry, stone = S + 0x1000, S + 0x2000
        m.w32(dialog + 0x5C, table)
        m.w32(entry + 0x1C, age)
        if game == 3:
            m.w32(dialog + 0x4C, stone)
            m.w32(stone + 4, value)
            m.w32(entry + 0x20, job)
            m.w32(sp + 0x14, entry)
        else:
            m.w32(entry + 0x28, job)
            m.w32(entry + 0x2C, value)
            m.w32(sp + 0x18, entry)
        m.uc.reg_write(UC_X86_REG_EBP, dialog)
    m.uc.reg_write(UC_X86_REG_ESP, sp)
    m.uc.emu_start(GRAVE_RUN[game]["start"], hi - 5, count=200)
    at = m.uc.reg_read(UC_X86_REG_ESP)
    assert m.uc.reg_read(UC_X86_REG_EIP) == hi - 5 and lo <= hi
    return fetched[-1], (at, m.r32(at), m.r32(at + 4))


@unittest.skipUnless(HAVE_EMULATOR, "unicorn/pefile not installed")
class ApprenticeGraves(unittest.TestCase):
    def test_the_manifests_are_the_generators(self):
        for game in (1, 2, 3, 5):
            stock_path(game)
            path = ROOT / "data" / f"vv{game}_apprentice_graves_feature.json"
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), gen.apprentice_feature(game), game)

    def test_the_rank_pick_stock_and_patched(self):
        """Every age edge, best skill edge and job (0 / -1 no job, each job): stock never says Apprentice;
        patched says it exactly for a child (under 280) with 20 or more, and hands the copy the same stack."""
        for game in (1, 2, 3, 5):
            stock, patched = rendered(game, ()), rendered(game, (APPRENTICE[game],))
            none_job = 0 if game in (1, 2) else -1
            jobs = [none_job] + ([1, 3, 5] if game in (1, 2) else [0, 2, 4] + ([5] if game == 5 else []))
            for age in AGES:
                for job in jobs:
                    for value in VALUES:
                        if value >= GRAVE_RUN[game]["master"] + 2:
                            continue
                        named = job != none_job
                        got_s, frame_s = run_rank(stock, game, age, job, value)
                        got_p, frame_p = run_rank(patched, game, age, job, value)
                        case = (game, age, job, value)
                        self.assertEqual(got_s, expected_id(game, age, named, value, False), case)
                        self.assertEqual(got_p, expected_id(game, age, named, value, True), case)
                        self.assertEqual(frame_s, frame_p, case)

    def test_the_string_is_the_games_apprentice(self):
        """The id is the game's own "Apprentice " (eSayApprentice in the later games), Untrained / Trainee its
        neighbours: read from the exe's built-in string table (VV3, VV5)."""
        for game, ident in ((3, 0x92), (5, 0xC6)):
            exe = stock_path(game).read_bytes()
            pe = pefile.PE(data=exe, fast_load=True)
            name = exe.index(b"eSayApprentice\t\x00")
            va = pe.get_rva_from_offset(name) + pe.OPTIONAL_HEADER.ImageBase
            row = exe.index(struct.pack("<I", va))
            self.assertEqual(struct.unpack_from("<I", exe, row - 4)[0], ident)
            text = struct.unpack_from("<I", exe, row + 4)[0]
            off = pe.get_offset_from_rva(text - pe.OPTIONAL_HEADER.ImageBase)
            self.assertEqual(exe[off:off + 12], b"Apprentice \x00")

    def test_on_by_default_and_needs_nothing(self):
        public = patcher.load_public_fun_patches()
        rows = {p.id: p for p in public}
        for game, pid in APPRENTICE.items():
            self.assertIn(pid, rows)
            self.assertTrue(default_fun_patch_selection(pid))
            self.assertEqual(patcher.patch_requirement_text(rows[pid], public), "Requires no other patch to be ticked.")
        self.assertNotIn("vv4_apprentice_graves", rows, "The Tree of Life has it in the stock game")

    def test_the_cause_of_death_companion_follows_the_row(self):
        """One rule a game: the companion's Deaths-log line and popup hook say Apprentice only when this row's
        bytes are in the exe (the bytes it checks are the generator's)."""
        src = (ROOT / "native" / "vvfp_cause_of_death" / "cod_vv12.inc").read_text(encoding="utf-8")
        for game, (va, n) in {1: (0x436516, 7), 2: (0x44456A, 7), 3: (0x41E946, 5), 5: (0x41C685, 5)}.items():
            lo, code = gen.GRAVES[game][0], gen.grave_block(game)[0]
            want = code[va - lo:va - lo + n]
            listed = ", ".join(f"0x{b:02X}" for b in want)
            self.assertIn("{ " + listed + " }", src, game)
            self.assertIn(f"cod_bytes_are(0x{va:X}u", src, game)
        later = (ROOT / "native" / "vvfp_cause_of_death" / "cod_vv345.inc").read_text(encoding="utf-8")
        self.assertIn("if (age < 0x118 && cod_apprentice_patched()) {", later)


# ---------------------------------------------------------------------------
# Faith Loss is Doubled/Gains Halved
# ---------------------------------------------------------------------------

DRIFT, APPLY = 0x468040, 0x468020
FOOD, PROJECT_DONE, STATUE_STAGE, TECH, BELIEVERS = 0x51D34C, 0x43AE80, 0x4271C0, 0x423600, 0x4713F0
# The rolls: (rand's return address, the condition that reaches it, +1 / -1).
ROLLS = {
    "food under 10": (0x468056, dict(food=5), -1),
    "food 10 to 250": (0x468076, dict(food=100), -1),
    "food 8000": (0x468096, dict(food=9000), +1),
    "sick": (0x4680B3, dict(sick=1), -1),
    "statue solved": (0x4680D5, dict(statue_done=1), +1),
    "statue stage 2": (0x4680F8, dict(stage=2), +1),
    "statue stage 1": (0x468107, dict(stage=1), +1),
    "spirituality 3": (0x468134, dict(spirit=3), +1),
    "spirituality 2": (0x468143, dict(spirit=2), +1),
    "spirituality 1": (0x468152, dict(spirit=1), +1),
    "11 believers": (0x468171, dict(believers=11), -1),
    "1 believer": (0x468171, dict(believers=1), -1),
    "50 believers": (0x468171, dict(believers=50), +1),
    "14 believers": (0x468171, dict(believers=14), +1),
}
STOCK_THRESHOLD = {"food under 10": 30, "food 10 to 250": 10, "food 8000": 20, "sick": 15, "statue solved": 30,
                   "statue stage 2": 20, "statue stage 1": 10, "spirituality 3": 30, "spirituality 2": 20,
                   "spirituality 1": 10, "11 believers": 1, "1 believer": 11, "50 believers": 10, "14 believers": 2}
PATCHED_THRESHOLD = {"food under 10": 60, "food 10 to 250": 20, "food 8000": 10, "sick": 30, "statue solved": 15,
                     "statue stage 2": 10, "statue stage 1": 5, "spirituality 3": 15, "spirituality 2": 10,
                     "spirituality 1": 5, "11 believers": 2, "1 believer": 22, "50 believers": 5, "14 believers": 1}


# The rule's rand(10) return address, in the rule cave (the rule without its companion).
STAY_ROLL = gen.FAITH_RULE_CAVE + gen.faith_rule_cave().index(b"\x6A\x0A\xE8") + 7
# New Heathens Get a Heathen's Faith's rand(30) return address, in its cave.
BLUE_ROLL = gen.NEW_HEATHEN_CAVE + gen.new_heathen_cave().index(b"\x6A\x1E\xE8") + 7


def drift(exe: bytes, *, faith=50, food=1000, sick=0, statue_done=0, stage=0, spirit=0, believers=12,
          forced: dict | None = None, default=99, registers: dict | None = None) -> int | None:
    """Run the drift once: the change it applies (None: none).  rand(100) gives `default` except where forced
    (return address -> value).  `registers`, when given, gets ebx, esi and ebp before and after the call."""
    m = Machine(exe)
    forced = forced or {}
    v = m.SCRATCH
    m.w32(FOOD, food)
    m.uc.mem_write(v + 0x1C48, bytes([sick]))
    m.w32(v + 0x1CF0, faith)
    m.stub(0x403660, lambda mm: forced.get(mm.r32(mm.uc.reg_read(UC_X86_REG_ESP)), default), 0)
    m.stub(PROJECT_DONE, lambda mm: statue_done, 4)
    m.stub(STATUE_STAGE, lambda mm: stage, 0)
    m.stub(TECH, lambda mm: spirit, 4)
    m.stub(BELIEVERS, lambda mm: believers, 0)
    applied = []
    m.stub(APPLY, lambda mm: applied.append(struct.unpack("<i", bytes(mm.uc.mem_read(
        mm.uc.reg_read(UC_X86_REG_ESP) + 4, 4)))[0]) or 0, 4)
    sp = m.STACK + 0x80000
    m.w32(sp, m.RET)
    m.uc.reg_write(UC_X86_REG_ESP, sp)
    m.uc.reg_write(UC_X86_REG_ECX, v)
    before = {"ebx": 0x1111, "esi": 0x2222, "ebp": 0x3333}
    m.uc.reg_write(UC_X86_REG_EBX, before["ebx"])
    m.uc.reg_write(UC_X86_REG_ESI, before["esi"])
    m.uc.reg_write(UC_X86_REG_EBP, before["ebp"])
    m.uc.emu_start(DRIFT, m.RET, count=2000)
    if registers is not None:
        registers["before"] = before
        registers["after"] = {"ebx": m.uc.reg_read(UC_X86_REG_EBX), "esi": m.uc.reg_read(UC_X86_REG_ESI),
                              "ebp": m.uc.reg_read(UC_X86_REG_EBP),
                              "esp": m.uc.reg_read(UC_X86_REG_ESP) - (sp + 4)}
    return applied[0] if applied else None


@unittest.skipUnless(HAVE_EMULATOR, "unicorn/pefile not installed")
class FaithLoss(unittest.TestCase):
    def test_the_manifest_is_the_generators(self):
        stock_path(5)
        path = ROOT / "data" / "vv5_faith_loss_feature.json"
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), gen.faith_feature())

    def threshold(self, exe: bytes, name: str) -> int:
        """The smallest forced rand(100) at the roll that no longer moves Faith (every other roll misses)."""
        at, cond, sign = ROLLS[name]
        for k in range(101):
            if drift(exe, forced={at: k}, **cond) != sign:
                return k
        return 100

    def test_every_loss_doubled_and_every_gain_halved(self):
        stock, patched = rendered(5, ()), rendered(5, (FAITH,))
        for name in ROLLS:
            self.assertEqual(self.threshold(stock, name), STOCK_THRESHOLD[name], ("stock", name))
            self.assertEqual(self.threshold(patched, name), PATCHED_THRESHOLD[name], ("patched", name))

    def test_a_fall_below_5_is_never_skipped_and_a_rise_above_75_still_is(self):
        stock, patched = rendered(5, ()), rendered(5, (FAITH,))
        fall = dict(food=100, forced={0x468076: 0, 0x4681B7: 0})        # the fall, and the skip roll's 0 (< 50)
        self.assertIsNone(drift(stock, faith=3, **fall), "stock skips the fall below 5 on rand(100) < 50")
        self.assertEqual(drift(patched, faith=3, **fall), -1)
        to_zero = dict(food=100, forced={0x468076: 0, 0x4681B7: 0, STAY_ROLL: 0})
        self.assertEqual(drift(patched, faith=1, **to_zero), -1, "reaches 0: the setter makes a Heathen as stock")
        rise = dict(food=9000, forced={0x468096: 0, 0x4681D3: 0})       # the rise, and the skip roll's 0 (< 70)
        self.assertIsNone(drift(stock, faith=80, **rise))
        self.assertIsNone(drift(patched, faith=80, **rise), "a rise above 75 is still skipped 70%")

    def test_without_its_companion_the_rule_is_1_in_10_each_time(self):
        """The cave's own rule (the companion decides once a crisis, tests/test_faith_loss_marks.py): a fall that the
        food or sickness losses take to 0 or less -- the drift's other changes alone leaving Faith above 0 -- is made
        on rand(10) < 1; otherwise the believer is left at Faith 1.  A fall the other changes make on their own is
        made as stock."""
        patched = rendered(5, (FAITH,))
        cases = (
            ("food under 10", dict(food=5), {0x468056: 0}, 1, 0),
            ("food 10 to 250", dict(food=100), {0x468076: 0}, 1, 0),
            ("food under 10, its second roll", dict(food=5), {0x468076: 0}, 1, 0),
            ("sickness", dict(sick=1), {0x4680B3: 0}, 1, 0),
            ("food, sickness and too few believers", dict(food=100, sick=1, believers=3),
             {0x468076: 0, 0x4680B3: 0, 0x468171: 0}, 3, 1),
        )
        for name, case, forced, fall, others in cases:
            for faith in (1, 2, 3, 4):
                for k in range(10):
                    with self.subTest(name, faith=faith, roll=k):
                        got = drift(patched, faith=faith, forced={**forced, STAY_ROLL: k}, **case)
                        if faith - fall > 0:
                            self.assertEqual(got, -fall, "a fall that leaves Faith above 0 is not decided")
                        elif faith - others <= 0:
                            self.assertEqual(got, -fall, "too few believers alone takes the last Faith: as stock")
                        elif k < 1:
                            self.assertEqual(got, -fall, "1 in 10 the believer becomes a Heathen")
                        else:
                            self.assertEqual(got, 1 - faith, "9 in 10 the believer stays at Faith 1")
        exact = sum(1 for v in range(32768) if v % 10 < 1)
        self.assertEqual(exact, 3277, "rand(10) < 1 comes 3,277 times in 32,768 (10.00%)")

    def test_too_few_believers_alone_and_every_rise_are_unchanged(self):
        stock, patched = rendered(5, ()), rendered(5, (FAITH,))
        for faith in (1, 2, 30):
            for k in range(10):
                self.assertEqual(drift(patched, faith=faith, believers=5, forced={0x468171: 0, STAY_ROLL: k}), -1)
        self.assertEqual(drift(stock, faith=50, food=9000, forced={0x468096: 0}), 1)
        self.assertEqual(drift(patched, faith=50, food=9000, forced={0x468096: 0}), 1)
        self.assertEqual(drift(patched, faith=50, food=5, forced={0x468056: 0}), -1,
                         "a fall that does not reach 0 is the stock fall")

    def test_the_drift_keeps_the_callers_registers(self):
        """ebp counts the food and sickness losses inside the routine; the caller's ebx, esi, ebp and esp come
        back as they were (the life tick 0x472C90 keeps ebp across the call)."""
        patched = rendered(5, (FAITH,))
        for case in (dict(food=100, forced={0x468076: 0}, faith=1), dict(food=9000, faith=50),
                     dict(food=9000, forced={0x468096: 0, 0x4681D3: 0}, faith=90), dict(sick=1, faith=3)):
            regs: dict = {}
            drift(patched, registers=regs, **case)
            after = dict(regs["after"])
            self.assertEqual(after.pop("esp"), 0, case)
            self.assertEqual(after, regs["before"], case)

    def test_default_off(self):
        self.assertFalse(default_fun_patch_selection(FAITH))
        rows = [p for p in patcher.load_public_fun_patches() if p.game_id == "vv5"]
        description = next(p for p in rows if p.id == FAITH).description
        self.assertTrue(description.endswith("Adds a real chance of your villagers becoming heathens. Makes the "
                                             "game that much harder. Good Luck!"))


# ---------------------------------------------------------------------------
# New Heathens Get a Heathen's Faith
# ---------------------------------------------------------------------------

SET_FAITH, TO_HEATHEN, MANAGER_OF, TO_BELIEVER = 0x467F90, 0x4669E0, 0x425950, 0x4668B0
GAME = 0x32000000                           # the manager 0x425950 returns: +0x17E39, the island runs
ORANGE, RED, ROLE, FACTION = 0x1CED, 0x1CEE, 0x1CFC, 0x1CEC


def setup_conversions(m, made: list) -> None:
    """The island runs (0x17E39) and 0x4669E0 makes the record a Heathen with role 0, as the game's does
    (0x4669F5, 0x4669FF); 0x4668B0 is only noted."""
    m.uc.mem_map(GAME, 0x20000)
    m.uc.mem_write(GAME + 0x17E39, b"\x01")
    m.stub(MANAGER_OF, lambda mm: GAME, 0)

    def to_heathen(mm):
        rec = mm.uc.reg_read(UC_X86_REG_ECX)
        made.append("heathen")
        mm.w32(rec + ROLE, 0)
        mm.uc.mem_write(rec + FACTION, b"\x01")
        return 0
    m.stub(TO_HEATHEN, to_heathen, 0)
    m.stub(TO_BELIEVER, lambda mm: made.append("believer") or 0, 0)


def set_faith(exe: bytes, *, old: int, new: int, flag: int = 1, running: int = 1) -> tuple[int, list]:
    """Run the setter 0x467F90 alone (as an island event calls it) on a record at Faith `old` with `new`: the Faith it
    stores and the conversions it made."""
    m = Machine(exe)
    v = m.SCRATCH
    m.w32(v + 0x1CF0, old)
    made: list = []
    setup_conversions(m, made)
    m.uc.mem_write(GAME + 0x17E39, bytes([running]))
    sp = m.STACK + 0x80000
    m.w32(sp, m.RET)
    m.w32(sp + 4, new)
    m.w32(sp + 8, flag)
    m.uc.reg_write(UC_X86_REG_ESP, sp)
    m.uc.reg_write(UC_X86_REG_ECX, v)
    m.uc.reg_write(UC_X86_REG_ESI, 0x2222)
    m.uc.emu_start(SET_FAITH, m.RET, count=500)
    assert m.uc.reg_read(UC_X86_REG_ESP) == sp + 12 and m.uc.reg_read(UC_X86_REG_ESI) == 0x2222
    return struct.unpack("<i", bytes(m.uc.mem_read(v + 0x1CF0, 4)))[0], made


def drift_convert(exe: bytes, *, faith: int, kind: tuple = (0, 0), role: int = 0, forced: dict | None = None,
                  default: int = 99, **conditions) -> dict:
    """Run the drift with the game's own FAITH_ADD and setter (food 100: a food fall when forced): the record's Faith,
    mask bytes, role and faction after it."""
    m = Machine(exe)
    v = m.SCRATCH
    forced = {0x468076: 0, **(forced or {})}
    m.w32(FOOD, conditions.get("food", 100))
    m.uc.mem_write(v + 0x1C48, bytes([conditions.get("sick", 0)]))
    m.w32(v + 0x1CF0, faith)
    m.uc.mem_write(v + ORANGE, bytes(kind))
    m.w32(v + ROLE, role)
    made: list = []
    setup_conversions(m, made)
    m.stub(0x403660, lambda mm: forced.get(mm.r32(mm.uc.reg_read(UC_X86_REG_ESP)), default)
           % mm.r32(mm.uc.reg_read(UC_X86_REG_ESP) + 4), 0)
    m.stub(PROJECT_DONE, lambda mm: 0, 4)
    m.stub(STATUE_STAGE, lambda mm: 0, 0)
    m.stub(TECH, lambda mm: 0, 4)
    m.stub(BELIEVERS, lambda mm: conditions.get("believers", 12), 0)
    sp = m.STACK + 0x80000
    m.w32(sp, m.RET)
    m.uc.reg_write(UC_X86_REG_ESP, sp)
    m.uc.reg_write(UC_X86_REG_ECX, v)
    m.uc.emu_start(DRIFT, m.RET, count=5000)
    raw = bytes(m.uc.mem_read(v + ORANGE, 2))
    return {"faith": struct.unpack("<i", bytes(m.uc.mem_read(v + 0x1CF0, 4)))[0], "orange": raw[0],
            "red": raw[1], "role": m.r32(v + ROLE), "heathen": bytes(m.uc.mem_read(v + FACTION, 1)) != b"\0",
            "made": made}


@unittest.skipUnless(HAVE_EMULATOR, "unicorn/pefile not installed")
class NewHeathensFaith(unittest.TestCase):
    def test_the_manifest_is_the_generators(self):
        stock_path(5)
        path = ROOT / "data" / "vv5_new_heathens_faith_feature.json"
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), gen.new_heathen_feature())

    def test_a_drift_convert_is_an_ordinary_blue_heathen_at_minus_38_to_minus_67(self):
        """The owner: "Once they turn heathen, have their faith randomly set to the typical blue heathen threshold"
        -- the mask by the mask type: role 0 and neither the orange nor the red byte; the Faith drawn as the game
        draws an ordinary Heathen's, -38 - rand(30)."""
        stock, patched = rendered(5, ()), rendered(5, (NEW_HEATHEN,))
        got = drift_convert(stock, faith=1, kind=(1, 0), role=5)
        self.assertEqual((got["faith"], got["heathen"], got["orange"], got["role"]), (0, True, 1, 0),
                         "stock: Faith 0, the orange byte kept")
        for k in (0, 1, 17, 29, 30, 59):
            for kind in ((0, 0), (1, 0), (0, 1)):
                with self.subTest(roll=k, kind=kind):
                    got = drift_convert(patched, faith=1, kind=kind, role=7, forced={BLUE_ROLL: k})
                    self.assertEqual(got["faith"], -38 - k % 30)
                    self.assertTrue(got["heathen"])
                    self.assertEqual((got["orange"], got["red"], got["role"]), (0, 0, 0), "the blue mask")
                    self.assertEqual(got["made"], ["heathen"])

    def test_with_faith_loss_the_drift_conversion_is_a_blue_heathen_too(self):
        both = rendered(5, tuple(sorted((FAITH, NEW_HEATHEN))))
        got = drift_convert(both, faith=1, kind=(0, 1), forced={STAY_ROLL: 0, BLUE_ROLL: 12})
        self.assertEqual((got["faith"], got["heathen"], got["orange"], got["red"]), (-50, True, 0, 0))
        stays = drift_convert(both, faith=1, kind=(0, 1), forced={STAY_ROLL: 4})
        self.assertEqual((stays["faith"], stays["heathen"]), (1, False), "9 in 10 stay at Faith 1")

    def test_island_events_and_every_other_setter_call_are_stock(self):
        """The Spa and The Cracked Mask call the setter with -10 themselves (0x415D02, 0x416C51): not the drift, so
        the stock answer, Faith -10."""
        stock, patched = rendered(5, ()), rendered(5, (NEW_HEATHEN,))
        for kw in (dict(old=1, new=0), dict(old=10, new=-10), dict(old=50, new=-3), dict(old=50, new=49),
                   dict(old=-55, new=-50), dict(old=-55, new=3), dict(old=-55, new=20), dict(old=-1, new=-5),
                   dict(old=5, new=0, flag=0), dict(old=5, new=-3, running=0), dict(old=99, new=150),
                   dict(old=5, new=-200)):
            self.assertEqual(set_faith(patched, **kw), set_faith(stock, **kw), kw)
        self.assertEqual(set_faith(patched, old=10, new=-10), (-10, ["heathen"]))

    def test_the_mask_is_chosen_by_role_and_kind_bytes_not_faith(self):
        """The Heathen draw 0x4728C6..0x472919: role +0x1CFC - 12 through the table 0x472B60 (12..16: purple or
        the Chief), then +0x1CED (orange) and +0x1CEE (red); nothing reads Faith there."""
        image = pefile.PE(data=rendered(5, ()), fast_load=True).get_memory_mapped_image()
        at = lambda va, n: bytes(image[va - 0x400000:va - 0x400000 + n])  # noqa: E731
        self.assertEqual(at(0x4728C6, 9), bytes.fromhex("8B86FC1C000083C0F4"), "mov eax,[esi+0x1CFC]; add eax,-12")
        self.assertEqual(at(0x4728D1, 12), bytes.fromhex("83F8047715FF2485602B4700"), "cmp 4; ja; jmp [table]")
        self.assertEqual(at(0x4728EB, 7), bytes.fromhex("80BEED1C000000"), "cmp byte [esi+0x1CED],0 (orange)")
        self.assertEqual(at(0x472903, 7), bytes.fromhex("80BEEE1C000000"), "cmp byte [esi+0x1CEE],0 (red)")
        self.assertNotIn(bytes.fromhex("F01C0000"), at(0x4728C6, 0x472919 - 0x4728C6), "no Faith (+0x1CF0) read")
        self.assertEqual(at(0x4669F5, 10), bytes.fromhex("C786FC1C000000000000"), "0x4669E0 sets the role to 0")

    def test_minus_38_to_minus_67_is_the_ordinary_heathens_faith(self):
        """A new village's Heathens are made at -1 (0x424AC0's creator calls) and every one still at -1 is set to
        -38 - rand(30) (0x471050..0x471099); Barrel O' Babies! (heathens) makes its at -55 (0x4152B0)."""
        image = pefile.PE(data=rendered(5, ()), fast_load=True).get_memory_mapped_image()
        at = lambda va, n: bytes(image[va - 0x400000:va - 0x400000 + n])  # noqa: E731
        self.assertEqual(at(0x424AC0, 2), bytes.fromhex("6AFF"), "the first creator call's Faith: push -1")
        self.assertEqual(at(0x47105A, 8), bytes.fromhex("83BC18381D0000FF"), "cmp [record+0x1CF0],-1")
        self.assertEqual(at(0x471070, 2), bytes.fromhex("6A1E"), "rand(30)")
        self.assertEqual(at(0x47107C, 5), bytes.fromhex("B9DAFFFFFF"), "-38 - rand(30)")
        self.assertEqual(at(0x47108E, 5), bytes.fromhex("BADAFFFFFF"), "-38 - rand(30)")
        self.assertEqual(at(0x4152B0, 2), bytes.fromhex("6AC9"), "Barrel O' Babies! (heathens): push -0x37")
        self.assertIn(-55, range(-67, -37))

    def test_on_by_default_and_needs_nothing(self):
        public = patcher.load_public_fun_patches()
        rows = {p.id: p for p in public}
        self.assertIn(NEW_HEATHEN, rows)
        self.assertTrue(default_fun_patch_selection(NEW_HEATHEN))
        self.assertEqual(patcher.patch_requirement_text(rows[NEW_HEATHEN], public),
                         "Requires no other patch to be ticked.")


# ---------------------------------------------------------------------------
# Puddle Play Moves to the Lake Shore, and Fix Vanilla Bugs' lake-bed spots
# ---------------------------------------------------------------------------

def emulation():
    try:
        import farmers_emulation_vv5 as fe
    except ImportError:  # pragma: no cover
        raise unittest.SkipTest("unicorn not installed")
    if not fe.available():
        raise unittest.SkipTest("New Believers' exe and map (research/game-data/vv5) not present")
    return fe


def poke(v, patches) -> None:
    """Write manifest patches into the running village's image (and drop unicorn's cached translations)."""
    for p in patches:
        at, data = int(p["offset"], 16) + 0x400000, bytes.fromhex(p["after"])
        v.uc.mem_write(at, data)
        v.uc.ctl_remove_cache(at, at + len(data))


def lake_village(fe, *, lake: bool, patches=(), seed=7):
    v = fe.Village(seed=seed, projects=(fe.GRANARY, fe.HUNGRY_TOTEM, fe.HYDRO_FARM) + ((fe.LAKE,) if lake else ()))
    v.call(0x43C620)                          # the lake's map areas, as the game sets them for its state
    poke(v, patches)
    v.villager(age=100, health=90)
    return v


def picker_fix():
    rows = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))["fun_patches"]
    row = next(p for p in rows if p["id"] == "vv5_fix_vanilla_bugs")
    return [p for p in row["patches"] if p["purpose"].startswith("Lake bed puddle spots")]


def lake_cells(fe):
    data = (fe.DATA / "lcmap.dat").read_bytes()
    cells = struct.unpack("<102400I", data)
    return cells


@unittest.skipUnless(HAVE_EMULATOR, "unicorn/pefile not installed")
class PuddlesByTheLake(unittest.TestCase):
    def test_the_manifest_is_the_generators(self):
        stock_path(5)
        path = ROOT / "data" / "vv5_puddles_by_the_lake_feature.json"
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), gen.puddles_feature())
        self.assertTrue(default_fun_patch_selection(PUDDLES))

    def test_every_shore_point_is_dry_walkable_and_joined_to_the_village(self):
        fe = emulation()
        cells = lake_cells(fe)

        def free(cx, cy):
            cell = cells[cy * 320 + cx]
            return not cell & 1 and (cell >> 4) & 0x7FF not in (0x69, 0x6A)
        # The village's walkable ground, from the flower patch (the dirt spot) outwards.
        start = (2000 // 8, 1580 // 8)
        seen, todo = {start}, [start]
        while todo:
            x, y = todo.pop()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < 320 and 0 <= ny < 320 and (nx, ny) not in seen and free(nx, ny):
                    seen.add((nx, ny))
                    todo.append((nx, ny))
        for r in range(gen.SHORE_SPAN):
            x, y = gen.shore_point(r)
            cx, cy = x // 8, y // 8
            self.assertIn((cx, cy), seen, (r, x, y))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    self.assertTrue(free(cx + dx, cy + dy), (r, x, y))

    def run_action(self, v, fe, behaviour: int = 0x5E):
        targets, areas = [], []
        hooks = [v.uc.hook_add(UC_HOOK_CODE, lambda uc, a, s, d: targets.append(struct.unpack(
                     "<ii", bytes(uc.mem_read(uc.reg_read(UC_X86_REG_ESP) + 4, 8)))), begin=0x4745A0, end=0x4745A0),
                 v.uc.hook_add(UC_HOOK_CODE, lambda uc, a, s, d: areas.append(struct.unpack(
                     "<i", bytes(uc.mem_read(uc.reg_read(UC_X86_REG_ESP) + 4, 4)))[0]), begin=0x4744C0, end=0x4744C0)]
        v.start(behaviour)                     # 0x5E "Playing in puddles" (0x68 "Playing in the dirt")
        for h in hooks:
            v.uc.hook_del(h)
        frames, ends = 0, []
        last = v.step_type()
        while v.step_type() != 0:
            v.step_frame()
            frames += 1
            if last == 4 and v.step_type() != 4:
                ends.append(v.feet())
            last = v.step_type()
            self.assertLess(frames, 20000, "the action ends")
        return targets, areas, ends

    def test_with_water_the_child_plays_on_the_shore_and_the_action_ends(self):
        fe = emulation()
        feature = gen.puddles_feature()
        for seed in (3, 7, 11):
            v = lake_village(fe, lake=True, patches=feature["patches"], seed=seed)
            targets, areas, ends = self.run_action(v, fe)
            self.assertEqual(areas, [])
            self.assertEqual(len(targets), 5)
            shore = {gen.shore_point(r) for r in range(gen.SHORE_SPAN)}
            for t in targets:
                self.assertIn(t, shore)
            # Each walk ends where the game puts a villager sent to that point (its feet 12 left, 35 up): on the shore.
            arrived = [e for e in ends if e != ends[0]] or ends
            self.assertTrue(any(abs(x - (tx - 12)) <= 4 and abs(y - (ty - 35)) <= 4
                                for (x, y) in arrived for (tx, ty) in targets), (targets, ends))

    def test_without_water_nothing_changes(self):
        fe = emulation()
        feature = gen.puddles_feature()
        v = lake_village(fe, lake=False, patches=feature["patches"])
        targets, areas, _ = self.run_action(v, fe)
        self.assertEqual((areas, targets), ([0x6A] * 5, []))

    def dirt_spot(self):
        return json.loads((ROOT / "data" / "vv5_playing_in_the_dirt_feature.json").read_text(encoding="utf-8"))

    def test_playing_in_the_dirt_goes_to_the_shore_with_the_lake_dry_or_full(self):
        """The owner (2026-11-08): Puddle Play Moves to the Lake Shore also moves "Playing in the dirt" (behaviour
        0x68, 0x45ED40) to the same shore, before and after The Lake has water.  Stock and with Move the "Playing in
        the dirt" Spot, the six go-tos stay in their own boxes; with the shore patch every one is a shore point, and
        the child arrives on the shore and the action ends."""
        fe = emulation()
        shore = {gen.shore_point(r) for r in range(gen.SHORE_SPAN)}
        puddles, spot = gen.puddles_feature()["patches"], self.dirt_spot()["patches"]
        for lake in (False, True):
            for seed in (3, 7):
                with self.subTest(lake=lake, seed=seed):
                    targets, areas, _ = self.run_action(lake_village(fe, lake=lake, seed=seed), fe, 0x68)
                    self.assertEqual((len(targets), areas), (6, []))
                    self.assertTrue(all(236 <= x <= 453 and 442 <= y <= 475 for x, y in targets), targets)
                    targets, _, _ = self.run_action(lake_village(fe, lake=lake, patches=spot, seed=seed), fe, 0x68)
                    self.assertEqual(len(targets), 6)
                    self.assertTrue(all(1860 <= x <= 2164 and 1479 <= y <= 1683 for x, y in targets), targets)
                    v = lake_village(fe, lake=lake, patches=puddles, seed=seed)
                    targets, areas, ends = self.run_action(v, fe, 0x68)
                    self.assertEqual((len(targets), areas), (6, []))
                    for t in targets:
                        self.assertIn(t, shore)
                    self.assertGreater(len({t for t in targets}), 1, "random points, not one spot")
                    # Each walk ends where the game puts a villager sent to that point (its feet 12 left, 35 up).
                    self.assertTrue(any(abs(x - (tx - 12)) <= 4 and abs(y - (ty - 35)) <= 4
                                        for (x, y) in ends for (tx, ty) in targets), (targets, ends))

    def test_the_dirt_cave_changes_only_the_dirt_walk(self):
        """Only "Playing in the dirt"'s own go-to is re-aimed: the cave's one caller is 0x45ED99, and every other
        call of 0x4745A0 in the executable is the stock one."""
        stock_path(5)
        feature = gen.puddles_feature()
        at = gen.dirt_cave_at()
        sites = {int(p["offset"], 16) + 0x400000: bytes.fromhex(p["after"]) for p in feature["patches"]}
        self.assertEqual(sites[gen.DIRT_SITE], bytes([0xE8]) + struct.pack("<i", at - (gen.DIRT_SITE + 5)))
        self.assertEqual(sites[at], gen.dirt_cave(at))
        image = rendered(5, (PUDDLES,))
        pe = pefile.PE(data=image, fast_load=True).get_memory_mapped_image()
        callers = [va for va in range(0x401000, 0x494000)
                   if pe[va - 0x400000] == 0xE8 and va + 5 + struct.unpack_from("<i", pe, va - 0x400000 + 1)[0] == at]
        self.assertEqual(callers, [gen.DIRT_SITE])
        # The puddles' own cave and the Fix Vanilla Bugs picker cave are where they were.
        self.assertEqual(at, gen.CAVE + len(gen.puddle_cave()))
        self.assertLessEqual(at + len(gen.dirt_cave(at)), gen.PICKER_CAVE)

    def test_the_two_dirt_patches_untick_each_other_and_never_build_together(self):
        from vv_fun_patcher_gui import UNTICKING_CONFLICT_IDS, conflict_blockers
        spot = self.dirt_spot()
        self.assertEqual(spot["conflicts"], [PUDDLES])
        self.assertEqual(gen.puddles_feature()["conflicts"], [gen.DIRT_SPOT_ID])
        self.assertEqual(UNTICKING_CONFLICT_IDS[PUDDLES], gen.DIRT_SPOT_ID)
        self.assertEqual(UNTICKING_CONFLICT_IDS[gen.DIRT_SPOT_ID], PUDDLES)
        public = patcher.load_public_fun_patches()
        self.assertEqual(conflict_blockers(gen.DIRT_SPOT_ID, public, {PUDDLES}), [])
        with self.assertRaises(patcher.PatcherError):
            patcher.resolve_fun_patch_ids([PUDDLES, gen.DIRT_SPOT_ID], game_id="vv5")
        self.assertIn(gen.DIRT_SPOT_ID, patcher.ALTERNATIVE_FUN_PATCH_IDS)
        self.assertIn("**Cannot be used with Move the \"Playing in the dirt\" Spot", gen.puddles_feature()["description"])
        self.assertIn("Cannot be used with Puddle Play Moves to the Lake Shore", spot["description"])

    def chooser(self, fe, patches, lake: bool, rain: int) -> int:
        """\"Excited about the puddles\"' child-activity pick 0x469DC0 (rand(6) = 4, the lake case)."""
        v = lake_village(fe, lake=lake, patches=patches)
        v.w32(0x718EB8, rain)
        v.by_caller[0x469DCD] = 4
        v.call(0x469DC0, fe.V0)
        return v.r32(fe.V0 + fe.BEHAVIOUR)

    def scheduler_case(self, fe, patches, lake: bool, rain: int) -> int:
        """The scheduler's case at 0x46EFB2 (after The Hollow Totem's check): its own frame, esi the villager."""
        v = lake_village(fe, lake=lake, patches=patches)
        v.w32(0x718EB8, rain)
        sp = fe.STACK + 0x1F0000
        v.uc.mem_write(sp, b"\0" * 0x30)
        v.w32(sp + 0x28, fe.RET)
        v.uc.reg_write(UC_X86_REG_ESP, sp)
        v.uc.reg_write(UC_X86_REG_ESI, fe.V0)
        v.uc.reg_write(UC_X86_REG_EBX, 0)
        v.uc.emu_start(0x46EFB2, fe.RET, count=5_000_000)
        return v.r32(fe.V0 + fe.BEHAVIOUR)

    def playing_chooser(self, fe, patches, lake: bool, rain: int, raining: bool = True) -> int | None:
        """\"Playing in puddles\"' chooser 0x46E4F7 (its function's own frame, esi the villager): the behaviour it
        starts, or None when it passes on (0x46E549)."""
        v = lake_village(fe, lake=lake, patches=patches)
        v.w32(0x718EB8, rain)
        v.by_caller[0x46E507] = 0                 # rand(100) < 75
        started = []

        def weather(uc, *_):                      # 0x477040, is it raining: al
            sp = uc.reg_read(UC_X86_REG_ESP)
            uc.reg_write(UC_X86_REG_EAX, int(raining))
            uc.reg_write(UC_X86_REG_EIP, struct.unpack("<I", bytes(uc.mem_read(sp, 4)))[0])
            uc.reg_write(UC_X86_REG_ESP, sp + 4)

        def start(uc, *_):
            started.append(struct.unpack("<I", bytes(uc.mem_read(uc.reg_read(UC_X86_REG_ESP) + 4, 4)))[0])
            uc.emu_stop()

        hooks = [v.uc.hook_add(UC_HOOK_CODE, weather, begin=0x477040, end=0x477040),
                 v.uc.hook_add(UC_HOOK_CODE, start, begin=0x465580, end=0x465580),
                 v.uc.hook_add(UC_HOOK_CODE, lambda uc, *_: uc.emu_stop(), begin=0x46E549, end=0x46E549)]
        sp = fe.STACK + 0x1F0000
        v.uc.mem_write(sp, b"\0" * 0x40)
        v.uc.reg_write(UC_X86_REG_ESP, sp)
        v.uc.reg_write(UC_X86_REG_ESI, fe.V0)
        v.uc.reg_write(UC_X86_REG_EBX, 0)
        v.uc.emu_start(0x46E4F7, fe.RET, count=5_000_000)
        for h in hooks:
            v.uc.hook_del(h)
        return started[0] if started else None

    def test_playing_in_puddles_keeps_the_rain_and_drops_the_water_test(self):
        fe = emulation()
        patches = gen.puddles_feature()["patches"]
        run = self.playing_chooser
        self.assertIsNone(run(fe, [], lake=True, rain=60))                  # stock: disabled once there is water
        self.assertEqual(run(fe, patches, lake=True, rain=60), 0x5E)        # patched: Playing in puddles
        self.assertIsNone(run(fe, patches, lake=True, rain=40))             # the rain level still counts
        self.assertIsNone(run(fe, patches, lake=True, rain=60, raining=False))
        self.assertEqual(run(fe, [], lake=False, rain=60), 0x5E)
        self.assertEqual(run(fe, patches, lake=False, rain=60), 0x5E)

    def test_excited_about_the_puddles_and_chasing_fish_are_stock(self):
        """The owner (2026-11-07): "Playing in puddles" only; "Excited about the puddles" stays as the game has it."""
        fe = emulation()
        patches = gen.puddles_feature()["patches"] + picker_fix()
        offsets = {int(p["offset"], 16) + 0x400000 for p in patches}
        for site in (0x469E5E, 0x46EFC5, 0x45423B, 0x454200):
            self.assertNotIn(site, offsets)
        for run in (self.chooser, self.scheduler_case):
            for lake, rain in ((True, 60), (True, 40), (False, 60)):
                self.assertEqual(run(fe, patches, lake=lake, rain=rain), run(fe, [], lake=lake, rain=rain),
                                 (run.__name__, lake, rain))

    def picks(self, fe, patches, start: int, stop: int, n: int):
        v = lake_village(fe, lake=False, patches=patches, seed=11)
        out = []
        hook = v.uc.hook_add(UC_HOOK_CODE, lambda uc, a, s, d: out.append(struct.unpack(
            "<ii", bytes(uc.mem_read(uc.reg_read(UC_X86_REG_ESP) + 0xC, 8)))), begin=0x4744EB, end=0x4744EB)
        for _ in range(n):
            v.call(fe.CLEAR_QUEUE, fe.V0)
            v.uc.reg_write(UC_X86_REG_ESI, fe.V0)
            v.uc.reg_write(UC_X86_REG_ESP, fe.STACK + 0x1F0000)
            v.uc.emu_start(start, stop, count=50_000_000)
        v.uc.hook_del(hook)
        return out

    def test_fix_vanilla_bugs_spreads_the_puddle_spots_over_the_whole_lake_bed(self):
        """Stock: only the first 1,024 of the puddles' 1,479 cells (area 0x6A).  Fixed: every cell, each equally
        likely (455 of 1,479, about 31%, lie past the first 1,024).  "Excited about the puddles" (area 0x69) and
        fishing (0x463B48) pick as stock either way."""
        fe = emulation()
        cells = lake_cells(fe)

        def area(n):
            return [(i % 320, i // 320) for i, c in enumerate(cells) if (c >> 4) & 0x7FF == n and not c & 1]
        puddles_area, bed = area(0x6A), area(0x69)
        self.assertEqual(len(puddles_area), 1479)
        first, bed_first = set(puddles_area[:1024]), set(bed[:1024])
        fix = picker_fix()
        self.assertEqual(len(fix), 4)
        for patches, beyond in (([], (0.0, 0.0)), (fix, (0.25, 0.37))):
            puddles = self.picks(fe, patches, 0x460030, 0x460040, 1200)
            excited = self.picks(fe, patches, 0x454230, 0x454240, 300)
            fishing = self.picks(fe, patches, 0x463B48, 0x463B55, 300)
            for x, y in puddles:
                self.assertIn((x // 8, y // 8), set(puddles_area))
            share = sum((x // 8, y // 8) not in first for x, y in puddles) / len(puddles)
            self.assertGreaterEqual(share, beyond[0], bool(patches))
            self.assertLessEqual(share, beyond[1], bool(patches))
            self.assertTrue(all((x // 8, y // 8) in bed_first for x, y in excited + fishing), "unchanged")

    def test_registered_and_documented(self):
        source = (ROOT / "src" / "vv_fun_patcher.py").read_text(encoding="utf-8")
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        log = (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8")
        howto = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        guided = {i for entry in howto["patches"] for i in entry.get("ids", [])}
        self.assertIn("PUDDLES_BY_THE_LAKE_FEATURE_PATHS", source)
        self.assertIn("NEW_HEATHENS_FAITH_FEATURE_PATHS", source)
        for pid in NEW_IDS:
            self.assertIn(f"- Patch ID: `{pid}`", readme)
            self.assertIn(f"`{pid}`", log)
        for name in ("vv1_apprentice_graves", "vv2_apprentice_graves", "vv3_apprentice_graves",
                     "vv5_apprentice_graves", "vv5_faith_loss", "vv5_new_heathens_faith", "vv5_puddles_by_the_lake"):
            self.assertIn(f'"data/{name}_feature.json"', release)
        for pid in NEW_IDS:
            self.assertIn(pid, guided)

    def test_no_other_patch_claims_the_bytes(self):
        mine: dict[str, set] = {}
        for record in [gen.apprentice_feature(g) for g in (1, 2, 3, 5)] + [gen.faith_feature(), gen.puddles_feature(),
                                                                           gen.new_heathen_feature()]:
            for p in record["patches"]:
                off = int(p["offset"], 16)
                mine.setdefault(record["game_id"], set()).update(range(off, off + len(p["after"]) // 2))
        for p in picker_fix():
            off = int(p["offset"], 16)
            mine["vv5"].update(range(off, off + len(p["after"]) // 2))
        ours = set(NEW_IDS) | {"vv5_fix_vanilla_bugs"}
        for record in patcher._load_fun_patch_records(include_expanded_time_warp=True):
            raw = record.raw if hasattr(record, "raw") else record
            if raw.get("id") in ours or raw.get("game_id") not in mine:
                continue
            for p in raw.get("patches", []) or []:
                try:
                    off, n = int(str(p.get("offset")), 16), len(p.get("before", "")) // 2
                except (TypeError, ValueError):
                    continue
                self.assertFalse(mine[raw["game_id"]] & set(range(off, off + n)), (raw.get("id"), p.get("offset")))


if __name__ == "__main__":
    unittest.main()
