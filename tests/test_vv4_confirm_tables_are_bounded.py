"""VV4's confirm tables must never be indexed past their end.

A player hit this: the Tech menu opened the "Grant Youth" popup under the
"Villager Upgrades" title, and the game then crashed. The crash dump names the
mechanism exactly --

    ACCESS_VIOLATION reading 0x1C131105, in user32.dll, EDI = 0x3E8

-- 0x3E8 is ID_BUY_FIRST, so it died setting a row button's caption from a
garbage string pointer.

`g_villager_names` and `g_villager_costs` hold five entries; the Tech menu has
fourteen rows. Indexed raw by `row`, rows 5..13 read past the end of the array
and hand user32 whatever follows in .rdata.

The wrong-mode trigger is a separate, still-open question. This asserts the
consequence is contained: whatever mode the dialog ends up in, a row lookup
returns a real string or "" and never walks off the table.

Asserted on the C source rather than the built DLL because what is being
guaranteed is a *property of every call site* -- that none of them subscript
the tables directly -- which the compiled form does not preserve legibly.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "native" / "vv4_origins_icons" / "vv4_origins_icons.c"

TABLES = ("g_villager_names", "g_villager_costs", "g_tech_names", "g_tech_costs")


def _source() -> str:
    return SOURCE.read_text(encoding="utf-8", errors="replace")


class VV4ConfirmTableBoundsTests(unittest.TestCase):
    def test_the_source_is_present(self) -> None:
        """Without this the whole file would pass vacuously."""
        self.assertTrue(SOURCE.is_file(), f"{SOURCE} is missing")
        self.assertIn("g_villager_names", _source())

    def test_no_table_is_subscripted_directly(self) -> None:
        """Every lookup must go through the bounds-checked accessors.

        The accessors themselves are the sole exception, and they are matched
        and excluded by name so adding a second raw call site still fails.
        """
        src = _source()
        # Drop the two accessor bodies; everything else must be subscript-free.
        without_accessors = re.sub(
            r"static const char \*vv4_row_(?:name|cost)\(.*?\n\}\n",
            "", src, flags=re.S)
        for table in TABLES:
            with self.subTest(table=table):
                hits = re.findall(rf"\b{table}\s*\[", without_accessors)
                # The declaration itself is `g_x[5] = {` -- allow exactly that.
                decls = re.findall(
                    rf"static const char \*const {table}\s*\[", without_accessors)
                self.assertEqual(
                    len(hits), len(decls),
                    f"{table} is subscripted outside vv4_row_name/vv4_row_cost; "
                    "route it through the accessor so a row past the end of the "
                    "table cannot reach user32 as a garbage pointer",
                )

    def test_both_accessors_bound_every_branch(self) -> None:
        src = _source()
        for fn in ("vv4_row_name", "vv4_row_cost"):
            with self.subTest(accessor=fn):
                m = re.search(rf"static const char \*{fn}\(.*?\n\}}", src, re.S)
                self.assertIsNotNone(m, f"{fn} is missing")
                body = m.group(0)
                self.assertIn("row < 0", body,
                              f"{fn} does not reject a negative row")
                self.assertEqual(
                    body.count("VV4_ARRAY_LEN"), 2,
                    f"{fn} must bound BOTH the villager and the tech branch")
                self.assertIn('""', body,
                              f"{fn} must fall back to an empty string")

    def test_the_villager_tables_are_still_shorter_than_the_tech_rows(self) -> None:
        """The premise of the bug: 5-entry tables, 14-row menu.

        If these ever match, the guard stops being load-bearing and this test
        should be revisited rather than silently passing for a new reason.
        """
        src = _source()
        villager = int(re.search(r"g_villager_names\[(\d+)\]", src).group(1))
        tech = int(re.search(r"g_tech_names\[(\d+)\]", src).group(1))
        self.assertLess(
            villager, tech,
            "the villager tables are no longer shorter than the tech tables; "
            "re-check whether the overflow this guards is still possible")


if __name__ == "__main__":
    unittest.main()
