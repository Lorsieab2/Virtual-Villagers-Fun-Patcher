"""Grant Full Mastery repairs a corrupted skill instead of refusing (v1.35.70).

The Tree of Life (VV4) and New Believers (VV5) raise each skill float to 100.0
through the stock writer (VV4 0x46AD80, VV5 0x475730), which stores
``current + delta`` and clamps an ordered result to 0..100. A NaN therefore
stays NaN and can never be mastered. Since v1.35.70 ("Can you reset
obviously-corrupted skill values?") both games repair such a value on the
villager(s) the upgrade acts on -- NaN / +-infinity / negative -> 0, above 100
-> 100, -0.0 left alone -- with a plain store, after the player confirms, and
then master as before:

* VV5 Details "Grant Full Mastery" (build_mastery): the snapshot keeps both the
  raw and the repaired skills; a villager full once repaired is repaired free
  with the no-change result; otherwise the repair is stored after the confirm
  and balance re-check, the writer masters the rest, and the result carries
  the count (amount_a) for the "Reset N corrupted skill values." line.
* VV5 Tech "Grant Full Mastery to All" (build_mastery_all): the repair runs
  inside the post-confirm walk; the count reaches the result as amount_b >> 16
  on success, amount_a otherwise. RESULT_INVALID_SKILL (9) is gone.
* VV4 Tech and Details: the companion repairs (vv4_repair_skills) and reports;
  the payload's post-check refund stays as a last guard.
The Tech rows and the other skill upgrades are also emulated end to end in
test_reset_corrupted_skills_vv4_vv5.py.
"""
from __future__ import annotations

import importlib.util
import math
import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_EIP, UC_X86_REG_ESP,
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
INVALID_TEXT = "Full Mastery cannot be applied because a skill is NaN"


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
    f32(current + delta); an ordered result above 100.0 is clamped to 100.0,
    one below 0 to 0; NaN is stored as computed."""
    total = _f32(current) + _f32(delta)
    if math.isnan(total):
        return NAN
    total = _bits(total)
    if _f32(total) > 100.0:
        return F100
    return 0 if _f32(total) < 0.0 else total


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


def _vv5_machine(villagers: list[dict], balance: int):
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
    mu.mem_write(VV5_BALANCE, struct.pack("<I", balance))
    for i, v in enumerate(villagers):
        base = VV5_RECORDS + i * VV5.STRIDE
        mu.mem_write(base + 0x1CD4, bytes([v.get("active", 1)]))
        mu.mem_write(base + 0x1CE1, bytes([v.get("heathen", 0)]))
        mu.mem_write(base + 0x1CEC, bytes([0]))
        mu.mem_write(base + 0x1C40, struct.pack("<i", v.get("health", 50)))
        mu.mem_write(base + 0x1C5C, struct.pack("<6I", *v["skills"]))
    return mu, page_va


def _run_vv5(routine: str, villagers: list[dict], *, answer: int = 1,
             balance: int = 2_000_000) -> dict:
    """Run the page's mastery_all (Tech row 7) or mastery (Details row 1, the
    selected villager is record 0) with the companion stubbed."""
    mu, page_va = _vv5_machine(villagers, balance)
    log = {"confirm": 0, "writes": [], "charges": [], "status": None}
    confirm = page_va + VV5.OFF["confirm"]
    status = page_va + VV5.OFF["status"]
    current = page_va + VV5.OFF["resolve_current"]
    by_index = page_va + VV5.OFF["resolve_index"]
    eligible = page_va + VV5.OFF["eligible"]

    def hook(uc, address, size, _):
        if address == confirm:
            log["confirm"] += 1
            _stub(uc, 12, answer)
        elif address == status:
            log["status"] = tuple(_arg(uc, i) for i in range(4))
            _stub(uc, 16, 0)
        elif address == current:
            uc.reg_write(UC_X86_REG_EDX, 0)
            _stub(uc, 0, VV5_RECORDS)
        elif address == by_index:
            _stub(uc, 4, VV5_RECORDS)
        elif address == eligible:
            _stub(uc, 4, 1)
        elif address == 0x475730:
            skills = uc.reg_read(UC_X86_REG_ECX)
            index, delta = _arg(uc, 0), _arg(uc, 1)
            now = struct.unpack("<I", uc.mem_read(skills + 4 * index, 4))[0]
            uc.mem_write(skills + 4 * index, struct.pack("<I", _native_writer(now, delta)))
            log["writes"].append(index)
            _stub(uc, 8)
        elif address == 0x4237B0:
            field = uc.reg_read(UC_X86_REG_ECX)
            delta = struct.unpack("<i", struct.pack("<I", _arg(uc, 0)))[0]
            value = struct.unpack("<i", uc.mem_read(field, 4))[0] + delta
            uc.mem_write(field, struct.pack("<i", max(value, 0)))
            log["charges"].append(delta)
            _stub(uc, 4)

    stubs = [confirm, status, 0x475730, 0x4237B0]
    if routine == "mastery":
        stubs += [current, by_index, eligible]
    for address in stubs:
        mu.hook_add(UC_HOOK_CODE, hook, begin=address, end=address)
    esp = STACK_TOP - 0x200
    mu.mem_write(esp, struct.pack("<I", RETURN))
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.emu_start(page_va + VV5.OFF[routine], RETURN, count=2_000_000)
    log["esp"] = mu.reg_read(UC_X86_REG_ESP) - esp
    log["balance"] = struct.unpack("<I", mu.mem_read(VV5_BALANCE, 4))[0]
    log["skills"] = [
        list(struct.unpack("<6I", mu.mem_read(VV5_RECORDS + i * VV5.STRIDE + 0x1C5C, 24)))
        for i in range(len(villagers))
    ]
    return log


def _run_vv5_mastery_all(villagers: list[dict], **kw) -> dict:
    return _run_vv5("mastery_all", villagers, **kw)


GOOD = [_bits(10.0), _bits(55.5), F100, 0, _bits(99.0), _bits(1.0)]
NEG_ZERO = 0x80000000


class VV5TechMasteryRepairsCorruptedSkills(unittest.TestCase):
    def _repaired(self, bad: int, fixed: int) -> None:
        villagers = [{"skills": GOOD}, {"skills": [_bits(20.0), bad, F100, F100, F100, F100]}]
        log = _run_vv5_mastery_all(villagers)
        self.assertEqual(log["confirm"], 1)
        # Both granted, none already mastered, one value reset (<< 16).
        self.assertEqual(log["status"], (21, 0, 2, 1 << 16))
        self.assertEqual(log["charges"], [-1_000_000])
        self.assertEqual(log["skills"], [[F100] * 6, [F100] * 6])
        # Repaired to `fixed` by a plain store, then the writer masters only
        # what is still below 100.
        expected = [0, 1] if fixed != F100 else [0]
        self.assertEqual(log["writes"], [0, 1, 3, 4, 5] + expected)
        self.assertEqual(log["esp"], 4)

    def test_nan_and_infinities_reset_to_zero_then_master(self) -> None:
        for bad in (NAN, 0xFFC00000, 0x7F800000, 0xFF800000):
            with self.subTest(bad=hex(bad)):
                self._repaired(bad, 0)

    def test_negative_resets_to_zero(self) -> None:
        self._repaired(_bits(-1.0), 0)
        self._repaired(0x80000001, 0)

    def test_above_one_hundred_resets_to_one_hundred(self) -> None:
        self._repaired(_bits(150.0), F100)
        self._repaired(_bits(100.00001), F100)

    def test_a_repair_alone_is_not_a_grant_or_a_charge(self) -> None:
        log = _run_vv5_mastery_all([{"skills": [F100, _bits(1e30), F100, F100, F100, F100]}])
        self.assertEqual(log["status"], (21, 1, 1, 0), "no change; one value reset")
        self.assertEqual(log["charges"], [])
        self.assertEqual(log["writes"], [])
        self.assertEqual(log["skills"], [[F100] * 6])

    def test_cancel_and_insufficient_repair_nothing(self) -> None:
        bad = [NAN] * 6
        for kw, status in (({"answer": 0}, (21, 4, 0, 0)), ({"balance": 999_999}, (21, 3, 0, 0))):
            with self.subTest(**kw):
                log = _run_vv5_mastery_all([{"skills": bad}], **kw)
                self.assertEqual(log["status"], status)
                self.assertEqual(log["skills"], [bad])
                self.assertEqual(log["charges"], [])

    def test_ineligible_villagers_are_not_touched(self) -> None:
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
        villagers = [{"skills": GOOD}, {"skills": [F100] * 6}, {"skills": [NEG_ZERO] + [F100] * 5}]
        log = _run_vv5_mastery_all(villagers)
        self.assertEqual(log["confirm"], 1)
        self.assertEqual(log["status"], (21, 0, 2, 1), "two granted, one already mastered, none reset")
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

    def test_the_refusal_is_gone(self) -> None:
        src = VV5_C.read_text(encoding="utf-8")
        self.assertNotIn(INVALID_TEXT, src)
        self.assertNotIn("RESULT_INVALID_SKILL = 9", src)
        page, _ = VV5.build_page(0x7C9000)
        for routine in ("mastery", "mastery_all"):
            code = bytes(page[VV5.OFF[routine]:VV5.OFF[routine] + VV5.SIZES[routine]])
            # push 9 (the old status) never reaches the status helper.
            self.assertNotIn(bytes.fromhex("6A09"), code, routine)


class VV5DetailsMasteryRepairsCorruptedSkills(unittest.TestCase):
    """build_mastery, the selected Believer (record 0)."""

    def test_corrupted_values_are_repaired_after_the_confirm(self) -> None:
        skills = [_bits(10.0), NAN, F100, F100, F100, _bits(-5.0)]
        log = _run_vv5("mastery", [{"skills": skills}])
        self.assertEqual(log["confirm"], 1)
        self.assertEqual(log["status"], (1, 0, 2, 0), "success, two values reset")
        self.assertEqual(log["writes"], [0, 1, 5])
        self.assertEqual(log["charges"], [-100_000])
        self.assertEqual(log["skills"], [[F100] * 6])
        self.assertEqual(log["esp"], 4)

    def test_full_once_repaired_is_free_and_skips_the_confirm(self) -> None:
        log = _run_vv5("mastery", [{"skills": [F100, F100, _bits(150.0), F100, F100, F100]}])
        self.assertEqual(log["confirm"], 0)
        self.assertEqual(log["status"], (1, 1, 1, 0), "no change, one value reset")
        self.assertEqual(log["writes"], [])
        self.assertEqual(log["charges"], [])
        self.assertEqual(log["skills"], [[F100] * 6])

    def test_cancel_and_insufficient_repair_nothing(self) -> None:
        skills = [_bits(10.0), NAN, F100, F100, F100, F100]
        for kw, status in (({"answer": 0}, (1, 4, 0, 0)), ({"balance": 99_999}, (1, 3, 0, 0))):
            with self.subTest(**kw):
                log = _run_vv5("mastery", [{"skills": skills}], **kw)
                self.assertEqual(log["status"], status)
                self.assertEqual(log["skills"], [skills])
                self.assertEqual(log["charges"], [])

    def test_valid_values_are_untouched_until_mastered(self) -> None:
        skills = [F100] * 5 + [NEG_ZERO]
        log = _run_vv5("mastery", [{"skills": skills}])
        self.assertEqual(log["status"], (1, 0, 0, 0), "no reset for -0.0")
        self.assertEqual(log["writes"], [5])
        self.assertEqual(log["skills"], [[F100] * 6])
        log = _run_vv5("mastery", [{"skills": [F100] * 6}])
        self.assertEqual(log["status"], (1, 1, 0, 0))
        self.assertEqual(log["confirm"], 0)


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
        # The companion repairs these before the payload runs; driven straight
        # into the payload they reach the post-check failure path, the last
        # guard.
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


def _c_repair(bits: int) -> int:
    """vv4_skill_repair_bits, mirrored from the source."""
    if bits & 0x7FFFFFFF >= 0x7F800000:
        return 0
    if bits & 0x80000000 and bits != 0x80000000:
        return 0
    if bits > 0x42C80000 and not bits & 0x80000000:
        return F100
    return bits


class VV4CompanionRepairsCorruptedSkills(unittest.TestCase):
    def setUp(self) -> None:
        self.src = VV4_C.read_text(encoding="utf-8", errors="replace")

    def test_the_rule_matches_vv5_and_the_writer_masters_every_repair(self) -> None:
        helper = _c_body(self.src, "static int vv4_skill_repair_bits(")
        self.assertIn("(bits & 0x7FFFFFFFu) >= 0x7F800000u", helper)
        self.assertIn("bits != 0x80000000u", helper)
        self.assertIn("*fixed = VV4_SKILL_MAX_BITS;", helper)
        self.assertIn("#define VV4_SKILL_MAX_BITS 0x42C80000u", self.src)
        cases = {
            0: 0, 0x80000000: 0x80000000, _bits(55.0): _bits(55.0), F100: F100,
            _bits(100.00001): F100, _bits(1e30): F100, _bits(-1.0): 0, NAN: 0,
            0xFFC00000: 0, 0x7F800000: 0, 0xFF800000: 0,
        }
        for bits, fixed in cases.items():
            with self.subTest(bits=hex(bits)):
                self.assertEqual(_c_repair(bits), fixed)
                self.assertEqual(
                    _native_writer(fixed, _bits(_f32(F100) - _f32(fixed))), F100)

    def test_the_refusal_is_gone(self) -> None:
        self.assertNotIn("VV4_SKILL_INVALID_TEXT", self.src)
        self.assertNotIn("vv4_skills_invalid", self.src)
        self.assertNotIn(INVALID_TEXT, self.src)
        dll = (ROOT / "assets" / "origins" / "VVFP VV4 Origins Icons.dll").read_bytes()
        self.assertNotIn(INVALID_TEXT.encode("ascii"), dll)
        self.assertIn(b"Reset %d corrupted skill %s.", dll)

    def test_repairs_are_plain_stores(self) -> None:
        body = _c_body(self.src, "static int vv4_repair_skills(")
        self.assertIn("*slot = fixed;", body)
        self.assertNotIn("0x46AD80", body)

    def test_tech_repairs_only_after_ok_or_when_nothing_is_sold(self) -> None:
        confirm = _c_body(self.src, "int __stdcall ConfirmOriginsVillageWide(int command)")
        mastery = confirm[confirm.index("if (command == 7)"):confirm.index("if (command == 8)")]
        self.assertTrue(mastery.lstrip("if (command == 7) {\n ").startswith("vv_scan_mastery(0);"))
        ok = mastery.index("!= IDOK)")
        self.assertIn("return 0;", mastery[ok:ok + 40])
        self.assertLess(ok, mastery.rindex("vv_scan_mastery(1);"))
        self.assertIn("g_reset_note = vw_repairs;", mastery[ok:])

    def test_details_click_repairs_after_the_confirm(self) -> None:
        handler = _c_body(self.src, "static INT_PTR CALLBACK upgrade_dialog(")
        check = handler.index("vv4_repair_skills(detail_rec, 0) > 0")
        self.assertIn("row == 1 && vv4_detail_living(detail_rec)", handler[check - 120:check])
        confirm = handler.index("MB_OKCANCEL | MB_ICONQUESTION")
        store = handler.index("g_reset_note = vv4_repair_skills(repair_rec, 1);")
        self.assertLess(confirm, store)
        self.assertLess(store, handler.index("g_last_row = row;"), "before the payload dispatch")
        # Full once repaired: repaired free, before any confirm, and the
        # already-mastered bit is set so a second click cannot charge.
        free = handler.index("vv4_skills_full_after_repair(detail_rec)")
        self.assertLess(free, confirm)
        self.assertIn("g_villager_mask |= (1 << 1);", handler[free:free + 600])

    def test_payload_results_consume_the_note(self) -> None:
        body = _c_body(self.src, "ShowOriginsUpgradeMessage(")
        self.assertIn("if (g_reset_note > 0)", body)
        self.assertIn("g_reset_note = 0;", body)
        menu = _c_body(self.src, "static int show_upgrade_menu(")
        self.assertIn("g_reset_note = 0;", menu)

    def test_details_record_slot_is_the_payloads(self) -> None:
        self.assertEqual(VV4.VV4_DETAIL_RECORD_VA, 0x728D40)

    def test_retained_key_is_expanded(self) -> None:
        body = _c_body(self.src, "ShowOriginsUpgradeMessage(")
        self.assertIn('lstrcmpA(text, "Mastery not verified.") == 0', body)
        self.assertIn("No tech points have been deducted.", body)
        dll = (ROOT / "assets" / "origins" / "VVFP VV4 Origins Icons.dll").read_bytes()
        self.assertIn(b"Mastery not verified.", dll)


if __name__ == "__main__":
    unittest.main()
