"""New Believers' "Practicing Devotion Builds Faith and Divine Energy" (the owner, 2026-11-21: "practicing Devotion
skill should give a 1-point increase in Faith. like a small chance which adds up over time."; "people practicing
devotion should also give 1 point in Divine Energy too. same mechanics"; "1 in 10 for both is good").

EMULATED, on the executable the patcher renders for the row, in each of the three public modes and with 256 Villagers
(Experimental):

* "VVFP Devotion Faith.dll" is started as VVFP More Companions.dll starts it (VvfpStartup(5, ...));
* the game's own skill check 0x46B270 runs, whole, on a villager (and through the step runner 0x473B30's step 10, the
  one live play and the catch-up's instant runner 0x46E020 both use), with the game's own Divine Energy adder
  0x424F80 and the ftol 0x47C9B0; stood in for: rand(n) 0x403660 (a queue of chosen values, recorded), the village
  manager (its word 0x4DACE0; the getter 0x425950 fails the test if called), the likes test 0x464F90 (likes nothing), the tech level 0x423600 (level 1), the skill add
  0x475730 (recorded), and the say / queue / action calls 0x4653D0, 0x44EF60, 0x469D90, 0x473440, 0x465580, and the
  adder's display refresh 0x450530 / 0x4500D0.
"""
from __future__ import annotations

import json
import struct
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

ROW = "vv5_devotion_builds_faith"
NAME = "Practicing Devotion Builds Faith and Divine Energy"
DLL_NAME = "VVFP Devotion Faith.dll"
DLL = ROOT / "assets" / "devotion_faith" / DLL_NAME
FEATURE = ROOT / "data" / f"{ROW}_feature.json"
MODES = ("stock", "collection_progression", "immediate_fixed")

STRIDE, RECORD, FACTION, FAITH, ROLE, SKILLS = 0x2F44, 0x1B88, 0x1CEC, 0x1CF0, 0x1CFC, 0x1C5C
DEVOTION = 5
STOCK_RECORDS, BIG_RECORDS = 0x554148 + 0x48, 0x800000 + 0x48
CHECK, STEPS = 0x46B270, 0x473B30
SITE_STOCK = bytes.fromhex("83EC0C5355")
ENERGY, ENERGY_CAP = 0x17D64, 0x17D60
MANAGER_WORD = 0x4DACE0
DRAWS = 32768


class Island(Machine):
    """The rendered game and the companion; the game's skill check with stand-ins around it."""

    def __init__(self, exe: bytes, *, big: bool = False):
        super().__init__(exe, DLL)
        self.records = BIG_RECORDS if big else STOCK_RECORDS
        self.queue: list[int] = []
        self.rolls: list[int] = []                         # the n of every rand(n) asked, in order
        self.skill_adds: list[tuple[int, float]] = []
        self.manager = self.alloc(0x18000)
        self.put32(self.manager + ENERGY_CAP, 200)
        self.put32(MANAGER_WORD, self.manager)            # the word the getter 0x425950 keeps the manager in
        self.stub(0x403660, self._rand)
        self.stub(0x425950, self._getter)
        self.stub(0x450530, lambda p: (self.manager, 0))
        self.stub(0x4500D0, lambda p: (0, 0))
        self.stub(0x464F90, lambda p: (0, 4))              # likes / dislikes learning: neither
        self.stub(0x423600, lambda p: (1, 4))              # Learning level 1, Spirituality level 1
        self.stub(0x475730, self._skill_add)
        self.stub(0x4653D0, lambda p: (0, 0))
        self.stub(0x44EF60, lambda p: (0, 8))
        self.stub(0x469D90, lambda p: (0, 4))
        self.stub(0x473440, lambda p: (0, 0))
        self.stub(0x465580, lambda p: (0, 8))

    def _getter(self, p):
        raise AssertionError("the getter 0x425950 is never called (it can build the game object)")

    def _rand(self, p):
        n = p.arg(0)
        self.rolls.append(n)
        value = self.queue.pop(0) if self.queue else n - 1
        assert 0 <= value < n, (value, n)
        return value, 0

    def _skill_add(self, p):
        self.skill_adds.append((p.arg(0), struct.unpack("<f", struct.pack("<I", p.arg(1)))[0]))
        return 0, 8

    def villager(self, index: int, *, faith: int = 50, devotion: float = 40.0, heathen: bool = False,
                 role: int = 0) -> tuple[int, int]:
        record = self.records + index * STRIDE
        self.write(record, bytes(STRIDE))
        self.write(record + FACTION, b"\x01" if heathen else b"\0")
        self.put32(record + FAITH, faith)
        self.put32(record + ROLE, role)
        for skill in range(6):
            self.write(record + SKILLS + 4 * skill, struct.pack("<f", devotion))
        villager = self.alloc(0x2000)
        self.put32(villager + RECORD, record)
        return villager, record

    def energy(self, value: int | None = None, cap: int | None = None) -> int:
        if cap is not None:
            self.put32(self.manager + ENERGY_CAP, cap)
        if value is not None:
            self.put32(self.manager + ENERGY, value)
        return self.u32(self.manager + ENERGY)

    def faith(self, record: int) -> int:
        return struct.unpack("<i", self.read(record + FAITH, 4))[0]

    def check(self, villager: int, skill: int = DEVOTION) -> int:
        return self.call(CHECK, [skill, 0], ecx=villager) & 0xFF

    def step(self, villager: int, skill: int = DEVOTION) -> None:
        """Step 10 through the step runner 0x473B30 (live play, and the catch-up's runner 0x46E020)."""
        item = self.alloc(0x1C00)
        self.put32(item, 10)
        self.put32(item + 4, skill)
        self.put32(item + 0x1B80, villager)
        self.call(STEPS, [], ecx=item)


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
        self.assertIn("there is a 1 in 10 chance their Faith rises by 1, and a separate 1 in 10 chance the village "
                      "gains 1 Divine Energy", row["description"])
        for bold in ("**Faith never goes above 100 and Divine Energy never above the village's cap**",
                     "**Believers only:**",
                     "**Works the same with every other patch and in every population mode.**"):
            self.assertIn(bold, row["description"])
        self.assertEqual([c["destination"] for c in row["companion_files"]], [DLL_NAME])
        self.assertEqual([(d["va"], d["stock_bytes"]) for d in row["runtime_detours"]], [("0x46B270", "83EC0C5355")])
        self.assertIn(ROW, {p.id for p in patcher.load_public_fun_patches()})
        self.assertEqual(patcher.STARTUP_LOADER_COMPANIONS_3.index(DLL_NAME), 13, "third word, bit 13")
        header = (ROOT / "native" / "shared" / "startup_companions_3.h").read_text(encoding="utf-8")
        self.assertIn(f'"{DLL_NAME}"', header)

    def test_defaults(self):
        """The owner's defaults for it (2026-11-21): off in the normal defaults, on in Owner's Defaults, and a normal
        row for Select All."""
        from vv_fun_patcher_gui import (default_fun_patch_selection, owners_default_fun_patch_selection,
                                        select_all_fun_patch_selection)
        self.assertEqual((default_fun_patch_selection(ROW), owners_default_fun_patch_selection(ROW),
                          select_all_fun_patch_selection(ROW)), (False, True, True))

    def test_registered_bundled_documented(self):
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        log = (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8")
        guide = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        how = (ROOT / "How to Use.txt").read_text(encoding="utf-8")
        row = json.loads(FEATURE.read_text(encoding="utf-8"))
        for path in (f"assets/devotion_faith/{DLL_NAME}", f"data/{ROW}_feature.json"):
            self.assertIn(f'"{path}"', release)
        self.assertIn(f"- Patch ID: `{ROW}`", readme)
        self.assertIn(row["description"], readme)
        whats_new = readme.split("## What's new in v1.35.97")[1].split("\n## ")[0]
        self.assertIn(f"- **{NAME}** (New Believers, new;", whats_new)
        self.assertIn("1 in 10 chance their Faith rises by 1", whats_new)
        self.assertIn(f"#### {NAME} (`{ROW}`)", log)
        self.assertEqual(len([e for e in guide["patches"] if ROW in e.get("ids", [])]), 1)
        self.assertIn(NAME.upper() + " (NEW BELIEVERS)", how)

    def test_the_game_mechanics_line(self):
        import vv_game_mechanics as gm
        import vv_game_mechanics_faith_vv5 as faith

        class Village:
            general = True

            def __init__(self, has):
                self._has = has

            def has(self, feature):
                return self._has if feature == faith.DEVOTION_FAITH else False

        on = [f.text for f in faith.lines(Village(True))]
        off = [f.text for f in faith.lines(Village(False))]
        mine = [t for t in on if gm.feature_name(ROW) in t]
        self.assertEqual(len(mine), 1)
        self.assertIn("1 in 10 chance (10.00%) of Faith +1, never above 100", mine[0])
        self.assertIn("Divine Energy +1", mine[0])
        self.assertEqual([t for t in off if gm.feature_name(ROW) in t], [])
        self.assertTrue(any(t.startswith("Practising Devotion is the game's Devotion skill check.") for t in off))

    def test_the_dll_exports_imports_and_shows_no_text(self):
        try:
            import pefile
        except ImportError:
            self.skipTest("pefile is not installed")
        pe = pefile.PE(str(DLL))
        names = sorted(e.name.decode() for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name)
        self.assertEqual(names, ["VvfpDevotionEnergyGiven", "VvfpDevotionFaithGiven", "VvfpDevotionFaithInstalled",
                                 "VvfpDevotionFaithSteps", "VvfpStartup"])
        imports = {i.name.decode() for e in pe.DIRECTORY_ENTRY_IMPORT for i in e.imports if i.name}
        self.assertEqual(imports & {"LoadLibraryA", "LoadLibraryW", "OutputDebugStringA", "OutputDebugStringW",
                                    "MessageBoxA", "MessageBoxW", "CreateFileA", "DeleteFileW", "MoveFileW", "RegSetValueExW", "Sleep", "CreateThread"}, set())
        source = (ROOT / "native" / "vvfp_devotion_faith" / "vvfp_devotion_faith.c").read_text(encoding="utf-8")
        self.assertNotIn("OutputDebugString", source)

    def test_the_stock_odds_one_in_ten(self):
        """rand(10) < 1 with the game's rand() % 10: 3,277 of the C library's 32,768 values, 10.00%."""
        self.assertEqual(sum(1 for v in range(DRAWS) if v % 10 < 1), 3277)

    def test_who_practises_devotion_in_the_stock_game(self):
        """The stock code the row hangs on: Honoring queues the Devotion check (push 5 / call 0x474780 at 0x45CC97) on
        rand(100) < 25 (0x45CC88..0x45CC95), and the sermon end checks the preacher (push 5 / call 0x46B270 at
        0x468E98); the step runner's step 10 calls the check with the step's skill (0x473C69)."""
        if not stock_path(5).is_file():
            self.skipTest("stock executable not present (inputs/)")
        exe = stock_path(5).read_bytes()
        at = lambda va, n: exe[va - 0x400000:va - 0x400000 + n]  # noqa: E731 -- .text is mapped 1:1 in this exe
        # push 100 / call rand / add esp, 4 / cmp eax, 25 / jge +9 / push 5 / mov ecx, esi / call 0x474780
        self.assertEqual(at(0x45CC88, 0x18), bytes.fromhex("6A64E8D169FAFF83C40483F8197D096A058BCEE8E07A0100"))
        self.assertEqual(at(0x468E98, 7), bytes.fromhex("6A05E8D1230000"))          # push 5 / call 0x46B270
        self.assertEqual(at(0x473C60, 14), bytes.fromhex("5250C7435401000000E80276FFFF"))  # step 10: call 0x46B270
        self.assertEqual(at(CHECK, 5), SITE_STOCK)


@unittest.skipIf(_skip(), _skip() or "")
class Practising(unittest.TestCase):
    maxDiff = None

    def island(self, mode="collection_progression", *, big=False, start=True) -> Island:
        rows = [ROW] + (["vv5_population_256"] if big else [])
        v = Island(render(5, with_requirements(5, rows), mode), big=big)
        if start:
            v.export("VvfpStartup", 5, 0)
            self.assertEqual(v.export("VvfpDevotionFaithInstalled"), 1)
        return v

    def test_one_in_ten_faith_and_separately_one_in_ten_energy_in_every_mode(self):
        for mode in MODES:
            for faith_roll in range(10):
                for energy_roll in (0, 1, 9):
                    with self.subTest(mode=mode, faith_roll=faith_roll, energy_roll=energy_roll):
                        v = self.island(mode)
                        villager, record = v.villager(1, faith=50)
                        v.energy(100, cap=200)
                        v.queue = [faith_roll, energy_roll]
                        v.check(villager)
                        self.assertEqual(v.rolls[:2], [10, 10], "two separate rand(10) rolls first")
                        self.assertEqual(v.faith(record), 51 if faith_roll == 0 else 50)
                        self.assertEqual(v.energy(), 101 if energy_roll == 0 else 100)
                        self.assertEqual(v.export("VvfpDevotionFaithSteps"), 1)

    def test_with_256_villagers(self):
        for index in (0, 149, 150, 255):
            with self.subTest(record=index):
                v = self.island("immediate_fixed", big=True)
                villager, record = v.villager(index, faith=70)
                v.energy(10, cap=200)
                v.queue = [0, 0]
                v.check(villager)
                self.assertEqual((v.faith(record), v.energy()), (71, 11))

    def test_through_the_step_runner_live_and_catch_up(self):
        v = self.island()
        villager, record = v.villager(1, faith=20)
        v.energy(0, cap=200)
        v.queue = [0, 0]
        v.step(villager)
        self.assertEqual((v.faith(record), v.energy()), (21, 1))

    def test_faith_never_above_100(self):
        for faith, after in ((99, 100), (100, 100)):
            with self.subTest(faith=faith):
                v = self.island()
                villager, record = v.villager(1, faith=faith)
                v.queue = [0, 9]
                v.check(villager)
                self.assertEqual(v.faith(record), after)
                self.assertEqual(v.export("VvfpDevotionFaithGiven"), after - faith)

    def test_divine_energy_never_above_the_cap(self):
        for energy, cap, after in ((199, 200, 200), (200, 200, 200), (1000, 1000, 1000)):
            with self.subTest(energy=energy, cap=cap):
                v = self.island()
                villager, _ = v.villager(1)
                v.energy(energy, cap=cap)
                v.queue = [9, 0]
                v.check(villager)
                self.assertEqual(v.energy(), after, "the game's own adder keeps it at most the cap")

    def test_the_stock_check_runs_unchanged_after_the_rolls(self):
        """The same stock rolls give the same skill adds and the same answer with or without the companion."""
        for stock_rolls in ([10], [90]):     # rand(100) <= Devotion 40 + 33 passes; above it fails
            with self.subTest(stock_rolls=stock_rolls):
                plain = self.island(start=False)
                pv, _ = plain.villager(1)
                plain.queue = list(stock_rolls)
                answer = plain.check(pv)
                v = self.island()
                villager, _ = v.villager(1)
                v.queue = [9, 9] + list(stock_rolls)
                self.assertEqual(v.check(villager), answer)
                self.assertEqual(v.skill_adds, plain.skill_adds)
                self.assertEqual(v.rolls[2:], plain.rolls)

    def test_other_skills_heathens_and_puzzle_roles_get_nothing(self):
        cases = [dict(skill=s) for s in range(5)]
        cases += [dict(heathen=True)] + [dict(role=r) for r in range(12, 18)]
        for case in cases:
            with self.subTest(**case):
                v = self.island()
                skill = case.get("skill", DEVOTION)
                villager, record = v.villager(1, faith=-40 if case.get("heathen") else 50,
                                              heathen=case.get("heathen", False), role=case.get("role", 0))
                v.energy(5, cap=200)
                v.queue = [0, 0, 0, 0]
                v.check(villager, skill)
                self.assertNotIn(10, v.rolls, "no roll of the companion's is made")
                self.assertEqual(v.faith(record), -40 if case.get("heathen") else 50)
                self.assertEqual(v.energy(), 5)
                self.assertEqual(v.export("VvfpDevotionFaithSteps"), 0)

    def test_untouched_when_unticked(self):
        """The row not ticked: the companion is not shipped or started, so the check is the stock one."""
        for mode in MODES:
            with self.subTest(mode=mode):
                exe = render(5, with_requirements(5, ["vv5_story_cheat_upgrades"]), mode)
                self.assertEqual(exe[CHECK - 0x400000:CHECK - 0x400000 + 5], SITE_STOCK)
                v = Island(exe)
                villager, record = v.villager(1, faith=50)
                v.energy(100, cap=200)
                v.queue = [0, 0, 0]
                v.check(villager)
                self.assertNotIn(10, v.rolls)
                self.assertEqual((v.faith(record), v.energy()), (50, 100))
                self.assertEqual(v.read(CHECK, 5), SITE_STOCK)

    def test_the_install_is_refused_on_other_bytes(self):
        exe = bytearray(render(5, with_requirements(5, [ROW]), "collection_progression"))
        exe[CHECK - 0x400000 + 3] ^= 0x01
        v = Island(bytes(exe))
        v.export("VvfpStartup", 5, 0)
        self.assertEqual(v.export("VvfpDevotionFaithInstalled"), 0)

    def test_another_game_installs_nothing(self):
        v = self.island(start=False)
        for game in (1, 2, 3, 4):
            v.export("VvfpStartup", game, 0)
        self.assertEqual(v.export("VvfpDevotionFaithInstalled"), 0)
        self.assertEqual(v.read(CHECK, 5), SITE_STOCK)


if __name__ == "__main__":
    unittest.main()
