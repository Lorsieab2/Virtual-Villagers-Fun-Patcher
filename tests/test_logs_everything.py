"""The logs keep track of everything (the owner, 2026-11-17): "the logs need to keep track of sex and gender
presentation changes, males carrying babies, and everything!!!" -- all five games.

Proves, on the shipped DLLs in the emulator (tests/story_emulator.py) and the test build of "VVFP Story
Upgrades.dll":

* a GENDER PRESENTATION change ("VVFP Gender Presentation.dll" VvfpGenderPresentationSet, which Change Appearance
  and the Custom Island Event's presentation effect both reach) writes ONE "Appearance changed" record to the
  Births and Conceptions log (the Parentage Export's WriteVillageRecord, kind 7) with "Old gender presentation" /
  "New gender presentation" lines; the same value again, a refused villager and a failed write write none;
* a HEAD LOOK change ("VVFP Head Look.dll" VvfpHeadLookSet / VvfpHeadLookSetMany) the same, "Old head look" / "New
  head look" in the Change Appearance window's words, one record per villager whose look changed;
* a branching event's STORY TRAIT is a line of the event's Island Events entry ("<name> now has the story trait
  mute."), once, and VvfpStoryTraitsOf answers it for the rosters;
* a name the event changes (lose_name) writes a "Name changed" record (kind 10) with the old name and the event,
  except in A New Home with its parentage companion in the game (which writes that record itself);
* a couple's pregnancy in which the PARTNER carries is a line of the Island Events entry naming who carries, and
  its Conception goes to WriteParentageRecordCarried with the flag (The Tree of Life and New Believers: the
  conception routine stood in, as tests/test_story_custom_island_event.py does);
* Repair Saves & Logs offers each new roster line (Sex at birth, Gender presentation, Head look, Story traits) for the
  older Village History snapshots, from the date the player picks, as it offers a mask.

The Births and Conceptions log's carrier notes are proved by native/parentage_export/parentage_export_harness.c, and
the rosters' new lines by native/population_export/population_export_harness.c (tests/test_vv1_expected_father.py
runs that harness).  Nothing here is verified live in a running game: UNCONFIRMED live.
"""
from __future__ import annotations

import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_log_additions as additions  # noqa: E402

try:
    import test_gender_presentation as tgp
    import test_head_look as thl
    from gender_presentation_emulation import Game as GpGame
    from head_look_emulation import Game as HlGame
    HAVE_EMULATOR = tgp.HAVE_EMULATOR
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

GAMES = (1, 2, 3, 4, 5)
PARENTAGE = 0x72000000
VV1_PARENTAGE = 0x73000000


class WriteVillageRecord:
    """"VVFP Parentage Export.dll" as a companion finds it (native/shared/patcher_files.h: by full path in the
    patcher's folder beside the game), its WriteVillageRecord recorded: (game, kind, record, check, before, after,
    detail).  Its other exports: `others` maps a name to its own stub."""

    def __init__(self, p, others: dict | None = None, hooked: bool = False):
        """hooked: the process runs with ranged code hooks only (tests/test_story_cie_graph_runtime.py Run), so
        each stub gets its own; otherwise the whole-range hook already sees them (a second would run them twice)."""
        self.hooked = hooked
        self.calls: list[tuple] = []
        self.p = p
        export = p.alloc(0x10)
        stubs = {"WriteVillageRecord": export}
        for name, fn in (others or {}).items():
            at = p.alloc(0x10)
            stubs[name] = at
            p.stub(at, fn)
        p.api_handlers["LoadLibraryExW"] = lambda q: (
            PARENTAGE if q.wstring(q.arg(0)).endswith(
                "\\Virtual Villagers Fun Patcher Files\\VVFP Parentage Export.dll") else 0, 12)
        p.api_handlers["GetProcAddress"] = lambda q: (
            stubs.get(q.cstring(q.arg(1)), 0) if q.arg(0) == PARENTAGE else 0, 8)

        def write(q):
            before = q.cstring(q.arg(4)) if q.arg(4) else None
            self.calls.append((q.arg(0), q.arg(1), q.arg(2), q.arg(3), before, q.arg(5), q.arg(6)))
            return 1, 28
        p.stub(export, write)
        self.hook(export)
        for at in stubs.values():
            self.hook(at)

    def hook(self, va):
        if self.hooked:
            from unicorn import UC_HOOK_CODE
            self.p.mu.hook_add(UC_HOOK_CODE, self.p._on_code, begin=va, end=va)


def gp_lines(was: str, now: str) -> str:
    return f"  Old gender presentation: {was}\n  New gender presentation: {now}\n"


@unittest.skipUnless(HAVE_EMULATOR, "needs unicorn, capstone and pefile")
class GenderPresentationIsLogged(unittest.TestCase):
    def test_each_change_is_one_appearance_record_in_every_game(self):
        ran = 0
        for game in GAMES:
            if not tgp.have(game):
                continue
            ran += 1
            with self.subTest(game=game):
                g = GpGame(game, tgp.stock_exe(game))
                log = WriteVillageRecord(g.p)
                ana = g.villager(0, "Ana", female=True, head=7)
                g.villager(1, "Bo")
                self.assertEqual(g.set(0, 1), 1)
                self.assertEqual(len(log.calls), 1, "one record for the change")
                c = log.calls[0]
                self.assertEqual(c[:4], (game, 7, ana, 1), "kind 7 (Appearance changed), the live record, checked")
                self.assertTrue(c[4].startswith("  Old head: 7\n  Old body: 0\n  New head: 7\n  New body: 0\n"),
                                "the looks the same before and after (the rows never change)")
                self.assertTrue(c[4].endswith(gp_lines("Own look", "Other sex's look")), c[4])
                self.assertEqual(g.set(0, 1), 1, "kept again")
                self.assertEqual(len(log.calls), 1, "...the same value again: no record")
                self.assertEqual(g.set(0, 0), 1)
                self.assertEqual(len(log.calls), 2)
                self.assertTrue(log.calls[1][4].endswith(gp_lines("Other sex's look", "Own look")), log.calls[1][4])
                self.assertEqual(g.set(1, 0), 1, "Bo kept as he is")
                self.assertEqual(len(log.calls), 2, "...nothing changed: no record")
        self.assertGreater(ran, 0, "needs the stock executables")

    def test_a_refused_villager_and_a_failed_write_log_nothing(self):
        if not tgp.have(1):
            self.skipTest("needs A New Home's stock executable")
        g = GpGame(1, tgp.stock_exe(1))
        log = WriteVillageRecord(g.p)
        golden = g.villager(0, "Goldie", age=100)
        g.p.put32(golden + 0x36C, 0xC7)                     # the Golden Child: never offered
        self.assertEqual(g.set(0, 1), 0)
        self.assertEqual(log.calls, [], "refused: no record")
        g = GpGame(1, tgp.stock_exe(1), slot=0)             # no save slot: nothing can be kept
        log = WriteVillageRecord(g.p)
        g.villager(0, "Ana", female=True)
        self.assertEqual(g.set(0, 1), 0)
        self.assertEqual(log.calls, [], "not kept: no record")


@unittest.skipUnless(HAVE_EMULATOR, "needs unicorn, capstone and pefile")
class HeadLookIsLogged(unittest.TestCase):
    def test_each_change_is_one_appearance_record_in_every_game(self):
        ran = 0
        for game in GAMES:
            if not thl.have(game):
                continue
            ran += 1
            with self.subTest(game=game):
                g = HlGame(game, thl.stock_exe(game))
                log = WriteVillageRecord(g.p)
                cy = g.villager(0, "Cy", age=600, head=3)
                g.villager(1, "Di", age=700, head=5)
                self.assertEqual(g.set_look(0, 2), 1)
                self.assertEqual(len(log.calls), 1)
                c = log.calls[0]
                self.assertEqual(c[:4], (game, 7, cy, 1))
                self.assertTrue(c[4].endswith("  Old head look: Auto (old from 55)\n  New head look: Old\n"), c[4])
                self.assertEqual(g.set_look(0, 2), 1)
                self.assertEqual(len(log.calls), 1, "the same look again: no record")
                self.assertEqual(g.set_look(0, 1), 1)
                self.assertTrue(log.calls[-1][4].endswith("  Old head look: Old\n  New head look: Young\n"))
                # Change Appearance for All: one write of the file, one record per villager whose look changed.
                records = g.p.alloc(8)
                looks = g.p.alloc(8)
                g.p.write(records, struct.pack("<2I", g.record(0), g.record(1)))
                g.p.write(looks, struct.pack("<2i", 1, 2))
                g.later()
                self.assertEqual(g.p.export("VvfpHeadLookSetMany", game, records, looks, 2), 1)
                self.assertEqual(len(log.calls), 3, "Cy stays Young (nothing), Di becomes Old (one record)")
                self.assertEqual(log.calls[-1][2], g.record(1))
                self.assertTrue(log.calls[-1][4].endswith("  Old head look: Auto (old from 55)\n  New head look: Old\n"))
                g.p.put32(looks, 7)                                   # a look above Old: refused, nothing kept
                g.later()
                self.assertEqual(g.p.export("VvfpHeadLookSetMany", game, records, looks, 2), 0)
                self.assertEqual(len(log.calls), 3, "refused: no record")
        self.assertGreater(ran, 0, "needs the stock executables")


# ---------------------------------------------------------------------------------------------------------------
# The branching events' engine (the test build of "VVFP Story Upgrades.dll")
# ---------------------------------------------------------------------------------------------------------------

try:
    import vv_cie_graph as cg
    import vv_event_content as content
    import test_story_cie_graph_runtime_v6 as rt
    from test_story_custom_island_event import _conception_stub, emulated, have_stock
    from unicorn import UC_HOOK_CODE
    ENGINE = rt.HAVE_EMULATOR
except ImportError:  # pragma: no cover - environment dependent
    ENGINE = False

ENGINE_GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")


def patched(data: bytes, old: bytes, new: bytes) -> bytes:
    """The compiled event with one effect record replaced, its checksum made again."""
    out = bytearray(data)
    assert out.count(old) == 1, old
    at = out.index(old)
    out[at:at + len(new)] = new
    struct.pack_into("<I", out, 12, 0)
    struct.pack_into("<I", out, 12, zlib.crc32(bytes(out)))
    return bytes(out)


def presentation_record(role: int) -> bytes:
    return struct.pack("<BBBBiiHH", 23, role, 0, 0, 1, 0, 0xFFFF, 0)


def one_effect_graph(game: str, roles: dict) -> dict:
    """One page whose one effect is a presentation on the first role (replaced by the test)."""
    first = next(iter(roles))
    return {"format": "vvfp-cie-graph", "version": 6, "title": "A Changed Day", "games": [int(game[2])],
            "roles": roles, "start": "p",
            "nodes": {"p": {"text": "(Name) has a changed day.",
                            "effects": [{"do": "presentation", "role": first, "on": True}]}}}


@unittest.skipUnless(ENGINE, "needs the emulator")
class EngineLogLines(unittest.TestCase):
    def filed(self, r) -> str:
        return r.log()[2]

    def test_a_story_trait_is_a_line_of_the_entry_once(self):
        quiet = cg.load({"format": "vvfp-cie-graph", "version": 6, "title": "The Quiet Hands",
                         "games": [1, 2, 3, 4, 5], "roles": {"subject": {"kind": "villager"}}, "start": "s",
                         "nodes": {"s": {"text": "(Name) folds (his/her) hands and says nothing.", "children": []}}})
        quiet, _plan = content.inject(quiet, {}, {"traits": [{"role": "subject", "trait": "mute"}]})
        data = cg.compile_graph(quiet)
        ran = 0
        for game in ENGINE_GAMES:
            if not have_stock(game):
                continue
            ran += 1
            with self.subTest(game=game):
                r = rt.Run(game)
                for round_ in (1, 2):
                    r.log(1)
                    r.rolls([1] + [0] * 40)
                    r.force([], graph=quiet)
                    self.assertIsNone(r.queue(data))
                    r.play()
                    self.assertEqual(r.state()["records"][0], 1, "Bea was cast")
                    entry = self.filed(r)
                    if round_ == 1:
                        self.assertIn("  Bea now has the story trait mute.\n", entry)
                    else:
                        self.assertNotIn("story trait", entry, "kept already: no second line")
                self.assertEqual(r.p.export("VvfpStoryTraitsOf", r.n, r.v.record(1)) & 1, 1,
                                 "the rosters' answer: Bea is mute")
                self.assertEqual(r.p.export("VvfpStoryTraitsOf", r.n, r.v.record(2)), 0, "Cal is not")
        self.assertGreater(ran, 0, "needs the stock executables")

    def test_a_lost_name_is_a_name_changed_record(self):
        ran = 0
        for game in ENGINE_GAMES:
            if not have_stock(game):
                continue
            for vv1_companion in ((False, True) if game == "vv1" else (False,)):
                ran += 1
                with self.subTest(game=game, vv1_parentage=vv1_companion):
                    r = rt.V6(game, [(0, "f", 30, "Ana", 0, False)])
                    log = WriteVillageRecord(r.p, hooked=True)
                    if vv1_companion:
                        r.p.api_handlers["GetModuleHandleA"] = lambda q: (
                            VV1_PARENTAGE if q.cstring(q.arg(0)) == "VVFP VV1 Parentage.dll" else 0, 4)
                    data = rt.compiled(one_effect_graph(game, {"subject": {"kind": "villager", "min_age": 14}}))
                    data = patched(data, presentation_record(0), struct.pack("<BBBBiiHH", 32, 0, 0, 0, 0, 0, 0xFFFF, 0))
                    r.rolls([0] * 40)
                    self.assertIsNone(r.queue6(data, strict=True, origin=2))
                    r.walk_through()
                    self.assertEqual(r.p.read(r.v.record(0) + r.v.L["name"], 2), b"?\0", "the name is lost")
                    renames = [c for c in log.calls if c[1] == 10]
                    if vv1_companion:
                        self.assertEqual(renames, [], "A New Home's parentage companion writes it itself")
                        continue
                    self.assertEqual(len(renames), 1, log.calls)
                    c = renames[0]
                    self.assertEqual((c[0], c[2], c[3], c[6]), (int(game[2]), r.v.record(0), 1, 1))
                    self.assertTrue(c[4].startswith("  Old name: Ana\n  Age: 600\n"), c[4])
                    self.assertIn("  Changed by: A Changed Day (island event)\n", c[4])
        self.assertGreater(ran, 0, "needs the stock executables")

    def test_the_partner_carries_line_and_its_conception(self):
        ran = 0
        for game in ("vv4", "vv5"):
            if not have_stock(game):
                continue
            ran += 1
            with self.subTest(game=game):
                r = rt.V6(game, [(0, "f", 30, "Ana", 0, False), (1, "m", 31, "Bo", 0, False)])
                calls = []

                def carried(q):
                    calls.append(("carried", q.arg(0), q.arg(2), q.arg(3), q.arg(4)))
                    return 1, 20

                def plain(q):
                    calls.append(("plain", q.arg(0), q.arg(2), q.arg(3)))
                    return 1, 16
                WriteVillageRecord(r.p, {"WriteParentageRecordCarried": carried,
                                         "WriteParentageRecordWithFather": plain}, hooked=True)
                _conception_stub(r.story)
                va = 0x45E7B0 if game == "vv4" else 0x465E00
                r.p.mu.hook_add(UC_HOOK_CODE, r.p._on_code, begin=va, end=va)
                if game == "vv4":
                    r.story.record_call(0x412F90, 8)
                    r.p.mu.hook_add(UC_HOOK_CODE, r.p._on_code, begin=0x412F90, end=0x412F90)
                # The parentage row ticked: its conception site (story_tables.h VV4/VV5_PARENTAGE_SITE, inside the
                # routine stood in above) no longer holds the stock bytes.
                site = {"vv4": 0x45E8E4, "vv5": 0x465F34}[game]
                r.p.write(site, bytes([r.p.read(site, 1)[0] ^ 0xFF]))
                text = f"vv{r.n}\n# partner_carry_percent=100\n"
                buf = r.p.alloc(len(text) + 1)
                r.p.write(buf, text.encode("ascii") + b"\0")
                r.p.export("VvfpStoryProbeInstalledPatches", r.n, buf)
                g = one_effect_graph(game, {"subject": {"kind": "villager", "min_age": 18, "sex": "female"},
                                            "partner": {"kind": "villager", "min_age": 18, "sex": "male"}})
                data = rt.compiled(g)
                names = rt.Names(data)
                subject, partner = names.roles.index("subject"), names.roles.index("partner")
                data = patched(data, presentation_record(subject),
                               struct.pack("<BBBBiiHH", 28, subject, 1 | 8, 0, partner, 0, 0xFFFF, 0))
                r.rolls([0] * 40)
                r.log(1)
                self.assertIsNone(r.queue6(data, strict=True, origin=2))
                r.walk_through()
                self.assertNotEqual(r.v.i32(1, r.v.L["pregnant"]), 0, "Bo carries")
                self.assertEqual(r.v.i32(0, r.v.L["pregnant"]), 0, "Ana does not")
                entry = r.log()[2]
                self.assertIn("  Bo, who is male, carries the babies (the partner carries instead of Ana).\n", entry)
                self.assertEqual(calls, [("carried", r.n, r.v.record(1), r.v.record(0), 1)],
                                 "the Conception goes to WriteParentageRecordCarried, the carrier as the mother")
        self.assertGreater(ran, 0, "needs the stock executables")


# ---------------------------------------------------------------------------------------------------------------
# Repair Saves & Logs: the new roster lines in older History snapshots
# ---------------------------------------------------------------------------------------------------------------

LOGS = "Virtual Villagers Fun Patcher Logs"


def write(folder: Path, relative: str, text: str) -> Path:
    path = folder / LOGS / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\n", "\r\n").encode("latin-1"))
    return path


def villager(n: int, name: str, head: int, body: int, extra: str = "") -> str:
    return (f"Villager {n}\n  Name: {name}\n  Age: 400\n  Sex: Male\n{extra}  Head: {head}\n  Body: {body}\n"
            f"  Likes: (none)\n  Dislikes: (none)\n\n")


def snapshot(date: str, *people: str) -> str:
    return f"=== Virtual Villagers 3 -- {date} ===\nVillage: Tribe (Save 1)\n" + "".join(people)


class RepairAddsTheNewLines(unittest.TestCase):
    KEPT = "  Sex at birth: Female\n  Gender presentation: Other sex's look\n  Head look: Old\n  Story traits: mute\n"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def kinds(self):
        return {k.id: k for k in additions.plan(self.folder, 3, 1)}

    def test_each_line_from_the_date_the_player_picks(self):
        write(self.folder, "Tribe Population/Village Population 1.txt",
              "Village: Tribe (Save 1)\n" + villager(1, "Kiwi", 7, 3, self.KEPT) + villager(2, "Budi", 4, 4))
        history = write(self.folder, "Tribe History/Village History 1.txt",
                        snapshot("2026-11-01 10:00", villager(1, "Kiwi", 7, 3), villager(2, "Budi", 4, 4))
                        + snapshot("2026-11-02 10:00", villager(1, "Kiwi", 7, 3), villager(2, "Budi", 4, 4)))
        kinds = self.kinds()
        ids = ("sex_at_birth", "presentation", "head_look", "story_traits")
        for kind_id in ids:
            with self.subTest(kind=kind_id):
                kind = kinds[kind_id]
                self.assertEqual(kind.decided, 0, "a date only the player can give")
                [question] = kind.questions.values()
                self.assertEqual(question.options, ["From 2026-11-01 10:00", "From 2026-11-02 10:00",
                                                    additions.FROM_NOW])
                self.assertEqual(question.default, additions.FROM_NOW, "nothing unless the player says")
                self.assertIn("Kiwi", question.text)
                self.assertIn(kind_id, additions.CHECKED)
                self.assertIn(kind_id, additions.ADDED)
        answers = {q.key: "From 2026-11-02 10:00" for k in ids for q in kinds[k].questions.values()}
        additions.apply(self.folder, [kinds[k] for k in ids], set(ids), answers)
        text = history.read_bytes().decode("latin-1")
        second = text.index("2026-11-02")
        self.assertNotIn("Head look", text[:second], "the first snapshot is left as it was")
        self.assertIn("  Name: Kiwi\r\n  Age: 400\r\n  Sex: Male\r\n  Sex at birth: Female\r\n"
                      "  Gender presentation: Other sex's look\r\n  Head look: Old\r\n  Story traits: mute\r\n"
                      "  Head: 7", text[second:], "after Sex, in the exporter's order")
        self.assertEqual(text.count("Head look"), 1, "Budi has none")
        again = self.kinds()
        self.assertEqual([q.options for q in again["head_look"].questions.values()],
                         [["From 2026-11-01 10:00", additions.FROM_NOW]], "only the snapshot still without it")

    def test_nothing_without_the_line_on_the_page(self):
        write(self.folder, "Tribe Population/Village Population 1.txt",
              "Village: Tribe (Save 1)\n" + villager(1, "Kiwi", 7, 3))
        write(self.folder, "Tribe History/Village History 1.txt",
              snapshot("2026-11-01 10:00", villager(1, "Kiwi", 7, 3)))
        kinds = self.kinds()
        for kind_id in ("sex_at_birth", "presentation", "head_look", "story_traits"):
            self.assertEqual(kinds[kind_id].questions, {}, kind_id)
            self.assertEqual(kinds[kind_id].inserts, [], kind_id)

    def test_two_villagers_of_one_name_and_looks_that_differ_are_left_alone(self):
        write(self.folder, "Tribe Population/Village Population 1.txt",
              "Village: Tribe (Save 1)\n" + villager(1, "Kiwi", 7, 3, "  Head look: Old\n") + villager(2, "Kiwi", 7, 3))
        write(self.folder, "Tribe History/Village History 1.txt",
              snapshot("2026-11-01 10:00", villager(1, "Kiwi", 7, 3), villager(2, "Kiwi", 7, 3)))
        kind = self.kinds()["head_look"]
        self.assertEqual(kind.questions, {})
        self.assertTrue(any("Two or more villagers named Kiwi" in n for n in kind.notes), kind.notes)


if __name__ == "__main__":
    unittest.main()
