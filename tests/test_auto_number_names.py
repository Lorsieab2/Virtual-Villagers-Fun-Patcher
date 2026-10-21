"""Number villagers who share a name automatically, in the running game (all five games).

The owner (2026-10-20): numbering villagers who share a full name ("Chip Kenobi I", "Chip Kenobi II",
...) "must be ON BY DEFAULT", done automatically "so names are numbered in the game and in every log", as
a per-village setting.  "VVFP Number Names.dll" (native/vvfp_number_names) numbers a baby born with a
living villager's full name at its birth; the parentage companions call it right after the last name,
before the Birth record; the parentage rows ship it.  The patcher's side (Repair Saves & Logs, the
setting, the Repairs Made record) is tested in tests/test_number_duplicate_names.py.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

NATIVE = ROOT / "native" / "vvfp_number_names"
DLL = ROOT / "assets" / "number_names" / "VVFP Number Names.dll"
VS_TOOLS = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231")
CL = VS_TOOLS / "bin" / "Hostx64" / "x86" / "cl.exe"
SDK = Path(r"C:\Program Files (x86)\Windows Kits\10")
SDK_VERSION = "10.0.26100.0"
# Per game: II, the namesake kept, IV, III, no namesake, inactive, no room, exactly the limit, already
# numbered, the setting (5), a pointer between records, numbers never given twice (7) -- and a look-alike in The Lost Children to
# New Believers.
HARNESS_CHECKS = 5 * 22 + 4


def manifest_files(name: str) -> list[dict]:
    data = json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))
    rows = data["features"] if "features" in data else [data]
    return [c for row in rows for c in row.get("companion_files", [])]


class Shipped(unittest.TestCase):
    def test_the_parentage_rows_ship_it_pinned(self):
        digest = hashlib.sha256(DLL.read_bytes()).hexdigest()
        for name in ["vv1_show_parents_feature.json"] + [f"vv{g}_parentage_feature.json" for g in range(2, 6)]:
            ours = [c for c in manifest_files(name) if c["destination"] == "VVFP Number Names.dll"]
            self.assertEqual(len(ours), 1, name)
            self.assertEqual(ours[0]["source"], "assets/number_names/VVFP Number Names.dll", name)
            self.assertEqual(ours[0]["sha256"].lower(), digest, name)
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn('"assets/number_names/VVFP Number Names.dll",', release)

    def test_each_companion_calls_it_after_the_last_name_and_before_the_birth_record(self):
        export = (ROOT / "native" / "parentage_export" / "parentage_export.c").read_text(encoding="utf-8")
        birth = export[export.index("int __stdcall WriteParentageBirthLitter("):
                       export.index("int __stdcall WriteParentageBirthAfterwards(")]
        self.assertLess(birth.index("rule_last_name(game_id, (unsigned char *)child_record);"),
                        birth.index("number_new_name(game_id, (unsigned char *)child_record);"))
        self.assertLess(birth.index("number_new_name(game_id, (unsigned char *)child_record);"),
                        birth.index("compose_birth("))
        self.assertIn('vvfp_load_patcher_dll("VVFP Number Names.dll")', export)
        self.assertIn("is_record_slot(g, records, rec)", export)
        vv1 = (ROOT / "native" / "vv1_parentage" / "vv1_parentage.c").read_text(encoding="utf-8")
        born = vv1[vv1.index("int __stdcall Vv1ParentageBorn("):vv1.index("int __stdcall Vv1ParentageTick(")]
        self.assertEqual(born.count("vv1_number_name((unsigned char *)child_pointer, c, slot);"), 2,
                         "the Golden Child and every delivery")
        for at in [m.start() for m in re.finditer(r"vv1_number_name\(\(unsigned char \*\)child_pointer", born)]:
            self.assertEqual(born.rfind("vv1_rule_last_name(", 0, at) >= 0, True)
        self.assertLess(born.index("vv1_number_name((unsigned char *)child_pointer, c, slot);\n        vv1_log_birth(")
                        if "\r\n" not in born else
                        born.index("vv1_number_name((unsigned char *)child_pointer, c, slot);\r\n        vv1_log_birth("),
                        len(born))
        # The frame watch follows the new name, so the numbering is no rename.
        self.assertIn("memcpy(g_prev_name[c], child + VV1_NAME_OFFSET, VV1_NAME_CAPACITY);",
                      vv1[vv1.index("static void vv1_number_name("):vv1.index("int __stdcall Vv1ParentageBorn(")])

    def test_the_setting_file_is_the_patchers(self):
        import vv_number_names as nn
        source = (NATIVE / "vvfp_number_names.c").read_text(encoding="utf-8")
        self.assertIn('"Virtual Villagers %d Number Names - Save %d.dat"', source)
        self.assertIn("Number Names\\\\", source)
        self.assertIn('"VVFP NUMBER NAMES v1 game=%d"', source)
        self.assertEqual(nn.SETTING_HEADER, "VVFP NUMBER NAMES v1 game={game}")
        self.assertIn('strncmp(line, "auto\\toff", 8)', source)
        import vv_last_names as ln
        self.assertEqual({g: int(re.search(r"ROOM\[GAMES \+ 1\] = \{ 0, (.*?) \}", source).group(1).split(", ")[g - 1])
                          for g in range(1, 6)}, ln.ROOM)


@unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
class NumberedAtBirth(unittest.TestCase):
    def test_every_game_in_the_shipped_code(self):
        with tempfile.TemporaryDirectory(prefix="vvfp_nn_") as out:
            exe = Path(out) / "number_names_harness.exe"
            build = subprocess.run(
                [str(CL), "/nologo", f"/Fo{out}\\", "/O2", "/MT", "/W4",
                 "/I", str(VS_TOOLS / "include"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "um"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "shared"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "ucrt"),
                 "/I", str(ROOT / "native" / "shared"),
                 str(NATIVE / "number_names_harness.c"),
                 "/link",
                 f"/LIBPATH:{VS_TOOLS / 'lib' / 'x86'}",
                 f"/LIBPATH:{SDK / 'Lib' / SDK_VERSION / 'um' / 'x86'}",
                 f"/LIBPATH:{SDK / 'Lib' / SDK_VERSION / 'ucrt' / 'x86'}",
                 f"/OUT:{exe}", "kernel32.lib", "shell32.lib"],
                capture_output=True, text=True, cwd=out, timeout=600,
            )
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            result = subprocess.run([str(exe), str(Path(out) / "d")], capture_output=True, text=True,
                                    cwd=out, timeout=300)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"== {HARNESS_CHECKS} check(s), 0 failure(s) ==", result.stdout)
        self.assertEqual(len(re.findall(r"^  ok ", result.stdout, re.M)), HARNESS_CHECKS, result.stdout)
        for game in range(1, 6):
            self.assertIn(f"== Virtual Villagers {game} ==", result.stdout)

    def test_the_shipped_dll_is_built_from_this_source(self):
        with tempfile.TemporaryDirectory(prefix="vvfp_nn_") as out:
            dll = Path(out) / "VVFP Number Names.dll"
            build = subprocess.run(
                [str(CL), "/nologo", "/LD", "/O2", "/MT", "/W4", f"/Fo{out}\\",
                 "/I", str(VS_TOOLS / "include"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "um"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "shared"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "ucrt"),
                 "/I", str(ROOT / "native" / "shared"),
                 str(NATIVE / "vvfp_number_names.c"),
                 "/link", "/Brepro", f"/DEF:{NATIVE / 'vvfp_number_names.def'}",
                 f"/LIBPATH:{VS_TOOLS / 'lib' / 'x86'}",
                 f"/LIBPATH:{SDK / 'Lib' / SDK_VERSION / 'um' / 'x86'}",
                 f"/LIBPATH:{SDK / 'Lib' / SDK_VERSION / 'ucrt' / 'x86'}",
                 f"/OUT:{dll}", "/RELEASE", "kernel32.lib", "shell32.lib"],
                capture_output=True, text=True, cwd=out, timeout=600,
            )
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            self.assertEqual(hashlib.sha256(dll.read_bytes()).hexdigest(), hashlib.sha256(DLL.read_bytes()).hexdigest())


class TheAutomaticSettingOnlyTakesBackItsOwnTick(unittest.TestCase):
    """Codex (#599): Repair Saves & Logs' "Number duplicate names" row is ticked by "Number villagers
    who share a name automatically" while there are names to number; unticking the setting must
    untick it again, or Repair renames villagers after the player turned numbering off -- but a tick
    the player made on their own stays."""

    def setUp(self):
        import vv_fun_patcher_gui as gui
        self.tick = gui.auto_number_tick

    def dialog(self, auto: bool, misnumbered: bool):
        # The dialog's start: the row is ticked by default only when the setting is off.
        state = {"ticked": misnumbered and not auto, "forced": False}

        def setting(on: bool):
            state["ticked"], state["forced"] = self.tick(on, misnumbered, state["ticked"], state["forced"])
            return state["ticked"]
        return state, setting

    def test_auto_on_forces_the_tick(self):
        state, setting = self.dialog(auto=True, misnumbered=True)
        self.assertTrue(setting(True))
        self.assertTrue(state["forced"])

    def test_auto_off_takes_the_forced_tick_back(self):
        state, setting = self.dialog(auto=True, misnumbered=True)
        setting(True)
        self.assertFalse(setting(False))
        self.assertFalse(state["forced"])
        self.assertTrue(setting(True), "on again: ticked again")
        self.assertFalse(setting(False))

    def test_a_manual_tick_stays_when_auto_goes_off(self):
        state, setting = self.dialog(auto=False, misnumbered=True)
        state["ticked"] = False
        self.assertFalse(setting(False))
        state["ticked"] = True                 # the player ticks the row
        self.assertTrue(setting(True))
        self.assertFalse(state["forced"], "the player's tick is not the setting's")
        self.assertTrue(setting(False), "the player's tick stays")
        # The row ticked by default (the setting off at the start) is not the setting's either.
        state, setting = self.dialog(auto=False, misnumbered=True)
        self.assertTrue(setting(True))
        self.assertTrue(setting(False))

    def test_nothing_to_number_is_never_ticked_by_the_setting(self):
        state, setting = self.dialog(auto=True, misnumbered=False)
        self.assertFalse(setting(True))
        self.assertFalse(setting(False))

    def test_the_dialog_uses_it(self):
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertIn("number_var = tk.BooleanVar(value=bool(misnumbered) and not number_auto_var.get())", source)
        self.assertIn("auto_number_tick(\n                number_auto_var.get(), bool(misnumbered), number_var.get(),"
                      " number_forced[\"by_auto\"])", source)
        self.assertNotIn("            if number_auto_var.get() and misnumbered:\n                number_var.set(True)",
                         source)


if __name__ == "__main__":
    unittest.main()
