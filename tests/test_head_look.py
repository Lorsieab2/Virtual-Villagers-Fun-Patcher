"""Change Appearance's head look -- Auto, Young or Old -- in all five games ("VVFP Head Look.dll",
native/vvfp_head_look; the owner, 2026-10-28).

THE DRAWS, by game, each the shown age compared against 1,100 alone, and where the game reaches it (direct
calls, and the scene classes whose vtables hold the callers, by the executable's own RTTI):

New Believers (record in ESI, `cmp dword [esi+0x1B8C], 0x44C`, 10 bytes)
  0x4722A2  in 0x4720E0, a villager in the village: setl/sub/and makes the head sheet's column offset 0 or
            8 (the old half).  <- 0x44F0F0 (0x44F284) <- theMainScene 0x4458C0 -> 0x442BD0 (0x442C53),
            CTechScene 0x440F80 (0x4411F0), theMenuScene 0x446740 (0x446751), theOverviewScene 0x448510
            (0x4485CD, the map).
  0x466DC1  in 0x466C40, a villager's figure: the old half of the head sheet (half its columns, the sprite's
            +8, added to the column) -- theVillagerScene (the Villager Details screen) 0x44B250 -> 0x468980
            (0x468992), CAdoptionScene 0x43E030 (0x43E0C2), theFernsaceDialog 0x419D80 (0x419DDF).  This
            settles the compare the request listed as UNCONFIRMED: it drives the Details portrait's head.
  0x466FE6  in 0x466EF0, a villager's portrait: setl/sub/and, the column offset 0 or 8 -- CIslandEventDialog
            0x417660 (0x417692), CAdoptionScene 0x43E030 (0x43E1C9).
  (0x43F824 in 0x43F6C0, CMausoleumScene 0x43FB50: a GRAVE's portrait in the Mausoleum, from the Roster of
   the Dead entry's own age at death (entry +0x1C).  Not a villager record: see the report.)

Each is emulated on the stock executable and on the executables the patcher renders (every population
mode, all of the game's patches): Auto draws young at 1,099 and old at 1,100; Young draws young at 1,100
and 3,000; Old draws old at 0 and 1,099; the registers and memory after the compare are the stock ones
but the flags (so the Origins masks, which hook elsewhere, see the state the game would give a villager of
that age); the head value and every record byte stay as they were.

THE FILE, by native/vvfp_head_look/head_look_harness.c on real files (round trip, following the villager
across a death and a packed reload, record reuse, a body not yet buried, a rename, copied and restored
files, another village's file, broken files, Start Over, a failed write, 256 records) and here through
the DLL itself on an emulated disk.

The live effect in a running game is NOT verified here.
"""
from __future__ import annotations

import functools
import hashlib
import json
import struct
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402

try:
    import pefile  # noqa: F401
    from unicorn import UC_HOOK_CODE

    from head_look_emulation import DLL, Game

    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

MODES = ("stock", "collection_progression", "immediate_fixed")
AUTO, YOUNG, OLD = 0, 1, 2


@functools.lru_cache(maxsize=None)
def _build(game: int):
    return {b.id: b for b in patcher.load_builds()}[f"vv{game}"]


def stock_path(game: int) -> Path:
    return ROOT / "inputs" / f"vv{game}-stock-copy" / _build(game).input_name


@functools.lru_cache(maxsize=None)
def stock_exe(game: int) -> bytes:
    return stock_path(game).read_bytes()


def have(game: int) -> bool:
    return HAVE_EMULATOR and stock_path(game).is_file() and DLL.is_file()


@functools.lru_cache(maxsize=None)
def _catalog() -> dict:
    return {p.id: p for p in patcher.load_fun_patches()}


def _public(game: int) -> list[str]:
    return [p.id for p in patcher.load_fun_patches()
            if p.game_id == f"vv{game}" and not p.raw.get("catalog_hidden") and p.raw.get("catalog_enabled", True)
            and p.raw.get("enabled", True) and p.id not in patcher.ALTERNATIVE_FUN_PATCH_IDS]


@functools.lru_cache(maxsize=None)
def rendered(game: int, mode: str) -> bytes:
    selection = _public(game)
    data, applied = patcher.render_patched_bytes(stock_path(game), _build(game), mode, list(selection))
    features = patcher._attach_automatic_companions(f"vv{game}", patcher._selected_fun_patches(_build(game),
                                                                                             list(selection)))
    patcher._finalize_published_bytes(data, _build(game), features, applied)
    return bytes(data)


# ---- each game's draws: (site, its length, how to run it, what it decides) ---------------------------------

def _column_offset(stop: int, reg: str, before: dict[str, int]):
    """The site's setl/sub/and: `reg` at `stop` is 0 for the young head, 8 for the old."""
    def run(g: Game, record: int) -> bool:

        g.run(SITE[g.game][run.site], regs=dict(before, esi=record), until=stop, count=100_000)
        value = g.p.reg(reg)
        assert value in (0, 8), hex(value)
        return value == 8
    return run


def _branch(young: int, old: int):
    """The site's jl: where the game goes on."""
    def run(g: Game, record: int) -> bool:
        stops = []
        hooks = [g.p.mu.hook_add(UC_HOOK_CODE, lambda mu, a, s, d: (stops.append(a), mu.emu_stop()),
                                 begin=at, end=at) for at in (young, old)]
        try:
            g.run(SITE[g.game][run.site], regs={"esi": record}, count=100_000)
        finally:
            for h in hooks:
                g.p.mu.hook_del(h)
        assert len(stops) == 1, stops
        return stops[0] == old
    return run


DRAWS = {
    5: {
        "village": (0x4722A2, 10, _column_offset(0x4722B9, "ecx", {"ecx": 0})),
        "figure": (0x466DC1, 10, _branch(0x466DDD, 0x466DCD)),
        "portrait": (0x466FE6, 10, _column_offset(0x46700B, "eax", {"eax": 0})),
    },
}
SITE = {game: {name: va for name, (va, _, _) in draws.items()} for game, draws in DRAWS.items()}
for _game, _draws in DRAWS.items():
    for _name, (_va, _length, _run) in _draws.items():
        _run.site = _name


def drawn_old(g: Game, name: str, record: int) -> bool:
    return DRAWS[g.game][name][2](g, record)


def _skip(game: int):
    return unittest.skipUnless(have(game), f"unicorn/pefile, the stock VV{game} or the DLL is missing")


class _DrawsBase:
    GAME = 0

    def game(self, exe: bytes | None = None, **kw) -> Game:
        return Game(self.GAME, exe if exe is not None else stock_exe(self.GAME), **kw)

    def test_installs_every_site(self):
        g = self.game()
        self.assertEqual(g.p.export("VvfpHeadLookInstalled", self.GAME), 1)
        for name, (va, length, _) in DRAWS[self.GAME].items():
            with self.subTest(site=name):
                self.assertEqual(g.p.read(va, 1), b"\xE9")
                self.assertEqual(g.p.read(va + 5, length - 5), b"\x90" * (length - 5))

    def test_auto_young_and_old_at_every_site(self):
        g = self.game()
        r = g.villager(3, "Kalani", age=1099, head=7)
        cases = [(AUTO, 1099, False), (AUTO, 1100, True), (AUTO, 0, False), (YOUNG, 1100, False),
                 (YOUNG, 3000, False), (OLD, 0, True), (OLD, 1099, True), (OLD, 2400, True)]
        for look, age, old in cases:
            g.p.put32(r + g.g["age"], age)
            self.assertEqual(g.set_look(3, look), 1)
            for name in DRAWS[self.GAME]:
                with self.subTest(site=name, look=look, age=age):
                    before = g.p.read(r, g.g["stride"])
                    self.assertEqual(drawn_old(g, name, r), old)
                    self.assertEqual(g.p.read(r, g.g["stride"]), before)          # no record byte written
                    self.assertEqual(g.p.u32(r + g.g["head"]), 7)                  # the head value unchanged

    def test_registers_are_the_stock_compares(self):
        """The stub leaves every register as the stock compare would: only the flags carry the look."""
        stock = self.game(start=False)
        hooked = self.game()
        for g in (stock, hooked):
            g.villager(2, "Moana", age=1500, head=3)
        hooked.set_look(2, YOUNG)
        for name, (va, length, _) in DRAWS[self.GAME].items():
            with self.subTest(site=name):
                seen = []
                for g in (stock, hooked):
                    regs = {"eax": 0x11, "ebx": 0x22, "ecx": 0x33, "edx": 0x44, "edi": 0x55, "ebp": 0x66,
                            "esi": g.record(2)}
                    g.run(va, regs=regs, until=va + length, count=100_000)
                    seen.append({r: g.p.reg(r) for r in ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")})
                self.assertEqual(seen[0], seen[1])

    def test_a_record_that_is_not_a_villager_keeps_the_real_age(self):
        g = self.game()
        fake = g.p.alloc(0x3000)
        g.p.put32(fake + g.g["age"], 2000)
        for name in DRAWS[self.GAME]:
            with self.subTest(site=name):
                self.assertTrue(drawn_old(g, name, fake))
        g.villager(1, "Ana", age=2000)
        g.set_look(1, YOUNG)
        misaligned = g.record(1) + 4
        g.p.put32(misaligned + g.g["age"], 2000)
        for name in DRAWS[self.GAME]:
            with self.subTest(site=name, misaligned=True):
                self.assertTrue(drawn_old(g, name, misaligned))

    def test_the_look_follows_the_villager_not_the_record(self):
        g = self.game()
        g.villager(0, "Ana", age=600)
        g.villager(1, "Bea", age=600)
        g.villager(2, "Cal", age=600)
        self.assertEqual(g.set_look(2, OLD), 1)
        # Bea dies and is buried; the save is reloaded, packed: Cal is now in record 1.
        g.p.write(g.record(1) + g.g["present"], b"\x00")
        g.look(0)
        stride = g.g["stride"]
        g.p.write(g.record(1), g.p.read(g.record(2), stride))
        g.p.write(g.record(2), bytes(stride))
        fresh = self.game()
        fresh.disk.files = dict(g.disk.files)
        fresh.disk.folders = set(g.disk.folders)
        fresh.p.write(fresh.record(0), g.p.read(g.record(0), 3 * stride))
        self.assertTrue(drawn_old(fresh, next(iter(DRAWS[self.GAME])), fresh.record(1)))
        self.assertEqual(fresh.look(1), OLD)
        self.assertEqual(fresh.look(0), AUTO)

    def test_the_file_drives_the_draws(self):
        """A look written by one session is read by the next from the per-save file."""
        g = self.game()
        g.villager(4, "Iolana", age=300)
        self.assertEqual(g.set_look(4, OLD), 1)
        data = g.disk.files[g.disk.looks_file(1)]
        count = 256 if g.g["count"] == 256 else g.g["count"]
        self.assertEqual(data[:12], struct.pack("<III", 0x314C4856, self.GAME, count))
        self.assertEqual(data[12 + count * 4 + 4], OLD)
        later = self.game()
        later.disk.files = dict(g.disk.files)
        later.disk.folders = set(g.disk.folders)
        later.villager(4, "Iolana", age=300)
        for name in DRAWS[self.GAME]:
            with self.subTest(site=name):
                self.assertTrue(drawn_old(later, name, later.record(4)))

    def test_no_slot_no_file_every_look_is_auto(self):
        g = self.game(slot=0)
        r = g.villager(1, "Ana", age=1100)
        self.assertEqual(g.set_look(1, YOUNG), 0)
        self.assertTrue(drawn_old(g, next(iter(DRAWS[self.GAME])), r))
        self.assertEqual(g.disk.files, {})

    def test_all_or_nothing(self):
        for va, length, _ in DRAWS[self.GAME].values():
            for k in (0, length - 1):
                exe = bytearray(stock_exe(self.GAME))
                pe = pefile.PE(data=bytes(exe))
                exe[pe.get_offset_from_rva(va + k - 0x400000)] ^= 0xFF
                g = self.game(bytes(exe))
                with self.subTest(va=hex(va), byte=k):
                    self.assertEqual(g.p.export("VvfpHeadLookInstalled", self.GAME), 0)
                    for other, other_len, _ in DRAWS[self.GAME].values():
                        if other != va:
                            self.assertNotEqual(g.p.read(other, 1), b"\xE9")

    def test_another_game_installs_nothing(self):
        g = self.game(start=False)
        g.p.export("VvfpStartup", 1 if self.GAME != 1 else 2, 0)
        self.assertEqual(g.p.export("VvfpHeadLookInstalled", self.GAME), 0)
        for va, _, _ in DRAWS[self.GAME].values():
            self.assertNotEqual(g.p.read(va, 1), b"\xE9")

    def test_every_mode_with_every_patch(self):
        for mode in MODES:
            exe = rendered(self.GAME, mode)
            with self.subTest(mode=mode):
                g = self.game(exe)
                self.assertEqual(g.p.export("VvfpHeadLookInstalled", self.GAME), 1)
                r = g.villager(5, "Keoni", age=200)
                g.set_look(5, OLD)
                for name in DRAWS[self.GAME]:
                    self.assertTrue(drawn_old(g, name, r), name)
                g.set_look(5, AUTO)
                for name in DRAWS[self.GAME]:
                    self.assertFalse(drawn_old(g, name, r), name)


@_skip(5)
class NewBelieversDraws(_DrawsBase, unittest.TestCase):
    GAME = 5


class TheSidecar(unittest.TestCase):
    def test_the_harness_on_real_files(self):
        """native/vvfp_head_look/head_look_harness.c: round trip, follow, reuse, rename, copies, broken files,
        Start Over, a failed write, 256 records."""
        script = ROOT / "scripts" / "build_head_look_harness.ps1"
        result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                                capture_output=True, text=True, timeout=600)
        if result.returncode != 0 and "cl.exe" in (result.stderr + result.stdout) and "not recognized" in (
                result.stderr + result.stdout):
            self.skipTest("the compiler is not installed")
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-2000:])
        self.assertIn("failures: 0", result.stdout)
        self.assertGreaterEqual(result.stdout.count("[PASS]"), 50)


class TheCompanion(unittest.TestCase):
    def test_started_from_the_second_word(self):
        self.assertIn("VVFP Head Look.dll", patcher.STARTUP_LOADER_COMPANIONS_2)
        header = (ROOT / "native" / "shared" / "startup_companions_2.h").read_text(encoding="utf-8")
        self.assertIn('"VVFP Head Look.dll"', header)
        self.assertEqual(list(patcher.STARTUP_LOADER_COMPANIONS_2),
                         [line.strip().strip('",') for line in header.splitlines()
                          if line.strip().startswith('"VVFP ')])

    def test_shipped_by_each_origins_row(self):
        dll = ROOT / "assets" / "head_look" / "VVFP Head Look.dll"
        digest = hashlib.sha256(dll.read_bytes()).hexdigest().upper()
        for game in DRAWS:
            row = ORIGINS_ROWS[game]
            with self.subTest(game=game):
                data = json.loads((ROOT / "data" / row).read_text(encoding="utf-8"))
                files = [f for f in data["companion_files"] if f["destination"] == "VVFP Head Look.dll"]
                self.assertEqual(len(files), 1)
                self.assertEqual(files[0]["source"], "assets/head_look/VVFP Head Look.dll")
                self.assertEqual(files[0]["sha256"], digest)

    def test_the_bit_is_set_when_origins_ships(self):
        bit = 1 << patcher.STARTUP_LOADER_COMPANIONS_2.index("VVFP Head Look.dll")
        for game in DRAWS:
            with self.subTest(game=game):
                origins = ORIGINS_IDS[game]
                features = patcher._attach_automatic_companions(
                    f"vv{game}", patcher._selected_fun_patches(_build(game), [origins]))
                self.assertEqual(patcher._startup_loader_mask_2(features) & bit, bit)


ORIGINS_ROWS = {5: "vv5_task9_native_actions.json"}
ORIGINS_IDS = {5: "vv5_enable_origins_exclusive_features"}


if __name__ == "__main__":
    unittest.main()
