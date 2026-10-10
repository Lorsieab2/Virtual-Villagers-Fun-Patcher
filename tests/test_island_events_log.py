"""Write Island Events Log: the companion's comparison (native/vvfp_island_events).

native/vvfp_island_events/island_events_harness.c includes the companion's
source whole and runs its comparison over villager arrays it owns, in all five
games' field tables (see its header): a renamed villager stays one villager
(The Secret City's Return of Biggles names its subject "?"), removals and
arrivals are still told apart, and an event that starts a pregnancy logs the
expected father's name, head and body and the babies, not only the Pregnant
flag (Codex, #577), in every game that keeps the father on the mother (all but
A New Home, which logs the babies) -- printed whole even when the last
pregnancy left the same father or babies on her.
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native" / "vvfp_island_events"
VS_TOOLS = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231")
CL = VS_TOOLS / "bin" / "Hostx64" / "x86" / "cl.exe"
SDK = Path(r"C:\Program Files (x86)\Windows Kits\10")
SDK_VERSION = "10.0.26100.0"
CHECKS = 5 * 11 + 4 + 1 + 3 * 4  # eleven checks in each of the five games; the look-alikes in the four
                                 # that have them; A New Home's conception with no father recorded;
                                 # the two-choice answer in the three later games


def body(source: str, head: str) -> str:
    text = source[source.index(head):]
    return text[:text.index("\n}\n")]


def table(source: str, head: str) -> str:
    text = source[source.index(head):]
    return text[:text.index("\n};")]


class IslandEventsSource(unittest.TestCase):
    def test_who_is_who_is_decided_by_the_slot_and_a_rename_alone_is_not_a_new_villager(self):
        source = (NATIVE / "vvfp_island_events.c").read_text(encoding="utf-8")
        compare = body(source, "static void compare(struct snapshot *s)")
        self.assertIn("if (!present_now(live, now, count) || reused(old, live)) {", compare)
        self.assertIn("!reused(s->copy + (size_t)k2 * g_layout->copy_size, now[i])", compare)
        self.assertNotIn("g_layout->name", compare)
        # A slot counts as reused only when the name AND head, body or sex differ.
        reused = body(source, "static int reused(")
        self.assertIn("return name_differs && other_differs;", reused)
        for label in ('"Name"', '"Sex"', "g_layout->head", "g_layout->body"):
            self.assertIn(label, reused)

    def test_the_manifests_list_every_stolen_byte_the_dll_checks(self):
        source = (NATIVE / "island_event_games.inc").read_text(encoding="utf-8")
        rows = re.findall(r"\{ (0x[0-9A-F]+), \{ ([^}]*) \}, (\d+),", source)
        stolen = {int(at, 16): bytes(int(b, 16) for b in data.split(", "))[:int(n)].hex().upper()
                  for at, data, n in rows}
        spec = importlib.util.spec_from_file_location(
            "build_island_events_features", ROOT / "scripts" / "build_island_events_features.py")
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        listed = {at: data for sites in generator.SITES.values() for at, data, _ in sites}
        self.assertEqual(listed, stolen)

    def test_the_village_list_skips_look_alikes_as_every_companion_does(self):
        source = (NATIVE / "island_event_games.inc").read_text(encoding="utf-8")
        self.assertIn('#include "../shared/villager_lookalike.h"', source)
        listing = body(source, "static int array_villagers(")
        self.assertIn("if (record[present] != 0 && !vv_lookalike(stride, record)) {", listing)

    def test_every_game_but_a_new_home_compares_the_expected_father(self):
        source = (NATIVE / "island_event_games.inc").read_text(encoding="utf-8")
        tables = {name: table(source, f"static const struct field {name}[] = {{")
                  for name in ("VV1_FIELDS", "VV2_FIELDS", "VV3_FIELDS", "VV4_FIELDS", "VV5_FIELDS")}
        # The parentage exporter's offsets: father, father_head_copy, father_body_copy, litter.
        # The Lost Children's: the conception 0x44B980 writes the father's name to +0x5C0, his head
        # to +0x5E0 and body to +0x5DC, and 2 / 3 to +0x544 (0 one baby) -- confirmed in the owner's
        # own saves and Births and Conceptions log (island_event_games.inc).
        expected = {
            "VV2_FIELDS": (0x5C0, 0x5E0, 0x5DC, 0x544),
            "VV3_FIELDS": (0xE48, 0xE68, 0xE64, 0xE90),
            "VV4_FIELDS": (0x1C10, 0x1C30, 0x1C2C, 0x1C50),
            "VV5_FIELDS": (0x1C10, 0x1C30, 0x1C2C, 0x1C50),
        }
        for name, (father, head, body_, litter) in expected.items():
            with self.subTest(table=name):
                text = tables[name]
                self.assertIn(f'{{ "Expected father", 0x{father:X}, F_TEXT, 0x18, 1 }}', text)
                self.assertIn(f'{{ "Expected father\'s head", 0x{head:X}, F_INT, 0, 1 }}', text)
                self.assertIn(f'{{ "Expected father\'s body", 0x{body_:X}, F_INT, 0, 1 }}', text)
                if name == "VV2_FIELDS":
                    # 0 for one baby, as A New Home: printed 1 while she is pregnant (+0x540).
                    self.assertIn('{ "Babies nursing", 0x544, F_BABIES, 0x540, 1 }', text)
                    self.assertIn('{ "Nursing", 0x540, F_FLAG, 0 }', text)
                else:
                    self.assertIn(f'{{ "Babies nursing", 0x{litter:X}, F_INT, 0, 1 }}', text)
        self.assertIn('{ "Babies nursing", 0x35C, F_BABIES, 0x358, 1 }', tables["VV1_FIELDS"])
        self.assertIn('{ "Nursing", 0x358, F_FLAG, 0 }', tables["VV1_FIELDS"])
        self.assertNotIn("Expected father", tables["VV1_FIELDS"])
        # The same four facts in every game but A New Home (which keeps no father on the mother).
        for name in ("VV2_FIELDS", "VV3_FIELDS", "VV4_FIELDS", "VV5_FIELDS"):
            labels = re.findall(r'\{ "([^"]+)", 0x[0-9A-F]+, F_\w+, \w+, 1 \}', tables[name])
            self.assertEqual(labels, ["Babies nursing", "Expected father", "Expected father's head",
                                      "Expected father's body"], name)

    def test_the_offsets_are_the_parentage_exporters(self):
        exporter = (ROOT / "native" / "parentage_export" / "parentage_export.c").read_text(encoding="utf-8")
        self.assertIn("FATHER_BY_NAME, 0x5C0, 0, 0x544,\n        0x5E0, 0x5DC,", exporter)
        self.assertIn("FATHER_BY_NAME, 0xE48, 0x18, 0xE90,\n        0xE68, 0xE64,", exporter)
        self.assertEqual(exporter.count("FATHER_BY_NAME, 0x1C10, 0x18, 0x1C50,\n        0x1C30, 0x1C2C,"), 2)

    def test_a_conception_prints_its_fields_whole(self):
        source = (NATIVE / "vvfp_island_events.c").read_text(encoding="utf-8")
        compare = body(source, "static void compare(struct snapshot *s)")
        self.assertIn('if (f->type == F_FLAG && strcmp(f->label, "Nursing") == 0) {', compare)
        self.assertIn("if (conceived && f->conception) {", compare)
        text = body(source, "static void field_text(")
        self.assertIn("value = value == 3 ? 3 : value != 0 ? 2 : 1;", text)

    def test_a_new_home_takes_the_expected_father_from_the_show_parents_record(self):
        games = (NATIVE / "island_event_games.inc").read_text(encoding="utf-8")
        self.assertIn("FIELDS(VV1_FIELDS),\n                                              vv1_expected_father };", games)
        self.assertIn('GetProcAddress(module, "Vv1ParentageQueryExpectedFather")', games)
        # The Show Parents companion's one expected-father export, (index, out[2], name, capacity).
        self.assertIn("typedef int (__stdcall *vv1_query_expected_fn)(int index, int *out, char *name, int capacity);",
                      games)
        parentage = ROOT / "native" / "vv1_parentage"
        self.assertIn("Vv1ParentageQueryExpectedFather=_Vv1ParentageQueryExpectedFather@16",
                      (parentage / "vv1_parentage.def").read_text(encoding="utf-8"))
        source = (parentage / "vv1_parentage.c").read_text(encoding="utf-8")
        self.assertIn("int __stdcall Vv1ParentageQueryExpectedFather(int index, int *out, char *name,", source)


@unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
class IslandEventsHarness(unittest.TestCase):
    def test_the_harness_passes_in_all_five_games(self):
        with tempfile.TemporaryDirectory(prefix="vvfp_island_events_harness_") as out:
            exe = Path(out) / "island_events_harness.exe"
            build = subprocess.run(
                [str(CL), "/nologo", f"/Fo{out}\\", "/O2", "/MT", "/W4",
                 "/I", str(VS_TOOLS / "include"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "um"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "shared"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "ucrt"),
                 str(NATIVE / "island_events_harness.c"),
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
        self.assertIn(f"== {CHECKS} check(s), 0 failure(s) ==", result.stdout)
        self.assertEqual(len(re.findall(r"^  ok ", result.stdout, re.M)), CHECKS, result.stdout)
        for game in range(1, 6):
            self.assertIn(f"Virtual Villagers {game} (", result.stdout)


if __name__ == "__main__":
    unittest.main()
