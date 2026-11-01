"""A record goes to the log of the save the game had LOADED when it was made (all five games).

The village header (" (Save N)") is published only when a village is saved, so after the player saves
village A and loads B in the same session it still names A until B is saved.  The parentage companion
(native/parentage_export/parentage_export.c, one DLL for all five games) read it in three places:

* a HELD record (made before the village on screen was saved) was written at the next save under that
  save's header.  The owner's Secret City, 2026-10-31: Conceptions 312 and 316 (Save 2's Kiwi Jumapili
  and Matate Jumapili with Motu Okelani) were written into Save 1's Births and Conceptions log at Save
  1's save.  The owner's decision: a held record goes to its own save's log -- the slot the game had
  loaded when it was made, captured then; one made with no slot loaded (the pre-tribe simulation) is
  written as before;
* a record written at once under the recalled header because the table matched the tribe saved last:
  a copy of that village in another slot passed;
* the "Custom title:" line (and VillageCustomTitle, which VVFP Island Events compares) and New
  Believers' Former Heathen titles: read from the recalled header's slot's files.

native/parentage_export/held_slot_harness.c runs the companion's source against a stand-in save manager.
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
HARNESS_CHECKS = 29


def function(name: str) -> str:
    source = EXPORT.read_text(encoding="utf-8")
    at = re.search(r"^static [^\n;]*\b" + re.escape(name) + r"\(", source, re.M)
    body = source[at.start():]
    return body[:body.index("\n}\n")]


class TheLoadedSaveDecides(unittest.TestCase):
    def test_a_held_record_keeps_the_slot_it_was_made_in(self):
        self.assertIn("entry->slot = game_slot_now(game_id);", function("hold_record"))
        goes = function("pending_goes_to")
        self.assertIn("entry->slot == 0 || header_slot == 0 || entry->slot == header_slot", goes)
        flush = function("flush_pending")
        self.assertIn("int header_slot = vv_log_header_slot(village);", flush)
        self.assertIn("int ours = pending_goes_to(entry, game_id, header_slot);", flush)
        # Another slot's record is kept, never written here and never dropped.
        self.assertIn("if (ours && !stopped) {", flush)
        self.assertIn("pending[kept++] = *entry;", flush)

    def test_a_record_is_written_at_once_only_into_the_loaded_saves_log(self):
        emit = function("emit_record")
        self.assertIn("game_slot_now(game_id) == 0 || game_slot_now(game_id) == vv_log_header_slot(village)", emit)
        self.assertIn("if (pending_for(game_id, vv_log_header_slot(village)) == 0) {", emit)

    def test_titles_read_the_loaded_saves_files(self):
        custom = function("record_custom_title")
        self.assertNotIn("vv_village_recall", custom)
        self.assertIn("slot = village_files_slot(game_id);", custom)
        special = function("record_special_title")
        self.assertNotIn("vv_village_recall", special)
        self.assertIn("vv_former_load(village_files_slot(game_id), former)", special)
        files = function("village_files_slot")
        self.assertIn("if (game_has_save_manager(game_id)) {\n        return game_slot_now(game_id);", files)
        # The published header only with no save manager at all (before the game builds it).
        self.assertLess(files.index("game_has_save_manager"), files.index("vv_village_recall"))

    def test_the_header_is_read_only_where_a_save_names_it(self):
        """The recalled header is still read by emit_record (the record's village, checked against the
        game's own slot) and nowhere else in the companion."""
        source = EXPORT.read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"vv_village_recall\(", source)), 2, "emit_record and village_files_slot")


@unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
class HeldSlotHarness(unittest.TestCase):
    def test_records_and_titles_follow_the_loaded_save(self):
        with tempfile.TemporaryDirectory(prefix="vvfp_held_slot_") as out:
            exe = Path(out) / "held_slot_harness.exe"
            build = subprocess.run(
                [str(CL), "/nologo", f"/Fo{out}\\", "/O2", "/MT",
                 "/I", str(VS_TOOLS / "include"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "um"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "shared"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "ucrt"),
                 "/I", str(NATIVE / "shared"),
                 str(NATIVE / "parentage_export" / "held_slot_harness.c"),
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
