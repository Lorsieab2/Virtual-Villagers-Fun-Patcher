"""Every game's Story / Cheat Upgrades host callbacks answer "no village" before the game object exists, and never
build it.

The New Believers start-up crash (2026-11-18, tests/test_vv5_story_startup_no_recursion.py): the Story DLL's install,
run from a hook INSIDE the game object's constructor, asked the Origins companion whether the clock runs, and the
answer called the object's getter -- which builds the object while its word is still 0, so it was built again, inside
its own constructor, without end.  The owner (2026-11-18): every such callback reads the game object's word directly
and never calls a getter that can build it, in all five games.

Each test maps the game's stock executable and the SHIPPED companion that hosts the Story DLL, finds the host table
the companion hands the Story DLL (vvfp_story_host: its size 0x28, then nine entries), and calls the clock callbacks
-- time_skip_running and time_skip_step -- with every game object word 0 (nothing built yet).  Every lazily-building
getter of that executable (`mov eax,[word]; test eax,eax; jnz; push size; call new ... mov [word],eax`) is watched:
none may be entered, and both callbacks answer 0.
"""
from __future__ import annotations

import re
import struct
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc, UcError
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EIP, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
STOCK_DIR = ROOT / "research" / "stock-executables"
GAMES = {
    1: ("Virtual Villagers - A New Home.exe", ROOT / "assets" / "origins" / "VVFP VV1 Origins Icons.dll"),
    2: ("Virtual Villagers - The Lost Children.exe", ROOT / "assets" / "origins" / "VVFP VV2 Origins Icons.dll"),
    3: ("Virtual Villagers - The Secret City.exe", ROOT / "data" / "candidates" / "VVFP VV3 Full Mastery Candidate.dll"),
    4: ("Virtual Villagers - The Tree of Life.exe", ROOT / "assets" / "origins" / "VVFP VV4 Origins Icons.dll"),
    5: ("Virtual Villagers - New Believers.exe", ROOT / "data" / "candidates" / "VVFP VV5 Task9 Origins Icons.dll"),
}
STOCK_PRESENT = all((STOCK_DIR / exe).is_file() for exe, _ in GAMES.values())
DLL_BASE = 0x10000000
STUBS = 0x7C000000
HALT = 0x0E000000
STACK_TOP = 0x0F000000
HOST_SIZE = 0x28                 # sizeof(vvfp_story_host): the size, then nine entries
STEP, RUNNING = 0x14, 0x1C       # time_skip_step(years), time_skip_running()
GETTER = re.compile(rb"\xA1(....)\x85\xC0(?:\x75.|\x0F\x85....)(?:\x68....|\x6A.)\xE8", re.S)


def building_getters(exe: Path) -> dict[int, int]:
    """Each lazily-building getter of `exe`: its entry -> the word it keeps the object in."""
    pe = pefile.PE(str(exe), fast_load=True)
    ib = pe.OPTIONAL_HEADER.ImageBase
    img = pe.get_memory_mapped_image()
    text = next(s for s in pe.sections if s.Name.startswith(b".text"))
    lo = text.VirtualAddress
    code = img[lo:lo + text.Misc_VirtualSize]
    found = {}
    for m in GETTER.finditer(code):
        if b"\xA3" + m.group(1) not in code[m.start():m.start() + 0x80]:
            continue
        s = m.start()          # the entry: back to the padding before the function
        while s > m.start() - 0x40 and code[s - 1] not in (0xCC, 0x90):
            s -= 1
        found[ib + lo + s] = struct.unpack("<I", m.group(1))[0]
    return found


class Process:
    """The executable at its base and the companion relocated to DLL_BASE; every import halts the run."""

    def __init__(self, exe: Path, dll: Path):
        self.mu = mu = Uc(UC_ARCH_X86, UC_MODE_32)
        pe = pefile.PE(str(exe))
        img = pe.get_memory_mapped_image()
        self.exe_base = pe.OPTIONAL_HEADER.ImageBase
        # the image, and the zeroed pages the patcher's appended sections occupy beyond it (nothing built, no slot)
        mu.mem_map(self.exe_base, 0x800000)
        mu.mem_write(self.exe_base, bytes(img))
        d = pefile.PE(str(dll))
        d.relocate_image(DLL_BASE)
        dimg = bytearray(d.get_memory_mapped_image(ImageBase=DLL_BASE))
        mu.mem_map(STUBS, 0x10000)
        mu.mem_write(STUBS, b"\xF4" * 0x10000)
        self.imports = {}
        stub = STUBS
        for entry in getattr(d, "DIRECTORY_ENTRY_IMPORT", []):
            for imp in entry.imports:
                struct.pack_into("<I", dimg, imp.address - DLL_BASE, stub)
                self.imports[stub] = imp.name.decode() if imp.name else f"#{imp.ordinal}"
                stub += 4
        mu.mem_map(DLL_BASE, (len(dimg) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(DLL_BASE, bytes(dimg))
        self.dll = d
        self.dll_size = len(dimg)
        mu.mem_map(HALT, 0x1000)
        mu.mem_write(HALT, b"\xF4")
        mu.mem_map(STACK_TOP - 0x40000, 0x40000)
        self.entered: list[int] = []
        self.unanswered: list[str] = []
        mu.hook_add(UC_HOOK_CODE, self._import, begin=STUBS, end=STUBS + 0xFFFF)

    # The companions' population-mode probe asks VirtualQuery about the executable's pages: no answer (0).
    ANSWERS = {"VirtualQuery": (12, 0)}

    def _import(self, mu, address, size, user):
        name = self.imports.get(address)
        if name not in self.ANSWERS:
            self.unanswered.append(str(name))
            mu.emu_stop()
            return
        pops, value = self.ANSWERS[name]
        sp = mu.reg_read(UC_X86_REG_ESP)
        mu.reg_write(UC_X86_REG_EAX, value)
        mu.reg_write(UC_X86_REG_ESP, sp + 4 + pops)
        mu.reg_write(UC_X86_REG_EIP, struct.unpack("<I", mu.mem_read(sp, 4))[0])

    def watch(self, getters) -> None:
        def hit(mu, address, size, user):
            self.entered.append(address)
            mu.emu_stop()
        for entry in getters:
            self.mu.hook_add(UC_HOOK_CODE, hit, begin=entry, end=entry)

    def host_table(self) -> int:
        """The vvfp_story_host the companion hands the Story DLL: the size, then entries in the companion's code."""
        text = next(s for s in self.dll.sections if s.Name.startswith(b".text"))
        lo, hi = DLL_BASE + text.VirtualAddress, DLL_BASE + text.VirtualAddress + text.Misc_VirtualSize
        img = bytes(self.mu.mem_read(DLL_BASE, self.dll_size))
        hits = []
        for off in range(0, len(img) - HOST_SIZE, 4):
            if struct.unpack_from("<I", img, off)[0] != HOST_SIZE:
                continue
            f = struct.unpack_from("<9I", img, off + 4)
            # slot, mask_get, mask_set, step, settled, running: always the companion's own code
            if all(lo <= f[k] < hi for k in (0, 1, 2, 4, 5, 6)) and all(v == 0 or lo <= v < hi for v in f):
                hits.append(DLL_BASE + off)
        if len(hits) != 1:
            raise AssertionError(f"host table not unique: {[hex(h) for h in hits]}")
        return hits[0]

    def call(self, fn: int, *args: int) -> int:
        mu = self.mu
        esp = STACK_TOP - 0x1000
        mu.mem_write(esp, struct.pack(f"<{1 + len(args)}I", HALT, *args))
        mu.reg_write(UC_X86_REG_ESP, esp)
        try:
            mu.emu_start(fn, HALT, count=200000)
        except UcError as exc:
            if not self.entered:
                raise AssertionError(f"emulation fault {exc} at {mu.reg_read(UC_X86_REG_EIP):#x}") from None
        pc = mu.reg_read(UC_X86_REG_EIP)
        if self.unanswered:
            raise AssertionError(f"unexpected import {self.unanswered}")
        if pc != HALT and not self.entered:
            raise AssertionError(f"stopped at {pc:#x}, not the return")
        return mu.reg_read(UC_X86_REG_EAX)


@unittest.skipUnless(STOCK_PRESENT, "the stock executables (research/stock-executables) are gitignored and absent")
class StoryHostCallbacksNeverBuild(unittest.TestCase):

    def test_the_getter_scan_finds_the_game_objects(self):
        objects = {1: (0x41D500, 0x48AEDC), 2: (0x44F4E0, 0x499F24), 3: (0x428B60, 0x4B309C),
                   4: (0x41FE70, 0x4CB51C), 5: (0x425950, 0x4DACE0)}
        for game, (entry, word) in objects.items():
            with self.subTest(game=game):
                self.assertEqual(building_getters(STOCK_DIR / GAMES[game][0]).get(entry), word)

    def test_no_village_and_nothing_built(self):
        for game, (exe, dll) in GAMES.items():
            with self.subTest(game=game):
                if not dll.is_file():
                    self.skipTest(f"{dll.name} is not built")
                getters = building_getters(STOCK_DIR / exe)
                p = Process(STOCK_DIR / exe, dll)
                for word in set(getters.values()):
                    p.mu.mem_write(word, b"\0\0\0\0")          # nothing built yet
                p.watch(getters)
                host = p.host_table()
                running, step = (struct.unpack("<I", p.mu.mem_read(host + off, 4))[0] for off in (RUNNING, STEP))
                self.assertEqual(p.call(running), 0, "running without a village")
                self.assertEqual(p.entered, [], f"a getter that builds its object was entered: "
                                                f"{[hex(a) for a in p.entered]}")
                self.assertEqual(p.call(step, 5), 0, "a time skip step without a village")
                self.assertEqual(p.entered, [], f"a getter that builds its object was entered: "
                                                f"{[hex(a) for a in p.entered]}")


if __name__ == "__main__":
    unittest.main()
