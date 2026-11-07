"""Checked Skill Preferences are listed as Jobs on Graves (all five games).  The rules and the burial writers are
in scripts/build_preferred_job_graves_features.py.

Each burial writer's recoded block is run, stock and patched, in unicorn from the executable the patcher renders,
with the game's own routines it calls (the best-skill routine, the elder / Scholar test, the name copy):
  * no preference checked (and any value out of range): every byte the block writes, every register and stack
    slot the code after it reads, and the flags it leaves are the stock ones;
  * a preference checked: the same, except the grave's job is the preference and its value that skill's (a
    float cut to a whole number in The Tree of Life and New Believers);
  * The Lost Children's epitaph: the job its pair is picked by is the grave's (stock: the highest skill again).
Tests that need the stock executables skip when they are absent.
"""
from __future__ import annotations

import importlib.util
import json
import random
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
    import pefile  # noqa: F401
    from unicorn import UC_ARCH_X86, UC_MODE_32, Uc
    from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX,
                                   UC_X86_REG_EDI, UC_X86_REG_EDX, UC_X86_REG_EFLAGS, UC_X86_REG_EIP,
                                   UC_X86_REG_ESI, UC_X86_REG_ESP)
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

_spec = importlib.util.spec_from_file_location("build_preferred_job_graves_features",
                                               ROOT / "scripts" / "build_preferred_job_graves_features.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

STOCK_DIR = ROOT / "research" / "stock-executables"
IDS = {g: gen.row_id(g) for g in range(1, 6)}
FLAGS = 0x8C1                     # CF, ZF, SF, OF: what a following jcc reads


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
    STACK, SCRATCH, BIG = 0x20000000, 0x30000000, 0x40000000

    def __init__(self, exe: bytes):
        import pefile as pf
        pe = pf.PE(data=exe, fast_load=True)
        base = pe.OPTIONAL_HEADER.ImageBase
        size = (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFFF) & ~0xFFFF
        self.uc = Uc(UC_ARCH_X86, UC_MODE_32)
        self.uc.mem_map(base, size)
        self.uc.mem_write(base, pe.get_memory_mapped_image()[:size])
        self.uc.mem_map(self.STACK, 0x100000)
        self.uc.mem_map(self.SCRATCH, 0x200000)
        self.uc.mem_map(self.BIG, 0x1000000)

    def w32(self, at: int, value: int) -> None:
        self.uc.mem_write(at, struct.pack("<I", value & 0xFFFFFFFF))

    def wf(self, at: int, value: float) -> None:
        self.uc.mem_write(at, struct.pack("<f", value))

    def r32(self, at: int) -> int:
        return struct.unpack("<i", bytes(self.uc.mem_read(at, 4)))[0]

    def read(self, at: int, n: int) -> bytes:
        return bytes(self.uc.mem_read(at, n))

    def regs(self, *names) -> tuple:
        return tuple(self.uc.reg_read(r) for r in names)


# ---------------------------------------------------------------------------
# The reference rules
# ---------------------------------------------------------------------------

# Skills in record order and the grave job id each one is (A New Home / The Lost Children: Parenting, Building,
# Farming, Healing, Research); the stock routine's comparison order (indices).
VV12_JOB = {1: (2, 4, 1, 5, 3), 2: (2, 5, 1, 3, 4)}
VV12_ORDER = {1: (0, 1, 3, 2, 4), 2: (0, 1, 3, 2, 4)}


def stock_best(game: int, skills: list) -> tuple[int, int]:
    """(job, value) the game's best-skill routine gives."""
    if game in (1, 2):
        order = VV12_ORDER[game]
        value, job = skills[order[0]], VV12_JOB[game][order[0]]
        for k in order[1:]:
            if skills[k] > value:
                value, job = skills[k], VV12_JOB[game][k]
        return (job if value != 0 else 0), value
    if game == 3:
        job, value = -1, 0
        for k, s in enumerate(skills):
            if s > value:
                job, value = k, s
        return job, value
    job, value = -1, 0
    for k, s in enumerate(skills):
        if s > value:
            job, value = k, int(s)
    return job, value


def preferred(game: int, skills: list, pref: int) -> tuple[int, int] | None:
    if game in (1, 2):
        if not 1 <= pref <= 5:
            return None
        return pref, skills[gen.PREF_SKILL[game][pref - 1]]
    if not 0 <= pref <= (5 if game == 5 else 4):
        return None
    return pref, int(skills[pref])


SKILL_COUNT = {1: 5, 2: 5, 3: 5, 4: 5, 5: 6}
PREF_OFFSET = {1: 0x3D0, 2: 0x7F8, 3: 0xEC0, 4: 0x1C70, 5: 0x1C74}


def cases(game: int):
    rng = random.Random(game)
    n = SKILL_COUNT[game]
    flt = game >= 4
    fixed = [[0] * n, [100] * n, [20] * n, [5, 5, 5, 5, 5, 5][:n], [0, 0, 0, 0, 1, 1][:n]]
    sets = fixed + [[(rng.randrange(0, 1001) / 10 if flt else rng.randrange(0, 101)) for _ in range(n)]
                    for _ in range(25)]
    if flt:
        sets.append([50.5, 50.7, 10.2, 99.99, 0.3, 7.0][:n])
    prefs = ([0, 1, 2, 3, 4, 5, 6, -1, 0x7FFFFFFF] if game in (1, 2)
             else [-1, 0, 1, 2, 3, 4, 5, 6, -2])
    for k, skills in enumerate(sets):
        for pref in prefs:
            yield skills, pref, (100, 279, 280, 359, 360, 900)[k % 6]


# ---------------------------------------------------------------------------
# Running each writer
# ---------------------------------------------------------------------------

def run_vv1(exe: bytes, skills, pref, age) -> dict:
    m = Machine(exe)
    v, g = m.SCRATCH, m.SCRATCH + 0x100000
    idx, place = 3, 7
    rec = v + idx * 0x3D8
    m.w32(v + 0x3E010, g)
    m.w32(rec + 0x348, age)
    m.uc.mem_write(rec + 0x370, b"Kalani Kahale\0")
    for k, s in enumerate(skills):
        m.w32(rec + 0x3BC + 4 * k, s)
    m.w32(rec + 0x3D0, pref)
    holder = m.SCRATCH + 0x80000
    m.w32(holder - 0x2EC, idx)
    grave = g + place * 0x2C
    sp = m.STACK + 0x80000
    m.uc.reg_write(UC_X86_REG_ESP, sp)
    m.uc.reg_write(UC_X86_REG_EDI, v)
    m.uc.reg_write(UC_X86_REG_ESI, holder)
    m.uc.reg_write(UC_X86_REG_EBP, place * 0x2C)
    m.uc.reg_write(UC_X86_REG_EBX, place)
    m.uc.reg_write(UC_X86_REG_EDX, g)
    m.uc.reg_write(UC_X86_REG_EAX, grave + 0xA340)
    m.uc.emu_start(0x448F8D, 0x448FFE, count=20000)
    return dict(grave=m.read(grave + 0xA31C, 0x2C), value=m.r32(grave + 0xA338), job=m.r32(grave + 0xA33C),
                regs=m.regs(UC_X86_REG_EBX, UC_X86_REG_ESP, UC_X86_REG_EDI, UC_X86_REG_ESI, UC_X86_REG_EBP),
                stack=m.read(sp, 0x40), eip=m.uc.reg_read(UC_X86_REG_EIP))


def setup_vv2(m: Machine, skills, pref, age, elder=0):
    world, g = m.BIG, m.SCRATCH
    idx, place = 2, 5
    rec = world + idx * 0xE48C
    m.w32(world + 0xE574D4, g)
    m.w32(rec + 0x530, age)
    m.uc.mem_write(rec + 0x564, b"Malo Kalama\0")
    for k, s in enumerate(skills):
        m.w32(rec + 0x7E4 + 4 * k, s)
    m.w32(rec + 0x7F8, pref)
    m.uc.mem_write(rec + 0x7FC, bytes([elder]))
    burier = m.SCRATCH + 0x100000
    m.w32(burier + 0x60, idx)
    grave = g + place * 0x7C
    sp = m.STACK + 0x80000
    m.uc.reg_write(UC_X86_REG_ESP, sp)
    m.uc.reg_write(UC_X86_REG_ESI, world)
    m.uc.reg_write(UC_X86_REG_EDI, burier)
    m.uc.reg_write(UC_X86_REG_EBP, place * 0x7C)
    m.uc.reg_write(UC_X86_REG_EBX, 0x5EB5EB5E)
    m.uc.reg_write(UC_X86_REG_ECX, place)
    m.uc.reg_write(UC_X86_REG_EAX, grave + 0x2EB80)
    return grave, sp


def run_vv2(exe: bytes, skills, pref, age) -> dict:
    m = Machine(exe)
    grave, sp = setup_vv2(m, skills, pref, age)
    m.uc.emu_start(0x465063, 0x4650D9, count=20000)
    return dict(grave=m.read(grave + 0x2EB0C, 0x7C), value=m.r32(grave + 0x2EB78), job=m.r32(grave + 0x2EB7C),
                regs=m.regs(UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EBX, UC_X86_REG_ESP, UC_X86_REG_ESI,
                            UC_X86_REG_EDI, UC_X86_REG_EBP),
                flags=m.uc.reg_read(UC_X86_REG_EFLAGS) & FLAGS, stack=m.read(sp, 0x40))


def vv2_epitaph_job(exe: bytes, skills, pref) -> int:
    """An adult's burial from the grave write to the epitaph's job switch: the job (1..5) its pair is picked by."""
    m = Machine(exe)
    setup_vv2(m, skills, pref, 900)
    m.uc.emu_start(0x465063, 0x4651BD, count=20000)
    return m.uc.reg_read(UC_X86_REG_EDX)


def run_vv3(exe: bytes, skills, pref, age, chief=0) -> dict:
    m = Machine(exe)
    rec, entry, this = m.SCRATCH, m.SCRATCH + 0x10000, m.SCRATCH + 0x20000
    place = 4
    m.w32(rec + 0xDC4, age)
    m.w32(rec + 0xE7C, 2)
    m.uc.mem_write(rec + 0xE80, bytes([chief]))
    for k, s in enumerate(skills):
        m.w32(rec + 0xEAC + 4 * k, s)
    m.w32(rec + 0xEC0, pref)
    sp = m.STACK + 0x80000
    m.w32(sp + 0x10, this)
    m.w32(sp + 0x18, rec)
    m.uc.reg_write(UC_X86_REG_ESP, sp)
    m.uc.reg_write(UC_X86_REG_EBP, rec)
    m.uc.reg_write(UC_X86_REG_ESI, entry)
    m.uc.reg_write(UC_X86_REG_EDI, place)
    m.uc.emu_start(0x45504E, 0x4550AC, count=20000)
    stone = this + place * 0x2C
    return dict(entry=m.read(entry, 0x30), stone=m.read(stone, 8), job=m.r32(entry + 0x20),
                value=m.r32(entry + 0x24), stone_value=m.r32(stone + 4),
                regs=m.regs(UC_X86_REG_EBX, UC_X86_REG_ESP, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP),
                stack=m.read(sp, 0x40))


def run_v45(game: int, exe: bytes, skills, pref, age) -> dict:
    m = Machine(exe)
    lo, hi = gen.V45[game][:2]
    rec, entry = m.SCRATCH, m.SCRATCH + 0x10000
    m.w32(rec + 0x1B8C, age)
    m.w32(rec + 0x1B90, age & 1)
    m.w32(rec + 0x1BB8, 7)
    m.w32(rec + 0x1BBC, 3)
    m.w32(rec + 0x1C44, 1)
    for k, s in enumerate(skills):
        m.wf(rec + 0x1C5C + 4 * k, s)
    m.w32(rec + PREF_OFFSET[game], pref)
    sp = m.STACK + 0x80000
    for k, value in enumerate((entry, rec + 0x1B9C, 0x19)):      # the strncpy's arguments, not yet dropped
        m.w32(sp + 4 * k, value)
    m.uc.reg_write(UC_X86_REG_ESP, sp)
    m.uc.reg_write(UC_X86_REG_EDI, rec)
    m.uc.reg_write(UC_X86_REG_ESI, entry)
    m.uc.reg_write(UC_X86_REG_EBP, 9)
    m.uc.emu_start(lo, hi, count=20000)
    return dict(entry=m.read(entry, 0x38), job=m.r32(entry + 0x28), value=m.r32(entry + 0x2C),
                al=m.uc.reg_read(UC_X86_REG_EAX) & 0xFF,
                regs=m.regs(UC_X86_REG_EBX, UC_X86_REG_ESP, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP),
                flags=m.uc.reg_read(UC_X86_REG_EFLAGS) & FLAGS, stack=m.read(sp + 0xC, 0x40))


def run(game: int, exe: bytes, skills, pref, age) -> dict:
    if game == 1:
        return run_vv1(exe, skills, pref, age)
    if game == 2:
        return run_vv2(exe, skills, pref, age)
    if game == 3:
        return run_vv3(exe, skills, pref, age)
    return run_v45(game, exe, skills, pref, age)


def without(d: dict, *keys) -> dict:
    return {k: v for k, v in d.items() if k not in keys}


def masked(game: int, d: dict) -> dict:
    """The writes the preference may change taken out: the job and value fields (and The Secret City's
    gravestone value)."""
    out = dict(d)
    if game == 1:
        out["grave"] = d["grave"][:0x1C]                         # name; value and job compared on their own
    elif game == 2:
        out["grave"] = d["grave"][:0x6C] + d["grave"][0x74:]
    elif game == 3:
        out["entry"] = d["entry"][:0x20] + d["entry"][0x28:]
        out["stone"] = d["stone"][:4]
    else:
        out["entry"] = d["entry"][:0x28] + d["entry"][0x30:]
    return without(out, "job", "value", "stone_value")


@unittest.skipUnless(HAVE_EMULATOR, "unicorn/pefile not installed")
class PreferredJobGraves(unittest.TestCase):
    def test_the_manifests_are_the_generators(self):
        for game in range(1, 6):
            stock_path(game)
            path = ROOT / "data" / f"vv{game}_preferred_job_graves_feature.json"
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), gen.feature(game), game)

    def test_each_burial_writer_stock_and_patched(self):
        """Alone, and with Fix Vanilla Bugs (A New Home and The Lost Children: it aims the name copy's call, which
        this row leaves where it is, at strcpy)."""
        for game, base in [(g, ()) for g in range(1, 6)] + [(1, ("vv1_fix_vanilla_bugs",)),
                                                            (2, ("vv2_fix_vanilla_bugs",))]:
            stock, patched = rendered(game, base), rendered(game, base + (IDS[game],))
            checked = 0
            for skills, pref, age in cases(game):
                s = run(game, stock, skills, pref, age)
                p = run(game, patched, skills, pref, age)
                case = (game, skills, pref, age)
                self.assertEqual((s["job"], s["value"]), stock_best(game, skills), case)
                want = preferred(game, skills, pref) or stock_best(game, skills)
                self.assertEqual((p["job"], p["value"]), want, case)
                if game == 3:
                    self.assertEqual(s["stone_value"], s["value"], case)
                    self.assertEqual(p["stone_value"], p["value"], case)
                if preferred(game, skills, pref) is None:
                    self.assertEqual(p, s, case)
                else:
                    self.assertEqual(masked(game, p), masked(game, s), case)
                checked += 1
            self.assertGreater(checked, 200, game)

    def test_the_lost_childrens_epitaph_follows_the_grave(self):
        stock, patched = rendered(2, ()), rendered(2, (IDS[2],))
        for skills, pref, _age in cases(2):
            s = vv2_epitaph_job(stock, skills, pref)
            p = vv2_epitaph_job(patched, skills, pref)
            best_job = stock_best(2, skills)[0] or 2           # every skill 0: Parenting's pair
            self.assertEqual(s, best_job, (skills, pref))
            self.assertEqual(p, (preferred(2, skills, pref) or (best_job,))[0], (skills, pref))

    def test_off_by_default_on_in_owners_defaults(self):
        import vv_fun_patcher_gui as gui
        public = {p.id: p for p in patcher.load_public_fun_patches()}
        for game, pid in IDS.items():
            self.assertIn(pid, public)
            self.assertEqual(public[pid].name, "Checked Skill Preferences are listed as Jobs on Graves")
            self.assertFalse(default_fun_patch_selection(pid), pid)
            self.assertEqual(patcher.patch_requirement_text(public[pid], list(public.values())),
                             "Requires no other patch to be ticked.")
            self.assertIn(pid, gui.DEFAULT_OFF_FUN_PATCH_IDS)

    def test_registered_and_documented(self):
        source = (ROOT / "src" / "vv_fun_patcher.py").read_text(encoding="utf-8")
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        log = (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8")
        howto = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        guided = {i for entry in howto["patches"] for i in entry.get("ids", [])}
        self.assertIn("PREFERRED_JOB_GRAVES_FEATURE_PATHS", source)
        for game, pid in IDS.items():
            self.assertIn(f"- Patch ID: `{pid}`", readme)
            self.assertIn(f"`{pid}`", log)
            self.assertIn(f'"data/vv{game}_preferred_job_graves_feature.json"', release)
            self.assertIn(pid, guided)

    def test_no_other_patch_claims_the_bytes(self):
        mine: dict[str, set] = {}
        for game in range(1, 6):
            for p in gen.feature(game)["patches"]:
                off = int(p["offset"], 16)
                mine.setdefault(f"vv{game}", set()).update(range(off, off + len(p["after"]) // 2))
        for record in patcher._load_fun_patch_records(include_expanded_time_warp=True):
            raw = record.raw if hasattr(record, "raw") else record
            if raw.get("id") in IDS.values() or raw.get("game_id") not in mine:
                continue
            for p in raw.get("patches", []) or []:
                try:
                    off, n = int(str(p.get("offset")), 16), len(p.get("before", "")) // 2
                except (TypeError, ValueError):
                    continue
                self.assertFalse(mine[raw["game_id"]] & set(range(off, off + n)), (raw.get("id"), p.get("offset")))

    def test_renders_with_every_other_patch_of_the_game(self):
        """With the game's default selection and with Owner's Defaults the row still applies (no byte guard
        fails)."""
        import vv_fun_patcher_gui as gui
        public = patcher.load_public_fun_patches()
        for game in range(1, 6):
            path = stock_path(game)
            ids = [p.id for p in public if p.game_id == f"vv{game}" and gui.owners_default_fun_patch_selection(p.id)]
            self.assertIn(IDS[game], ids)
            data = bytes(patcher.render_patched_bytes(path, build(game), patcher.DEFAULT_PATCH_MODE, ids)[0])
            for p in gen.feature(game)["patches"]:
                off = int(p["offset"], 16)
                self.assertEqual(data[off:off + len(p["after"]) // 2].hex().upper(), p["after"], (game, p["offset"]))


if __name__ == "__main__":
    unittest.main()
