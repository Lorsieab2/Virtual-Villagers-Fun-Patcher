"""VV2 stuck walks: the stock The Lost Children exe in unicorn with "VVFP Stuck Walks.dll" (its TEST build,
tests/test_dlls/) mapped and its detour written where VvfpStartup writes it, optionally beside "VVFP Improved
Pathfinding.dll" (its test build, its two detours written where VvfpPathfindingInstall writes them).

What runs is machine code: the game's walk, band handler, queue and scheduler, and the companion's handler,
which calls the game's own map read 0x4181D0, queue push 0x449B70 and step start 0x44FBB0.  The harness is
tests/farmers_emulation_vv2.py (the grown village's map) and the herb 6 study of
tests/vv2_stuck_villager_emulation.py.
"""
from __future__ import annotations

import struct
from pathlib import Path

import pefile

import farmers_emulation_vv2 as fe
from vv2_stuck_villager_emulation import BAND_JA, HERB6_JOB, queue

ROOT = Path(__file__).resolve().parents[1]
STUCK_DLL = ROOT / "tests" / "test_dlls" / "VVFP Stuck Walks.test.dll"
PATH_DLL = ROOT / "tests" / "test_dlls" / "VVFP Improved Pathfinding.test.dll"
STUCK_BASE, PATH_BASE = 0x10000000, 0x11000000
SCRATCH = 0x0D000000            # probe buffers
BAND = 0x44FCB0

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


def _map(v: fe.Village, path: Path, base: int) -> dict[str, int]:
    image, exports = _image(path, base)
    v.uc.mem_map(base, (len(image) + 0xFFFF) & ~0xFFFF)
    v.uc.mem_write(base, image)
    return exports


class NativeRun:
    """Villager 0 starts the herb 6 study at `start` (feet).  stuck_walks: the companion installed;
    pathfinding: Improved Pathfinding installed too."""

    def __init__(self, start, *, stuck_walks: bool = True, pathfinding: bool = False, seed: int = 1,
                 carried: int | None = None, block_alternates: bool = False):
        self.v = v = fe.Village(seed=seed, state=fe.grown_state())
        v.uc.mem_map(SCRATCH, 0x1000)
        self.stock_hits: list[tuple] = []          # band hits that reached the stock handler's dispatch
        self.ai: list[int] = []
        self.ex = None
        if stuck_walks:
            self.ex = ex = _map(v, STUCK_DLL, STUCK_BASE)
            n = v.call(ex["VvfpStuckWalksProbeSite"], 0, 2, SCRATCH, SCRATCH + 0x10)
            va = struct.unpack("<I", bytes(v.uc.mem_read(SCRATCH, 4)))[0]
            assert va == BAND and n == 5
            assert bytes(v.uc.mem_read(BAND, 5)) == bytes.fromhex("8B44240856")   # the stock bytes
            v.uc.mem_write(va, bytes(v.uc.mem_read(SCRATCH + 0x10, n)))
            v.call(ex["VvfpStuckWalksProbeReset"], 0)
        if pathfinding:
            px = _map(v, PATH_DLL, PATH_BASE)
            for which in (0, 1):
                n = v.call(px["VvfpPathfindingProbeSiteBytes"], 0, 2, which, SCRATCH, SCRATCH + 0x10,
                           SCRATCH + 0x8)
                va = struct.unpack("<I", bytes(v.uc.mem_read(SCRATCH, 4)))[0]
                v.uc.mem_write(va, bytes(v.uc.mem_read(SCRATCH + 0x10, n)))
        if block_alternates:
            # Every alternate refused: the game's map read answers "blocked" (cell 1) to the companion's
            # own calls only (return address inside the DLL), so its ring search finds nothing.
            v.uc.hook_add(fe.UC_HOOK_CODE, self._refuse, begin=0x4181D0, end=0x4181D0)
        v.villager(skills={"healing": 30}, preference=0, health=100, feet=start)
        if carried is not None:
            v.w32(v.rec(0) + 0x44, carried)
        v.uc.hook_add(fe.UC_HOOK_CODE, self._band, begin=BAND_JA, end=BAND_JA)
        v.uc.hook_add(fe.UC_HOOK_CODE, lambda *_: self.ai.append(v.frame), begin=fe.AI, end=fe.AI)
        v.call(HERB6_JOB, fe.MGR, 0)

    def _refuse(self, uc, address, size, data):
        sp = uc.reg_read(fe.UC_X86_REG_ESP)
        back = struct.unpack("<I", bytes(uc.mem_read(sp, 4)))[0]
        if STUCK_BASE <= back < STUCK_BASE + 0x100000:
            uc.reg_write(fe.UC_X86_REG_EAX, 1)
            uc.reg_write(fe.UC_X86_REG_ESP, sp + 12)
            uc.reg_write(fe.UC_X86_REG_EIP, back)

    def _band(self, uc, address, size, data):
        eax = uc.reg_read(fe.UC_X86_REG_EAX)
        if eax <= 3:
            self.stock_hits.append((self.v.frame, eax + 76, self.v.feet(), queue(self.v, 1)[0]))

    def stats(self) -> dict[str, int]:
        names = ("band_calls", "approaches", "loops", "alternates", "give_ups")
        raw = struct.unpack("<5i", bytes(self.v.uc.mem_read(self.ex["VvfpStuckWalksStats"], 20)))
        return dict(zip(names, raw))

    def go(self, frames: int = 5000, stop_on_ai: bool = True):
        v = self.v
        self.trace = []
        for k in range(frames):
            v.step_frame()
            self.trace.append((v.frame, v.feet(), queue(v, 1)[0]))
            if stop_on_ai and self.ai and k > 5:
                return v.frame
        return None
