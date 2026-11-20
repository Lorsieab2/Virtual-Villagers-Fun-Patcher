"""New Believers with Story / Cheat Upgrades never builds its game object again inside its own constructor.

The crash (v1.35.92 - v1.35.97, seen 2026-11-18): the game started, and died within seconds with a stack overflow
(c00000fd in _chkstk at 0x47EBB7).  The chain, read from the crash dump and the executables:

* the game object's getter 0x425950 builds the object while its word 0x4DACE0 is 0 (operator new, then the
  constructor 0x425880, which reads the settings through 0x425640 -- a 0x17E04-byte frame -- and 0x403770);
* 0x403770 calls buildSavePath (0x403600), whose detour runs the Origins companion's Vv5InstallCompanions;
* that runs the Story DLL's install (vvfp_story_bridge), whose Faith -> Heathen notice tick asks the host whether
  the game clock runs (time_skip_running);
* New Believers' answer called the getter 0x425950 -- with 0x4DACE0 still 0, because the constructor has not
  returned -- which built the object again: the constructor again, buildSavePath again, the install again ... about
  ten rounds of 0x17E04 bytes fill the 1 MB stack.

This test EMULATES that hook in the executable the patcher renders, with the SHIPPED Origins companion and the
SHIPPED Story DLL mapped, while the object is being built (0x4DACE0 = 0).  The getter is emulated as the game runs
it then: it builds the object, whose constructor calls buildSavePath again (the detour re-entered), with its frame.
Before the fix the hook re-enters itself until the stack is gone; now the callbacks read 0x4DACE0 and the getter is
never called, so the hook returns once.
"""
from __future__ import annotations

import struct
import unittest
from pathlib import Path

from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP

import test_builders_decision_roll as harness
from test_builders_decision_roll import HALT, ROWS, STOCK_ABSENT, STOCK_PRESENT, TEST_BUILD_ABSENT, TEST_BUILDS_PRESENT, VILLAGE

ROOT = Path(__file__).resolve().parents[1]
STORY_DLL = ROOT / "assets" / "story_upgrades" / "VVFP Story Upgrades.dll"
harness.TEST_DLLS.setdefault("story", STORY_DLL)
harness.MODULE_FILE.setdefault("story", "VVFP Story Upgrades.dll")
harness.BASES.setdefault("story", 0x16000000)

import test_catch_up_work_first as work_first  # noqa: E402
import test_companions_install_before_catch_up as install  # noqa: E402

GETTER = 0x425950            # the game object's getter (builds it while the word is 0)
OBJECT_WORD = 0x4DACE0       # where the getter keeps the object
SAVE_PATH = 0x403600         # buildSavePath: the Task9 page's detour (Vv5InstallCompanions)
RESUME = 0x403606            # the stock body the detour returns to
FRAME = 0x17E04 + 0x40       # 0x425640's own frame (its _chkstk size) and the constructor's
STACK = 0x100000             # the game's 1 MB main-thread stack
STORY_ROWS = ("vv5_origins_village_wide_upgrades", "vv5_story_cheat_upgrades")


class _StoryWorker(install.EarlyWorker):
    """The Story DLL's own kernel32 calls on its install, answered as at game start: no sidecar file yet."""

    ANSWERS = {"CreateFileW": (28, 0xFFFFFFFF), "CreateFileA": (28, 0xFFFFFFFF), "GetTickCount": (0, 100000),
               "MultiByteToWideChar": (24, 0)}

    def _import(self, name: str) -> None:
        if name in self.ANSWERS:
            pops, value = self.ANSWERS[name]
            mu = self.mu
            sp = mu.reg_read(UC_X86_REG_ESP)
            mu.reg_write(UC_X86_REG_EAX, value)
            mu.reg_write(UC_X86_REG_ESP, sp + 4 + pops)
            mu.reg_write(UC_X86_REG_EIP, struct.unpack("<I", mu.mem_read(sp, 4))[0])
            return
        super()._import(name)


def story_world() -> _StoryWorker:
    saved_rows, saved_world = ROWS["vv5"], install.world
    ROWS["vv5"] = tuple(saved_rows) + STORY_ROWS
    install.world = lambda game, modules=(), **kw: work_first.world(game, modules=tuple(modules) + ("story",), **kw)
    try:
        install._DEFAULT_EXE.pop(("vv5", "stock"), None)
        m = install.early_world("vv5", "stock")
    finally:
        ROWS["vv5"], install.world = saved_rows, saved_world
        install._DEFAULT_EXE.pop(("vv5", "stock"), None)
    m.__class__ = _StoryWorker
    return m


def save_path_while_building(m: _StoryWorker) -> dict:
    """buildSavePath from the object's constructor (0x4DACE0 = 0), with the getter as the game runs it."""
    seen = {"rounds": 0, "stack": 0, "overflow": False}
    m.w32(OBJECT_WORD, 0)

    def getter(mu, address, size, user_data):
        if m.u32(OBJECT_WORD) != 0:
            return
        # Built again: the constructor's frames, then buildSavePath(slot 2) -- the detour once more.
        seen["rounds"] += 1
        seen["stack"] += FRAME
        if seen["stack"] >= STACK:
            seen["overflow"] = True
            mu.emu_stop()
            return
        sp = mu.reg_read(UC_X86_REG_ESP) - 8
        mu.mem_write(sp, struct.pack("<II", HALT, 2))
        mu.reg_write(UC_X86_REG_ESP, sp)
        mu.reg_write(UC_X86_REG_ECX, VILLAGE + 0x900000)
        mu.reg_write(UC_X86_REG_EIP, SAVE_PATH)

    m.mu.hook_add(UC_HOOK_CODE, getter, begin=GETTER, end=GETTER)
    m.stop_at = None
    try:
        m.run(SAVE_PATH, RESUME, {UC_X86_REG_ECX: VILLAGE + 0x900000}, stack=(HALT, 2))
    except AssertionError:
        if not seen["overflow"]:
            raise
    return seen


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
@unittest.skipUnless(install.ORIGINS_PRESENT and STORY_DLL.is_file(), "the Origins / Story companions are not built")
class Vv5StoryStartupNoRecursion(unittest.TestCase):

    def test_the_chain_is_where_the_reasoning_needs_it(self):
        exe = install.STOCK["vv5"].read_bytes()
        import pefile
        pe = pefile.PE(data=exe, fast_load=True)
        at = lambda va, n: exe[pe.get_offset_from_rva(va - 0x400000):][:n]
        # the getter tests and stores 0x4DACE0; the constructor's settings read has the 0x17E04 frame
        self.assertIn(struct.pack("<I", OBJECT_WORD), at(GETTER, 0x60))
        self.assertEqual(at(0x425640, 5), b"\xB8" + struct.pack("<I", 0x17E04))
        self.assertEqual(at(SAVE_PATH, 6).hex().upper(), "81EC04010000")

    def test_the_install_never_builds_the_game_object_again(self):
        m = story_world()
        seen = save_path_while_building(m)
        loaded = [c[1] for c in m.calls if c[0] == "LoadLibraryExW"]
        self.assertTrue(any(p.endswith("VVFP Story Upgrades.dll") for p in loaded), loaded)
        self.assertFalse(seen["overflow"], f"buildSavePath re-entered itself {seen['rounds']} times: stack overflow")
        self.assertEqual(seen["rounds"], 0)


if __name__ == "__main__":
    unittest.main()
