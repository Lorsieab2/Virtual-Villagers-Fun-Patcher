"""Builders Fix Huts When Idle -- regardless of the food supply.

The owner: "Builders fix huts regardless of the food supply when not all
population huts are built."  Every game's idle scheduler reads the food
total before the Building dispatcher: A New Home and The Lost Children skip
the preferred-job attempt when food is plentiful; The Secret City, The Tree
of Life and New Believers make a picked job wait behind farming, and swap it
half the time for a food action, when food is scarce.

Pinned here:

* Each food site's stock bytes are exactly what the stock executable holds,
  and the bytes around them are the scheduler shape the source describes.
* The DLL's VV1/VV2/VV4/VV5 food stubs, RUN in an emulator over the game's
  own record and flag layout: a builder with a hut still unbuilt takes the
  builder path; a non-builder, a builder in a village whose huts are all
  built, and low food (VV1/VV2) take exactly the stock paths, with the
  registers the stock continuations read left as the stock code leaves them.
* The Secret City's executable-side food stub, run the same way through a
  scripted VvfpFixHutsBuilderFirst.
* A New Home's Builder Action Fixes compares the selected job with 4
  (Building) -- the picker's own switch maps 1 to Farming.
"""
from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX,
    UC_X86_REG_EDI, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "assets" / "fix_huts" / "VVFP Fix Huts.dll"
# The probes and counters the emulator drives exist only in the TEST build
# (VVFP_TEST, same source; tests/test_shipped_dlls_have_no_test_hooks.py).
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Fix Huts.test.dll"
# tests/test_dlls/ is export-ignore: the release source archive carries no test
# build, so there the tests that drive one skip instead of failing.
TEST_BUILD_ABSENT = "test builds are not in the release source archive (tests/test_dlls)"
STOCK = {g: ROOT / "research" / "stock-executables" / n for g, n in (
    ("vv1", "Virtual Villagers - A New Home.exe"), ("vv2", "Virtual Villagers - The Lost Children.exe"),
    ("vv3", "Virtual Villagers - The Secret City.exe"), ("vv4", "Virtual Villagers - The Tree of Life.exe"),
    ("vv5", "Virtual Villagers - New Believers.exe"))}
GAME_NO = {"vv1": 1, "vv2": 2, "vv3": 3, "vv4": 4, "vv5": 5}
STACK = 0x70000000
VILLAGE = 0x20000000
STATE = 0x30000000
RECORD = 0x38000000


def _stock(game: str, va: int, n: int) -> bytes:
    pe = pefile.PE(str(STOCK[game]), fast_load=True)
    data = STOCK[game].read_bytes()
    return data[pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase):][:n]


def _dll():
    pe = pefile.PE(str(TEST_DLL))
    base = pe.OPTIONAL_HEADER.ImageBase
    exports = {e.name.decode(): base + e.address for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
    return pe, base, exports


IMPORTS = 0x7C000000
IMPORT_STUBS: dict[str, int] = {}
STDCALL_BYTES = {"GetModuleFileNameA": 12, "LoadLibraryA": 4, "GetProcAddress": 8, "lstrcpyA": 8}


def _new_emulator():
    pe, base, exports = _dll()
    image = bytearray(pe.get_memory_mapped_image())
    # Point every import at a `ret N` stand-in the test's hook answers:
    # "VVFP Work First.dll" shipped or not is the only question the food
    # stubs can ask KERNEL32.
    for k, imp in enumerate(i for e in pe.DIRECTORY_ENTRY_IMPORT for i in e.imports):
        name = imp.name.decode() if imp.name else f"ord{imp.ordinal}"
        stub = IMPORTS + 16 * k
        IMPORT_STUBS[name] = stub
        struct.pack_into("<I", image, imp.address - base, stub)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(base, (len(image) + 0xFFFF) & ~0xFFFF)
    mu.mem_write(base, bytes(image))
    mu.mem_map(IMPORTS, 0x10000)
    for name, stub in IMPORT_STUBS.items():
        mu.mem_write(stub, b"\xC2" + struct.pack("<H", STDCALL_BYTES.get(name, 0)) if name in STDCALL_BYTES else b"\xC3")
    mu.mem_map(STACK - 0x10000, 0x20000)
    mu.mem_map(VILLAGE, 0x1000000)
    mu.mem_map(STATE, 0x100000)
    mu.mem_map(RECORD, 0x10000)
    return mu, exports


def _probe_food_site(game_no: int):
    mu, ex = _new_emulator()
    buf = STACK - 0x8000
    ret = STACK - 0x100
    mu.mem_write(ret, b"\xF4")
    esp = STACK - 0x200
    mu.mem_write(esp, struct.pack("<6I", ret, game_no, buf, buf + 0x10, buf + 0x30, buf + 0x50))
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.emu_start(ex["VvfpFixHutsProbeFoodSite"], ret, count=10000)
    n = mu.reg_read(UC_X86_REG_EAX)
    va, = struct.unpack("<I", mu.mem_read(buf, 4))
    stub, = struct.unpack("<I", mu.mem_read(buf + 0x50, 4))
    return n, va, bytes(mu.mem_read(buf + 0x10, n)), bytes(mu.mem_read(buf + 0x30, n)), stub


class StubRun:
    """Run a food stub from its first byte until it leaves for a game
    address in `exits`; game helpers in `predicates` answer per call."""

    def __init__(self, game: str, regs: dict, exits: set[int], setup, predicates=None,
                 work_first: bool = False):
        _, _, _, _, stub = _probe_food_site(GAME_NO[game])
        mu, _ = _new_emulator()
        setup(mu)
        self.work_first = work_first
        self.loaded: list[str] = []
        self.predicates = predicates or {}
        for va in set(exits) | set(self.predicates):
            try:
                mu.mem_map(va & ~0xFFF, 0x1000)
            except Exception:
                pass
            mu.mem_write(va, b"\xC3")
        esp = STACK - 0x400
        mu.reg_write(UC_X86_REG_ESP, esp)
        for reg, value in regs.items():
            mu.reg_write(reg, value)
        self.exits, self.exit, self.calls = exits, None, []
        mu.hook_add(UC_HOOK_CODE, self._hook)
        mu.emu_start(stub, 0, count=100000)
        self.mu = mu
        self.esp_before = esp
        self.regs = {r: mu.reg_read(r) for r in (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX,
                                                 UC_X86_REG_EDI, UC_X86_REG_ESI, UC_X86_REG_EBP,
                                                 UC_X86_REG_ESP)}

    def _hook(self, mu, address, size, user_data):
        if address == IMPORT_STUBS.get("GetModuleFileNameA"):
            esp = mu.reg_read(UC_X86_REG_ESP)
            buf, = struct.unpack("<I", mu.mem_read(esp + 8, 4))
            path = b"C:\\Games\\VV\\game.exe\0"
            mu.mem_write(buf, path)
            mu.reg_write(UC_X86_REG_EAX, len(path) - 1)
        elif address == IMPORT_STUBS.get("lstrcpyA"):
            esp = mu.reg_read(UC_X86_REG_ESP)
            dst, src = struct.unpack("<2I", mu.mem_read(esp + 4, 8))
            text = bytes(mu.mem_read(src, 260)).split(b"\0")[0] + b"\0"
            mu.mem_write(dst, text)
            mu.reg_write(UC_X86_REG_EAX, dst)
        elif address == IMPORT_STUBS.get("LoadLibraryA"):
            esp = mu.reg_read(UC_X86_REG_ESP)
            name, = struct.unpack("<I", mu.mem_read(esp + 4, 4))
            self.loaded.append(bytes(mu.mem_read(name, 64)).split(b"\0")[0].decode())
            mu.reg_write(UC_X86_REG_EAX, 0x10000000 if self.work_first else 0)
        elif address in self.predicates:
            esp = mu.reg_read(UC_X86_REG_ESP)
            arg, = struct.unpack("<I", mu.mem_read(esp + 4, 4))
            self.calls.append(arg)
            mu.reg_write(UC_X86_REG_EAX, 1 if self.predicates[address](arg) else 0)
            ret, = struct.unpack("<I", mu.mem_read(esp, 4))
            mu.reg_write(UC_X86_REG_ESP, esp + 8)       # __stdcall(int)
            mu.reg_write(UC_X86_REG_EIP, ret)
        elif address in self.exits:
            self.exit = address
            mu.emu_stop()


# ---- A New Home / The Lost Children: the high-food gate --------------------

VV12 = {
    "vv1": dict(site=0x448336, low=0x448342, high=0x44836F, threshold=400,
                food_reg=UC_X86_REG_EBP, food_off=0xA2EC, stride=0x3D8, pref=0x3D0, builder=4,
                state_ptr=0x3E010, huts=(0x9FE8, 0x9FF0, 0x9FF8)),
    "vv2": dict(site=0x4619E9, low=0x4619F5, high=0x461A22, threshold=300,
                food_reg=UC_X86_REG_ECX, food_off=0x2EAA4, pref=0x7F8, builder=5,
                state_ptr=0xE574D4, huts=(0x2E818, 0x2E820, 0x2E828)),
}


LEVEL_OFF = {"vv1": 0xA2CC, "vv2": 0x2EA84}


def _run_vv12(game: str, food: int, preference: int, huts: tuple[int, int, int], level: int = 3):
    g = VV12[game]
    index = 7

    def setup(mu):
        mu.mem_write(VILLAGE + g["state_ptr"], struct.pack("<I", STATE))
        for off, done in zip(g["huts"], huts):
            mu.mem_write(STATE + off, bytes([done]))
        mu.mem_write(STATE + g["food_off"], struct.pack("<i", food))
        mu.mem_write(STATE + LEVEL_OFF[game], struct.pack("<i", level))
        if game == "vv1":
            mu.mem_write(VILLAGE + index * g["stride"] + g["pref"], struct.pack("<i", preference))
        else:
            mu.mem_write(RECORD + g["pref"], struct.pack("<i", preference))

    regs = {UC_X86_REG_ESI: VILLAGE, UC_X86_REG_EDI: index, UC_X86_REG_EAX: 0x1234ABCD}
    if game == "vv1":
        regs[UC_X86_REG_EBP] = STATE
    else:
        regs[UC_X86_REG_ECX] = STATE
        regs[UC_X86_REG_EBP] = RECORD
    return StubRun(game, regs, {g["low"], g["high"]}, setup)


class HighFoodGateTests(unittest.TestCase):
    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_the_sites_hold_the_stock_food_gates(self):
        for game, g in VV12.items():
            with self.subTest(game=game):
                n, va, stock, patched, stub = _probe_food_site(GAME_NO[game])
                self.assertEqual(va, g["site"])
                self.assertEqual(_stock(game, va, n), stock)
                self.assertEqual(stock[:2], b"\x81" + (b"\xBD" if game == "vv1" else b"\xB9"))
                self.assertEqual(struct.unpack_from("<I", stock, 6)[0], g["threshold"])
                self.assertEqual(stock[-2], 0x7D, "jge")
                self.assertEqual(va + 12 + stock[-1], g["high"], "the stock jge target")
                self.assertEqual(va + 12, g["low"], "falls through to the preferred attempt")
                rel, = struct.unpack("<i", patched[1:5])
                self.assertEqual(va + 5 + rel, stub)
                manifest = json.loads((ROOT / "data" / f"{game}_builders_fix_huts_feature.json").read_text(encoding="utf-8"))
                self.assertIn({"va": f"{va:#x}", "stock_bytes": stock.hex().upper()},
                              [{"va": d["va"].lower(), "stock_bytes": d["stock_bytes"]} for d in manifest["runtime_detours"]])

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_a_builder_with_a_hut_unbuilt_gets_the_attempt_at_high_food(self):
        for game, g in VV12.items():
            with self.subTest(game=game):
                r = _run_vv12(game, food=g["threshold"] + 5000, preference=g["builder"], huts=(1, 0, 1))
                self.assertEqual(r.exit, g["low"])
                self.assertEqual(r.regs[UC_X86_REG_ESP], r.esp_before, "stack balanced")
                self.assertEqual(r.regs[UC_X86_REG_ESI], VILLAGE)
                self.assertEqual(r.regs[UC_X86_REG_EDI], 7)

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_below_level_3_a_builder_with_every_hut_built_gets_the_attempt(self):
        # The owner: "below level 3, at all food levels, villagers will fix
        # huts if at least one is built" -- every hut built included (Codex on
        # #464: the food gate must let them through too).
        for game, g in VV12.items():
            with self.subTest(game=game):
                r = _run_vv12(game, food=g["threshold"] + 5000, preference=g["builder"], huts=(1, 1, 1), level=2)
                self.assertEqual(r.exit, g["low"])
                r = _run_vv12(game, food=g["threshold"] + 5000, preference=g["builder"], huts=(0, 0, 0), level=2)
                self.assertEqual(r.exit, g["low"], "no hut built: a hut is still unbuilt, the attempt as before")
                r = _run_vv12(game, food=g["threshold"] + 5000, preference=g["builder"], huts=(1, 1, 1), level=3)
                self.assertEqual(r.exit, g["high"], "level 3 or above with every hut built: stock")

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_everything_else_takes_the_stock_path(self):
        for game, g in VV12.items():
            with self.subTest(game=game):
                cases = [
                    # (food, preference, huts, expected exit)
                    (g["threshold"] + 5000, g["builder"], (1, 1, 1), g["high"]),   # all huts built
                    (g["threshold"] + 5000, 1, (1, 0, 1), g["high"]),               # not a builder
                    (g["threshold"] + 5000, 0, (0, 0, 0), g["high"]),               # no preference
                    (g["threshold"], 3, (1, 0, 1), g["high"]),                      # exactly the threshold
                    (g["threshold"] - 1, 3, (1, 1, 1), g["low"]),                   # low food: stock attempt
                    (0, g["builder"], (1, 1, 1), g["low"]),
                ]
                for food, pref, huts, expected in cases:
                    r = _run_vv12(game, food, pref, huts, level=3)
                    self.assertEqual(r.exit, expected, (food, pref, huts))
                    self.assertEqual(r.regs[UC_X86_REG_ESP], r.esp_before)


# ---- The Tree of Life / New Believers: the low-food path ------------------

LATER = {
    "vv4": dict(site=0x4659B0, dispatch=0x465A0F, resume=0x4659B6, complete=0x438960,
                obj=0x4D8BF8, base=19),
    "vv5": dict(site=0x46F271, dispatch=0x46F2CE, resume=0x46F277, complete=0x43AE80,
                obj=0x51E008, base=19),
}


def _run_later(game: str, pick: int, huts: tuple[int, int, int, int], work_first: bool = False):
    g = LATER[game]
    villager = 0x0BADF00D

    def setup(mu):
        mu.mem_write(VILLAGE + 0x1B88, struct.pack("<I", villager))

    regs = {UC_X86_REG_EAX: pick, UC_X86_REG_ESI: VILLAGE, UC_X86_REG_EDI: 0x55555555,
            UC_X86_REG_ECX: 0x66666666}
    done = lambda arg: huts[arg - g["base"]] == 1
    r = StubRun(game, regs, {g["dispatch"], g["resume"]}, setup, {g["complete"]: done},
                work_first=work_first)
    r.villager = villager
    return r


class LowFoodPathTests(unittest.TestCase):
    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_the_sites_hold_the_stock_instruction_after_the_pick(self):
        for game, g in LATER.items():
            with self.subTest(game=game):
                n, va, stock, patched, stub = _probe_food_site(GAME_NO[game])
                self.assertEqual(va, g["site"])
                self.assertEqual(_stock(game, va, n), stock)
                self.assertEqual(stock, bytes.fromhex("8B8E881B0000"), "mov ecx, [esi+0x1B88]")
                self.assertEqual(_stock(game, va - 5, 1), b"\xE8", "right after the picker call")
                self.assertEqual(_stock(game, g["dispatch"], 3), bytes.fromhex("578BCE"),
                                 "push edi; mov ecx, esi: the dispatch-with-pick")
                rel, = struct.unpack("<i", patched[1:5])
                self.assertEqual(va + 5 + rel, stub)

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_a_picked_building_job_with_a_hut_unbuilt_is_dispatched_at_once(self):
        for game, g in LATER.items():
            with self.subTest(game=game):
                r = _run_later(game, pick=4, huts=(1, 1, 1, 0))
                self.assertEqual(r.exit, g["dispatch"])
                self.assertEqual(r.regs[UC_X86_REG_EDI], 4, "the dispatch reads the pick from edi")
                self.assertEqual(r.regs[UC_X86_REG_ESP], r.esp_before)

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_a_builders_pick_is_dispatched_with_every_hut_built_too(self):
        # Codex on #464: once every hut is built the stock "fix a hut" option is
        # the builder's hut work (no level gate before these games' hut site),
        # and the owner wants huts fixed "at all food levels".
        for game, g in LATER.items():
            with self.subTest(game=game):
                r = _run_later(game, pick=4, huts=(1, 1, 1, 1))
                self.assertEqual(r.exit, g["dispatch"])
                self.assertEqual(r.regs[UC_X86_REG_EDI], 4)

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_a_healers_pick_waits_unless_work_first_is_shipped(self):
        # Builders and Healers Work First (the addendum) extends the bypass to
        # a healer's pick (job 2); without its DLL the healer keeps the stock
        # low-food path.
        for game, g in LATER.items():
            with self.subTest(game=game):
                r = _run_later(game, pick=2, huts=(1, 0, 1, 1), work_first=True)
                self.assertEqual(r.exit, g["dispatch"])
                self.assertEqual(r.regs[UC_X86_REG_EDI], 2)
                self.assertEqual(r.loaded, ["C:\\Games\\VV\\VVFP Work First.dll"], "loaded by full path")
                r = _run_later(game, pick=2, huts=(1, 0, 1, 1), work_first=False)
                self.assertEqual(r.exit, g["resume"])
                # "Healers should not be gated by huts at all."
                r = _run_later(game, pick=2, huts=(1, 1, 1, 1), work_first=True)
                self.assertEqual(r.exit, g["dispatch"], "every hut built: still dispatched at once")
                r = _run_later(game, pick=2, huts=(0, 0, 0, 0), work_first=True)
                self.assertEqual(r.exit, g["dispatch"], "no hut built: still dispatched at once")

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_everything_else_resumes_the_stock_low_food_path(self):
        for game, g in LATER.items():
            for pick, huts in ((0, (0, 0, 0, 0)), (2, (1, 0, 1, 0)), (3, (1, 1, 1, 0))):
                with self.subTest(game=game, pick=pick, huts=huts):
                    r = _run_later(game, pick, huts)
                    self.assertEqual(r.exit, g["resume"])
                    self.assertEqual(r.regs[UC_X86_REG_ECX], r.villager, "the displaced mov ecx, [esi+0x1B88]")
                    self.assertEqual(r.regs[UC_X86_REG_EAX], pick, "eax (the pick) untouched")
                    self.assertEqual(r.regs[UC_X86_REG_EDI], 0x55555555)
                    self.assertEqual(r.regs[UC_X86_REG_ESP], r.esp_before)


# ---- The Secret City: the executable-side stub ----------------------------

class SecretCityFoodTests(unittest.TestCase):
    def setUp(self):
        m = json.loads((ROOT / "data" / "vv3_builders_fix_huts_feature.json").read_text(encoding="utf-8"))
        self.overlay = m["pe_append_transaction"]["composition_overlays"]["vv3_enable_origins_exclusive_features"]
        self.page = bytes.fromhex(self.overlay["append_bytes"])
        self.base = int(self.overlay["page_virtual_address"], 16)

    def test_the_site_is_the_stock_farming_test(self):
        food = [p for p in self.overlay["hook_patches"] if p["offset"] == "0x5C229"]
        self.assertEqual(len(food), 1)
        self.assertEqual(_stock("vv3", 0x45C229, 9), bytes.fromhex(food[0]["before"]))
        self.assertEqual(_stock("vv3", 0x45C222, 5)[:1], b"\xE8", "right after the picker call")
        self.assertEqual(_stock("vv3", 0x45C227, 2), bytes.fromhex("8BD8"), "mov ebx, eax: the pick")
        self.assertEqual(_stock("vv3", 0x45C271, 4), bytes.fromhex("53568BCF"), "push ebx; push esi; mov ecx, edi")
        after = bytes.fromhex(food[0]["after"])
        rel, = struct.unpack("<i", after[1:5])
        self.assertEqual(0x45C229 + 5 + rel, self.base + 0x100)

    def _run(self, pick: int, answer, farming_skill: int = 30):
        """answer: None = the companion is missing; else the export's result."""
        mu = Uc(UC_ARCH_X86, UC_MODE_32)
        # The overlay starts mid-page (0x6DF800); map through .vv3md, whose
        # cache slot 0x6E0FFC the stub reads, zeroed as the game starts it.
        mu.mem_map(self.base & ~0xFFF, 0x2000)
        mu.mem_write(self.base, self.page[:0x400])
        mu.mem_map(0x47C000, 0x1000)
        for iat, fn in ((0x47C074, 0x7A000000), (0x47C124, 0x7A000010), (0x47C128, 0x7A000020)):
            mu.mem_write(iat, struct.pack("<I", fn))
        mu.mem_map(0x7A000000, 0x1000)
        mu.mem_write(0x7A000000, b"\xC2\x04\x00" + b"\x90" * 13 + b"\xC2\x04\x00" + b"\x90" * 13 + b"\xC2\x08\x00")
        mu.mem_map(0x7B000000, 0x1000)
        mu.mem_write(0x7B000000, b"\xC3")
        mu.mem_map(0x45C000, 0x1000)
        for va in (0x45C232, 0x45C244, 0x45C271):
            mu.mem_write(va, b"\xC3")
        mu.mem_map(STACK - 0x10000, 0x20000)
        mu.mem_map(VILLAGE, 0x10000)
        mu.mem_write(VILLAGE + 0xEAC, struct.pack("<i", farming_skill))
        esp = STACK - 0x400
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.reg_write(UC_X86_REG_EBX, pick)
        mu.reg_write(UC_X86_REG_ESI, VILLAGE)
        mu.reg_write(UC_X86_REG_EDI, 0x44444444)
        state = {"exit": None, "args": None}

        def hook(mu, address, size, user_data):
            sp = mu.reg_read(UC_X86_REG_ESP)
            if address in (0x7A000000, 0x7A000010):            # GetModuleHandleA / LoadLibraryA
                mu.reg_write(UC_X86_REG_EAX, 0 if answer is None else 0x10000000)
            elif address == 0x7A000020:                         # GetProcAddress
                mu.reg_write(UC_X86_REG_EAX, 0 if answer is None else 0x7B000000)
            elif address == 0x7B000000:                         # VvfpFixHutsBuilderFirst
                state["args"] = struct.unpack("<2i", mu.mem_read(sp + 4, 8))
                mu.reg_write(UC_X86_REG_EAX, answer)
            elif address in (0x45C232, 0x45C244, 0x45C271):
                state["exit"] = address
                mu.emu_stop()

        mu.hook_add(UC_HOOK_CODE, hook)
        mu.emu_start(self.base + 0x100, 0, count=10000)
        return state, mu, esp

    def test_a_builder_goes_straight_to_the_dispatch(self):
        state, mu, esp = self._run(pick=4, answer=1)
        self.assertEqual(state["exit"], 0x45C271)
        self.assertEqual(state["args"], (3, 4), "VvfpFixHutsBuilderFirst(3, pick)")
        self.assertEqual(mu.reg_read(UC_X86_REG_EBX), 4, "the dispatch pushes ebx")
        self.assertEqual(mu.reg_read(UC_X86_REG_ESP), esp)

    def test_otherwise_and_without_the_companion_the_stock_test_runs(self):
        for answer in (0, None):
            for skill, expected in ((30, 0x45C232), (20, 0x45C232), (19, 0x45C244)):
                with self.subTest(answer=answer, skill=skill):
                    state, mu, esp = self._run(pick=4, answer=answer, farming_skill=skill)
                    self.assertEqual(state["exit"], expected)
                    self.assertEqual(mu.reg_read(UC_X86_REG_ESP), esp)
                    self.assertEqual(mu.reg_read(UC_X86_REG_EBX), 4)


# ---- A New Home: Builder Action Fixes targets Building ---------------------

class BuilderActionFixesTests(unittest.TestCase):
    def test_the_selected_job_compare_is_building_by_the_pickers_own_numbering(self):
        # The picker's switch on the selected job (0x439CAC): 1..5 -> the skill
        # it rates. Building's skill is +0x3C0 and Farming's +0x3C4, measured in
        # the owner's running game (docs/origins-village-wide-upgrades.md).
        pe = pefile.PE(str(STOCK["vv1"]), fast_load=True)
        data = STOCK["vv1"].read_bytes()
        table = pe.get_offset_from_rva(0x439CAC - 0x400000)
        cases = [struct.unpack_from("<I", data, table + 4 * k)[0] for k in range(5)]
        skill_of = {}
        for job, case in enumerate(cases, start=1):
            code = _stock("vv1", case, 7)
            self.assertEqual(code[:2], bytes.fromhex("8BB7"), f"mov esi, [edi+disp32] at {case:#x}")
            skill_of[job] = struct.unpack_from("<I", code, 2)[0]
        self.assertEqual(skill_of, {1: 0x3C4, 2: 0x3BC, 3: 0x3CC, 4: 0x3C0, 5: 0x3C8})
        builds = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
        row = next(f for f in builds["fun_patches"] if f["id"] == "vv1_builder_action_fixes")
        cave = next(p for p in row["patches"] if p["offset"] == "0x568A0")["after"]
        self.assertIn("83BC30D003000004", cave, "cmp [record+0x3D0], 4: Building")


if __name__ == "__main__":
    unittest.main()
