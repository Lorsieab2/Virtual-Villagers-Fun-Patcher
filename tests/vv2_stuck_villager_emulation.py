"""VV2 stuck villager: emulation of the stock exe (Unicorn) and a SCRATCH fix.  Investigation only: nothing here is
installed in any patcher.  Needs the stock exe (research/stock-executables) and the grown village save copy
(research/game-data/vv2/grown_village.ldw); tests/test_vv2_stuck_villager_emulation.py skips when they are absent.

The stock code (all addresses in the stock The Lost Children exe):
  * the walk step 0x45E880 reads the map cell the villager is about to enter (0x4181D0); a cell of 76..80 calls the
    band handler 0x44FCB0 (return address 0x45EB1F or 0x45ECFA), then undoes the step (the villager does not enter the cell);
  * 0x44FCB0 for cells 76..79 queues fixed waypoints at the FRONT of the step queue (0x449B70 mode 2) and restarts
    the front step (0x44FBB0).  Cell 79 (the lines y 1210 and y 1280, x 1400..1579) queues the walk (3, 1325, 1242).
  * the herb 6 study (drop on the herb: 0x4306A2 -> 0x459130) queues the walk (3, 1611, 1391) first.
"""
from __future__ import annotations

import math
import struct

import farmers_emulation_vv2 as fe

ESP = fe.UC_X86_REG_ESP
BAND_JA = 0x44FCC2          # the band handler's `ja 0x44fdf2` (eax = cell - 76; the pushes and esi/edi are set up)
BAND_DONE = 0x44FDF2        # push edi; mov ecx, esi; call 0x44fbb0 (start the front step); pop; ret 8
GIVE_UP = 0x4492A0          # stock queue clear (also resets +0x40 and +0x44)
HERB6_JOB = 0x459130
HERB6 = (1611, 1391)
WAYPOINT = (1325, 1242)


def queue(v, n=3):
    return [struct.unpack("<6i", bytes(v.uc.mem_read(v.rec(0) + 0x4C + 24 * i, 24))) for i in range(n)]


def free(v, x, y):
    c = v.grid(x, y)
    return (c == 0 or c > 23) and not 76 <= c <= 80


def line_free(v, a, b, step=3):
    n = max(1, int(math.dist(a, b) // step))
    return all(free(v, round(a[0] + (b[0] - a[0]) * i / n), round(a[1] + (b[1] - a[1]) * i / n)) for i in range(n + 1))


class Run:
    """Villager 0 starts the herb 6 study at `start` (feet).  fix=False: the stock exe.  fix=True: the scratch fix."""

    def __init__(self, start, fix=False, seed=1, block_alternates=False):
        self.v = v = fe.Village(seed=seed, state=fe.grown_state())
        v.villager(skills={"healing": 30}, preference=0, health=100, feet=start)
        self.fix, self.block = fix, block_alternates
        self.hits: list[tuple] = []       # (frame, cell, feet, queue front, caller)
        self.ai: list[int] = []
        self.last_hit = -10 ** 9
        self.episodes: list[tuple[int, int]] = []
        self.tried: set[tuple[int, int]] = set()
        self.fixes: list[tuple] = []
        self.gave_up = None
        v.uc.hook_add(fe.UC_HOOK_CODE, self._band, begin=BAND_JA, end=BAND_JA)
        v.uc.hook_add(fe.UC_HOOK_CODE, lambda *_: self.ai.append(v.frame), begin=fe.AI, end=fe.AI)
        v.call(HERB6_JOB, fe.MGR, 0)

    def _insert_front(self, entry):
        v = self.v
        base = v.rec(0) + 0x4C
        if 0 < v.r32(v.rec(0) + 0x58) and v.r32(v.rec(0) + 0x58) > 0x1F4:
            v.w32(v.rec(0) + 0x58, 1)
        for n in range(48, 0, -1):
            v.uc.mem_write(base + 24 * n, bytes(v.uc.mem_read(base + 24 * (n - 1), 24)))
        v.uc.mem_write(base, struct.pack("<6i", *entry))

    def _band(self, uc, address, size, data):
        v = self.v
        eax = uc.reg_read(fe.UC_X86_REG_EAX)
        if eax > 3:
            return
        sp = uc.reg_read(ESP)
        ret = struct.unpack("<I", bytes(uc.mem_read(sp + 8, 4)))[0]       # after the two pushes
        feet = v.feet()
        self.hits.append((v.frame, eax + 76, feet, queue(v, 1)[0], hex(ret)))
        new_episode = v.frame - self.last_hit > 60
        self.last_hit = v.frame
        if not self.fix:
            return
        if new_episode:
            near = sum(1 for e in self.episodes if math.dist(e, feet) <= 8)
            self.episodes.append(feet)
            self.loop = near >= 2             # the third approach at the same spot: the stock redirect is cycling
        if not getattr(self, "loop", False):
            return
        target = queue(v, 1)[0]
        target = (target[1], target[2]) if target[0] == 3 else None
        if target is None:
            return
        cands = []
        for r in (12, 24, 36, 48, 60, 80):
            for k in range(16):
                a = 2 * math.pi * k / 16
                c = (round(feet[0] + r * math.cos(a)), round(feet[1] + r * math.sin(a)))
                if c in self.tried or self.block:
                    continue
                if free(v, *c) and line_free(v, feet, c) and line_free(v, c, target):
                    cands.append((math.dist(feet, c), c))
        if cands:
            c = min(cands)[1]
            self.tried.add(c)
            self.fixes.append((v.frame, feet, c))
            self._insert_front((3, c[0], c[1], 0, 2, 100))
        else:
            # no route: stock-like give up (clear the queue) but keep +0x40/+0x44 (what the villager carries)
            self.gave_up = (v.frame, v.r32(v.rec(0) + 0x44))
            base = v.rec(0) + 0x4C
            v.uc.mem_write(base - 4 + 4, bytes(24 * 50))
            v.w32(v.rec(0) + 0x50, 0)
            v.w32(v.rec(0) + 0x54, 0)
            uc.reg_write(fe.UC_X86_REG_EIP, 0x44FDFA)       # pop edi; pop esi; ret 8 (skip the step start)
            return
        uc.reg_write(fe.UC_X86_REG_EIP, BAND_DONE)

    def go(self, frames=4000, stop_on_ai=True):
        v = self.v
        self.trace = []
        for k in range(frames):
            v.step_frame()
            self.trace.append((v.frame, v.feet(), queue(v, 1)[0]))
            if stop_on_ai and self.ai and k > 5:
                return v.frame
            if self.gave_up and stop_on_ai:
                return None
        return None
