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


def change(name: str, old: tuple[int, int], new: tuple[int, int]) -> str:
    return (f"Appearance changed\n  Name: {name}\n  Old head: {old[0]}\n  Old body: {old[1]}\n"
            f"  New head: {new[0]}\n  New body: {new[1]}\n\n")


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
# The DLL in each game, and how it ships
# ---------------------------------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def _builds():
    return {b.id: b for b in patcher.load_builds()}


def stock_path(game: int) -> Path:
    return ROOT / "inputs" / f"vv{game}-stock-copy" / _builds()[f"vv{game}"].input_name


@unittest.skipUnless(HAVE_EMULATOR, "pefile and unicorn are not installed")
class WritesNothingIntoTheGame(unittest.TestCase):
    """The all-or-none rule, for a companion with nothing to install: VvfpStartup writes no byte of any
    game's image and unlocks no page; it sets one WH_GETMESSAGE hook on the game's own thread and one
    thread timer, and nothing else."""

    def test_each_game(self):
        for game in (1, 2, 3, 4, 5):
            if not stock_path(game).is_file():
                continue
            with self.subTest(game=game):
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
                self.assertEqual(writes, [], "no byte of the game's image is written")
                self.assertNotIn("VirtualProtect", m.api_calls)
                self.assertEqual(len(hooks), 1)
                self.assertEqual(hooks[0][0], 3, "WH_GETMESSAGE")
                self.assertEqual(hooks[0][1:], (0, 0x1234), "on the game's own thread, no module")
                self.assertEqual(timers, [(0, 250, 0)], "a thread timer: no window, 250 ms, no procedure")
                m.export("VvfpStartup", game, 0)
                self.assertEqual(len(hooks), 1, "a second start changes nothing")


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
