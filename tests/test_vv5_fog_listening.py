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
NAME = 0x1B9C
POPUP = "popup"                                   # what the Story companion's popup is recorded as
SAVE_MANAGER, SAVE_SLOT_FIELD = 0x4DACE0, 0x17D80  # native/shared/game_save_slot.h
STRINGS = 0x5240A8
WONT = "The fog hides you, but {} still won't listen. Something stronger may stir them."
WARY = "The fog hides you, but {} is still wary. Perhaps another approach may convince them."


class Island(Machine):
    """The rendered game and the companion; the game's drop handler and sermon end, with stand-ins around them."""

    def __init__(self, exe: bytes, *, big: bool = False, free: bool = False, files: dict | None = None,
                 slot: int = 1, isola: bool = False):
        super().__init__(exe, DLL, present=(FLAG,) if free else ())
        self.free = free
        self.files = {} if files is None else files     # the disk, by lower-cased path (shared across "restarts")
        self.said: list[str] = []
        self._handles: dict[int, str] = {}
        manager = self.alloc(0x18000)
        self.put32(SAVE_MANAGER, manager)
        self.put32(manager + SAVE_SLOT_FIELD, slot)
        if isola:
            text = self.alloc(0x40)
            self.write(text, b"A villager has left the tribe!\0")
            entry = self.alloc(0x20)
            self.put32(entry, 0x48)
            self.put32(entry + 8, text)
            self.put32(STRINGS + 4 * 0x48, entry)
        self.story_can_show = True                       # the Story companion's popup slot is free
        for name, fn in (("SHGetSpecialFolderPathW", self._docs), ("GetFileAttributesW", self._attributes),
                         ("CreateFileW", self._create), ("WriteFile", self._write_file),
                         ("CloseHandle", lambda p: (1, 4)), ("CreateDirectoryW", lambda p: (1, 8)),
                         ("wsprintfW", self._wsprintf_w)):
            self.api_handlers[name] = fn
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

    # ---- the Story companion's popup and the disk -------------------------------------------------------------
    def story_frame(self) -> None:
        """One frame of "VVFP Story Upgrades.dll"'s fog_notice_tick (story_fog_notice.inc): ask for the words; when
        the popup can be armed now, record it as shown and tell the companion it was taken."""
        buffer = self.alloc(0x1000)
        if self.export("VvfpFogNoticePending", 5, buffer, 0x1000) and self.story_can_show:
            self.said.append((POPUP, self.cstring(buffer)))
            self.export("VvfpFogNoticeTaken", 5)

    def _wsprintf_w(self, p):
        """wsprintfW (cdecl): the %d / %s / %ls / %hs the companion's names use."""
        fmt, out, arg, i = p.wstring(p.arg(1)), [], 2, 0
        while i < len(fmt):
            if fmt[i] == "%":
                spec = fmt[i + 1:i + 3]
                if spec.startswith("d"):
                    out.append(str(struct.unpack("<i", struct.pack("<I", p.arg(arg)))[0]))
                    i += 2
                elif spec.startswith("hs"):
                    out.append(p.cstring(p.arg(arg)))
                    i += 3
                elif spec.startswith("ls"):
                    out.append(p.wstring(p.arg(arg)))
                    i += 3
                elif spec.startswith("s"):
                    out.append(p.wstring(p.arg(arg)))
                    i += 2
                else:
                    raise AssertionError(f"wsprintfW format {fmt!r}")
                arg += 1
                continue
            out.append(fmt[i])
            i += 1
        text = "".join(out)
        p.write(p.arg(0), text.encode("utf-16-le") + b"\0\0")
        return len(text), 0

    def _docs(self, p):
        p.write(p.arg(1), "C:\\Docs".encode("utf-16-le") + b"\0\0")
        return 1, 16

    def _attributes(self, p):
        path = p.wstring(p.arg(0))
        if path.lower() in self.files or (self.free and path.endswith(FLAG)):
            return 0x20, 4
        return 0xFFFFFFFF, 4

    def _create(self, p):
        path, disposition = p.wstring(p.arg(0)).lower(), p.arg(4)
        if disposition != 1 or path in self.files:          # only CREATE_NEW of a file that is not there
            return 0xFFFFFFFF, 28
        self.files[path] = b""
        handle = 0x7000 + len(self._handles)
        self._handles[handle] = path
        return handle, 28

    def _write_file(self, p):
        handle, data, size, wrote = p.arg(0), p.arg(1), p.arg(2), p.arg(3)
        path = self._handles[handle]
        self.files[path] += p.read(data, size)
        if wrote:
            p.put32(wrote, size)
        return 1, 20

    def notices(self) -> list[str]:
        return [path for path in self.files if path.endswith(".dat") and "fog of doom notice" in path]

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

    def heathen(self, index: int, kind: str, faith: int, role: int = 0, name: bytes = b"Kaimana Nalu") -> int:
        orange, red = KINDS[kind]
        record = self.record(index)
        self.write(record, bytes(STRIDE))
        self.write(record + NAME, name + b"\0")
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
        handled = self.call(DROP, [believer], ecx=self.scene) & 0xFF
        self.story_frame()                               # the next frame
        return handled

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

    def test_the_story_companion_shows_it_like_the_faith_popup(self):
        story = (ROOT / "native" / "vvfp_story_upgrades" / "story_fog_notice.inc").read_text(encoding="utf-8")
        main = (ROOT / "native" / "vvfp_story_upgrades" / "vvfp_story_upgrades.c").read_text(encoding="utf-8")
        exports = (ROOT / "native" / "vvfp_fog_listening" / "vvfp_fog_listening.def").read_text(encoding="utf-8")
        for name in ("VvfpFogNoticePending", "VvfpFogNoticeTaken", "VvfpFogNoticeVillageReset"):
            self.assertIn(f'"{name}"', story)
            self.assertIn(name, exports)
        self.assertIn('GetModuleHandleA("VVFP Fog Listening.dll")', story)
        self.assertIn("story_notice_arm(game, &fog_notice_event)", story, "the Faith popup's own arm and waits")
        self.assertIn("time_skip_event_open()", story)
        tick = story.split("static void fog_notice_tick")[1].split("static void fog_notice_village_reset")[0]
        self.assertNotIn("lstrcpynA(fog_notice_event.title", tick, "the owner: no title (left empty)")
        self.assertIn("memset(&fog_notice_event, 0, sizeof fog_notice_event);", tick)
        self.assertNotIn("FOG_NOTICE_TITLE", story)
        strings = (ROOT / "data" / "translations" / "patcher_strings.json").read_text(encoding="utf-8")
        self.assertNotIn("story_fog_notice.FOG_NOTICE_TITLE", strings, "no title row to translate")
        self.assertIn("fog_notice_tick(game);", main)
        self.assertIn("fog_notice_village_reset(game);", main)
        row = json.loads(FEATURE.read_text(encoding="utf-8"))
        self.assertEqual([n["id"] for n in row["needs_on"]], ["vv5_story_cheat_upgrades"])

    def test_the_dll_exports_imports_and_shows_no_text(self):
        try:
            import pefile
        except ImportError:
            self.skipTest("pefile is not installed")
        pe = pefile.PE(str(DLL))
        names = sorted(e.name.decode() for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name)
        self.assertEqual(names, ["VvfpFogListeningCount", "VvfpFogListeningInstalled",
                                 "VvfpFogListeningNoRestrictions", "VvfpFogListeningNotices", "VvfpFogNoticePending",
                                 "VvfpFogNoticeTaken", "VvfpFogNoticeVillageReset", "VvfpStartup"])
        imports = {i.name.decode() for e in pe.DIRECTORY_ENTRY_IMPORT for i in e.imports if i.name}
        self.assertEqual(imports & {"LoadLibraryA", "LoadLibraryW", "OutputDebugStringA", "OutputDebugStringW",
                                    "MessageBoxA", "MessageBoxW", "CreateFileA", "DeleteFileW", "MoveFileW",
                                    "RegSetValueExW", "Sleep", "CreateThread"}, set())
        source = (ROOT / "native" / "vvfp_fog_listening" / "vvfp_fog_listening.c").read_text(encoding="utf-8")
        self.assertNotIn("OutputDebugString", source)


@unittest.skipIf(_skip(), _skip() or "")
class Listening(unittest.TestCase):
    maxDiff = None

    def island(self, mode="collection_progression", *, big=False, free=False, start=True, **kw) -> Island:
        rows = [ROW] + ([FREE] if free else []) + (["vv5_population_256"] if big else [])
        v = Island(render(5, with_requirements(5, rows), mode), big=big, free=free, **kw)
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

    # ---- the notice -------------------------------------------------------------------------------------------
    def test_the_first_refusal_in_a_village_says_why_once(self):
        for mode in MODES:
            for kind in ("orange", "red"):
                with self.subTest(mode=mode, kind=kind):
                    v = self.island(mode)
                    v.weather(True, 4.0)
                    self.refused(v, v.believer(1), v.heathen(2, kind, -10, name=b"Kaimana Nalu"))
                    self.assertEqual(v.said, [(POPUP, WONT.format("Kaimana Nalu"))],
                                     "one popup, with the Heathen's name")
                    self.assertEqual(len(v.notices()), 1)
                    self.assertIn("\\virtual villagers fun patcher\\save 1\\data\\fog of doom\\", v.notices()[0])
                    v.actions.clear()
                    self.refused(v, v.believer(3), v.heathen(4, kind, 0, name=b"Other"))
                    self.assertEqual(len(v.said), 1, "never again in that village")
                    self.assertEqual(v.export("VvfpFogListeningNotices"), 1)

    def test_with_guardians_of_isola_the_wary_words(self):
        v = self.island(isola=True)
        v.weather(True, 4.0)
        self.refused(v, v.believer(1), v.heathen(2, "red", 5, name=b"Lani"))
        self.assertEqual(v.said, [(POPUP, WARY.format("Lani"))])

    def test_the_notice_survives_quitting_and_start_over_resets_it(self):
        files: dict = {}
        v = self.island(files=files)
        v.weather(True, 4.0)
        self.refused(v, v.believer(1), v.heathen(2, "orange", -3))
        self.assertEqual(len(v.said), 1)
        again = self.island(files=files)                   # the game quit and started again: the same disk
        again.weather(True, 4.0)
        self.refused(again, again.believer(1), again.heathen(2, "orange", -3))
        self.assertEqual(again.said, [], "kept across quitting")
        other = self.island(files=files, slot=2)            # another slot's village has its own
        other.weather(True, 4.0)
        self.refused(other, other.believer(1), other.heathen(2, "red", -1, name=b"Mele"))
        self.assertEqual(other.said, [(POPUP, WONT.format("Mele"))])
        # Start Over: native/shared/save_reset.c deletes the slot's whole "Virtual Villagers Fun Patcher\Save 1"
        # folder (START OVER WIPES THE WHOLE SAVE).
        for path in [p for p in files if "\\virtual villagers fun patcher\\save 1\\" in p]:
            del files[path]
        fresh = self.island(files=files)
        fresh.weather(True, 4.0)
        self.refused(fresh, fresh.believer(1), fresh.heathen(2, "red", -10, name=b"Keoni"))
        self.assertEqual(fresh.said, [(POPUP, WONT.format("Keoni"))], "a new village is told again")
        self.assertEqual(len([p for p in files if "save 2" in p]), 1, "slot 2's mark untouched")

    def test_no_notice_for_blue_natural_fog_no_fog_listening_or_no_restrictions(self):
        cases = (("blue", True, 4.0, 0, False), ("red", True, 1.0, 0, False), ("red", False, 0.0, 0, False),
                 ("orange", True, 4.0, -11, False), ("orange", True, 4.0, 0, True), ("red", True, 1.0, 0, True))
        for kind, fog, thickness, faith, free in cases:
            with self.subTest(kind=kind, fog=fog, thickness=thickness, faith=faith, free=free):
                v = self.island(free=free)
                v.weather(fog, thickness)
                v.drop(v.believer(1), v.heathen(2, kind, faith))
                self.assertEqual((v.said, v.notices()), ([], []))

    def test_the_popup_waits_for_the_story_companion_and_is_never_doubled(self):
        """While another popup or event holds the slot (story_notice_arm refuses), the notice waits; more refusals
        meanwhile make no second one; the village is marked only once it is armed."""
        v = self.island()
        v.weather(True, 4.0)
        v.story_can_show = False
        self.refused(v, v.believer(1), v.heathen(2, "orange", -4, name=b"First"))
        v.actions.clear()
        self.refused(v, v.believer(3), v.heathen(4, "red", 2, name=b"Second"))
        self.assertEqual((v.said, v.notices()), ([], []), "waiting: not shown, the village not marked yet")
        v.story_can_show = True
        v.story_frame()
        v.story_frame()
        self.assertEqual(v.said, [(POPUP, WONT.format("First"))], "shown once, for the first refusal")
        self.assertEqual(len(v.notices()), 1)

    def test_start_over_drops_a_waiting_popup_and_another_slot_never_gets_it(self):
        v = self.island()
        v.weather(True, 4.0)
        v.story_can_show = False
        self.refused(v, v.believer(1), v.heathen(2, "red", 0))
        v.export("VvfpFogNoticeVillageReset", 5)           # VvfpStoryVillageReset (Start Over, a deleted tribe)
        v.story_can_show = True
        v.story_frame()
        self.assertEqual((v.said, v.notices()), ([], []))
        w = self.island()
        w.weather(True, 4.0)
        w.story_can_show = False
        self.refused(w, w.believer(1), w.heathen(2, "red", 0))
        w.put32(w.u32(SAVE_MANAGER) + SAVE_SLOT_FIELD, 3)  # the player went to the village in slot 3
        w.story_can_show = True
        w.story_frame()
        self.assertEqual((w.said, w.notices()), ([], []), "slot 1's notice is never shown in slot 3")

    def test_other_games_and_small_buffers_get_nothing(self):
        v = self.island()
        v.weather(True, 4.0)
        v.story_can_show = False
        self.refused(v, v.believer(1), v.heathen(2, "red", 0))
        buffer = v.alloc(0x1000)
        self.assertEqual(v.export("VvfpFogNoticePending", 4, buffer, 0x1000), 0)
        self.assertEqual(v.export("VvfpFogNoticePending", 5, buffer, 100), 0)
        self.assertEqual(v.export("VvfpFogNoticePending", 5, buffer, 0x1000), 1)

    def test_no_slot_known_no_notice(self):
        v = self.island(slot=0)
        v.weather(True, 4.0)
        self.refused(v, v.believer(1), v.heathen(2, "red", 0))
        self.assertEqual((v.said, v.notices()), ([], []))

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
