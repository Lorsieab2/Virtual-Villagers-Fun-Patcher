"""Builders and Healers Work First (all five games) -- the addendum to
Builders Fix Huts When Idle.

The owner: "in both low and high food situations, builders and healers still
should prioritize fixing huts over other stuff for all 5 games" -- builders
their building work, healers their healing and study, first, while not every
population hut is built -- and "make the work patches an addendum to the
preexisting ones".  Codex on #462: a forced job with nothing to do must fall
back to the stock choice, not leave the villager idle.

Pinned here:

* Each game's work dispatcher entry, its displaced bytes and the adult
  scheduler's call sites are what the stubs assume, read from the stock
  executables.
* The DLL's dispatcher stubs (VV1/VV2/VV4/VV5), RUN in an emulator with the
  dispatcher's body scripted: for a builder or healer called from the adult
  scheduler with a hut unbuilt, the own job is asked for first; if it starts
  something the scheduler gets "started" (with the stock ret N); if it starts
  nothing, the scheduler's own request runs (so the villager is never left
  idle by the addendum).  Any other job, any other caller, a request that is
  already the own job, or all huts built runs the stock request alone.
* The Secret City's dispatcher stub in the fix-huts page, run the same way
  with VvfpWorkFirstFirst scripted, and with the DLL missing.
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
INDEX = 7

G = {
    "vv1": dict(disp=0x4472C0, stock="8B44240885C0", calls=(0x448350, 0x44837D), building=4, healing=5, ret=8),
    "vv2": dict(disp=0x45FBF0, stock="8B44240885C0", calls=(0x461A03, 0x461A30), building=5, healing=3, ret=8),
    "vv3": dict(disp=0x45AF00, stock="8B44240881ECA0000000", calls=(0x45C237, 0x45C275, 0x45C28A),
                building=4, healing=2, ret=8),
    "vv4": dict(disp=0x4639B0, stock="8B44240481EC98000000", calls=(0x4659CD, 0x465A12, 0x465A25),
                building=4, healing=2, ret=4),
    "vv5": dict(disp=0x46C540, stock="81EC94000000", calls=(0x46F28C, 0x46F2D1, 0x46F2E5),
                building=4, healing=2, ret=4),
}
HUT_PREDICATE = {"vv4": (0x438960, 19), "vv5": (0x43AE80, 19)}


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


class DispatchRun:
    """Enter a dispatcher stub as `call dispatcher` from `call_site` would.
    The dispatcher's body (after the displaced bytes) is scripted: it records
    the job it was asked for and answers `starts(job)`."""

    def __init__(self, game: str, call_site: int, selected: int, requested: int,
                 huts_done: bool, starts, level: int = 3):
        g = G[game]
        stub = _probe(GAME_NO[game])[4]
        mu, _ = _emulator()
        if game == "vv1":
            mu.mem_write(VILLAGE + 0x3E010, struct.pack("<I", STATE))
            for off in (0x9FE8, 0x9FF0, 0x9FF8):
                mu.mem_write(STATE + off, bytes([1]))
            if not huts_done:
                mu.mem_write(STATE + 0x9FF0, bytes([0]))
            mu.mem_write(VILLAGE + INDEX * 0x3D8 + 0x3D0, struct.pack("<i", selected))
            mu.mem_write(STATE + 0xA2CC, struct.pack("<i", level))
        elif game == "vv2":
            mu.mem_write(VILLAGE + 0xE574D4, struct.pack("<I", STATE))
            for off in (0x2E818, 0x2E820, 0x2E828):
                mu.mem_write(STATE + off, bytes([1]))
            if not huts_done:
                mu.mem_write(STATE + 0x2E828, bytes([0]))
            mu.mem_write(VILLAGE + INDEX * 0xE48C + 0x7F8, struct.pack("<i", selected))
            mu.mem_write(STATE + 0x2EA84, struct.pack("<i", level))
        else:
            mu.mem_write(VILLAGE + 0x1B88, struct.pack("<I", RECORD))
            mu.mem_write(RECORD + (0x1C70 if game == "vv4" else 0x1C74), struct.pack("<i", selected))
        self.huts_done, self.starts, self.game, self.g = huts_done, starts, game, g
        self.body = g["disp"] + len(bytes.fromhex(g["stock"]))
        self.ret = call_site + 5
        for va in (self.ret, self.body) + ((HUT_PREDICATE[game][0],) if game in HUT_PREDICATE else ()):
            try:
                mu.mem_map(va & ~0xFFF, 0x1000)
            except Exception:
                pass
            mu.mem_write(va, b"\xC3")
        esp = STACK - 0x400
        args = struct.pack("<2I", INDEX, requested) if g["ret"] == 8 else struct.pack("<I", requested)
        mu.mem_write(esp, struct.pack("<I", self.ret) + args)
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.reg_write(UC_X86_REG_ECX, VILLAGE)
        mu.reg_write(UC_X86_REG_EBX, 0x11111111)
        mu.reg_write(UC_X86_REG_ESI, 0x22222222)
        mu.reg_write(UC_X86_REG_EDI, 0x33333333)
        self.asked, self.exit, self.stock_frame = [], None, None
        mu.hook_add(UC_HOOK_CODE, self._hook)
        mu.emu_start(stub, 0, count=200000)
        self.mu, self.esp_before = mu, esp

    def _hook(self, mu, address, size, user_data):
        g = self.g
        if self.game in HUT_PREDICATE and address == HUT_PREDICATE[self.game][0]:
            sp = mu.reg_read(UC_X86_REG_ESP)
            ret, arg = struct.unpack("<2I", mu.mem_read(sp, 8))
            done = self.huts_done or arg != HUT_PREDICATE[self.game][1] + 3
            mu.reg_write(UC_X86_REG_EAX, 1 if done else 0)
            mu.reg_write(UC_X86_REG_ESP, sp + 8)
            mu.reg_write(UC_X86_REG_EIP, ret)
        elif address == self.body:
            # The body runs after the displaced bytes, which moved esp by the
            # stock prologue's own amount; the caller's frame sits above it.
            sp = mu.reg_read(UC_X86_REG_ESP)
            shift = {"vv1": 0, "vv2": 0, "vv3": 0xA0, "vv4": 0x98, "vv5": 0x94}[self.game]
            frame = sp + shift
            ret, = struct.unpack("<I", mu.mem_read(frame, 4))
            job_at = frame + (8 if g["ret"] == 8 else 4)
            job, = struct.unpack("<i", mu.mem_read(job_at, 4))
            self.asked.append(job)
            self.stock_frame = (ret, mu.reg_read(UC_X86_REG_ECX))
            # the displaced `mov eax, [esp+N]` (not VV5) loads the job argument
            if self.game != "vv5":
                assert mu.reg_read(UC_X86_REG_EAX) == job, (hex(mu.reg_read(UC_X86_REG_EAX)), job)
            mu.reg_write(UC_X86_REG_EAX, 1 if self.starts(job) else 0)
            mu.reg_write(UC_X86_REG_ESP, frame + 4 + g["ret"])
            mu.reg_write(UC_X86_REG_EIP, ret)
        elif address == self.ret:
            self.exit = address
            mu.emu_stop()

    def reg(self, r):
        return self.mu.reg_read(r)


class SiteTests(unittest.TestCase):
    def test_the_dispatcher_entries_and_the_scheduler_call_sites(self):
        for game, g in G.items():
            with self.subTest(game=game):
                n = len(bytes.fromhex(g["stock"]))
                self.assertEqual(_stock(game, g["disp"], n), bytes.fromhex(g["stock"]))
                for call in g["calls"]:
                    code = _stock(game, call, 5)
                    self.assertEqual(code[0], 0xE8, hex(call))
                    rel, = struct.unpack("<i", code[1:])
                    self.assertEqual(call + 5 + rel, g["disp"], hex(call))
                if game != "vv3":
                    k, va, stock, patched, stub = _probe(GAME_NO[game])
                    self.assertEqual((va, stock), (g["disp"], bytes.fromhex(g["stock"])))
                    rel, = struct.unpack("<i", patched[1:5])
                    self.assertEqual(va + 5 + rel, stub)
                    self.assertEqual(patched[5:], b"\x90" * (n - 5))


class DispatcherStubTests(unittest.TestCase):
    GAMES = ("vv1", "vv2", "vv4", "vv5")

    def other_job(self, g):
        return next(j for j in range(0, 6) if j not in (g["building"], g["healing"]))

    def test_the_own_job_is_tried_first_and_a_start_is_returned(self):
        for game in self.GAMES:
            g = G[game]
            for own in (g["building"], g["healing"]):
                for call in g["calls"]:
                    with self.subTest(game=game, own=own, call=hex(call)):
                        r = DispatchRun(game, call, own, self.other_job(g), huts_done=False,
                                        starts=lambda job, own=own: job == own)
                        self.assertEqual(r.asked, [own], "only the own job, and it started")
                        self.assertEqual(r.exit, call + 5)
                        self.assertEqual(r.reg(UC_X86_REG_EAX) & 0xFF, 1, "started")
                        self.assertEqual(r.reg(UC_X86_REG_ESP), r.esp_before + 4 + g["ret"], "ret N")
                        self.assertEqual(r.reg(UC_X86_REG_ECX), VILLAGE)
                        self.assertEqual((r.reg(UC_X86_REG_EBX), r.reg(UC_X86_REG_ESI), r.reg(UC_X86_REG_EDI)),
                                         (0x11111111, 0x22222222, 0x33333333))

    def test_with_nothing_of_their_own_to_do_the_stock_request_runs(self):
        # Codex #462: never leave the villager idle -- the scheduler's own
        # request still runs when the own job starts nothing.
        for game in self.GAMES:
            g = G[game]
            requested = self.other_job(g)
            for started in (True, False):
                with self.subTest(game=game, stock_request_starts=started):
                    r = DispatchRun(game, g["calls"][0], g["building"], requested, huts_done=False,
                                    starts=lambda job: started and job == requested)
                    self.assertEqual(r.asked, [g["building"], requested])
                    self.assertEqual(r.exit, g["calls"][0] + 5)
                    self.assertEqual(r.reg(UC_X86_REG_EAX) & 0xFF, 1 if started else 0)
                    self.assertEqual(r.reg(UC_X86_REG_ESP), r.esp_before + 4 + g["ret"])
                    self.assertEqual(r.stock_frame, (g["calls"][0] + 5, VILLAGE),
                                     "the stock request sees the scheduler's own frame and ecx")

    def test_healers_come_first_even_with_every_hut_built(self):
        # The owner, v1.35.38: "For healers, they should study medicine at all
        # food levels, when they can study medicine" -- not tied to the huts,
        # unlike builders.
        for game in self.GAMES:
            g = G[game]
            with self.subTest(game=game):
                r = DispatchRun(game, g["calls"][0], g["healing"], self.other_job(g), huts_done=True,
                                starts=lambda job: job == g["healing"])
                self.assertEqual(r.asked, [g["healing"]])
                self.assertEqual(r.reg(UC_X86_REG_EAX) & 0xFF, 1)
                r = DispatchRun(game, g["calls"][0], g["healing"], self.other_job(g), huts_done=True,
                                starts=lambda job: False)
                self.assertEqual(r.asked, [g["healing"], self.other_job(g)], "can't study: the stock request")

    def test_below_level_3_a_builder_with_every_hut_built_comes_first(self):
        # A New Home / The Lost Children: below Building level 3 a built hut is
        # hut work even once every one is built (Codex on #464).
        for game in ("vv1", "vv2"):
            g = G[game]
            with self.subTest(game=game):
                r = DispatchRun(game, g["calls"][0], g["building"], self.other_job(g), huts_done=True,
                                starts=lambda job: job == g["building"], level=2)
                self.assertEqual(r.asked, [g["building"]])

    def test_everything_else_runs_the_stock_request_alone(self):
        for game in self.GAMES:
            g = G[game]
            other = self.other_job(g)
            cases = [
                (g["calls"][0], g["building"], other, True),     # all huts built
                (g["calls"][0], other, g["building"], False),     # not a builder or healer
                (g["calls"][0], g["building"], g["building"], False),  # already the own job
                (0x401000, g["healing"], other, False),           # another caller
            ]
            for call, selected, requested, huts_done in cases:
                with self.subTest(game=game, call=hex(call), selected=selected, requested=requested,
                                  huts_done=huts_done):
                    r = DispatchRun(game, call, selected, requested, huts_done, starts=lambda job: True)
                    self.assertEqual(r.asked, [requested])
                    self.assertEqual(r.reg(UC_X86_REG_ESP), r.esp_before + 4 + g["ret"])


class SecretCityTests(unittest.TestCase):
    def setUp(self):
        m = json.loads((ROOT / "data" / "vv3_builders_fix_huts_feature.json").read_text(encoding="utf-8"))
        self.overlay = m["pe_append_transaction"]["composition_overlays"]["vv3_enable_origins_exclusive_features"]
        self.page = bytes.fromhex(self.overlay["append_bytes"])
        self.base = int(self.overlay["page_virtual_address"], 16)

    def test_the_site_patch(self):
        (patch,) = [p for p in self.overlay["hook_patches"] if p["offset"] == "0x5AF00"]
        self.assertEqual(bytes.fromhex(patch["before"]), _stock("vv3", 0x45AF00, 10))
        after = bytes.fromhex(patch["after"])
        rel, = struct.unpack("<i", after[1:5])
        self.assertEqual(0x45AF00 + 5 + rel, self.base + 0x200)
        self.assertEqual(after[5:], b"\x90" * 5)
        self.assertIn(b"VVFP Work First.dll\0", self.page)
        self.assertIn(b"VvfpWorkFirstFirst\0", self.page)

    def _run(self, answer, requested, starts, call=0x45C275):
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
        mu.mem_map(0x45A000, 0x1000)
        mu.mem_write(0x45AF0A, b"\xC3")
        mu.mem_map(0x45C000, 0x1000)
        ret = call + 5
        mu.mem_write(ret, b"\xC3")
        mu.mem_map(STACK - 0x10000, 0x20000)
        esp = STACK - 0x400
        mu.mem_write(esp, struct.pack("<3I", ret, RECORD, requested))
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.reg_write(UC_X86_REG_ECX, 0x44444444)
        state = {"exit": None, "args": None, "asked": []}

        def hook(mu, address, size, user_data):
            sp = mu.reg_read(UC_X86_REG_ESP)
            if address in (0x7A000000, 0x7A000010):
                mu.reg_write(UC_X86_REG_EAX, 0 if answer is None else 0x10000000)
            elif address == 0x7A000020:
                mu.reg_write(UC_X86_REG_EAX, 0 if answer is None else 0x7B000000)
            elif address == 0x7B000000:
                state["args"] = struct.unpack("<4I", mu.mem_read(sp + 4, 16))
                mu.reg_write(UC_X86_REG_EAX, answer & 0xFFFFFFFF)
            elif address == 0x45AF0A:
                frame = sp + 0xA0
                r, rec, job = struct.unpack("<3I", mu.mem_read(frame, 12))
                state["asked"].append(job)
                assert rec == RECORD and mu.reg_read(UC_X86_REG_ECX) == 0x44444444
                assert mu.reg_read(UC_X86_REG_EAX) == job
                mu.reg_write(UC_X86_REG_EAX, 1 if starts(job) else 0)
                mu.reg_write(UC_X86_REG_ESP, frame + 12)
                mu.reg_write(UC_X86_REG_EIP, r)
            elif address == ret:
                state["exit"] = address
                mu.emu_stop()

        mu.hook_add(UC_HOOK_CODE, hook)
        mu.emu_start(self.base + 0x200, 0, count=20000)
        return state, mu, esp, ret

    def test_the_own_job_first_then_the_stock_request(self):
        state, mu, esp, ret = self._run(answer=4, requested=0, starts=lambda j: j == 4)
        self.assertEqual(state["args"], (3, ret, RECORD, 0), "VvfpWorkFirstFirst(3, caller, record, job)")
        self.assertEqual(state["asked"], [4])
        self.assertEqual(mu.reg_read(UC_X86_REG_EAX) & 0xFF, 1)
        self.assertEqual(mu.reg_read(UC_X86_REG_ESP), esp + 12, "ret 8")
        state, mu, esp, ret = self._run(answer=2, requested=0, starts=lambda j: j == 0)
        self.assertEqual(state["asked"], [2, 0], "nothing to heal: the scheduler's farming runs")
        self.assertEqual(mu.reg_read(UC_X86_REG_EAX) & 0xFF, 1)
        self.assertEqual(mu.reg_read(UC_X86_REG_ESP), esp + 12)

    def test_minus_one_or_no_dll_runs_the_stock_request_alone(self):
        for answer in (-1, None):
            state, mu, esp, ret = self._run(answer=answer, requested=3, starts=lambda j: True)
            self.assertEqual(state["asked"], [3])
            self.assertEqual(state["exit"], ret)
            self.assertEqual(mu.reg_read(UC_X86_REG_ESP), esp + 12)


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
