"""The Tree of Life: Clear All Skill Preferences and Check Highest Skill.

The owner: "add an option to uncheck all skill preferences too ... Should cost
half the equal division of labor cost", then two Check Highest Skill rows
(with / without Parenting) at the Equal Division price.

Pinned here, on the source, the resource, the built companion and the stock
executable:

* rows 13 / 14 / 15 (Buy 1013 / 1014 / 1015) come right after the two Equal
  Division of Labor rows; Change Appearance for All moves to row 16 (1016);
* each row is confirmed by the menu's standard prompt and then bought inside
  the companion, so the payload's fixed 1,000,000 charge never applies; the
  price is vvfp_story_price(4, 500000) / (4, 1000000), 0 under Story / Cheat
  Upgrades, and the charge is skipped at 0;
* the same villagers as Equal Division (vv_eligible), the same field
  (+0x1C70), -1 for "none" as the stock game writes it;
* nothing is written or charged unless a preference really changes and the
  player can pay;
* the descriptions name the rows.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
C = ROOT / "native" / "vv4_origins_icons" / "vv4_origins_icons.c"
RC = ROOT / "native" / "vv4_origins_icons" / "vv4_origins_icons.rc"
DLL = ROOT / "assets" / "origins" / "VVFP VV4 Origins Icons.dll"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Tree of Life.exe"

ROWS = (
    (11, "Equal Division of Labor (Includes Parenting)", "1,000,000"),
    (12, "Equal Division of Labor (No Parenting)", "1,000,000"),
    (13, "Clear All Skill Preferences", "500,000"),
    (14, "Check Highest Skill (Includes Parenting)", "1,000,000"),
    (15, "Check Highest Skill (No Parenting)", "1,000,000"),
    (16, "Change Appearance for All", "450,000"),
)


def _c() -> str:
    return C.read_text(encoding="utf-8", errors="replace")


def _body(src: str, signature: str) -> str:
    start = src.index(signature)
    opening = src.index("{", start)
    depth = 0
    for i in range(opening, len(src)):
        depth += {"{": 1, "}": -1}.get(src[i], 0)
        if depth == 0:
            return src[opening:i + 1]
    raise AssertionError(signature)


def _tech_dialog() -> str:
    text = RC.read_text(encoding="utf-8")
    start = text.index("201 DIALOGEX")
    return text[start:text.index("202 DIALOGEX")]


class RowsTests(unittest.TestCase):
    def test_resource_rows_follow_equal_division(self) -> None:
        rows = re.findall(
            r'LTEXT\s+"([^"]+)"[^\n]*\n\s*LTEXT\s+"([^"]+) tech points"[^\n]*\n'
            r'\s*PUSHBUTTON\s+"Buy",\s*(\d+)', _tech_dialog())
        self.assertEqual(len(rows), 17)
        for row, label, cost in ROWS:
            with self.subTest(row=row):
                self.assertEqual(rows[row], (label, cost, str(1000 + row)))

    def test_the_dialog_fits_its_rows(self) -> None:
        dialog = _tech_dialog()
        height = int(re.search(r"201 DIALOGEX 0, 0, \d+, (\d+)", dialog).group(1))
        cancel_y = int(re.search(r'DEFPUSHBUTTON "Cancel", 2, \d+, (\d+)', dialog).group(1))
        esc_y = int(re.search(r'"Press ESC to exit this menu.", -1, \d+, (\d+)', dialog).group(1))
        bottoms = [int(y) + 18 for y in re.findall(r'PUSHBUTTON\s+"Buy",\s*\d+,\s*\d+,\s*(\d+)', dialog)]
        self.assertLess(max(bottoms), esc_y)
        self.assertLess(esc_y, cancel_y)
        self.assertLessEqual(cancel_y + 14, height)

    def test_tables_and_ids(self) -> None:
        src = _c()
        self.assertIn("ID_BUY_LAST = 1016", src)
        self.assertIn("#define ID_CLEAR_PREFS_ROW     13", src)
        self.assertIn("#define ID_HIGHEST_P_ROW       14", src)
        self.assertIn("#define ID_HIGHEST_NP_ROW      15", src)
        self.assertIn("#define ID_FORALL_ROW 16", src)
        names = re.search(r"g_tech_names\[17\] = \{(.*?)\};", src, re.S).group(1)
        costs = re.search(r"g_tech_costs\[17\] = \{(.*?)\};", src, re.S).group(1)
        names = re.findall(r'"([^"]*)"', names)
        costs = re.findall(r'"([^"]*)"', costs)
        for row, label, cost in ROWS:
            with self.subTest(row=row):
                self.assertEqual(names[row], label)
                self.assertEqual(costs[row], cost)
        self.assertIn("? 17 : 6", src)
        self.assertIn("for (row = 0; row < 17; ++row)", src)


class RoutingTests(unittest.TestCase):
    def test_rows_are_confirmed_then_bought_in_the_companion(self) -> None:
        handler = _body(_c(), "static INT_PTR CALLBACK upgrade_dialog(")
        confirm = handler.index("Do you want to buy %s for %s tech points?")
        buy = handler.index("vv4_skill_pref_purchase(row);")
        dispatch = handler.index("g_last_row = row;")
        self.assertLess(confirm, buy, "the standard confirm runs first")
        self.assertLess(buy, dispatch, "bought before the payload dispatch")
        tail = handler[buy:buy + 120]
        self.assertIn("EndDialog(window, -1);", tail, "the payload never sees these rows")
        self.assertIn("row == ID_CLEAR_PREFS_ROW || row == ID_HIGHEST_P_ROW", handler)

    def test_the_payload_still_only_dispatches_rows_up_to_twelve(self) -> None:
        builder = (ROOT / "scripts" / "build_vv4_origins_feature.py").read_text(encoding="utf-8")
        self.assertIn("Rows 9-12 map to DLL ordinals 101-104", builder)


class PurchaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.src = _c()
        self.buy = _body(self.src, "static int vv4_skill_pref_buy(int kind)")
        self.scan = _body(self.src, "static int vv4_skill_pref_scan(")
        self.highest = _body(self.src, "static int vv4_highest_skill(")

    def test_price_goes_through_the_story_price(self) -> None:
        self.assertIn(
            "vvfp_story_price(4, kind == SP_CLEAR ? 500000 : 1000000)", self.buy)
        charge = self.buy[self.buy.index("if (price != 0)"):]
        self.assertIn("int delta = -price;", charge)
        self.assertIn("mov  ecx, 0x4D6F88", charge)
        self.assertIn("mov  eax, 0x41E300", charge)
        self.assertEqual(self.buy.count("0x41E300"), 1, "charged once")

    def test_nothing_is_charged_unless_something_changes_and_is_affordable(self) -> None:
        b = self.buy
        dry = b.index("vv4_skill_pref_scan(kind, 0,")
        none = b.index("No villagers were eligible. No tech points have been deducted.")
        same = b.index("Every villager's skill preference is already cleared. ")
        poor = b.index('"Not enough tech points."')
        apply = b.index("vv4_skill_pref_scan(kind, 1,")
        charge = b.index("0x41E300")
        self.assertLess(dry, none)
        self.assertLess(none, same)
        self.assertLess(same, poor)
        self.assertLess(poor, apply)
        self.assertLess(apply, charge)
        self.assertIn("Every villager already has their highest skill checked. "
                      "No tech points have been deducted.", re.sub(r'"\s*\n\s*"', "", b))
        for section in (b[none:same], b[same:poor], b[poor:apply]):
            self.assertIn("return 0;", section)

    def test_result_wording(self) -> None:
        b = self.buy
        self.assertIn('"Cleared %d %s Skill %s."', b)
        self.assertIn('changed == 1 ? "Villager\'s" : "Villagers\'"', b)
        self.assertIn('"Set %d %s\' Job Preferences."', b)
        for name, v in (("Farming", 0), ("Building", 4), ("Research", 3), ("Healing", 2)):
            self.assertIn(f'vv4_sp_line(p, "{name}", {v})', b)
        self.assertIn('if (kind == SP_HIGHEST_P) p = vv4_sp_line(p, "Breeding", 1);', b)
        self.assertIn('"\\n\\nSkipped %d %s: no skill progress yet."', self.src)
        self.assertIn('"\\n\\n%s: %d %s (%d Male, %d Female)."', _body(self.src, "static char *vv4_sp_line("))

    def test_same_villagers_and_field_as_equal_division(self) -> None:
        s = self.scan
        self.assertIn("if (!vv_eligible(r)) continue;", s)
        self.assertIn("(int *)(r + VV_PREF_OFFSET)", s)
        self.assertIn("target = VV_PREF_NONE;", s)
        self.assertIn("#define VV_PREF_NONE (-1)", self.src)
        self.assertIn("if (*pref != target)", s)
        self.assertIn("if (apply) *pref = target;", s)
        ed = _body(self.src, "static int vv4_apply_equal_division(")
        self.assertIn("vv_eligible(r)", ed)

    def test_highest_skill_order_ties_and_no_progress(self) -> None:
        h = self.highest
        self.assertIn("{ 0, 4, 3, 2, 1 }", h, "Skills list order: ties go to the first")
        self.assertIn("(const float *)(r + VV_SKILL0_OFFSET)", h)
        self.assertIn("if (s == 1 && !include_parenting) continue;", h)
        self.assertIn("if (!(v > 0.0f)) continue;", h, "0, negative and NaN are skipped")
        self.assertIn("v > best_value", h, "strict: an equal later skill does not win")
        self.assertIn("#define VV_SKILL0_OFFSET     0x1C5C", self.src)
        self.assertIn("#define VV_PREF_OFFSET       0x1C70", self.src)


def _mirror_highest(skills: list[float], include_parenting: bool) -> int:
    """The C rule, restated: used to pin the cases the owner named."""
    best, best_value = -1, 0.0
    for s in (0, 4, 3, 2, 1):
        if s == 1 and not include_parenting:
            continue
        v = skills[s]
        if not v > 0.0:
            continue
        if best == -1 or v > best_value:
            best, best_value = s, v
    return best


class HighestRuleTests(unittest.TestCase):
    def test_cases(self) -> None:
        nan = float("nan")
        self.assertEqual(_mirror_highest([10, 50, 20, 30, 40], True), 1)
        self.assertEqual(_mirror_highest([10, 50, 20, 30, 40], False), 4)
        self.assertEqual(_mirror_highest([30, 0, 30, 30, 30], True), 0, "tie: Farming first")
        self.assertEqual(_mirror_highest([0, 0, 30, 30, 30], True), 4, "tie: Building next")
        self.assertEqual(_mirror_highest([0, 0, 30, 30, 0], True), 3, "tie: Research before Healing")
        self.assertEqual(_mirror_highest([0, 9, 0, 0, 0], False), -1, "only Parenting: skipped")
        self.assertEqual(_mirror_highest([nan, -5, 0, nan, 0], True), -1)


class StockEvidenceTests(unittest.TestCase):
    @unittest.skipUnless(STOCK.is_file(), "stock executable not present")
    def test_minus_one_is_the_games_own_none_and_skills_index_by_preference(self) -> None:
        import pefile

        pe = pefile.PE(str(STOCK), fast_load=True)
        data = STOCK.read_bytes()

        def at(va: int, n: int) -> bytes:
            off = pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase)
            return data[off:off + n]

        self.assertEqual(at(0x45DA28, 10).hex(), "c786701c0000ffffffff")
        self.assertEqual(at(0x4402F5, 11).hex(), "8b81701c000083f8ff7412")
        self.assertEqual(at(0x461E5B, 7).hex(), "d984985c1c0000")


class BuiltCompanionTests(unittest.TestCase):
    @unittest.skipUnless(DLL.is_file(), "companion not built")
    def test_the_built_companion_carries_the_rows(self) -> None:
        data = DLL.read_bytes()
        for _, label, _ in ROWS[2:5]:
            self.assertIn(label.encode("utf-16-le"), data, "dialog resource")
            self.assertIn(label.encode("ascii") + b"\0", data, "confirm name table")
        for text in ("Cleared %d %s Skill %s.",
                     "Every villager's skill preference is already cleared. "
                     "No tech points have been deducted.",
                     "Every villager already has their highest skill checked. "
                     "No tech points have been deducted."):
            self.assertIn(text.encode("ascii"), data)
        manifest = json.loads((ROOT / "data" / "vv4_origins_feature.json").read_text(encoding="utf-8"))
        import hashlib
        row = next(r for r in manifest["companion_files"]
                   if r["source"] == "assets/origins/VVFP VV4 Origins Icons.dll")
        self.assertEqual(row["sha256"], hashlib.sha256(data).hexdigest().upper())


class DescriptionTests(unittest.TestCase):
    def test_catalog_descriptions(self) -> None:
        base = json.loads((ROOT / "data" / "vv4_origins_feature.json").read_text(encoding="utf-8"))
        wide = json.loads((ROOT / "data" / "vv4_origins_village_wide_upgrades.json").read_text(encoding="utf-8"))
        self.assertIn(
            "Clear All Skill Preferences (500,000 tech points): unchecks every villager's "
            "skill preference (job checkmark) so each villager is free to choose their own "
            "work, as in the stock game. Skills themselves are not changed.",
            base["description"])
        self.assertIn(
            "Check Highest Skill (Includes Parenting) / (No Parenting) (1,000,000 tech "
            "points each): sets each villager's skill preference (job checkmark) to the "
            "skill they have the most progress in", base["description"])
        self.assertIn("Clear All Skill Preferences, and Check Highest Skill with and "
                      "without Parenting", wide["description"])


if __name__ == "__main__":
    unittest.main()
