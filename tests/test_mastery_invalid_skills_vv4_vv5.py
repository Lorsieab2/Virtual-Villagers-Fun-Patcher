"""Grant Full Mastery refuses a villager whose skills it cannot master.

The Tree of Life (VV4) and New Believers (VV5) raise each skill float to 100.0
through the stock writer (VV4 0x46AD80, VV5 0x475730), which stores
``current + (100 - current)`` and clamps only an ordered result above 100. A
NaN or an infinity therefore comes back as NaN, and a far-out-of-range value
(set in Cheat Engine, say) as something other than 100.0 -- so the purchase
must be refused before any tech points are taken:

* VV5 Tech "Grant Full Mastery to All": a pre-scan of the same eligible
  Believers refuses with RESULT_INVALID_SKILL (9) before the confirm, exactly
  like the Details row; -0.0 is a valid zero. It used to skip such a villager
  silently and report it "already fully mastered".
* VV4 Tech "Grant Full Mastery to All Villagers": the companion's dry run
  (vv_scan_mastery) counts such villagers and the confirm refuses with VV5's
  wording; it used to confirm, charge, and let the payload stop part-way.
* VV4 Details "Grant Full Mastery": the companion refuses the click before the
  payload charges; and should the payload's post-check ever fail it now
  refunds the exact charge and says so, instead of showing "Not enough tech
  points." with the price kept.
"""
from __future__ import annotations

import importlib.util
import math
import re
import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import vv_fun_patcher as vfp  # noqa: E402

STOCK = ROOT / "research" / "stock-executables"
VV4_C = ROOT / "native" / "vv4_origins_icons" / "vv4_origins_icons.c"
VV5_C = ROOT / "native" / "vv5_task9_origins" / "vv5_task9_origins.c"
RETURN = 0x0F000800
STACK_TOP = 0x10800000
F100 = 0x42C80000
NAN = 0x7FC00000
INVALID_TEXT = (
    "Full Mastery cannot be applied because a skill is NaN, infinite, "
    "negative, or outside 0..100.\\r\\nNo tech points have been deducted."
)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _f32(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", bits))[0]


def _bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def _native_writer(current: int, delta: int) -> int:
    """The stock skill writer (VV4 0x46AD80 / VV5 0x475730, identical): store
    f32(current + delta); an ordered result above 100.0 is clamped to 100.0;
    anything else (including NaN) is stored as computed."""
    total = _f32(current) + _f32(delta)
    if math.isnan(total):
        return NAN
    total = _bits(total)
    return F100 if _f32(total) > 100.0 else total


def _stub(mu: Uc, pops: int, eax: int | None = None) -> None:
    esp = mu.reg_read(UC_X86_REG_ESP)
    ret = struct.unpack("<I", mu.mem_read(esp, 4))[0]
    mu.reg_write(UC_X86_REG_ESP, esp + 4 + pops)
    if eax is not None:
        mu.reg_write(UC_X86_REG_EAX, eax & 0xFFFFFFFF)
    mu.reg_write(UC_X86_REG_EIP, ret)


def _arg(mu: Uc, index: int) -> int:
    esp = mu.reg_read(UC_X86_REG_ESP)
    return struct.unpack("<I", mu.mem_read(esp + 4 + 4 * index, 4))[0]


# --------------------------------------------------------------- VV5 Tech row

VV5 = _load("vv5_task9_builder_mastery_invalid", ROOT / "scripts/build_vv5_task9_native_actions.py")
VV5_RECORDS = 0x554190
VV5_BALANCE = 0x51D5F8


def _run_vv5_mastery_all(villagers: list[dict]) -> dict:
    page_va = 0x7C9000
    page, _ = VV5.build_page(page_va)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(page_va, 0x8000)
    mu.mem_write(page_va, bytes(page))
    mu.mem_map(0x400000, 0x154000)                      # stubs + balance
    mu.mem_map(0x554000, 0x1C0000)                      # 150 records
    mu.mem_map(RETURN & ~0xFFF, 0x1000)
    mu.mem_map(STACK_TOP - 0x10000, 0x10000)
    mu.mem_write(RETURN, b"\xF4")
    balance = 2_000_000
    mu.mem_write(VV5_BALANCE, struct.pack("<I", balance))
    for i, v in enumerate(villagers):
        base = VV5_RECORDS + i * VV5.STRIDE
        mu.mem_write(base + 0x1CD4, bytes([v.get("active", 1)]))
        mu.mem_write(base + 0x1CE1, bytes([v.get("heathen", 0)]))
        mu.mem_write(base + 0x1CEC, bytes([0]))
        mu.mem_write(base + 0x1C40, struct.pack("<i", v.get("health", 50)))
        mu.mem_write(base + 0x1C5C, struct.pack("<6I", *v["skills"]))
    log = {"confirm": 0, "writes": [], "charges": [], "status": None}
    confirm = page_va + VV5.OFF["confirm"]
    status = page_va + VV5.OFF["status"]

    def hook(uc, address, size, _):
        if address == confirm:
            log["confirm"] += 1
            _stub(uc, 12, 1)
        elif address == status:
            log["status"] = tuple(_arg(uc, i) for i in range(4))
            _stub(uc, 16, 0)
        elif address == 0x475730:
            skills = uc.reg_read(UC_X86_REG_ECX)
            index, delta = _arg(uc, 0), _arg(uc, 1)
            current = struct.unpack("<I", uc.mem_read(skills + 4 * index, 4))[0]
            uc.mem_write(skills + 4 * index, struct.pack("<I", _native_writer(current, delta)))
            log["writes"].append(index)
            _stub(uc, 8)
        elif address == 0x4237B0:
            field = uc.reg_read(UC_X86_REG_ECX)
            delta = struct.unpack("<i", struct.pack("<I", _arg(uc, 0)))[0]
            value = struct.unpack("<i", uc.mem_read(field, 4))[0] + delta
            uc.mem_write(field, struct.pack("<i", max(value, 0)))
            log["charges"].append(delta)
            _stub(uc, 4)

    for address in (confirm, status, 0x475730, 0x4237B0):
        mu.hook_add(UC_HOOK_CODE, hook, begin=address, end=address)
    esp = STACK_TOP - 0x200
    mu.mem_write(esp, struct.pack("<I", RETURN))
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.emu_start(page_va + VV5.OFF["mastery_all"], RETURN, count=2_000_000)
    log["esp"] = mu.reg_read(UC_X86_REG_ESP) - esp
    log["balance"] = struct.unpack("<I", mu.mem_read(VV5_BALANCE, 4))[0]
    log["skills"] = [
        list(struct.unpack("<6I", mu.mem_read(VV5_RECORDS + i * VV5.STRIDE + 0x1C5C, 24)))
        for i in range(len(villagers))
    ]
    return log


GOOD = [_bits(10.0), _bits(55.5), F100, 0, _bits(99.0), _bits(1.0)]


class VV5TechMasteryRefusesInvalidSkills(unittest.TestCase):
    def _refused(self, bad: int) -> None:
        villagers = [{"skills": GOOD}, {"skills": [_bits(20.0), bad, F100, F100, F100, F100]}]
        log = _run_vv5_mastery_all(villagers)
        self.assertEqual(log["status"], (21, 9, 0, 0), "RESULT_INVALID_SKILL for row 21")
        self.assertEqual(log["confirm"], 0, "refused before the confirm")
        self.assertEqual(log["writes"], [], "no skill is written")
        self.assertEqual(log["charges"], [], "nothing is charged")
        self.assertEqual(log["balance"], 2_000_000)
        self.assertEqual(log["skills"][0], GOOD)
        self.assertEqual(log["esp"], 4)

    def test_nan_is_refused(self) -> None:
        self._refused(NAN)

    def test_infinities_are_refused(self) -> None:
        self._refused(0x7F800000)
        self._refused(0xFF800000)

    def test_negative_is_refused(self) -> None:
        self._refused(_bits(-1.0))

    def test_above_one_hundred_is_refused(self) -> None:
        self._refused(_bits(150.0))
        self._refused(_bits(100.00001))

    def test_ineligible_villagers_are_not_checked(self) -> None:
        bad = [NAN] * 6
        villagers = [
            {"skills": GOOD},
            {"skills": bad, "heathen": 1},
            {"skills": bad, "health": 0},
            {"skills": bad, "active": 0},
        ]
        log = _run_vv5_mastery_all(villagers)
        self.assertEqual(log["status"], (21, 0, 1, 0))
        self.assertEqual(log["charges"], [-1_000_000])
        self.assertEqual(log["skills"][0], [F100] * 6)
        for i in (1, 2, 3):
            self.assertEqual(log["skills"][i], bad)

    def test_valid_village_is_mastered_and_charged_once(self) -> None:
        villagers = [{"skills": GOOD}, {"skills": [F100] * 6}, {"skills": [0x80000000] + [F100] * 5}]
        log = _run_vv5_mastery_all(villagers)
        self.assertEqual(log["confirm"], 1)
        self.assertEqual(log["status"], (21, 0, 2, 1), "two granted, one already mastered")
        self.assertEqual(log["charges"], [-1_000_000])
        self.assertEqual(log["balance"], 1_000_000)
        for skills in log["skills"]:
            self.assertEqual(skills, [F100] * 6, "-0.0 is a valid zero and is mastered")

    def test_already_mastered_village_is_no_change(self) -> None:
        log = _run_vv5_mastery_all([{"skills": [F100] * 6}])
        self.assertEqual(log["status"], (21, 1, 0, 0))
        self.assertEqual(log["charges"], [])

    def test_docstring_names_the_real_price_and_record_count(self) -> None:
        doc = VV5.build_mastery_all.__doc__
        self.assertIn("1,000,000", doc)
        self.assertNotIn("300,000", doc)
        self.assertIn("150, or 256 with 256 Villagers", doc)

    def test_result_text_is_the_details_rows_invalid_skill_wording(self) -> None:
        src = VV5_C.read_text(encoding="utf-8")
        self.assertIn(INVALID_TEXT, src)


# --------------------------------------------------------- VV4 Details payload

VV4 = _load("vv4_origins_builder_mastery_invalid", ROOT / "scripts/build_vv4_origins_feature.py")
VV4_BALANCE = 0x4D6F88
VV4_OBJ = 0x30000000
VV4_REC = 0x31000000
_VV4_IMAGE: bytes | None = None


def _vv4_image() -> bytes:
    global _VV4_IMAGE
    if _VV4_IMAGE is None:
        feature = "vv4_enable_origins_exclusive_features"
        build = next(b for b in vfp.load_builds() if b.id == "vv4")
        ids = vfp.resolve_fun_patch_ids([feature], game_id="vv4")
        rendered, applied = vfp.render_patched_bytes(
            STOCK / "Virtual Villagers - The Tree of Life.exe", build, "immediate_fixed", ids)
        assert f"feature:{feature}" in {r["owner"] for r in applied}
        _VV4_IMAGE = bytes(rendered)
    return _VV4_IMAGE


def _read_c_string(mu: Uc, va: int) -> str:
    out = bytearray()
    while True:
        byte = mu.mem_read(va + len(out), 1)[0]
        if byte == 0:
            return out.decode("latin-1")
        out.append(byte)


def _run_vv4_details_mastery(skills: list[int], row: int = 1, health: int = 50, ghost: int = 0) -> dict:
    image = _vv4_image()
    pe = pefile.PE(data=image)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(0x400000, (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF)
    mu.mem_write(0x400000, image[:pe.OPTIONAL_HEADER.SizeOfHeaders])
    for section in pe.sections:
        mu.mem_write(0x400000 + section.VirtualAddress, section.get_data())
    mu.mem_map(VV4_OBJ, 0x20000)
    mu.mem_map(VV4_REC, 0x4000)
    mu.mem_map(RETURN & ~0xFFF, 0x1000)
    mu.mem_map(STACK_TOP - 0x10000, 0x10000)
    mu.mem_write(RETURN, b"\xF4")
    mu.mem_write(VV4_OBJ + 0x171B0, struct.pack("<I", 0))
    mu.mem_write(VV4_REC + 0x1CC4, b"\x01")
    mu.mem_write(VV4_REC + 0x1CC7, bytes([ghost]))
    mu.mem_write(VV4_REC + 0x1C40, struct.pack("<i", health))
    mu.mem_write(VV4_REC + 0x1B8C, struct.pack("<i", 400))
    mu.mem_write(VV4_REC + 0x1C5C, struct.pack("<5I", *skills))
    mu.mem_write(VV4_REC + 0x1E60, struct.pack("<3i", -1, -1, -1))
    mu.mem_write(VV4_REC + 0x1E6C, struct.pack("<3i", -1, -1, -1))
    balance = 150_000
    mu.mem_write(VV4_BALANCE, struct.pack("<I", balance))
    show_dialog = VV4.PAYLOAD_VA + 0x1B0
    show_message = VV4.VV4_RESULT_HELPER_VA
    log = {"dialogs": 0, "messages": [], "charges": [], "writes": []}

    def hook(uc, address, size, _):
        if address == 0x41FE70:
            _stub(uc, 0, VV4_OBJ)
        elif address == 0x466040:
            _stub(uc, 4, VV4_REC)
        elif address == show_dialog:
            log["dialogs"] += 1
            _stub(uc, 8, row if log["dialogs"] == 1 else -1)   # the row, then close
        elif address == show_message:
            log["messages"].append(_read_c_string(uc, _arg(uc, 1)))
            _stub(uc, 8, 0)
        elif address == 0x41E300:
            field = uc.reg_read(UC_X86_REG_ECX)
            delta = struct.unpack("<i", struct.pack("<I", _arg(uc, 0)))[0]
            value = struct.unpack("<i", uc.mem_read(field, 4))[0] + delta
            uc.mem_write(field, struct.pack("<i", max(value, 0)))
            log["charges"].append(delta)
            _stub(uc, 4)
        elif address == 0x46AD80:
            base = uc.reg_read(UC_X86_REG_ECX)
            index, delta = _arg(uc, 0), _arg(uc, 1)
            current = struct.unpack("<I", uc.mem_read(base + 4 * index, 4))[0]
            uc.mem_write(base + 4 * index, struct.pack("<I", _native_writer(current, delta)))
            log["writes"].append(index)
            _stub(uc, 8)

    for address in (0x41FE70, 0x466040, show_dialog, show_message, 0x41E300, 0x46AD80):
        mu.hook_add(UC_HOOK_CODE, hook, begin=address, end=address)
    esp = STACK_TOP - 0x200
    mu.mem_write(esp, struct.pack("<I", RETURN))
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.reg_write(UC_X86_REG_ECX, VV4_OBJ)
    mu.emu_start(VV4.PAYLOAD_VA + 0x500, RETURN, count=2_000_000)
    log["esp"] = mu.reg_read(UC_X86_REG_ESP) - esp
    log["balance"] = struct.unpack("<I", mu.mem_read(VV4_BALANCE, 4))[0]
    log["skills"] = list(struct.unpack("<5I", mu.mem_read(VV4_REC + 0x1C5C, 20)))
    log["age"] = struct.unpack("<i", mu.mem_read(VV4_REC + 0x1B8C, 4))[0]
    log["likes"] = list(struct.unpack("<3i", mu.mem_read(VV4_REC + 0x1E60, 12)))
    return log


class VV4DetailsMasteryPayload(unittest.TestCase):
    def test_valid_skills_are_mastered_for_the_full_price(self) -> None:
        log = _run_vv4_details_mastery([_bits(10.0), _bits(0.5), F100, 0, 0x80000000])
        self.assertEqual(log["charges"], [-100_000])
        self.assertEqual(log["balance"], 50_000)
        self.assertEqual(log["skills"], [F100] * 5)
        self.assertEqual(log["messages"], ["Purchased."])
        self.assertEqual(log["esp"], 4)

    def test_a_failed_post_check_refunds_and_says_so(self) -> None:
        # The companion refuses these before the payload runs; driven straight
        # into the payload they reach the post-check failure path.
        log = _run_vv4_details_mastery([_bits(10.0), NAN, F100, F100, F100])
        self.assertEqual(log["charges"], [-100_000], "charged once, through 0x41E300")
        self.assertEqual(log["balance"], 150_000, "the exact charge is refunded")
        self.assertEqual(log["messages"], ["Mastery not verified."])
        self.assertNotIn("Not enough tech points.", log["messages"])
        self.assertEqual(log["esp"], 4)


class VV4DetailsRefuseDeadOrGhost(unittest.TestCase):
    """A corpse stays active and selected until stock 0x466450 clears it 240
    time units after death, so the Details rows (Grant Youth 0, Grant Full
    Mastery 1, Grant Running 2, Set Age to 18 3) must refuse a dead
    (health <= 0) or ghost (+0x1CC7) villager before any charge."""

    SKILLS = [_bits(10.0), _bits(20.0), _bits(30.0), _bits(40.0), _bits(50.0)]

    def _refused(self, **record) -> None:
        for row in (0, 1, 2, 3):
            with self.subTest(row=row, **record):
                log = _run_vv4_details_mastery(self.SKILLS, row=row, **record)
                self.assertEqual(log["charges"], [], "nothing is charged")
                self.assertEqual(log["balance"], 150_000)
                self.assertEqual(log["writes"], [])
                self.assertEqual(log["skills"], self.SKILLS)
                self.assertEqual(log["age"], 400)
                self.assertEqual(log["likes"], [-1, -1, -1])
                self.assertEqual(log["messages"], ["Not living."])
                self.assertEqual(log["esp"], 4)

    def test_dead_villager_is_refused(self) -> None:
        self._refused(health=0)
        self._refused(health=-5)

    def test_ghost_is_refused(self) -> None:
        self._refused(ghost=1)

    def test_living_villager_is_served(self) -> None:
        for row, check in ((0, lambda log: log["age"] == 100),
                           (3, lambda log: log["age"] == 360)):
            with self.subTest(row=row):
                log = _run_vv4_details_mastery(self.SKILLS, row=row)
                self.assertEqual(len(log["charges"]), 1)
                self.assertTrue(check(log))
                self.assertEqual(log["messages"], ["Purchased."])

    def test_not_living_key_is_expanded_by_the_companion(self) -> None:
        src = VV4_C.read_text(encoding="utf-8", errors="replace")
        self.assertIn('lstrcmpA(text, "Not living.") == 0', src)
        self.assertIn('"No valid living villager is selected. "', src)
        dll = (ROOT / "assets" / "origins" / "VVFP VV4 Origins Icons.dll").read_bytes()
        self.assertIn(b"No valid living villager is selected. No tech points have been deducted.", dll)


# ---------------------------------------------------------- VV4 companion DLL

def _c_body(src: str, signature: str) -> str:
    start = src.index(signature)
    opening = src.index("{", start)
    depth = 0
    for i in range(opening, len(src)):
        depth += {"{": 1, "}": -1}.get(src[i], 0)
        if depth == 0:
            return src[opening:i + 1]
    raise AssertionError(signature)


def _c_predicate(bits: int) -> bool:
    """vv4_skills_invalid's per-skill test, mirrored from the source."""
    return bits > 0x42C80000 and bits != 0x80000000


class VV4CompanionRefusesInvalidSkills(unittest.TestCase):
    def setUp(self) -> None:
        self.src = VV4_C.read_text(encoding="utf-8", errors="replace")

    def test_the_predicate_matches_vv5(self) -> None:
        helper = _c_body(self.src, "static int vv4_skills_invalid(")
        self.assertIn("for (s = 0; s < 5; ++s)", helper)
        self.assertIn("rec + 0x1C5C + 4 * s", helper)
        self.assertIn("bits > 0x42C80000u && bits != 0x80000000u", helper)
        cases = {
            0: False, 0x80000000: False, _bits(55.0): False, F100: False,
            _bits(100.00001): True, _bits(-1.0): True, NAN: True, 0xFFC00000: True,
            0x7F800000: True, 0xFF800000: True, _bits(1e30): True,
        }
        for bits, invalid in cases.items():
            with self.subTest(bits=hex(bits)):
                self.assertEqual(_c_predicate(bits), invalid)
        # Every value the predicate accepts is mastered exactly by the writer.
        for bits in (0, 0x80000000, 1, _bits(0.1), _bits(33.3), _bits(99.99999), F100 - 1):
            self.assertEqual(_native_writer(bits, _bits(_f32(F100) - _f32(bits))), F100, hex(bits))
        # And every value it refuses is not.
        for bits in (NAN, 0x7F800000, 0xFF800000, _bits(1e30), _bits(-1e30)):
            self.assertNotEqual(_native_writer(bits, _bits(_f32(F100) - _f32(bits))), F100, hex(bits))

    def test_the_wording_is_vv5s(self) -> None:
        start = self.src.index("#define VV4_SKILL_INVALID_TEXT")
        define = "\n".join(self.src[start:].splitlines()[:3])
        text = "".join(re.findall(r'"([^"]*)"', define))
        self.assertEqual(text, INVALID_TEXT)

    def test_tech_dry_run_refuses_before_the_confirm(self) -> None:
        scan = _c_body(self.src, "static void vv_scan_mastery(void)")
        self.assertIn("vw_invalid = 0", scan)
        self.assertIn("if (vv4_skills_invalid(r)) { ++vw_invalid; continue; }", scan)
        self.assertLess(scan.index("vv_eligible(r)"), scan.index("vv4_skills_invalid(r)"))
        confirm = _c_body(self.src, "int __stdcall ConfirmOriginsVillageWide(int command)")
        mastery = confirm[confirm.index("if (command == 7)"):confirm.index("if (command == 8)")]
        refuse = mastery.index("if (vw_invalid)")
        self.assertLess(mastery.index("vv_scan_mastery();"), refuse)
        self.assertLess(refuse, mastery.index("Do you want to buy Grant Full Mastery"))
        self.assertIn("VV4_SKILL_INVALID_TEXT", mastery[refuse:refuse + 200])
        self.assertIn("return 0;", mastery[refuse:refuse + 250])

    def test_details_click_is_refused_before_the_payload_charges(self) -> None:
        handler = _c_body(self.src, "static INT_PTR CALLBACK upgrade_dialog(")
        check = handler.index("vv4_skills_invalid(detail_rec)")
        self.assertIn("*(const unsigned char **)(UINT_PTR)0x728D40u", handler)
        self.assertIn("row == 1 && detail_rec != NULL", handler[check - 120:check])
        self.assertIn("return TRUE; /* Stay in the menu; nothing was purchased. */",
                      handler[check:check + 500])
        self.assertLess(check, handler.index("g_last_row = row;"), "before the payload dispatch")

    def test_details_record_slot_is_the_payloads(self) -> None:
        self.assertEqual(VV4.VV4_DETAIL_RECORD_VA, 0x728D40)

    def test_retained_key_is_expanded(self) -> None:
        body = _c_body(self.src, "ShowOriginsUpgradeMessage(")
        self.assertIn('lstrcmpA(text, "Mastery not verified.") == 0', body)
        self.assertIn("No tech points have been deducted.", body)

    def test_built_companion_carries_the_new_text(self) -> None:
        dll = (ROOT / "assets" / "origins" / "VVFP VV4 Origins Icons.dll").read_bytes()
        self.assertIn(INVALID_TEXT.replace("\\r\\n", "\r\n").encode("ascii"), dll)
        self.assertIn(b"Mastery not verified.", dll)


if __name__ == "__main__":
    unittest.main()
