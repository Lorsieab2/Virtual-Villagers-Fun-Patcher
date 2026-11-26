"""New Believers: the Deaths log names a Heathen's grave at the mud hut ("VVFP Heathen Mausoleum.dll", W-C).

The Cause of Death companion's TEST build is installed on the stock executable and the game's own burial end runs
(0x473F8F..0x473FB6: the roster writer 0x464C70, its exit hook 0x464E51 and the burial hook 0x473FAE).  The Heathen
Mausoleum companion is stood in for: its routing is the writer called on another table (the burial's `mov ecx,
0x5481A8` pointed at a table of the same layout, as the companion's 0x473FA9 splice does), and its two exports
(VvfpHeathenMausoleumIsHeathenGrave, VvfpHeathenMausoleumInstalled) answer from that table.  The companion itself
is tested in tests/test_vv5_heathen_mausoleum.py.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

try:
    from test_cause_of_death import DEATH, EPITAPH, STOCK, TEST_DLL, later
    HAVE = STOCK["vv5"].is_file() and TEST_DLL.is_file()
except Exception:  # pragma: no cover - environment dependent
    HAVE = False

FAKE_MAUSOLEUM = 0x0B500000
TABLE_BYTES = 0xBB84
FACTION = 0x1CEC
ROSTER_IMM = 0x473FA5            # the burial's `mov ecx, 0x5481A8` (0x473FA4)


def guardians(p) -> None:
    """The Guardians of Isola rewrite, as the running game shows it (native/shared/heathen_word.h): string 0x48 of
    the table at 0x5240A8 says "left the tribe"."""
    text = p.alloc(0x40)
    p.write(text, b"%s has left the tribe.\0")
    entry = p.alloc(0x10)
    p.write(entry, struct.pack("<4I", 0x48, 0, text, 0))
    p.put32(0x5240A8 + 4 * 0x48, entry)


class MudHut:
    def __init__(self):
        self.g, self.w = later("vv5")
        p = self.g.p
        self.table = p.alloc(TABLE_BYTES)
        self.installed = 1
        self.names: dict[int, str] = {}
        p.mu.mem_map(FAKE_MAUSOLEUM, 0x1000)
        stubs = {"VvfpHeathenMausoleumIsHeathenGrave": FAKE_MAUSOLEUM,
                 "VvfpHeathenMausoleumInstalled": FAKE_MAUSOLEUM + 0x10}
        p.stub(FAKE_MAUSOLEUM, lambda proc: (int(self.table <= proc.arg(0) < self.table + 500 * 0x5C
                                                  and (proc.arg(0) - self.table) % 0x5C == 0), 4))
        p.stub(FAKE_MAUSOLEUM + 0x10, lambda proc: (self.installed, 0))
        p.api_handlers["GetModuleHandleA"] = (
            lambda proc: ((0x400000 if proc.arg(0) == 0
                           else FAKE_MAUSOLEUM if proc.cstring(proc.arg(0)) == "VVFP Heathen Mausoleum.dll"
                           else 0), 4))
        get_proc = p.api_handlers["GetProcAddress"]

        def proc_address(proc):
            if proc.arg(0) == FAKE_MAUSOLEUM:
                return stubs.get(proc.cstring(proc.arg(1)), 0), 8
            return get_proc(proc)
        p.api_handlers["GetProcAddress"] = proc_address

    def bury(self, index: int, name: str, *, heathen: bool, age: int = 900, routed: bool | None = None) -> None:
        r = self.w.villager(index, name, age, 0, 2)
        self.names[r] = name
        self.g.p.write(r + FACTION, b"\x01" if heathen else b"\x00")
        routed = heathen if routed is None else routed
        if routed:
            # The companion's routing.  (Set before the burial's code first runs: the emulator keeps code it has
            # translated, so a village routes either every burial or none.)
            self.g.p.put32(ROSTER_IMM, self.table)
        self.w.bury(index)

    def deaths(self) -> list[tuple[str, str]]:
        return [(self.names.get(e["record"]), e["Grave"]) for e in self.g.of_kind(DEATH)]


@unittest.skipIf(not HAVE, "the stock executable or the Cause of Death test build is missing")
class MudHutGraves(unittest.TestCase):
    def test_a_heathens_grave_is_named_the_shrine_to_the_ancestors(self):
        m = MudHut()
        m.bury(1, "Hea", heathen=True)
        self.assertEqual(m.deaths(), [("Hea", "the Shrine to the Ancestors (Untrained)")])
        self.assertEqual(m.g.p.cstring(m.table), "Hea")
        self.assertEqual(m.g.p.u32(0x5481A8 + 0x1C), 0, "nothing in the believers' roster")
        epitaph = m.g.of_kind(DEATH)[0]["Epitaph"]
        self.assertEqual(epitaph, m.g.p.cstring(m.table + 0x38), "the epitaph from the mud hut's own grave")
        b = MudHut()
        b.bury(2, "Bel", heathen=False)
        self.assertEqual(b.deaths(), [("Bel", "Untrained")])
        self.assertEqual(b.g.p.cstring(0x5481A8), "Bel")

    def test_with_guardians_of_isola_it_is_still_the_shrine_to_the_ancestors(self):
        for full in (False, True):
            with self.subTest(full=full):
                m = MudHut()
                guardians(m.g.p)
                if full:
                    for i in range(500):
                        m.g.p.put32(m.table + i * 0x5C + 0x1C, 100)
                m.bury(1, "Hea", heathen=True)
                self.assertEqual(m.deaths(), [("Hea", "no grave (the Shrine to the Ancestors was full)" if full
                                               else "the Shrine to the Ancestors (Untrained)")])
                self.assertEqual(self.died_among_heathens(m), "Isolans",
                                 "the companion really sees the rewrite in this emulation")
        self.assertEqual(self.died_among_heathens(MudHut()), "Heathens", "and without it, the stock wording")

    @staticmethod
    def died_among_heathens(m: "MudHut") -> str:
        """The wording Cause of Death picks by the same Guardians test (heathen_word.h): a Heathen who dies with nothing
        left gets "no grave (died among the Heathens ...)" or "(... the Isolans ...)"."""
        r = m.w.villager(3, "Kai", 640, 80)
        m.g.p.write(r + FACTION, b"\x01")
        m.g.tick()
        m.g.p.write(r + m.w.l["present"], b"\x00")
        m.g.p.export("VvfpCauseDiedAmongHeathens", 5, 3, 2)
        grave = [e["Grave"] for e in m.g.of_kind(DEATH) if e["record"] == r][-1]
        return "Isolans" if "Isolans" in grave else "Heathens" if "Heathens" in grave else grave

    def test_a_full_shrine_is_named_so(self):
        m = MudHut()
        for i in range(500):
            m.g.p.put32(m.table + i * 0x5C + 0x1C, 100)
        m.bury(1, "Late", heathen=True)
        self.assertEqual(m.deaths(), [("Late", "no grave (the Shrine to the Ancestors was full)")])

    def test_without_the_mausoleum_a_full_roster_keeps_its_words(self):
        m = MudHut()
        m.installed = 0
        for i in range(500):
            m.g.p.put32(0x5481A8 + i * 0x5C + 0x1C, 100)
        m.bury(1, "Late", heathen=True, routed=False)
        self.assertEqual(m.deaths()[-1], ("Late", "no grave (the Roster of the Dead was full)"))

    def test_an_epitaph_edited_on_the_heathen_screen_names_the_mud_hut_grave(self):
        m = MudHut()
        m.bury(1, "Elda", heathen=True, age=1500)
        g, p = m.g, m.g.p
        typed = "Rest Well"

        def text(proc):
            p.write(proc.arg(0), typed.encode() + b"\0")
            return 0, 8
        p.stub(0x40D910, text)
        p.stub(0x40E580, lambda proc: (0, 0))
        dialog = p.alloc(0x100)
        p.put32(dialog + 0x50, 7)
        p.put32(dialog + 0x4C, m.table)
        p.call(0x41CB20, [8, 7], ecx=dialog)
        change = g.of_kind(EPITAPH)
        self.assertEqual([(e["Grave"], e["New epitaph"], e["Age at death"]) for e in change],
                         [("the Shrine to the Ancestors (Untrained)", typed, "1500")])
        self.assertEqual(p.cstring(m.table + 0x38), typed)


if __name__ == "__main__":
    unittest.main()
