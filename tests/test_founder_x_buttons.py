"""X Buttons to Remove Chosen Founders (The Tree of Life, New Believers): "VVFP Founder X Buttons.dll".

The owner (2026-11-24): "add patches to vv4 and vv5 when selecting villagers for the expedition. I want to add X
buttons beside the 5 slots so we can choose new candidates."  Clicking an X removes that chosen villager -- gone, like
a Reject; the slot opens, the others stay (moved down) and the player picks on until five are chosen.  On by default,
in Owner's Defaults and in Select All.

* THE ROWS: one per game, the DLL pinned by SHA-256, its three run-time sites' stock bytes those of the stock
  executables, on in every preset, started from the third word, shipped by the release.
* THE HARNESS (native/vvfp_founder_x_buttons/founder_x_harness.c): the companion's logic against a fake screen and
  table in both games' layouts with 150 and 256 records -- with no X the stock screen byte for byte; every slot
  removed with 1..5 chosen, the Done state, Rejects after a removal, the started island.
* EMULATED on the executable the patcher renders for the row (and with 256 Villagers): the install, the candidate
  generator's own stock code run through the splice (the count read as the lowest free record, the real count put
  back), an X click through the screen's vtable, the Done state's way back, the X buttons made and put on in the
  draw -- each routine the companion calls stood in for with its real argument count, so a wrong calling convention
  breaks the run.
"""
from __future__ import annotations

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
    from test_companion_installs_all_or_none import HAVE_EMULATOR, Machine, render, stock_path, with_requirements
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

NAME = "X Buttons to Remove Chosen Founders"
DLL_NAME = "VVFP Founder X Buttons.dll"
DLL = ROOT / "assets" / "founder_x_buttons" / DLL_NAME
SOURCE = ROOT / "native" / "vvfp_founder_x_buttons" / "vvfp_founder_x_buttons.c"
CL = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231\bin\Hostx64\x86\cl.exe")
X_ID = 0x5858
COUNT, CANDIDATE, CHOSEN, REJECT = 0x18, 0x08, 0x1C, 0x30


def row_id(game: int) -> str:
    return f"vv{game}_founder_x_buttons"


def feature(game: int) -> dict:
    return json.loads((ROOT / "data" / f"{row_id(game)}_feature.json").read_text(encoding="utf-8"))


# The game's addresses the companion uses (native/vvfp_founder_x_buttons/vvfp_founder_x_buttons.c).
GAME = {
    4: dict(vtable=0x48EB38, handler=0x43BC00, draw=0x43B6A0, generator=0x43B830, table=0x50E568, big=0x800000,
            first=0x44, size=0x2E3C, present=0x1CC4, rand=0x4036D0, names=0x46C800, names_pop=0x1C, allocate=0x466270,
            next=0x43BA80, op_new=0x470C5C, images=0x44CCF0, image=0x44CB70, image_id=0xEB, button=0x401C20,
            label=0x401600, label_text=0x4015F0, colour=0x4BE894, add=0x40C190, find=0x40C1E0, remove=0x40C210,
            resources=0x44DA20, string=0x44D3D0, select=0x54, sound=0x448E10, sounds=0x4DA020, sound_id=0x64,
            slots=(97, 245, 398, 546, 698), plank=140),
    5: dict(vtable=0x49A074, handler=0x43E600, draw=0x43E030, generator=0x43E220, table=0x554148, big=0x800000,
            first=0x48, size=0x2F44, present=0x1CD4, rand=0x403660, names=0x477DE0, names_pop=0x20, allocate=0x46FAD0,
            next=0x43E470, op_new=0x47BBDC, images=0x44FBB0, image=0x44FA30, image_id=0xCD, button=0x401BD0,
            label=0x4015D0, label_text=0x4015C0, colour=0x4CCBCC, add=0x40C680, find=0x40C6D0, remove=0x40C700,
            resources=0x450D40, string=0x4506D0, select=0x49, sound=0x44C440, sounds=0x51F440, sound_id=0x66,
            slots=(202, 350, 503, 651, 803), plank=215),
}


class TheRows(unittest.TestCase):
    def test_each_game_has_its_row(self) -> None:
        digest = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        for game in (4, 5):
            with self.subTest(game=game):
                row = feature(game)
                self.assertEqual(row["id"], row_id(game))
                self.assertEqual(row["game_id"], f"vv{game}")
                self.assertEqual(row["name"], NAME)
                self.assertEqual(row["dependencies"], [])
                self.assertEqual(row["patches"], [])
                self.assertEqual(row["companion_files"], [{"source": f"assets/founder_x_buttons/{DLL_NAME}",
                                                           "destination": DLL_NAME, "sha256": digest}])
                self.assertIn("Select 5 villagers", row["description"])
                self.assertIn("**Seen working in a running game** (2026-11-24;", row["description"])
                self.assertEqual([d["va"] for d in row["runtime_detours"]],
                                 [f"0x{GAME[game]['generator']:X}", f"0x{GAME[game]['vtable'] + 0xC:X}",
                                  f"0x{GAME[game]['vtable'] + 0x18:X}"])

    def test_no_other_game_has_the_row(self) -> None:
        ids = {p.id for p in patcher.load_public_fun_patches() if p.id.endswith("_founder_x_buttons")}
        self.assertEqual(ids, {"vv4_founder_x_buttons", "vv5_founder_x_buttons"})

    def test_the_sites_hold_these_stock_bytes(self) -> None:
        import pefile
        for game in (4, 5):
            exe = ROOT / "inputs" / f"vv{game}-stock-copy"
            found = sorted(exe.glob("*.exe")) if exe.is_dir() else []
            if not found:
                self.skipTest("stock executables not present (inputs/)")
            pe = pefile.PE(str(found[0]), fast_load=True)
            for detour in feature(game)["runtime_detours"]:
                with self.subTest(game=game, va=detour["va"]):
                    stock = bytes.fromhex(detour["stock_bytes"])
                    rva = int(detour["va"], 16) - pe.OPTIONAL_HEADER.ImageBase
                    self.assertEqual(pe.get_data(rva, len(stock)), stock)

    def test_on_by_default_in_owners_defaults_and_select_all(self) -> None:
        import vv_fun_patcher_gui as gui
        for game in (4, 5):
            pid = row_id(game)
            with self.subTest(pid):
                self.assertTrue(gui.default_fun_patch_selection(pid))
                self.assertTrue(gui.owners_default_fun_patch_selection(pid))
                self.assertTrue(gui.select_all_fun_patch_selection(pid))
                self.assertNotIn(pid, gui.DEFAULT_OFF_FUN_PATCH_IDS)

    def test_started_from_the_third_word(self) -> None:
        # In the append-only third word (later companions come after it; position = bit).
        self.assertIn(DLL_NAME, patcher.STARTUP_LOADER_COMPANIONS_3)
        header = (ROOT / "native" / "shared" / "startup_companions_3.h").read_text(encoding="utf-8")
        self.assertIn(f'"{DLL_NAME}",', header)
        record = json.loads((ROOT / "data" / "more_companions_companion.json").read_text(encoding="utf-8"))
        more = ROOT / record["source"]
        self.assertEqual(hashlib.sha256(more.read_bytes()).hexdigest().upper(), record["sha256"])

    def test_the_release_ships_its_files(self) -> None:
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        for path in (f"assets/founder_x_buttons/{DLL_NAME}", "data/vv4_founder_x_buttons_feature.json",
                     "data/vv5_founder_x_buttons_feature.json"):
            self.assertIn(f'    "{path}",\n', release)

    def test_the_exports(self) -> None:
        import pefile
        pe = pefile.PE(str(DLL))
        names = sorted(s.name.decode() for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name)
        self.assertEqual(names, ["VvfpFounderXInstalled", "VvfpStartup"])

    def test_the_source_pins(self) -> None:
        text = SOURCE.read_text(encoding="utf-8")
        # The game's own art and label; the table read from the generator, never a fixed population.
        self.assertIn('static const char FX_LABEL[] = "X";', text)
        self.assertIn("0xEB, 37, 40", text)
        self.assertIn("0xCD, 37, 40", text)
        self.assertIn("fx_table(g)", text)
        self.assertNotIn("0x96", text)
        self.assertNotIn("150", text.replace("150 and 256", ""))
        # The X buttons go on and off the screen only in its draw, never inside a click.
        take_out = text[text.index("static void fx_take_out("):text.index("static int fx_command(")]
        self.assertNotIn("fx_add(", take_out)
        self.assertNotIn("fx_remove_child(", take_out)
        self.assertIn("g_restore_reject = 1;", take_out)
        self.assertNotRegex(text, r"OutputDebugString|printf")


@unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
class TheHarness(unittest.TestCase):
    def test_the_harness_passes(self) -> None:
        result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                 str(ROOT / "scripts" / "build_founder_x_harness.ps1")],
                                capture_output=True, text=True, timeout=600)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("== 0 failure(s) ==", result.stdout)
        self.assertNotIn("FAIL", result.stdout)
        for layout in ("The Tree of Life, 150 records", "The Tree of Life, 256 records",
                       "New Believers, 150 records", "New Believers, 256 records"):
            self.assertIn(layout, result.stdout)


class Screen:
    """The rendered game with the companion installed, a "Select 5 villagers" screen object in its heap and the
    routines around the screen stood in for (each popping its real argument bytes)."""

    def __init__(self, test: unittest.TestCase, game: int, big: bool):
        rows = [row_id(game)] + ([f"vv{game}_population_256"] if big else [])
        self.g = g = GAME[game]
        self.m = m = Machine(render(game, with_requirements(game, rows), "collection_progression"), DLL)
        m.export("VvfpStartup", game, 0)
        test.assertEqual(m.export("VvfpFounderXInstalled"), 1, "installed")
        self.table = g["big"] if big else g["table"]
        test.assertEqual(m.u32(g["generator"] + 0xC), self.table, "the generator's own table")
        self.population = 256 if big else 150
        self.screen = m.alloc(0x100)
        self.reject = m.alloc(0x20)
        m.put32(self.reject + 4, 2)
        self.select = m.alloc(0x20)
        m.put32(self.select + 4, 1)
        m.put32(self.screen + REJECT, self.reject)
        m.put32(self.screen + CANDIDATE, 0xFFFFFFFF)
        self.children = [self.select, self.reject]
        self.buttons: dict[int, tuple[int, int, int, str]] = {}
        self.labels: list[tuple[int, str]] = []
        self.sounds = 0
        self.nexts = 0
        self.draws = 0
        self.serial = 0
        self.select_text = m.alloc(16)
        m.write(self.select_text, b"Select\0")
        m.stub(g["rand"], lambda p: (0, 0))                       # rand(n) 0: a girl of 6, never pregnant
        m.stub(g["names"], lambda p: (0, g["names_pop"]))
        m.stub(g["allocate"], self._allocate)
        m.stub(g["next"], self._next)
        m.stub(g["op_new"], lambda p: (p.alloc(max(p.arg(0), 0x20)), 0))
        m.stub(g["images"], lambda p: (0x1234, 0))
        m.stub(g["image"], lambda p: (0x5678 if p.arg(0) == g["image_id"] and p.reg("ecx") == 0x1234 else 0, 4))
        m.stub(g["button"], self._button)
        m.stub(g["label"], self._label)
        m.stub(g["label_text"], self._label_text)
        m.stub(g["add"], self._add)
        m.stub(g["find"], self._find)
        m.stub(g["remove"], self._remove)
        m.stub(g["resources"], lambda p: (0x9ABC, 0))
        m.stub(g["string"], lambda p: (self.select_text if p.arg(0) == g["select"] else 0, 4))
        m.stub(g["sound"], self._sound)
        m.stub(g["draw"], self._draw)

    # ---- the stand-ins -----------------------------------------------------------------------------------------
    def record(self, i: int) -> int:
        return self.table + self.g["first"] + i * self.g["size"]

    def present(self, i: int) -> bool:
        return self.m.read(self.record(i) + self.g["present"], 1) != b"\0"

    def _allocate(self, p):
        assert p.reg("ecx") == self.table
        for i in range(self.population):
            if not self.present(i):
                p.write(self.record(i) + self.g["present"], b"\1")
                self.serial += 1
                p.put32(self.record(i) + 0x10, self.serial)
                return i, 0x38
        return 0xFFFFFFFF, 0x38

    def _next(self, p):
        self.nexts += 1
        return 0, 0

    def _button(self, p):
        bid, picture, x, y, parent = (p.arg(i) for i in range(5))
        assert picture == 0x5678 and parent == self.screen and p.arg(5) == 0
        p.put32(p.reg("ecx") + 4, bid)
        self.buttons[bid] = (p.reg("ecx"), x, y, "")
        return p.reg("ecx"), 0x18

    def _string(self, p, va):
        return bytes(p.read(va, 16)).split(b"\0")[0].decode()

    def _label(self, p):
        colour = p.u32(self.g["colour"])
        assert (p.arg(1), p.arg(2), p.arg(3), p.arg(4)) == (colour, colour, colour, 0)
        self.labels.append((p.reg("ecx"), self._string(p, p.arg(0))))
        return 0, 0x14

    def _label_text(self, p):
        assert p.arg(1) == 0
        self.labels.append((p.reg("ecx"), self._string(p, p.arg(0))))
        return 0, 8

    def _add(self, p):
        assert p.reg("ecx") == self.screen
        self.children.append(p.arg(0))
        return 0, 4

    def _remove(self, p):
        assert p.reg("ecx") == self.screen
        self.children.remove(p.arg(0))
        return 0, 4

    def _find(self, p):
        for child in self.children:
            if p.u32(child + 4) == p.arg(0):
                return child, 4
        return 0, 4

    def _sound(self, p):
        assert p.reg("ecx") == self.g["sounds"] and p.arg(0) == self.g["sound_id"]
        self.sounds += 1
        return 0, 4

    def _draw(self, p):
        self.draws += 1
        return 0, 0

    # ---- the screen ----------------------------------------------------------------------------------------------
    def count(self) -> int:
        return self.m.u32(self.screen + COUNT)

    def ids(self) -> list[int]:
        return [self.m.u32(self.screen + CHOSEN + 4 * k) for k in range(self.count())]

    def generate(self) -> int:
        made = self.m.call(self.g["generator"], ecx=self.screen)
        self.m.put32(self.screen + CANDIDATE, made)
        return made

    def choose(self) -> None:
        n = self.count()
        self.m.put32(self.screen + CHOSEN + 4 * n, self.m.u32(self.screen + CANDIDATE))
        self.m.put32(self.screen + COUNT, n + 1)

    def command(self, command: int, ident: int) -> int:
        return self.m.call(self.m.u32(self.g["vtable"] + 0xC), [command, ident], ecx=self.screen) & 0xFF

    def frame(self) -> None:
        self.m.call(self.m.u32(self.g["vtable"] + 0x18), ecx=self.screen)

    def xs(self) -> list[int]:
        return sorted(self.m.u32(c + 4) - X_ID for c in self.children if self.m.u32(c + 4) >= X_ID)

    def present_set(self) -> set[int]:
        return {i for i in range(self.population) if self.present(i)}


@unittest.skipUnless(HAVE_EMULATOR, "unicorn/pefile not installed")
class Emulated(unittest.TestCase):
    def screen(self, game: int, big: bool = False) -> Screen:
        if not stock_path(game).is_file():
            self.skipTest("stock executable not present (inputs/)")
        return Screen(self, game, big)

    def test_the_sites_are_written(self) -> None:
        for game in (4, 5):
            with self.subTest(game=game):
                s = self.screen(game)
                g = s.g
                self.assertEqual(s.m.read(g["generator"], 1), b"\xE9")
                self.assertNotEqual(s.m.u32(g["vtable"] + 0xC), g["handler"])
                self.assertNotEqual(s.m.u32(g["vtable"] + 0x18), g["draw"])
                self.assertEqual(s.m.u32(g["vtable"] + 0x24), {4: 0x43BB60, 5: 0x43E560}[game], "show untouched")

    def test_the_stock_generator_runs_through_the_splice(self) -> None:
        """With no X: the candidate made in record [+0x18], as the stock code alone does.  After an X: the count
        reads as the lowest free record while the stock code runs, and the real count is back after."""
        for game in (4, 5):
            for big in (False, True):
                with self.subTest(game=game, big=big):
                    s = self.screen(game, big)
                    self.assertEqual(s.generate(), 0)
                    s.choose()
                    self.assertEqual(s.generate(), 1)                # the stock flow: record [+0x18]
                    s.generate()                                     # a Reject: the same record again
                    self.assertEqual(s.m.u32(s.screen + CANDIDATE), 1)
                    self.assertEqual(s.present_set(), {0, 1})
                    s.choose()
                    self.assertEqual(s.generate(), 2)
                    s.choose()
                    self.assertEqual(s.generate(), 3)
                    self.assertEqual((s.count(), s.ids()), (3, [0, 1, 2]))
                    # X on slot 0: record 0 goes, the others move down, the candidate (3) stays.
                    self.assertEqual(s.command(8, X_ID + 0), 1)
                    self.assertEqual((s.count(), s.ids()), (2, [1, 2]))
                    self.assertEqual(s.present_set(), {1, 2, 3})
                    self.assertEqual(s.m.u32(s.screen + CANDIDATE), 3)
                    self.assertEqual(s.sounds, 1)
                    # A Reject now: the candidate 3 freed, the new one in record 0, the count back to 2.
                    self.assertEqual(s.generate(), 0)
                    self.assertEqual(s.count(), 2)
                    self.assertEqual(s.present_set(), {0, 1, 2})
                    s.choose()
                    self.assertEqual(s.generate(), 3)
                    self.assertEqual((s.count(), s.ids()), (3, [1, 2, 0]))
                    self.assertEqual(s.present_set(), {0, 1, 2, 3})
                    # An empty slot's X does nothing; another message goes on to the stock handler.
                    self.assertEqual(s.command(8, X_ID + 4), 1)
                    self.assertEqual((s.count(), s.ids()), (3, [1, 2, 0]))
                    self.assertEqual(s.command(6, 0), 0)

    def test_the_buttons_are_made_and_put_on_in_the_draw(self) -> None:
        for game in (4, 5):
            with self.subTest(game=game):
                s = self.screen(game)
                g = s.g
                s.generate()
                s.frame()
                self.assertEqual((s.xs(), s.buttons, s.draws), ([], {}, 1), "none chosen: no X, none made")
                for _ in range(3):
                    s.choose()
                    s.generate()
                s.frame()
                self.assertEqual(s.xs(), [0, 1, 2])
                self.assertEqual(sorted(s.buttons), [X_ID + k for k in range(5)])
                for k in range(5):
                    _, x, y, _ = s.buttons[X_ID + k]
                    self.assertEqual((x + 37, y + 40), (g["slots"][k] + 67, g["plank"] - 1), "the plank's right end")
                self.assertEqual([text for _, text in s.labels], ["X"] * 5)
                s.command(8, X_ID + 1)
                self.assertEqual(s.xs(), [0, 1, 2], "nothing goes on or off inside the click")
                s.frame()
                self.assertEqual(s.xs(), [0, 1])
                self.assertEqual(s.draws, 3)

    def test_the_done_state(self) -> None:
        """Five chosen, Reject off, Select labelled Done: an X gives Select its label back, a new candidate and, in
        the next draw, Reject.  Five chosen with Reject still on (the island started): no X, and an X does nothing."""
        for game in (4, 5):
            with self.subTest(game=game):
                s = self.screen(game)
                s.generate()
                for _ in range(5):
                    s.choose()
                    if s.count() < 5:
                        s.generate()
                s.children.remove(s.reject)                      # the Done state
                s.frame()
                self.assertEqual(s.xs(), [0, 1, 2, 3, 4])
                self.assertEqual(s.command(8, X_ID + 2), 1)
                self.assertEqual((s.count(), s.ids()), (4, [0, 1, 3, 4]))
                self.assertFalse(s.present(2))
                self.assertEqual(s.labels[-1], (s.select, "Select"))
                self.assertEqual(s.nexts, 1)
                self.assertNotIn(s.reject, s.children)
                s.frame()
                self.assertIn(s.reject, s.children)
                self.assertEqual(s.xs(), [0, 1, 2, 3])
                # The island started at the fifth Select (Reject still on): no X, and an X click does nothing.
                s.choose()
                s.frame()
                self.assertEqual(s.xs(), [])
                before = (s.count(), s.ids(), s.present_set())
                self.assertEqual(s.command(8, X_ID + 0), 1)
                self.assertEqual((s.count(), s.ids(), s.present_set()), before)


if __name__ == "__main__":
    unittest.main()
