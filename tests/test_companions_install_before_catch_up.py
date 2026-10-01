"""The Lost Children and New Believers install the runtime companions before
the first catch-up.

The runtime companions (Builders Fix Huts When Idle, which loads Builders and
Healers Work First; in The Lost Children also Healers Study Plants Regardless
of Food, Improved Pathfinding and the lesson cap) are installed by bridges in
the Origins companion.  A New Home and The Tree of Life call those bridges
from the screen-present hook, which runs from the first frame.  The Lost
Children called them only from the village compositor's Vv2MaskSweep, and New
Believers only from the villager head draw's Vv5MaskSync -- and both games
catch up the time that passed while they were closed before either runs (The
Lost Children's frame 0x42D2A0 runs the life update 0x42EBBC, whose 0x43B690
calls the catch-up worker, ahead of the compositor 0x42FAD0; New Believers
catches up at the village screen's entry, 0x425E30 from 0x4425C0, before any
head is drawn).  So a session's first load-time catch-up ran with none of the
detours in place.

Now:

* The Lost Children: the init hook at the tail of the village object's
  constructor (0x44C5E6 in 0x44C1B0, the only constructor of that object,
  reached only from the singleton getter 0x44F4E0) calls the companion's
  Vv2ExtractAtlas, which runs the bridges first.  The catch-up worker works
  on that object's villager records, so the constructor -- and the
  install -- necessarily precede it.
* New Believers: buildSavePath (0x403600), which the game runs to read the
  village's save before it can catch up its clock, is detoured to the Task9
  page's slot_capture, which now calls the companion's Vv5InstallCompanions.

Each test EMULATES that hook in the executable the patcher renders, with the
SHIPPED Origins companion and the test builds of the runtime companions
mapped: after the hook returns, every detour is in the executable's code, and
the very next catch-up decision already puts a builder to work first.
"""
from __future__ import annotations

import struct
import unittest
from pathlib import Path

import pefile
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_ESI, UC_X86_REG_ESP

import test_builders_decision_roll as harness
from test_builders_decision_roll import (
    HALT, ROWS, STOCK, STOCK_ABSENT, STOCK_PRESENT, TEST_BUILD_ABSENT, TEST_BUILDS_PRESENT, VILLAGE, Leaf,
)
from test_catch_up_work_first import G, Worker, decide, jobs, world

ROOT = Path(__file__).resolve().parents[1]
ORIGINS = {
    "vv2": ("origins2", ROOT / "assets" / "origins" / "VVFP VV2 Origins Icons.dll", "VVFP VV2 Origins Icons.dll",
            0x15000000),
    "vv5": ("origins5", ROOT / "data" / "candidates" / "VVFP VV5 Task9 Origins Icons.dll", "VVFP Origins Icons.dll",
            0x14000000),
}
for _game, (_key, _path, _name, _base) in ORIGINS.items():
    harness.TEST_DLLS[_key] = _path
    harness.MODULE_FILE[_key] = _name
    harness.BASES[_key] = _base
# kernel32 calls the Origins companions make on the way (stub `ret N`).
harness.STDCALL_BYTES.update({"lstrlenA": 4, "lstrcatA": 8, "CreateDirectoryA": 8, "GetFileAttributesA": 4,
                              "FindResourceA": 12})
ORIGINS_PRESENT = all(p.is_file() for _, p, _, _ in ORIGINS.values())

# Where the companions write their detours (stock bytes before, E9 after).
DETOURS = {
    "vv2": {0x461850: "Fix Huts: the idle scheduler's entry", 0x45FBF0: "Work First: the dispatcher",
            0x43B52D: "Work First: the catch-up research pick", 0x461A22: "Healers Study: the scheduler",
            0x43B581: "Healers Study: the catch-up worker"},
    "vv5": {0x46F070: "Fix Huts: the idle scheduler's entry", 0x46C540: "Work First: the dispatcher",
            0x46E92F: "Work First: the catch-up research pick"},
}


class EarlyWorker(Worker):
    """The Origins companions' own kernel32 calls, answered so the atlas
    extraction finds nothing to do and returns."""

    def _import(self, name: str) -> None:
        mu = self.mu
        sp = mu.reg_read(UC_X86_REG_ESP)
        arg = lambda k: struct.unpack("<I", mu.mem_read(sp + 4 + 4 * k, 4))[0]
        cstr = lambda va: bytes(mu.mem_read(va, 260)).split(b"\0")[0]
        if name == "GetModuleHandleA" and arg(0) == 0:
            mu.reg_write(UC_X86_REG_EAX, 0x400000)
        elif name == "lstrlenA":
            mu.reg_write(UC_X86_REG_EAX, len(cstr(arg(0))))
        elif name == "lstrcatA":
            mu.mem_write(arg(0), cstr(arg(0)) + cstr(arg(1)) + b"\0")
            mu.reg_write(UC_X86_REG_EAX, arg(0))
        elif name == "CreateDirectoryA":
            mu.reg_write(UC_X86_REG_EAX, 1)
        elif name == "GetFileAttributesA":
            mu.reg_write(UC_X86_REG_EAX, 0xFFFFFFFF)      # no atlas yet
        elif name == "FindResourceA":
            mu.reg_write(UC_X86_REG_EAX, 0)               # nothing to extract: return
        else:
            super()._import(name)


_DEFAULT_EXE: dict[tuple, bytes] = {}
# The population modes.  New Believers' Task9 page hooks -- slot_capture among
# them -- belong to the collection-progression and immediate-fixed modes; the
# stock mode carries the page but only the install-only stock_save_path
# detour.  The Lost Children's init hook is part of the Origins base in every
# mode.
MODES = ("stock", "collection_progression", "immediate_fixed")
SETUPS = [("vv2", "collection_progression")] + [("vv5", mode) for mode in MODES]
SLOT_SCRATCH, OWNERSHIP = 0x7B1D7C, 0x51D388


def mode_exe(game: str, mode: str) -> bytes:
    """The executable the patcher writes in `mode` for the rows."""
    if (game, mode) not in _DEFAULT_EXE:
        import vv_fun_patcher as vfp
        build = next(b for b in vfp.load_builds() if b.id == game)
        data, _ = vfp.render_patched_bytes(STOCK[game], build, mode, list(ROWS[game]))
        _DEFAULT_EXE[(game, mode)] = bytes(data)
    return _DEFAULT_EXE[(game, mode)]


def default_mode_exe(game: str) -> bytes:
    import vv_fun_patcher as vfp
    return mode_exe(game, vfp.DEFAULT_PATCH_MODE)


def early_world(game: str, mode: str | None = None, **kw) -> Worker:
    key = ORIGINS[game][0]
    base = ("fix_huts", "work_first", "healers") if game == "vv2" else ("fix_huts", "work_first")
    exe = default_mode_exe(game) if mode is None else mode_exe(game, mode)
    m = world(game, modules=base + (key,), install=False, exe=exe, **kw)
    # The pages the Origins base appends run for real (their routines call
    # each other).
    for section in pefile.PE(data=exe, fast_load=True).sections:
        if section.Name.rstrip(b"\0").startswith(b".vv"):
            start = 0x400000 + section.VirtualAddress
            m.real_ranges.append((start, start + section.Misc_VirtualSize))
    m.__class__ = EarlyWorker
    return m


def code(m: Worker, va: int, n: int = 1) -> bytes:
    return bytes(m.mu.mem_read(va, n))


def stock(game: str, va: int, n: int = 1) -> bytes:
    pe = pefile.PE(str(STOCK[game]), fast_load=True)
    return STOCK[game].read_bytes()[pe.get_offset_from_rva(va - 0x400000):][:n]


def lost_children_village_constructed(m: Worker) -> None:
    """The tail of the village constructor: `mov [esi+0xE574D8], eax` at
    0x44C5E6, which the Origins base routes through its init stub."""
    m.leaves.update({
        0x467F83: Leaf(1, lambda m, a, c, r: VILLAGE + 0x800000, cdecl=True, name="operator new"),
        0x40A270: Leaf(3, lambda m, a, c, r: VILLAGE + 0x800100, name="atlas loader"),
    })
    m.run(0x44C5E6, 0x44C5EC, {UC_X86_REG_ESI: VILLAGE, UC_X86_REG_EAX: 0x1234})   # this = the village


def new_believers_save_path_built(m: Worker, slot: int = 2) -> None:
    """buildSavePath(this, slot) from the load: its entry 0x403600 is the
    Task9 page's slot_capture detour; the stock body resumes at 0x403606."""
    m.run(0x403600, 0x403606, {UC_X86_REG_ECX: VILLAGE + 0x900000}, stack=(HALT, slot))


HOOK = {"vv2": lost_children_village_constructed, "vv5": new_believers_save_path_built}


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
@unittest.skipUnless(ORIGINS_PRESENT, "the Origins companions are not built")
class CompanionsInstallBeforeCatchUp(unittest.TestCase):

    def test_the_hook_sites_are_where_the_reasoning_needs_them(self):
        # The Lost Children: 0x44C5E6 is the tail of 0x44C1B0, which only the
        # singleton getter constructs (call at 0x44F51E after `push 0xE57500`
        # operator new), and the catch-up worker's caller 0x43B690 runs from the
        # life update at 0x42EBBC, ahead of the compositor call at 0x42FAD0.
        self.assertEqual(stock("vv2", 0x44C5E6, 6).hex().upper(), "8986D874E500")
        self.assertEqual(stock("vv2", 0x44C5EC, 1), b"\x5F")
        self.assertEqual(stock("vv2", 0x44F4FF, 5), b"\x68\x00\x75\xE5\x00")
        rel = struct.unpack("<i", stock("vv2", 0x44F51F, 4))[0]
        self.assertEqual(0x44F523 + rel, 0x44C1B0)
        rel = struct.unpack("<i", stock("vv2", 0x42EBBD, 4))[0]
        self.assertEqual(0x42EBC1 + rel, 0x43B690)
        rel = struct.unpack("<i", stock("vv2", 0x42FAD1, 4))[0]
        self.assertEqual(0x42FAD5 + rel, 0x445B50)
        # New Believers: buildSavePath's prologue, the detour's preimage.
        self.assertEqual(stock("vv5", 0x403600, 6).hex().upper(), "81EC04010000")

    def test_before_the_hook_nothing_is_installed(self):
        for game, mode in SETUPS:
            m = early_world(game, mode)
            for va, what in DETOURS[game].items():
                with self.subTest(game=game, mode=mode, site=what):
                    self.assertNotEqual(code(m, va), b"\xE9")

    def test_the_hook_installs_every_detour(self):
        for game, mode in SETUPS:
            m = early_world(game, mode)
            HOOK[game](m)
            loaded = [c[1] for c in m.calls if c[0] == "LoadLibraryA"]
            for va, what in DETOURS[game].items():
                with self.subTest(game=game, mode=mode, site=what):
                    self.assertEqual(code(m, va), b"\xE9", f"{what} not installed; loaded {loaded}")

    def test_the_first_catch_up_is_already_boosted(self):
        for game, mode in SETUPS:
            g = G[game]
            with self.subTest(game=game, mode=mode):
                m = early_world(game, mode, selected=g["healing"], pick=g["other"])
                HOOK[game](m)
                m.roll_force(1)
                decide(m)
                self.assertEqual(jobs(m), [g["healing"]])
                # ... and the research pick, through the catch-up site.
                m = early_world(game, mode, selected=g["healing"], pick=g["research"])
                HOOK[game](m)
                m.roll_force(1)
                decide(m)
                self.assertEqual(jobs(m), [g["healing"]])

    def test_new_believers_slot_capture_is_the_same_in_every_mode(self):
        """Every population mode carries slot_capture whole: the slot is
        captured (village slots only), a save's backup path keeps it, and only
        a real village switch clears the Origins ownership word."""
        for mode in MODES:
            with self.subTest(mode=mode):
                m = early_world("vv5", mode)
                HOOK["vv5"](m, 1)
                m.w32(OWNERSHIP, 0x3)
                for slot in (1 + 0x14, 1, 0):          # a save of village 1, the meta file
                    HOOK["vv5"](m, slot)
                    self.assertEqual((m.u32(SLOT_SCRATCH), m.u32(OWNERSHIP)), (1, 0x3))
                HOOK["vv5"](m, 3)                       # another village
                self.assertEqual((m.u32(SLOT_SCRATCH), m.u32(OWNERSHIP)), (3, 0))

    def test_the_lost_children_healer_studies_in_the_first_catch_up(self):
        m = early_world("vv2", selected=1, pick=1, task=9, cont=1)
        HOOK["vv2"](m)
        m.roll_force(1)
        decide(m)
        self.assertEqual([c[1] for c in m.calls if c[0] == "continue"], [(harness.INDEX, 40)])

    def test_hooking_again_installs_nothing_twice(self):
        for game, mode in SETUPS:
            with self.subTest(game=game, mode=mode):
                m = early_world(game, mode)
                HOOK[game](m)
                image = {va: code(m, va, 5) for va in DETOURS[game]}
                m.calls = []
                HOOK[game](m)
                self.assertEqual({va: code(m, va, 5) for va in DETOURS[game]}, image)
                self.assertNotIn("VirtualProtect", [c[0] for c in m.calls])


if __name__ == "__main__":
    unittest.main()
