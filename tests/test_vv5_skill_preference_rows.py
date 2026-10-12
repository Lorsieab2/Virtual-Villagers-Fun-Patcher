"""New Believers' three skill-preference Tech rows.

Clear All Skill Preferences (row 13, 500,000), Check Highest Skill (Includes
Parenting) (row 14, 1,000,000) and Check Highest Skill (No Parenting) (row 15,
1,000,000) sit after the two Equal Division of Labor rows; Change Appearance
for All moved to row 16.  The Task9 page routes rows 13..16 through one
`skill_rows` entry to the companion export ShowVV5SkillPreferenceUpgrade(row +
13), which owns the whole transaction and prices it through vvfp_story_price.

The emulated tests run the real page routine and the real companion DLL in
unicorn over the rendered executable of every population mode, 150 and 256
slots."""
from __future__ import annotations

import json
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

import build_vv5_task9_native_actions as builder  # noqa: E402

NATIVE = ROOT / "native/vv5_task9_origins/vv5_task9_origins.c"
RC = ROOT / "native/vv5_task9_origins/vv5_task9_origins.rc"
DEF = ROOT / "native/vv5_task9_origins/vv5_task9_origins.def"
DLL = ROOT / "data/candidates/VVFP VV5 Task9 Origins Icons.dll"
MANIFEST = ROOT / "data/vv5_task9_native_actions.json"

PAGE = 0x7C9000
TECH = 0x51D5F8
CHARGE = 0x4237B0
STRIDE = 0x2F44
ACTIVE, MASK, FACTION, HEALTH, SEX = 0x1CD4, 0x1CE1, 0x1CEC, 0x1C40, 0x1B90
PREFERENCE, SKILLS = 0x1C74, 0x1C5C
OWNER = 0x1234
PID = 77


def _rows(dialog: str) -> list[tuple[str, str, int]]:
    pattern = re.compile(
        r'^\s*LTEXT\s+"([^"]+)"[^\r\n]*\r?\n'
        r'\s*LTEXT\s+"([^"]+)"[^\r\n]*\r?\n'
        r'\s*PUSHBUTTON\s+"Buy"\s*,\s*(\d+)\b',
        re.MULTILINE,
    )
    return [(a, b, int(c)) for a, b, c in pattern.findall(dialog)]


class SourceAndRoutingTests(unittest.TestCase):
    def test_rows_follow_equal_division_in_the_tech_dialog(self) -> None:
        tech = RC.read_text(encoding="utf-8").split("202 DIALOGEX", 1)[0]
        rows = _rows(tech)
        self.assertEqual(rows[11:], [
            ("Equal Division of Labor (Includes Parenting)", "1,000,000 tech points", 1011),
            ("Equal Division of Labor (No Parenting)", "1,000,000 tech points", 1012),
            ("Clear All Skill Preferences", "500,000 tech points", 1013),
            ("Check Highest Skill (Includes Parenting)", "1,000,000 tech points", 1014),
            ("Check Highest Skill (No Parenting)", "1,000,000 tech points", 1015),
            ("Change Appearance for All", "450,000 tech points", 1016),
        ])

    def test_companion_names_prices_and_exports(self) -> None:
        native = NATIVE.read_text(encoding="utf-8")
        self.assertIn("ID_BUY_LAST = 1016", native)
        self.assertIn("int row_count = villager_menu ? 5 : 17;", native)
        self.assertIn('case ACTION_CLEAR_SKILL_PREFERENCES: return "Clear All Skill Preferences";', native)
        self.assertIn('case ACTION_HIGHEST_SKILL_PARENTING: return "Check Highest Skill (Includes Parenting)";', native)
        self.assertIn('case ACTION_HIGHEST_SKILL_NO_PARENTING: return "Check Highest Skill (No Parenting)";', native)
        self.assertIn('case ACTION_CLEAR_SKILL_PREFERENCES: return "500,000";', native)
        # The price shown and the price charged both go through the Story /
        # Cheat Upgrades row: action_cost answers "0" first, and the charge is
        # vvfp_story_price, which is 0 while that row is active.
        cost = native[native.index("static const char *action_cost"):]
        self.assertLess(cost.index('return "0";'), cost.index("ACTION_CLEAR_SKILL_PREFERENCES"))
        self.assertIn("price = vvfp_story_price(5, clear ? 500000 : 1000000);", native)
        self.assertIn("ShowVV5SkillPreferenceUpgrade=_ShowVV5SkillPreferenceUpgrade@4",
                      DEF.read_text(encoding="utf-8"))
        self.assertIn(b"ShowVV5SkillPreferenceUpgrade\0", DLL.read_bytes())
        self.assertIn("Clear All Skill Preferences".encode("utf-16-le"), DLL.read_bytes())

    def test_late_rows_ignore_the_pending_event_state_bits(self) -> None:
        # Row 15/16's "unavailable" bit would be STATE_ISLAND_PENDING /
        # STATE_BARREL_PENDING; only rows 0..13 own state bits.
        native = NATIVE.read_text(encoding="utf-8")
        self.assertIn("#define VV5_ROWS_WITH_STATE_BITS 14", native)
        self.assertIn("row < VV5_ROWS_WITH_STATE_BITS\n                    && (lparam & (1L << (8 + row))) != 0", native)
        self.assertIn("row < VV5_ROWS_WITH_STATE_BITS && (lparam & (1 << row)) != 0", native)

    def test_stock_page_routes_rows_13_to_16_and_expanded_does_not(self) -> None:
        stock, stock_map = builder.build_page(PAGE)
        _, expanded_map = builder.build_page(0x904000)
        self.assertIn("skill_rows", stock_map["routine_length"])
        self.assertNotIn("skill_rows", expanded_map["routine_length"])
        tech = stock[builder.OFF["tech_menu"]: builder.OFF["tech_menu"] + builder.SIZES["tech_menu"]]
        self.assertIn(bytes.fromhex("83FB10"), tech)          # cmp ebx, 16 (bound)
        self.assertIn(bytes.fromhex("83FB0D0F83"), tech)      # cmp ebx, 13; jae (near)
        skill = stock[builder.OFF["skill_rows"]: builder.OFF["skill_rows"] + stock_map["routine_length"]["skill_rows"]]
        self.assertIn(bytes.fromhex("8D4B0D"), skill)         # lea ecx, [ebx+13]
        self.assertIn(int(stock_map["string_virtual_addresses"]["skill_export"], 16).to_bytes(4, "little"), skill)
        # No price immediate in the page: the companion prices it.
        for price in (500000, 1000000):
            self.assertNotIn(struct.pack("<i", price), skill)
            self.assertNotIn(struct.pack("<i", -price), skill)

    def test_every_mode_ships_the_route(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        layouts = manifest["pe_append_transaction"]["layouts"]
        for mode in ("collection_progression", "immediate_fixed"):
            with self.subTest(mode=mode):
                page = bytes.fromhex(layouts[mode]["append_bytes"])
                self.assertIn(b"ShowVV5SkillPreferenceUpgrade\0", page)
        # The stock population mode takes the collection-progression page.
        self.assertEqual(manifest["patch_mode_overrides"]["stock"],
                         manifest["patch_mode_overrides"]["collection_progression"])
        # Expanded-256 layouts keep their frozen page; the companion disables
        # the rows there (STATE_LIMITED_CAPABILITY, rows >= 6).
        for mode in ("experimental_expanded_256", "experimental_expanded_256_progression"):
            with self.subTest(mode=mode):
                self.assertNotIn(b"ShowVV5SkillPreferenceUpgrade\0",
                                 bytes.fromhex(layouts[mode]["append_bytes"]))

    def test_catalog_describes_the_rows(self) -> None:
        text = (ROOT / "data/vv5_origins_village_wide_upgrades.json").read_text(encoding="utf-8")
        self.assertIn("Clear All Skill Preferences (500,000 tech points)", text)
        self.assertIn("Check Highest Skill (Includes Parenting) / (No Parenting) (1,000,000 tech points each)", text)


class EmulatedTests(unittest.TestCase):
    """The page's skill_rows routine and the real companion, emulated."""

    def _process(self, mode: str = "collection_progression", with_256: bool = False):
        from story_emulator import Process
        from vv5_population_256_harness import render

        proc = Process(render(mode, with_256, True), DLL)
        proc.api_handlers["GetForegroundWindow"] = lambda p: (OWNER, 0)
        proc.api_handlers["IsWindow"] = lambda p: (1, 4)

        def thread_pid(p):
            if p.arg(1):
                p.put32(p.arg(1), PID)
            return 1, 8
        proc.api_handlers["GetWindowThreadProcessId"] = thread_pid
        proc.api_handlers["GetCurrentProcessId"] = lambda p: (PID, 0)

        def load(p):
            name = p.cstring(p.arg(0))
            return (proc.dll_base if name == "VVFP Origins Icons.dll" else 0), 4
        proc.api_handlers["LoadLibraryA"] = load
        proc.api_handlers["GetProcAddress"] = lambda p: (proc.exports.get(p.cstring(p.arg(1)), 0), 8)

        def charge(p):
            delta = struct.unpack("<i", struct.pack("<I", p.arg(0)))[0]
            balance = struct.unpack("<i", p.read(p.reg("ecx"), 4))[0]
            p.write(p.reg("ecx"), struct.pack("<i", balance + delta))
            proc.charges.append(delta)
            return 0, 4
        proc.charges = []
        proc.stub(CHARGE, charge)
        self.assertEqual(proc.export("BeginOriginsOwner"), 1)
        manager = struct.unpack("<I", proc.read(0x494051, 4))[0]
        proc.base = manager + 0x48
        proc.slots = struct.unpack("<I", proc.read(0x41F1E6, 4))[0]
        for i in range(proc.slots):
            proc.write(proc.base + i * STRIDE + ACTIVE, b"\0")
        proc.put32(TECH, 2_000_000)
        return proc

    def _villager(self, proc, slot, *, sex=0, preference=-1, skills=(0,) * 6,
                  mask=0, faction=0, health=50):
        r = proc.base + slot * STRIDE
        proc.write(r + ACTIVE, b"\x01")
        proc.write(r + MASK, bytes([mask]))
        proc.write(r + FACTION, bytes([faction]))
        proc.put32(r + HEALTH, health)
        proc.put32(r + SEX, sex)
        proc.put32(r + PREFERENCE, preference)
        proc.write(r + SKILLS, struct.pack("<6f", *skills))
        return r

    def _pref(self, proc, r):
        return struct.unpack("<i", proc.read(r + PREFERENCE, 4))[0]

    def _row(self, proc, row):
        """Run the page's own skill_rows entry with the Tech row in EBX."""
        return proc.call(PAGE + builder.OFF["skill_rows"], regs={"ebx": row})

    def test_clear_writes_minus_one_to_believers_only_and_charges_once(self):
        for mode in ("stock", "collection_progression", "immediate_fixed"):
            for with_256 in (False, True):
                with self.subTest(mode=mode, with_256=with_256):
                    proc = self._process(mode, with_256)
                    a = self._villager(proc, 0, preference=3)
                    b = self._villager(proc, 1, preference=-1)
                    last = self._villager(proc, proc.slots - 1, preference=0, sex=1)
                    heathen = self._villager(proc, 2, preference=2, mask=3)
                    other = self._villager(proc, 3, preference=4, faction=1)
                    dead = self._villager(proc, 4, preference=5, health=0)
                    self._row(proc, 13)
                    self.assertEqual([self._pref(proc, r) for r in (a, b, last)], [-1, -1, -1])
                    self.assertEqual([self._pref(proc, r) for r in (heathen, other, dead)], [2, 4, 5])
                    self.assertEqual(proc.charges, [-500000])
                    self.assertEqual(proc.u32(TECH), 1_500_000)
                    self.assertIn("Do you want to buy Clear All Skill Preferences for 500,000 tech points?",
                                  proc.messages[0])
                    self.assertEqual(proc.messages[-1], "Cleared 2 Villagers' Skill Preferences.")

    def test_clear_singular_and_no_change_and_nobody(self):
        proc = self._process()
        self._villager(proc, 0, preference=2)
        self._row(proc, 13)
        self.assertEqual(proc.messages[-1], "Cleared 1 Villager's Skill Preferences.")
        self._row(proc, 13)
        self.assertEqual(proc.messages[-1], "Every villager's skill preference is already cleared. "
                                            "No tech points have been deducted.")
        self.assertEqual(proc.charges, [-500000])
        proc = self._process()
        self._villager(proc, 0, preference=2, mask=1)
        self._row(proc, 13)
        self.assertEqual(proc.messages[-1], "No villagers were eligible. No tech points have been deducted.")
        self.assertEqual(proc.charges, [])

    def test_insufficient_and_cancel_charge_nothing(self):
        proc = self._process()
        r = self._villager(proc, 0, preference=2)
        proc.put32(TECH, 499_999)
        self._row(proc, 13)
        self.assertEqual(proc.messages[-1], "Not enough tech points.")
        proc.put32(TECH, 2_000_000)
        proc.message_answer = 2          # IDCANCEL
        self._row(proc, 13)
        self.assertEqual(proc.messages[-1], "Clear All Skill Preferences was canceled.\r\nNo tech points have been deducted.")
        self.assertEqual(self._pref(proc, r), 2)
        self.assertEqual(proc.charges, [])

    def test_check_highest_skill_includes_parenting(self):
        proc = self._process()
        a = self._villager(proc, 0, skills=(10, 50, 5, 5, 5, 5))           # Parenting highest
        b = self._villager(proc, 1, sex=1, skills=(20, 0, 0, 0, 20, 0))   # tie Farming/Building -> Farming
        c = self._villager(proc, 2, skills=(0, 0, 30, 30, 0, 0))          # tie Healing/Research -> Research
        d = self._villager(proc, 3, preference=2, skills=(0,) * 6)        # nothing yet: kept
        e = self._villager(proc, 4, preference=4, skills=(float("nan"), -1, 0, 0, 0, 0))
        heathen = self._villager(proc, 5, preference=-1, mask=2, skills=(90, 0, 0, 0, 0, 0))
        self._row(proc, 14)
        self.assertEqual([self._pref(proc, r) for r in (a, b, c, d, e, heathen)], [1, 0, 3, 2, 4, -1])
        self.assertEqual(proc.charges, [-1000000])
        self.assertIn("Check Highest Skill (Includes Parenting) for 1,000,000 tech points", proc.messages[0])
        self.assertEqual(proc.messages[-1],
                         "Set 3 Villagers' Job Preferences."
                         "\r\n\r\nFarming: 1 Villager (0 Male, 1 Female)."
                         "\r\n\r\nBuilding: 0 Villagers (0 Male, 0 Female)."
                         "\r\n\r\nResearch: 1 Villager (1 Male, 0 Female)."
                         "\r\n\r\nHealing: 0 Villagers (0 Male, 0 Female)."
                         "\r\n\r\nBreeding: 1 Villager (1 Male, 0 Female)."
                         "\r\n\r\nDevotion: 0 Villagers (0 Male, 0 Female)."
                         "\r\n\r\nSkipped 2 Villagers: no skill progress yet.")
        # Again: nothing changes, nothing is charged.
        self._row(proc, 14)
        self.assertEqual(proc.messages[-1], "Every villager already has their highest skill checked. "
                                            "No tech points have been deducted.")
        self.assertEqual(proc.charges, [-1000000])

    def test_check_highest_skill_no_parenting_ignores_parenting(self):
        proc = self._process()
        a = self._villager(proc, 0, skills=(10, 50, 5, 5, 5, 40))   # Parenting ignored -> Devotion
        b = self._villager(proc, 1, skills=(0, 90, 0, 0, 0, 0))     # only Parenting: skipped
        self._row(proc, 15)
        self.assertEqual([self._pref(proc, r) for r in (a, b)], [5, -1])
        self.assertNotIn("Breeding", proc.messages[-1])
        self.assertTrue(proc.messages[-1].startswith("Set 1 Villager's Job Preferences."))
        self.assertTrue(proc.messages[-1].endswith("Skipped 1 Villager: no skill progress yet."))
        self.assertEqual(proc.charges, [-1000000])

    def test_row_16_is_change_appearance_for_all(self):
        proc = self._process()
        seen = []
        proc.stub(PAGE + builder.OFF["appearance_all"], lambda p: (seen.append(1) or 0, 0))
        self._row(proc, 16)
        self.assertEqual(seen, [1])
        self.assertEqual(proc.messages, [])


if __name__ == "__main__":
    unittest.main()
