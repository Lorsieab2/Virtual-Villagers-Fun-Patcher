"""Deaths in the load-time catch-up and in a Time Warp or Time Skip keep their
real cause (all five games).

The owner (2026-10-11): "deaths during catchup should still be recorded" --
A New Home's Death 53, Hiji Temitope (age 1682, old age in a Time Skip), said
"Cause of death: (not recorded: ...)".  His body lay through the save of
20:48:51 and was buried after the village was loaded again.

What the stock executables show (checked below where the research copies
are present):

* Every death of A New Home and The Lost Children in a catch-up passes the
  same hooked sites as a live one.  The catch-up is the aging step's own
  replay loop (A New Home 0x42E900, The Lost Children 0x43B690), which holds
  the old-age, starvation and sickness sites and the removal of an unburied
  body; the live update and the loading screen both call it.  Its job worker
  (0x42E790, 0x43B4D0) completes the jobs through the same callbacks whose
  work injuries are hooked (0x43A230 via 0x446C70; 0x461B10 via 0x464680).
  Time Warp and Choose Time Skip move the clock and the ages and let that same
  loop replay the years.
* The Secret City, The Tree of Life and New Believers keep the cause on the
  record; their catch-up workers bury through the hooked burial (VV3
  0x45BF00 -> 0x45B790 -> 0x461FB0, VV4 0x465750 -> 0x464FA0 -> 0x46A4D0, VV5
  0x46E8E0 -> 0x46E020 -> 0x473B30), and the update that runs the catch-up
  also removes unburied bodies through the hooked removal.

So the sites were not the problem.  A New Home and The Lost Children keep no
cause of their own: the companion keeps each body's, by record, in its graves
file.  The game's load packs the records, and the file was read -- and its
causes moved to the bodies' new records -- only by the per-frame tick, which
runs once a village frame is drawn: after the load-time catch-up and the
village's first updates.  Before it a body from before the load that was
removed or buried had no cause, and a death in the catch-up overwrote the
cause the file kept for another body in that record.  Now every hooked
death, burial and removal first binds the tables to the village being loaded
and moves the causes to their bodies (cod_vv12.inc vv12_sync).

* native/vvfp_cause_of_death/catchup_deaths_harness.c compiles the Cause of
  Death source in with the Documents folder redirected to a throwaway folder
  and plays it per game: two bodies saved, then a new session (slot known at
  the load, or only at the first frame) and a reload in the same session; the
  catch-up kills a villager the load packed into a body's old record, removes
  a body, and a burial runs before the first frame.  Every Death record must
  carry the real cause.  It failed before the fix (A New Home and The Lost
  Children: "(not recorded ...)"), and passes after.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

try:
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs

    HAVE_CAPSTONE = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_CAPSTONE = False

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native" / "vvfp_cause_of_death"
CL = Path(
    r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC"
    r"\14.51.36231\bin\Hostx64\x86\cl.exe"
)
STOCK = ROOT / "research" / "stock-executables"
EXES = {
    1: "Virtual Villagers - A New Home.exe",
    2: "Virtual Villagers - The Lost Children.exe",
    3: "Virtual Villagers - The Secret City.exe",
    4: "Virtual Villagers - The Tree of Life.exe",
    5: "Virtual Villagers - New Believers.exe",
}

# (the call, its target): each a call (or a tail jmp) of the stock code.
CALLS = {
    1: [
        (0x426193, 0x42E900),   # the loading screen runs the aging step (its catch-up)
        (0x42348C, 0x42E900),   # ...and so does the live update
        (0x42F10A, 0x42E790),   # the replay loop's job worker, for each adult
        (0x42E80D, 0x446C70),   # the worker completes the job...
        (0x446DBF, 0x43A230),   # ...through the callbacks whose work injuries are hooked
    ],
    2: [
        (0x431DC3, 0x43B690),
        (0x42EBBC, 0x43B690),
        (0x43BFDD, 0x43B4D0),
        (0x43B55A, 0x464680),
        (0x4647B1, 0x461B10),
    ],
    3: [
        (0x428CA0, 0x45FFE0),   # the update: the aging step (with its catch-up)...
        (0x428C96, 0x45F3E0),   # ...and the removal of unburied bodies
        (0x460568, 0x45BF00),   # the catch-up worker...
        (0x45BF70, 0x45B790),   # ...completes the job...
        (0x45B7CD, 0x461FB0),   # ...through the hooked burial
    ],
    4: [
        (0x420560, 0x468430),
        (0x420556, 0x466450),
        (0x468A60, 0x465750),
        (0x4657BE, 0x464FA0),
        (0x464FDC, 0x46A4D0),
    ],
    5: [
        (0x4260EB, 0x472C90),
        (0x4260E1, 0x46FE90),
        (0x473311, 0x46E8E0),
        (0x46E960, 0x46E020),
        (0x46E05C, 0x473B30),
    ],
}

# Each hooked site of A New Home and The Lost Children inside the aging step
# whose replay loop is the catch-up: [start, end) of the step.
AGING_STEP = {1: (0x42E900, 0x42F31B), 2: (0x43B690, 0x43C288)}


class _Pe:
    def __init__(self, path: Path) -> None:
        import struct

        self.data = path.read_bytes()
        pe = struct.unpack_from("<I", self.data, 0x3C)[0]
        count = struct.unpack_from("<H", self.data, pe + 6)[0]
        optional = struct.unpack_from("<H", self.data, pe + 20)[0]
        base = struct.unpack_from("<I", self.data, pe + 24 + 28)[0]
        self.sections = []
        for i in range(count):
            h = pe + 24 + optional + 40 * i
            vsize, va, rsize, raw = struct.unpack_from("<IIII", self.data, h + 8)
            self.sections.append((base + va, max(vsize, rsize), raw))

    def at(self, va: int, size: int) -> bytes:
        for start, span, raw in self.sections:
            if start <= va < start + span:
                return self.data[raw + va - start: raw + va - start + size]
        raise ValueError(hex(va))

    def first(self, va: int):
        return next(Cs(CS_ARCH_X86, CS_MODE_32).disasm(self.at(va, 16), va))


def _sites(game: int) -> list[tuple[int, str]]:
    """The death sites and the removal cod_vv12.inc hooks for `game`."""
    text = (NATIVE / "cod_vv12.inc").read_text(encoding="utf-8")
    body = text.split("static void vv12_sites(void) {", 1)[1].split("\n}\n", 1)[0]
    part = body.split("} else {", 1)[0 if game == 1 else 1]
    sites = [(int(m.group(1), 16), m.group(2)) for m in re.finditer(r'add_death\(0x([0-9A-F]+)u, "([0-9A-F" ]+)",', part)]
    removal = re.search(r'cod_add\(0x([0-9A-F]+)u, "([0-9A-F]+)", vv%d_decayed\)' % game, part)
    return sites + [(int(removal.group(1), 16), removal.group(2))]


@unittest.skipUnless(HAVE_CAPSTONE, "capstone is not installed")
class TheCatchUpPassesTheHookedSites(unittest.TestCase):
    def test_the_catch_up_reaches_the_hooked_code(self) -> None:
        for game, calls in CALLS.items():
            path = STOCK / EXES[game]
            if not path.is_file():
                continue
            pe = _Pe(path)
            for site, target in calls:
                with self.subTest(game=game, site=hex(site)):
                    ins = pe.first(site)
                    # a call, or the tail call that ends the caller
                    self.assertIn(ins.mnemonic, ("call", "jmp"))
                    self.assertEqual(ins.op_str, hex(target))

    def test_every_aging_death_site_is_in_the_step_the_catch_up_replays(self) -> None:
        for game in (1, 2):
            sites = _sites(game)
            start, end = AGING_STEP[game]
            in_step = [va for va, _ in sites if start <= va < end]
            # old age, the two starvation drains, sickness, the unburied body's removal
            self.assertEqual(len(in_step), 5, (game, [hex(va) for va in in_step]))
            path = STOCK / EXES[game]
            if not path.is_file():
                continue
            pe = _Pe(path)
            for va, stock in sites:
                with self.subTest(game=game, site=hex(va)):
                    raw = bytes.fromhex(stock.replace('"', "").replace(" ", ""))
                    self.assertEqual(pe.at(va, len(raw)), raw)


class EveryEventBindsTheVillageFirst(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (NATIVE / "cod_vv12.inc").read_text(encoding="utf-8")

    def _body(self, signature: str) -> str:
        return self.text.split(signature, 1)[1].split("\n}\n", 1)[0]

    def test_death_burial_and_removal_sync_before_reading_or_writing_a_cause(self) -> None:
        died = self._body("static void cod_died(const unsigned char *record, int cause) {")
        self.assertLess(died.index("vv12_sync(-1);"), died.index("cod_event(&e);"))
        buried = self._body("static void cod_buried(int index, int found, int slot) {")
        self.assertLess(buried.index("vv12_sync(index);"), buried.index("cause = cod_cause_of(record, index);"))
        decayed = self._body("static void cod_decayed(unsigned char *record) {")
        self.assertLess(decayed.index("vv12_sync(-1);"), decayed.index("cause = cod_cause_of(record, index);"))

    def test_the_sync_binds_the_games_slot_and_moves_the_causes(self) -> None:
        sync = self._body("static void vv12_sync(int keep) {")
        self.assertIn("int slot = cod_slot();", sync)
        self.assertIn("cod_bind(slot);", sync)
        self.assertIn("cod_rehome_bodies(records, keep);", sync)

    def test_a_bind_moves_the_files_causes_before_replaying_the_events(self) -> None:
        bind = self._body("static void cod_bind(int slot) {")
        self.assertLess(bind.index("cod_rehome_bodies(records, -1);"), bind.index("cod_apply(e);"))

    def test_the_note_no_longer_blames_the_loading(self) -> None:
        main = (NATIVE / "vvfp_cause_of_death.c").read_text(encoding="utf-8")
        self.assertNotIn("while the village was loading", main)
        self.assertIn('"(not recorded: the villager died while this patch was not watching', main)


@unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
class CatchUpDeathsKeepTheirCause(unittest.TestCase):
    def test_harness(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vvfp_cause_catchup_docs_") as docs:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                 str(ROOT / "scripts" / "build_cause_catchup_harness.ps1"), "-Docs", docs],
                capture_output=True, text=True, timeout=600,
            )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertNotIn("FAIL", output)
        self.assertNotIn("(not recorded", output)
        # A New Home, The Lost Children: write + read twice, and a reload; the later three once each.
        self.assertEqual(output.count("all passed"), 13, output)


if __name__ == "__main__":
    unittest.main()
