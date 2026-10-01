"""Builders Fix Huts When Idle (all five games): the companion,
the five rows, the detour sites and the loaders.

Pinned here against the stock executables and the shipped files:

* Each runtime site's stock bytes (VV1, VV2, VV4, VV5) are exactly what the
  stock executable holds, so the DLL's verify-then-install can succeed on the
  real game; the jmp it writes lands on the game's stub (decoded in an
  emulator from the DLL's own probe).
* The VV1/VV2 choosers, RUN in the emulator over a village image laid out
  as the game keeps its flags: no hut complete -> stock; all complete ->
  stock; some complete -> only a complete hut is ever chosen.
* The Secret City's row: the site patch replaces the exact stock test, the
  overlay stub assembles to the addresses the manifest names (resolves the
  companion through the stock import table, calls VvfpFixHutsDecide(3, esi),
  takes the stock 'started' / 'nothing' paths), sits in a zero range of
  Origins' page after the parentage overlay, and the composed VV3 image
  renders in every mode with the stub in place.
* The rows are selectable by default, registered, bundled and described; the four
  per-frame companions carry the loader bridge and are re-pinned.
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs
from unicorn import UC_ARCH_X86, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
DLL = ROOT / "assets" / "fix_huts" / "VVFP Fix Huts.dll"
# The probes and counters the emulator drives exist only in the TEST build
# (VVFP_TEST, same source; tests/test_shipped_dlls_have_no_test_hooks.py).
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Fix Huts.test.dll"
# tests/test_dlls/ is export-ignore: the release source archive carries no test
# build, so there the tests that drive one skip instead of failing.
TEST_BUILD_ABSENT = "test builds are not in the release source archive (tests/test_dlls)"
SOURCE = ROOT / "native" / "vvfp_fix_huts" / "vvfp_fix_huts.c"
STOCK = {g: ROOT / "research" / "stock-executables" / n for g, n in (
    ("vv1", "Virtual Villagers - A New Home.exe"), ("vv2", "Virtual Villagers - The Lost Children.exe"),
    ("vv3", "Virtual Villagers - The Secret City.exe"), ("vv4", "Virtual Villagers - The Tree of Life.exe"),
    ("vv5", "Virtual Villagers - New Believers.exe"))}
MANIFESTS = {g: ROOT / "data" / f"{g}_builders_fix_huts_feature.json" for g in STOCK}
GAME_NO = {"vv1": 1, "vv2": 2, "vv3": 3, "vv4": 4, "vv5": 5}
STACK = 0x70000000
VILLAGE = 0x50000000
STATE = 0x60000000


def _stock(game: str, va: int, n: int) -> bytes:
    pe = pefile.PE(str(STOCK[game]), fast_load=True)
    data = STOCK[game].read_bytes()
    return data[pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase):][:n]


def _emulator():
    pe = pefile.PE(str(TEST_DLL))
    exports = {e.name.decode(): pe.OPTIONAL_HEADER.ImageBase + e.address
               for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
    base = pe.OPTIONAL_HEADER.ImageBase
    image = pe.get_memory_mapped_image()
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(base, (len(image) + 0xFFFF) & ~0xFFFF)
    mu.mem_write(base, image)
    mu.mem_map(STACK, 0x10000)
    mu.mem_map(VILLAGE, 0x1000000)
    mu.mem_map(STATE, 0x100000)
    return mu, exports


def _call(mu, fn, *args):
    esp = STACK + 0x8000
    ret = STACK + 0x100
    mu.mem_write(ret, b"\xF4")   # hlt: an end marker
    mu.mem_write(esp, struct.pack("<I", ret) + b"".join(struct.pack("<I", a) for a in args))
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.emu_start(fn, ret, count=200000)
    return mu.reg_read(UC_X86_REG_EAX)


def _probe_site(game_no: int):
    mu, ex = _emulator()
    buf = STACK + 0x4000
    n = _call(mu, ex["VvfpFixHutsProbeSite"], game_no, buf, buf + 0x10, buf + 0x30, buf + 0x50)
    va, = struct.unpack("<I", mu.mem_read(buf, 4))
    stub, = struct.unpack("<I", mu.mem_read(buf + 0x50, 4))
    return n, va, bytes(mu.mem_read(buf + 0x10, n)), bytes(mu.mem_read(buf + 0x30, n)), stub


def _probe_decision_site(game_no: int, which: int):
    """which: 0 the scheduler entry, 1 Builder Action Fixes' gate (VV1)."""
    mu, ex = _emulator()
    buf = STACK + 0x4000
    n = _call(mu, ex["VvfpFixHutsProbeDecisionSite"], game_no, which, buf, buf + 0x20, buf + 0x60, buf + 0xA0)
    va, = struct.unpack("<I", mu.mem_read(buf, 4))
    stub, = struct.unpack("<I", mu.mem_read(buf + 0xA0, 4))
    return n, va, bytes(mu.mem_read(buf + 0x20, n)), bytes(mu.mem_read(buf + 0x60, n)), stub


class RuntimeSiteTests(unittest.TestCase):
    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_each_runtime_sites_stock_bytes_match_and_the_jmp_lands_on_the_stub(self):
        for game in ("vv1", "vv2", "vv4", "vv5"):
            manifest = json.loads(MANIFESTS[game].read_text(encoding="utf-8"))
            # The hut site first; the food-gate site second (its own tests
            # are in tests/test_builders_regardless_of_food.py); in A New Home
            # and The Lost Children the Building-level gate third
            # (tests/test_builders_level_gate.py) and the lifted new-hut test
            # fourth (tests/test_finish_started_huts.py); last, the scheduler
            # entry that opens each decision (tests/test_builders_decision_roll.py).
            self.assertEqual(len(manifest["runtime_detours"]), {"vv1": 5, "vv2": 4}.get(game, 3), game)
            site = manifest["runtime_detours"][0]
            n, va, stock, patched, stub = _probe_site(GAME_NO[game])
            self.assertEqual(va, int(site["va"], 16), game)
            self.assertEqual(stock, bytes.fromhex(site["stock_bytes"]), game)
            self.assertEqual(_stock(game, va, n), stock, game)
            self.assertEqual(patched[0], 0xE9)
            rel, = struct.unpack("<i", patched[1:5])
            self.assertEqual((va + 5 + rel) & 0xFFFFFFFF, stub, game)
            self.assertEqual(patched[5:], b"\x90" * (n - 5), game)

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_the_scheduler_entries_are_the_stock_prologues_and_the_jmp_lands_on_the_wrapper(self):
        # About three times in four, once per decision: the companion wraps
        # each game's idle scheduler (VvfpFixHutsInstall installs it first and
        # nothing else without it).  The displaced prologue is what the stock
        # executable holds; the manifest names the same bytes.
        prologues = {"vv1": (0x448220, "535556578B7C2414"), "vv2": (0x461850, "535556578B7C2414"),
                     "vv4": (0x465840, "83EC08568BF1"), "vv5": (0x46F070, "83EC085356")}
        for game, (va_want, stock_hex) in prologues.items():
            with self.subTest(game=game):
                n, va, stock, patched, stub = _probe_decision_site(GAME_NO[game], 0)
                self.assertEqual((va, stock.hex().upper()), (va_want, stock_hex))
                self.assertEqual(_stock(game, va, n), stock)
                rel, = struct.unpack("<i", patched[1:5])
                self.assertEqual((patched[0], (va + 5 + rel) & 0xFFFFFFFF), (0xE9, stub))
                self.assertEqual(patched[5:], b"\x90" * (n - 5))
                manifest = json.loads(MANIFESTS[game].read_text(encoding="utf-8"))
                self.assertEqual(manifest["runtime_detours"][-1]["va"].upper(), f"0X{va_want:X}")
                self.assertEqual(manifest["runtime_detours"][-1]["stock_bytes"], stock_hex)
        # Every call of each scheduler is one of the callers the decision
        # bookkeeping knows (A New Home, The Lost Children: a per-frame call and
        # a load-time retry loop; the later games: one retry loop).
        callers = {"vv1": {0x448488, 0x4487C8}, "vv2": {0x464498, 0x464E9C}, "vv3": {0x45C388, 0x45C4E3},
                   "vv4": {0x465B1A}, "vv5": {0x46F3DA}}
        entries = {"vv1": 0x448220, "vv2": 0x461850, "vv3": 0x45BFE0, "vv4": 0x465840, "vv5": 0x46F070}
        for game, want in callers.items():
            with self.subTest(game=game, callers=True):
                data = STOCK[game].read_bytes()
                pe = pefile.PE(str(STOCK[game]), fast_load=True)
                found = set()
                for sec in pe.sections:
                    if not sec.Characteristics & 0x20000000:
                        continue
                    raw = data[sec.PointerToRawData:sec.PointerToRawData + sec.SizeOfRawData]
                    base = 0x400000 + sec.VirtualAddress
                    i = raw.find(b"\xE8")
                    while i >= 0:
                        if i + 5 <= len(raw) and base + i + 5 + struct.unpack_from("<i", raw, i + 1)[0] == entries[game]:
                            found.add(base + i)
                        i = raw.find(b"\xE8", i + 1)
                self.assertEqual(found, want)

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_builder_action_fixes_gate_is_taken_over_only_as_that_row_writes_it(self):
        n, va, stock, patched, stub = _probe_decision_site(1, 1)
        builds = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
        row = next(f for f in builds["fun_patches"] if f["id"] == "vv1_builder_action_fixes")
        jump = next(q for q in row["patches"] if q["offset"] == "0x48336")
        self.assertEqual(va, 0x448336)
        self.assertEqual(stock, bytes.fromhex(jump["after"]), "the row's own jmp is what is verified")
        rel, = struct.unpack("<i", patched[1:5])
        self.assertEqual((va + 5 + rel) & 0xFFFFFFFF, stub)

    def test_the_sites_are_the_dispatcher_points_the_source_describes(self):
        # VV1/VV2: the skip roll `push 100; call rand; add esp,4` right before
        # `cmp eax, 20` and the random-hut pick.  VV3-5: `cmp edi, ebx; je`.
        self.assertEqual(_stock("vv1", 0x447724 + 10, 3), bytes.fromhex("83F814"))
        self.assertEqual(_stock("vv1", 0x447737, 2), bytes.fromhex("6A03"), "rand(3) follows")
        self.assertEqual(_stock("vv2", 0x46029D + 10, 3), bytes.fromhex("83F814"))
        self.assertEqual(_stock("vv2", 0x4602B0, 2), bytes.fromhex("6A04"), "rand(4) follows")
        for game, va in (("vv3", 0x45B39E), ("vv4", 0x463F8A), ("vv5", 0x46CADA)):
            self.assertEqual(_stock(game, va, 2), bytes.fromhex("3BFB"), game)
            self.assertEqual(_stock(game, va + 8, 1), b"\x57", f"{game}: push edi (rand(count)) follows")


class ChooserTests(unittest.TestCase):
    """The VV1/VV2 choosers over a village image with the game's own flags."""

    def _choose(self, game_no: int, flags: dict[int, int]) -> int:
        mu, ex = _emulator()
        state_off = {1: 0x3E010, 2: 0xE574D4}[game_no]
        mu.mem_write(VILLAGE + state_off, struct.pack("<I", STATE))
        for off, value in flags.items():
            mu.mem_write(STATE + off, bytes([value]))
        return _call(mu, ex["VvfpFixHutsProbeChoose"], game_no, VILLAGE) & 0xFFFFFFFF

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_vv1_chooses_only_among_complete_huts_while_one_is_incomplete(self):
        none = self._choose(1, {0x9FE8: 0, 0x9FF0: 0, 0x9FF8: 0})
        self.assertEqual(none, 0xFFFFFFFF, "no hut complete: stock")
        every = self._choose(1, {0x9FE8: 1, 0x9FF0: 1, 0x9FF8: 1})
        self.assertEqual(every, 0xFFFFFFFF, "all complete: stock (its own fix-a-hut option)")
        seen = {self._choose(1, {0x9FE8: 1, 0x9FF0: 0, 0x9FF8: 1}) for _ in range(12)}
        self.assertTrue(seen <= {9, 11}, seen)
        self.assertEqual(self._choose(1, {0x9FE8: 0, 0x9FF0: 1, 0x9FF8: 0}), 10)

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_vv2_chooses_only_among_complete_huts_while_one_is_incomplete(self):
        self.assertEqual(self._choose(2, {0x2E818: 0, 0x2E820: 0, 0x2E828: 0}), 0xFFFFFFFF)
        self.assertEqual(self._choose(2, {0x2E818: 1, 0x2E820: 1, 0x2E828: 1}), 0xFFFFFFFF)
        seen = {self._choose(2, {0x2E818: 1, 0x2E820: 1, 0x2E828: 0}) for _ in range(12)}
        self.assertTrue(seen <= {24, 25}, seen)


class SecretCityTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFESTS["vv3"].read_text(encoding="utf-8"))
        self.overlay = self.manifest["pe_append_transaction"]["composition_overlays"][
            "vv3_enable_origins_exclusive_features"]

    def test_the_site_patch_replaces_the_exact_stock_test(self):
        # The hut site, the food site and the dispatcher site for the Builders
        # and Healers Work First addendum (tests/test_work_first.py).
        self.assertEqual([p["offset"] for p in self.overlay["hook_patches"]],
                         ["0x5B39E", "0x5C229", "0x5AF00", "0x5BFE0"])
        sched = self.overlay["hook_patches"][3]
        self.assertEqual(_stock("vv3", 0x45BFE0, 6), bytes.fromhex(sched["before"]))
        self.assertEqual(bytes.fromhex(sched["before"]), bytes.fromhex("51568B74240C"))
        after = bytes.fromhex(sched["after"])
        rel, = struct.unpack("<i", after[1:5])
        self.assertEqual(0x45BFE0 + 5 + rel, int(self.overlay["page_virtual_address"], 16) + 0x300)
        self.assertEqual(after[5:], b"\x90")
        patch = self.overlay["hook_patches"][0]
        self.assertEqual(int(patch["offset"], 16), 0x45B39E - 0x400000)
        self.assertEqual(_stock("vv3", 0x45B39E, 8), bytes.fromhex(patch["before"]))
        self.assertEqual(bytes.fromhex(patch["before"]), bytes.fromhex("3BFB0F849C030000"))
        after = bytes.fromhex(patch["after"])
        rel, = struct.unpack("<i", after[1:5])
        self.assertEqual(0x45B39E + 5 + rel, int(self.overlay["page_virtual_address"], 16))
        self.assertEqual(after[5:], b"\x90\x90\x90")

    def test_the_stub_resolves_the_companion_and_takes_the_stock_paths(self):
        page = bytes.fromhex(self.overlay["append_bytes"])
        base = int(self.overlay["page_virtual_address"], 16)
        self.assertEqual(base, 0x6DF800, "after the parentage overlay at 0x6DF400")
        self.assertEqual(self.overlay["overlay_offset"], "0xCB800")
        self.assertIn(b"VVFP Fix Huts.dll\0", page)
        # Build first, fix last: every option list goes to VvfpFixHutsFilter
        # (tests/test_builders_build_before_fixing.py runs it in the real
        # dispatcher).
        self.assertIn(b"VvfpFixHutsFilter\0", page)
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        text = "\n".join(f"{i.mnemonic} {i.op_str}" for i in md.disasm(page[:0x80], base))
        self.assertIn("lea ecx, [esp + 0x84]", text, "the option list, [esp+0x64] before pushad")
        self.assertIn("mov dword ptr [esp], eax", text, "the filtered count replaces edi")
        self.assertIn("cmp edi, ebx", text)
        self.assertIn("jmp 0x45b3a6", text, "an option remains: the stock pick")
        self.assertIn("call dword ptr [0x47c074]", text, "GetModuleHandleA")
        self.assertIn("call dword ptr [0x47c124]", text, "LoadLibraryA")
        self.assertIn("call dword ptr [0x47c128]", text, "GetProcAddress")
        self.assertIn("push 3", text)
        self.assertIn("je 0x45b742", text, "nothing to do: the stock path")
        self.assertIn("jmp 0x45b5f0", text, "a job was started: the stock epilogue")
        self.assertIn("mov dword ptr [0x6e0ff8], eax", text, "the resolved export, cached in .vv3md")
        # The stock import table really has those slots.
        pe = pefile.PE(str(STOCK["vv3"]), fast_load=True)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
        imports = {i.name: i.address for e in pe.DIRECTORY_ENTRY_IMPORT for i in e.imports if i.name}
        self.assertEqual(imports[b"GetModuleHandleA"], 0x47C074)
        self.assertEqual(imports[b"LoadLibraryA"], 0x47C124)
        self.assertEqual(imports[b"GetProcAddress"], 0x47C128)

    def _run_sched_stub(self, answer, cached=0):
        """The scheduler-entry stub at page+0x300, entered as `call 0x45BFE0`
        lands there.  answer: None = the companion is missing, else the
        export's address.  Returns (exit address, registers, stack, calls)."""
        from unicorn import UC_HOOK_CODE
        from unicorn.x86_const import (UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI,
                                       UC_X86_REG_EDX, UC_X86_REG_ESI)
        page = bytes.fromhex(self.overlay["append_bytes"])
        base = int(self.overlay["page_virtual_address"], 16)
        mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(base & ~0xFFF, 0x2000)          # through .vv3md's cache slots
        mu.mem_write(base, page[:0x400])
        mu.mem_write(0x6E0FEC, struct.pack("<I", cached))
        mu.mem_map(0x47C000, 0x1000)
        for iat, fn in ((0x47C074, 0x7A000000), (0x47C124, 0x7A000010), (0x47C128, 0x7A000020)):
            mu.mem_write(iat, struct.pack("<I", fn))
        mu.mem_map(0x7A000000, 0x1000)
        mu.mem_write(0x7A000000, b"\xC2\x04\x00" + b"\x90" * 13 + b"\xC2\x04\x00" + b"\x90" * 13 + b"\xC2\x08\x00")
        mu.mem_map(0x45B000, 0x2000)
        mu.mem_map(0x7B000000, 0x1000)
        mu.mem_map(STACK, 0x10000)
        esp = STACK + 0x8000
        mu.mem_write(esp, struct.pack("<3I", 0x45C38D, 0x12345678, 0xCAFEBABE))   # [ret][record]
        regs = {UC_X86_REG_EAX: 0xA1A1A1A1, UC_X86_REG_EBX: 3, UC_X86_REG_ECX: 0x12345678,
                UC_X86_REG_EDX: 0xD1D1D1D1, UC_X86_REG_ESI: 0x51515151, UC_X86_REG_EDI: 0x12345678,
                UC_X86_REG_EBP: 0xB0B0B0B0, UC_X86_REG_ESP: esp}
        for r, v in regs.items():
            mu.reg_write(r, v)
        state = {"exit": None, "calls": []}
        exits = {0x45BFE6, 0x7B000000}

        def hook(mu, address, size, user_data):
            if address in (0x7A000000, 0x7A000010, 0x7A000020):
                sp = mu.reg_read(UC_X86_REG_ESP)
                state["calls"].append(address)
                if address == 0x7A000020:
                    name = bytes(mu.mem_read(struct.unpack("<I", mu.mem_read(sp + 8, 4))[0], 32)).split(b"\0")[0]
                    state["calls"].append(name)
                    mu.reg_write(UC_X86_REG_EAX, 0 if answer is None else answer)
                else:
                    mu.reg_write(UC_X86_REG_EAX, 0 if answer is None else 0x10000000)
            elif address in exits:
                state["exit"] = address
                mu.emu_stop()

        mu.hook_add(UC_HOOK_CODE, hook)
        mu.emu_start(base + 0x300, 0, count=10000)
        out = {r: mu.reg_read(r) for r in regs}
        stack = struct.unpack("<5I", mu.mem_read(mu.reg_read(UC_X86_REG_ESP), 20))
        return state, regs, out, stack, struct.unpack("<I", mu.mem_read(0x6E0FEC, 4))[0]

    def test_the_scheduler_stub_jumps_to_the_companion_with_nothing_touched(self):
        from unicorn.x86_const import UC_X86_REG_ESP as ESP
        state, regs, out, stack, slot = self._run_sched_stub(0x7B000000)
        self.assertEqual(state["exit"], 0x7B000000, "the companion's VvfpFixHutsScheduler3")
        self.assertIn(b"VvfpFixHutsScheduler3", state["calls"])
        self.assertEqual(out, regs, "every register the scheduler would have received")
        self.assertEqual(stack[:2], (0x45C38D, 0x12345678), "[ret][record], as the caller left them")
        self.assertEqual(slot, 0x7B000000, "resolved once, cached")
        # Cached: no lookup at all.
        state, regs, out, stack, slot = self._run_sched_stub(None, cached=0x7B000000)
        self.assertEqual((state["exit"], state["calls"]), (0x7B000000, []))
        self.assertEqual(out, regs)

    def test_without_the_companion_the_scheduler_stub_runs_the_stock_prologue(self):
        from unicorn.x86_const import UC_X86_REG_ESI as ESI, UC_X86_REG_ESP as ESP
        for cached in (0, 1):
            with self.subTest(cached=cached):
                state, regs, out, stack, slot = self._run_sched_stub(None, cached=cached)
                self.assertEqual(state["exit"], 0x45BFE6, "the stock body after the displaced bytes")
                self.assertEqual(slot, 1, "the failure is remembered")
                # push ecx; push esi; mov esi, [esp+0xC] -- as the stock prologue.
                self.assertEqual(out[ESP], regs[ESP] - 8)
                self.assertEqual(stack[:4], (0x51515151, 0x12345678, 0x45C38D, 0x12345678))
                self.assertEqual(out[ESI], 0x12345678, "esi = the record argument")
                self.assertEqual({r: v for r, v in out.items() if r not in (ESP, ESI)},
                                 {r: v for r, v in regs.items() if r not in (ESP, ESI)})

    def test_the_cache_slot_is_unclaimed(self):
        """0x6E0FEC..0x6E0FFF in .vv3md (this row's four cache slots and
        lesson-cap's): Origins' and parentage's pages reference nothing there."""
        for path, key in ((ROOT / "data" / "vv3_origins_feature.json", None),
                          (ROOT / "data" / "vv3_parentage_feature.json", "vv3_write_parentage_log")):
            d = json.loads(path.read_text(encoding="utf-8"))
            feats = [f for f in d.get("features", [d]) if key is None or f["id"] == key]
            for f in feats:
                blobs = [bytes.fromhex(p["after"]) for p in f.get("patches", [])]
                t = f.get("pe_append_transaction", {})
                for lay in t.get("layouts", {}).values():
                    blobs.append(bytes.fromhex(lay["append_bytes"]))
                for ov in t.get("composition_overlays", {}).values():
                    blobs.append(bytes.fromhex(ov["append_bytes"]))
                for b in blobs:
                    for i in range(len(b) - 3):
                        v = struct.unpack_from("<I", b, i)[0]
                        self.assertFalse(0x6E0FEC <= v < 0x6E1000, f"{path.name} references {v:#x}")

    def test_the_composed_image_renders_in_every_mode_with_the_stub_in_place(self):
        import vv_fun_patcher as vfp
        build = next(b for b in vfp.load_builds() if b.id == "vv3")
        page = bytes.fromhex(self.overlay["append_bytes"])[:0x400]
        for mode in vfp.load_patch_modes():
            rendered, applied = vfp.render_patched_bytes(
                STOCK["vv3"], build, mode.id,
                ["vv3_enable_origins_exclusive_features", "vv3_write_parentage_log",
                 "vv3_builders_fix_huts"])
            self.assertEqual(bytes(rendered[0xCB800:0xCBC00]), page, mode.id)
            site = bytes(rendered[0x5B39E:0x5B3A6])
            self.assertEqual(site, bytes.fromhex(self.overlay["hook_patches"][0]["after"]), mode.id)
            owners = {edit["owner"] for edit in applied}
            self.assertIn("feature:vv3_builders_fix_huts", owners)


class RowTests(unittest.TestCase):
    def test_the_rows_are_default_off_registered_bundled_and_pin_the_dll(self):
        import vv_fun_patcher as vfp
        from vv_fun_patcher_gui import default_fun_patch_selection
        sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        ids = {p.id: p for p in vfp.load_public_fun_patches()}
        for game in STOCK:
            pid = f"{game}_builders_fix_huts"
            self.assertIn(pid, ids)
            self.assertTrue(default_fun_patch_selection(pid), "the owner: selectable by default")
            m = json.loads(MANIFESTS[game].read_text(encoding="utf-8"))
            self.assertEqual(m["dependencies"], [f"{game}_enable_origins_exclusive_features"])
            self.assertEqual([c["sha256"] for c in m["companion_files"]], [sha])
            self.assertIn("**Runs on the Origins-exclusive base, which the patcher installs automatically with it**", m["description"])
            self.assertIn("adds the Origins Upgrades buttons", m["description"])
            self.assertNotIn("Enable Origins-Exclusive Features", m["description"])
            if game == "vv2":
                # The new-hut test only (tests/test_finish_started_huts.py).
                self.assertEqual([q["offset"] for q in m["patches"]], ["0x600DE"])
            elif game != "vv3":
                self.assertEqual(m["patches"], [])
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn("assets/fix_huts/VVFP Fix Huts.dll", release)
        for game in STOCK:
            self.assertIn(f"data/{game}_builders_fix_huts_feature.json", release)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertEqual(readme.count("**Builders Fix Huts When Idle**"), 5)

    def test_the_four_per_frame_companions_carry_the_loader_bridge(self):
        for path, call in (
            (ROOT / "native/vv1_origins_icons/vv1_origins_icons.c", "vvfp_fix_huts_bridge(1);"),
            (ROOT / "native/vv4_origins_icons/vv4_origins_icons.c", "install(4)"),
            (ROOT / "native/vv5_task9_origins/vv5_task9_origins.c", "install(5)"),
        ):
            source = path.read_text(encoding="utf-8")
            self.assertIn('"VVFP Fix Huts.dll"', source, path.name)
            self.assertIn('GetProcAddress(companion, "VvfpFixHutsInstall")', source, path.name)
            self.assertIn(call, source, path.name)
        # The Lost Children's companion compiles A New Home's source in and
        # calls the shared bridge with its own game id.
        vv2 = (ROOT / "native/vv2_origins_icons/vv2_origins_icons.c").read_text(encoding="utf-8")
        self.assertIn('#include "../vv1_origins_icons/vv1_origins_icons.c"', vv2)
        self.assertIn("vvfp_fix_huts_bridge(2);", vv2)
        for dll in (ROOT / "assets/origins/VVFP VV1 Origins Icons.dll",
                    ROOT / "assets/origins/VVFP VV2 Origins Icons.dll",
                    ROOT / "assets/origins/VVFP VV4 Origins Icons.dll",
                    ROOT / "data/candidates/VVFP VV5 Task9 Origins Icons.dll"):
            self.assertIn(b"VVFP Fix Huts.dll", dll.read_bytes(), dll.name)


if __name__ == "__main__":
    unittest.main()
