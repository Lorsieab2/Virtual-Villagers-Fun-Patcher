"""Esteemed Elders in Every Game (the owner, 2026-11-22: "all 5 games should change a villager's title to 'Esteemed
Elder' if they master 3 skills (EXCEPT SPECIAL VILLAGERS LIKE THE GOLDEN CHILD, VV3 TRIBAL CHIEF ETC)").

EMULATED, on the executable the patcher renders for the row (A New Home, The Lost Children, The Tree of Life), with
"VVFP Esteemed Elders.dll" started as VVFP More Companions.dll starts it (VvfpStartup(game, ...)):

* the villager panel's own title code runs from the companion's site with the game's registers and stack, and ends
  where the game copies the title (the Esteemed Elder), goes on to the rank (anyone else), or to its own special
  title (the Golden Child, The Tree of Life's Scholar) -- and WITHOUT the companion (the stock game) the same
  villager goes on to the rank: the test fails on the stock executable and passes with the row;
* The Lost Children's burial picks the game's own elder epitaph for a three-mastered villager it has not flagged;
* The Tree of Life's Roster of the Dead writer 0x45D470 runs whole and the grave's epitaph is "Esteemed Elder" for
  three or four mastered, the job's for a Scholar or anyone else (and for everyone in the stock game);
* A New Home's grave epitaph (the Cause of Death companion's test build, its burial routine) is epitaph 14 only
  while the Esteemed Elders companion answers that it is installed.

The Secret City and New Believers already give the title in the stock game (0x462570, 0x475610): no row, nothing
changed; the logs' rule there is the game's (native/shared/special_title.h).
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
sys.path.insert(0, str(ROOT / "scripts"))

import vv_fun_patcher as patcher  # noqa: E402

try:
    from unicorn import UC_HOOK_CODE

    from test_companion_installs_all_or_none import HAVE_EMULATOR, Machine, render, stock_path, with_requirements
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

DLL_NAME = "VVFP Esteemed Elders.dll"
DLL = ROOT / "assets" / "esteemed_elders" / DLL_NAME
CAUSE_TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Cause of Death.test.dll"
GAMES = (1, 2, 4, 5)
FAKE_ELDERS = 0x0C800000
TITLE = "Esteemed Elder"


def row_id(game: int) -> str:
    return f"vv{game}_esteemed_elders"


def feature(game: int) -> dict:
    return json.loads((ROOT / "data" / f"{row_id(game)}_feature.json").read_text(encoding="utf-8"))


class Panel(Machine):
    """The rendered game with the companion (started or not), and stops at the panel's branch targets."""

    def __init__(self, game: int, *, start: bool = True):
        super().__init__(render(game, with_requirements(game, [row_id(game)]), "collection_progression"), DLL)
        self.game = game
        self.stops: dict[int, str] = {}
        self.stopped: str | None = None
        if start:
            self.export("VvfpStartup", game, 0)

    def stop_at(self, targets: dict[int, str]) -> None:
        self.stops = targets

        def hit(mu, address, size, user):
            if address in self.stops:
                self.stopped = self.stops[address]
                mu.emu_stop()
        for va in targets:
            self.mu.hook_add(UC_HOOK_CODE, hit, begin=va, end=va)

    def run_from(self, site: int, regs: dict[str, int], stack: dict[int, int] | None = None) -> int:
        """Run from `site` with `regs` and a stack (`stack`: offset from esp -> dword); returns esp at the site."""
        esp = 0x0FF00000 - 0x4000
        for offset, value in (stack or {}).items():
            self.put32(esp + offset, value)
        self.set_reg("esp", esp)
        for name, value in regs.items():
            self.set_reg(name, value)
        self.stopped = None
        self.mu.emu_start(site, 0xFFFFFFFF, count=2_000_000)
        return esp


def _skip() -> str | None:
    if not HAVE_EMULATOR:
        return "unicorn/pefile not installed"
    for game in GAMES:
        if not stock_path(game).is_file():
            return "stock executables not present (inputs/)"
    if not DLL.is_file():
        return f"{DLL} missing"
    return None


class TheRows(unittest.TestCase):
    def test_one_row_per_game_that_needs_it(self):
        ids = {p.id for p in patcher.load_public_fun_patches()}
        for game in GAMES:
            with self.subTest(game=game):
                row = feature(game)
                self.assertEqual(row["id"], row_id(game))
                self.assertIn(row_id(game), ids)
                self.assertEqual(row["name"], "Esteemed Elders in Every Game")
                self.assertEqual(row["game_id"], f"vv{game}")
                self.assertEqual(row["patches"], [])
                self.assertEqual([c["destination"] for c in row["companion_files"]], [DLL_NAME])
                self.assertIn("Esteemed Elder", row["description"])
                self.assertIn("**", row["description"])
        self.assertNotIn(row_id(3), ids, "the stock game already gives the title")
        self.assertIn(DLL_NAME, patcher.STARTUP_LOADER_COMPANIONS_3)
        header = (ROOT / "native" / "shared" / "startup_companions_3.h").read_text(encoding="utf-8")
        self.assertIn(f'"{DLL_NAME}"', header)

    def test_on_in_owners_defaults_only(self):
        from vv_fun_patcher_gui import (default_fun_patch_selection, owners_default_fun_patch_selection,
                                        select_all_fun_patch_selection)
        for game in GAMES:
            with self.subTest(game=game):
                self.assertFalse(default_fun_patch_selection(row_id(game)))
                self.assertTrue(owners_default_fun_patch_selection(row_id(game)))
                self.assertFalse(select_all_fun_patch_selection(row_id(game)))

    def test_bundled(self):
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn(f'"assets/esteemed_elders/{DLL_NAME}"', release)
        for game in GAMES:
            self.assertIn(f'"data/{row_id(game)}_feature.json"', release)

    def test_the_dll_exports_imports_and_no_debug(self):
        try:
            import pefile
        except ImportError:
            self.skipTest("pefile is not installed")
        pe = pefile.PE(str(DLL))
        names = sorted(e.name.decode() for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name)
        self.assertEqual(names, ["VvfpEsteemedEldersGiven", "VvfpEsteemedEldersInstalled", "VvfpStartup"])
        imports = {i.name.decode() for e in pe.DIRECTORY_ENTRY_IMPORT for i in e.imports if i.name}
        # (The static C runtime brings its own file calls; the companion's source opens no file: checked below.)
        self.assertEqual(imports & {"OutputDebugStringA", "OutputDebugStringW", "MessageBoxA", "MessageBoxW",
                                    "CreateThread", "LoadLibraryA", "LoadLibraryW"}, set())
        for section in pe.sections:
            self.assertFalse(section.Characteristics & 0x20000000 and section.Characteristics & 0x80000000)
        source = (ROOT / "native" / "vvfp_esteemed_elders" / "vvfp_esteemed_elders.c").read_text(encoding="utf-8")
        self.assertNotIn("OutputDebugString", source)
        self.assertNotIn("CreateFile", source)


# ---- records -------------------------------------------------------------------------------------------------

def vv1_record(m: Machine, skills, golden=False) -> int:
    r = m.alloc(0x400)
    for k, v in enumerate(skills):
        m.put32(r + 0x3BC + 4 * k, v)
    m.put32(r + 0x36C, 0xC7 if golden else 3)
    return r


def vv2_record(m: Machine, skills, flag=0, totem=0) -> int:
    r = m.alloc(0x900)
    for k, v in enumerate(skills):
        m.put32(r + 0x7E4 + 4 * k, v)
    m.write(r + 0x7FC, bytes([flag]))
    m.write(r + 0x558, bytes([totem]))
    return r


def vv4_record(m: Machine, skills, ghost=0, age=1200) -> int:
    r = m.alloc(0x2E40)
    for k, v in enumerate(skills):
        m.write(r + 0x1C5C + 4 * k, struct.pack("<f", v))
    m.write(r + 0x1CC7, bytes([ghost]))
    m.put32(r + 0x1B8C, age)
    m.write(r + 0x1B9C, b"Kalani\0")
    return r


@unittest.skipIf(_skip(), _skip() or "")
class TitleOnThePanel(unittest.TestCase):
    maxDiff = None

    def vv1(self, skills, golden=False, start=True) -> tuple[str, str | None]:
        m = Panel(1, start=start)
        if start:
            self.assertEqual(m.export("VvfpEsteemedEldersInstalled"), 1)
        m.stop_at({0x41FBE8: "golden", 0x41FBFD: "rank", 0x41FD6D: "title"})
        r = vv1_record(m, skills, golden)
        esp = m.run_from(0x41FBDC, {"ecx": r, "eax": max(skills), "ebx": 0, "ebp": m.alloc(0x400)})
        text = None
        if m.stopped == "title":
            self.assertEqual(m.reg("esp"), esp - 8)
            self.assertEqual(m.u32(m.reg("esp")), esp + 0x24, "the panel's own title buffer")
            text = m.cstring(m.u32(m.reg("esp") + 4))
        elif m.stopped == "rank":
            self.assertEqual((m.reg("esp"), m.reg("eax"), m.reg("ecx")), (esp, max(skills), r),
                             "the rank goes on with the game's registers")
        return m.stopped, text

    def test_vv1_three_mastered_at_90(self):
        self.assertEqual(self.vv1([90, 95, 100, 10, 0]), ("title", TITLE))
        self.assertEqual(self.vv1([90, 95, 89, 10, 0]), ("rank", None), "89 is Adept in A New Home")
        self.assertEqual(self.vv1([100, 100, 100, 100, 100], golden=True), ("golden", None), "the Golden Child first")

    def test_vv1_stock_game_gives_no_title(self):
        """Before: the stock panel shows the rank for the same villager (what the row changes)."""
        self.assertEqual(self.vv1([90, 95, 100, 10, 0], start=False), ("rank", None))

    def vv2(self, skills, flag=0, totem=0, start=True) -> str | None:
        m = Panel(2, start=start)
        m.stop_at({0x429C25: "title", 0x429C3D: "rank"})
        r = vv2_record(m, skills, flag, totem)
        esp = m.run_from(0x429C1D, {"ecx": r, "eax": max(skills), "ebx": 0, "ebp": m.alloc(0x400)})
        if m.stopped == "rank":
            self.assertEqual((m.reg("esp"), m.reg("eax"), m.reg("ecx")), (esp, max(skills), r))
        return m.stopped

    def test_vv2_flag_or_three_mastered(self):
        self.assertEqual(self.vv2([88, 88, 88, 0, 0]), "title")
        self.assertEqual(self.vv2([10, 0, 0, 0, 0], flag=1), "title", "the stock flag still gives it")
        self.assertEqual(self.vv2([88, 88, 87, 0, 0]), "rank")
        self.assertEqual(self.vv2([88, 88, 88, 0, 0], totem=1), "rank", "never a totem statue")

    def test_vv2_stock_game_needs_the_flag(self):
        self.assertEqual(self.vv2([88, 88, 88, 0, 0], start=False), "rank")
        self.assertEqual(self.vv2([0, 0, 0, 0, 0], flag=1, start=False), "title")

    def vv4(self, skills, ghost=0, start=True) -> tuple[str, str | None]:
        m = Panel(4, start=start)
        m.stop_at({0x44031D: "scholar", 0x440335: "rank", 0x4404D1: "title"})
        r = vv4_record(m, skills, ghost)
        esp = m.run_from(0x440314, {"ecx": r + 0x1C5C, "esi": r + 0x1C5C, "ebx": 0, "ebp": m.alloc(0x400)},
                         {0x10: r})
        text = None
        if m.stopped == "title":
            self.assertEqual(m.reg("esp"), esp - 8)
            self.assertEqual(m.u32(m.reg("esp")), esp + 0x28, "the panel's own title buffer")
            text = m.cstring(m.u32(m.reg("esp") + 4))
        elif m.stopped == "rank":
            self.assertEqual(m.reg("esp"), esp)
        return m.stopped, text

    def test_vv4_three_or_four_mastered_scholar_still_wins(self):
        self.assertEqual(self.vv4([88.0, 90.5, 100.0, 3.0, 0.0]), ("title", TITLE))
        self.assertEqual(self.vv4([88.0, 90.5, 100.0, 99.0, 0.0]), ("title", TITLE))
        self.assertEqual(self.vv4([88.0] * 5), ("scholar", None))
        self.assertEqual(self.vv4([88.0, 87.9, 100.0, 3.0, 0.0]), ("rank", None))
        self.assertEqual(self.vv4([88.0, 90.5, 100.0, 3.0, 0.0], ghost=1), ("rank", None), "never a ghost")

    def test_vv4_stock_game_gives_no_title(self):
        self.assertEqual(self.vv4([88.0, 90.5, 100.0, 3.0, 0.0], start=False), ("rank", None))
        self.assertEqual(self.vv4([88.0] * 5, start=False), ("scholar", None))


def vv5_record(m: Machine, skills, faction=0, role=0, orange=0) -> int:
    r = m.alloc(0x2F48)
    for k, v in enumerate(skills):
        m.write(r + 0x1C5C + 4 * k, struct.pack("<f", v))
    m.write(r + 0x1CEC, bytes([faction, orange]))
    m.put32(r + 0x1CFC, role)
    return r


@unittest.skipIf(_skip(), _skip() or "")
class NewBelieversHeathens(unittest.TestCase):
    """The owner (2026-11-22): a current Heathen NEVER shows "Esteemed Elder"; a Former Heathen (a believer now) does
    with three mastered skills (88+)."""

    def vv5(self, skills, start=True, **kw) -> str | None:
        m = Panel(5, start=start)
        if start:
            self.assertEqual(m.export("VvfpEsteemedEldersInstalled"), 1)
        m.stop_at({0x442EBE: "title", 0x442EFD: "rank"})
        r = vv5_record(m, skills, **kw)
        esp = m.run_from(0x442EB5, {"ecx": r + 0x1C5C, "esi": r + 0x1C5C, "ebx": 0, "ebp": m.alloc(0x400)}, {0x10: r})
        self.assertEqual(m.reg("esp"), esp)
        return m.stopped

    MASTERED = [88.0, 90.0, 100.0, 1.0, 0.0, 0.0]

    def test_a_heathen_never_a_former_heathen_and_a_believer_yes(self):
        self.assertEqual(self.vv5(self.MASTERED, faction=1, role=3), "rank", "a current Heathen")
        self.assertEqual(self.vv5(self.MASTERED, faction=1, role=12), "rank", "the Heathen Doctor keeps the role")
        self.assertEqual(self.vv5(self.MASTERED), "title", "a believer")
        self.assertEqual(self.vv5(self.MASTERED, orange=1), "title", "a Former Heathen (the orange mask byte)")
        self.assertEqual(self.vv5([88.0, 90.0, 87.9, 1.0, 0.0, 0.0]), "rank")

    def test_stock_game_titles_a_heathen(self):
        """Before: the stock panel gives a Heathen of no role title "Esteemed Elder"."""
        self.assertEqual(self.vv5(self.MASTERED, start=False, faction=1, role=3), "title")

@unittest.skipIf(_skip(), _skip() or "")
class TitleOnTheGrave(unittest.TestCase):
    def vv2_burial(self, skills, flag=0, start=True) -> str | None:
        m = Panel(2, start=start)
        m.stop_at({0x465146: "elder epitaph", 0x465172: "job epitaph"})
        r = vv2_record(m, skills, flag)
        m.run_from(0x46513C, {"ecx": r, "ebx": 0})
        return m.stopped

    def test_vv2_an_unflagged_elder_gets_the_games_own_epitaph(self):
        self.assertEqual(self.vv2_burial([88, 88, 88, 0, 0]), "elder epitaph")
        self.assertEqual(self.vv2_burial([88, 88, 0, 0, 0]), "job epitaph")
        self.assertEqual(self.vv2_burial([0, 0, 0, 0, 0], flag=1), "elder epitaph")

    def test_vv2_stock_burial_needs_the_flag(self):
        self.assertEqual(self.vv2_burial([88, 88, 88, 0, 0], start=False), "job epitaph")

    def vv4_grave(self, skills, age=1200, start=True) -> tuple[str, int]:
        m = Panel(4, start=start)
        job_text = m.alloc(0x40)
        m.write(job_text, b"Inspired Architect\0")
        m.stub(0x4036D0, lambda p: (0, 0))                       # rand(100): the first of the pair
        m.stub(0x44DA20, lambda p: (p.arg(0), 4))                # the string table (stdcall, the id)
        m.stub(0x44D3D0, lambda p: (job_text, 0))                # its text (thiscall)

        def strncpy(p):
            dest, src, n = p.arg(0), p.arg(1), p.arg(2)
            data = p.read(src, n)
            end = data.find(b"\0")
            data = data[:end] + bytes(n - end) if end >= 0 else data
            p.write(dest, data)
            return dest, 0
        m.stub(0x4724E0, strncpy)
        roster = m.alloc(0xC000)
        r = vv4_record(m, skills, age=age)
        m.call(0x45D470, [r, 7], ecx=roster)
        return m.cstring(roster + 0x38), m.read(roster + 0x31, 1)[0]

    def test_vv4_the_roster_writer_gives_an_elders_grave_the_title(self):
        self.assertEqual(self.vv4_grave([88.0, 90.0, 100.0, 0.0, 0.0]), (TITLE, 0))
        self.assertEqual(self.vv4_grave([88.0, 90.0, 100.0, 95.0, 0.0]), (TITLE, 0))
        self.assertEqual(self.vv4_grave([88.0] * 5)[1], 1, "the Scholar keeps the game's own epitaph and byte")
        self.assertNotEqual(self.vv4_grave([88.0] * 5)[0], TITLE)
        self.assertEqual(self.vv4_grave([88.0, 50.0, 100.0, 0.0, 0.0]), ("Inspired Architect", 0))
        self.assertNotEqual(self.vv4_grave([88.0, 90.0, 100.0, 0.0, 0.0], age=300)[0], TITLE,
                            "a child's grave keeps the children's epitaph")

    def test_vv4_stock_writer_gives_the_job(self):
        self.assertEqual(self.vv4_grave([88.0, 90.0, 100.0, 0.0, 0.0], start=False), ("Inspired Architect", 0))


@unittest.skipIf(_skip() or not CAUSE_TEST_DLL.is_file(), _skip() or "the Cause of Death test build is missing")
class ANewHomesEpitaph(unittest.TestCase):
    """cod_vv12.inc cod_buried: the Graves file's epitaph for A New Home's grave."""

    STRIDE, HEALTH, AGE, NAME, SKILLS, FAMILY = 0x3D8, 0x344, 0x348, 0x370, 0x3BC, 0x36C

    def grave_epitaph(self, skills, *, elders: bool, age=1200, golden=False) -> int:
        exe = render(1, with_requirements(1, ["vv1_cause_of_death"]), "collection_progression")
        m = Machine(exe, CAUSE_TEST_DLL)
        installed = m.alloc(0x10)
        m.stub(installed, lambda p: (1, 0))

        def module(p):
            return (FAKE_ELDERS if elders and p.cstring(p.arg(0)) == DLL_NAME else 0), 4

        def proc(p):
            return (installed if p.arg(0) == FAKE_ELDERS and p.cstring(p.arg(1)) == "VvfpEsteemedEldersInstalled"
                    else 0), 8
        m.api_handlers["GetModuleHandleA"] = module
        m.api_handlers["GetProcAddress"] = proc
        slot_fn = m.alloc(0x10)
        m.stub(slot_fn, lambda p: (1, 0))
        host = m.alloc(0x10)
        m.put32(host, 8)
        m.put32(host + 4, slot_fn)
        table = m.alloc(0x3E020)
        manager = m.alloc(0xC000)
        m.put32(table + 0x3E010, manager)
        rec = table
        m.write(rec + self.NAME, b"Kalani\0")
        m.put32(rec + self.AGE, age)
        m.put32(rec + self.HEALTH, 0)
        m.put32(rec + self.FAMILY, 0xC7 if golden else 2)
        for k, v in enumerate(skills):
            m.put32(rec + self.SKILLS + 4 * k, v)
        grave = manager + 0xA31C
        m.write(grave, b"Kalani\0")
        m.put32(grave + 0x1C, max(skills))
        m.put32(grave + 0x20, 4)                              # Builder
        m.put32(grave + 0x24, age)
        m.put32(m.exports["VvfpCauseRollTest"], 0)
        self.assertEqual(m.export("VvfpCauseTestSetup", 1, host, table), 1)
        m.export("VvfpCauseTestBuried", 0, 0)
        out = m.alloc(8)
        self.assertEqual(m.export("VvfpCauseTestGrave", 0, out, out + 4), 1)
        return m.u32(out + 4)

    def test_an_adult_elders_grave_gets_epitaph_14_only_with_the_row(self):
        self.assertEqual(self.grave_epitaph([90, 95, 100, 0, 0], elders=True), 14)
        self.assertNotEqual(self.grave_epitaph([90, 95, 100, 0, 0], elders=False), 14, "stock: the job's")
        self.assertNotEqual(self.grave_epitaph([90, 95, 89, 0, 0], elders=True), 14)
        self.assertNotEqual(self.grave_epitaph([90, 95, 100, 0, 0], elders=True, age=300), 14)


if __name__ == "__main__":
    unittest.main()
