"""The Tree of Life (VV4) and New Believers (VV5) reset obviously corrupted
skill values instead of refusing (v1.35.70).

The owner: "Can you reset obviously-corrupted skill values?"  Both games keep
their skills as floats that the stock writer (VV4 0x46AD80, VV5 0x475730)
clamps to 0..100, so the only impossible values are NaN, +-infinity, negatives
and values above 100.  Every skill upgrade -- Grant Full Mastery (Tech and
Details), Equal Division of Labor (both), Check Highest Skill (both) and Clear
All Skill Preferences -- now repairs those on the villagers it acts on, after
the player confirms: NaN / infinity / negative -> 0, above 100 -> 100.  -0.0 is
a valid zero and is never touched.  A repair alone is never charged for, and
every result after one ends with "Reset N corrupted skill value(s)."

These tests run the real page routines and the real companions in unicorn over
the rendered executables (every population mode, 150 and 256 slots where the
routine walks the village).  The Details Grant Full Mastery rows have their own
emulation in test_mastery_invalid_skills_vv4_vv5.py.
"""
from __future__ import annotations

import math
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

import build_vv5_task9_native_actions as vv5_builder  # noqa: E402

VV4_DLL = ROOT / "assets" / "origins" / "VVFP VV4 Origins Icons.dll"
VV5_DLL = ROOT / "data" / "candidates" / "VVFP VV5 Task9 Origins Icons.dll"
MODES = ("stock", "collection_progression", "immediate_fixed")

F100 = 0x42C80000
NAN = 0x7FC00000
POS_INF = 0x7F800000
NEG_INF = 0xFF800000
NEG_ZERO = 0x80000000


def _bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def _f32(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", bits))[0]


def _writer(current: int, delta: int) -> int:
    """The stock skill writer's store (VV4 0x46AD80 / VV5 0x475730): current
    + delta, an ordered result above 100.0 clamped to 100.0, one below 0 to 0,
    NaN stored as computed."""
    total = _f32(current) + _f32(delta)
    if math.isnan(total):
        return NAN
    if total > 100.0:
        return F100
    if total < 0.0:
        return 0
    return _bits(total)


def _repaired(bits: int) -> int:
    """The rule both companions and both page routines implement."""
    if bits & 0x7FFFFFFF >= 0x7F800000:
        return 0
    if bits & 0x80000000 and bits != NEG_ZERO:
        return 0
    if bits > F100 and not bits & 0x80000000:
        return F100
    return bits


class RepairRule(unittest.TestCase):
    def test_only_impossible_values_change(self) -> None:
        cases = {
            0: 0, NEG_ZERO: NEG_ZERO, 1: 1, _bits(55.5): _bits(55.5), F100: F100,
            _bits(100.00001): F100, _bits(150.0): F100, _bits(1e30): F100,
            NAN: 0, 0xFFC00000: 0, 0x7F800001: 0, POS_INF: 0, NEG_INF: 0,
            _bits(-1.0): 0, 0x80000001: 0, _bits(-1e30): 0,
        }
        for bits, expected in cases.items():
            with self.subTest(bits=hex(bits)):
                self.assertEqual(_repaired(bits), expected)

    def test_the_writer_clamps_to_0_100_so_max_is_100(self) -> None:
        # The game's own clamp (see vv4/vv5 companion comments): 150 -> 100,
        # -5 -> 0, and it cannot master a NaN.
        self.assertEqual(_writer(_bits(90.0), _bits(60.0)), F100)
        self.assertEqual(_writer(_bits(5.0), _bits(-10.0)), 0)
        self.assertEqual(_writer(NAN, _bits(10.0)), NAN)
        # Every repaired value is mastered exactly by the writer.
        for bits in (NAN, POS_INF, NEG_INF, _bits(-3.0), _bits(150.0)):
            fixed = _repaired(bits)
            self.assertEqual(_writer(fixed, _bits(100.0 - _f32(fixed))), F100, hex(bits))

    def test_companion_sources_implement_it(self) -> None:
        for path, name in ((ROOT / "native/vv4_origins_icons/vv4_origins_icons.c", "vv4_skill_repair_bits"),
                           (ROOT / "native/vv5_task9_origins/vv5_task9_origins.c", "vv5_skill_repair_bits")):
            src = path.read_text(encoding="utf-8", errors="replace")
            start = src.index(f"static int {name}(")
            body = src[start:src.index("\n}\n", start)]
            self.assertIn("(bits & 0x7FFFFFFFu) >= 0x7F800000u", body)
            self.assertIn("bits != 0x80000000u", body)
            self.assertIn("0x42C80000u", src[start - 200:start])
            # A plain store, never the awarding writer.
            self.assertNotIn("0x46AD80", body)
            self.assertNotIn("0x475730", body)


# ------------------------------------------------------------------ VV4

VV4_STRIDE = 0x2E3C
VV4_ACTIVE, VV4_GHOST, VV4_HEALTH, VV4_SEX = 0x1CC4, 0x1CC7, 0x1C40, 0x1B90
VV4_SKILLS, VV4_PREF = 0x1C5C, 0x1C70


def _vv4(mode: str = "collection_progression", with_256: bool = False):
    from story_emulator import Process
    from vv4_population_256_harness import render

    proc = Process(render(mode, with_256, True), VV4_DLL)
    proc.api_handlers["GetForegroundWindow"] = lambda p: (0, 0)
    manager = struct.unpack("<I", proc.read(0x488D71, 4))[0]
    proc.slots = struct.unpack("<I", proc.read(0x42001C, 4))[0]
    proc.base = manager + 0x44
    for i in range(proc.slots):
        proc.write(proc.base + i * VV4_STRIDE + VV4_ACTIVE, b"\0")
    return proc


def _vv4_villager(proc, slot: int, skills: list[int], *, health: int = 50, ghost: int = 0,
                  sex: int = 0, pref: int = -1) -> int:
    r = proc.base + slot * VV4_STRIDE
    proc.write(r + VV4_ACTIVE, b"\x01")
    proc.write(r + VV4_GHOST, bytes([ghost]))
    proc.put32(r + VV4_HEALTH, health)
    proc.put32(r + VV4_SEX, sex)
    proc.put32(r + VV4_PREF, pref)
    proc.write(r + VV4_SKILLS, struct.pack("<5I", *skills))
    return r


def _vv4_skills(proc, r: int) -> list[int]:
    return list(struct.unpack("<5I", proc.read(r + VV4_SKILLS, 20)))


def _c_string(proc, text: str) -> int:
    at = proc.alloc(len(text) + 1)
    proc.write(at, text.encode("latin-1") + b"\0")
    return at


class VV4TechFullMastery(unittest.TestCase):
    """ConfirmOriginsVillageWide(7) + ShowOriginsVillageWideResult(7)."""

    A = [_bits(10.0), NAN, F100, _bits(150.0), _bits(-3.0)]
    B = [F100, F100, F100, F100, NEG_ZERO]          # valid: -0.0 is mastered, not reset
    C = [F100, F100, _bits(150.0), F100, F100]      # full once repaired

    def _village(self, proc):
        a = _vv4_villager(proc, 0, self.A)
        b = _vv4_villager(proc, 1, self.B)
        c = _vv4_villager(proc, proc.slots - 1, self.C)
        dead = _vv4_villager(proc, 2, [NAN] * 5, health=0)
        ghost = _vv4_villager(proc, 3, [NAN] * 5, ghost=1)
        return a, b, c, dead, ghost

    def test_confirmed_purchase_repairs_then_reports(self) -> None:
        for mode in MODES:
            for with_256 in (False, True):
                with self.subTest(mode=mode, with_256=with_256):
                    proc = _vv4(mode, with_256)
                    a, b, c, dead, ghost = self._village(proc)
                    self.assertEqual(proc.export("ConfirmOriginsVillageWide", 7), 1)
                    self.assertTrue(proc.messages[-1].startswith(
                        "Do you want to buy Grant Full Mastery to All Villagers"))
                    self.assertEqual(_vv4_skills(proc, a), [_bits(10.0), 0, F100, F100, 0])
                    self.assertEqual(_vv4_skills(proc, b), self.B)
                    self.assertEqual(_vv4_skills(proc, c), [F100] * 5)
                    self.assertEqual(_vv4_skills(proc, dead), [NAN] * 5, "the dead are never touched")
                    self.assertEqual(_vv4_skills(proc, ghost), [NAN] * 5)
                    proc.export("ShowOriginsVillageWideResult", 7, 0, 0, 0)
                    self.assertEqual(proc.messages[-1],
                                     "Granted Full Mastery to 2 Villagers.\r\n\r\n"
                                     "Skipped 1 Villager: already fully mastered.\r\n\r\n"
                                     "Reset 4 corrupted skill values.")

    def test_cancel_changes_nothing(self) -> None:
        proc = _vv4()
        a, b, c, dead, ghost = self._village(proc)
        proc.message_answer = 2                     # IDCANCEL
        self.assertEqual(proc.export("ConfirmOriginsVillageWide", 7), 0)
        self.assertEqual(_vv4_skills(proc, a), self.A)
        self.assertEqual(_vv4_skills(proc, c), self.C)
        # Nothing was repaired, so the next payload message has no Reset line.
        proc.export("ShowOriginsUpgradeMessage", _c_string(proc, "Origins Upgrades"),
                    _c_string(proc, "Not enough tech points."))
        self.assertEqual(proc.messages[-1], "Not enough tech points.")

    def test_nothing_to_buy_but_a_repair_is_free(self) -> None:
        proc = _vv4()
        c = _vv4_villager(proc, 0, self.C)
        self.assertEqual(proc.export("ConfirmOriginsVillageWide", 7), 0)
        self.assertEqual(proc.messages, [
            "Everyone has already mastered their skills. No tech points have been deducted."
            "\r\n\r\nReset 1 corrupted skill value."])
        self.assertEqual(_vv4_skills(proc, c), [F100] * 5)

    def test_already_mastered_village_has_no_reset_line(self) -> None:
        proc = _vv4()
        _vv4_villager(proc, 0, [F100] * 5)
        self.assertEqual(proc.export("ConfirmOriginsVillageWide", 7), 0)
        self.assertEqual(proc.messages, [
            "Everyone has already mastered their skills. No tech points have been deducted."])

    def test_payload_result_after_the_repair_carries_the_line_once(self) -> None:
        # Confirmed but the payload then finds the balance short: its own
        # "Not enough tech points." reports the repair, and only once.
        proc = _vv4()
        self._village(proc)
        self.assertEqual(proc.export("ConfirmOriginsVillageWide", 7), 1)
        title = _c_string(proc, "Origins Upgrades")
        proc.export("ShowOriginsUpgradeMessage", title, _c_string(proc, "Not enough tech points."))
        self.assertEqual(proc.messages[-1],
                         "Not enough tech points.\r\n\r\nReset 4 corrupted skill values.")
        proc.export("ShowOriginsUpgradeMessage", title, _c_string(proc, "Not enough tech points."))
        self.assertEqual(proc.messages[-1], "Not enough tech points.")


class VV4EqualDivision(unittest.TestCase):
    """ApplyVV4EqualDivision* runs after the payload's confirm and charge."""

    def test_repairs_eligible_villagers_before_rating_them(self) -> None:
        for export in ("ApplyVV4EqualDivisionParenting", "ApplyVV4EqualDivisionNoParenting"):
            for with_256 in (False, True):
                with self.subTest(export=export, with_256=with_256):
                    proc = _vv4("collection_progression", with_256)
                    a = _vv4_villager(proc, 0, [NAN, _bits(20.0), POS_INF, 0, _bits(500.0)])
                    b = _vv4_villager(proc, proc.slots - 1, [_bits(-2.0), NEG_ZERO, 0, 0, 0], sex=1)
                    dead = _vv4_villager(proc, 1, [NAN] * 5, health=-1)
                    self.assertEqual(proc.export(export), 2)
                    self.assertEqual(_vv4_skills(proc, a), [0, _bits(20.0), 0, 0, F100])
                    self.assertEqual(_vv4_skills(proc, b), [0, NEG_ZERO, 0, 0, 0])
                    self.assertEqual(_vv4_skills(proc, dead), [NAN] * 5)
                    self.assertTrue(proc.messages[-1].startswith("Set 2 Villagers' Job Preferences."))
                    self.assertTrue(proc.messages[-1].endswith(
                        "\r\n\r\nReset 4 corrupted skill values."), proc.messages[-1])

    def test_clean_village_has_no_reset_line(self) -> None:
        proc = _vv4()
        _vv4_villager(proc, 0, [_bits(5.0), 0, 0, 0, 0])
        proc.export("ApplyVV4EqualDivisionParenting")
        self.assertNotIn("Reset", proc.messages[-1])
        self.assertTrue(proc.messages[-1].endswith("Breeding: 0 Villagers (0 Male, 0 Female)."))


class VV4SkillPreferenceRows(unittest.TestCase):
    """vv4_skill_pref_buy runs inside the menu dialog after its confirm, so
    it is checked in the source: repair first, on vv_eligible villagers, and
    every result carries the line."""

    def setUp(self) -> None:
        src = (ROOT / "native/vv4_origins_icons/vv4_origins_icons.c").read_text(
            encoding="utf-8", errors="replace")
        start = src.index("static int vv4_skill_pref_buy(int kind) {")
        self.body = src[start:src.index("\n}\n", start)]

    def test_repair_precedes_every_read(self) -> None:
        repair = self.body.index("repaired += vv4_repair_skills(r, 1);")
        self.assertIn("if (vv_eligible(r)) repaired += vv4_repair_skills(r, 1);", self.body)
        self.assertLess(repair, self.body.index("vv4_skill_pref_scan(kind, 0,"))

    def test_every_result_after_it_reports_it(self) -> None:
        self.assertEqual(self.body.count("vv4_reset_line("), 3)
        for marker in ("already cleared", "Not enough tech points.", "Cleared %d %s Skill %s."):
            at = self.body.index(marker)
            self.assertIn("vv4_reset_line(", self.body[at:at + 900])


# ------------------------------------------------------------------ VV5

PAGE = 0x7C9000
TECH = 0x51D5F8
CHARGE = 0x4237B0
WRITER = 0x475730
VV5_STRIDE = 0x2F44
ACTIVE, MASK, FACTION, HEALTH, SEX = 0x1CD4, 0x1CE1, 0x1CEC, 0x1C40, 0x1B90
PREFERENCE, SKILLS = 0x1C74, 0x1C5C
OWNER = 0x1234
PID = 77


def _vv5(mode: str = "collection_progression", with_256: bool = False):
    from story_emulator import Process
    from vv5_population_256_harness import render

    proc = Process(render(mode, with_256, True), VV5_DLL)
    proc.api_handlers["GetForegroundWindow"] = lambda p: (OWNER, 0)
    proc.api_handlers["IsWindow"] = lambda p: (1, 4)

    def thread_pid(p):
        if p.arg(1):
            p.put32(p.arg(1), PID)
        return 1, 8
    proc.api_handlers["GetWindowThreadProcessId"] = thread_pid
    proc.api_handlers["GetCurrentProcessId"] = lambda p: (PID, 0)

    def load(p):
        return (proc.dll_base if p.cstring(p.arg(0)) == "VVFP Origins Icons.dll" else 0), 4
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

    def writer(p):
        slot = p.reg("ecx") + 4 * p.arg(0)
        p.put32(slot, _writer(p.u32(slot), p.arg(1)))
        proc.writes.append(p.arg(0))
        return 0, 8
    proc.writes = []
    proc.stub(WRITER, writer)
    assert proc.export("BeginOriginsOwner") == 1
    manager = struct.unpack("<I", proc.read(0x494051, 4))[0]
    proc.base = manager + 0x48
    proc.slots = struct.unpack("<I", proc.read(0x41F1E6, 4))[0]
    for i in range(proc.slots):
        proc.write(proc.base + i * VV5_STRIDE + ACTIVE, b"\0")
    proc.put32(TECH, 2_000_000)
    return proc


def _vv5_villager(proc, slot: int, skills: list[int], *, sex: int = 0, preference: int = -1,
                  mask: int = 0, faction: int = 0, health: int = 50) -> int:
    r = proc.base + slot * VV5_STRIDE
    proc.write(r + ACTIVE, b"\x01")
    proc.write(r + MASK, bytes([mask]))
    proc.write(r + FACTION, bytes([faction]))
    proc.put32(r + HEALTH, health)
    proc.put32(r + SEX, sex)
    proc.put32(r + PREFERENCE, preference)
    proc.write(r + SKILLS, struct.pack("<6I", *skills))
    return r


def _vv5_skills(proc, r: int) -> list[int]:
    return list(struct.unpack("<6I", proc.read(r + SKILLS, 24)))


def _vv5_pref(proc, r: int) -> int:
    return struct.unpack("<i", proc.read(r + PREFERENCE, 4))[0]


class VV5TechFullMastery(unittest.TestCase):
    """The page's mastery_all routine (Tech row 7) with the real companion."""

    A = [_bits(10.0), NAN, F100, _bits(150.0), _bits(-3.0), NEG_INF]
    B = [F100] * 5 + [NEG_ZERO]
    C = [F100, F100, _bits(150.0), F100, F100, F100]

    def test_confirmed_purchase_repairs_masters_and_reports(self) -> None:
        for mode in MODES:
            for with_256 in (False, True):
                with self.subTest(mode=mode, with_256=with_256):
                    proc = _vv5(mode, with_256)
                    a = _vv5_villager(proc, 0, self.A)
                    b = _vv5_villager(proc, 1, self.B)
                    c = _vv5_villager(proc, proc.slots - 1, self.C)
                    heathen = _vv5_villager(proc, 2, [NAN] * 6, mask=2)
                    other = _vv5_villager(proc, 3, [NAN] * 6, faction=1)
                    dead = _vv5_villager(proc, 4, [NAN] * 6, health=0)
                    proc.call(PAGE + vv5_builder.OFF["mastery_all"])
                    self.assertIn("Do you want to buy Grant Full Mastery to All Villagers",
                                  proc.messages[0])
                    for r in (a, b, c):
                        self.assertEqual(_vv5_skills(proc, r), [F100] * 6)
                    for r in (heathen, other, dead):
                        self.assertEqual(_vv5_skills(proc, r), [NAN] * 6)
                    self.assertEqual(proc.charges, [-1_000_000])
                    self.assertEqual(proc.messages[-1],
                                     "Granted Full Mastery to 2 Villagers.\r\n\r\n"
                                     "Skipped 1 Villager: already fully mastered.\r\n\r\n"
                                     "Reset 5 corrupted skill values.")

    def test_cancel_repairs_nothing(self) -> None:
        proc = _vv5()
        a = _vv5_villager(proc, 0, self.A)
        proc.message_answer = 2
        proc.call(PAGE + vv5_builder.OFF["mastery_all"])
        self.assertEqual(_vv5_skills(proc, a), self.A)
        self.assertEqual(proc.charges, [])
        self.assertNotIn("Reset", proc.messages[-1])

    def test_a_repair_alone_is_not_charged(self) -> None:
        proc = _vv5()
        c = _vv5_villager(proc, 0, self.C)
        proc.call(PAGE + vv5_builder.OFF["mastery_all"])
        self.assertEqual(_vv5_skills(proc, c), [F100] * 6)
        self.assertEqual(proc.writes, [])
        self.assertEqual(proc.charges, [])
        self.assertEqual(proc.messages[-1],
                         "Everyone has already mastered their skills. No tech points have been "
                         "deducted.\r\n\r\nReset 1 corrupted skill value.")

    def test_insufficient_repairs_nothing(self) -> None:
        proc = _vv5()
        a = _vv5_villager(proc, 0, self.A)
        proc.put32(TECH, 999_999)
        proc.call(PAGE + vv5_builder.OFF["mastery_all"])
        self.assertEqual(_vv5_skills(proc, a), self.A)
        self.assertEqual(proc.messages[-1], "Not enough tech points.")


class VV5EqualDivision(unittest.TestCase):
    def test_repairs_before_rating_and_reports(self) -> None:
        for name in ("division_parenting", "division_no_parenting"):
            for with_256 in (False, True):
                with self.subTest(routine=name, with_256=with_256):
                    proc = _vv5("collection_progression", with_256)
                    a = _vv5_villager(proc, 0, [NAN, 0, 0, 0, _bits(300.0), 0])
                    b = _vv5_villager(proc, proc.slots - 1, [_bits(-1.0), 0, 0, 0, 0, NEG_ZERO], sex=1)
                    heathen = _vv5_villager(proc, 1, [NAN] * 6, mask=1)
                    proc.call(PAGE + vv5_builder.OFF[name])
                    self.assertEqual(_vv5_skills(proc, a), [0, 0, 0, 0, F100, 0])
                    self.assertEqual(_vv5_skills(proc, b), [0, 0, 0, 0, 0, NEG_ZERO])
                    self.assertEqual(_vv5_skills(proc, heathen), [NAN] * 6)
                    self.assertEqual(proc.charges, [-1_000_000])
                    self.assertTrue(proc.messages[-1].endswith(
                        "\r\n\r\nReset 3 corrupted skill values."), proc.messages[-1])

    def test_no_change_keeps_the_repair_and_charges_nothing(self) -> None:
        proc = _vv5()
        a = _vv5_villager(proc, 0, [_bits(10.0), 0, 0, 0, 0, 0])
        proc.call(PAGE + vv5_builder.OFF["division_parenting"])
        self.assertEqual(proc.charges, [-1_000_000])
        proc.write(a + SKILLS + 4, struct.pack("<I", POS_INF))
        proc.call(PAGE + vv5_builder.OFF["division_parenting"])
        self.assertEqual(proc.charges, [-1_000_000])
        self.assertEqual(_vv5_skills(proc, a)[1], 0)
        self.assertEqual(proc.messages[-1],
                         "Every villager already has this division of labor. No tech points have "
                         "been deducted.\r\n\r\nReset 1 corrupted skill value.")


class VV5SkillPreferenceRows(unittest.TestCase):
    def _row(self, proc, row: int) -> None:
        proc.call(PAGE + vv5_builder.OFF["skill_rows"], regs={"ebx": row})

    def test_check_highest_skill_rates_the_repaired_values(self) -> None:
        for mode in MODES:
            for with_256 in (False, True):
                with self.subTest(mode=mode, with_256=with_256):
                    proc = _vv5(mode, with_256)
                    a = _vv5_villager(proc, 0, [_bits(10.0), 0, 0, 0, _bits(200.0), POS_INF])
                    b = _vv5_villager(proc, proc.slots - 1, [NAN, 0, _bits(-4.0), 0, 0, 0], preference=2)
                    heathen = _vv5_villager(proc, 1, [NAN] * 6, mask=3)
                    self._row(proc, 14)
                    self.assertEqual(_vv5_skills(proc, a), [_bits(10.0), 0, 0, 0, F100, 0])
                    self.assertEqual(_vv5_skills(proc, b), [0] * 6)
                    self.assertEqual(_vv5_skills(proc, heathen), [NAN] * 6)
                    self.assertEqual([_vv5_pref(proc, a), _vv5_pref(proc, b)], [4, 2])
                    self.assertEqual(proc.charges, [-1_000_000])
                    self.assertTrue(proc.messages[-1].endswith(
                        "Skipped 1 Villager: no skill progress yet.\r\n\r\n"
                        "Reset 4 corrupted skill values."), proc.messages[-1])

    def test_clear_repairs_and_no_change_still_reports(self) -> None:
        proc = _vv5()
        a = _vv5_villager(proc, 0, [_bits(150.0), 0, 0, 0, 0, 0], preference=3)
        self._row(proc, 13)
        self.assertEqual(_vv5_skills(proc, a)[0], F100)
        self.assertEqual(proc.messages[-1],
                         "Cleared 1 Villager's Skill Preferences.\r\n\r\nReset 1 corrupted skill value.")
        proc.write(a + SKILLS, struct.pack("<I", NAN))
        self._row(proc, 13)
        self.assertEqual(proc.charges, [-500_000])
        self.assertEqual(_vv5_skills(proc, a)[0], 0)
        self.assertEqual(proc.messages[-1],
                         "Every villager's skill preference is already cleared. No tech points have "
                         "been deducted.\r\n\r\nReset 1 corrupted skill value.")

    def test_cancel_repairs_nothing(self) -> None:
        proc = _vv5()
        a = _vv5_villager(proc, 0, [NAN, 0, 0, 0, 0, 0], preference=3)
        proc.message_answer = 2
        self._row(proc, 13)
        self.assertEqual(_vv5_skills(proc, a)[0], NAN)
        self.assertEqual(_vv5_pref(proc, a), 3)


if __name__ == "__main__":
    unittest.main()
