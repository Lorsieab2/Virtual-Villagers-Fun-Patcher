"""Healers Study Plants Regardless of Food (A New Home, The Lost Children).

The owner: "Healers study plants (VV1-VV2) ... regardless of the food
supply."  Below 400 (VV1) / 300 (VV2) food the stock idle scheduler calls
its continue-last-activity routine, which keeps a villager in plant-study
state 9 studying; at or above it the call is skipped.

Pinned here:

* The site is the first instruction of the general selection -- the target
  of the stock food jump, which the low-food path also falls into -- and the
  continuation, its arguments and the "done" epilogue are where the stub says.
* The DLL's stubs, RUN in an emulator over the game's own layout with the
  continuation and picker scripted: a state-9 villager at high food gets the
  stock continuation call with the stock arguments; if it starts a job the
  done epilogue runs, else the stock selection continues with the picker's
  result.  Low food, any other state, and a continuation that starts nothing
  all take the stock selection with stack and registers as stock leaves them.
* The Origins companions carry the loader bridge; the rows are registered,
  bundled, default-on and pin the DLL.
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_ECX, UC_X86_REG_EDI,
    UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
DLL = ROOT / "assets" / "healers_study" / "VVFP Healers Study.dll"
# The probes and counters the emulator drives exist only in the TEST build
# (VVFP_TEST, same source; tests/test_shipped_dlls_have_no_test_hooks.py).
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Healers Study.test.dll"
# tests/test_dlls/ is export-ignore: the release source archive carries no test
# build, so there the tests that drive one skip instead of failing.
TEST_BUILD_ABSENT = "test builds are not in the release source archive (tests/test_dlls)"
STOCK = {"vv1": ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe",
         "vv2": ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"}
STACK = 0x70000000
VILLAGE = 0x20000000
STATE = 0x30000000
RECORD = 0x38000000
INDEX = 7
PICK = 4
G = {
    "vv1": dict(no=1, site=0x44836F, resume=0x448379, done=0x44843D, picker=0x439AE0,
                cont=0x447CD0, cont_arg=0x3C, threshold=400, stride=0x3D8),
    "vv2": dict(no=2, site=0x461A22, resume=0x461A2C, done=0x461AF0, picker=0x449C60,
                cont=0x460590, cont_arg=0x28, threshold=300),
}


def _stock(game: str, va: int, n: int) -> bytes:
    pe = pefile.PE(str(STOCK[game]), fast_load=True)
    return STOCK[game].read_bytes()[pe.get_offset_from_rva(va - 0x400000):][:n]


def _emulator():
    pe = pefile.PE(str(TEST_DLL))
    base = pe.OPTIONAL_HEADER.ImageBase
    exports = {e.name.decode(): base + e.address for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
    image = pe.get_memory_mapped_image()
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(base, (len(image) + 0xFFFF) & ~0xFFFF)
    mu.mem_write(base, image)
    mu.mem_map(STACK - 0x10000, 0x20000)
    mu.mem_map(VILLAGE, 0x1000000)
    mu.mem_map(STATE, 0x100000)
    mu.mem_map(RECORD, 0x10000)
    return mu, exports


def _probe(game_no: int):
    mu, ex = _emulator()
    buf, ret, esp = STACK - 0x8000, STACK - 0x100, STACK - 0x200
    mu.mem_write(ret, b"\xF4")
    mu.mem_write(esp, struct.pack("<6I", ret, game_no, buf, buf + 0x10, buf + 0x30, buf + 0x50))
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.emu_start(ex["VvfpHealersStudyProbeSite"], ret, count=10000)
    n = mu.reg_read(UC_X86_REG_EAX)
    va, = struct.unpack("<I", mu.mem_read(buf, 4))
    stub, = struct.unpack("<I", mu.mem_read(buf + 0x50, 4))
    return n, va, bytes(mu.mem_read(buf + 0x10, n)), bytes(mu.mem_read(buf + 0x30, n)), stub


class Run:
    def __init__(self, game: str, food: int, state9: int, cont_result: int):
        g = G[game]
        stub = _probe(g["no"])[4]
        mu, _ = _emulator()
        if game == "vv1":
            mu.mem_write(STATE + 0xA2EC, struct.pack("<i", food))
            mu.mem_write(VILLAGE + INDEX * g["stride"] + 0x3B8, struct.pack("<i", state9))
        else:
            mu.mem_write(VILLAGE + 0xE574D4, struct.pack("<I", STATE))
            mu.mem_write(STATE + 0x2EAA4, struct.pack("<i", food))
            mu.mem_write(RECORD + 0x7E0, struct.pack("<i", state9))
        for va in (g["cont"], g["picker"], g["resume"], g["done"]):
            try:
                mu.mem_map(va & ~0xFFF, 0x1000)
            except Exception:
                pass
            mu.mem_write(va, b"\xC3")
        esp = STACK - 0x400
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.reg_write(UC_X86_REG_ESI, VILLAGE)
        mu.reg_write(UC_X86_REG_EDI, INDEX)
        mu.reg_write(UC_X86_REG_EBP, STATE if game == "vv1" else RECORD)
        self.g, self.cont_result, self.calls, self.exit = g, cont_result, [], None
        mu.hook_add(UC_HOOK_CODE, self._hook)
        mu.emu_start(stub, 0, count=100000)
        self.mu, self.esp_before = mu, esp

    def _hook(self, mu, address, size, user_data):
        g = self.g
        if address in (g["cont"], g["picker"]):             # thiscall(idx, arg), ret 8
            sp = mu.reg_read(UC_X86_REG_ESP)
            ret, a, b = struct.unpack("<3I", mu.mem_read(sp, 12))
            name = "cont" if address == g["cont"] else "picker"
            self.calls.append((name, a, b, mu.reg_read(UC_X86_REG_ECX)))
            mu.reg_write(UC_X86_REG_EAX, self.cont_result if name == "cont" else PICK)
            mu.reg_write(UC_X86_REG_ESP, sp + 12)
            mu.reg_write(UC_X86_REG_EIP, ret)
        elif address in (g["resume"], g["done"]):
            self.exit = address
            mu.emu_stop()


class HealersStudyTests(unittest.TestCase):
    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_the_sites_and_their_surroundings_are_what_the_stub_assumes(self):
        for game, g in G.items():
            with self.subTest(game=game):
                n, va, stock, patched, stub = _probe(g["no"])
                self.assertEqual(va, g["site"])
                self.assertEqual(_stock(game, va, n), stock)
                self.assertEqual(stock[:5], bytes.fromhex("6A00578BCE"), "push 0; push edi; mov ecx, esi")
                rel, = struct.unpack("<i", stock[6:10])
                self.assertEqual(va + 10 + rel, g["picker"], "call the picker")
                self.assertEqual(va + 10, g["resume"])
                rel, = struct.unpack("<i", patched[1:5])
                self.assertEqual(va + 5 + rel, stub)
                # The low-food path falls into the site right after the stock
                # continuation call with the same arguments this stub uses.
                before = _stock(game, va - 18, 18)
                self.assertEqual(before[:2], bytes([0x6A, g["cont_arg"]]))
                crel, = struct.unpack("<i", before[6:10])
                self.assertEqual(va - 18 + 10 + crel, g["cont"])
                self.assertEqual(_stock(game, g["done"], 4), bytes.fromhex("5F5E5D5B"), "pop edi/esi/ebp/ebx")

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_a_studying_villager_at_high_food_continues_the_study(self):
        for game, g in G.items():
            with self.subTest(game=game):
                r = Run(game, food=g["threshold"] + 1000, state9=9, cont_result=1)
                self.assertEqual(r.calls, [("cont", INDEX, g["cont_arg"], VILLAGE)])
                self.assertEqual(r.exit, g["done"])
                self.assertEqual(r.mu.reg_read(UC_X86_REG_EAX), 1, "the continuation's result")
                self.assertEqual(r.mu.reg_read(UC_X86_REG_ESP), r.esp_before)
                r = Run(game, food=g["threshold"], state9=9, cont_result=1)
                self.assertEqual(r.exit, g["done"], "exactly the threshold counts as high")

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_otherwise_the_stock_selection_runs(self):
        for game, g in G.items():
            for food, state, result in ((g["threshold"] - 1, 9, 1), (0, 9, 1),
                                        (g["threshold"] + 1000, 8, 1), (g["threshold"] + 1000, 0, 1),
                                        (g["threshold"] + 1000, 9, 0)):
                with self.subTest(game=game, food=food, state=state, result=result):
                    r = Run(game, food, state, result)
                    self.assertEqual(r.exit, g["resume"])
                    self.assertEqual(r.calls[-1], ("picker", INDEX, 0, VILLAGE), "push 0; push edi; mov ecx, esi")
                    self.assertEqual(r.mu.reg_read(UC_X86_REG_EAX), PICK, "the pick reaches push eax")
                    self.assertEqual(r.mu.reg_read(UC_X86_REG_ESP), r.esp_before)
                    self.assertEqual(r.mu.reg_read(UC_X86_REG_EDI), INDEX)
                    self.assertEqual(r.mu.reg_read(UC_X86_REG_ESI), VILLAGE)
                    expect_cont = food >= g["threshold"] and state == 9
                    self.assertEqual([c[0] for c in r.calls].count("cont"), 1 if expect_cont else 0)

    def test_the_rows_are_registered_bundled_and_the_bridge_is_shipped(self):
        import vv_fun_patcher as vfp
        from vv_fun_patcher_gui import default_fun_patch_selection
        sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        ids = {p.id for p in vfp.load_public_fun_patches()}
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("assets/healers_study/VVFP Healers Study.dll", release)
        for game, g in G.items():
            with self.subTest(game=game):
                rid = f"{game}_healers_study_regardless_of_food"
                m = json.loads((ROOT / "data" / f"{game}_healers_study_feature.json").read_text(encoding="utf-8"))
                self.assertIn(rid, ids)
                self.assertTrue(default_fun_patch_selection(rid))
                self.assertEqual(m["dependencies"], [f"{game}_enable_origins_exclusive_features"])
                self.assertEqual(m["patches"], [])
                self.assertEqual([c["sha256"] for c in m["companion_files"]], [sha])
                self.assertIn("**Requires Enable Origins-Exclusive Features**", m["description"])
                self.assertIn(f"data/{game}_healers_study_feature.json", release)
                self.assertIn(f"`{rid}`", readme)
                source = (ROOT / f"native/{game}_origins_icons/{game}_origins_icons.c").read_text(encoding="utf-8")
                self.assertIn(f"vvfp_healers_study_bridge({g['no']});", source)
                dll = (ROOT / f"assets/origins/VVFP {game.upper()} Origins Icons.dll").read_bytes()
                self.assertIn(b"VVFP Healers Study.dll", dll)
                self.assertIn(b"VvfpHealersStudyInstall", dll)


if __name__ == "__main__":
    unittest.main()
