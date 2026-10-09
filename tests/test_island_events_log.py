"""Write Island Events Log: the companion's comparison (native/vvfp_island_events).

native/vvfp_island_events/island_events_harness.c includes the companion's
source whole and runs its comparison over villager arrays it owns, in all five
games' field tables (see its header): a renamed villager stays one villager
(The Secret City's Return of Biggles names its subject "?"), removals and
arrivals are still told apart, and an event that starts a pregnancy logs the
expected father's name, head and body and the babies, not only the Pregnant
flag (Codex, #577) -- except in The Lost Children, which logs only Pregnant:
the owner's own VV2 log disproved its father offsets on the mother, and its
babies offset has never been confirmed by a real log.
"""
from __future__ import annotations

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
CHECKS = 5 * 6   # six checks in each of the five games


def body(source: str, head: str) -> str:
    text = source[source.index(head):]
    return text[:text.index("\n}\n")]


def table(source: str, head: str) -> str:
    text = source[source.index(head):]
    return text[:text.index("\n};")]


class IslandEventsSource(unittest.TestCase):
    def test_who_is_who_is_decided_by_the_slot_never_the_name(self):
        source = (NATIVE / "vvfp_island_events.c").read_text(encoding="utf-8")
        compare = body(source, "static void compare(struct snapshot *s)")
        self.assertIn("if (!present_now(live, now, count)) {", compare)
        self.assertNotIn("g_layout->name", compare.split("Villagers the event brought")[1])
        self.assertNotIn("memcmp(live + g_layout->name", compare)

    def test_every_game_but_a_new_home_compares_the_expected_father(self):
        source = (NATIVE / "island_event_games.inc").read_text(encoding="utf-8")
        tables = {name: table(source, f"static const struct field {name}[] = {{")
                  for name in ("VV1_FIELDS", "VV2_FIELDS", "VV3_FIELDS", "VV4_FIELDS", "VV5_FIELDS")}
        # The parentage exporter's offsets: father, father_head_copy, father_body_copy, litter.
        expected = {
            "VV3_FIELDS": (0xE48, 0xE68, 0xE64, 0xE90),
            "VV4_FIELDS": (0x1C10, 0x1C30, 0x1C2C, 0x1C50),
            "VV5_FIELDS": (0x1C10, 0x1C30, 0x1C2C, 0x1C50),
        }
        for name, (father, head, body_, litter) in expected.items():
            with self.subTest(table=name):
                text = tables[name]
                self.assertIn(f'{{ "Expected father", 0x{father:X}, F_TEXT, 0x18 }}', text)
                self.assertIn(f'{{ "Expected father\'s head", 0x{head:X}, F_INT, 0 }}', text)
                self.assertIn(f'{{ "Expected father\'s body", 0x{body_:X}, F_INT, 0 }}', text)
                self.assertIn(f'{{ "Babies in pregnancy", 0x{litter:X}, F_INT, 0 }}', text)
        self.assertIn('{ "Babies in pregnancy", 0x35C, F_INT, 0 }', tables["VV1_FIELDS"])
        self.assertNotIn("Expected father", tables["VV1_FIELDS"])
        # The Lost Children: the owner's own VV2 log disproved the father copies on the mother
        # (0x5C0 / 0x5E0 / 0x5DC) and no real log has confirmed the babies (0x544): only Pregnant.
        self.assertIn('{ "Pregnant", 0x540, F_FLAG, 0 }', tables["VV2_FIELDS"])
        for absent in ('"Expected father', '"Babies in pregnancy"', "0x5C0, F", "0x5E0, F", "0x5DC, F", "0x544, F"):
            self.assertNotIn(absent, tables["VV2_FIELDS"])

    def test_the_offsets_are_the_parentage_exporters(self):
        exporter = (ROOT / "native" / "parentage_export" / "parentage_export.c").read_text(encoding="utf-8")
        self.assertIn("FATHER_BY_NAME, 0xE48, 0x18, 0xE90,\n        0xE68, 0xE64,", exporter)
        self.assertEqual(exporter.count("FATHER_BY_NAME, 0x1C10, 0x18, 0x1C50,\n        0x1C30, 0x1C2C,"), 2)


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
