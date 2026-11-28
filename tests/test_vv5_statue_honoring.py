"""New Believers' "Villagers Dropped on an Unfinished Statue May Honor" (the owner, 2026-11-27: "villagers when
dropped on the statue when it can be improved, should have a chance of practicing devotion (honoring) instead of being
confused (roughly equal) so people can always get triggered to honor no matter what").

EMULATED, on the executable the patcher renders for the row, in each of the three public modes and with 256 Villagers
(Experimental):

* "VVFP Statue Honoring.dll" is started as VVFP More Companions.dll starts it (VvfpStartup(5, ...));
* the statue's area is registered by the game's own code (0x47A9D9: area 0x18, handler 0x479560, highlight 6,
  permission 0) and stamped on a map cell;
* a villager is dropped through the game's own drop dispatcher 0x4794A0 (the map lookup 0x477860, the permission
  test, the statue handler 0x479560, the statue's own tests 0x432350 / 0x43AE80 / 0x4271C0 over the game's statue,
  technology and puzzle memory).  Stood in for: the villager's point 0x466350, the action setter 0x465580 (it
  records the behaviour and its parameter), the tips 0x44E730 / 0x44EF60, and the game's rand 0x403660 (it records
  every draw: the companion must never draw it).
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
    from story_emulator import STACK_TOP
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

ROW = "vv5_unfinished_statue_drops_honor"
NAME = "Villagers Dropped on an Unfinished Statue May Honor"
DLL_NAME = "VVFP Statue Honoring.dll"
DLL = ROOT / "assets" / "statue_honoring" / DLL_NAME
FEATURE = ROOT / "data" / f"{ROW}_feature.json"
MODES = ("stock", "collection_progression", "immediate_fixed")

STRIDE, AGE, PREGNANT, FACTION = 0x2F44, 0x1B8C, 0x1C4C, 0x1CEC
STOCK_RECORDS, BIG_RECORDS = 0x554148 + 0x48, 0x800000 + 0x48
SITE, SITE_STOCK = 0x479726, bytes.fromhex("6A1FC744240C66000000")
HANDLER, DISPATCH, REGISTER, REGISTERED = 0x479560, 0x4794A0, 0x47A9D9, 0x47A9E9
AREAS, GRID, STATUE_AREA = 0x77DC80, 0x718EE8, 0x18
STATUE = 0x51D950                       # the statue object: +8 stage, +0xC the stage's work
TECHS = 0x51D5CC                        # levels by index: 3 Construction, 5 Spirituality
PUZZLES, NEEDED, IDOL = 0x51E008, 0x51DF30, 14
CONFUSED, HONORING, BUILDING, POLISHING = 0x1F, 0xA0, 0x95, 0x9D
POINT = (1000, 1000)


class Island(Machine):
    def __init__(self, exe: bytes, *, big: bool = False):
        super().__init__(exe, DLL)
        self.records = BIG_RECORDS if big else STOCK_RECORDS
        self.actions: list[tuple[int, int, int]] = []
        self.rand_calls: list[int] = []
        self.game = self.alloc(0x18000)
        self.stub(0x425950, lambda p: (p.game, 0))     # the village object the handler asks for first (0x479563)
        self.stub(0x466350, self._point)
        self.stub(0x465580, self._action)
        self.stub(0x44E730, lambda p: (0, 12))
        self.stub(0x44EF60, lambda p: (0, 8))
        self.stub(0x403660, lambda p: (p.rand_calls.append(p.arg(0)) or 0, 0))
        # The game's own registration of the statue's area (push 0 / push 6 / push 0x479560 / push 0x18 / call).
        self.set_reg("esp", STACK_TOP - 0x8000)
        self.run(REGISTER, REGISTERED)
        x, y = POINT
        self.put32(GRID + ((y // 8) * 320 + x // 8) * 4, STATUE_AREA << 15)
        self.image_writes.clear()                       # the game's own registration is not the companion's

    def _point(self, p):
        out = p.arg(0)
        p.put32(out, POINT[0])
        p.put32(out + 4, POINT[1])
        return out, 4

    def _action(self, p):
        self.actions.append((p.reg("ecx"), p.arg(0), p.u32(p.arg(1))))
        return 0, 8

    def villager(self, index: int = 1, *, age: int = 600, heathen: bool = False, expecting: bool = False) -> int:
        record = self.records + index * STRIDE
        self.write(record, bytes(STRIDE))
        self.put32(record + AGE, age)
        self.put32(record + PREGNANT, 30 if expecting else 0)
        self.write(record + FACTION, b"\x01" if heathen else b"\x00")
        return record

    def statue(self, stage: int, *, work: int = 0, construction: int = 1, spirituality: int = 1,
               solved: bool = False) -> None:
        self.put32(STATUE + 8, stage)
        self.put32(STATUE + 0xC, work)
        self.put32(TECHS + 3 * 4, construction)
        self.put32(TECHS + 5 * 4, spirituality)
        self.put32(NEEDED + IDOL * 4, 3)
        self.put32(PUZZLES + IDOL * 8, 3 if solved else 0)

    def drop(self, record: int) -> int:
        return self.call(DISPATCH, [record, 1], ecx=0x77DECC) & 0xFF


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
        self.assertEqual((row["id"], row["name"], row["game_id"], row["dependencies"], row["patches"]),
                         (ROW, NAME, "vv5", [], []))
        for bold in ("**Only while the statue is carved to its first or second stage and its next stage waits for "
                     "technology**", "**Adults only, as in the normal game**",
                     "**Heathens cannot be picked up in the game, so they are never dropped on it.**",
                     "**Needs no other patch; works the same with every other patch and in every population mode.**"):
            self.assertIn(bold, row["description"])
        self.assertEqual([c["destination"] for c in row["companion_files"]], [DLL_NAME])
        self.assertEqual([(d["va"], d["stock_bytes"]) for d in row["runtime_detours"]], [("0x479726", SITE_STOCK.hex().upper())])
        self.assertIn(ROW, {p.id for p in patcher.load_public_fun_patches()})

    def test_on_by_default_everywhere(self):
        """The owner's own request: on by default, in Owner's Defaults and in Select All."""
        from vv_fun_patcher_gui import (default_fun_patch_selection, owners_default_fun_patch_selection,
                                        select_all_fun_patch_selection)
        self.assertEqual((default_fun_patch_selection(ROW), owners_default_fun_patch_selection(ROW),
                          select_all_fun_patch_selection(ROW)), (True, True, True))

    def test_the_third_word_starts_it_and_appends_only(self):
        header = (ROOT / "native" / "shared" / "startup_companions_3.h").read_text(encoding="utf-8")
        names = [line.strip().strip('",') for line in header.split("VVFP_STARTUP_COMPANIONS_3[] = {")[1]
                 .split("};")[0].splitlines() if line.strip().startswith('"')]
        self.assertEqual(names, list(patcher.STARTUP_LOADER_COMPANIONS_3))
        self.assertEqual(names[-1], DLL_NAME)
        self.assertEqual(names.index(DLL_NAME), 23)

    def test_registered_bundled_documented(self):
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        log = (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8")
        guide = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        row = json.loads(FEATURE.read_text(encoding="utf-8"))
        for path in (f"assets/statue_honoring/{DLL_NAME}", f"data/{ROW}_feature.json"):
            self.assertIn(f'"{path}"', release)
        self.assertIn(f"- Patch ID: `{ROW}`", readme)
        self.assertIn(row["description"], readme)
        self.assertIn(f"#### {NAME} (`{ROW}`)", log)
        self.assertEqual(len([e for e in guide["patches"] if ROW in e.get("ids", [])]), 1)

    def test_the_game_mechanics_page_tells_it(self):
        import vv_game_mechanics_faith_vv5 as faith
        import vv_game_mechanics_items_vv5 as items
        self.assertEqual(faith.STATUE_HONORING, ROW)
        self.assertEqual(items.STATUE_HONORING, ROW)
        self.assertIn(ROW, items.PATCHES)
        self.assertNotIn(ROW, items.DEFAULT_OFF)

    def test_the_dll_exports_imports_and_shows_no_text(self):
        try:
            import pefile
        except ImportError:
            self.skipTest("pefile is not installed")
        pe = pefile.PE(str(DLL))
        names = sorted(e.name.decode() for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name)
        self.assertEqual(names, ["VvfpStartup", "VvfpStatueHonoringCount", "VvfpStatueHonoringInstalled"])
        imports = {i.name.decode() for e in pe.DIRECTORY_ENTRY_IMPORT for i in e.imports if i.name}
        self.assertEqual(imports & {"LoadLibraryA", "LoadLibraryW", "OutputDebugStringA", "OutputDebugStringW",
                                    "MessageBoxA", "MessageBoxW", "CreateFileA", "DeleteFileW", "MoveFileW",
                                    "RegSetValueExW", "Sleep", "CreateThread"}, set())
        source = (ROOT / "native" / "vvfp_statue_honoring" / "vvfp_statue_honoring.c").read_text(encoding="utf-8")
        self.assertNotIn("OutputDebugString", source)
        self.assertNotIn("0x403660u", source, "never the game's rand")


@unittest.skipIf(_skip(), _skip() or "")
class Drops(unittest.TestCase):
    maxDiff = None

    def island(self, mode: str = "collection_progression", *, big: bool = False, start: bool = True) -> Island:
        rows = [ROW] + (["vv5_population_256"] if big else [])
        v = Island(render(5, with_requirements(5, rows), mode), big=big)
        if start:
            v.export("VvfpStartup", 5, 0)
            self.assertEqual(v.export("VvfpStatueHonoringInstalled"), 1)
        return v

    def behaviours(self, v: Island, record: int, times: int) -> list[tuple[int, int]]:
        v.actions.clear()
        for _ in range(times):
            self.assertEqual(v.drop(record), 1)
        self.assertTrue(all(who == record for who, _, _ in v.actions))
        return [(behaviour, parameter) for _, behaviour, parameter in v.actions]

    def test_the_site_is_stock_in_every_mode(self):
        stock = stock_path(5).read_bytes()
        self.assertEqual(stock[SITE - 0x400000:SITE - 0x400000 + len(SITE_STOCK)], SITE_STOCK)
        for mode in MODES:
            exe = render(5, with_requirements(5, [ROW]), mode)
            self.assertEqual(exe[SITE - 0x400000:SITE - 0x400000 + len(SITE_STOCK)], SITE_STOCK, mode)

    def test_one_wrong_stock_byte_installs_nothing(self):
        for offset in (0, len(SITE_STOCK) - 1):
            with self.subTest(offset=offset):
                exe = bytearray(render(5, with_requirements(5, [ROW]), "collection_progression"))
                exe[SITE - 0x400000 + offset] ^= 0x01
                v = Island(bytes(exe))
                v.export("VvfpStartup", 5, 0)
                self.assertEqual(v.export("VvfpStatueHonoringInstalled"), 0)
                self.assertEqual(v.image_writes, [], "nothing written")
        v = Island(render(5, with_requirements(5, [ROW]), "collection_progression"))
        v.export("VvfpStartup", 4, 0)
        self.assertEqual(v.export("VvfpStatueHonoringInstalled"), 0, "only New Believers")

    def test_without_the_companion_the_stock_confused(self):
        v = self.island(start=False)
        v.statue(1)
        self.assertEqual(set(self.behaviours(v, v.villager(), 40)), {(CONFUSED, 0x66)})

    def test_a_drop_waiting_for_technology_honors_about_half_the_time(self):
        for mode in MODES:
            for big in (False, True):
                for stage in (1, 2):
                    with self.subTest(mode=mode, big=big, stage=stage):
                        v = self.island(mode, big=big)
                        v.statue(stage)
                        got = self.behaviours(v, v.villager(7), 400)
                        self.assertEqual(set(got), {(CONFUSED, 0x66), (HONORING, 0)},
                                         "the stock Confused with its 0x66, or Honoring with its byte 0")
                        honored = got.count((HONORING, 0))
                        self.assertTrue(150 <= honored <= 250, honored)
                        self.assertEqual((v.export("VvfpStatueHonoringCount", 1),
                                          v.export("VvfpStatueHonoringCount", 0)), (honored, 400 - honored))
                        self.assertEqual(v.rand_calls, [], "never a draw of the game's rand")

    def test_the_other_drop_cases_are_the_stock_ones(self):
        v = self.island()
        adult = v.villager()
        cases =(("the first stage", dict(stage=0), BUILDING),
                 ("a stage under way", dict(stage=1, work=10), BUILDING),
                 ("the second stage with its technology", dict(stage=1, construction=2, spirituality=2), BUILDING),
                 ("the third stage with its technology", dict(stage=2, construction=3, spirituality=3), BUILDING),
                 ("solved", dict(stage=3, solved=True), POLISHING))
        for what, state, expected in cases:
            with self.subTest(what):
                v.statue(**state)
                got = {behaviour for behaviour, _ in self.behaviours(v, adult, 30)}
                self.assertEqual(got, {expected})
        self.assertEqual(v.export("VvfpStatueHonoringCount", 1) + v.export("VvfpStatueHonoringCount", 0), 0)

    def test_who_keeps_the_stock_answer(self):
        v = self.island()
        v.statue(1)
        heathen = v.villager(2, heathen=True)
        self.assertEqual(set(self.behaviours(v, heathen, 60)), {(CONFUSED, 0x66)},
                         "a Heathen record (the game never lets one be picked up) keeps the stock Confused")
        v.statue(0)
        self.assertEqual({b for b, _ in self.behaviours(v, heathen, 5)}, {BUILDING}, "and the other cases")

    def test_children_and_expecting_mothers_are_turned_away_first(self):
        v = self.island()
        v.statue(1)
        for what, record in (("a child", v.villager(3, age=279)), ("expecting", v.villager(4, expecting=True))):
            with self.subTest(what):
                v.actions.clear()
                self.assertEqual(v.drop(record), 0, "the dispatcher's own refusal (permission 0)")
                self.assertEqual(v.actions, [])
        self.assertEqual(v.export("VvfpStatueHonoringCount", 1) + v.export("VvfpStatueHonoringCount", 0), 0)

    def test_the_splice_leaves_registers_flags_and_stack_as_the_stock_push(self):
        """From 0x479726 to the stock call 0x479730: the behaviour where `push 0x1F` puts it, the handler's local
        as the chosen behaviour's dispatch sets it, every register and the flags unchanged."""
        v = self.island()
        v.statue(1)
        record = v.villager()
        seen = set()
        for attempt in range(60):
            esp = STACK_TOP - 0x6000
            local = esp + 0x40
            v.put32(local, 0xA5A5A5A5)
            v.put32(esp, local)                       # push ecx (the local's address), as 0x479721 did
            regs = dict(eax=0x11111111, ebx=0x22222222, ecx=record, edx=0x44444444, esi=0x55555555,
                        edi=0x66666666, ebp=0x77777777, esp=esp)
            for name, value in regs.items():
                v.set_reg(name, value)
            flags = 0x202 | (0x41 if attempt % 2 else 0x880)
            v.set_reg("eflags", flags)
            v.run(SITE, 0x479730)
            self.assertEqual({n: v.reg(n) for n in regs}, dict(regs, esp=esp - 4))
            self.assertEqual(v.reg("eflags") & 0xCD5, flags & 0xCD5)
            behaviour = v.u32(esp - 4)
            self.assertEqual(v.u32(esp), local)
            if behaviour == CONFUSED:
                self.assertEqual(v.u32(local), 0x66)
            else:
                self.assertEqual(behaviour, HONORING)
                self.assertEqual(v.u32(local), 0xA5A5A500, "only the parameter byte, as 0x46CDE8 sets it")
            seen.add(behaviour)
        self.assertEqual(seen, {CONFUSED, HONORING})


if __name__ == "__main__":
    unittest.main()
