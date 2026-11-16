"""A New Home: "Fix Vanilla Bugs" (vv1_fix_vanilla_bugs).

One row holds every base-game bug fix the owner has approved for A New Home;
each fix is its own exact-byte patch in the row and has its own tests here.
A later approved fix is added as another patch in the same row and another
test class below.

1. A Mysterious Vial (blue liquid), "Drink the liquid", toddler result.  The
   two-choice resolve 0x419380, case 0x419C3F: rand(100) < 50 turns the
   drinker back into a toddler -- age +0x348 and +0x34C := 80, pregnancy
   +0x358 := 0 (0x419CC1) -- but leaves the litter size +0x35C alone.  The
   conception routine writes +0x35C only for twins (0x43BC4E) and triplets
   (0x43BC8C), never for one baby, and delivery reads it (0x42F011), so a
   villager who drank while carrying twins or triplets keeps 2 or 3 and her
   next single pregnancy brings twins or triplets.  Seen live (v1.35.49 test
   build without the fix, 2026-10-02): Pupa, set pregnant with litter 2,
   drank and became a toddler: +0x358 1028 -> 0, +0x35C stayed 2.

   The record tail 0x419CC1..0x419CEB is re-encoded with the drinker's record
   computed once, which leaves room to clear +0x35C beside +0x358 -- as the
   game's own delivery (0x42F0B2/0x42F0C7) and villager creation
   (0x43C71C/0x43C722, 0x43CAB8/0x43CABE) do.  Everything else the tail
   leaves (fields, EAX/ECX/EDX, the popped registers) is the base game's.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs
from capstone.x86 import X86_OP_MEM
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX,
    UC_X86_REG_EDI, UC_X86_REG_EDX, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    load_builds,
    load_fun_patches,
    load_public_fun_patches,
    render_patched_bytes,
)

FEATURE_ID = "vv1_fix_vanilla_bugs"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
MODES = ("stock", "collection_progression", "immediate_fixed")

VIAL_OFFSET = 0x19CC1
VIAL_STOCK = bytes.fromhex(
    "899C02580300008B8E985000008B96A850000069C9D80300005F8D04118B88480300005D5E89884C030000"
)
VIAL_PATCHED = bytes.fromhex(
    "8D040289985803000089985C0300008B96A85000008B88480300005F5D5E89884C0300000F1F8000000000"
)
# Every default name can be chosen (tests/test_every_default_name_can_be_chosen.py):
# the creator's and the twin's name rolls cover the whole list.
NAME_FIXES = (
    (0x3C645, bytes.fromhex("6A64"), bytes.fromhex("6A65")),
    (0x3C657, bytes.fromhex("40"), bytes.fromhex("90")),
    (0x3C674, bytes.fromhex("40"), bytes.fromhex("90")),
    (0x3C9FB, bytes.fromhex("83F862"), bytes.fromhex("83F864")),
    (0x3CA06, bytes.fromhex("6A64"), bytes.fromhex("6A65")),
    (0x3CA10, bytes.fromhex("40"), bytes.fromhex("90")),
)
PERCENT_FIXES = (  # '%' in a name never a format; text boxes refuse it (#566)
    (0x4A66A, bytes.fromhex("E8CE0B0000"), bytes.fromhex("E8F26BFBFF")),  # through the name box fill record
    (0x18760, bytes.fromhex("E8D82A0300"), bytes.fromhex("E81B6C0300")),
    (0x1FAA1, bytes.fromhex("E897B70200"), bytes.fromhex("E8DAF80200")),
    (0x27892, bytes.fromhex("E8A6390200"), bytes.fromhex("E8E97A0200")),
    (0x2A952, bytes.fromhex("E8E6080200"), bytes.fromhex("E8294A0200")),
    (0x48FF1, bytes.fromhex("E847220000"), bytes.fromhex("E88A630000")),
    (0x0BEB7, bytes.fromhex("83FA1F7E0881FAFF0000007E1784DB740A"), bytes.fromhex("83FA25744B8D72E081FEDF000000761490")),
)

# The Details screen's Likes/Dislikes (tests/test_vanilla_likes_panel.py).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_vanilla_likes_panel import likes_fixes  # noqa: E402

LIKES_FIXES = likes_fixes("vv1")
from test_details_name_identity import name_identity_fixes  # noqa: E402
# The Details screen's name box is written back only to the villager it shows
# (tests/test_details_name_box.py).
NAME_BOX_FIXES = (
    (0x4A6F2, bytes.fromhex("90" * 14), bytes.fromhex("807E24007505E9E4DAFBFFC20800")),
    (0x4A748, bytes.fromhex("E82314FCFF"), bytes.fromhex("E8A5FFFFFF")),
    (0x4A7A4, bytes.fromhex("E8C713FCFF"), bytes.fromhex("E849FFFFFF")),
    (0x4A859, bytes.fromhex("E81213FCFF"), bytes.fromhex("E894FEFFFF")),
)
FIXES = ((VIAL_OFFSET, VIAL_STOCK, VIAL_PATCHED),) + NAME_FIXES + PERCENT_FIXES + LIKES_FIXES + NAME_BOX_FIXES
# ...and to the villager it was filled for (tests/test_details_name_identity.py).
FIXES = FIXES + name_identity_fixes("vv1")
# Healers learn Healing in catch-up (tests/test_catch_up_healing_practice.py).
from test_catch_up_healing_practice import healing_practice_fixes  # noqa: E402

FIXES = FIXES + healing_practice_fixes("vv1")
# Liking work works as in VV2-VV5 (LikingWorkTests below).
LIKE_WORK_FIXES = (
    (0x39AF8, bytes.fromhex("5E5D33C05BC20800"), bytes.fromhex("E994B90100909090")),
    (0x55491, b"\xCC" * 15, bytes.fromhex("6A2AFF7424148BCBE8721EFEFFEB12")),
    (0x554B2, b"\xCC" * 14, bytes.fromhex("84C00F854646FEFF57E96246FEFF")),
)
# ...and keeping a job the player assigned follows The Lost Children's rule (KeepAssignedJobTests below).
KEEP_JOB_CAVE = bytes.fromhex(
    "506A2A558BCEE80505FEFF84C0753E6A64E8FAC0FAFF83C40483F8147C396A64E8EBC0FAFF83C40483F8287D208B8610E00300"
    "81B8ECA20000A00F00007D186A2A558BCEE89704FEFF84C0750A588BCEFF2485A880440058E99E11FFFF")
KEEP_JOB_FIXES = (
    (0x47CFF, bytes.fromhex("FF2485A8804400"), bytes.fromhex("E9FCF000009090")),
    (0x56E00, b"\0" * len(KEEP_JOB_CAVE), KEEP_JOB_CAVE),
)
FIXES = FIXES + LIKE_WORK_FIXES + KEEP_JOB_FIXES

# Game addresses and fields.
BLUE_VIAL = 0x419C3F           # resolve 0x419380's case for the blue vial
RAND = 0x402F10
STUBS = {
    0x433970: 4,   # text table lookup
    0x44B23D: 0,   # sprintf (cdecl)
    0x4184A0: 8,   # show the result text
    0x443FA0: 8,   # queue the dance (the other result)
}
STRIDE = 0x3D8
AGE, AGE2, PREGNANT, LITTER, HEALTH = 0x348, 0x34C, 0x358, 0x35C, 0x344

STACK = 0x70000000
THIS = 0x20000000
POOL = 0x30000000
RETURN = 0x0BAD0000
FRAME = 0x2710


def _vv1():
    return next(build for build in load_builds() if build.id == "vv1")


def _render(mode: str, ids) -> bytes:
    rendered, _ = render_patched_bytes(STOCK, _vv1(), mode, list(ids))
    return bytes(rendered)


def _other_public_vv1_ids() -> list[str]:
    return [p.id for p in [alt for alt in load_public_fun_patches() if alt.id not in __import__("vv_fun_patcher").ALTERNATIVE_FUN_PATCH_IDS] if p.game_id == "vv1" and p.id != FEATURE_ID]


def _changed_bytes(before: bytes, after: bytes) -> list[int]:
    field = pefile.PE(data=after, fast_load=True).OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    return [
        i for i in range(min(len(before), len(after)))
        if before[i] != after[i] and not field <= i < field + 4
    ]


def _allowed() -> set[int]:
    allowed = set()
    for offset, before, _ in FIXES:
        allowed.update(range(offset, offset + len(before)))
    return allowed


def _drink(exe: bytes, roll: int, drinker: int, pregnant: int, litter: int):
    """Run the blue vial's "Drink the liquid" (choice 1) inside a frame laid
    out as the resolve's own; return the drinker's record and the registers
    the resolve returns with."""
    pe = pefile.PE(data=exe)
    image = pe.get_memory_mapped_image()
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(0x400000, (len(image) + 0xFFFF) & ~0xFFFF)
    mu.mem_write(0x400000, image)
    mu.mem_map(STACK - 0x10000, 0x20000)
    mu.mem_map(THIS, 0x10000)
    mu.mem_map(POOL, 0x100000)
    mu.mem_map(RETURN, 0x1000)
    mu.mem_write(THIS + 0x509C, struct.pack("<i", 1))          # choice: drink
    mu.mem_write(THIS + 0x5098, struct.pack("<i", drinker))
    mu.mem_write(THIS + 0x50A8, struct.pack("<I", POOL))
    rec = POOL + drinker * STRIDE
    for field, value in ((AGE, 1028), (AGE2, 1028), (PREGNANT, pregnant), (LITTER, litter), (HEALTH, 99)):
        mu.mem_write(rec + field, struct.pack("<i", value))
    calls = []

    def on_code(uc, address, size, user_data):
        pop = None
        value = 0
        if address == RAND:
            pop, value = 0, roll
        elif address in STUBS:
            pop = STUBS[address]
        if pop is None:
            return
        calls.append(address)
        esp = uc.reg_read(UC_X86_REG_ESP)
        ret = struct.unpack("<I", uc.mem_read(esp, 4))[0]
        uc.reg_write(UC_X86_REG_EAX, value)
        uc.reg_write(UC_X86_REG_ESP, esp + 4 + pop)
        uc.reg_write(UC_X86_REG_EIP, ret)

    mu.hook_add(UC_HOOK_CODE, on_code)
    top = STACK - 4
    mu.mem_write(top, struct.pack("<I", RETURN))
    esp = top - FRAME - 16
    # pushed by the prologue: ebx, esi, then ebp, edi
    mu.mem_write(esp, struct.pack("<IIII", 0x5EED0004, 0x5EED0003, 0x5EED0002, 0x5EED0001))
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.reg_write(UC_X86_REG_ESI, THIS)
    mu.reg_write(UC_X86_REG_EBX, 0)        # the resolve's zero register (0x419394)
    mu.emu_start(BLUE_VIAL, RETURN, count=100000)
    assert mu.reg_read(UC_X86_REG_ESP) == STACK
    assert tuple(mu.reg_read(r) for r in (UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_ESI, UC_X86_REG_EBX)) == (
        0x5EED0004, 0x5EED0003, 0x5EED0002, 0x5EED0001)
    record = bytes(mu.mem_read(rec, STRIDE))
    registers = tuple(mu.reg_read(r) for r in (UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX))
    pool = bytes(mu.mem_read(POOL, 0x100000))
    return record, registers, calls, pool


def _field(record: bytes, offset: int) -> int:
    return struct.unpack_from("<i", record, offset)[0]


class ManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stock = STOCK.read_bytes()
        cls.feature = next(p for p in load_fun_patches() if p.id == FEATURE_ID)

    def test_manifest_row(self) -> None:
        raw = self.feature.raw
        self.assertEqual(raw["game_id"], "vv1")
        self.assertEqual(raw["name"], "Fix Vanilla Bugs")
        self.assertIn(FEATURE_ID, {p.id for p in load_public_fun_patches()})
        self.assertNotIn("dependencies", raw)
        self.assertIn("**Needs no other patch.**", raw["description"])
        pinned = [(int(p["offset"], 16), bytes.fromhex(p["before"]), bytes.fromhex(p["after"])) for p in raw["patches"]]
        self.assertEqual(pinned, list(FIXES))

    def test_default_on(self) -> None:
        from vv_fun_patcher_gui import DEFAULT_OFF_FUN_PATCH_IDS, OWNERS_DEFAULT_OFF_FUN_PATCH_IDS

        self.assertNotIn(FEATURE_ID, DEFAULT_OFF_FUN_PATCH_IDS)
        self.assertNotIn(FEATURE_ID, OWNERS_DEFAULT_OFF_FUN_PATCH_IDS)

    def test_stock_bytes_and_offset(self) -> None:
        pe = pefile.PE(str(STOCK), fast_load=True)
        self.assertEqual(pe.get_offset_from_rva(0x419CC1 - 0x400000), VIAL_OFFSET)
        self.assertEqual(self.stock[VIAL_OFFSET:VIAL_OFFSET + len(VIAL_STOCK)], VIAL_STOCK)
        # the resolve keeps EBX zero for the whole switch
        self.assertEqual(self.stock[0x19394:0x19396], bytes.fromhex("33DB"))

    def test_the_litter_is_written_only_by_these_stock_sites(self) -> None:
        """Root cause, pinned: +0x35C is written by delivery, by the two
        villager creators and, for twins and triplets only, by conception;
        the vial result clears +0x358 without it."""
        pe = pefile.PE(str(STOCK))
        text = next(s for s in pe.sections if s.Name.startswith(b".text"))
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.detail = True
        md.skipdata = True
        writes = {PREGNANT: [], LITTER: []}
        for ins in md.disasm(text.get_data(), 0x400000 + text.VirtualAddress):
            try:
                ops = ins.operands
            except Exception:  # skipdata
                continue
            if ins.mnemonic == "mov" and ops and ops[0].type == X86_OP_MEM and ops[0].mem.disp in writes \
                    and ins.reg_name(ops[0].mem.base) != "esp":
                writes[ops[0].mem.disp].append(ins.address)
        self.assertEqual(writes[LITTER], [0x424326, 0x42F0C7, 0x43BC4E, 0x43BC8C, 0x43C722, 0x43CABE])
        self.assertEqual(writes[PREGNANT], [0x4195BE, 0x419CC1, 0x41C1E4, 0x42431C, 0x42F0B2, 0x43BBFA, 0x43C71C, 0x43CAB8])

    def test_nothing_else_branches_into_the_region(self) -> None:
        pe = pefile.PE(str(STOCK))
        text = next(s for s in pe.sections if s.Name.startswith(b".text"))
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.skipdata = True
        start, end = 0x419CC1, 0x419CC1 + len(VIAL_STOCK)
        incoming = []
        for ins in md.disasm(text.get_data(), 0x400000 + text.VirtualAddress):
            if not (ins.mnemonic.startswith("j") or ins.mnemonic == "call"):
                continue
            try:
                target = int(ins.op_str, 16)
            except ValueError:
                continue
            if start <= target < end and not start <= ins.address < end:
                incoming.append((hex(ins.address), hex(target)))
        self.assertEqual(incoming, [])

    def test_patched_region_decodes(self) -> None:
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        listing = [(i.address, i.mnemonic, i.op_str) for i in md.disasm(VIAL_PATCHED, 0x419CC1)]
        self.assertEqual(sum(i.size for i in md.disasm(VIAL_PATCHED, 0x419CC1)), len(VIAL_STOCK))
        self.assertEqual(
            listing,
            [
                (0x419CC1, "lea", "eax, [edx + eax]"),
                (0x419CC4, "mov", "dword ptr [eax + 0x358], ebx"),
                (0x419CCA, "mov", "dword ptr [eax + 0x35c], ebx"),
                (0x419CD0, "mov", "edx, dword ptr [esi + 0x50a8]"),
                (0x419CD6, "mov", "ecx, dword ptr [eax + 0x348]"),
                (0x419CDC, "pop", "edi"),
                (0x419CDD, "pop", "ebp"),
                (0x419CDE, "pop", "esi"),
                (0x419CDF, "mov", "dword ptr [eax + 0x34c], ecx"),
                (0x419CE5, "nop", "dword ptr [eax]"),
            ],
        )

    def test_render_alone_in_every_mode(self) -> None:
        allowed = _allowed()
        for mode in MODES:
            with self.subTest(mode=mode):
                without = _render(mode, [])
                rendered = _render(mode, [FEATURE_ID])
                for offset, before, after in FIXES:
                    self.assertEqual(without[offset:offset + len(before)], before)
                    self.assertEqual(rendered[offset:offset + len(after)], after)
                diff = _changed_bytes(without, rendered)
                self.assertTrue(diff)
                self.assertTrue(set(diff) <= allowed, [hex(i) for i in sorted(set(diff) - allowed)[:8]])
                self.assertEqual(len(rendered), len(without))

    def test_render_with_every_other_vv1_patch_in_every_mode(self) -> None:
        others = _other_public_vv1_ids()
        self.assertGreater(len(others), 10)
        allowed = _allowed()
        for mode in MODES:
            with self.subTest(mode=mode):
                without = _render(mode, others)
                rendered = _render(mode, others + [FEATURE_ID])
                for offset, before, after in FIXES:
                    self.assertEqual(without[offset:offset + len(before)], before)
                    self.assertEqual(rendered[offset:offset + len(after)], after)
                diff = _changed_bytes(without, rendered)
                self.assertTrue(set(diff) <= allowed, [hex(i) for i in sorted(set(diff) - allowed)[:8]])
                self.assertEqual(len(rendered), len(without))


class BlueVialLitterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        others = _other_public_vv1_ids()
        cls.builds = {}
        for mode in MODES:
            cls.builds[(mode, "stock")] = _render(mode, [])
            cls.builds[(mode, "patched")] = _render(mode, [FEATURE_ID])
            cls.builds[(mode, "patched_with_all")] = _render(mode, others + [FEATURE_ID])

    def test_emulated_toddler_result_ends_the_whole_pregnancy(self) -> None:
        for (mode, label), exe in self.builds.items():
            stock = self.builds[(mode, "stock")]
            for drinker in (0, 5, 200):
                for pregnant, litter in ((1028, 2), (900, 3), (0, 0), (0, 2)):
                    with self.subTest(mode=mode, build=label, drinker=drinker, litter=litter, pregnant=pregnant):
                        record, registers, calls, pool = _drink(exe, 10, drinker, pregnant, litter)
                        self.assertEqual((_field(record, AGE), _field(record, AGE2)), (80, 80))
                        self.assertEqual(_field(record, PREGNANT), 0)
                        self.assertEqual(_field(record, LITTER), litter if label == "stock" else 0)
                        s_record, s_registers, s_calls, s_pool = _drink(stock, 10, drinker, pregnant, litter)
                        # Everything else is the base game's: the record but
                        # the litter, the rest of the pool, the registers the
                        # resolve returns with and the calls it makes.
                        mask = lambda r: r[:LITTER] + r[LITTER + 4:]  # noqa: E731
                        self.assertEqual(mask(record), mask(s_record))
                        start = drinker * STRIDE
                        self.assertEqual(pool[:start] + pool[start + STRIDE:], s_pool[:start] + s_pool[start + STRIDE:])
                        self.assertEqual(registers, s_registers)
                        self.assertEqual(calls, s_calls)

    def test_emulated_dance_result_unchanged(self) -> None:
        for (mode, label), exe in self.builds.items():
            with self.subTest(mode=mode, build=label):
                record, _registers, calls, _pool = _drink(exe, 50, 7, 1028, 2)
                self.assertEqual((_field(record, AGE), _field(record, PREGNANT), _field(record, LITTER)), (1028, 1028, 2))
                self.assertIn(0x443FA0, calls)


# ---- Liking work ---------------------------------------------------------------------------------------------
# The owner (2026-11-16): "liking or disliking 'work' now works like VV2-VV5".  The Lost Children (0x449C6E..0x449C8B),
# The Secret City (0x45973A), The Tree of Life (0x461CCC) and New Believers (0x46A3CC) make the job chooser's blank
# roll -- rand(100) < 15 -> no job -- only for a villager who does not like work, and then refuse 70 in 100 for one
# who dislikes it.  A New Home's chooser 0x439AE0 makes the blank roll for everyone (0x439AEB..0x439AFD) and has the
# 70 in 100 dislike roll (0x439B05..0x439B28, word 42 = work).  Fix Vanilla Bugs asks the like test 0x437310
# (index, 42) first.  The chooser is shared by live play (0x448347, 0x448374) and catch-up (0x42E7DB), so this is
# every mode; it is RUN here from the chooser's entry, the game's rand(100) scripted, the like and dislike tests real.
CHOOSER, CHOSEN_ON = 0x439AE0, 0x439B2B      # CHOSEN_ON: past both gates, the skills are weighed
VILLAGE, INDEX, HALT = 0x20000000, 7, 0x0BAD0000
LIKES, DISLIKES, WORK = 0x398, 0x3A8, 42


def _choose(exe: bytes, *, blank: int, likes=(), dislikes=(), dislike_roll: int = 99):
    """Run the chooser for villager INDEX: the first rand(100) answers `blank`, the dislike roll `dislike_roll`.
    ("choice", None) when it goes on to weigh the skills (0x439B2B), else ("none", eax) when it returns, with
    its stack and saved registers checked."""
    image = pefile.PE(data=exe, fast_load=True).get_memory_mapped_image()
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(0x400000, (len(image) + 0xFFFF) & ~0xFFFF)
    mu.mem_write(0x400000, image)
    mu.mem_map(VILLAGE, 0x100000)
    mu.mem_map(STACK - 0x10000, 0x20000)
    mu.mem_map(HALT, 0x1000)
    rec = VILLAGE + INDEX * STRIDE
    for i in range(4):
        mu.mem_write(rec + LIKES + 4 * i, struct.pack("<i", likes[i] if i < len(likes) else -1))
        mu.mem_write(rec + DISLIKES + 4 * i, struct.pack("<i", dislikes[i] if i < len(dislikes) else -1))
    rolls = [blank, dislike_roll]

    def hook(uc, address, size, _):
        if address == RAND:
            esp = uc.reg_read(UC_X86_REG_ESP)
            ret, = struct.unpack("<I", uc.mem_read(esp, 4))
            uc.reg_write(UC_X86_REG_EAX, rolls.pop(0) if rolls else 99)
            uc.reg_write(UC_X86_REG_ECX, 0xC0C0C0C0)
            uc.reg_write(UC_X86_REG_EDX, 0xD0D0D0D0)
            uc.reg_write(UC_X86_REG_ESP, esp + 4)
            uc.reg_write(UC_X86_REG_EIP, ret)
        elif address in (CHOSEN_ON, HALT):
            uc.emu_stop()

    mu.hook_add(UC_HOOK_CODE, hook)
    esp = STACK - 0x100
    mu.mem_write(esp, struct.pack("<III", HALT, INDEX, 0))
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.reg_write(UC_X86_REG_ECX, VILLAGE)
    saved = ((UC_X86_REG_EBX, 0xB0B0B0B0), (UC_X86_REG_ESI, 0x51515151), (UC_X86_REG_EDI, 0xD1D1D1D1),
             (UC_X86_REG_EBP, 0xB9B9B9B9))
    for reg, value in saved:
        mu.reg_write(reg, value)
    mu.emu_start(CHOOSER, 0xFFFFFFFF, count=20000)
    eip = mu.reg_read(UC_X86_REG_EIP)
    if eip == CHOSEN_ON:
        return "choice", None
    assert eip == HALT, hex(eip)
    assert mu.reg_read(UC_X86_REG_ESP) == esp + 12, "ret 8"
    assert [mu.reg_read(r) for r, _ in saved] == [v for _, v in saved], "the saved registers"
    return "none", mu.reg_read(UC_X86_REG_EAX)


class LikingWorkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stock = STOCK.read_bytes()
        cls.fixed = {mode: _render(mode, [FEATURE_ID]) for mode in MODES}

    def test_stock_blanks_a_villager_who_likes_work(self) -> None:
        for blank in (0, 14):
            self.assertEqual(_choose(self.stock, blank=blank, likes=(WORK,)), ("none", 0))
        self.assertEqual(_choose(self.stock, blank=15, likes=(WORK,))[0], "choice")

    def test_fixed_a_villager_who_likes_work_is_never_blanked(self) -> None:
        for mode, exe in self.fixed.items():
            for blank in (0, 14, 15, 99):
                with self.subTest(mode=mode, blank=blank):
                    self.assertEqual(_choose(exe, blank=blank, likes=(1, WORK))[0], "choice")

    def test_fixed_anyone_else_is_blanked_as_before(self) -> None:
        for mode, exe in self.fixed.items():
            for likes in ((), (1,), (38, 3, 4, 5)):
                for blank, want in ((0, "none"), (14, "none"), (15, "choice")):
                    with self.subTest(mode=mode, likes=likes, blank=blank):
                        got = _choose(exe, blank=blank, likes=likes)
                        self.assertEqual(got, _choose(self.stock, blank=blank, likes=likes))
                        self.assertEqual(got[0], want)

    def test_disliking_work_still_refuses_70_in_100(self) -> None:
        for exe in (self.stock, self.fixed["stock"]):
            for roll, want in ((0, "none"), (69, "none"), (70, "choice")):
                with self.subTest(roll=roll, fixed=exe is not self.stock):
                    self.assertEqual(_choose(exe, blank=50, dislikes=(WORK,), dislike_roll=roll)[0], want)

    def test_every_blank_roll_matches_the_later_games(self) -> None:
        # Over every blank roll: one who likes work is blanked 0 in 100 (stock: 15); anyone else 15, as before.
        for likes, fixed_none, stock_none in (((WORK,), 0, 15), ((), 15, 15)):
            with self.subTest(likes=likes):
                fixed = sum(_choose(self.fixed["stock"], blank=b, likes=likes)[0] == "none" for b in range(100))
                stock = sum(_choose(self.stock, blank=b, likes=likes)[0] == "none" for b in range(100))
                self.assertEqual((fixed, stock), (fixed_none, stock_none))

    def test_the_caves_are_unused_padding_no_code_or_row_reaches(self) -> None:
        for offset, before, _ in LIKE_WORK_FIXES[1:]:
            self.assertEqual(self.stock[offset:offset + len(before)], before)
        pe = pefile.PE(data=self.stock, fast_load=True)
        text = pe.sections[0]
        code = self.stock[text.PointerToRawData:text.PointerToRawData + text.SizeOfRawData]
        targets = set()
        for insn in Cs(CS_ARCH_X86, CS_MODE_32).disasm(code, 0x400000 + text.VirtualAddress):
            if insn.mnemonic.startswith("j") or insn.mnemonic == "call":
                try:
                    targets.add(int(insn.op_str, 16))
                except ValueError:
                    pass
        for lo, n in ((0x455491, 15), (0x4554B2, 14)):
            self.assertFalse(any(lo <= t < lo + n for t in targets), hex(lo))
        for p in load_fun_patches():
            if p.game_id != "vv1" or p.id == FEATURE_ID:
                continue
            for patch in p.raw.get("patches", []):
                o, n = int(patch["offset"], 16), len(patch["after"]) // 2
                for lo, size in ((0x55491, 15), (0x554B2, 14), (0x39AF8, 8)):
                    self.assertFalse(o < lo + size and lo < o + n, (p.id, hex(o)))


# ---- Keeping a job the player assigned ---------------------------------------------------------------------------
# The owner (2026-11-16): "add part 2 like VV2".  The Lost Children's 0x461580, before a villager goes back to the job
# a player assigned: likes work (0x445510, word 43) -> keep; else rand(100) < 20 -> nothing that turn (0x46159E);
# else rand(100) >= 40 -> keep (0x4615B1); else food (+0x2EAA4) >= 4,000 (0x4615BC) or dislikes work (0x4615CD) ->
# nothing; else keep.  A New Home's work-spot routine 0x447CD0 reads no like at all; Fix Vanilla Bugs puts the same
# rule before its spot jump (0x447CFF -> 0x456E00).  Live play calls 0x447CD0 (0x448362, 0x4483AB); catch-up never
# does.  RUN from the routine's entry: the game's rand(100) scripted, the like and dislike tests real, and the run
# stopped at the spot's own case (the jump table 0x4480A8) or at the routine's return.
SPOT_ROUTINE, SPOT_TABLE, SPOT_FIELD, FOOD = 0x447CD0, 0x4480A8, 0x3B8, 0xA2EC
STATE = 0x30000000


def _spot(exe: bytes, *, spot: int = 2, likes=(), dislikes=(), food: int = 1000, rolls=(99, 99)):
    """("spot", case address) when it goes to the spot's case, or ("none", eax) when it returns."""
    image = pefile.PE(data=exe, fast_load=True).get_memory_mapped_image()
    table = [struct.unpack_from("<I", image, SPOT_TABLE - 0x400000 + 4 * i)[0] for i in range(14)]
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(0x400000, (len(image) + 0xFFFF) & ~0xFFFF)
    mu.mem_write(0x400000, image)
    mu.mem_map(VILLAGE, 0x100000)
    mu.mem_map(STATE, 0x100000)
    mu.mem_map(STACK - 0x10000, 0x20000)
    mu.mem_map(HALT, 0x1000)
    mu.mem_write(VILLAGE + 0x3E010, struct.pack("<I", STATE))
    mu.mem_write(STATE + FOOD, struct.pack("<i", food))
    rec = VILLAGE + INDEX * STRIDE
    mu.mem_write(rec + SPOT_FIELD, struct.pack("<i", spot))
    for i in range(4):
        mu.mem_write(rec + LIKES + 4 * i, struct.pack("<i", likes[i] if i < len(likes) else -1))
        mu.mem_write(rec + DISLIKES + 4 * i, struct.pack("<i", dislikes[i] if i < len(dislikes) else -1))
    queue = list(rolls)
    drawn = []
    cases = set(table)

    def hook(uc, address, size, _):
        if address == RAND:
            esp = uc.reg_read(UC_X86_REG_ESP)
            ret, = struct.unpack("<I", uc.mem_read(esp, 4))
            value = queue.pop(0) if queue else 99
            drawn.append(value)
            uc.reg_write(UC_X86_REG_EAX, value)
            uc.reg_write(UC_X86_REG_ECX, 0xC0C0C0C0)
            uc.reg_write(UC_X86_REG_EDX, 0xD0D0D0D0)
            uc.reg_write(UC_X86_REG_ESP, esp + 4)
            uc.reg_write(UC_X86_REG_EIP, ret)
        elif address in cases or address == HALT:
            uc.emu_stop()

    mu.hook_add(UC_HOOK_CODE, hook)
    esp = STACK - 0x100
    mu.mem_write(esp, struct.pack("<III", HALT, INDEX, 60))
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.reg_write(UC_X86_REG_ECX, VILLAGE)
    saved = ((UC_X86_REG_EBX, 0xB0B0B0B0), (UC_X86_REG_ESI, 0x51515151), (UC_X86_REG_EDI, 0xD1D1D1D1),
             (UC_X86_REG_EBP, 0xB9B9B9B9))
    for reg, value in saved:
        mu.reg_write(reg, value)
    mu.emu_start(SPOT_ROUTINE, 0xFFFFFFFF, count=20000)
    eip = mu.reg_read(UC_X86_REG_EIP)
    if eip in cases and eip != HALT:
        assert eip == table[spot - 1], hex(eip)
        assert mu.reg_read(UC_X86_REG_ECX) == VILLAGE, "ECX as at the site"
        assert mu.reg_read(UC_X86_REG_ESP) == esp - 16, "the routine's own four saves, nothing more"
        return ("spot", eip), drawn
    assert eip == HALT, hex(eip)
    assert mu.reg_read(UC_X86_REG_ESP) == esp + 12, "ret 8"
    assert [mu.reg_read(r) for r, _ in saved] == [v for _, v in saved], "the saved registers"
    return ("none", mu.reg_read(UC_X86_REG_EAX)), drawn


class KeepAssignedJobTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stock = STOCK.read_bytes()
        cls.fixed = {mode: _render(mode, [FEATURE_ID]) for mode in MODES}

    def test_stock_always_goes_to_the_spot(self) -> None:
        for likes, dislikes, food in (((), (), 0), ((), (WORK,), 9000), ((WORK,), (), 9000)):
            for rolls in ((0, 0), (19, 39), (99, 99)):
                with self.subTest(likes=likes, dislikes=dislikes, food=food, rolls=rolls):
                    got, drawn = _spot(self.stock, likes=likes, dislikes=dislikes, food=food, rolls=rolls)
                    self.assertEqual(got[0], "spot")
                    self.assertEqual(drawn, [], "no roll in the base game")

    def test_likes_work_always_keeps_it(self) -> None:
        for mode, exe in self.fixed.items():
            for food in (0, 4000, 9000):
                with self.subTest(mode=mode, food=food):
                    got, drawn = _spot(exe, likes=(3, WORK), food=food, rolls=(0, 0))
                    self.assertEqual(got[0], "spot")
                    self.assertEqual(drawn, [], "no roll for one who likes work")

    def test_the_lost_childrens_rule(self) -> None:
        cases = (  # (dislikes, food, first roll, second roll) -> kept
            ((), 1000, 19, None, False), ((), 1000, 20, 39, True), ((), 1000, 20, 40, True),
            ((), 3999, 50, 0, True), ((), 4000, 50, 39, False), ((), 9000, 50, 40, True),
            ((WORK,), 1000, 50, 39, False), ((WORK,), 1000, 50, 40, True), ((WORK,), 1000, 0, None, False),
        )
        for mode, exe in self.fixed.items():
            for dislikes, food, first, second, kept in cases:
                with self.subTest(mode=mode, dislikes=dislikes, food=food, first=first, second=second):
                    rolls = (first,) if second is None else (first, second)
                    got, drawn = _spot(exe, dislikes=dislikes, food=food, rolls=rolls)
                    self.assertEqual(got[0], "spot" if kept else "none")
                    if not kept:
                        self.assertEqual(got[1], 0, "nothing started: the scheduler goes on to its next choice")
                    self.assertEqual(drawn, list(rolls))

    def test_shares(self) -> None:
        # Over every pair of rolls: 80 in 100 kept at low food; 48 in 100 at 4,000 food or for one who dislikes work.
        exe = self.fixed["stock"]
        for dislikes, food, kept_in_10000 in (((), 1000, 8000), ((), 4000, 4800), ((WORK,), 0, 4800)):
            with self.subTest(dislikes=dislikes, food=food):
                kept = 0
                for first in range(100):
                    if first < 20:
                        continue                        # skipped; no second roll is drawn
                    for second in range(100):
                        kept += _spot(exe, dislikes=dislikes, food=food, rolls=(first, second))[0][0] == "spot"
                self.assertEqual(kept, kept_in_10000)

    def test_every_spot_case_is_reached_as_before(self) -> None:
        for spot in range(1, 15):
            with self.subTest(spot=spot):
                stock = _spot(self.stock, spot=spot)[0]
                fixed = _spot(self.fixed["stock"], spot=spot, likes=(WORK,))[0]
                self.assertEqual(fixed, stock)

    def test_the_cave_is_unused_space_no_code_or_row_reaches(self) -> None:
        pe = pefile.PE(data=self.stock, fast_load=True)
        text = pe.sections[0]
        self.assertGreaterEqual(text.PointerToRawData + text.SizeOfRawData, 0x56E00 + len(KEEP_JOB_CAVE))
        self.assertTrue(text.Characteristics & 0x20000000, "executable")
        for p in load_fun_patches():
            if p.game_id != "vv1" or p.id == FEATURE_ID:
                continue
            for patch in p.raw.get("patches", []):
                o, n = int(patch["offset"], 16), len(patch["after"]) // 2
                for lo, size in ((0x56E00, len(KEEP_JOB_CAVE)), (0x47CFF, 7)):
                    self.assertFalse(o < lo + size and lo < o + n, (p.id, hex(o)))


if __name__ == "__main__":
    unittest.main()
