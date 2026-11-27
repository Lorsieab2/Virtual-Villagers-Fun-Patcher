"""The parents follow their sex (the owner, 2026-11-27: "make sure the parents appearances and names are fixed").

Villagers of any sex may carry a baby (the owner, 2026-11-25), and every game copies the villager who CARRIED into the
newborn's Mother fields and the carrier's expected other parent into its Father fields.  So when a man carried a
woman's baby -- New Believers' Heathen Mommy Ahi Mashudu and Vaihi Salongo's daughter Coral Siutiti -- the child
listed him as its Mother and her as its Father, and the Details screen drew each with the other sex's sheets.

The rule, all five games: when the parents' sexes differ the woman is the Mother and the man the Father, whoever
carried, each with their own name, head and body; two of one sex keep the carrier as the Mother.

  * Live: "VVFP Parentage Export.dll" at the game's birth splice (The Lost Children to New Believers: every delivery,
    catch-up and Time Warp included), "VVFP Heathen Aging.dll" at a Heathen birth, "VVFP VV1 Parentage.dll" at A
    New Home's births.  The Birth record then names them so, with "Note: Carried by <him>, who is male (named as
    the Father; ...)", which the readers that pair a pregnancy with its Birth follow.
  * Repair Saves & Logs (src/vv_parents_follow_sex.py): a child recorded the stock way -- a man as its Mother and a
    woman as its Father, by the sex the save and the logs record for each -- is swapped in the save, the Birth
    records and the History / Population snapshots, the patcher's per-villager files re-keyed; a parent whose sex
    nothing records is asked about; a child recorded right is left alone.
"""
from __future__ import annotations

import re
import struct
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native"
VS_TOOLS = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231")
CL = VS_TOOLS / "bin" / "Hostx64" / "x86" / "cl.exe"
SDK = Path(r"C:\Program Files (x86)\Windows Kits\10")
SDK_VERSION = "10.0.26100.0"
HARNESS_CHECKS = 4 * 12 + 1


@unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
class ParentageExportFollowsSex(unittest.TestCase):
    """native/parentage_export/parents_follow_sex_harness.c compiles the companion whole over each game's table."""

    def test_the_birth_splice_gives_the_parents_by_sex(self):
        with tempfile.TemporaryDirectory(prefix="vvfp_pfs_") as out:
            exe = Path(out) / "parents_follow_sex_harness.exe"
            build = subprocess.run(
                [str(CL), "/nologo", f"/Fo{out}\\", "/O2", "/MT",
                 "/I", str(VS_TOOLS / "include"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "um"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "shared"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "ucrt"),
                 "/I", str(NATIVE / "shared"),
                 str(NATIVE / "parentage_export" / "parents_follow_sex_harness.c"),
                 str(NATIVE / "shared" / "village_identity.c"),
                 str(NATIVE / "shared" / "save_folder.c"),
                 "/link",
                 f"/LIBPATH:{VS_TOOLS / 'lib' / 'x86'}",
                 f"/LIBPATH:{SDK / 'Lib' / SDK_VERSION / 'um' / 'x86'}",
                 f"/LIBPATH:{SDK / 'Lib' / SDK_VERSION / 'ucrt' / 'x86'}",
                 f"/OUT:{exe}", "kernel32.lib", "shell32.lib"],
                capture_output=True, text=True, cwd=out, timeout=600,
            )
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            result = subprocess.run([str(exe)], capture_output=True, text=True, cwd=out, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"== {HARNESS_CHECKS} check(s), 0 failure(s) ==", result.stdout)
        self.assertEqual(len(re.findall(r"^  ok ", result.stdout, re.M)), HARNESS_CHECKS, result.stdout)


class CompanionsCallIt(unittest.TestCase):
    """The three live places, in their source and their shipped DLLs."""

    def test_the_exports_are_shipped(self):
        try:
            import pefile
        except ImportError:  # pragma: no cover - environment dependent
            self.skipTest("pefile is not installed")
        pe = pefile.PE(str(ROOT / "assets" / "parentage" / "VVFP Parentage Export.dll"), fast_load=True)
        pe.parse_data_directories([pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])
        self.assertIn(b"WriteParentageBirthCarried", {e.name for e in pe.DIRECTORY_ENTRY_EXPORT.symbols})
        for dll in (ROOT / "assets" / "heathen_aging" / "VVFP Heathen Aging.dll",
                    ROOT / "assets" / "parentage" / "VVFP VV1 Parentage.dll"):
            with self.subTest(dll=dll.name):
                self.assertIn(b"WriteParentageBirthCarried\0", dll.read_bytes())

    def test_the_splice_swaps_before_the_last_name_and_the_number(self):
        source = (NATIVE / "parentage_export" / "parentage_export.c").read_text(encoding="utf-8")
        body = source[source.index("int __stdcall WriteParentageBirthLitter("):
                      source.index("int __stdcall WriteParentageBirthCarried(")]
        self.assertLess(body.index("delivery_litter("), body.index("parents_follow_sex("),
                        "the litter is read from the carrier before the parents trade places")
        self.assertLess(body.index("parents_follow_sex("), body.index("rule_last_name("))
        self.assertLess(body.index("rule_last_name("), body.index("number_new_name("))
        # A pregnancy the carrier's Conception names is ended by the Birth that names him as its Father.
        self.assertIn("birth_carried_by(later->text, name)", source)

    def test_heathen_births_and_a_new_home_follow_the_same_rule(self):
        heathen = (NATIVE / "vvfp_heathen_aging" / "vvfp_heathen_aging.c").read_text(encoding="utf-8")
        deliver = heathen[heathen.index("static void deliver("):]
        self.assertLess(deliver.index("follow_sex(baby, mother)"), deliver.index("tell_born("))
        vv1 = (NATIVE / "vv1_parentage" / "vv1_parentage.c").read_text(encoding="utf-8")
        self.assertEqual(vv1.count("(void)vv1_follow_sex(records, "), 2, "the hooked birth and the frame's inference")


LOGS = "Virtual Villagers Fun Patcher Logs"
FIXTURES = ROOT / "tests" / "fixtures" / "rename_tribe"


class FakeProcesses:
    def find(self, exe_name):
        return []


def _write(folder: Path, relative: str, text: str) -> Path:
    path = folder / LOGS / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\n", "\r\n").encode("latin-1"))
    return path


def _birth(n: int, child: str, mother: tuple, father: tuple) -> str:
    return (f"Birth {n}\n  Child: {child}\n    Sex: Female\n    Head: 1\n    Body: 1\n    Likes: (none)\n"
            f"    Dislikes: (none)\n  Mother: {mother[0]}\n    Head: {mother[1]}\n    Body: {mother[2]}\n"
            f"  Father: {father[0]}\n    Head: {father[1]}\n    Body: {father[2]}\n  Born as: Single birth\n\n")


def _snapshot_entry(n: int, v, father: tuple, mother: tuple) -> str:
    return (f"Villager {n}\n  Name: {v.name}\n  Age: 400\n  Sex: {v.sex}\n  Head: {v.head}\n  Body: {v.body}\n"
            f"  Parents:\n    Father: {father[0]}\n      Head: {father[1]}\n      Body: {father[2]}\n"
            f"    Mother: {mother[0]}\n      Head: {mother[1]}\n      Body: {mother[2]}\n\n")


class RepairBackfill(unittest.TestCase):
    """Repair Saves & Logs puts a child recorded the stock way right -- the save, the Birth record, the History
    snapshot -- leaves a child recorded right and one of a same-sex couple alone, and asks when a parent's sex is not
    recorded (src/vv_parents_follow_sex.py).  On each game's real save (the Rename Tribe fixtures)."""

    def _village(self, game: int):
        import gzip
        import sys
        sys.path.insert(0, str(ROOT / "src"))
        import vv_last_names as ln
        import vv_log_additions as additions
        import vv_log_tools as tools
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        folder = Path(tmp.name)
        checker = tools.load_checker()
        save = folder / f"{checker.SAVE_STEMS[game]}1.ldw"
        save.write_bytes(gzip.decompress((FIXTURES / f"vv{game}-huttest-1.ldw.gz").read_bytes()))
        header = sorted(additions.current_villages(folder, game, 1) or {"Village: Tribe (Save 1)"})[0]
        return folder, save, header, ln, additions, tools

    def _put_parents(self, ln, game: int, buf: bytearray, v, mother: tuple, father: tuple) -> None:
        f = ln.FIELDS[game]
        fh, fb, mh, mb, _eh, _eb = f.looks
        ln._put_name(buf, v.at + f.mother, f.parent_cap, mother[0])
        ln._put_name(buf, v.at + f.father, f.parent_cap, father[0])
        for off, value in ((mh, mother[1]), (mb, mother[2]), (fh, father[1]), (fb, father[2])):
            struct.pack_into("<i", buf, v.at + off, value)

    def _parents(self, ln, game: int, data: bytes, v) -> tuple:
        f = ln.FIELDS[game]
        fh, fb, mh, mb, _eh, _eb = f.looks
        return ((ln._cstr(data, v.at + f.mother, f.parent_cap), ln._i32(data, v.at + mh), ln._i32(data, v.at + mb)),
                (ln._cstr(data, v.at + f.father, f.parent_cap), ln._i32(data, v.at + fh), ln._i32(data, v.at + fb)))

    def test_the_later_four_games(self):
        import vv_parents_follow_sex as pfs
        for game in (2, 3, 4, 5):
            with self.subTest(game=game):
                folder, save, header, ln, additions, tools = self._village(game)
                people = ln.living(folder, game, 1)
                men = [v for v in people if v.sex == "Male"]
                women = [v for v in people if v.sex == "Female"]
                orphans = [v for v in people if not self._parents(ln, game, save.read_bytes(), v)[0][0]]
                right = next(v for v in people if self._parents(ln, game, save.read_bytes(), v)[0][0])
                stock, same, unsure = orphans[0], orphans[1], orphans[2]
                man, woman, man2 = men[0], women[0], men[1]
                buf = bytearray(save.read_bytes())
                self._put_parents(ln, game, buf, stock, man.identity, woman.identity)     # a man as the Mother
                self._put_parents(ln, game, buf, same, man.identity, man2.identity)       # two men
                self._put_parents(ln, game, buf, unsure, man.identity, ("Ihu", 3, 3))     # her sex not recorded
                save.write_bytes(bytes(buf))
                right_before = self._parents(ln, game, bytes(buf), right)
                births = _write(folder, f"Births and Conceptions/Virtual Villagers {game} Births and Conceptions "
                                        "Log 1.txt",
                                f"{header}\n" + _birth(1, stock.name, man.identity, woman.identity)
                                + _birth(2, right.name, *right_before))
                history = _write(folder, "Tribe History/Village History 1.txt",
                                 f"=== Virtual Villagers {game} -- 2026-11-20 10:00:00 ===\n{header}\n"
                                 + _snapshot_entry(1, stock, woman.identity, man.identity))
                kinds = additions.plan(folder, game, 1)
                kind = next(k for k in kinds if k.id == pfs.KIND_ID)
                self.assertEqual(len(kind.questions), 1, "the unsure pair is asked about, nothing else")
                (key, question), = kind.questions.items()
                self.assertIn("Ihu", question.text)
                yes = next(o for o in question.options if o.startswith("Yes"))
                result = tools.approve_repair(folder, game, 1, FakeProcesses(), datetime(2026, 11, 27, 12, 0),
                                              chosen={pfs.KIND_ID}, answers={key: yes}, kinds=kinds, rearm=False)
                data = save.read_bytes()
                self.assertEqual(self._parents(ln, game, data, stock), (woman.identity, man.identity),
                                 "a man as the Mother and a woman as the Father: she is the Mother, with her looks")
                self.assertEqual(self._parents(ln, game, data, same), (man.identity, man2.identity),
                                 "two men: the carrier stays the Mother")
                self.assertEqual(self._parents(ln, game, data, unsure), (("Ihu", 3, 3), man.identity),
                                 "asked, and answered yes")
                self.assertEqual(self._parents(ln, game, data, right), right_before, "recorded right: left alone")
                text = births.read_bytes().decode("latin-1")
                self.assertIn(f"  Mother: {woman.name}\r\n    Head: {woman.head}\r\n    Body: {woman.body}\r\n"
                              f"  Father: {man.name}\r\n    Head: {man.head}\r\n    Body: {man.body}\r\n", text)
                self.assertIn(f"  Note: Carried by {man.name}, who is male (named as the Father; {woman.name} is "
                              "named as the Mother)", text)
                self.assertIn(f"  Mother: {right_before[0][0]}\r\n    Head: {right_before[0][1]}\r\n", text,
                              "the Birth recorded right is as it was")
                self.assertEqual(text.count("Carried by"), 1)
                snap = history.read_bytes().decode("latin-1")
                self.assertIn(f"    Father: {man.name}\r\n      Head: {man.head}\r\n      Body: {man.body}\r\n"
                              f"    Mother: {woman.name}\r\n      Head: {woman.head}\r\n", snap)
                self.assertIsNotNone(result.backup, "the save folder was backed up first")
                repairs = "".join(p.read_bytes().decode("latin-1") for p in folder.rglob("*Repairs*.txt"))
                self.assertIn("Parents put by their sex", repairs, "listed in the Repairs log")
                # Planned again: nothing left to do.
                again = next(k for k in additions.plan(folder, game, 1) if k.id == pfs.KIND_ID)
                self.assertEqual((again.questions, again.replaces, again.inserts), ({}, [], []))

    def test_a_rename_keeps_the_carrier_found(self):
        """Codex (#887): a rename through the name tools renames the names inside the "Carried by" note too (the
        carrier's and the Mother's, by their parent lines' name and looks), and the carrier is found by the note
        whatever name it gives."""
        folder, save, header, ln, additions, tools = self._village(5)
        people = ln.living(folder, 5, 1)
        man = next(v for v in people if v.sex == "Male")
        woman = next(v for v in people if v.sex == "Female")
        note = (f"  Note: Carried by {man.name}, who is male (named as the Father; {woman.name} is named as the "
                "Mother)\n")
        record = _birth(1, "Coral", woman.identity, man.identity).replace("  Born as: Single birth\n",
                                                                         "  Born as: Single birth\n" + note)
        births = _write(folder, "Births and Conceptions/Virtual Villagers 5 Births and Conceptions Log 1.txt",
                        f"{header}\n{record}")
        for who, new in ((man, "Ahi Renamed"), (woman, "Vaihi Renamed")):
            with self.subTest(renamed=who.name):
                plan = ln.Plan({})
                ln._plan_logs(plan, folder, 5, 1, {who.identity: new}, {})
                (change,) = [c for c in plan.changes if c.path == births]
                text = change.updated.decode("latin-1").replace("\r\n", "\n")
                carrier = man.name if who is woman else new
                mother = woman.name if who is man else new
                self.assertIn(f"  Note: Carried by {carrier}, who is male (named as the Father; {mother} is named as "
                              "the Mother)", text)
                lines = text.split("\n")
                birth = next(b for b in additions.blocks(births, lines) if additions.is_birth(b.heading))
                self.assertEqual(additions.birth_carrier(birth), (carrier, man.head, man.body))
        # A note an older rename left behind still names the Father as the carrier, by his own line.
        stale = record.replace(f"  Father: {man.name}\n", "  Father: Someone Else\n")
        lines = (f"{header}\n{stale}").split("\n")
        birth = next(b for b in additions.blocks(births, lines) if additions.is_birth(b.heading))
        self.assertEqual(additions.birth_carrier(birth), ("Someone Else", man.head, man.body))

    def test_a_new_home(self):
        """A New Home keeps the parents in its Parentage Records (VVFP VV1 Parentage.dll), not on the record."""
        import vv_parents_follow_sex as pfs
        folder, save, header, ln, additions, tools = self._village(1)
        people = ln.living(folder, 1, 1)
        man = next(v for v in people if v.sex == "Male")
        woman = next(v for v in people if v.sex == "Female")
        child = people[-1]
        right = people[-2]
        raw = bytearray(b"VP02" + bytes(8) + bytes(256 * 36) + bytes(256 * 92))

        def entry(i: int, who, mother, father):
            occ = 12 + i * 36
            raw[occ] = 1 if who.sex == "Male" else 2
            raw[occ + 2], raw[occ + 3] = who.head + 1, who.body + 1
            raw[occ + 8:occ + 8 + len(who.name)] = who.name.encode("latin-1")
            e = pfs.VV1_ENTRIES + i * 92
            raw[e:e + 4] = bytes((father.head + 1, father.body + 1, mother.head + 1, mother.body + 1))
            raw[e + 8:e + 8 + len(father.name)] = father.name.encode("latin-1")
            raw[e + 36:e + 36 + len(mother.name)] = mother.name.encode("latin-1")
        entry(5, child, man, woman)                     # a man as the Mother
        entry(6, right, woman, man)                     # recorded right
        target = pfs._vv1_files(folder, 1)[0]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(bytes(raw))
        births = _write(folder, "Births and Conceptions/Virtual Villagers 1 Births and Conceptions Log 1.txt",
                        f"{header}\n" + _birth(1, child.name, man.identity, woman.identity))
        kinds = additions.plan(folder, 1, 1)
        tools.approve_repair(folder, 1, 1, FakeProcesses(), datetime(2026, 11, 27, 12, 0), chosen={pfs.KIND_ID},
                             answers={}, kinds=kinds, rearm=False)
        after = target.read_bytes()
        e = pfs.VV1_ENTRIES + 5 * 92
        self.assertEqual(pfs._vv1_entry_parents(after, e), (woman.identity, man.identity))
        e = pfs.VV1_ENTRIES + 6 * 92
        self.assertEqual(pfs._vv1_entry_parents(after, e), (woman.identity, man.identity), "left alone")
        self.assertIn(f"  Mother: {woman.name}\r\n", births.read_bytes().decode("latin-1"))

    def test_the_files_keyed_by_the_parents_follow_the_child(self):
        """Codex (#887): every per-villager file whose identity holds the parents' names is re-keyed with the save --
        Change Appearance's Original Looks (so Reset to original still finds the child's original), the island
        events' story traits and The Tree of Life's yellow fruit tree roster."""
        import vv_original_look as ol
        import vv_parents_follow_sex as pfs
        for game in (4, 5):
            with self.subTest(game=game):
                folder, save, header, ln, additions, tools = self._village(game)
                people = ln.living(folder, game, 1)
                man = next(v for v in people if v.sex == "Male")
                woman = next(v for v in people if v.sex == "Female")
                child = next(v for v in people if not self._parents(ln, game, save.read_bytes(), v)[0][0]
                             and v not in (man, woman))
                buf = bytearray(save.read_bytes())
                self._put_parents(ln, game, buf, child, man.identity, woman.identity)   # a man as the Mother
                save.write_bytes(bytes(buf))
                f = ln.FIELDS[game]
                before = {v.seen.at: v for v in ol.living(folder, game, 1)}[child.at]
                record, count = before.seen.record, 150
                entries = [ol.Entry() for _ in range(count)]
                entries[record] = ol.Entry(roster=before.id, id=before.id, head=7, body=8, mask=0, source=1)
                looks_path = ol.path(folder, 1)
                looks_path.parent.mkdir(parents=True, exist_ok=True)
                looks_path.write_bytes(ol.build(ol.OriginalLooks(game, entries, [ol.Logged(before.id, 7, 8, 0, 1)])))
                worn = ln._store_identity(game, buf, child.at, f)
                traits = bytearray(b"VST1" + struct.pack("<II", game, count) + bytes(count * 9 + 255 * 4))
                struct.pack_into("<I", traits, 12 + 4 * record, worn)
                struct.pack_into("<I", traits, 12 + 4 * count + 4 * record, worn)
                traits_path = ln._data_file(folder, "Island Events", "Island Event Story Traits - Save 1.dat")
                traits_path.parent.mkdir(parents=True, exist_ok=True)
                traits_path.write_bytes(bytes(traits))
                fruit_path = ln._data_file(folder, "Fruit Trees", "Virtual Villagers 4 Yellow Fruit Tree - Save 1.dat")
                if game == 4:
                    fruit = bytearray(b"VV4F" + struct.pack("<7I", 1, 4, 1, 500, 3, 1, 0) + bytes(256 * 4))
                    struct.pack_into("<I", fruit, 32 + 4 * record, ln._mask_identities(game, buf, child.at)[0])
                    fruit_path.parent.mkdir(parents=True, exist_ok=True)
                    fruit_path.write_bytes(bytes(fruit))
                kinds = additions.plan(folder, game, 1)
                # The plan re-keys the logged look too (the backfill after the Repair may then spend it).
                planned, _who = pfs.plan_save(folder, game, 1, next(k for k in kinds if k.id == pfs.KIND_ID), {})
                (looks_change,) = [c for c in planned if c.path == looks_path]
                planned_looks = ol.parse(looks_change.updated, game)
                self.assertEqual(planned_looks.logged[0].id, planned_looks.entries[record].id)
                self.assertNotEqual(planned_looks.logged[0].id, before.id)
                tools.approve_repair(folder, game, 1, FakeProcesses(), datetime(2026, 11, 27, 12, 0),
                                     chosen={pfs.KIND_ID}, answers={}, kinds=kinds, rearm=False)
                data = save.read_bytes()
                self.assertEqual(self._parents(ln, game, data, child), (woman.identity, man.identity))
                after = {v.seen.at: v for v in ol.living(folder, game, 1)}[child.at]
                self.assertNotEqual(after.id, before.id, "the identity holds the parents' names, in their order")
                looks = ol.parse(looks_path.read_bytes(), game)
                self.assertEqual((looks.entries[record].roster, looks.entries[record].id, looks.entries[record].head,
                                  looks.entries[record].body), (after.id, after.id, 7, 8),
                                 "Reset to original still finds the child's original")
                new_worn = ln._store_identity(game, data, child.at, f)
                raw = traits_path.read_bytes()
                self.assertEqual(struct.unpack_from("<I", raw, 12 + 4 * record)[0], new_worn)
                self.assertEqual(struct.unpack_from("<I", raw, 12 + 4 * count + 4 * record)[0], new_worn)
                if game == 4:
                    self.assertEqual(struct.unpack_from("<I", fruit_path.read_bytes(), 32 + 4 * record)[0],
                                     ln._mask_identities(game, data, child.at)[0])


if __name__ == "__main__":
    unittest.main()
