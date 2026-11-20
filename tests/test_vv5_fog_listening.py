"""New Believers' "Fog of Doom Lets Every Heathen Listen" and its modifier "No Restrictions on Fog of Doom Conversions"
(the owner, 2026-11-19: "the Fog of Doom can allow villagers to be dropped on red/yellow heathens to convert them like
they can the blue ones"; "for heathens, they work only when the heathen's faith is lower than -10. at -10 or above
only the Earthquake power can convert them"; the drop starts the game's own listening, which raises Faith as for a
blue Heathen; only the cast Fog of Doom God Power counts, never natural weather).

EMULATED, on the executable the patcher renders for the row, in each of the three public modes and with 256 Villagers
(Experimental):

* "VVFP Fog Listening.dll" is started as VVFP More Companions.dll starts it (VvfpStartup(5, ...)), its modifier file
  present or not;
* the game's own drop handler 0x443BF0 runs a believer dropped on a Heathen (the target lookup 0x470450, the spot
  0x466350, the activity clear 0x473440 and the action setter 0x465580 stood in for: the setter records which action
  each villager is given);
* the weather 0x710948 is set as the Fog of Doom God Power sets it (fog on, thickness 4: 0x41FB60) or as natural fog
  does (thickness 1: 0x475EDC), or clear;
* the game's own sermon end, the work event 0x468DA0, runs on the believer afterwards, with the game's own Faith
  routines 0x468020 / 0x467F90 (the Devotion check 0x46B270 and the conversion 0x4668B0 stood in for: the
  conversion records that it ran).
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

ROW = "vv5_fog_of_doom_every_heathen_listens"
FREE = "vv5_fog_of_doom_no_restrictions"
DLL_NAME = "VVFP Fog Listening.dll"
DLL = ROOT / "assets" / "fog_listening" / DLL_NAME
FLAG = "VVFP Fog Listening No Restrictions.txt"
FEATURE = ROOT / "data" / f"{ROW}_feature.json"
FREE_FEATURE = ROOT / "data" / f"{FREE}_feature.json"
MODES = ("stock", "collection_progression", "immediate_fixed")

STRIDE, FACTION, ORANGE, RED, FAITH, WAIT, ROLE = 0x2F44, 0x1CEC, 0x1CED, 0x1CEE, 0x1CF0, 0x1CF4, 0x1CFC
AGE, CARRYING, SKILLS = 0x1B8C, 0x1C4C, 0x1C5C
DEVOTION = 5
STOCK_RECORDS, BIG_RECORDS = 0x554148 + 0x48, 0x800000 + 0x48
DROP, SERMON_END = 0x443BF0, 0x468DA0
SITE, SITE_STOCK = 0x443D4D, bytes.fromhex("389EED1C00000F85D4020000389EEE1C00000F85C8020000")
WEATHER = 0x710948
WAITING, EXPLAINING, LISTENING = 6, 0x27, 0x29
NOW = 50_000
TWO_HOURS = 0x1C20

KINDS = {"blue": (0, 0), "orange": (1, 0), "red": (0, 1)}


class Island(Machine):
    """The rendered game and the companion; the game's drop handler and sermon end, with stand-ins around them."""

    def __init__(self, exe: bytes, *, big: bool = False, free: bool = False):
        super().__init__(exe, DLL, present=(FLAG,) if free else ())
        self.records = BIG_RECORDS if big else STOCK_RECORDS
        self.actions: list[tuple[int, int]] = []
        self.converted: list[int] = []
        self.target = 0
        self.skill_passes = True
        self.scene = self.alloc(0x100)
        self.game = self.alloc(0x18000)
        self.write(self.game + 0x17E39, b"\x01")          # the island is running: Faith converts
        self.stub(0x466350, lambda p: (p.arg(0), 4))     # the spot: a point the caller reads
        self.stub(0x470450, lambda p: (self.target, 16))  # the villager under the drop
        self.stub(0x4706F0, lambda p: (self.target, 12))  # the villager the sermon is to
        self.stub(0x473440, lambda p: (0, 0))
        self.stub(0x465580, self._action)
        self.stub(0x425950, lambda p: (self.game, 0))
        self.stub(0x4036E0, lambda p: (NOW, 0))          # the real clock
        self.stub(0x46B270, lambda p: (1 if self.skill_passes else 0, 8))
        self.stub(0x44E730, lambda p: (0, 12))
        self.stub(0x44EF60, lambda p: (0, 8))
        self.stub(0x474910, lambda p: (0, 4))
        self.stub(0x4733F0, lambda p: (0, 4))
        self.stub(0x4668B0, self._convert)

    def _action(self, p):
        self.actions.append((p.reg("ecx"), p.arg(0)))
        return 0, 8

    def _convert(self, p):
        self.converted.append(p.reg("ecx"))
        p.write(p.reg("ecx") + FACTION, b"\0")
        return 0, 0

    def record(self, index: int) -> int:
        return self.records + index * STRIDE

    def believer(self, index: int, devotion: float = 0.0) -> int:
        record = self.record(index)
        self.write(record, bytes(STRIDE))
        self.put32(record + AGE, 400)
        self.put32(record + FAITH, 60)
        self.write(record + SKILLS + 4 * DEVOTION, struct.pack("<f", devotion))
        return record

    def heathen(self, index: int, kind: str, faith: int, role: int = 0) -> int:
        orange, red = KINDS[kind]
        record = self.record(index)
        self.write(record, bytes(STRIDE))
        self.put32(record + AGE, 400)
        self.write(record + FACTION, b"\x01")
        self.write(record + ORANGE, bytes([orange]))
        self.write(record + RED, bytes([red]))
        self.put32(record + FAITH, faith & 0xFFFFFFFF)
        self.put32(record + ROLE, role)
        return record

    def weather(self, fog: bool, thickness: float) -> None:
        self.write(WEATHER + 0x500C, b"\x01" if fog else b"\0")
        self.write(WEATHER + 0x5010, struct.pack("<f", thickness))

    def drop(self, believer: int, heathen: int) -> int:
        self.target = heathen
        return self.call(DROP, [believer], ecx=self.scene) & 0xFF

    def sermon_end(self, believer: int, heathen: int) -> None:
        self.target = heathen
        self.call(SERMON_END, [], ecx=believer)

    def faith(self, record: int) -> int:
        return struct.unpack("<i", self.read(record + FAITH, 4))[0]


def _skip() -> str | None:
    if not HAVE_EMULATOR:
        return "unicorn/pefile not installed"
    if not stock_path(5).is_file():
        return "stock executable not present (inputs/)"
    if not DLL.is_file():
        return f"{DLL} missing"
    return None


class TheRows(unittest.TestCase):
    def test_the_rows(self):
        row = json.loads(FEATURE.read_text(encoding="utf-8"))
        free = json.loads(FREE_FEATURE.read_text(encoding="utf-8"))
        self.assertEqual((row["id"], row["name"], row["game_id"]),
                         (ROW, "Fog of Doom Lets Every Heathen Listen", "vv5"))
        self.assertEqual(row["dependencies"], [])
        self.assertEqual(row["patches"], [])
        self.assertTrue(row["description"].startswith("**Needs the Fog of Doom God Power**"))
        for bold in ("**Only a Heathen whose Faith is below -10 listens.**",
                     "**From Faith -10 up, only the Earthquake God Power reaches them**",
                     "**Only the Fog of Doom God Power counts: natural fog, a Tempest and every other weather do "
                     "nothing.**"):
            self.assertIn(bold, row["description"])
        self.assertEqual([c["destination"] for c in row["companion_files"]], [DLL_NAME])
        self.assertEqual([d["va"] for d in row["runtime_detours"]], ["0x443D4D"])
        self.assertEqual((free["id"], free["name"], free["dependencies"]),
                         (FREE, "No Restrictions on Fog of Doom Conversions", [ROW]))
        self.assertTrue(free["description"].startswith(
            "**Needs \"Fog of Doom Lets Every Heathen Listen\": ticking this patch ticks it too"))
        self.assertIn("No restrictions on Fog of Doom Conversions: red and yellow heathens can be talked to, and the "
                      "-10 faith limit requiring Earthquakes is removed. Those heathens can now be talked to like any "
                      "other blue heathen and eventually converted, as long as Fog of Doom is active.",
                      free["description"])
        self.assertEqual([c["destination"] for c in free["companion_files"]], [FLAG])
        ids = {p.id for p in patcher.load_public_fun_patches()}
        self.assertTrue({ROW, FREE} <= ids)
        self.assertIn(DLL_NAME, patcher.STARTUP_LOADER_COMPANIONS_3)

    def test_defaults(self):
        from vv_fun_patcher_gui import (default_fun_patch_selection, owners_default_fun_patch_selection,
                                        select_all_fun_patch_selection)
        self.assertEqual((default_fun_patch_selection(ROW), owners_default_fun_patch_selection(ROW),
                          select_all_fun_patch_selection(ROW)), (False, True, False))
        self.assertEqual((default_fun_patch_selection(FREE), owners_default_fun_patch_selection(FREE),
                          select_all_fun_patch_selection(FREE)), (False, False, False))

    def test_registered_bundled_documented(self):
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        log = (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8")
        guide = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        for path in (f"assets/fog_listening/{DLL_NAME}", f"assets/fog_listening/{FLAG}",
                     f"data/{ROW}_feature.json", f"data/{FREE}_feature.json"):
            self.assertIn(f'"{path}"', release)
        for row_id, feature in ((ROW, FEATURE), (FREE, FREE_FEATURE)):
            row = json.loads(feature.read_text(encoding="utf-8"))
            self.assertIn(f"- Patch ID: `{row_id}`", readme)
            self.assertIn(row["description"], readme)
            self.assertIn(f"#### {row['name']} (`{row_id}`)", log)
            entry = [e for e in guide["patches"] if row_id in e.get("ids", [])]
            self.assertEqual(len(entry), 1)

    def test_the_dll_exports_imports_and_shows_no_text(self):
        try:
            import pefile
        except ImportError:
            self.skipTest("pefile is not installed")
        pe = pefile.PE(str(DLL))
        names = sorted(e.name.decode() for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name)
        self.assertEqual(names, ["VvfpFogListeningCount", "VvfpFogListeningInstalled",
                                 "VvfpFogListeningNoRestrictions", "VvfpStartup"])
        imports = {i.name.decode() for e in pe.DIRECTORY_ENTRY_IMPORT for i in e.imports if i.name}
        self.assertEqual(imports & {"LoadLibraryA", "LoadLibraryW", "OutputDebugStringA", "OutputDebugStringW",
                                    "MessageBoxA", "MessageBoxW", "CreateFileA", "DeleteFileW", "MoveFileW",
                                    "RegSetValueExW", "Sleep", "CreateThread"}, set())
        source_calls = (ROOT / "native" / "vvfp_fog_listening" / "vvfp_fog_listening.c").read_text(encoding="utf-8")
        for call in ("CreateFile", "WriteFile", "DeleteFile"):
            self.assertNotIn(call, source_calls, "it writes no file (the static C library's imports aside)")
        source = (ROOT / "native" / "vvfp_fog_listening" / "vvfp_fog_listening.c").read_text(encoding="utf-8")
        self.assertNotIn("OutputDebugString", source)


@unittest.skipIf(_skip(), _skip() or "")
class Listening(unittest.TestCase):
    maxDiff = None

    def island(self, mode="collection_progression", *, big=False, free=False, start=True) -> Island:
        rows = [ROW] + ([FREE] if free else []) + (["vv5_population_256"] if big else [])
        v = Island(render(5, with_requirements(5, rows), mode), big=big, free=free)
        if start:
            v.export("VvfpStartup", 5, 0)
            self.assertEqual(v.export("VvfpFogListeningInstalled"), 1)
            self.assertEqual(v.export("VvfpFogListeningNoRestrictions"), int(free))
        return v

    def listens(self, v: Island, believer: int, heathen: int) -> None:
        self.assertEqual(v.drop(believer, heathen), 1)
        self.assertEqual(v.actions, [(heathen, WAITING), (believer, EXPLAINING)],
                         "the stock pair: the Heathen waits, the believer is Explaining the truth")

    def refused(self, v: Island, believer: int, heathen: int) -> None:
        self.assertEqual(v.drop(believer, heathen), 1, "the drop is handled, as in the stock game")
        self.assertEqual(v.actions, [], "nothing happens, as for a masked Heathen in the stock game")

    def test_the_fog_of_doom_lets_masked_heathens_below_minus_ten_listen_in_every_mode(self):
        for mode in MODES:
            for kind in ("orange", "red"):
                with self.subTest(mode=mode, kind=kind):
                    v = self.island(mode)
                    v.weather(True, 4.0)
                    believer, heathen = v.believer(1), v.heathen(2, kind, -11)
                    self.listens(v, believer, heathen)
                    v.sermon_end(believer, heathen)
                    self.assertEqual(v.actions[-1], (heathen, LISTENING), "the Heathen is Listening")
                    self.assertEqual(v.faith(heathen), -8, "Faith +3, the stock sermon's amount")
                    self.assertEqual(v.u32(heathen + WAIT), NOW + TWO_HOURS, "the stock 2-hour wait")
                    self.assertEqual(v.converted, [])
                    self.assertEqual(v.export("VvfpFogListeningCount"), 1)

    def test_the_stock_devotion_amounts(self):
        for devotion, gain in ((0.0, 3), (50.0, 4), (90.0, 5)):
            with self.subTest(devotion=devotion):
                v = self.island()
                v.weather(True, 4.0)
                believer, heathen = v.believer(1, devotion), v.heathen(2, "red", -40)
                self.listens(v, believer, heathen)
                v.sermon_end(believer, heathen)
                self.assertEqual(v.faith(heathen), -40 + gain)

    def test_a_failed_devotion_check_gives_nothing(self):
        v = self.island()
        v.weather(True, 4.0)
        v.skill_passes = False
        believer, heathen = v.believer(1), v.heathen(2, "orange", -30)
        self.listens(v, believer, heathen)
        v.sermon_end(believer, heathen)
        self.assertEqual(v.faith(heathen), -30)
        self.assertNotIn((heathen, LISTENING), v.actions)

    def test_minus_ten_and_above_do_not_listen(self):
        for faith in (-10, -5, 0):
            for kind in ("orange", "red"):
                with self.subTest(faith=faith, kind=kind):
                    v = self.island()
                    v.weather(True, 4.0)
                    self.refused(v, v.believer(1), v.heathen(2, kind, faith))
                    self.assertEqual(v.export("VvfpFogListeningCount"), 0)

    def test_natural_fog_and_clear_weather_do_nothing(self):
        for fog, thickness in ((True, 1.0), (False, 4.0), (False, 0.0)):
            with self.subTest(fog=fog, thickness=thickness):
                v = self.island()
                v.weather(fog, thickness)
                self.refused(v, v.believer(1), v.heathen(2, "red", -50))

    def test_blue_heathens_are_unchanged(self):
        for fog, faith in ((False, -50), (True, -50), (False, -5), (True, 0)):
            with self.subTest(fog=fog, faith=faith):
                v = self.island()
                v.weather(fog, 4.0 if fog else 0.0)
                self.listens(v, v.believer(1), v.heathen(2, "blue", faith))
                self.assertEqual(v.export("VvfpFogListeningCount"), 0, "the companion is not asked")

    def test_without_the_companion_masked_heathens_never_listen(self):
        v = self.island(start=False)
        v.weather(True, 4.0)
        self.refused(v, v.believer(1), v.heathen(2, "red", -50))

    def test_no_restrictions_lifts_the_faith_limit_but_not_the_fog(self):
        for faith in (0, 5, -5, -10):
            with self.subTest(faith=faith):
                v = self.island(free=True)
                v.weather(True, 4.0)
                believer, heathen = v.believer(1), v.heathen(2, "orange", faith)
                self.listens(v, believer, heathen)
                v.sermon_end(believer, heathen)
                # The setter 0x467F90 converts a Heathen whose Faith rises from 0 or less to above 0 (a convert
                # below 5 set to 55); one already above 0 (not a state the game leaves a Heathen in) just rises.
                rises_past_zero = faith <= 0 < faith + 3
                self.assertEqual(v.faith(heathen), 55 if rises_past_zero else faith + 3)
                self.assertEqual(v.converted, [heathen] if rises_past_zero else [],
                                 "the game's own conversion when Faith rises above 0")
        for fog, thickness in ((True, 1.0), (False, 0.0)):
            with self.subTest(fog=fog, thickness=thickness, free=True):
                v = self.island(free=True)
                v.weather(fog, thickness)
                self.refused(v, v.believer(1), v.heathen(2, "red", 0))

    def test_without_no_restrictions_faith_zero_and_up_never_listens(self):
        for faith in (0, 5, -5):
            with self.subTest(faith=faith):
                v = self.island()
                v.weather(True, 4.0)
                self.refused(v, v.believer(1), v.heathen(2, "orange", faith))

    def test_with_256_villagers(self):
        for index in (0, 149, 150, 255):
            with self.subTest(record=index):
                v = self.island(big=True)
                v.weather(True, 4.0)
                believer, heathen = v.believer(index ^ 1), v.heathen(index, "red", -20)
                self.listens(v, believer, heathen)

    def test_the_install_is_refused_on_other_bytes(self):
        exe = bytearray(render(5, with_requirements(5, [ROW]), "collection_progression"))
        exe[SITE - 0x400000 + 7] ^= 0x01
        v = Island(bytes(exe))
        v.export("VvfpStartup", 5, 0)
        self.assertEqual(v.export("VvfpFogListeningInstalled"), 0)

    def test_another_game_installs_nothing(self):
        v = self.island(start=False)
        for game in (1, 2, 3, 4):
            v.export("VvfpStartup", game, 0)
        self.assertEqual(v.export("VvfpFogListeningInstalled"), 0)
        self.assertEqual(v.read(SITE, len(SITE_STOCK)), SITE_STOCK)


class TheEarthquake(unittest.TestCase):
    """The Earthquake God Power is stock and unchanged: its loop (0x41F746..0x41F7CC) raises every living villager's
    Faith by rand(7) + 2 through 0x468020, skipping only the roles 12-17; it reads no mask."""

    def test_the_earthquake_reads_no_mask(self):
        if not stock_path(5).is_file():
            self.skipTest("stock executable not present (inputs/)")
        code = stock_path(5).read_bytes()[0x1F744:0x1F7D2]
        self.assertNotIn(b"\xED\x1C\x00\x00", code, "no orange-mask read")
        self.assertNotIn(b"\xEE\x1C\x00\x00", code, "no red-mask read")
        self.assertIn(bytes.fromhex("6A07E8"), code, "rand(7)")
        self.assertIn(bytes.fromhex("E87C880400"), code, "the Faith add 0x468020 at 0x41F79F")


if __name__ == "__main__":
    unittest.main()
