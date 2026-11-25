"""New Believers' "Max Divine Energy Continues to Increase" (the owner, 2026-11-25: "removes the hardcoded 1000 max
energy to allow it to increase with population and collectibles").

EMULATED, on the executable the patcher renders for the row, in each of the three public modes and with 256 Villagers
(Experimental):

* "VVFP Divine Energy Cap.dll" is started as VVFP More Companions.dll starts it (VvfpStartup(5, ...));
* the game's own cap routine 0x425020 runs, whole, on a village manager, with the game's own adder 0x424F80; stood in
  for: the believer count 0x4713F0, the statue's stage 0x4271C0, the puzzle test 0x43AE80, the tech level 0x423600,
  the collectible count 0x413F50 and the adder's display refresh 0x450530 / 0x4500D0;
* the HUD's bar call (0x443201..0x443223) runs with the game's own bar 0x450380; stood in for: the bar object's getter
  0x450530 and the two sprite draws 0x409B90 / 0x409BA0 (recorded, so the frame, fill and glow slices are counted).
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402

try:
    from test_companion_installs_all_or_none import HAVE_EMULATOR, Machine, render, stock_path, with_requirements
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

ROW = "vv5_max_divine_energy_increases"
NAME = "Max Divine Energy Continues to Increase"
DLL_NAME = "VVFP Divine Energy Cap.dll"
DLL = ROOT / "assets" / "divine_energy_cap" / DLL_NAME
FEATURE = ROOT / "data" / f"{ROW}_feature.json"
MODES = ("stock", "collection_progression", "immediate_fixed")

CAP_ROUTINE, BAR_CALL_FROM, BAR_CALL_BACK = 0x425020, 0x443201, 0x443223
ENERGY, ENERGY_CAP, FORCED = 0x17D64, 0x17D60, 0x17E11
SITES = {0x4250B4: bytes.fromhex("81FEE80300007E07BEE8030000"),
         0x4250D8: bytes.fromhex("C787607D0100E8030000"),
         0x44321E: bytes.fromhex("E85DD10000")}
FRAME, FILL, GLOW = 0x1F, 0x0B, 0x20          # the stand-in bar's three sprites (+0x1C, +0x0C, +0x20)
FRAME_PIXELS = 372


def formula(believers: int, *, statue: int = 2, solved: bool = True, spirituality: int = 3, relics: int = 24) -> int:
    """The cap routine's sum, unclamped (0x425020..0x4250B1)."""
    total = 5 * (believers + 2)
    total += 50 * (statue >= 1) + 50 * (statue >= 2) + 100 * solved
    total += 50 * (spirituality >= 2) + 50 * (spirituality >= 3)
    return total + (90 if relics >= 24 else 3 * relics)


class Island(Machine):
    """The rendered game and the companion; the cap routine and the HUD's bar with stand-ins around them."""

    def __init__(self, exe: bytes):
        super().__init__(exe, DLL)
        self.manager = self.alloc(0x18000)
        self.believers, self.statue, self.solved, self.spirituality, self.relics = 0, 0, False, 1, 0
        self.draws: list[tuple[int, int]] = []
        self.bar = self.alloc(0x40)
        self.put32(self.bar, self.alloc(0x10))
        for at, sprite in ((0x0C, FILL), (0x1C, FRAME), (0x20, GLOW)):
            self.put32(self.bar + at, sprite)
        self.stub(0x4713F0, lambda p: (self.believers, 0))
        self.stub(0x4271C0, lambda p: (self.statue, 0))
        self.stub(0x43AE80, lambda p: (int(self.solved and p.arg(0) == 14), 4))
        self.stub(0x423600, lambda p: (self.spirituality if p.arg(0) == 5 else 1, 4))
        self.stub(0x413F50, lambda p: (self.relics if p.arg(0) == 0x68 else 0, 0x10))
        self.stub(0x450530, lambda p: (self.bar, 0))
        self.stub(0x4500D0, lambda p: (0, 0))
        self.stub(0x409B90, lambda p: (self.draws.append((p.arg(0), p.arg(1))), (0, 0xC))[1])
        self.stub(0x409BA0, lambda p: (self.draws.append((p.arg(0), p.arg(1))), (0, 0x10))[1])

    def village(self, believers: int, *, statue: int = 2, solved: bool = True, spirituality: int = 3,
                relics: int = 24, energy: int = 0, cap: int = 50, forced: bool = False) -> None:
        self.believers, self.statue, self.solved = believers, statue, solved
        self.spirituality, self.relics = spirituality, relics
        self.put32(self.manager + ENERGY, energy)
        self.put32(self.manager + ENERGY_CAP, cap)
        self.write(self.manager + FORCED, b"\x01" if forced else b"\0")

    def update(self) -> tuple[int, int]:
        """The cap routine once (as every village update runs it): (cap, Divine Energy)."""
        self.call(CAP_ROUTINE, [], ecx=self.manager)
        return self.i32(self.manager + ENERGY_CAP), self.i32(self.manager + ENERGY)

    def i32(self, va: int) -> int:
        value = self.u32(va)
        return value - (1 << 32) if value & 0x80000000 else value

    def hud(self, cap: int, energy: int, cost: int = 0) -> dict[int, list[int]]:
        """The HUD's bar call with this cap, Divine Energy and chosen power's cost: each sprite's slice x's."""
        self.put32(self.manager + ENERGY_CAP, cap)
        self.put32(self.manager + ENERGY, energy)
        self.draws = []
        self.call(BAR_CALL_FROM, [], regs={"ebp": self.manager, "eax": cost}, until=BAR_CALL_BACK)
        out: dict[int, list[int]] = {FRAME: [], FILL: [], GLOW: []}
        for sprite, x in self.draws:
            out[sprite].append(x)
        return out


def _skip() -> str | None:
    if not HAVE_EMULATOR:
        return "unicorn/pefile not installed"
    if not stock_path(5).is_file():
        return "stock executable not present (inputs/)"
    if not DLL.is_file():
        return f"{DLL} missing"
    return None


class TheRow(unittest.TestCase):
    def test_the_row(self):
        row = json.loads(FEATURE.read_text(encoding="utf-8"))
        self.assertEqual((row["id"], row["name"], row["game_id"]), (ROW, NAME, "vv5"))
        self.assertEqual((row["dependencies"], row["patches"]), ([], []))
        self.assertIn("Removes the hardcoded 1,000 maximum Divine Energy", row["description"])
        for bold in ("**Below 1,000 nothing changes.**",
                     "**Works the same with every other patch and in every population mode.**",
                     "**Not yet seen in a running game**"):
            self.assertIn(bold, row["description"])
        self.assertEqual([c["destination"] for c in row["companion_files"]], [DLL_NAME])
        self.assertEqual([(int(d["va"], 16), bytes.fromhex(d["stock_bytes"])) for d in row["runtime_detours"]],
                         list(SITES.items()))
        self.assertIn(ROW, {p.id for p in patcher.load_public_fun_patches()})
        self.assertEqual(patcher.STARTUP_LOADER_COMPANIONS_3[-1], DLL_NAME, "appended to the third word")
        header = (ROOT / "native" / "shared" / "startup_companions_3.h").read_text(encoding="utf-8")
        self.assertIn(f'"{DLL_NAME}"', header)

    def test_defaults(self):
        """The owner (2026-11-25): "owners defaults on only for the divine energy cap"."""
        from vv_fun_patcher_gui import (default_fun_patch_selection, owners_default_fun_patch_selection,
                                        select_all_fun_patch_selection)
        self.assertEqual((default_fun_patch_selection(ROW), owners_default_fun_patch_selection(ROW),
                          select_all_fun_patch_selection(ROW)), (False, True, False))

    def test_registered_bundled_documented(self):
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        guide = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        how = (ROOT / "How to Use.txt").read_text(encoding="utf-8")
        row = json.loads(FEATURE.read_text(encoding="utf-8"))
        for path in (f"assets/divine_energy_cap/{DLL_NAME}", f"data/{ROW}_feature.json"):
            self.assertIn(f'"{path}"', release)
        self.assertIn(f"- Patch ID: `{ROW}`", readme)
        self.assertIn(row["description"], readme)
        whats_new = readme.split("## What's new in v1.35.101")[1].split("\n## ")[0]
        self.assertIn(f"- **{NAME}** (New Believers, new;", whats_new)
        self.assertEqual(len([e for e in guide["patches"] if ROW in e.get("ids", [])]), 1)
        self.assertIn(NAME.upper() + " (NEW BELIEVERS)", how)

    def test_the_game_mechanics_line(self):
        import vv_game_mechanics as gm
        import vv_game_mechanics_vv5 as vv5

        self.assertEqual(vv5.ENERGY_CAP_ROW, ROW)
        on, off = vv5.energy_cap_line(True), vv5.energy_cap_line(False)
        self.assertIn("at most 1,000", off)
        self.assertNotIn(gm.feature_name(ROW), off)
        self.assertIn(gm.feature_name(ROW), on)
        self.assertIn("no longer held at 1,000", on)

    def test_the_dll_exports_imports_and_shows_no_text(self):
        try:
            import pefile
        except ImportError:
            self.skipTest("pefile is not installed")
        pe = pefile.PE(str(DLL))
        names = sorted(e.name.decode() for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name)
        self.assertEqual(names, ["VvfpDivineEnergyCapInstalled", "VvfpStartup"])
        imports = {i.name.decode() for e in pe.DIRECTORY_ENTRY_IMPORT for i in e.imports if i.name}
        self.assertEqual(imports & {"LoadLibraryA", "LoadLibraryW", "OutputDebugStringA", "OutputDebugStringW",
                                    "MessageBoxA", "MessageBoxW", "CreateFileA", "DeleteFileW",
                                    "MoveFileW", "RegSetValueExW", "Sleep", "CreateThread"}, set())
        source = (ROOT / "native" / "vvfp_divine_energy_cap" / "vvfp_divine_energy_cap.c").read_text(encoding="utf-8")
        self.assertNotIn("OutputDebugString", source)

    def test_the_stock_sites(self):
        """The stock bytes the companion checks, and the code around them it relies on."""
        if not stock_path(5).is_file():
            self.skipTest("stock executable not present (inputs/)")
        exe = stock_path(5).read_bytes()
        at = lambda va, n: exe[va - 0x400000:va - 0x400000 + n]  # noqa: E731 -- .text is mapped 1:1 in this exe
        for va, stock in SITES.items():
            self.assertEqual(at(va, len(stock)), stock, hex(va))
        # test esi, esi / jge / xor esi, esi (the jmp's target: at least 0); cmp byte [edi+0x17E11], 0 / mov
        # [edi+0x17D60], esi / je 0x4250E2.
        self.assertEqual(at(0x4250C3, 6), bytes.fromhex("85F67D0233F6"))
        self.assertEqual(at(0x4250C9, 15), bytes.fromhex("80BF117E01000089B7607D0100740A"))
        # The bar call's five pushes: cost (eax), current, cap, 0xC, 0x269.
        self.assertEqual(at(0x443201, 0x1D), bytes.fromhex("8B8D607D0100508B85647D010050516A0C6869020000E814D300008BC8"))
        # The bar: cmp ebx (the cap), 1000 / ... / mov [esp+20h], 1000 (the clamp the fill divides by).
        self.assertEqual(at(0x45038C, 6), bytes.fromhex("81FBE8030000"))
        self.assertEqual(at(0x45039E, 8), bytes.fromhex("C7442420E8030000"))
        # The only write of +0x17E11 in the whole executable is the reset's clear (0x424807, mov [esi+17E11h], bl).
        self.assertEqual(exe.count(bytes.fromhex("117E0100")), 2)
        self.assertEqual(at(0x424807, 6), bytes.fromhex("889E117E0100"))

    def test_the_numbers(self):
        self.assertEqual(formula(150), 1150)
        self.assertEqual(formula(256), 1680)
        self.assertEqual(formula(120), 1000)
        self.assertEqual(formula(121), 1005)


@unittest.skipIf(_skip(), _skip() or "")
class Uncapped(unittest.TestCase):
    maxDiff = None

    def island(self, mode="collection_progression", *, big=False, start=True, rows=None) -> Island:
        rows = [ROW] + (["vv5_population_256"] if big else []) if rows is None else rows
        v = Island(render(5, with_requirements(5, rows), mode))
        if start:
            v.export("VvfpStartup", 5, 0)
            self.assertEqual(v.export("VvfpDivineEnergyCapInstalled"), 1)
        return v

    def test_the_cap_goes_past_1000_in_every_mode(self):
        cases = [(mode, False) for mode in MODES] + [("immediate_fixed", True)]
        for mode, big in cases:
            for believers in (0, 10, 119, 120, 121, 150) + ((255, 256) if big else ()):
                with self.subTest(mode=mode, big=big, believers=believers):
                    v = self.island(mode, big=big)
                    v.village(believers, energy=5)
                    self.assertEqual(v.update(), (formula(believers), 5))

    def test_1150_and_1680(self):
        v = self.island()
        v.village(150, energy=1150)
        self.assertEqual(v.update(), (1150, 1150))
        v = self.island("immediate_fixed", big=True)
        v.village(256, energy=2000)
        self.assertEqual(v.update(), (1680, 1680), "the Divine Energy is still kept at most the cap")

    def test_every_bonus_counts_above_1000(self):
        base = dict(statue=0, solved=False, spirituality=1, relics=0)
        for change in ({}, dict(statue=1), dict(statue=2), dict(solved=True), dict(spirituality=2),
                       dict(spirituality=3), dict(relics=1), dict(relics=23), dict(relics=24)):
            with self.subTest(**change):
                v = self.island()
                v.village(200, **{**base, **change})
                self.assertEqual(v.update()[0], formula(200, **{**base, **change}))

    def test_the_cap_falls_with_the_village_and_takes_the_energy_down(self):
        v = self.island()
        v.village(150, energy=1150)
        self.assertEqual(v.update(), (1150, 1150))
        v.believers = 100
        self.assertEqual(v.update(), (formula(100), formula(100)))

    def test_the_forced_path_is_at_least_1000(self):
        """+0x17E11 set (never in the game): the patched store is max(the formula, 1,000)."""
        for believers, cap in ((0, 1000), (50, 1000), (150, 1150), (200, formula(200))):
            with self.subTest(believers=believers):
                v = self.island()
                v.village(believers, forced=True)
                self.assertEqual(v.update()[0], cap)
                self.assertGreaterEqual(cap, 1000)

    def test_the_bar_is_scaled_and_never_past_its_frame(self):
        full = FRAME_PIXELS // 4                                   # 93 slices of 4 px at a 1,000 cap
        for mode in MODES:
            for cap, energy, cost in ((1150, 1150, 0), (1680, 1680, 0), (1680, 840, 0), (1680, 0, 0),
                                      (1150, 575, 800), (1680, 1680, 10), (5000, 4999, 0)):
                with self.subTest(mode=mode, cap=cap, energy=energy, cost=cost):
                    v = self.island(mode)
                    drawn = v.hud(cap, energy, cost)
                    self.assertEqual(len(drawn[FRAME]), full, "the frame: 1,000's, 372 px")
                    scaled = energy * 1000 // cap
                    self.assertEqual(len(drawn[FILL]), (FRAME_PIXELS * scaled // 1000) // 4)
                    self.assertLessEqual(len(drawn[FILL]), full)
                    if drawn[FILL]:
                        self.assertLessEqual(max(drawn[FILL]), max(drawn[FRAME]))
                    if cost:
                        glow = max(1, cost * 1000 // cap)
                        self.assertEqual(len(drawn[GLOW]), (FRAME_PIXELS * glow // 1000) // 4)
                        self.assertLessEqual(len(drawn[GLOW]), full)
        v = self.island()
        self.assertEqual(len(v.hud(1680, 1680)[FILL]), full, "a full village fills the whole frame")

    def test_the_bar_at_1000_or_less_is_the_stock_bar(self):
        for cap, energy, cost in ((10, 0, 0), (100, 50, 0), (400, 400, 25), (1000, 1000, 0), (1000, 640, 300)):
            with self.subTest(cap=cap, energy=energy, cost=cost):
                plain = self.island(start=False)
                v = self.island()
                self.assertEqual(v.hud(cap, energy, cost), plain.hud(cap, energy, cost))

    def test_untouched_when_unticked(self):
        """The row not ticked: the companion is not shipped or started; the stock clamp, forced path and bar."""
        for mode in MODES:
            with self.subTest(mode=mode):
                exe = render(5, with_requirements(5, ["vv5_story_cheat_upgrades"]), mode)
                for va, stock in SITES.items():
                    self.assertEqual(exe[va - 0x400000:va - 0x400000 + len(stock)], stock)
                v = Island(exe)
                v.village(150, energy=1150)
                self.assertEqual(v.update(), (1000, 1000))
                v.village(10, forced=True)
                self.assertEqual(v.update()[0], 1000)
                for va, stock in SITES.items():
                    self.assertEqual(v.read(va, len(stock)), stock)

    def test_the_install_is_refused_on_other_bytes_at_any_site(self):
        for va, stock in SITES.items():
            with self.subTest(site=hex(va)):
                exe = bytearray(render(5, with_requirements(5, [ROW]), "collection_progression"))
                exe[va - 0x400000 + len(stock) - 1] ^= 0x01
                v = Island(bytes(exe))
                v.export("VvfpStartup", 5, 0)
                self.assertEqual(v.export("VvfpDivineEnergyCapInstalled"), 0)
                for other, other_stock in SITES.items():
                    if other != va:
                        self.assertEqual(v.read(other, len(other_stock)), other_stock, "none written")

    def test_another_game_installs_nothing(self):
        v = self.island(start=False)
        for game in (1, 2, 3, 4):
            v.export("VvfpStartup", game, 0)
        self.assertEqual(v.export("VvfpDivineEnergyCapInstalled"), 0)
        for va, stock in SITES.items():
            self.assertEqual(v.read(va, len(stock)), stock)


if __name__ == "__main__":
    unittest.main()
