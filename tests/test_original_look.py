"""The original looks behind Change Appearance's "Reset to original", all five games ("VVFP Original Look.dll",
native/vvfp_original_look; src/vv_original_look.py; the owner, 2026-10-28).

THE STORE, by native/vvfp_original_look/original_look_harness.c on real files (the real games' record
layouts): recording at first sight (the first run over an existing save, a birth, a record named late);
an original never written over (a later change, a later session, the Origins companion not loaded yet);
following the villager (a death in play, a packed reload, a death the file missed, a reused record, a
rename); an identity two villagers share never recorded; the logs' part over a first-run snapshot, never
over a seen one, a "not known" stopping any first sight; corrupt and missing files; another village's file
(a copied save, the title screen's seeded records) never replaced on what is on screen alone; a roster
that never holds still never bound; Start Over; a failed write; 256 records; every game's layout.

THE BACKFILL, here on the repository's fixture saves with logs written beside them: the earliest
"Appearance changed" record wins, followed back from the save's look; no guessing (a change seen with no
record, a mask not recorded, an off-chain record of a unique name, one record on two villagers' ways,
namesakes of one identity); the island event's mask; idempotent; a file it cannot read is never written
over; the DLL's record entries are kept byte for byte; Repair Saves & Logs runs it.

THE CONTRACT: the identity and checksum the Python side computes are the DLL's (the harness prints them);
a file the DLL wrote is read here, and one written here is read by the DLL's own store; the export and the
header; the DLL writes nothing into any game (emulated on each stock executable); the row, the startup
list, FILES and the pins.

The live effect in a running game is NOT verified here.
"""
from __future__ import annotations

import functools
import gzip
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402
import vv_log_tools as tools  # noqa: E402
import vv_original_look as ol  # noqa: E402
import vv_tribe_rename as rename  # noqa: E402

try:
    import pefile  # noqa: F401
    from story_emulator import Process

    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False
    Process = object

DLL_NAME = "VVFP Original Look.dll"
DLL = ROOT / "assets" / "original_look" / DLL_NAME
FIXTURES = ROOT / "tests" / "fixtures" / "rename_tribe"
HARNESS = ROOT / "scripts" / "build_original_look_harness.ps1"
LOGS = "Virtual Villagers Fun Patcher Logs"


def _run_harness(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(HARNESS), *args],
                          capture_output=True, text=True, timeout=600)


@functools.lru_cache(maxsize=None)
def harness(*args: str) -> str:
    result = _run_harness(*args)
    out = result.stdout + result.stderr
    if result.returncode != 0 and "cl.exe" in out and "not recognized" in out:
        raise unittest.SkipTest("the compiler is not installed")
    if result.returncode != 0:
        raise AssertionError(out[-4000:])
    return result.stdout


# ---------------------------------------------------------------------------------------------------
# The store, on real files
# ---------------------------------------------------------------------------------------------------

class TheStore(unittest.TestCase):
    def test_the_harness_passes(self):
        out = harness()
        self.assertIn("failures: 0", out)
        self.assertNotIn("[FAIL]", out)
        self.assertGreaterEqual(out.count("[PASS]"), 75)
        for proven in ("everyone's look is recorded at first sight", "a birth in play is recorded as SEEN",
                       "Change Appearance afterwards: the original stays",
                       "after the reload Kai3's original is on Kai3 in record 2",
                       "a newborn in a dead villager's record is seen as themselves",
                       "a renamed villager keeps the original", "never recorded for either",
                       "the logs' original takes over a first-run snapshot",
                       "a SEEN original is never replaced by the logs",
                       "...is set aside intact, never read or overwritten",
                       "the slot's own file is never touched while another village is on screen",
                       "Start Over deletes the slot's Original Looks file",
                       "a write that fails leaves the file as it was"):
            self.assertIn(f"[PASS] {proven}", out)


# ---------------------------------------------------------------------------------------------------
# The contract between the DLL and the Python side
# ---------------------------------------------------------------------------------------------------

class TheContract(unittest.TestCase):
    def test_the_identity_and_checksum_are_the_dlls(self):
        out = harness("identities")
        lines = re.findall(r"^IDENTITY (\d) (\d) (\d+) (\d+)$", out, re.M)
        self.assertEqual(len(lines), 15)
        made = {
            0: (b"Kai", 1, b"Aru", b"Malia"),
            1: (b"Leilani Kahale", 0, b"", b""),
            2: (b"Ana", 0, b"Kaimana Alohilani", b"Pua"),
        }
        for game, k, ident, stable in lines:
            game, k = int(game), int(k)
            name, sex, father, mother = made[k]
            family = struct.pack("<i", 7 if (game == 1 and k == 0) else 0)
            with self.subTest(game=game, record=k):
                self.assertEqual(ol.identity(game, name, struct.pack("<i", sex), father, mother, family),
                                 (int(ident), int(stable)))
        self.assertEqual(int(re.search(r"^CRC (\d+)$", out, re.M).group(1)), zlib.crc32(b"123456789"))

    def test_a_file_the_dll_wrote_is_read_here(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "written.dat"
            harness("write", str(out))
            looks = ol.parse(out.read_bytes(), 5)
        self.assertIsNotNone(looks)
        self.assertEqual(looks.count, 150)
        self.assertEqual(looks.logged, [])
        for i in range(10):
            ident = ol.identity(5, f"Kai{i}".encode(), struct.pack("<i", i & 1))[0]
            e = looks.entries[i]
            with self.subTest(record=i):
                self.assertEqual((e.roster, e.id, e.head, e.body, e.source), (ident, ident, i % 20, i % 10, ol.FIRST_RUN))
                self.assertEqual(e.mask, 3 if i == 4 else 0)
        baby = looks.entries[10]
        self.assertEqual((baby.head, baby.body, baby.source), (7, 3, ol.SEEN))
        self.assertEqual(baby.id, ol.identity(5, b"Baby", struct.pack("<i", 0), b"Kai0", b"Kai1")[0])
        self.assertTrue(all(e.source == 0 and e.roster == 0 for e in looks.entries[11:]))

    def test_a_file_written_here_is_read_by_the_dlls_store(self):
        ids = [ol.identity(5, f"Kai{i}".encode(), struct.pack("<i", i & 1))[0] for i in range(10)]
        entries = [ol.Entry() for _ in range(150)]
        for i, ident in enumerate(ids):
            entries[i].roster = ident
        looks = ol.OriginalLooks(5, entries, [ol.Logged(ids[3], 3, 3, 0, ol.KNOWN), ol.Logged(ids[5], 0, 0, 0, ol.UNKNOWN)])
        with tempfile.TemporaryDirectory() as d:
            made = Path(d) / "python.dat"
            made.write_bytes(ol.build(looks))
            out = harness("read", str(made))
        got = {int(i): (int(o), int(s)) for i, o, s in re.findall(r"^ORIGINAL (\d+) (-?\d+) (\d+)$", out, re.M)}
        self.assertEqual(got[3], (30030, ol.LOGS), "Kai3, changed since, gets the logs' original")
        self.assertEqual(got[5], (-1, 0), "Kai5's original is not known: nothing recorded")
        self.assertEqual(got[4], (40043, ol.FIRST_RUN), "everyone else is seen as they are now")
        self.assertEqual(got[0], (0, ol.FIRST_RUN))

    def test_the_header(self):
        text = (ROOT / "native" / "shared" / "original_look.h").read_text(encoding="utf-8")
        self.assertIn('#define VVFP_ORIGINAL_LOOK_DLL "VVFP Original Look.dll"', text)
        self.assertIn('#define VVFP_ORIGINAL_LOOK_GET "VvfpOriginalLookGet"', text)
        self.assertIn("typedef int (__stdcall *vvfp_original_look_get_fn)(int game, const void *record, int *head, "
                      "int *body, int *mask);", text)
        self.assertIn("static vvfp_original_look_get_fn vvfp_original_look_find(void)", text)
        self.assertIn("GetModuleHandleA(VVFP_ORIGINAL_LOOK_DLL)", text)
        for game in ("A New Home", "The Lost Children", "The Secret City", "The Tree of Life", "New Believers"):
            self.assertIn(game, text, "the header says where each game's mask comes from")

    def test_the_export(self):
        names = {e.name.decode(): e.ordinal for e in pefile.PE(str(DLL)).DIRECTORY_ENTRY_EXPORT.symbols} \
            if HAVE_EMULATOR else None
        if names is None:
            self.skipTest("pefile is not installed")
        self.assertEqual(set(names), {"VvfpStartup", "VvfpOriginalLookGet"})
        source = (ROOT / "native" / "vvfp_original_look" / "vvfp_original_look.c").read_text(encoding="utf-8")
        self.assertIn("int __stdcall VvfpOriginalLookGet(int game, const void *record, int *head, int *body, "
                      "int *mask)", source)
        self.assertIn("VvfpOriginalLookGet=_VvfpOriginalLookGet@20",
                      (ROOT / "native" / "vvfp_original_look" / "vvfp_original_look.def").read_text(encoding="utf-8"))

    def test_the_layout_is_the_head_looks(self):
        """The identity an original is kept by is the head look's: the same record fields."""
        def table(path: Path, name: str) -> list[list[str]]:
            text = path.read_text(encoding="utf-8")
            body = text[text.index(f"{name}[6] = {{"):]
            body = body[:body.index("};")]
            return [re.findall(r"0x[0-9A-F]+u|0u", row) for row in re.findall(r"\{([^{}]*)\}", body)[1:]]
        mine = table(ROOT / "native" / "vvfp_original_look" / "original_look_records.inc", "LAYOUT")
        theirs = table(ROOT / "native" / "vvfp_head_look" / "vvfp_head_look.c", "LAYOUT")
        self.assertEqual(len(mine), 5)
        for game, (a, b) in enumerate(zip(mine, theirs), 1):
            with self.subTest(game=game):
                self.assertEqual(a[:8], b[:8], "stride, presence, name, name bytes, sex, father, mother, family")


# ---------------------------------------------------------------------------------------------------
# The backfill from the logs
# ---------------------------------------------------------------------------------------------------

def fixture(game: int) -> bytes:
    return gzip.decompress((FIXTURES / f"vv{game}-huttest-1.ldw.gz").read_bytes())


class Village:
    """Save 1 of one game from the repository's fixture, and the logs written beside it."""

    def __init__(self, root: Path, game: int):
        self.game = game
        saves = rename.GAMES[game - 1]
        self.folder = root / "LDW" / f"{saves.title} - Test"
        self.folder.mkdir(parents=True)
        data = fixture(game)
        (self.folder / f"{tools.load_checker().SAVE_STEMS[game]}1.ldw").write_bytes(data)
        self.header = rename.village_header(rename.save_name(saves, data), 1)
        self.people = ol.living(self.folder, game, 1)

    def log(self, sub: str, name: str, text: str) -> None:
        path = self.folder / LOGS / "Save 1" / sub / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"{self.header}\n{text}".replace("\n", "\r\n").encode("latin-1"))

    def births(self, text: str, number: int = 1) -> None:
        self.log("Births and Conceptions", f"Virtual Villagers {self.game} Births and Conceptions Log {number}.txt",
                 text)

    def events(self, text: str) -> None:
        self.log("Island Events", f"Virtual Villagers {self.game} Island Events Log 1.txt", text)

    def file(self) -> ol.OriginalLooks | None:
        path = ol.path(self.folder, 1)
        return ol.parse(path.read_bytes(), self.game) if path.is_file() else None

    def logged(self) -> dict[str, ol.Logged]:
        looks = self.file()
        by_id = {e.id: e for e in looks.logged} if looks else {}
        return {v.seen.name: by_id[v.id] for v in self.people if v.id in by_id}


def change(name: str, old: tuple[int, int], new: tuple[int, int], masks: tuple[str, str] | None = None) -> str:
    masked = f"  Old mask: {masks[0]}\n  New mask: {masks[1]}\n" if masks else ""
    return (f"Appearance changed\n  Name: {name}\n  Old head: {old[0]}\n  Old body: {old[1]}\n"
            f"  New head: {new[0]}\n  New body: {new[1]}\n{masked}\n")


def birth(number: int, name: str, sex: str, looks: tuple[int, int], mask: str | None = None) -> str:
    masked = f"    Mask: {mask}\n" if mask else ""
    return (f"Birth {number}\n  Child: {name}\n    Sex: {sex}\n    Head: {looks[0]}\n    Body: {looks[1]}\n{masked}"
            "  Mother: (unknown)\n  Father: (unknown)\n\n")


def arrived(number: int, name: str, sex: str, looks: tuple[int, int], mask: str | None = None) -> str:
    masked = f"  Mask: {mask}\n" if mask else ""
    return f"Arrived {number}\n  Name: {name}\n  Sex: {sex}\n  Head: {looks[0]}\n  Body: {looks[1]}\n{masked}\n"


class Backfill(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def village(self, game: int) -> Village:
        v = Village(self.root / f"g{game}", game)
        self.assertGreaterEqual(len(v.people), 6)
        return v

    def test_the_earliest_record_wins_in_every_game(self):
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                v = self.village(game)
                a = v.people[0].seen
                now = (a.head, a.body)
                v.births(birth(1, a.name, a.sex, (40, 41)) + change(a.name, (40, 41), (42, 43)), 1)
                v.births(change(a.name, (42, 43), (44, 45)) + change(a.name, (44, 45), now), 2)
                result = ol.backfill(v.folder, game, 1)
                self.assertTrue(result.written)
                got = v.logged()[a.name]
                self.assertEqual((got.head, got.body, got.mask, got.kind), (40, 41, 0, ol.KNOWN))

    def test_numbered_logs_are_read_in_number_order(self):
        v = self.village(5)
        a = v.people[0].seen
        v.births(birth(1, a.name, a.sex, (1, 2)) + change(a.name, (1, 2), (3, 4)), 2)
        v.births(change(a.name, (3, 4), (a.head, a.body)), 10)
        ol.backfill(v.folder, 5, 1)
        self.assertEqual((v.logged()[a.name].head, v.logged()[a.name].body), (1, 2))

    def test_no_guessing(self):
        v = self.village(4)
        p = [x.seen for x in v.people]
        # p0: a change seen with no record (their Birth says other looks): not known.
        text = birth(1, p[0].name, p[0].sex, (p[0].head + 1, p[0].body))
        # p1: changes recorded, but no record of them that says their mask: not known.
        text += change(p[1].name, (50, 51), (p[1].head, p[1].body))
        # p2: nothing recorded at all: nothing (the DLL's first sight is right for them).
        # p3: a recorded change, its own Arrived record and an island event's mask: known, that mask.
        text += arrived(1, p[3].name, p[3].sex, (60, 61)) + change(p[3].name, (60, 61), (p[3].head, p[3].body))
        # p4: a record of their (unique) name off their way: not known.
        text += birth(2, p[4].name, p[4].sex, (70, 71)) + change(p[4].name, (70, 71), (p[4].head, p[4].body))
        text += change(p[4].name, (90, 91), (92, 93))
        v.births(text)
        v.events(f"Island event 1\n  Name: {p[3].name}\n  Mask: Red Mask -> none\n\n")
        result = ol.backfill(v.folder, 4, 1)
        got = v.logged()
        self.assertEqual(got[p[0].name].kind, ol.UNKNOWN)
        self.assertEqual(got[p[1].name].kind, ol.UNKNOWN)
        self.assertNotIn(p[2].name, got)
        self.assertEqual((got[p[3].name].kind, got[p[3].name].head, got[p[3].name].body, got[p[3].name].mask),
                         (ol.KNOWN, 60, 61, 3))
        self.assertEqual(got[p[4].name].kind, ol.UNKNOWN)
        self.assertEqual((result.known, result.unknown), (1, 3))

    def test_an_island_events_change_with_no_appearance_record_is_not_known(self):
        v = self.village(3)
        a, b = v.people[0].seen, v.people[1].seen
        v.births(birth(1, a.name, a.sex, (5, 5)) + change(a.name, (5, 5), (a.head, a.body))
                 + birth(2, b.name, b.sex, (b.head, b.body)))
        v.events(f"Island event 1\n  Name: {a.name}\n  Head: 1 -> 5\n\n"
                 f"Island event 2\n  Name: {b.name}\n  Body: 3 -> {b.body}\n\n")
        ol.backfill(v.folder, 3, 1)
        got = v.logged()
        self.assertEqual(got[a.name].kind, ol.UNKNOWN, "an earlier change no Appearance changed record has")
        self.assertEqual(got[b.name].kind, ol.UNKNOWN, "a change seen, and no record of it at all")

    def test_new_believers_masks_in_the_logs_are_never_taken(self):
        """New Believers' logs name a Heathen's own mask and the patcher's cosmetic one alike."""
        v = self.village(5)
        a, b = v.people[0].seen, v.people[1].seen
        v.births(birth(1, a.name, a.sex, (5, 5), mask="Blue Mask") + change(a.name, (5, 5), (a.head, a.body))
                 + birth(2, b.name, b.sex, (6, 6)) + change(b.name, (6, 6), (b.head, b.body)))
        ol.backfill(v.folder, 5, 1)
        got = v.logged()
        self.assertEqual(got[a.name].kind, ol.UNKNOWN)
        self.assertEqual((got[b.name].kind, got[b.name].head, got[b.name].body, got[b.name].mask), (ol.KNOWN, 6, 6, 0))

    def test_the_mask_in_the_record_itself_is_used_in_every_game(self):
        """Every "Appearance changed" record carries the mask before and after since 2026-10-28; its "Old
        mask" is Change Appearance's own store, so New Believers takes it too."""
        for game in (2, 5):
            with self.subTest(game=game):
                v = self.village(game)
                a, b = v.people[0].seen, v.people[1].seen
                v.births(birth(1, a.name, a.sex, (5, 5)) + change(a.name, (5, 5), (5, 5), ("Red Mask", "none"))
                         + change(a.name, (5, 5), (a.head, a.body), ("none", "none"))
                         + birth(2, b.name, b.sex, (6, 6)) + change(b.name, (6, 6), (b.head, b.body)))
                ol.backfill(v.folder, game, 1)
                got = v.logged()
                self.assertEqual((got[a.name].kind, got[a.name].head, got[a.name].body, got[a.name].mask),
                                 (ol.KNOWN, 5, 5, 3), "a mask-only record is on the way; its Old mask wins")
                self.assertEqual((got[b.name].kind, got[b.name].mask), (ol.KNOWN, 0),
                                 "an older record without mask lines still reads (the Birth record's mask)")

    def test_the_secret_citys_robe_is_kept(self):
        import vv_last_names as ln
        v = self.village(3)
        a, b = v.people[0].seen, v.people[1].seen
        save = v.folder / f"{tools.load_checker().SAVE_STEMS[3]}1.ldw"
        data = bytearray(save.read_bytes())
        f = ln.FIELDS[3]
        struct.pack_into("<i", data, a.at + f.body, 29)
        data[a.at + ol.VV3_CHIEF_FROM_NAME] = 1
        save.write_bytes(bytes(data))
        v.people = ol.living(v.folder, 3, 1)
        self.assertTrue(v.people[0].robed and not v.people[1].robed)
        # Changed by Change Appearance (logged), then robed by the game (no record).
        v.births(birth(1, a.name, a.sex, (4, 7)) + change(a.name, (4, 7), (a.head, 9))
                 + birth(2, b.name, b.sex, (b.head, 7)) + change(b.name, (b.head, 7), (b.head, b.body)))
        ol.backfill(v.folder, 3, 1)
        got = v.logged()
        self.assertEqual((got[a.name].kind, got[a.name].head, got[a.name].body), (ol.KNOWN, 4, 29),
                         "the robed chief's original: the head before Change Appearance, the robe")
        self.assertEqual((got[b.name].kind, got[b.name].body), (ol.KNOWN, 7), "anyone else: as before")

    def test_one_record_on_two_ways_is_never_given_to_either(self):
        import vv_last_names as ln
        v = self.village(5)
        a, b = v.people[0].seen, v.people[1].seen
        # Two living villagers who look alike now and were both called "Twin" before: the one record of that
        # name leads back from both.
        save = v.folder / f"{tools.load_checker().SAVE_STEMS[5]}1.ldw"
        data = bytearray(save.read_bytes())
        f = ln.FIELDS[5]
        struct.pack_into("<ii", data, b.at + f.head, a.head, a.body)
        save.write_bytes(bytes(data))
        v.people = ol.living(v.folder, 5, 1)
        v.births(birth(1, a.name, a.sex, (9, 9)) + birth(2, b.name, b.sex, (9, 9))
                 + f"Name changed\n  Name: {a.name}\n  Old name: Twin\n\nName changed\n  Name: {b.name}\n  Old name: Twin\n\n"
                 + change("Twin", (9, 9), (a.head, a.body)))
        ol.backfill(v.folder, 5, 1)
        got = v.logged()
        self.assertEqual(got[a.name].kind, ol.UNKNOWN)
        self.assertEqual(got[b.name].kind, ol.UNKNOWN)
    def test_idempotent(self):
        v = self.village(3)
        a = v.people[2].seen
        v.births(birth(1, a.name, a.sex, (5, 6)) + change(a.name, (5, 6), (a.head, a.body)))
        first = ol.backfill(v.folder, 3, 1)
        data = ol.path(v.folder, 1).read_bytes()
        second = ol.backfill(v.folder, 3, 1)
        self.assertTrue(first.written)
        self.assertFalse(second.written)
        self.assertEqual(ol.path(v.folder, 1).read_bytes(), data)

    def test_the_dlls_entries_are_kept_byte_for_byte(self):
        v = self.village(4)
        a = v.people[1].seen
        entries = [ol.Entry() for _ in range(150)]
        for x in v.people:
            entries[x.seen.record].roster = x.id
        entries[0] = ol.Entry(v.people[0].id, v.people[0].id, 7, 8, 2, ol.SEEN)
        entries[1] = ol.Entry(v.people[1].id, v.people[1].id, a.head, a.body, 0, ol.FIRST_RUN)
        path = ol.path(v.folder, 1)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(ol.build(ol.OriginalLooks(4, entries)))
        v.births(birth(1, a.name, a.sex, (3, 3)) + change(a.name, (3, 3), (a.head, a.body)))
        self.assertTrue(ol.backfill(v.folder, 4, 1).written)
        looks = v.file()
        self.assertEqual(looks.entries, entries, "the record entries are the DLL's, untouched")
        self.assertEqual([(e.head, e.body, e.kind) for e in looks.logged], [(3, 3, ol.KNOWN)])

    def test_a_file_it_cannot_read_is_never_written_over(self):
        v = self.village(2)
        a = v.people[0].seen
        v.births(birth(1, a.name, a.sex, (3, 3)) + change(a.name, (3, 3), (a.head, a.body)))
        path = ol.path(v.folder, 1)
        path.parent.mkdir(parents=True, exist_ok=True)
        for bad in (b"VOL1 broken", ol.build(ol.OriginalLooks(2, [ol.Entry() for _ in range(256)]))[:-1] + b"\0"):
            with self.subTest(bad=bad[:8]):
                path.write_bytes(bad)
                result = ol.backfill(v.folder, 2, 1)
                self.assertFalse(result.written)
                self.assertEqual(path.read_bytes(), bad)
                self.assertIn("could not be read", result.note)

    def test_a_new_file_names_the_saves_living_by_their_records(self):
        v = self.village(1)
        a = v.people[0].seen
        v.births(birth(1, a.name, a.sex, (3, 3)) + change(a.name, (3, 3), (a.head, a.body)))
        self.assertTrue(ol.backfill(v.folder, 1, 1).written)
        looks = v.file()
        self.assertEqual(looks.count, 256)
        for x in v.people:
            self.assertEqual(looks.entries[x.seen.record].roster, x.id)
        self.assertTrue(all(e.source == 0 and e.id == 0 for e in looks.entries))
        self.assertEqual(ol.path(v.folder, 1).relative_to(v.folder).parts[:4],
                         ("Virtual Villagers Fun Patcher", "Save 1", "Data", "Original Looks"))

    def test_nothing_to_add_writes_no_file(self):
        v = self.village(5)
        result = ol.backfill(v.folder, 5, 1)
        self.assertFalse(result.written)
        self.assertFalse(ol.path(v.folder, 1).exists())

    def test_repair_saves_and_logs_runs_it(self):
        class NoGame:
            def find(self, exe_name):
                return []

        v = self.village(5)
        a = v.people[0].seen
        v.births(birth(1, a.name, a.sex, (3, 3)) + change(a.name, (3, 3), (a.head, a.body)))
        result = tools.approve_repair(v.folder, 5, 1, NoGame(), chosen=set())
        self.assertTrue(result.originals.written)
        self.assertEqual(v.logged()[a.name].kind, ol.KNOWN)
        self.assertIsNotNone(result.backup, "the backup made before the repair is kept: a file changed")


# ---------------------------------------------------------------------------------------------------
# Mask-only changes are logged ("Appearance changed" with "Old mask" / "New mask")
# ---------------------------------------------------------------------------------------------------

LOGGER = r'''
#include <windows.h>
#include <stdio.h>
#include "patcher_files.h"
static char g_text[512];
static int g_calls;
static int __stdcall fake_write(int game, int kind, const void *record, int detail, const char *before,
                                const char *after, int flags) {
    (void)game; (void)record; (void)detail; (void)after; (void)flags;
    ++g_calls;
    _snprintf(g_text, sizeof g_text, "%d|%s", kind, before);
    return 1;
}
static HMODULE fake_load(const char *name) { (void)name; return (HMODULE)(UINT_PTR)0x1000; }
static HMODULE WINAPI fake_module(LPCSTR name) { (void)name; return NULL; }
static FARPROC WINAPI fake_proc(HMODULE m, LPCSTR name) { (void)m; (void)name; return (FARPROC)fake_write; }
#define vvfp_load_patcher_dll fake_load
#define GetModuleHandleA fake_module
#define GetProcAddress fake_proc
#include "appearance_log.h"
int main(void) {
    static unsigned char record[16];
    vv_log_appearance_mask(3, record, 4, 5, 0, 4, 5, 3);
    printf("MASKONLY %d [%s]\n", g_calls, g_text);
    vv_log_appearance_mask(3, record, 4, 5, 2, 6, 7, 2);
    printf("BOTH %d [%s]\n", g_calls, g_text);
    vv_log_appearance_mask(3, record, 4, 5, 2, 4, 5, 2);
    printf("NOTHING %d\n", g_calls);
    vv_log_appearance_mask(3, record, 1, 2, -1, 3, 4, -1);
    printf("OLD %d [%s]\n", g_calls, g_text);
    vv_log_appearance_mask(3, record, 1, 2, -1, 1, 2, -1);
    printf("OLDNOTHING %d\n", g_calls);
    return 0;
}
'''


@functools.lru_cache(maxsize=None)
def logger_output() -> str:
    script = ROOT / "scripts" / "build_head_look_harness.ps1"
    text = script.read_text(encoding="utf-8")
    tools_dir = re.search(r'\$vsTools = "([^"]+)"', text).group(1)
    sdk = re.search(r'\$sdkRoot = "([^"]+)"', text).group(1)
    version = re.search(r'\$sdkVersion = "([^"]+)"', text).group(1)
    cl = Path(tools_dir) / "bin" / "Hostx64" / "x86" / "cl.exe"
    if not cl.is_file():
        raise unittest.SkipTest("the compiler is not installed")
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "logger.c"
        src.write_text(LOGGER, encoding="utf-8")
        exe = Path(d) / "logger.exe"
        result = subprocess.run(
            [str(cl), "/nologo", "/W4", f"/Fo{d}\\", "/I", str(ROOT / "native" / "shared"),
             "/I", str(Path(tools_dir) / "include"), "/I", f"{sdk}\\Include\\{version}\\um",
             "/I", f"{sdk}\\Include\\{version}\\shared", "/I", f"{sdk}\\Include\\{version}\\ucrt", str(src),
             "/link", f"/LIBPATH:{Path(tools_dir) / 'lib' / 'x86'}", f"/LIBPATH:{sdk}\\Lib\\{version}\\um\\x86",
             f"/LIBPATH:{sdk}\\Lib\\{version}\\ucrt\\x86", "user32.lib", "shell32.lib", f"/OUT:{exe}"],
            capture_output=True, text=True, timeout=300, cwd=d)
        if result.returncode != 0:
            raise AssertionError(result.stdout[-3000:] + result.stderr[-2000:])
        return subprocess.run([str(exe)], capture_output=True, text=True, timeout=60).stdout


class MaskOnlyChangesAreLogged(unittest.TestCase):
    def test_the_writer(self):
        out = logger_output()
        self.assertIn("MASKONLY 1 [7|  Old head: 4\n  Old body: 5\n  New head: 4\n  New body: 5\n  Old mask: none\n"
                      "  New mask: Red Mask\n]", out)
        self.assertIn("BOTH 2 [7|  Old head: 4\n  Old body: 5\n  New head: 6\n  New body: 7\n  Old mask: Orange Mask\n"
                      "  New mask: Orange Mask\n]", out)
        self.assertIn("NOTHING 2", out, "nothing changed: nothing logged")
        self.assertIn("OLD 3 [7|  Old head: 1\n  Old body: 2\n  New head: 3\n  New body: 4\n]", out,
                      "masks not known (-1): the head and body alone, no mask lines")
        self.assertIn("OLDNOTHING 3", out)

    def test_the_parentage_exporter_still_reads_the_four_look_lines_first(self):
        export = (ROOT / "native" / "parentage_export" / "parentage_export.c").read_text(encoding="utf-8")
        self.assertIn('"  Old head: %d\\n  Old body: %d\\n  New head: %d\\n  New body: %d"', export)

    def test_the_readers_take_a_mask_only_record_for_no_change_of_look(self):
        import vv_genealogy as gen
        import vv_log_additions as additions
        root = Path(tempfile.mkdtemp())
        try:
            v = Village(root, 4)
            a = v.people[0].seen
            v.births(change(a.name, (a.head, a.body), (a.head, a.body), ("none", "Blue Mask"))
                     + change(a.name, (1, 1), (a.head, a.body)))
            reg = gen._Registry()
            gen._appearance_changes(reg, v.folder, 4, 1)
            self.assertNotIn((a.name, a.head, a.body), reg.relooked, "the tree draws the same look")
            self.assertEqual(reg.relooked.get((a.name, 1, 1)), (a.name, a.head, a.body))
            self.assertEqual(additions.plan_appearance(v.folder, 4, 1).id, "appearance", "the Repair plan reads it")
        finally:
            shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------------------------------
# The DLL in each game, and how it ships
# ---------------------------------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def _builds():
    return {b.id: b for b in patcher.load_builds()}


def stock_path(game: int) -> Path:
    return ROOT / "inputs" / f"vv{game}-stock-copy" / _builds()[f"vv{game}"].input_name


# THE GAME'S OWN WRITERS of a villager's head or body in each stock executable (the owner, 2026-10-28: "Keep
# game changes"), every store to the record's head or body field -- directly, or through the record's
# +0xDC4 / +0x1B8C block -- found by reading every instruction (the scan in test_every_writer_is_accounted_for),
# and what each is.  Only GAME's are spliced (their body is folded into the original); CREATION is seen at
# first sight; ISLAND events are Reset's to undo.
CREATION, ISLAND, GAME, NOT_A_RECORD = "creation", "island event", "game", "not a villager record"
GAME_WRITERS = {
    1: {0x41C1F1: CREATION, 0x41C214: CREATION, 0x41C22B: CREATION,       # a new village's founders
        0x42C94B: ISLAND, 0x42C9E7: ISLAND, 0x42CA14: ISLAND, 0x42CA41: ISLAND,   # the crates (0x42D050)
        0x43C633: CREATION, 0x43C647: CREATION,                          # the villager creator 0x43C350
        0x43C7EF: CREATION, 0x43C7F5: CREATION,                          # ...its Golden Child (family 199)
        0x43C9D3: CREATION, 0x43C9DF: CREATION},                         # twins and triplets 0x43C840
    2: {0x4228E4: GAME,                                                  # the clothing dialog's OK
        0x424F2B: CREATION, 0x424F4E: CREATION, 0x424F65: CREATION,     # a new village's founders
        0x43960B: ISLAND, 0x4396AD: ISLAND, 0x4396DA: ISLAND, 0x439707: ISLAND,   # the crates
        **{va: CREATION for va in (0x44CC00, 0x44CC08, 0x44CC19, 0x44CC2F, 0x44CC3C, 0x44CC6A, 0x44CC79,
                                   0x44CC91, 0x44CCA3, 0x44CCC5, 0x44CCE4)},   # the villager creator
        0x44D00F: CREATION, 0x44D01B: CREATION,                          # the child materializer 0x44CEC0
        0x44D35F: CREATION, 0x44D36B: CREATION,                          # a new record copied from its source
        0x4664A4: NOT_A_RECORD},                                         # a byte of the scene object 0x4663B0 builds
    3: {0x41594E: ISLAND, 0x415965: ISLAND, 0x41752C: ISLAND, 0x41753E: ISLAND,  # island event outcomes
        0x417649: ISLAND, 0x41764E: ISLAND,
        0x41BF89: GAME,                                                  # the clothing dialog's OK
        0x456527: CREATION, 0x456550: CREATION, 0x456571: CREATION,     # the villager creator
        0x45650A: CREATION, 0x45650F: CREATION, 0x456519: CREATION,
        0x45FBDE: GAME},                                                 # the robe (robing 0x45FBC0)
    4: {0x41961D: GAME,                                                  # theFernsaceDialog's OK
        0x45F2BF: CREATION, 0x45F2DE: CREATION, 0x45F2FF: CREATION,     # the villager creator
        0x45F298: CREATION, 0x45F29D: CREATION, 0x45F2A7: CREATION},
    5: {0x419D68: GAME, 0x419E8E: GAME,                                  # theFernsaceDialog's two buttons
        0x4685C4: CREATION, 0x4685E3: CREATION, 0x468604: CREATION,     # the villager creator
        0x46859D: CREATION, 0x4685A2: CREATION, 0x4685AC: CREATION},
}
LOOK_FIELDS = {1: (0x360, 0x364), 2: (0x548, 0x54C), 3: (0xDF0, 0xDF4), 4: (0x1BB8, 0x1BBC), 5: (0x1BB8, 0x1BBC)}
WINDOW = {3: 0xDC4, 4: 0x1B8C, 5: 0x1B8C}
# What each spliced writer does: (record registers, value register or None, the immediate, the field).
SPLICED = {
    2: {0x4228E4: (("eax", "edx"), "ecx", None, 0x54C)},
    3: {0x41BF89: (("eax",), "ecx", None, 0xDF4), 0x45FBDE: (("eax",), None, 29, 0xDF4)},
    4: {0x41961D: (("eax",), "edx", None, 0x1BBC)},
    5: {0x419D68: (("edi",), "edx", None, 0x1BBC), 0x419E8E: (("edi",), "ecx", None, 0x1BBC)},
}


def scan_writers(game: int) -> set[int]:
    """Every instruction of the stock executable that stores to a record's head or body field."""
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    from capstone.x86 import X86_OP_MEM, X86_OP_REG
    pe = pefile.PE(str(stock_path(game)))
    base = pe.OPTIONAL_HEADER.ImageBase
    text = next(s for s in pe.sections if s.Characteristics & 0x20000000)
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    md.skipdata = True
    found = set()
    inss = list(md.disasm(text.get_data(), base + text.VirtualAddress))
    for i, ins in enumerate(inss):
        try:
            ops = ins.operands
        except Exception:      # skipdata
            continue
        if not ops:
            continue
        if ins.mnemonic.startswith("mov") and ops[0].type == X86_OP_MEM and ops[0].mem.disp in LOOK_FIELDS[game]:
            found.add(ins.address)
        if game in WINDOW and len(ops) == 2 and ops[0].type == X86_OP_REG and (
                (ins.mnemonic == "lea" and ops[1].type == X86_OP_MEM and ops[1].mem.disp == WINDOW[game])
                or (ins.mnemonic == "add" and ops[1].type not in (X86_OP_MEM, X86_OP_REG)
                    and ops[1].imm == WINDOW[game])):
            reg = ops[0].reg
            for w in inss[i + 1:i + 60]:
                try:
                    wo = w.operands
                except Exception:
                    break
                if wo and wo[0].type == X86_OP_MEM and wo[0].mem.base == reg and wo[0].mem.disp in (0x2C, 0x30) \
                        and w.mnemonic.startswith("mov"):
                    found.add(w.address)
                if wo and wo[0].type == X86_OP_REG and wo[0].reg == reg and w.mnemonic in ("mov", "lea", "pop", "xor"):
                    break
    return found


@unittest.skipUnless(HAVE_EMULATOR, "pefile and unicorn are not installed")
class TheGamesOwnChanges(unittest.TestCase):
    """The game's own writers: every one accounted for, and only the game's spliced, all or none."""

    def test_every_writer_is_accounted_for(self):
        try:
            import capstone  # noqa: F401
        except ImportError:
            self.skipTest("capstone is not installed")
        for game in (1, 2, 3, 4, 5):
            if not stock_path(game).is_file():
                continue
            with self.subTest(game=game):
                self.assertEqual(scan_writers(game), set(GAME_WRITERS[game]))

    def test_the_spliced_writers_are_the_dlls(self):
        source = (ROOT / "native" / "vvfp_original_look" / "vvfp_original_look.c").read_text(encoding="utf-8")
        for game, writers in GAME_WRITERS.items():
            for va, kind in writers.items():
                with self.subTest(game=game, va=hex(va)):
                    self.assertEqual(f"{{ 0x{va:06X}u," in source, kind == GAME)

    def machine(self, game: int):
        m = Process(stock_path(game).read_bytes(), DLL)
        writes = []
        base = m._exe_pe.OPTIONAL_HEADER.ImageBase
        size = m._exe_pe.OPTIONAL_HEADER.SizeOfImage
        from unicorn import UC_HOOK_MEM_WRITE
        m.mu.hook_add(UC_HOOK_MEM_WRITE, lambda mu, a, addr, s, v, u: writes.append(addr),
                      begin=base, end=base + size - 1)
        hooks, timers = [], []
        m.api_handlers["GetCurrentThreadId"] = lambda p: (0x1234, 0)
        m.api_handlers["SetWindowsHookExA"] = lambda p: (hooks.append((p.arg(0), p.arg(2), p.arg(3))) or 0x77, 16)
        m.api_handlers["SetTimer"] = lambda p: (timers.append((p.arg(0), p.arg(2), p.arg(3))) or 1, 16)
        m.export("VvfpStartup", game, 0)
        return m, writes, hooks, timers

    def test_startup_splices_only_the_games_writers_and_watches_between_frames(self):
        for game in (1, 2, 3, 4, 5):
            if not stock_path(game).is_file():
                continue
            with self.subTest(game=game):
                m, writes, hooks, timers = self.machine(game)
                sites = SPLICED.get(game, {})
                allowed = {va + k for va in sites for k in range(10)}
                self.assertTrue(set(writes) <= allowed, "only the game's own writers are written")
                for va in sites:
                    self.assertEqual(m.read(va, 1), b"\xE9", hex(va))
                if not sites:
                    self.assertEqual(writes, [], "A New Home: nothing")
                self.assertEqual(len(hooks), 1)
                self.assertEqual(hooks[0], (3, 0, 0x1234), "WH_GETMESSAGE on the game's own thread, no module")
                self.assertEqual(timers, [(0, 250, 0)], "a thread timer: no window, 250 ms, no procedure")
                m.export("VvfpStartup", game, 0)
                self.assertEqual(len(hooks), 1, "a second start changes nothing")

    def test_a_splice_makes_the_games_own_write(self):
        for game, sites in SPLICED.items():
            if not stock_path(game).is_file():
                continue
            for va, (regs, value_reg, imm, field) in sites.items():
                with self.subTest(game=game, va=hex(va)):
                    m, _w, _h, _t = self.machine(game)
                    stock = pefile.PE(str(stock_path(game)))
                    length = len(bytes.fromhex(json.loads(
                        (ROOT / "data" / f"vv{game}_original_look_feature.json").read_text(encoding="utf-8"))
                        ["runtime_detours"][list(sites).index(va)]["stock_bytes"]))
                    record = m.alloc(0x10000)
                    values = {"eax": 0x1111, "ebx": 0x2222, "ecx": 0x3333, "edx": 0x4444, "esi": 0x5555,
                              "edi": 0x6666, "ebp": 0x7777}
                    values[regs[0]] = record
                    if len(regs) > 1:
                        values[regs[1]] = 0
                    expected = imm if value_reg is None else 0x1C
                    if value_reg is not None:
                        values[value_reg] = expected
                    for name, value in values.items():
                        m.set_reg(name, value)
                    m.run(va, va + length)
                    self.assertEqual(struct.unpack("<i", m.read(record + field, 4))[0], expected)
                    for name, value in values.items():
                        self.assertEqual(m.reg(name), value, name)
                    del stock

class HowItShips(unittest.TestCase):
    def test_started_from_the_second_word(self):
        self.assertIn(DLL_NAME, patcher.STARTUP_LOADER_COMPANIONS_2)
        header = (ROOT / "native" / "shared" / "startup_companions_2.h").read_text(encoding="utf-8")
        self.assertLess(header.index('"VVFP Head Look.dll"'), header.index(f'"{DLL_NAME}"'))   # append only
        self.assertEqual(list(patcher.STARTUP_LOADER_COMPANIONS_2),
                         [line.strip().strip('",') for line in header.splitlines()
                          if line.strip().startswith('"VVFP ')])

    def test_each_row_ships_it_on_by_default_with_the_origins_row(self):
        digest = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        public = {p.id: p for p in patcher.load_public_fun_patches()}
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                data = json.loads((ROOT / "data" / f"vv{game}_original_look_feature.json").read_text(encoding="utf-8"))
                self.assertTrue(data["enabled"] and data["catalog_enabled"] and not data["catalog_hidden"])
                self.assertIn("**On by default.**", data["description"])
                self.assertEqual(data["dependencies"], [f"vv{game}_enable_origins_exclusive_features"])
                self.assertIn("**Requires the Origins-exclusive base", data["description"])
                self.assertEqual(data["companion_files"],
                                 [{"source": f"assets/original_look/{DLL_NAME}", "destination": DLL_NAME,
                                   "sha256": digest}])
                self.assertEqual(data["patches"], [])
                self.assertIn(f"vv{game}_original_look", public)

    def test_the_bit_is_set_when_the_row_ships_in_every_mode(self):
        bit = 1 << patcher.STARTUP_LOADER_COMPANIONS_2.index(DLL_NAME)
        for game in (1, 2, 3, 4, 5):
            build = _builds()[f"vv{game}"]
            with self.subTest(game=game):
                features = patcher._attach_automatic_companions(
                    f"vv{game}", patcher._selected_fun_patches(build, [f"vv{game}_original_look"]))
                self.assertEqual(patcher._startup_loader_mask_2(features) & bit, bit)
                self.assertIn(f"vv{game}_enable_origins_exclusive_features", [f.id for f in features])
                if not stock_path(game).is_file():
                    continue
                for mode in ("collection_progression", "immediate_fixed", "experimental_expanded_256"):
                    if mode not in {m.id for m in patcher.load_patch_modes()} or (
                            mode == "experimental_expanded_256" and game < 3):
                        continue
                    with self.subTest(mode=mode):
                        data, _ = patcher.render_patched_bytes(stock_path(game), build, mode,
                                                               [f"vv{game}_original_look"])
                        self.assertTrue(data)

    def test_in_the_release(self):
        text = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn(f'"assets/original_look/{DLL_NAME}"', text)
        self.assertTrue(DLL.is_file())

    def test_the_per_save_inventory_names_it(self):
        text = (ROOT / "docs" / "per-save-folders.md").read_text(encoding="utf-8")
        self.assertIn("| Original Looks (Change Appearance's Reset to original) | `...Data\\Original Looks` |", text)


if __name__ == "__main__":
    unittest.main()
