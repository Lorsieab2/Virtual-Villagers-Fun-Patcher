"""A New Home's Golden Child's grave: "Golden Child" under Job, a child's epitaph (the owner, 2026-11-07: "A New
Home's Golden Child gets no grave title at all. In case he ever dies due to an island event or something, his job
should be "Golden Child" and his epitaph should be either of the default child ones.").

How the grave is known to be his: the grave keeps no family number -- the burial 0x448F70..0x448FF1 copies only
the name, the age, the best skill and its job -- so the Cause of Death companion marks his grave's entry at the
burial (family 199 at record +0x36C, the Villager Detail panel's own test 0x41FBDC) in its Graves file (flag 2,
VCD1 version 3).  The Job line is Children's Graves Say Apprentice's rule: only with that row in the exe the
companion puts the game's own string 0x5F "Golden Child" in the line's buffer right before the popup draws it
(0x43667C, native/vvfp_cause_of_death/cod_vv12.inc vv1_job_line).

Checked here:
  * the grave dialog, run in unicorn from the job test (0x436501) to the skill line's draw (0x43669A), stock and
    with Children's Graves Say Apprentice, for the Golden Child's grave and an ordinary child's grave with the same
    numbers: the drawn line, that every path meets the hook site with the line at [esp+0x14], and the hook's
    write giving "Golden Child" for his marked grave only;
  * string 0x5F is the game's "Golden Child", the burial copies no family number, the hook site is the companion's;
  * the patcher's Graves file reader/writer (src/vv_graves.py) keeps the flag (version 3);
  * Repair Saves & Logs (src/vv_log_additions.py plan_apprentice): his old Death and Epitaph changed records get
    "Golden Child", and an empty epitaph gets the child epitaph his grave holds.
The companion itself (burial mark, epitaph pick, Deaths log line, file bytes, a new session) is run by
native/vvfp_cause_of_death/cause_files_harness.c section 12 (tests/test_deaths_log_and_graves_file.py).
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

import test_apprentice_faith_puddles as apf  # noqa: E402
import test_apprentice_repair as rep  # noqa: E402
import vv_graves  # noqa: E402
import vv_last_names as ln  # noqa: E402
import vv_log_additions as additions  # noqa: E402

if apf.HAVE_EMULATOR:
    import pefile
    from unicorn import UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_EBX, UC_X86_REG_EIP, UC_X86_REG_ESP

JOB_TEST, HOOK, DRAW = 0x436501, 0x43667C, 0x43669A
STRING, PRINT = 0x433970, 0x44B23D
GOLDEN_STRING = 0x5F
PARENT = 2                      # the best-skill pick 0x43B520 keeps Parenting on a tie: his grave's job


def string_rows(exe: bytes) -> dict[int, int]:
    """The game's built-in string table (rows of id + four languages' pointers, English first): id -> English."""
    pe = pefile.PE(data=exe, fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    va = pe.get_rva_from_offset(exe.index(b"Golden Child\x00")) + base
    row = exe.index(struct.pack("<I", va)) - 4
    while struct.unpack_from("<I", exe, row - 20)[0] == struct.unpack_from("<I", exe, row)[0] - 1:
        row -= 20
    out = {}
    while True:
        ident, english = struct.unpack_from("<II", exe, row)
        if out and ident != max(out) + 1:
            return out
        out[ident] = english
        row += 20


def c_string(m, va: int) -> bytes:
    return bytes(m.uc.mem_read(va, 64)).split(b"\0", 1)[0]


def run_dialog(exe: bytes, *, value: int, job: int, age: int, companion_golden: bool = False):
    """The grave dialog from its job test to the skill line's draw: (the drawn line, the buffer at the hook site
    and whether it was the draw's argument)."""
    m = apf.Machine(exe)
    rows = string_rows(exe)
    m.stub(STRING, lambda mm: rows[mm.r32(mm.uc.reg_read(UC_X86_REG_ESP) + 4)], 4)

    def sprintf(mm):            # cdecl (buffer, text): the rank's string, no arguments here
        sp = mm.uc.reg_read(UC_X86_REG_ESP)
        text = c_string(mm, mm.r32(sp + 8))
        mm.uc.mem_write(mm.r32(sp + 4), text + b"\0")
        return len(text)
    m.stub(PRINT, sprintf, 0)
    seen = {}

    def at_hook(uc, _a, _s, _d):
        sp = uc.reg_read(UC_X86_REG_ESP)
        seen["buffer"] = sp + 0x14
        seen["line"] = c_string(m, sp + 0x14)
        if companion_golden:    # vv1_job_line: lstrcpyA(esp + 0x14, string(0x5F))
            uc.mem_write(sp + 0x14, c_string(m, rows[GOLDEN_STRING]) + b"\0")
    m.uc.hook_add(UC_HOOK_CODE, at_hook, begin=HOOK, end=HOOK)
    S = m.SCRATCH
    dialog, manager = S, S + 0x1000
    m.w32(dialog + 0x60, 0)
    m.w32(dialog + 0x74, manager)
    m.w32(dialog + 0x7C, S + 0x800)
    m.w32(manager + 0xA338, value)
    m.w32(manager + 0xA33C, job)
    m.w32(manager + 0xA340, age)
    m.uc.reg_write(UC_X86_REG_EBX, dialog)
    m.uc.reg_write(UC_X86_REG_ESP, m.STACK + 0x80000)
    m.uc.emu_start(JOB_TEST, DRAW, count=2000)
    assert m.uc.reg_read(UC_X86_REG_EIP) == DRAW
    drawn = m.r32(m.uc.reg_read(UC_X86_REG_ESP))
    return c_string(m, drawn).decode("cp1252"), seen, drawn == seen.get("buffer")


@unittest.skipUnless(apf.HAVE_EMULATOR, "unicorn/pefile not installed")
class GoldenChildGraveDialog(unittest.TestCase):
    def setUp(self):
        self.stock = apf.rendered(1, ())
        self.patched = apf.rendered(1, (apf.APPRENTICE[1],))

    def test_string_0x5f_is_the_games_golden_child_the_panels_own(self):
        rows = string_rows(self.stock)
        pe = pefile.PE(data=self.stock, fast_load=True)
        at = pe.get_offset_from_rva(rows[GOLDEN_STRING] - pe.OPTIONAL_HEADER.ImageBase)
        self.assertEqual(self.stock[at:at + 13], b"Golden Child\x00")
        at = pe.get_offset_from_rva(rows[0x56] - pe.OPTIONAL_HEADER.ImageBase)
        self.assertEqual(self.stock[at:at + 12], b"Apprentice \x00")
        # The Villager Detail panel 0x41FBDC: family (+0x36C) 199 -> string 0x5F in place of the rank.
        off = pe.get_offset_from_rva(0x41FBDC - 0x400000)
        self.assertEqual(self.stock[off:off + 17].hex().upper(), "81B96C030000C70000007515" "8B4D2C6A5F")

    def test_the_grave_keeps_no_family_number(self):
        """The burial's grave write 0x448F70..0x448FF6 reads the record's age, best skill and name, never +0x36C:
        his grave is the same as any child's of his name, age and skills."""
        pe = pefile.PE(data=self.stock, fast_load=True)
        off = pe.get_offset_from_rva(0x448F70 - 0x400000)
        block = self.stock[off:off + 0x448FF6 - 0x448F70]
        self.assertNotIn(struct.pack("<I", 0x36C), block)
        for field in (0xA340, 0xA33C, 0xA338):
            self.assertIn(struct.pack("<I", field), block)

    def test_the_line_stock_with_the_row_and_with_the_companions_mark(self):
        # The Golden Child: 5 years (100 age units), every skill 100 -> Parenting 100; a child with the same numbers.
        grave = dict(value=100, job=PARENT, age=100)
        self.assertEqual(run_dialog(self.stock, **grave)[0], "Master Parent")
        self.assertEqual(run_dialog(self.patched, **grave)[0], "Apprentice Parent")
        self.assertEqual(run_dialog(self.patched, **grave, companion_golden=True)[0], "Golden Child")
        # The stock exe with the companion: the companion writes only with the row in (cod_apprentice_patched),
        # so the run without the write is the stock line above.

    def test_every_path_meets_the_hook_with_the_line_in_its_buffer(self):
        for exe in (self.stock, self.patched):
            for job in range(0, 6):
                for value in (19, 20, 100):
                    for age in (100, 280):
                        line, seen, same = run_dialog(exe, value=value, job=job, age=age)
                        case = (exe is self.patched, job, value, age)
                        self.assertIn("buffer", seen, case)
                        self.assertTrue(same, case)
                        self.assertEqual(seen["line"].decode("cp1252"), line, case)
                        golden, _seen, _same = run_dialog(exe, value=value, job=job, age=age, companion_golden=True)
                        self.assertEqual(golden, "Golden Child", case)

    def test_the_hook_site_is_the_companions_and_the_rows_bytes_leave_it(self):
        pe = pefile.PE(data=self.patched, fast_load=True)
        for exe in (self.stock, self.patched):
            off = pe.get_offset_from_rva(HOOK - 0x400000)
            self.assertEqual(exe[off:off + 6].hex().upper(), "8B1508B64800")
        row = json.loads((ROOT / "data" / "vv1_cause_of_death_feature.json").read_text(encoding="utf-8"))
        self.assertIn({"va": "0x43667C", "stock_bytes": "8B1508B64800"},
                      [{"va": d["va"], "stock_bytes": d["stock_bytes"]} for d in row["runtime_detours"]])
        src = (ROOT / "native" / "vvfp_cause_of_death" / "cod_vv12.inc").read_text(encoding="utf-8")
        self.assertIn('cod_add(0x43667Cu, "8B1508B64800", vv1_job_line);', src)
        self.assertIn("(regs[R_ESP] + 0x14u)", src)
        self.assertIn("0x433970u)(*(void *const *)(popup + 0x7C), 0, 0x5F)", src)
        self.assertIn("cod_slot_golden(slot, manager + GRV[1].graves + (size_t)slot * GRV[1].stride) && "
                      "cod_apprentice_patched()", src)
        # His epitaph: always the child pair (cod_epitaph_for), the mark set from family 199 at the burial.
        self.assertIn("if (golden || *(const int *)(grave + g->age) < 360) {", src)
        self.assertIn("e.entry.golden = (unsigned char)cod_record_golden(record);", src)
        self.assertIn("*(const int *)(record + VV1_FAMILY) == GOLDEN_FAMILY", src)

    def test_both_rows_say_so(self):
        apprentice = json.loads((ROOT / "data" / "vv1_apprentice_graves_feature.json").read_text(encoding="utf-8"))
        cod = json.loads((ROOT / "data" / "vv1_cause_of_death_feature.json").read_text(encoding="utf-8"))
        self.assertIn("**With Show Cause of Death and Age at Death on Graves ticked too,** the Golden Child's grave "
                      "says \"Golden Child\" under Job", apprentice["description"])
        self.assertIn("**With Children's Graves Say Apprentice ticked too,** the Golden Child's grave says \"Golden "
                      "Child\" under Job", cod["description"])
        self.assertIn("the Golden Child's is always one of the two child epitaphs", cod["description"])
        for game in (2, 3, 5):
            other = json.loads((ROOT / "data" / f"vv{game}_apprentice_graves_feature.json").read_text(encoding="utf-8"))
            self.assertNotIn("Golden Child", json.dumps(other))


def vcd1_entry(place: int, fp: int, epitaph: int, flags: int, text: bytes = b"") -> bytes:
    return struct.pack("<HHIbBBB", 0, place, fp, 3, epitaph, flags, 0) + text.ljust(32, b"\0")


class GravesFileVersion3(unittest.TestCase):
    def test_read_and_written_with_the_flag(self):
        e = vcd1_entry(2, 1234, 13, 2)
        data = struct.pack("<4sIII", b"VCD1", 3, 1, 1) + e
        entries = vv_graves._vcd1_entries(data, 1)
        self.assertEqual([bytes(x) for x in entries], [e])
        self.assertEqual(vv_graves._sidecar_values(1, e)["epitaph"], "Loving and Special")
        self.assertEqual(vv_graves._vcd1_bytes(1, entries), data)
        # The flag outside version 3 is not the companion's file: set aside, never read.
        self.assertIsNone(vv_graves._vcd1_entries(struct.pack("<4sIII", b"VCD1", 2, 1, 1) + e, 1))
        # Without the flag: version 1 as before.
        plain = vcd1_entry(2, 1234, 13, 0)
        self.assertEqual(struct.unpack_from("<I", vv_graves._vcd1_bytes(1, [bytearray(plain)]), 4)[0], 1)
        # The player's own epitaph over his grave: flags 3, both kept.
        custom = vcd1_entry(2, 1234, 0, 3, b"Our golden boy")
        self.assertEqual(vv_graves._sidecar_values(1, custom)["epitaph"], "Our golden boy")


GOLDEN_LOG = (f"{rep.VILLAGE}\n"
              "Death 1\n  Name: Lulu Chuchip\n  Special villager: Golden Child\n  Age at death: 100\n  Sex: Male\n"
              "  Cause of death: Unknown causes\n  Grave: Master Parent\n  Epitaph: (none)\n\n"
              "Epitaph changed\n  Name: Lulu Chuchip\n  Age at death: 100\n  Grave: Apprentice Parent\n"
              "  Old epitaph: Loving and Special\n  New epitaph: Our golden boy\n\n"
              # Another five-year-old with the same numbers: an ordinary child's grave.
              "Death 2\n  Name: Kiki\n  Age at death: 100\n  Sex: Female\n  Cause of death: Disease\n"
              "  Grave: Master Parent\n  Epitaph: (none)\n\n")


class GoldenChildRepair(unittest.TestCase):
    def fixture(self, rows):
        f = rep.Fixture(1, rows)
        f.log.write_bytes(GOLDEN_LOG.encode("cp1252"))
        path = vv_graves.graves_file(f.folder, 1, 1)       # where the companion writes it for this save
        path.parent.mkdir(parents=True, exist_ok=True)
        fp = ln.grave_fingerprint(b"Lulu Chuchip", 0x1C, 100)
        path.write_bytes(
            struct.pack("<4sIII", b"VCD1", 3, 1, 1) + vcd1_entry(0, fp, 13, 2))
        return f

    def plan(self, f):
        return next(k for k in additions.plan(f.folder, 1, 1, f.game_folders) if k.id == "apprentice")

    def test_his_records_get_golden_child_and_the_epitaph_his_grave_holds(self):
        f = self.fixture(["vv1_apprentice_graves", "vv1_cause_of_death"])
        try:
            kind = self.plan(f)
            lines = f.log.read_text(encoding="cp1252").split("\n")
            got = sorted((lines[i], new) for _p, i, new in kind.replaces)
            self.assertEqual(got, sorted([
                ("  Epitaph: (none)", "  Epitaph: Loving and Special"),
                ("  Grave: Master Parent", "  Grave: Golden Child"),
                ("  Grave: Apprentice Parent", "  Grave: Golden Child"),
                # Kiki: an ordinary child's rank line, the Apprentice repair's own.
                ("  Grave: Master Parent", "  Grave: Apprentice Parent")]))
            self.assertEqual([i for _p, i, new in kind.replaces if new == "  Grave: Apprentice Parent"],
                             [lines.index("  Name: Kiki") + 4])
            additions.apply(f.folder, [kind], {"apprentice"}, {})
            text = f.log.read_text(encoding="cp1252")
            self.assertEqual(text.count("  Grave: Golden Child\n"), 2)
            self.assertIn("  Epitaph: Loving and Special\n", text)
            self.assertEqual(self.plan(f).replaces, [], "planned again: nothing left")
        finally:
            f.close()

    def test_without_the_row_only_the_epitaph(self):
        f = self.fixture(["vv1_cause_of_death"])
        try:
            kind = self.plan(f)
            self.assertEqual([new for _p, _i, new in kind.replaces], ["  Epitaph: Loving and Special"])
        finally:
            f.close()


def write_graves(f, graves) -> None:
    """A New Home's grave table in the fixture's save (file offset 0xA320, 50 x 0x2C: name +0, best skill +0x1C,
    job +0x20, age +0x24)."""
    save = ln.save_path(f.folder, 1, 1)
    data = bytearray(save.read_bytes())
    for place, name, age in graves:
        at = 0xA320 + place * 0x2C
        data[at:at + 0x1C] = name.encode("cp1252").ljust(0x1C, b"\0")
        struct.pack_into("<iii", data, at + 0x1C, 100, PARENT, age)
    save.write_bytes(bytes(data))


class GoldenChildGraveMark(unittest.TestCase):
    """His grave buried before the companion marked it: Repair marks its Graves file entry (flag 2, version 3)
    when his Death record's name and age match exactly one grave; otherwise it is left and the check says why."""

    def fixture(self, graves, entries: bytes | None, version: int = 2):
        f = rep.Fixture(1, ["vv1_apprentice_graves", "vv1_cause_of_death"])
        f.log.write_bytes(GOLDEN_LOG.encode("cp1252"))
        write_graves(f, graves)
        self.dat = vv_graves.graves_file(f.folder, 1, 1)
        if entries is not None:
            self.dat.parent.mkdir(parents=True, exist_ok=True)
            self.dat.write_bytes(struct.pack("<4sIII", b"VCD1", version, 1, len(entries) // 44) + entries)
        return f

    def plan(self, f):
        return next(k for k in additions.plan(f.folder, 1, 1, f.game_folders) if k.id == "apprentice")

    def shown(self, f, place):
        """What the popup path reads for grave `place`: the companion's mark, as src/vv_graves.py reads it."""
        data = ln.save_path(f.folder, 1, 1).read_bytes()
        graves = vv_graves.read_graves(1, data)
        vv_graves._load_sidecar(f.folder, 1, 1, graves)
        return next(g for g in graves if g.place == place).values["grave"]

    def test_an_old_unmarked_grave_is_marked_and_the_file_copied_first(self):
        fp = ln.grave_fingerprint(b"Lulu Chuchip", 0x1C, 100)
        kiki = ln.grave_fingerprint(b"Kiki", 0x1C, 100)
        old = vcd1_entry(3, fp, 13, 0) + vcd1_entry(4, kiki, 12, 0)
        f = self.fixture([(3, "Lulu Chuchip", 100), (4, "Kiki", 100)], old, version=2)
        try:
            before = self.dat.read_bytes()
            self.assertEqual(self.shown(f, 3), "Apprentice Parent")
            kind = self.plan(f)
            self.assertEqual(len(kind.context["golden_marks"]), 1)
            checked = additions.tools.check_logs(f.folder, 1, 1, f.game_folders)
            self.assertIn("the Golden Child's grave is not marked as his", checked.text)
            done = additions.apply(f.folder, [kind], {"apprentice"}, {})
            after = self.dat.read_bytes()
            self.assertEqual(struct.unpack_from("<I", after, 4)[0], 3, "version 3")
            self.assertEqual(after[16 + 10], 2, "his entry: flag 2, epitaph kept")
            self.assertEqual(after[16 + 9], 13)
            self.assertEqual(after[16 + 44 + 10], 0, "the other child's entry is untouched")
            self.assertEqual(after[16:], before[16:16 + 10] + b"\x02" + before[16 + 11:])
            self.assertEqual(self.shown(f, 3), "Golden Child")
            self.assertEqual(self.shown(f, 4), "Apprentice Parent")
            copies = [p for p in f.folder.rglob("*") if p.is_file() and p != self.dat and p.read_bytes() == before]
            self.assertTrue(copies, "the Graves file is copied before it is changed")
            self.assertTrue(any(fix.name.endswith(self.dat.name) for fix in done["apprentice"]))
            self.assertNotIn("golden_marks", self.plan(f).context, "planned again: nothing left")
        finally:
            f.close()

    def test_a_grave_with_no_entry_gets_one_with_his_child_epitaph(self):
        f = self.fixture([(0, "Lulu Chuchip", 100)], None)
        try:
            kind = self.plan(f)
            additions.apply(f.folder, [kind], {"apprentice"}, {})
            data = self.dat.read_bytes()
            entries = vv_graves._vcd1_entries(data, 1)
            self.assertEqual(len(entries), 1)
            fp = ln.grave_fingerprint(b"Lulu Chuchip", 0x1C, 100)
            self.assertEqual(struct.unpack_from("<HHIb", entries[0], 0), (0, 0, fp, vv_graves.CAUSE_NONE))
            self.assertEqual((entries[0][9], entries[0][10]), (12, 2), "Curious and Playful, marked")
            self.assertEqual(self.shown(f, 0), "Golden Child")
            # His record had no epitaph: it gets the one the new entry holds (the grave and record agree).
            self.assertIn("  Epitaph: Curious and Playful\n", f.log.read_text(encoding="cp1252").split("Death 2")[0])
        finally:
            f.close()

    def test_an_ambiguous_match_is_left_and_reported(self):
        fp = ln.grave_fingerprint(b"Lulu Chuchip", 0x1C, 100)
        old = vcd1_entry(3, fp, 13, 0) + vcd1_entry(5, fp, 12, 0)
        f = self.fixture([(3, "Lulu Chuchip", 100), (5, "Lulu Chuchip", 100)], old)
        try:
            before = self.dat.read_bytes()
            kind = self.plan(f)
            self.assertNotIn("golden_marks", kind.context)
            self.assertTrue(any("2 graves in the save match his name and age at death" in n for n in kind.notes))
            checked = additions.tools.check_logs(f.folder, 1, 1, f.game_folders)
            self.assertIn("2 graves in the save match his name and age at death", checked.text)
            additions.apply(f.folder, [kind], {"apprentice"}, {})
            self.assertEqual(self.dat.read_bytes(), before, "untouched")
        finally:
            f.close()


if __name__ == "__main__":
    unittest.main()
