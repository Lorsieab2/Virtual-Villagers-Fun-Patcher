"""Source/resource contract for the five Origins upgrade-menu shells.

These checks deliberately inspect the dialog structure and the dialog-procedure
route, rather than comparing compiled resource bytes.  VV1 and VV2 retain
different resource IDs/layout details, while their visible row inventory is
otherwise the same; VV3's dialog 203 is a dormant historical route and is not
part of the public menu contract.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

COMMON_TECH_ROWS = (
    ("Time Warp - Advances the Village Clock", "50,000 tech points"),
    ("Island Event", "30,000 tech points"),
    ("Barrel of Babies", "75,000 tech points"),
    ("Tech Point Doubler", "500,000 tech points"),
    ("Food Point Doubler", "500,000 tech points"),
    ("Full Heal / Cure All", "30,000 tech points"),
    ("Grant Running to All Villagers", "1,000,000 tech points"),
    ("Grant Full Mastery to All Villagers", "1,000,000 tech points"),
    ("All Villagers are Exactly 18", "1,000,000 tech points"),
)
COLLECTION_ROWS = (
    ("Complete All Collections", "1,000,000 tech points"),
    ("Reset All Collections", "1,000,000 tech points"),
)
EQUAL_DIVISION_ROWS = (
    ("Equal Division of Labor (Includes Parenting)", "1,000,000 tech points"),
    ("Equal Division of Labor (No Parenting)", "1,000,000 tech points"),
)
COMMON_TECH_TAIL = EQUAL_DIVISION_ROWS + (("Change Appearance for All", "450,000 tech points"),)
DETAIL_ROWS = (
    ("Grant Youth (-35 years, min age 5)", "50,000 tech points"),
    ("Grant Full Mastery", "100,000 tech points"),
    ("Grant Running", "40,000 tech points"),
    ("Set Age to 18", "50,000 tech points"),
    ("Change Appearance", "5,000 tech points"),
)

MENU_SPECS = {
    "vv1": {
        "rc": "native/vv1_origins_icons/vv1_origins_icons.rc",
        "c": "native/vv1_origins_icons/vv1_origins_icons.c",
        "tech_id": 201,
        "detail_id": 202,
        "tech_token": "IDD_ORIGINS_TECH",
        "detail_token": "IDD_ORIGINS_VILLAGER",
        "handler": "upgrade_dialog",
        "entry": "show_upgrade_menu",
        "tech_rows": COMMON_TECH_ROWS + COMMON_TECH_TAIL,
    },
    "vv2": {
        "rc": "native/vv2_origins_icons/vv2_origins_icons.rc",
        "c": "native/vv2_origins_icons/vv2_origins_icons.c",
        "tech_id": 211,
        "detail_id": 212,
        "tech_token": "IDD_VV2_TECH",
        "detail_token": "IDD_VV2_VILLAGER",
        "handler": "vv2_upgrade_dialog",
        "entry": "ShowVV2UpgradeMenuState",
        "tech_rows": COMMON_TECH_ROWS + COLLECTION_ROWS + COMMON_TECH_TAIL,
    },
    "vv3": {
        "rc": "native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.rc",
        "c": "native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c",
        "tech_id": 201,
        "detail_id": 202,
        "tech_token": "IDD_ORIGINS_TECH",
        "detail_token": "IDD_ORIGINS_VILLAGER",
        "handler": "upgrade_dialog",
        "entry": "show_upgrade_menu",
        "tech_rows": COMMON_TECH_ROWS + COLLECTION_ROWS + COMMON_TECH_TAIL,
    },
    "vv4": {
        "rc": "native/vv4_origins_icons/vv4_origins_icons.rc",
        "c": "native/vv4_origins_icons/vv4_origins_icons.c",
        "tech_id": 201,
        "detail_id": 202,
        "tech_token": "IDD_ORIGINS_TECH",
        "detail_token": "IDD_ORIGINS_VILLAGER",
        "handler": "upgrade_dialog",
        "entry": "show_upgrade_menu",
        "tech_rows": COMMON_TECH_ROWS + COLLECTION_ROWS + COMMON_TECH_TAIL,
    },
    "vv5": {
        "rc": "native/vv5_task9_origins/vv5_task9_origins.rc",
        "c": "native/vv5_task9_origins/vv5_task9_origins.c",
        "tech_id": 201,
        "detail_id": 202,
        "tech_token": "IDD_ORIGINS_TECH",
        "detail_token": "IDD_ORIGINS_VILLAGER",
        "handler": "upgrade_dialog",
        "entry": "ShowOriginsUpgradeMenuState",
        "tech_rows": COMMON_TECH_ROWS + COLLECTION_ROWS + COMMON_TECH_TAIL,
    },
}


def _dialog_block(resource_text: str, dialog_id: int) -> str:
    """Extract one numeric DIALOGEX resource, without folding in later dialogs."""

    start = re.search(
        rf"(?m)^\s*{dialog_id}\s+DIALOGEX\b", resource_text
    )
    if start is None:
        raise AssertionError(f"dialog {dialog_id} is missing")
    end = re.search(r"(?m)^\s*\d+\s+DIALOGEX\b", resource_text[start.end() :])
    stop = start.end() + end.start() if end else len(resource_text)
    return resource_text[start.start() : stop]


def _rows(dialog: str) -> list[tuple[str, str, int]]:
    """Read visible label/cost/Buy triples from a dialog template."""

    pattern = re.compile(
        r'^\s*LTEXT\s+"([^"]+)"[^\r\n]*\r?\n'
        r'\s*LTEXT\s+"([^"]+)"[^\r\n]*\r?\n'
        r'\s*PUSHBUTTON\s+"Buy"\s*,\s*(\d+)\b',
        re.MULTILINE,
    )
    return [(label, cost, int(control)) for label, cost, control in pattern.findall(dialog)]


def _function_body(source: str, function_name: str) -> str:
    """Return one C function body using balanced braces."""

    signature = re.search(
        rf"(?:static\s+)?INT_PTR\s+CALLBACK\s+{re.escape(function_name)}\s*\([^)]*\)",
        source,
    )
    if signature is None:
        raise AssertionError(f"{function_name} declaration is missing")
    opening = source.find("{", signature.end())
    if opening < 0:
        raise AssertionError(f"{function_name} body is missing")
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening : index + 1]
    raise AssertionError(f"{function_name} body is unterminated")


def _named_body(source: str, function_name: str) -> str:
    """Return a non-callback function body for the public menu entry."""

    marker = source.find(function_name)
    if marker < 0:
        raise AssertionError(f"{function_name} entry is missing")
    opening = source.find("{", marker)
    if opening < 0:
        raise AssertionError(f"{function_name} body is missing")
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening : index + 1]
    raise AssertionError(f"{function_name} body is unterminated")


class MenuShellParityTests(unittest.TestCase):
    def test_all_games_keep_canonical_rows_costs_and_order(self) -> None:
        for game, spec in MENU_SPECS.items():
            with self.subTest(game=game):
                resource = (ROOT / spec["rc"]).read_text(encoding="utf-8")
                tech = _dialog_block(resource, spec["tech_id"])
                detail = _dialog_block(resource, spec["detail_id"])
                expected_tech = [
                    (label, cost, 1000 + row)
                    for row, (label, cost) in enumerate(spec["tech_rows"])
                ]
                expected_detail = [
                    (label, cost, 1000 + row)
                    for row, (label, cost) in enumerate(DETAIL_ROWS)
                ]
                self.assertEqual(_rows(tech), expected_tech)
                self.assertEqual(_rows(detail), expected_detail)
                if game == "vv1":
                    self.assertNotIn("Collections", tech)
                else:
                    self.assertIn("Complete All Collections", tech)
                    self.assertIn("Reset All Collections", tech)

    def test_active_dialog_shells_have_captions_cancel_and_escape_hint(self) -> None:
        for game, spec in MENU_SPECS.items():
            with self.subTest(game=game):
                resource = (ROOT / spec["rc"]).read_text(encoding="utf-8")
                tech = _dialog_block(resource, spec["tech_id"])
                detail = _dialog_block(resource, spec["detail_id"])
                self.assertRegex(tech, r'(?m)^\s*CAPTION\s+"Origins Upgrades"\s*$')
                self.assertRegex(detail, r'(?m)^\s*CAPTION\s+"Villager Upgrades"\s*$')
                for dialog in (tech, detail):
                    self.assertEqual(dialog.count("Press ESC to exit this menu."), 1)
                    self.assertRegex(
                        dialog,
                        r'(?m)^\s*DEFPUSHBUTTON\s+"Cancel"\s*,\s*2\b',
                    )

    def test_dialog_handlers_wire_cancel_close_and_active_resource_selection(self) -> None:
        for game, spec in MENU_SPECS.items():
            with self.subTest(game=game):
                source = (ROOT / spec["c"]).read_text(encoding="utf-8")
                tech_definition = rf"{re.escape(spec['tech_token'])}(?:\s*=\s*|\s+){spec['tech_id']}\b"
                detail_definition = rf"{re.escape(spec['detail_token'])}(?:\s*=\s*|\s+){spec['detail_id']}\b"
                self.assertRegex(source, tech_definition)
                self.assertRegex(source, detail_definition)
                handler = _function_body(source, spec["handler"])
                self.assertRegex(handler, r"message\s*==\s*WM_COMMAND")
                self.assertRegex(handler, r"command\s*==\s*IDCANCEL")
                self.assertRegex(handler, r"message\s*==\s*WM_CLOSE")
                self.assertIn("EndDialog", handler)
                # The public menu entry must feed this handler from the Tech /
                # Villager resource IDs, not from the appearance chooser.
                entry = _named_body(source, spec["entry"])
                self.assertIn("DialogBoxParamA", entry)
                self.assertIn(spec["handler"], entry)
                self.assertRegex(
                    entry,
                    r"\b(?:IDD_ORIGINS_TECH|IDD_ORIGINS_VILLAGER|IDD_VV2_TECH|IDD_VV2_VILLAGER)\b",
                )

    def test_vv3_public_route_uses_dialog_201_and_leaves_203_dormant(self) -> None:
        source = (ROOT / MENU_SPECS["vv3"]["c"]).read_text(encoding="utf-8")
        show = source[source.index("static int show_upgrade_menu") :]
        self.assertIn("IDD_ORIGINS_TECH", show)
        self.assertIn("STATE_FULL_MASTERY_ONLY", show)
        self.assertIn("IDD_ORIGINS_FULL_MASTERY", show)
        builder = (ROOT / "scripts/build_vv3_origins_feature.py").read_text(
            encoding="utf-8"
        )
        # The public combined route marks STATE_VILLAGE_WIDE, selecting dialog
        # 201; dialog 203 remains an explicitly separate historical mode.
        self.assertIn("or dword ptr [esp + 0x10], 0x20000", builder)
        self.assertIn("dialog VILLAGE_WIDE (0x20000)", builder)


if __name__ == "__main__":
    unittest.main()
