"""Builders and Healers Work First (all five games) -- the addendum to
Builders Fix Huts When Idle.

The owner: "in both low and high food situations, builders and healers still
should prioritize fixing huts over other stuff for all 5 games" -- builders
their building work, healers their healing and study, first, while not every
population hut is built -- and "make the work patches an addendum to the
preexisting ones".

Pinned here:

* Each game's job picker entry, the displaced bytes and the adult
  scheduler's two call sites (their return addresses) are what the stubs
  assume, read from the stock executables; the picker's other caller (the
  younger villagers' routine) is a third, different return address.
* The DLL's picker stubs (VV1/VV2/VV4/VV5), RUN in an emulator over the
  games' own record layouts: a builder or healer called from the adult
  scheduler with a hut unbuilt gets its own job back with the stock return
  (ret 8 / ret); any other job, any other caller, or all huts built replays
  the displaced bytes into the stock picker with stack and registers intact.
* The Secret City's picker stub in the fix-huts page, run the same way with
  VvfpWorkFirstPriority scripted, and with the DLL missing.
* The five rows depend on Builders Fix Huts When Idle, ship and pin the DLL,
  and the fix-huts companion loads it by full path.
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
    UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI, UC_X86_REG_EIP,
    UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
DLL = ROOT / "assets" / "work_first" / "VVFP Work First.dll"
STOCK = {g: ROOT / "research" / "stock-executables" / n for g, n in (
    ("vv1", "Virtual Villagers - A New Home.exe"), ("vv2", "Virtual Villagers - The Lost Children.exe"),
    ("vv3", "Virtual Villagers - The Secret City.exe"), ("vv4", "Virtual Villagers - The Tree of Life.exe"),
    ("vv5", "Virtual Villagers - New Believers.exe"))}
GAME_NO = {"vv1": 1, "vv2": 2, "vv3": 3, "vv4": 4, "vv5": 5}
STACK = 0x70000000
VILLAGE = 0x20000000
STATE = 0x30000000
RECORD = 0x38000000
ORIGINAL = 0x0BADC0DE

G = {
    "vv1": dict(picker=0x439AE0, stock="5355566A64", calls=(0x448347, 0x448374), other=0x42E7DB,
                building=4, healing=5, ret=8),
    "vv2": dict(picker=0x449C60, stock="5153565733F6", calls=(0x4619FA, 0x461A27), other=0x43B526,
                building=5, healing=3, ret=8),
    "vv3": dict(picker=0x459730, stock="5356576A64", calls=(0x45C222, 0x45C281), other=0x45BF4B,
                building=4, healing=2, ret=4),
    "vv4": dict(picker=0x461CC0, stock="5356576A64", calls=(0x4659AB, 0x465A1D), other=0x465798,
                building=4, healing=2, ret=0),
    "vv5": dict(picker=0x46A3C0, stock="5356576A64", calls=(0x46F26C, 0x46F2DD), other=0x46E928,
                building=4, healing=2, ret=0),
}


def _stock(game: str, va: int, n: int) -> bytes:
    pe = pefile.PE(str(STOCK[game]), fast_load=True)
    return STOCK[game].read_bytes()[pe.get_offset_from_rva(va - 0x400000):][:n]


def _emulator():
    pe = pefile.PE(str(DLL))
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
    mu.emu_start(ex["VvfpWorkFirstProbeSite"], ret, count=10000)
    n = mu.reg_read(UC_X86_REG_EAX)
    va, = struct.unpack("<I", mu.mem_read(buf, 4))
    stub, = struct.unpack("<I", mu.mem_read(buf + 0x50, 4))
    return n, va, bytes(mu.mem_read(buf + 0x10, n)), bytes(mu.mem_read(buf + 0x30, n)), stub


HUT_PREDICATE = {"vv4": (0x438960, 19), "vv5": (0x43AE80, 19)}


class PickerRun:
    """Enter a picker stub as `call picker` from `caller` would."""

    def __init__(self, game: str, caller: int, selected: int, huts_done: bool):
        g = G[game]
        stub = _probe(GAME_NO[game])[4]
        mu, _ = _emulator()
        index = 7
        if game == "vv1":
            mu.mem_write(VILLAGE + 0x3E010, struct.pack("<I", STATE))
            for off in (0x9FE8, 0x9FF0, 0x9FF8):
                mu.mem_write(STATE + off, bytes([1]))
            if not huts_done:
                mu.mem_write(STATE + 0x9FF0, bytes([0]))
            mu.mem_write(VILLAGE + index * 0x3D8 + 0x3D0, struct.pack("<i", selected))
        elif game == "vv2":
            mu.mem_write(VILLAGE + 0xE574D4, struct.pack("<I", STATE))
            for off in (0x2E818, 0x2E820, 0x2E828):
                mu.mem_write(STATE + off, bytes([1]))
            if not huts_done:
                mu.mem_write(STATE + 0x2E828, bytes([0]))
            mu.mem_write(VILLAGE + index * 0xE48C + 0x7F8, struct.pack("<i", selected))
        else:
            mu.mem_write(VILLAGE + 0x1B88, struct.pack("<I", RECORD))
            mu.mem_write(RECORD + (0x1C70 if game == "vv4" else 0x1C74), struct.pack("<i", selected))
        self.huts_done = huts_done
        ret = caller + 5
        body = g["picker"] + len(bytes.fromhex(g["stock"]))
        for va in (ret, body) + ((HUT_PREDICATE[game][0],) if game in HUT_PREDICATE else ()):
            try:
                mu.mem_map(va & ~0xFFF, 0x1000)
            except Exception:
                pass
            mu.mem_write(va, b"\xC3")
        esp = STACK - 0x400
        args = struct.pack("<2I", index, 0) if g["ret"] == 8 else b""
        mu.mem_write(esp, struct.pack("<I", ret) + args)
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.reg_write(UC_X86_REG_ECX, VILLAGE)
        mu.reg_write(UC_X86_REG_EAX, ORIGINAL)
        mu.reg_write(UC_X86_REG_EBX, 0x11111111)
        mu.reg_write(UC_X86_REG_ESI, 0x22222222)
        mu.reg_write(UC_X86_REG_EDI, 0x33333333)
        self.g, self.ret, self.body, self.exit = g, ret, body, None
        self.game = game
        mu.hook_add(UC_HOOK_CODE, self._hook)
        mu.emu_start(stub, 0, count=100000)
        self.mu, self.esp_before = mu, esp

    def _hook(self, mu, address, size, user_data):
        if self.game in HUT_PREDICATE and address == HUT_PREDICATE[self.game][0]:
            sp = mu.reg_read(UC_X86_REG_ESP)
            ret, arg = struct.unpack("<2I", mu.mem_read(sp, 8))
            done = self.huts_done or arg != HUT_PREDICATE[self.game][1] + 3
            mu.reg_write(UC_X86_REG_EAX, 1 if done else 0)
            mu.reg_write(UC_X86_REG_ESP, sp + 8)
            mu.reg_write(UC_X86_REG_EIP, ret)
        elif address in (self.ret, self.body):
            self.exit = address
            mu.emu_stop()

    def reg(self, r):
        return self.mu.reg_read(r)


class SiteTests(unittest.TestCase):
    def test_the_picker_entries_and_their_callers(self):
        for game, g in G.items():
            with self.subTest(game=game):
                n = len(bytes.fromhex(g["stock"]))
                self.assertEqual(_stock(game, g["picker"], n), bytes.fromhex(g["stock"]))
                for call in g["calls"] + (g["other"],):
                    code = _stock(game, call, 5)
                    self.assertEqual(code[0], 0xE8, hex(call))
                    rel, = struct.unpack("<i", code[1:])
                    self.assertEqual(call + 5 + rel, g["picker"], hex(call))
                if game != "vv3":
                    k, va, stock, patched, stub = _probe(GAME_NO[game])
                    self.assertEqual((va, stock), (g["picker"], bytes.fromhex(g["stock"])))
                    rel, = struct.unpack("<i", patched[1:5])
                    self.assertEqual(va + 5 + rel, stub)


class PickerStubTests(unittest.TestCase):
    GAMES = ("vv1", "vv2", "vv4", "vv5")

    def test_a_builder_or_healer_from_the_adult_scheduler_gets_its_own_job(self):
        for game in self.GAMES:
            g = G[game]
            for job in (g["building"], g["healing"]):
                for call in g["calls"]:
                    with self.subTest(game=game, job=job, call=hex(call)):
                        r = PickerRun(game, call, job, huts_done=False)
                        self.assertEqual(r.exit, call + 5, "returns to the scheduler")
                        self.assertEqual(r.reg(UC_X86_REG_EAX), job)
                        self.assertEqual(r.reg(UC_X86_REG_ESP), r.esp_before + 4 + g["ret"], "ret N")
                        self.assertEqual((r.reg(UC_X86_REG_EBX), r.reg(UC_X86_REG_ESI), r.reg(UC_X86_REG_EDI)),
                                         (0x11111111, 0x22222222, 0x33333333))

    def test_everything_else_runs_the_stock_picker(self):
        for game in self.GAMES:
            g = G[game]
            other_job = next(j for j in range(1, 6) if j not in (g["building"], g["healing"]))
            cases = [(g["calls"][0], g["building"], True), (g["calls"][1], g["healing"], True),
                     (g["other"], g["building"], False), (g["calls"][0], other_job, False),
                     (g["calls"][0], 0, False)]
            for call, job, huts_done in cases:
                with self.subTest(game=game, call=hex(call), job=job, huts_done=huts_done):
                    r = PickerRun(game, call, job, huts_done)
                    self.assertEqual(r.exit, r.body, "into the stock picker body")
                    pushed = len(bytes.fromhex(g["stock"]))
                    self.assertEqual(r.reg(UC_X86_REG_EAX), ORIGINAL if game != "vv2" else ORIGINAL)
                    self.assertEqual(r.reg(UC_X86_REG_ECX), VILLAGE)
                    # the displaced pushes, as the stock prologue leaves them
                    depth = 4 * (3 if game != "vv2" else 4) + (4 if game != "vv2" else 0)
                    self.assertEqual(r.reg(UC_X86_REG_ESP), r.esp_before - depth, pushed)
                    if game == "vv2":
                        self.assertEqual(r.reg(UC_X86_REG_ESI), 0, "xor esi, esi")


class SecretCityTests(unittest.TestCase):
    def setUp(self):
        m = json.loads((ROOT / "data" / "vv3_builders_fix_huts_feature.json").read_text(encoding="utf-8"))
        self.overlay = m["pe_append_transaction"]["composition_overlays"]["vv3_enable_origins_exclusive_features"]
        self.page = bytes.fromhex(self.overlay["append_bytes"])
        self.base = int(self.overlay["page_virtual_address"], 16)

    def test_the_site_patch(self):
        (patch,) = [p for p in self.overlay["hook_patches"] if p["offset"] == "0x59730"]
        self.assertEqual(bytes.fromhex(patch["before"]), _stock("vv3", 0x459730, 5))
        rel, = struct.unpack("<i", bytes.fromhex(patch["after"])[1:5])
        self.assertEqual(0x459730 + 5 + rel, self.base + 0x200)
        self.assertIn(b"VVFP Work First.dll\0", self.page)
        self.assertIn(b"VvfpWorkFirstPriority\0", self.page)

    def _run(self, answer, caller=0x45C222):
        mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(self.base & ~0xFFF, 0x2000)
        mu.mem_write(self.base, self.page[:0x400])
        mu.mem_map(0x47C000, 0x1000)
        for iat, fn in ((0x47C074, 0x7A000000), (0x47C124, 0x7A000010), (0x47C128, 0x7A000020)):
            mu.mem_write(iat, struct.pack("<I", fn))
        mu.mem_map(0x7A000000, 0x1000)
        mu.mem_write(0x7A000000, b"\xC2\x04\x00" + b"\x90" * 13 + b"\xC2\x04\x00" + b"\x90" * 13 + b"\xC2\x08\x00")
        mu.mem_map(0x7B000000, 0x1000)
        mu.mem_write(0x7B000000, b"\xC3")
        mu.mem_map(0x459000, 0x1000)
        mu.mem_write(0x459735, b"\xC3")
        mu.mem_map(0x45C000, 0x1000)
        ret = caller + 5
        mu.mem_write(ret, b"\xC3")
        mu.mem_map(STACK - 0x10000, 0x20000)
        esp = STACK - 0x400
        mu.mem_write(esp, struct.pack("<2I", ret, RECORD))
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.reg_write(UC_X86_REG_EAX, ORIGINAL)
        state = {"exit": None, "args": None, "loaded": None}

        def hook(mu, address, size, user_data):
            sp = mu.reg_read(UC_X86_REG_ESP)
            if address in (0x7A000000, 0x7A000010):
                name, = struct.unpack("<I", mu.mem_read(sp + 4, 4))
                state["loaded"] = bytes(mu.mem_read(name, 32)).split(b"\0")[0]
                mu.reg_write(UC_X86_REG_EAX, 0 if answer is None else 0x10000000)
            elif address == 0x7A000020:
                mu.reg_write(UC_X86_REG_EAX, 0 if answer is None else 0x7B000000)
            elif address == 0x7B000000:
                state["args"] = struct.unpack("<3I", mu.mem_read(sp + 4, 12))
                mu.reg_write(UC_X86_REG_EAX, answer & 0xFFFFFFFF)
            elif address in (0x459735, ret):
                state["exit"] = address
                mu.emu_stop()

        mu.hook_add(UC_HOOK_CODE, hook)
        mu.emu_start(self.base + 0x200, 0, count=10000)
        return state, mu, esp, ret

    def test_the_answer_becomes_the_pick(self):
        for answer in (4, 2):
            state, mu, esp, ret = self._run(answer)
            self.assertEqual(state["exit"], ret)
            self.assertEqual(state["args"], (3, ret, RECORD), "VvfpWorkFirstPriority(3, caller, record)")
            self.assertEqual(state["loaded"], b"VVFP Work First.dll")
            self.assertEqual(mu.reg_read(UC_X86_REG_EAX), answer)
            self.assertEqual(mu.reg_read(UC_X86_REG_ESP), esp + 8, "ret 4")

    def test_minus_one_or_no_dll_runs_the_stock_picker(self):
        for answer in (-1, None):
            state, mu, esp, ret = self._run(answer)
            self.assertEqual(state["exit"], 0x459735)
            self.assertEqual(mu.reg_read(UC_X86_REG_EAX), ORIGINAL)
            self.assertEqual(mu.reg_read(UC_X86_REG_ESP), esp - 16, "push ebx/esi/edi/100 replayed")


class RowTests(unittest.TestCase):
    def test_the_rows_are_an_addendum_that_ships_and_pins_the_dll(self):
        import vv_fun_patcher as vfp
        from vv_fun_patcher_gui import default_fun_patch_selection
        sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        ids = {p.id for p in vfp.load_public_fun_patches()}
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("assets/work_first/VVFP Work First.dll", release)
        for game in G:
            with self.subTest(game=game):
                rid = f"{game}_builders_and_healers_work_first"
                m = json.loads((ROOT / "data" / f"{game}_work_first_feature.json").read_text(encoding="utf-8"))
                self.assertIn(rid, ids)
                self.assertTrue(default_fun_patch_selection(rid))
                self.assertEqual(m["dependencies"], [f"{game}_builders_fix_huts"])
                self.assertEqual(m["patches"], [])
                self.assertEqual([c["sha256"] for c in m["companion_files"]], [sha])
                self.assertIn("**Requires Builders Fix Huts When Idle**", m["description"])
                self.assertIn(f"data/{game}_work_first_feature.json", release)
                self.assertIn(f"`{rid}`", readme)
        source = (ROOT / "native/vvfp_fix_huts/vvfp_fix_huts.c").read_text(encoding="utf-8")
        self.assertIn('lstrcpyA(slash + 1, "VVFP Work First.dll")', source)
        self.assertIn('GetProcAddress(work_first_module, "VvfpWorkFirstInstall")', source)
        self.assertIn(b"VVFP Work First.dll", (ROOT / "assets/fix_huts/VVFP Fix Huts.dll").read_bytes())


if __name__ == "__main__":
    unittest.main()
