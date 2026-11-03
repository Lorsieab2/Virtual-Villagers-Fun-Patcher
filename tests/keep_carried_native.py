"""Keep Carried: the stock exes in unicorn with "VVFP Keep Carried.dll" (its TEST build, tests/test_dlls/) mapped and
its site written where VvfpStartup writes it, optionally beside "VVFP Improved Pathfinding.dll" (its test build).

What runs is machine code: the game's walk, blocked handler, queue, step starters and runner, and the companion's
own handler, which calls the game's map read, queue push and step start.  A New Home: the harness is
tests/farmers_emulation_vv1.py (its new-village map); the villager carries `item` and walks to `target` with the
fish job's tail behind the walk (wait, step 8, release 0xD, 0xE, 0x13, 5 -- 0x43F5D1..0x43F677), so a finished
delivery pays the food.
"""
from __future__ import annotations

import struct
from pathlib import Path

import pefile

import farmers_emulation_vv1 as fe1

ROOT = Path(__file__).resolve().parents[1]
KEEP_DLL = ROOT / "tests" / "test_dlls" / "VVFP Keep Carried.test.dll"
PATH_DLL = ROOT / "tests" / "test_dlls" / "VVFP Improved Pathfinding.test.dll"
KEEP_BASE, PATH_BASE = 0x10000000, 0x11000000
SCRATCH = 0x0D000000

_IMAGES: dict = {}


def _image(path: Path, base: int):
    key = (path, base)
    if key not in _IMAGES:
        pe = pefile.PE(str(path))
        if pe.OPTIONAL_HEADER.ImageBase != base:
            pe.relocate_image(base)
        exports = {e.name.decode(): base + e.address for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
        _IMAGES[key] = (pe.get_memory_mapped_image(ImageBase=base), exports)
    return _IMAGES[key]


def map_dll(v, path: Path, base: int) -> dict[str, int]:
    image, exports = _image(path, base)
    v.uc.mem_map(base, (len(image) + 0xFFFF) & ~0xFFFF)
    v.uc.mem_write(base, image)
    return exports


def stats(v, ex) -> dict[str, int]:
    names = ("calls", "kept", "alternates", "give_ups")
    raw = struct.unpack("<4i", bytes(v.uc.mem_read(ex["VvfpKeepCarriedStats"], 16)))
    return dict(zip(names, raw))


class Vv1Run:
    """Villager 0 carries `item` from `start` (feet) to `target` (feet), the delivery steps queued behind."""

    PUSH, START = 0x4399F0, 0x43DEF0
    SITES = ((0x43DFEE, "E87DB4FFFF"), (0x445F3B, "E83035FFFF"), (0x445F71, "E8FA34FFFF"))

    def __init__(self, start, target, *, keep: bool = True, pathfinding: bool = False, item: int = 8, seed: int = 1,
                 block_alternates: bool = False, tail: bool = True):
        self.v = v = fe1.Village(seed=seed)
        v.uc.mem_map(SCRATCH, 0x1000)
        self.ex = None
        if keep:
            self.ex = ex = map_dll(v, KEEP_DLL, KEEP_BASE)
            for which, (site, stock) in enumerate(self.SITES):
                n = v.call(ex["VvfpKeepCarriedProbeSite"], 0, 1, which, SCRATCH, SCRATCH + 0x10)
                va = struct.unpack("<I", bytes(v.uc.mem_read(SCRATCH, 4)))[0]
                assert va == site and n == 5
                assert bytes(v.uc.mem_read(va, 5)) == bytes.fromhex(stock)        # the stock call 0x439470
                v.uc.mem_write(va, bytes(v.uc.mem_read(SCRATCH + 0x10, n)))
            v.call(ex["VvfpKeepCarriedProbeReset"], 0)
        if pathfinding:
            px = map_dll(v, PATH_DLL, PATH_BASE)
            n = v.call(px["VvfpPathfindingProbeSiteBytes"], 0, 1, 0, SCRATCH, SCRATCH + 0x10, SCRATCH + 0x8)
            va = struct.unpack("<I", bytes(v.uc.mem_read(SCRATCH, 4)))[0]
            v.uc.mem_write(va, bytes(v.uc.mem_read(SCRATCH + 0x10, n)))
        if block_alternates:
            # Every alternate refused: the map read answers "blocked" (cell 1) to the companion's own calls only.
            from unicorn import UC_HOOK_CODE
            from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EIP, UC_X86_REG_ESP

            def refuse(uc, address, size, data):
                sp = uc.reg_read(UC_X86_REG_ESP)
                back = struct.unpack("<I", bytes(uc.mem_read(sp, 4)))[0]
                if KEEP_BASE <= back < KEEP_BASE + 0x100000:
                    uc.reg_write(UC_X86_REG_EAX, 1)
                    uc.reg_write(UC_X86_REG_ESP, sp + 12)
                    uc.reg_write(UC_X86_REG_EIP, back)
            v.uc.hook_add(UC_HOOK_CODE, refuse, begin=0x414200, end=0x414200)
        v.villager(feet=start)
        v.w32(v.rec(0) + 0x3C, item)
        self.queue_walk(target, tail)
        v.call(self.START, fe1.MGR, 0)
        self.trace: list = []

    def queue_walk(self, target, tail: bool = True) -> None:
        v = self.v

        def push(*a):
            v.call(self.PUSH, fe1.MGR, 0, *a)
        push(3, target[0], target[1], 0, 0, 100)
        if tail:
            push(0x12, 0, 0, 0, 0, 0xC)
            push(8, 0, 0, 1, 0, 1)
            push(0x0D, 0, 0, 0, 0, 0)
            push(0x0E, 0, 0, 0, 0, 0x11)
            push(0x13, 0, 0, 0, 0, 0)
            push(5, 0, 0, 0xA, 0, 0)

    def item(self) -> int:
        return self.v.r32(self.v.rec(0) + 0x3C)

    def go(self, frames: int = 6000):
        """Frames until villager 0's queue is empty (None if it never is)."""
        v = self.v
        for _ in range(frames):
            v.call(fe1.RUNNER, fe1.MGR, count=60_000_000)       # Improved Pathfinding's flood needs room
            v.frame += 1
            v.t += fe1.FRAME_MS / 1000.0
            self.trace.append((v.frame, v.feet(), v.queue_type(), self.item()))
            if v.queue_type() == 0:
                return v.frame
        return None
