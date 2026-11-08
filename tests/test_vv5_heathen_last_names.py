"""New Believers' Heathens get last names (the owner, 2026-11-08).

"in vv5, please give heathens random last names thanks!!!! (they can share last names but be unrelated if
there's not enough default ones in the list, but try to make them all unique)".  The owner's answers: an
existing Heathen with no last name gets one the first time the patched game loads the village; a Heathen who
converts keeps it; a Heathen's last name does not count toward "Random from the existing Village Names" while
they are a Heathen.

VVFP Last Names.dll names them (native/vvfp_last_names, HEATHENS): native/vvfp_last_names/
heathen_names_harness.c runs the shipped source over New Believers' own table layout, and test_last_names.py
runs the shipped DLL inside the stock executable.  Here: the harness, and the patcher's side -- the record's
"heathen" lines are kept by every rewrite, and the village's names leave the Heathens out.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import vv_last_names as ln  # noqa: E402
from test_last_names_rename import NoGame  # noqa: E402

NATIVE = ROOT / "native" / "vvfp_last_names"
VS_TOOLS = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231")
CL = VS_TOOLS / "bin" / "Hostx64" / "x86" / "cl.exe"
SDK = Path(r"C:\Program Files (x86)\Windows Kits\10")
SDK_VERSION = "10.0.26100.0"
# 1: 5; 2: 4; 3: 7; 4: 4; 5: 4; 6: 2; 7: 3; 8: 1.
HARNESS_CHECKS = 5 + 4 + 7 + 4 + 4 + 2 + 3 + 1


@unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
class TheShippedCode(unittest.TestCase):
    def test_heathens_get_unique_random_last_names(self):
        with tempfile.TemporaryDirectory(prefix="vvfp_heathen_names_") as out:
            exe = Path(out) / "heathen_names_harness.exe"
            build = subprocess.run(
                [str(CL), "/nologo", f"/Fo{out}\\", "/O2", "/MT", "/W4",
                 "/I", str(VS_TOOLS / "include"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "um"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "shared"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "ucrt"),
                 str(NATIVE / "heathen_names_harness.c"),
                 "/link",
                 f"/LIBPATH:{VS_TOOLS / 'lib' / 'x86'}",
                 f"/LIBPATH:{SDK / 'Lib' / SDK_VERSION / 'um' / 'x86'}",
                 f"/LIBPATH:{SDK / 'Lib' / SDK_VERSION / 'ucrt' / 'x86'}",
                 f"/OUT:{exe}", "kernel32.lib", "shell32.lib"],
                capture_output=True, text=True, cwd=out, timeout=300)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            self.assertNotIn("warning", build.stdout.lower(), build.stdout)
            result = subprocess.run([str(exe), str(Path(out) / "documents")], capture_output=True, text=True,
                                    cwd=out, timeout=300)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"== {HARNESS_CHECKS} check(s), 0 failure(s) ==", result.stdout)


def _record(folder: Path, text: str) -> Path:
    path = ln.record_path(folder, 5, 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


class TheRecord(unittest.TestCase):
    def test_heathen_lines_are_read_and_kept_by_every_rewrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = _record(folder, "VVFP LAST NAMES v1 game=5\nrule\tmother\nused\tAkikai\n"
                                   "heathen\tWikimak\nheathen\tKaimana\tTama\t3\t4\nheathen\tbad\tline\n")
            self.assertEqual(ln.read_heathens(folder, 5, 1), {"Wikimak", "Kaimana"})
            self.assertEqual(ln.read_record(folder, 5, 1)[0], "mother", "an earlier reader's lines are unchanged")
            self.assertEqual(ln.read_used(folder, 5, 1), {"Akikai"}, "a Heathen's name is no used line")
            ln.write_record(folder, 5, 1, "village", {}, used={"Alosaka"})
            text = path.read_text(encoding="utf-8")
            self.assertIn("heathen\tWikimak\nheathen\tKaimana\tTama\t3\t4\n", text)
            self.assertIn("rule\tvillage\n", text)
            self.assertEqual(ln.read_used(folder, 5, 1), {"Akikai", "Alosaka"})
            ln.save_arrivals(folder, 5, 1, False, processes=NoGame())
            self.assertEqual(ln.read_heathens(folder, 5, 1), {"Wikimak", "Kaimana"}, "the arrivals toggle keeps them")

    def test_only_new_believers_has_heathens(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(ln.heathen_identities(Path(tmp), 3, 1), set())


class TheVillagesNames(unittest.TestCase):
    """village_names: the record's used lines and every villager's -- never a Heathen's until they convert."""

    def people(self):
        tribe = ln.Living(0, "Ana Akikai", "Female", 1, 1, 1, "Akikai")
        heathen = ln.Living(0, "Tama Wikimak", "Male", 2, 2, 1, "Akikai")
        convert = ln.Living(0, "Pua Kaimana", "Female", 3, 3, 1, "Akikai")
        mommy = ln.Living(0, "Hina Alosaka", "Female", 4, 4, 1, "Akikai")
        child = ln.Living(0, "Keo", "Male", 5, 5, 1, "Akikai")
        return [tribe, heathen, convert, mommy, child], {child.identity: (None, mommy.identity)}

    def names(self, heathens):
        people, parents = self.people()
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(ln, "heathen_identities", return_value=heathens):
            folder = Path(tmp)
            _record(folder, "VVFP LAST NAMES v1 game=5\nused\tAwanata\nheathen\tPowaka\n")
            return ln.village_names(folder, 5, 1, people, parents, set())

    def test_a_heathens_last_name_is_not_a_village_name(self):
        got = self.names({("Tama Wikimak", 2, 2), ("Hina Alosaka", 4, 4)})
        self.assertEqual(got, {"Akikai", "Kaimana", "Awanata"},
                         "the Heathens' (as villagers and as parents) and the heathen lines are left out")

    def test_once_converted_it_is_one(self):
        got = self.names({("Hina Alosaka", 4, 4)})
        self.assertEqual(got, {"Akikai", "Kaimana", "Awanata", "Wikimak"})


if __name__ == "__main__":
    unittest.main()
