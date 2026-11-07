"""Children's Graves Say Apprentice (A New Home, The Lost Children, The Secret City, New Believers), Faith Loss is
Doubled/Gains Halved and Puddle Play Moves to the Lake Shore (New Believers), and New Believers' Fix Vanilla Bugs
lake-bed spots.  The traces and the rules are in scripts/build_apprentice_faith_puddles_features.py.

Each patch is run, stock and patched, in unicorn from the executable the patcher renders:
  * the grave dialog's rank pick, for every age edge, best skill edge and job (none included): the string id it
    fetches and the stack and buffer it hands the copy call;
  * New Believers' Faith drift 0x468040, every roll's threshold found by forcing the game's rand(100) at that roll;
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
FAITH, PUDDLES = gen.FAITH_ID, gen.PUDDLES_ID
NEW_IDS = tuple(APPRENTICE.values()) + (FAITH, PUDDLES)


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


def drift(exe: bytes, *, faith=50, food=1000, sick=0, statue_done=0, stage=0, spirit=0, believers=12,
          forced: dict | None = None, default=99) -> int | None:
    """Run the drift once: the change it applies (None: none).  rand(100) gives `default` except where forced
    (return address -> value)."""
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
    m.uc.emu_start(DRIFT, m.RET, count=2000)
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
        self.assertEqual(drift(patched, faith=1, **fall), -1, "reaches 0: the setter makes a Heathen as stock")
        rise = dict(food=9000, forced={0x468096: 0, 0x4681D3: 0})       # the rise, and the skip roll's 0 (< 70)
        self.assertIsNone(drift(stock, faith=80, **rise))
        self.assertIsNone(drift(patched, faith=80, **rise), "a rise above 75 is still skipped 70%")

    def test_default_off(self):
        self.assertFalse(default_fun_patch_selection(FAITH))
        rows = [p for p in patcher.load_public_fun_patches() if p.game_id == "vv5"]
        description = next(p for p in rows if p.id == FAITH).description
        self.assertTrue(description.endswith("Adds a real chance of your villagers becoming heathens. Makes the "
                                             "game that much harder. Good Luck!"))


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

    def run_action(self, v, fe):
        targets, areas = [], []
        hooks = [v.uc.hook_add(UC_HOOK_CODE, lambda uc, a, s, d: targets.append(struct.unpack(
                     "<ii", bytes(uc.mem_read(uc.reg_read(UC_X86_REG_ESP) + 4, 8)))), begin=0x4745A0, end=0x4745A0),
                 v.uc.hook_add(UC_HOOK_CODE, lambda uc, a, s, d: areas.append(struct.unpack(
                     "<i", bytes(uc.mem_read(uc.reg_read(UC_X86_REG_ESP) + 4, 4)))[0]), begin=0x4744C0, end=0x4744C0)]
        v.start(0xEB)
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
            self.assertEqual(len(targets), 3)
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
        self.assertEqual((areas, targets), ([0x69, 0x69, 0x69], []))

    def chooser(self, fe, patches, lake: bool, rain: int) -> int:
        v = lake_village(fe, lake=lake, patches=patches)
        v.w32(0x718EB8, rain)
        v.by_caller[0x469DCD] = 4                 # the child-activity pick 0x469DC0: rand(6) = 4, the lake case
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

    def test_the_choosers_keep_the_rain_and_drop_the_water_test(self):
        fe = emulation()
        patches = gen.puddles_feature()["patches"]
        for run in (self.chooser, self.scheduler_case):
            self.assertEqual(run(fe, [], lake=True, rain=60), 0xEA, run.__name__)        # stock: disabled
            self.assertEqual(run(fe, patches, lake=True, rain=60), 0xEB, run.__name__)   # patched: puddles
            self.assertEqual(run(fe, patches, lake=True, rain=40), 0xEA, run.__name__)   # no rain: as stock
            self.assertEqual(run(fe, [], lake=False, rain=60), 0xEB, run.__name__)
            self.assertEqual(run(fe, patches, lake=False, rain=60), 0xEB, run.__name__)

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
        """Stock: only the lake bed's first 1,024 cells.  Fixed: every cell, each equally likely (about 1,973 of
        2,997 cells lie past the first 1,024).  Fishing (0x463B48) picks as stock either way."""
        fe = emulation()
        cells = lake_cells(fe)
        bed = [(i % 320, i // 320) for i, c in enumerate(cells) if (c >> 4) & 0x7FF == 0x69 and not c & 1]
        first = set(bed[:1024])
        fix = picker_fix()
        self.assertEqual(len(fix), 4)
        for patches, puddle_beyond in (([], (0.0, 0.0)), (fix, (0.60, 0.72))):
            puddles = self.picks(fe, patches, 0x454230, 0x454240, 1200)
            fishing = self.picks(fe, patches, 0x463B48, 0x463B55, 300)
            for x, y in puddles + fishing:
                self.assertIn((x // 8, y // 8), set(bed))
            share = sum((x // 8, y // 8) not in first for x, y in puddles) / len(puddles)
            self.assertGreaterEqual(share, puddle_beyond[0], bool(patches))
            self.assertLessEqual(share, puddle_beyond[1], bool(patches))
            self.assertTrue(all((x // 8, y // 8) in first for x, y in fishing), "fishing is unchanged")

    def test_registered_and_documented(self):
        source = (ROOT / "src" / "vv_fun_patcher.py").read_text(encoding="utf-8")
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        log = (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8")
        howto = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        guided = {i for entry in howto["patches"] for i in entry.get("ids", [])}
        self.assertIn("PUDDLES_BY_THE_LAKE_FEATURE_PATHS", source)
        for pid in NEW_IDS:
            self.assertIn(f"- Patch ID: `{pid}`", readme)
            self.assertIn(f"`{pid}`", log)
        for name in ("vv1_apprentice_graves", "vv2_apprentice_graves", "vv3_apprentice_graves",
                     "vv5_apprentice_graves", "vv5_faith_loss", "vv5_puddles_by_the_lake"):
            self.assertIn(f'"data/{name}_feature.json"', release)
        for pid in NEW_IDS:
            self.assertIn(pid, guided)

    def test_no_other_patch_claims_the_bytes(self):
        mine: dict[str, set] = {}
        for record in [gen.apprentice_feature(g) for g in (1, 2, 3, 5)] + [gen.faith_feature(), gen.puddles_feature()]:
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
