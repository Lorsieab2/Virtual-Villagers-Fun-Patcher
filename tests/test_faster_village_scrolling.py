"""Faster Village-Scrolling (A New Home, The Lost Children; on by default).

The owner: "Updates the slow scrolling when selecting villagers and dragging
the screen to VV3-VV5's behavior" -- including a villager selected from the
Details screen.  A New Home and The Lost Children share The Secret City's
camera design (same 800x600 screen, 30 fps, viewport 205,5-795,480) but:

* follow the selected villager (the Details-screen path too) at a flat
  2 px/frame where The Secret City adds/subtracts 1 px every frame;
* scroll while carrying a villager at distance/40 from (518,247) with a
  120 px dead zone, where The Secret City uses distance/20 from the viewport
  centre (500,242) and no dead zone;
* (A New Home only) do not zero the vertical speed when the view clamps at
  the top/bottom, which The Lost Children and The Secret City do.
Dragging the screen is already 1:1 in every game.

Everything here RUNS the patcher's rendered bytes in an emulator: the stock
bytes match a model of the stock behaviour and the patched bytes a model of
The Secret City's, at every margin and bound.
"""
from __future__ import annotations

import random
import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI, UC_X86_REG_EDX,
    UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_fun_patcher as vfp  # noqa: E402

STOCK = ROOT / "research" / "stock-executables"
NAMES = {"vv1": "A New Home", "vv2": "The Lost Children"}
BASE = 0x400000
SCR, VIL, ARR, STK = 0x10000000, 0x20000000, 0x30000000, 0x40000000
LAY = {"vv1": dict(stride=0x3D8, vx=0x2D8, vy=0x2DC, L=0x298, T=0x29C, R=0x2A0, B=0x2A4),
       "vv2": dict(stride=0xE48C, vx=0x228, vy=0x22C, L=0x1E8, T=0x1EC, R=0x1F0, B=0x1F4)}
_FILES: dict[tuple[str, bool], bytes] = {}


def _file(game: str, patched: bool) -> bytes:
    if (game, patched) not in _FILES:
        exe = STOCK / f"Virtual Villagers - {NAMES[game]}.exe"
        if patched:
            build = next(b for b in vfp.load_builds() if b.id == game)
            data, applied = vfp.render_patched_bytes(exe, build, "immediate_fixed",
                                                     [f"{game}_faster_village_scrolling"])
            assert f"feature:{game}_faster_village_scrolling" in {r["owner"] for r in applied}
            _FILES[(game, patched)] = bytes(data)
        else:
            _FILES[(game, patched)] = exe.read_bytes()
    return _FILES[(game, patched)]


def mk(game: str, patched: bool) -> Uc:
    data = _file(game, patched)
    pe = pefile.PE(data=data, fast_load=True)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(BASE, 0x200000)
    for s in pe.sections:
        va = BASE + s.VirtualAddress
        if va < BASE + 0x200000:
            mu.mem_write(va, data[s.PointerToRawData:s.PointerToRawData + s.SizeOfRawData][:BASE + 0x200000 - va])
    for a in (SCR, VIL, ARR, STK):
        mu.mem_map(a, 0x200000)
    return mu


def rd(mu, a):
    return struct.unpack("<i", mu.mem_read(a, 4))[0]


def wr(mu, a, v):
    mu.mem_write(a, struct.pack("<i", v))


def run_follow(game, patched, vx0, vy0, rx, ry, sx, sy):
    L = LAY[game]
    mu = mk(game, patched)
    wr(mu, SCR + 0x10, VIL)
    wr(mu, SCR + 0x20, ARR)
    wr(mu, SCR + L["vx"], vx0)
    wr(mu, SCR + L["vy"], vy0)
    wr(mu, VIL + 8, sx)
    wr(mu, VIL + 0xC, sy)
    idx = 3
    wr(mu, ARR + idx * L["stride"] + 4, rx)
    wr(mu, ARR + idx * L["stride"] + 8, ry)
    mu.reg_write(UC_X86_REG_ESI, SCR)
    mu.reg_write(UC_X86_REG_EBX, 0)
    mu.reg_write(UC_X86_REG_ESP, STK + 0x100000)
    mu.reg_write(UC_X86_REG_EAX, idx)
    if game == "vv1":
        mu.reg_write(UC_X86_REG_EDX, VIL)
        start, end = 0x423F24, 0x423F89
    else:
        mu.reg_write(UC_X86_REG_ECX, VIL)
        start, end = 0x42F7AF, 0x42F814
    mu.emu_start(start, end, count=200)
    village = mu.reg_read(UC_X86_REG_EDX if game == "vv1" else UC_X86_REG_ECX)
    return rd(mu, SCR + L["vx"]), rd(mu, SCR + L["vy"]), village


def vv3_follow(v, d, lo, hi):
    return v - 1 if d < lo else (0 if d <= hi else v + 1)


def stock_follow(v, d, lo, hi):
    return -2 if d < lo else (0 if d <= hi else 2)


def run_clamp(patched, x, y, vx, vy):
    L = LAY["vv1"]
    mu = mk("vv1", patched)
    wr(mu, SCR + 0x10, VIL)
    for k, v in zip(("L", "T", "R", "B"), (205, 5, 795, 480)):
        wr(mu, SCR + L[k], v)
    wr(mu, SCR + L["vx"], vx)
    wr(mu, SCR + L["vy"], vy)
    wr(mu, VIL + 8, x)
    wr(mu, VIL + 0xC, y)
    mu.reg_write(UC_X86_REG_ESI, SCR)
    mu.reg_write(UC_X86_REG_EBX, 0)
    mu.reg_write(UC_X86_REG_ESP, STK + 0x100000)
    mu.emu_start(0x423FD6, 0x42402D, count=200)
    return rd(mu, VIL + 8), rd(mu, VIL + 0xC), rd(mu, SCR + L["vx"]), rd(mu, SCR + L["vy"])


def model_clamp(x, y, vx, vy, zero_y):
    l, t, r, b = 205, 5, 795, 480
    if x < -l:
        x, vx = -l, 0
    elif x > 1680 - r:
        x, vx = 1680 - r, 0
    if y < -t:
        y, vy = -t, (0 if zero_y else vy)
    elif y > t - b + 1680:
        y, vy = t - b + 1680, (0 if zero_y else vy)
    return x, y, vx, vy


def run_hold(game, patched, cx, cy):
    L = LAY[game]
    mu = mk(game, patched)
    mu.reg_write(UC_X86_REG_ESI, SCR)
    mu.reg_write(UC_X86_REG_ESP, STK + 0x100000)
    if game == "vv1":
        mu.reg_write(UC_X86_REG_EBP, cx)
        mu.reg_write(UC_X86_REG_EBX, cy)
        start, end = 0x425963, 0x4259CD
    else:
        mu.reg_write(UC_X86_REG_EBX, cx)
        mu.reg_write(UC_X86_REG_EDI, cy)
        start, end = 0x4316DD, 0x431747
    mu.emu_start(start, end, count=200)
    return rd(mu, SCR + L["vx"]), rd(mu, SCR + L["vy"])


def ctrunc(a, b):
    q = abs(a) // b
    return q if a >= 0 else -q


class FasterScrollingTests(unittest.TestCase):
    def test_following_a_selected_villager(self):
        rng = random.Random(7)
        for game in NAMES:
            for patched, model in ((False, stock_follow), (True, vv3_follow)):
                with self.subTest(game=game, patched=patched):
                    for _ in range(400):
                        vx0, vy0 = rng.randint(-60, 60), rng.randint(-60, 60)
                        sx, sy = rng.randint(-205, 885), rng.randint(-5, 1205)
                        dx = rng.choice([244, 245, 246, 734, 735, 736, rng.randint(-400, 1200)])
                        dy = rng.choice([44, 45, 46, 379, 380, 381, rng.randint(-400, 1000)])
                        got = run_follow(game, patched, vx0, vy0, sx + dx, sy + dy, sx, sy)
                        self.assertEqual(got, (model(vx0, dx, 245, 735), model(vy0, dy, 45, 380), VIL),
                                         (vx0, vy0, dx, dy))

    def test_a_new_home_clamp_also_stops_vertical_speed(self):
        rng = random.Random(11)
        for patched in (False, True):
            with self.subTest(patched=patched):
                for _ in range(400):
                    x = rng.choice([-206, -205, -204, 884, 885, 886, rng.randint(-600, 1400)])
                    y = rng.choice([-6, -5, -4, 1204, 1205, 1206, rng.randint(-600, 1600)])
                    vx, vy = rng.randint(-50, 50), rng.randint(-50, 50)
                    self.assertEqual(run_clamp(patched, x, y, vx, vy), model_clamp(x, y, vx, vy, patched),
                                     (x, y, vx, vy))

    def test_carrying_a_villager_to_the_edge(self):
        for game in NAMES:
            for patched in (False, True):
                with self.subTest(game=game, patched=patched):
                    for cx in range(225, 776, 3):
                        for cy in (25, 100, 200, 242, 247, 300, 420):
                            if patched:
                                want = (ctrunc(cx - 500, 20), ctrunc(cy - 242, 20))
                            else:
                                vx, vy = ctrunc(cx - 518, 40), ctrunc(cy - 247, 40)
                                want = (vx if abs(vx) >= 3 else 0, vy if abs(vy) >= 3 else 0)
                            self.assertEqual(run_hold(game, patched, cx, cy), want, (cx, cy))

    def test_on_by_default_and_documented(self):
        from vv_fun_patcher_gui import default_fun_patch_selection
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for game in NAMES:
            with self.subTest(game=game):
                self.assertTrue(default_fun_patch_selection(f"{game}_faster_village_scrolling"))
                self.assertIn(f"`{game}_faster_village_scrolling`", readme)


if __name__ == "__main__":
    unittest.main()
