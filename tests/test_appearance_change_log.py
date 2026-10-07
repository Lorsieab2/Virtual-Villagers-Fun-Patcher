"""Change Appearance is logged ("Appearance changed" in the Births and Conceptions log) in all five
games, only once the new look is committed, so the Family Tree Maker can follow a villager whose
head and body changed.  native/parentage_export/death_log_harness.c proves the record itself."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native"
COMPANIONS = {
    1: NATIVE / "vv1_origins_icons" / "vv1_origins_icons.c",
    2: NATIVE / "vv2_origins_icons" / "vv2_origins_icons.c",
    3: NATIVE / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.c",
    4: NATIVE / "vv4_origins_icons" / "vv4_origins_icons.c",
    5: NATIVE / "vv5_task9_origins" / "vv5_task9_origins.c",
}
VV5_BUILDER = ROOT / "scripts" / "build_vv5_task9_native_actions.py"
VV5_DLL = ROOT / "data" / "candidates" / "VVFP VV5 Task9 Origins Icons.dll"
VV5_ACTIONS = ROOT / "data" / "vv5_task9_native_actions.json"


class AppearanceChangeLogTests(unittest.TestCase):
    def test_every_game_logs_with_its_own_game_number(self) -> None:
        for game, path in COMPANIONS.items():
            with self.subTest(game=game):
                text = path.read_text(encoding="utf-8")
                # The Lost Children's companion compiles A New Home's source (and its include);
                # A New Home's own picker there is left out (VV_STORY_GAME == 1 only).
                self.assertTrue('#include "../shared/appearance_log.h"' in text
                                or '#include "../vv1_origins_icons/vv1_origins_icons.c"' in text)
                self.assertEqual(text.count(f"vv_log_appearance({game}, "), 1)

    def test_the_log_skips_an_unchanged_look_and_never_writes_the_villager(self) -> None:
        text = (NATIVE / "shared" / "appearance_log.h").read_text(encoding="utf-8")
        self.assertIn("old_head == new_head && old_body == new_body", text)
        self.assertIn('"VVFP Parentage Export.dll"', text)
        self.assertIn("VV_KIND_APPEARANCE 7", text)
        export = (NATIVE / "parentage_export" / "parentage_export.c").read_text(encoding="utf-8")
        self.assertIn("KIND_APPEARANCE = 7", export)

    def test_vv3_logs_after_a_committed_mask_and_the_staged_look(self) -> None:
        text = COMPANIONS[3].read_text(encoding="utf-8")
        chooser = text.split("ShowVV3AppearanceChooser", 1)[1].split("Change Appearance for All dialog", 1)[0]
        log = chooser.index("vv_log_appearance(3, ")
        self.assertLess(chooser.index("!VV3_SetMaskForRecord(record, vv3_appearance_mask)"), log)
        self.assertLess(chooser.index("*body = vv3_appearance_body;"), log)
        self.assertEqual(chooser[log:].split(";", 1)[1].split("}", 1)[0].strip(), "return 1;")

    def test_vv5_router_logs_after_writing_the_record_and_before_the_charge(self) -> None:
        source = VV5_BUILDER.read_text(encoding="utf-8")
        routine = source.split("def build_appearance(", 1)[1].split("def build_appearance_all(", 1)[0]
        log = routine.index("push 0x{s['logappearance_export']:X}")
        self.assertLess(routine.index("mov dword ptr [esi+0x1BBC], eax"), log)
        self.assertLess(log, routine.index("push -5000"))
        # Old head, old body, new head, new body and the record, as the export takes them.
        call = routine[log:].split("log_skip:", 1)[0]
        self.assertIn(
            "push dword ptr [ebp-0x20]\n        push dword ptr [ebp-0x1C]\n"
            "        push dword ptr [ebp-0x30]\n        push dword ptr [ebp-0x2C]\n"
            "        push dword ptr [ebp-0x18]\n        call eax",
            call,
        )

    def test_vv5_companion_exports_the_logger_and_the_stock_pages_name_it(self) -> None:
        pe = pefile.PE(str(VV5_DLL))
        names = {item.name.decode("ascii") for item in pe.DIRECTORY_ENTRY_EXPORT.symbols if item.name}
        self.assertIn("LogVV5AppearanceChange", names)
        layouts = json.loads(VV5_ACTIONS.read_text(encoding="utf-8"))["pe_append_transaction"]["layouts"]
        for name in ("collection_progression", "immediate_fixed"):
            with self.subTest(layout=name):
                page = bytes.fromhex(layouts[name]["append_bytes"])
                self.assertIn(b"LogVV5AppearanceChange\0", page)


if __name__ == "__main__":
    unittest.main()
