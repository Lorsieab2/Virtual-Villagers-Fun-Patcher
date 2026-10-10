"""A New Home's expected father: the father of the child a woman is carrying.

The owner's rule: "VV1-5 will have at a minimum the same information in all of its logs UNLESS A
SPECIFIC GAME LACKS THAT FEATURE."  The Lost Children to New Believers copy the father onto the
mother at conception, so their Village Population log prints him under a pregnant woman and the
Family Tree Maker / Village Matchmaker read him from the save.  A New Home copies nothing onto her,
but the VV1 Parentage companion records him at conception -- in its pregnancy stash, kept in the
Parents (A New Home) sidecar -- so the feature exists and A New Home must show it too:

* the Village Population log prints the same "Father:" / "Head:" / "Body:" block, from the
  companion's Vv1ParentageQueryExpectedFather (the father the birth will record), under the same
  pregnancy gate; a pregnancy with no recorded father prints no block, as the later games print
  none for an empty name;
* the Family Tree Maker and the Village Matchmaker fill the expected father from the mother's last
  Conception record, else from that sidecar (under either folder name), matched to the living
  villager by the identity its roster keeps -- never by record number.

Fixtures are built here; no file outside the repository is read.
"""
from __future__ import annotations

import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_genealogy as gen  # noqa: E402

POPULATION_C = ROOT / "native" / "population_export" / "population_export.c"
PARENTAGE_C = ROOT / "native" / "vv1_parentage" / "vv1_parentage.c"
COMPANION = ROOT / "assets" / "parentage" / "VVFP VV1 Parentage.dll"
POPULATION_DLL = ROOT / "assets" / "population" / "VVFP Population Export.dll"
HARNESS_BUILD = ROOT / "scripts" / "build_population_export_harness.ps1"

LOGS = "Virtual Villagers Fun Patcher Logs"
DATA = "Virtual Villagers Fun Patcher Data"


def _exports(path: Path) -> set[str]:
    pe = pefile.PE(str(path))
    return {e.name.decode() for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}


class PopulationLogTests(unittest.TestCase):
    def test_the_companion_exports_the_expected_father(self):
        self.assertIn("Vv1ParentageQueryExpectedFather", _exports(COMPANION))
        source = PARENTAGE_C.read_text(encoding="utf-8")
        # one rule for the birth and for the log: the birth's father IS the expected father
        self.assertIn("if (vv1_expected_father(m, mother, &father)) {", source)
        self.assertIn("vv1_expected_out(records, index, out, name, capacity);", source)

    def test_the_exporter_asks_for_it_and_prints_the_later_games_block(self):
        source = POPULATION_C.read_text(encoding="utf-8")
        self.assertIn('GetProcAddress(companion, "Vv1ParentageQueryExpectedFather")', source)
        body = source[source.index("static int write_vv1_expected_father("):]
        body = body[:body.index("\n}\n")]
        # the very format VV2-VV5 print from the copy on the mother
        for line in ('"  Father: %s\\n"', '"    Head: %d\\n"', '"    Body: %d\\n"'):
            self.assertIn(line, body)
            self.assertIn(line, source[source.index("The father of the child this villager is CARRYING"):])
        # the pregnancy gate, and only in the roster (never the history)
        self.assertRegex(source, r"with_pregnancy && game_id == GAME_VV1\s*&& g->age_at_conception != 0u")

    def test_the_shipped_exporter_resolves_the_export_by_name(self):
        data = POPULATION_DLL.read_bytes()
        self.assertIn(b"Vv1ParentageQueryExpectedFather", data)


class PopulationHarnessTests(unittest.TestCase):
    """native/population_export/population_export_harness.c, run on the shipped exporter: VV2-VV5 as
    before, and A New Home through a stand-in companion (vv1_parentage_stub.c)."""

    @classmethod
    def setUpClass(cls):
        build = HARNESS_BUILD.read_text(encoding="utf-8")
        vs = Path(re.search(r'\$vsTools = "([^"]+)"', build).group(1))
        if not (vs / "bin" / "Hostx64" / "x86" / "cl.exe").exists():
            raise unittest.SkipTest("MSVC x86 toolchain not installed")
        cls.work = Path(tempfile.mkdtemp())
        cls.result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(HARNESS_BUILD),
             "-OutDir", str(cls.work)],
            capture_output=True, text=True, timeout=600)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "work", ""), ignore_errors=True)

    def test_every_check_passes(self):
        out = self.result.stdout
        self.assertIn("\n0 failure(s)", out, out + self.result.stderr)
        self.assertEqual(self.result.returncode, 0, out + self.result.stderr)

    def test_a_new_home_prints_the_expected_father(self):
        out = self.result.stdout
        for case in (
            "roster: her expected father, head and body, in the later games' shape",
            "roster: no father is printed for a woman not carrying",
            "roster: ...with no Father block, as the later games print none for an unknown father",
            "the history never names an expected father",
        ):
            with self.subTest(case=case):
                self.assertIn("  ok   " + case, out)


# ---------------------------------------------------------------------------
# The Family Tree Maker and the Village Matchmaker
# ---------------------------------------------------------------------------

# name, male, family scalar, head, body, carrying
VILLAGERS = [
    ("Goro", True, 30, 7, 2, False),
    ("Aisha", False, 17, 4, 9, True),
    ("Nina", False, 18, 11, 3, False),
    ("Tadao", True, 44, 6, 0, False),
]


def vv1_save(villagers) -> bytes:
    """A save in A New Home's layout (the records the game keeps: +0x33C..+0x3D4, 0x9C apart)."""
    data = bytearray(0x184 + 256 * 0x9C)
    for i, (name, male, scalar, head, body, carrying) in enumerate(villagers):
        base = 0x184 + i * 0x9C - 0x33C
        struct.pack_into("<i", data, base + 0x350, 1 if male else 2)
        struct.pack_into("<i", data, base + 0x344, 100)       # health: alive
        struct.pack_into("<i", data, base + 0x348, 25 * 20)
        struct.pack_into("<i", data, base + 0x358, 480 if carrying else 0)
        struct.pack_into("<i", data, base + 0x360, head)
        struct.pack_into("<i", data, base + 0x364, body)
        struct.pack_into("<i", data, base + 0x36C, scalar)
        struct.pack_into("<i", data, base + 0x3D4, 1)
        data[base + 0x370:base + 0x370 + len(name)] = name.encode()
    return bytes(data)


def sidecar(roster, stashes: dict[int, tuple], slot: int = 1, looks: bool = True) -> bytes:
    """A VP02 file: `roster` names who holds each record, `stashes[i]` the father (name, head, body)
    stashed against record i at a conception."""
    out = bytearray(struct.pack("<III", 0x32305056, 0, slot))
    for i in range(256):
        rec = bytearray(36)
        if i < len(roster):
            name, male, scalar, head, body, _ = roster[i]
            struct.pack_into("<BBBBi", rec, 0, 1 if male else 2, 0,
                             head + 1 if looks else 0, body + 1 if looks else 0, scalar)
            rec[8:8 + len(name)] = name.encode()
        out += rec
    for i in range(256):
        e = bytearray(92)
        if i in stashes:
            name, head, body = stashes[i]
            e[4], e[5] = head + 1, body + 1
            e[64:64 + len(name)] = name.encode()
        out += e
    return bytes(out)


def conception(mother, father) -> str:
    return "\n".join(["Village: Harness Tribe (Save 1)", "Conception",
                      f"  Mother: {mother[0]}", f"    Head: {mother[3]}", f"    Body: {mother[4]}",
                      f"  Father: {father[0]}", f"    Head: {father[3]}", f"    Body: {father[4]}",
                      "  Babies: 1", ""]) + "\n"


class FamilyTreeTests(unittest.TestCase):
    def build(self, *, stashes=None, folder="Parents (A New Home)", roster=None, log=None, slot=1,
              looks=True) -> Path:
        game = Path(self.enterContext(tempfile.TemporaryDirectory())) / "Virtual Villagers - A New Home"
        (game / LOGS / "Births and Conceptions").mkdir(parents=True)
        (game / DATA / folder).mkdir(parents=True)
        (game / "Virtual Villagers1.ldw").write_bytes(vv1_save(VILLAGERS))
        if log is not None:
            (game / LOGS / "Births and Conceptions" / "Virtual Villagers 1 Births and Conceptions Log 1.txt"
             ).write_text(log, encoding="latin-1")
        if stashes is not None:
            (game / DATA / folder / "Virtual Villagers 1 Parentage Records - Save 1.dat").write_bytes(
                sidecar(roster if roster is not None else VILLAGERS, stashes, slot, looks))
        return game

    def upcoming_father(self, game: Path):
        village = gen.load_village(game, 1, 1)
        babies = [p for p in village.people.values() if p.upcoming]
        self.assertEqual(len(babies), 1, "one baby on the way: Aisha's")
        self.assertEqual(village.people[babies[0].mother].name, "Aisha")
        father = babies[0].father
        return village, (None if father is None else village.people[father].key)

    def test_the_sidecar_names_the_expected_father(self):
        _v, father = self.upcoming_father(self.build(stashes={1: ("Goro", 7, 2)}))
        self.assertEqual(father, ("Goro", 7, 2))

    def test_the_older_folder_name_is_read_too(self):
        _v, father = self.upcoming_father(self.build(stashes={1: ("Goro", 7, 2)}, folder="Parentage Records"))
        self.assertEqual(father, ("Goro", 7, 2))

    def test_the_entry_follows_the_villager_not_the_record_number(self):
        # The sidecar was written when Aisha held record 5 (the game repacks its records on a load).
        roster = [VILLAGERS[0], VILLAGERS[2], VILLAGERS[3], ("Hawa", False, 50, 2, 19, False),
                  ("Kito", True, 19, 0, 18, False), VILLAGERS[1]]
        _v, father = self.upcoming_father(self.build(stashes={5: ("Tadao", 6, 0)}, roster=roster))
        self.assertEqual(father, ("Tadao", 6, 0), "head 0 / body 0 is a real father")

    def test_an_older_roster_without_looks_still_binds_by_name_sex_and_family(self):
        _v, father = self.upcoming_father(self.build(stashes={1: ("Goro", 7, 2)}, looks=False))
        self.assertEqual(father, ("Goro", 7, 2))

    def test_the_last_conception_record_comes_first(self):
        # The companion's own rule (vv1_expected_father): the Births log's record of the
        # conception -- written with the save -- over a stash that may be ahead of the save.
        log = conception(VILLAGERS[1], VILLAGERS[3])
        _v, father = self.upcoming_father(self.build(stashes={1: ("Goro", 7, 2)}, log=log))
        self.assertEqual(father, ("Tadao", 6, 0))

    def test_another_village_or_slot_or_no_record_gives_no_father(self):
        strangers = [("Penyo", False, 50, 8, 15, False), ("Kaimi", False, 39, 5, 16, False)]
        for kwargs in ({"stashes": {1: ("Goro", 7, 2)}, "roster": strangers},   # Start Over in the slot
                       {"stashes": {1: ("Goro", 7, 2)}, "slot": 2},              # another slot's file
                       {"stashes": {}},                                          # no conception recorded
                       {}):                                                      # no sidecar at all
            with self.subTest(**{k: str(v) for k, v in kwargs.items()}):
                _v, father = self.upcoming_father(self.build(**kwargs))
                self.assertIsNone(father)

    def test_an_identity_two_villagers_share_is_nobodys(self):
        roster = [VILLAGERS[0], VILLAGERS[1], VILLAGERS[2], VILLAGERS[3], VILLAGERS[1]]
        _v, father = self.upcoming_father(self.build(stashes={1: ("Goro", 7, 2), 4: ("Tadao", 6, 0)},
                                                     roster=roster))
        self.assertIsNone(father, "two entries fit Aisha: left unknown rather than guessed")

    def test_the_matchmaker_sees_the_baby_on_the_way(self):
        village, _father = self.upcoming_father(self.build(stashes={1: ("Goro", 7, 2)}))
        rules = gen.Rules(close_in_age=False, no_shared_ancestors=False, max_relatedness=False,
                          different_last_name=False, prefer_fresh_blood=False, one_family_per_partner=False,
                          not_expecting=False)
        _pairs, every, _least = gen.suggest(village, rules)
        aisha = next(p for p in village.people.values() if p.name == "Aisha")
        together = {pair.man.name: pair.expected for pair in every[aisha.id]}
        self.assertEqual(together["Goro"], 1)
        self.assertEqual(together["Tadao"], 0)
        self.assertIn("a baby on the way together",
                      next(pair for pair in every[aisha.id] if pair.man.name == "Goro").together)
        # and "Not already expecting" leaves her out
        self.assertNotIn(aisha, gen.candidates(village, gen.Rules(not_expecting=True))[1])


if __name__ == "__main__":
    unittest.main()
