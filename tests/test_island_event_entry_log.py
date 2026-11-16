"""A branching Custom Island Event keeps ONE entry in the Island Events log, matching the save at every save.

The owner (2026-11-12): the Island Events log keeps one entry per branching event -- its title, its "Choice:"
line, then every change in page order as it happens -- and (the standing rule "logs must match the save") at
every save during the event the log already holds the entry so far; later pages continue that SAME entry.

native/parentage_export/parentage_export.c WriteVillageEventEntry holds the entry as a record that is REPLACED as
the event goes on, and each save writes what it has gained onto the same entry, append-only
(append_event_entry); native/parentage_export/event_entry_harness.c runs the companion's source against real
files in a throwaway Documents folder:

* pages 1 and 2, then a save: the log holds one entry with both pages (full names), left open;
* a quit, a reload told what the save's log holds, page 3 and the end, then a save: ONE entry with pages 1-3 in
  order, nothing twice, closed with its blank line;
* another island event after it is its own record, numbered next;
* an entry left open when another record comes first: closed first, then a marked "(continued) Island event <n>"
  part with only its new lines, never numbered or counted.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native"
EXPORT = NATIVE / "parentage_export" / "parentage_export.c"
VS_TOOLS = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231")
CL = VS_TOOLS / "bin" / "Hostx64" / "x86" / "cl.exe"
SDK = Path(r"C:\Program Files (x86)\Windows Kits\10")
SDK_VERSION = "10.0.26100.0"
HARNESS_CHECKS = 18


class TheEntrySource(unittest.TestCase):
    def test_the_entry_is_a_replaced_held_record_written_at_each_save(self):
        source = EXPORT.read_text(encoding="utf-8")
        self.assertIn("WriteVillageEventEntry=_WriteVillageEventEntry@20",
                      (NATIVE / "parentage_export" / "parentage_export.def").read_text(encoding="utf-8"))
        flush = source[source.index("static void flush_pending("):]
        flush = flush[:flush.index("\n}\n")]
        self.assertIn("append_event_entry(g, village, entry->open_entry - 1, text)", flush)
        # Any other Island Events record closes an open entry first.
        append = source[source.index("static int append_record("):]
        append = append[:append.index("\n}\n")]
        self.assertIn("log_family_of(kind) == LOG_EVENTS && events_tail_open(path)", append)


@unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
class EventEntryHarness(unittest.TestCase):
    def test_one_entry_matches_the_save_at_every_save(self):
        with tempfile.TemporaryDirectory(prefix="vvfp_event_entry_") as out:
            exe = Path(out) / "event_entry_harness.exe"
            build = subprocess.run(
                [str(CL), "/nologo", f"/Fo{out}\\", "/O2", "/MT",
                 "/I", str(VS_TOOLS / "include"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "um"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "shared"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "ucrt"),
                 "/I", str(NATIVE / "shared"),
                 str(NATIVE / "parentage_export" / "event_entry_harness.c"),
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


if __name__ == "__main__":
    unittest.main()
