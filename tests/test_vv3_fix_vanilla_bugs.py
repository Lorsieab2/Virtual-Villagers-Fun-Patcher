"""The Secret City: "Fix Vanilla Bugs" (vv3_fix_vanilla_bugs).

One row holds every base-game bug fix the owner has approved for The Secret
City; each fix is its own exact-byte patch in the row and has its own tests
here.  A later approved fix is added as another patch in the same row and
another test class below.

1. The Royal Jelly (island event slot 45).  The owner: "The Clear Vial is
   intended to cause the jelly to become bitter. The dark vial is intended to
   cure the cold. But the effects are swapped."  applyChoice 0x4180A0 tests
   the clicked choice at 0x4180F5 and runs the cure (sick flag rec+0xE89 := 0,
   Healing rec+0xEB4 += 15 + rand_n(15), clamped 0..100, activity 0x90) for
   choice 0, the clear vial, whose text (S1014) says the jelly spoiled; choice
   1, the dark vial, whose text (S1015) says the cold is gone, skips to the
   return.  Seen live: the clear vial cured the villager and raised Healing
   0 -> 24, the dark vial changed nothing.  The fix turns the `jne` at
   0x4180FB into `je`, so the dark vial runs the cure.

2. The Mysterious Vial, amber (slot 39), "scientific insight" result.  Its
   text (S974) says the villagers gain tech points, yet applyChoice 0x417770
   state 0 only raises the villager's Research (rec+0xEB8 += 15 +
   rand_n(30)).  The owner: "add a small tech point reward for the 'insight'
   result in addition to adding villager research skill."  The Research gain
   and its 0..100 clamp are re-encoded compactly in the same 53 bytes, which
   leaves room for `push 100; mov ecx, 0x582644; call 0x427130` -- the
   game's own tech adder, the one every island event that grants tech calls.
   100 is the game's own smallest tech reward (a duplicate common
   collectible, 0x42DF48); the events that grant tech give 1000 or 2000 per
   20 villagers.

3. The Mysterious Vial, quartz (slot 37), at exactly age 14.  resultText
   0x4173C0 picks the "becomes a little child" text (S959) when age >= 280
   (setge at 0x4173E0) while applyChoice takes the "becomes an elder" path
   when age <= 280 (jg at 0x417435).  Seen live: a villager aged 280 was told
   they became a little child and became an elder (age 1000, Healing +48,
   Research +39).  The owner: "for exactly-14, swap the text to match the
   effects."  setge becomes setg; the effects are untouched.

4. A village of exactly 150 villagers cannot be loaded again.  The save
   writer 0x45EF80 packs every active villager into the 150 x 0x11C-byte table
   at game+0x786C and then writes a 0 end-of-list flag at entry[count]; with
   150 villagers that flag lands on game+0x11ED4, the first byte of the block
   of 0x594990 saved just before it, whose size dword 0x2AD becomes 0x200.
   The load-time check 0x435710 compares it with 0x2AD and fails.  Seen live
   (v1.35.50 test build, Immediate Fixed, 2026-10-02): 149 saved and reloaded;
   150 was written with the size 0x200 and the game showed an empty main menu.
   Same fix as The Tree of Life's (see test_vv4_fix_vanilla_bugs.py): the end
   flag only below 150, the loader 0x45C860 bounded at 150 entries, and the
   block check accepting a size whose only difference is a zeroed low byte when
   entry #150 is in use, which repairs saves the unfixed game damaged.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX,
    UC_X86_REG_EDI, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from vv_fun_patcher import (  # noqa: E402
    EXPERIMENTAL_FUN_PATCH_IDS,
    load_builds,
    load_fun_patches,
    load_public_fun_patches,
    render_patched_bytes,
)
from save_table_emulator import VV3, SaveTableCases  # noqa: E402

FEATURE_ID = "vv3_fix_vanilla_bugs"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
MODES = ("stock", "collection_progression", "immediate_fixed")

# The three fixes: file offset, stock bytes, patched bytes.
JELLY_OFFSET = 0x180FB
JELLY_STOCK = bytes.fromhex("7558")
JELLY_PATCHED = bytes.fromhex("7458")
AMBER_OFFSET = 0x17797
AMBER_STOCK = bytes.fromhex(
    "8B4E048B91B80E000081C1AC0E000083C00F03D08BC283C40483F86489510C7E09C7410C64000000"
    "EB0B85C07D07C7410C00000000"
)
AMBER_PATCHED = bytes.fromhex(
    "8B4E040381B80E000083C00F83C40483F8647E036A645885C07D0231C08981B80E0000"
    "6864000000B944265800E867F900000F1F00"
)
QUARTZ_OFFSET = 0x173E0
QUARTZ_STOCK = bytes.fromhex("0F9DC1")
QUARTZ_PATCHED = bytes.fromhex("0F9FC1")
SAVE_WRITER_OFFSET = 0x5EFC5
SAVE_WRITER_STOCK = bytes.fromhex(
    "E8969BFCFF69DB1C0100005F5EC684186C780000005DB0015BC20400909090909090909090909090909090"
)
SAVE_WRITER_PATCHED = bytes.fromhex(
    "81FB96000000730DE88E9BFCFFC684386C780000005F5E5DB0015BC2040090909090909090909090909090"
)
SAVE_LOADER_OFFSET = 0x5C88D
SAVE_LOADER_STOCK = bytes.fromhex(
    "743233F6E8CAC2FCFF8D84306C780000508BCFE88B9FFFFF81C78C1F000081C61C010000E8AAC2FCFF8A8C306C"
    "78000084C975D05F5EB0015BC2040090909090909090"
)
SAVE_LOADER_PATCHED = bytes.fromhex(
    "743933F6E8CAC2FCFF8D84306C780000508BCFE88B9FFFFF81C78C1F000081C61C01000081FE68A60000730FE8"
    "A2C2FCFF80BC306C7800000075C95F5EB0015BC20400"
)
SAVE_CHECK_OFFSET = 0x35710
SAVE_CHECK_STOCK = bytes.fromhex(
    "8B5424045355568B32578BD9E8DFFFFFFF3D001000007F543BF075508B83380100008D7204B9340000008BFB33ED"
    "85C0F3A5BED40000007E2A8DBBD0000000EB048B5424148B0F8B0103D652FF500C85C07C1903F08B8338010000"
    "4583C7043BE87CDE5F5E5DB0015BC204005F5E5D32C05BC204009090909090909090909090"
)
SAVE_CHECK_PATCHED = bytes.fromhex(
    "8B5424045355568B325789CBE8DFFFFFFF3D001000007F5E39C6741189C130C939CE755280BAE4FEFFFF017549"
    "8B83380100008D72046A345989DF31ED85C0F3A5BED40000007E2A8DBBD0000000EB048B5424148B0F8B0101F2"
    "52FF500C85C07C1401C68B83380100004583C70439C57CDEB001EB0230C05F5E5D5BC2040090"
)
FIXES = (
    (JELLY_OFFSET, JELLY_STOCK, JELLY_PATCHED),
    (AMBER_OFFSET, AMBER_STOCK, AMBER_PATCHED),
    (QUARTZ_OFFSET, QUARTZ_STOCK, QUARTZ_PATCHED),
    (SAVE_WRITER_OFFSET, SAVE_WRITER_STOCK, SAVE_WRITER_PATCHED),
    (SAVE_LOADER_OFFSET, SAVE_LOADER_STOCK, SAVE_LOADER_PATCHED),
    (SAVE_CHECK_OFFSET, SAVE_CHECK_STOCK, SAVE_CHECK_PATCHED),
)
TECH_REWARD = 100

# Game addresses.
TECH = 0x582644                # the tech-points object; its first dword is the points
TECH_TOTAL = 0x5824A4          # lifetime tech earned (the 1,000,000 achievement)
JELLY_APPLY = 0x4180A0
AMBER_APPLY = 0x417770
QUARTZ_TEXT = 0x4173C0
RAND_N = 0x4032D0
# Helpers the event bodies call that are not under test: VA -> bytes their
# `ret` pops.
STUBS = {
    0x45C900: 4,   # village: start the subject's event action
    0x460F70: 4,   # villager: clear the task queue
    0x461080: 8,   # villager: pose
    0x461BF0: 4,   # villager: walk to the event spot
    0x455570: 8,   # villager: activity
    0x462670: 8,   # health setter (amber "younger" result)
    0x45F2D0: 4,   # clone (amber "two copies" result)
    0x412CD0: 4,   # achievement (reached only at 1,000,000 lifetime tech)
}

# Emulation layout.
STACK = 0x70000000
EVENT = 0x20000000
RECORD = 0x21000000
RETURN = 0x0BAD0000
HEALING, RESEARCH, SICK, AGE = 0xEB4, 0xEB8, 0xE89, 0xDC4


def _vv3():
    return next(build for build in load_builds() if build.id == "vv3")


def _render(mode: str, ids) -> bytes:
    rendered, _ = render_patched_bytes(STOCK, _vv3(), mode, list(ids))
    return bytes(rendered)


def _other_public_vv3_ids() -> list[str]:
    # The ordinary build: 256 Villagers (Experimental) replaces the save
    # writer and loader these rows fix (its own tests cover the two together,
    # tests/test_vv3_population_256.py FixVanillaBugsTests).
    return [p.id for p in load_public_fun_patches()
            if p.game_id == "vv3" and p.id != FEATURE_ID and p.id not in EXPERIMENTAL_FUN_PATCH_IDS]


def _changed_bytes(before: bytes, after: bytes) -> list[int]:
    field = pefile.PE(data=after, fast_load=True).OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    return [
        i for i in range(min(len(before), len(after)))
        if before[i] != after[i] and not field <= i < field + 4
    ]


class _Machine:
    """The real executable image in unicorn, with the helpers in STUBS
    returning at once, rand_n returning `roll`, and everything else real."""

    def __init__(self, exe: bytes, roll: int = 0) -> None:
        pe = pefile.PE(data=exe)
        image = pe.get_memory_mapped_image()
        self.mu = mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(0x400000, (len(image) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(0x400000, image)
        mu.mem_map(STACK - 0x10000, 0x20000)
        mu.mem_map(EVENT, 0x1000)
        mu.mem_map(RECORD, 0x2000)
        mu.mem_map(RETURN, 0x1000)
        self.roll = roll
        self.calls: list[int] = []
        mu.hook_add(UC_HOOK_CODE, self._on_code)

    def _on_code(self, mu, address, size, user_data) -> None:
        if address == RAND_N:
            self.calls.append(address)
            self._return(self.roll, 0)
        elif address in STUBS:
            self.calls.append(address)
            self._return(0, STUBS[address])

    def _return(self, value: int, pop: int) -> None:
        mu = self.mu
        esp = mu.reg_read(UC_X86_REG_ESP)
        ret = struct.unpack("<I", mu.mem_read(esp, 4))[0]
        mu.reg_write(UC_X86_REG_EAX, value & 0xFFFFFFFF)
        mu.reg_write(UC_X86_REG_ESP, esp + 4 + pop)
        mu.reg_write(UC_X86_REG_EIP, ret)

    def i32(self, va: int) -> int:
        return struct.unpack("<i", self.mu.mem_read(va, 4))[0]

    def set_i32(self, va: int, value: int) -> None:
        self.mu.mem_write(va, struct.pack("<i", value))

    def thiscall(self, entry: int, this: int, *args: int) -> int:
        """Call `entry` as __thiscall with stack args; return EAX.  The callee
        must pop exactly its arguments and keep the callee-saved registers."""
        mu = self.mu
        esp = STACK
        for arg in reversed(args):
            esp -= 4
            mu.mem_write(esp, struct.pack("<I", arg & 0xFFFFFFFF))
        esp -= 4
        mu.mem_write(esp, struct.pack("<I", RETURN))
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.reg_write(UC_X86_REG_ECX, this)
        saved = (0x5EED0001, 0x5EED0002, 0x5EED0003, 0x5EED0004)
        mu.reg_write(UC_X86_REG_EBX, saved[0])
        mu.reg_write(UC_X86_REG_EBP, saved[1])
        mu.reg_write(UC_X86_REG_EDI, saved[2])
        mu.reg_write(UC_X86_REG_ESI, saved[3])
        mu.emu_start(entry, RETURN, count=100000)
        assert mu.reg_read(UC_X86_REG_ESP) == STACK, hex(mu.reg_read(UC_X86_REG_ESP))
        assert (
            mu.reg_read(UC_X86_REG_EBX), mu.reg_read(UC_X86_REG_EBP),
            mu.reg_read(UC_X86_REG_EDI), mu.reg_read(UC_X86_REG_ESI),
        ) == saved
        return mu.reg_read(UC_X86_REG_EAX)


def _event_machine(exe: bytes, roll: int, state: int = 0, **record) -> _Machine:
    m = _Machine(exe, roll)
    m.set_i32(EVENT + 4, RECORD)          # the event's subject
    m.set_i32(EVENT + 0x10, state)        # the result resultText chose
    for field, value in record.items():
        offset = {"healing": HEALING, "research": RESEARCH, "age": AGE}[field]
        m.set_i32(RECORD + offset, value)
    return m


class ManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stock = STOCK.read_bytes()
        cls.feature = next(p for p in load_fun_patches() if p.id == FEATURE_ID)

    def test_manifest_row(self) -> None:
        raw = self.feature.raw
        self.assertEqual(raw["game_id"], "vv3")
        self.assertEqual(raw["name"], "Fix Vanilla Bugs")
        self.assertIn(FEATURE_ID, {p.id for p in load_public_fun_patches()})
        self.assertNotIn("dependencies", raw)
        self.assertIn("**Needs no other patch.**", raw["description"])
        self.assertIn(str(TECH_REWARD) + " tech points", raw["description"])
        pinned = [(int(p["offset"], 16), bytes.fromhex(p["before"]), bytes.fromhex(p["after"])) for p in raw["patches"]]
        self.assertEqual(pinned, list(FIXES))

    def test_default_on(self) -> None:
        from vv_fun_patcher_gui import DEFAULT_OFF_FUN_PATCH_IDS, OWNERS_DEFAULT_OFF_FUN_PATCH_IDS

        self.assertNotIn(FEATURE_ID, DEFAULT_OFF_FUN_PATCH_IDS)
        self.assertNotIn(FEATURE_ID, OWNERS_DEFAULT_OFF_FUN_PATCH_IDS)

    def test_stock_bytes_and_offsets(self) -> None:
        pe = pefile.PE(str(STOCK), fast_load=True)
        vas = (0x4180FB, 0x417797, 0x4173E0, 0x45EFC5, 0x45C88D, 0x435710)
        self.assertEqual(len(vas), len(FIXES))
        for va, (offset, before, _after) in zip(vas, FIXES):
            self.assertEqual(pe.get_offset_from_rva(va - 0x400000), offset)
            self.assertEqual(self.stock[offset:offset + len(before)], before)

    def test_nothing_else_branches_into_a_rewritten_region(self) -> None:
        pe = pefile.PE(str(STOCK))
        text = next(s for s in pe.sections if s.Name.startswith(b".text"))
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.skipdata = True
        regions = [(0x400000 + off, 0x400000 + off + len(before)) for off, before, _ in FIXES]
        incoming = []
        for ins in md.disasm(text.get_data(), 0x400000 + text.VirtualAddress):
            if not (ins.mnemonic.startswith("j") or ins.mnemonic == "call"):
                continue
            try:
                target = int(ins.op_str, 16)
            except ValueError:
                continue
            for start, end in regions:
                # A branch that lands on a region's first byte enters it the
                # way the stock fall-through does.
                # The save loader's region keeps its loop head 0x45C891 where it was.
                if start < target < end and not start <= ins.address < end and target != 0x45C891:
                    incoming.append((hex(ins.address), hex(target)))
        self.assertEqual(incoming, [])

    def test_render_alone_in_every_mode(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                without = _render(mode, [])
                rendered = _render(mode, [FEATURE_ID])
                for offset, before, after in FIXES:
                    self.assertEqual(without[offset:offset + len(before)], before)
                    self.assertEqual(rendered[offset:offset + len(after)], after)
                diff = _changed_bytes(without, rendered)
                allowed = set()
                for offset, before, _ in FIXES:
                    allowed.update(range(offset, offset + len(before)))
                self.assertTrue(diff)
                self.assertTrue(set(diff) <= allowed, [hex(i) for i in sorted(set(diff) - allowed)[:8]])
                self.assertEqual(len(rendered), len(without))

    def test_render_with_every_other_vv3_patch_in_every_mode(self) -> None:
        others = _other_public_vv3_ids()
        self.assertGreater(len(others), 10)
        allowed = set()
        for offset, before, _ in FIXES:
            allowed.update(range(offset, offset + len(before)))
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


class _Builds:
    @classmethod
    def builds(cls) -> dict[str, bytes]:
        if not hasattr(cls, "_builds"):
            others = _other_public_vv3_ids()
            builds = {}
            for mode in MODES:
                builds[(mode, "stock")] = _render(mode, [])
                builds[(mode, "patched")] = _render(mode, [FEATURE_ID])
                builds[(mode, "patched_with_all")] = _render(mode, others + [FEATURE_ID])
            cls._builds = builds
        return cls._builds


class RoyalJellyTests(unittest.TestCase, _Builds):
    def test_decoded(self) -> None:
        ins = next(Cs(CS_ARCH_X86, CS_MODE_32).disasm(JELLY_PATCHED, 0x4180FB))
        self.assertEqual((ins.mnemonic, ins.op_str), ("je", "0x418155"))
        stock = next(Cs(CS_ARCH_X86, CS_MODE_32).disasm(JELLY_STOCK, 0x4180FB))
        self.assertEqual((stock.mnemonic, stock.op_str), ("jne", "0x418155"))

    def _apply(self, exe: bytes, choice: int, roll: int, healing: int):
        m = _event_machine(exe, roll, healing=healing)
        m.mu.mem_write(RECORD + SICK, b"\x01")
        m.thiscall(JELLY_APPLY, EVENT, choice)
        return m.i32(RECORD + HEALING), m.mu.mem_read(RECORD + SICK, 1)[0], 0x455570 in m.calls

    def test_emulated_effect_follows_the_vial_text(self) -> None:
        for (mode, label), exe in self.builds().items():
            for roll in (0, 9, 14):
                for healing in (0, 50, 80, 100):
                    with self.subTest(mode=mode, build=label, roll=roll, healing=healing):
                        clear = self._apply(exe, 0, roll, healing)
                        dark = self._apply(exe, 1, roll, healing)
                        cured = (min(healing + 15 + roll, 100), 0, True)
                        unchanged = (healing, 1, False)
                        if label == "stock":
                            # The base game: the clear vial ("spoiled") cures.
                            self.assertEqual(clear, cured)
                            self.assertEqual(dark, unchanged)
                        else:
                            # Fixed: the dark vial ("the cold is gone") cures.
                            self.assertEqual(dark, cured)
                            self.assertEqual(clear, unchanged)


class AmberInsightTests(unittest.TestCase, _Builds):
    def test_decoded(self) -> None:
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        listing = [(i.address, i.mnemonic, i.op_str) for i in md.disasm(AMBER_PATCHED, 0x417797)]
        self.assertEqual(sum(i.size for i in md.disasm(AMBER_PATCHED, 0x417797)), len(AMBER_STOCK))
        self.assertEqual(
            listing,
            [
                (0x417797, "mov", "ecx, dword ptr [esi + 4]"),
                (0x41779A, "add", "eax, dword ptr [ecx + 0xeb8]"),
                (0x4177A0, "add", "eax, 0xf"),
                (0x4177A3, "add", "esp, 4"),
                (0x4177A6, "cmp", "eax, 0x64"),
                (0x4177A9, "jle", "0x4177ae"),
                (0x4177AB, "push", "0x64"),
                (0x4177AD, "pop", "eax"),
                (0x4177AE, "test", "eax, eax"),
                (0x4177B0, "jge", "0x4177b4"),
                (0x4177B2, "xor", "eax, eax"),
                (0x4177B4, "mov", "dword ptr [ecx + 0xeb8], eax"),
                (0x4177BA, "push", "0x64"),
                (0x4177BF, "mov", "ecx, 0x582644"),
                (0x4177C4, "call", "0x427130"),
                (0x4177C9, "nop", "dword ptr [eax]"),
            ],
        )
        # The tech adder is the one every tech-granting island event calls
        # with ECX = the tech object (The Mysterious Fog 0x414F43, the beans
        # 0x415923/0x415AA6, a duplicate collectible 0x42DF74).
        stock = STOCK.read_bytes()
        for va in (0x414F43, 0x415923, 0x415AA6, 0x42DF74):
            self.assertEqual(stock[va - 0x400000:va - 0x400000 + 10][:5], bytes.fromhex("B944265800"))
            call = stock[va - 0x400000 + 5:va - 0x400000 + 10]
            self.assertEqual(call[0], 0xE8)
            self.assertEqual(va + 10 + struct.unpack("<i", call[1:])[0], 0x427130)
        # The game's own smallest tech reward: a duplicate common collectible.
        self.assertEqual(stock[0x2DF48:0x2DF4D], bytes.fromhex("BA64000000"))

    def _insight(self, exe: bytes, roll: int, research: int, tech: int = 5000, total: int = 12345, state: int = 0):
        m = _event_machine(exe, roll, state=state, research=research)
        m.set_i32(TECH, tech)
        m.set_i32(TECH_TOTAL, total)
        m.thiscall(AMBER_APPLY, EVENT, 0)
        return m.i32(RECORD + RESEARCH), m.i32(TECH), m.i32(TECH_TOTAL), list(m.calls)

    def test_emulated_insight_keeps_research_and_adds_tech(self) -> None:
        for (mode, label), exe in self.builds().items():
            for roll in (0, 13, 29):
                for research in (-60, -20, 0, 40, 70, 85, 100, 130):
                    with self.subTest(mode=mode, build=label, roll=roll, research=research):
                        got_research, tech, total, calls = self._insight(exe, roll, research)
                        new = research + 15 + roll
                        self.assertEqual(got_research, max(0, min(100, new)))
                        reward = 0 if label == "stock" else TECH_REWARD
                        self.assertEqual(tech, 5000 + reward)
                        self.assertEqual(total, 12345 + reward)
                        # The same helper calls, in order, as the base game.
                        self.assertEqual(calls, [0x45C900, RAND_N, 0x460F70, 0x455570])

    def test_emulated_tech_reward_goes_through_the_game_adder(self) -> None:
        # Negative tech (left as in the base game) still gains exactly the
        # reward; the lifetime counter reaching 1,000,000 runs the game's own
        # achievement call.
        for mode in MODES:
            exe = self.builds()[(mode, "patched")]
            with self.subTest(mode=mode):
                _r, tech, _t, _c = self._insight(exe, 0, 0, tech=-300)
                self.assertEqual(tech, -300 + TECH_REWARD)
                _r, tech, total, calls = self._insight(exe, 0, 0, tech=0, total=999_950)
                self.assertEqual((tech, total), (TECH_REWARD, 999_950 + TECH_REWARD))
                self.assertIn(0x412CD0, calls)

    def test_emulated_other_amber_results_unchanged(self) -> None:
        for (mode, label), exe in self.builds().items():
            for state, expected_call in ((1, 0x462670), (2, 0x45F2D0)):
                with self.subTest(mode=mode, build=label, state=state):
                    research, tech, total, calls = self._insight(exe, 7, 40, state=state)
                    self.assertEqual((research, tech, total), (40, 5000, 12345))
                    self.assertIn(expected_call, calls)
                    self.assertNotIn(RAND_N, calls)
            with self.subTest(mode=mode, build=label, choice="bring it back"):
                m = _event_machine(exe, 7, state=0, research=40)
                m.set_i32(TECH, 5000)
                m.thiscall(AMBER_APPLY, EVENT, 1)
                self.assertEqual((m.i32(RECORD + RESEARCH), m.i32(TECH)), (40, 5000))


class QuartzAgeFourteenTests(unittest.TestCase, _Builds):
    ELDER_TEXT, CHILD_TEXT = 0x3BE, 0x3BF

    def test_decoded(self) -> None:
        ins = next(Cs(CS_ARCH_X86, CS_MODE_32).disasm(QUARTZ_PATCHED, 0x4173E0))
        self.assertEqual((ins.mnemonic, ins.op_str), ("setg", "cl"))
        # The effect's own test, which the text now matches: age > 280 takes
        # the "becomes a child" path.
        stock = STOCK.read_bytes()
        self.assertEqual(stock[0x1742B:0x1743B], bytes.fromhex("81B8C40D0000180100000F8FA4000000"))

    def _text(self, exe: bytes, age: int, choice: int = 0) -> int:
        m = _event_machine(exe, 0, age=age)
        return m.thiscall(QUARTZ_TEXT, EVENT, choice)

    def test_emulated_text_matches_the_effect_at_every_age(self) -> None:
        for (mode, label), exe in self.builds().items():
            for age in (0, 100, 279, 280, 281, 360, 999, 1000, 2000):
                with self.subTest(mode=mode, build=label, age=age):
                    text = self._text(exe, age)
                    effect_is_elder = age <= 0x118   # applyChoice: jg 0x4174DF
                    if label == "stock" and age == 280:
                        # The base game's mismatch the fix removes.
                        self.assertEqual(text, self.CHILD_TEXT)
                    else:
                        self.assertEqual(text, self.ELDER_TEXT if effect_is_elder else self.CHILD_TEXT)
                    self.assertEqual(self._text(exe, age, choice=1), 0x3C1)


def _listing(code: bytes, va: int) -> list[tuple[int, str, str]]:
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    assert sum(i.size for i in md.disasm(code, va)) == len(code)
    return [(i.address, i.mnemonic, i.op_str) for i in md.disasm(code, va)]


class Save150DecodeTests(unittest.TestCase):
    def test_writer_decoded(self) -> None:
        listing = _listing(SAVE_WRITER_PATCHED, 0x45EFC5)
        self.assertEqual(
            listing[:10],
            [
                (0x45EFC5, "cmp", "ebx, 0x96"),
                (0x45EFCB, "jae", "0x45efda"),
                (0x45EFCD, "call", "0x428b60"),
                (0x45EFD2, "mov", "byte ptr [eax + edi + 0x786c], 0"),
                (0x45EFDA, "pop", "edi"),
                (0x45EFDB, "pop", "esi"),
                (0x45EFDC, "pop", "ebp"),
                (0x45EFDD, "mov", "al, 1"),
                (0x45EFDF, "pop", "ebx"),
                (0x45EFE0, "ret", "4"),
            ],
        )
        self.assertEqual({m for _a, m, _o in listing[10:]}, {"nop"})
        # EDI is the entry offset: the stock loop adds 0x11C to it for each saved villager.
        stock = _listing(STOCK.read_bytes()[0x5EF80:0x5EFC5], 0x45EF80)
        self.assertIn((0x45EF86, "xor", "edi, edi"), stock)
        self.assertIn((0x45EFB5, "inc", "ebx"), stock)
        self.assertIn((0x45EFB6, "add", "edi, 0x11c"), stock)

    def test_loader_decoded(self) -> None:
        self.assertEqual(
            _listing(SAVE_LOADER_PATCHED, 0x45C88D),
            [
                (0x45C88D, "je", "0x45c8c8"),
                (0x45C88F, "xor", "esi, esi"),
                (0x45C891, "call", "0x428b60"),
                (0x45C896, "lea", "eax, [eax + esi + 0x786c]"),
                (0x45C89D, "push", "eax"),
                (0x45C89E, "mov", "ecx, edi"),
                (0x45C8A0, "call", "0x456830"),
                (0x45C8A5, "add", "edi, 0x1f8c"),
                (0x45C8AB, "add", "esi, 0x11c"),
                (0x45C8B1, "cmp", "esi, 0xa668"),
                (0x45C8B7, "jae", "0x45c8c8"),
                (0x45C8B9, "call", "0x428b60"),
                (0x45C8BE, "cmp", "byte ptr [eax + esi + 0x786c], 0"),
                (0x45C8C6, "jne", "0x45c891"),
                (0x45C8C8, "pop", "edi"),
                (0x45C8C9, "pop", "esi"),
                (0x45C8CA, "mov", "al, 1"),
                (0x45C8CC, "pop", "ebx"),
                (0x45C8CD, "ret", "4"),
            ],
        )
        self.assertEqual(0xA668, 150 * 0x11C)

    def test_check_decoded(self) -> None:
        listing = _listing(SAVE_CHECK_PATCHED, 0x435710)
        self.assertEqual(
            listing[7:17],
            [
                (0x43571C, "call", "0x435700"),
                (0x435721, "cmp", "eax, 0x1000"),
                (0x435726, "jg", "0x435786"),
                (0x435728, "cmp", "esi, eax"),
                (0x43572A, "je", "0x43573d"),
                (0x43572C, "mov", "ecx, eax"),
                (0x43572E, "xor", "cl, cl"),
                (0x435730, "cmp", "esi, ecx"),
                (0x435732, "jne", "0x435786"),
                (0x435734, "cmp", "byte ptr [edx - 0x11c], 1"),
            ],
        )
        self.assertEqual(listing[17], (0x43573B, "jne", "0x435786"))
        self.assertEqual(listing[-2:], [(0x43578C, "ret", "4"), (0x43578F, "nop", "")])

    def test_only_caller_passes_the_block_right_after_the_table(self) -> None:
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.skipdata = True
        pe = pefile.PE(str(STOCK))
        text = next(s for s in pe.sections if s.Name.startswith(b".text"))
        calls = [i.address for i in md.disasm(text.get_data(), 0x400000 + text.VirtualAddress)
                 if i.mnemonic == "call" and i.op_str == "0x435710"]
        self.assertEqual(calls, [0x4289F8])
        site = _listing(STOCK.read_bytes()[0x289EC:0x289F3], 0x4289EC)
        self.assertEqual(site[0], (0x4289EC, "lea", "ecx, [ebx + 0x11ed4]"))
        self.assertEqual(0x786C + 150 * 0x11C, 0x11ED4)
        # the block size the check compares with (stubbed in the emulation) is this constant
        self.assertEqual(_listing(STOCK.read_bytes()[0x35700:0x35706], 0x435700),
                         [(0x435700, "mov", "eax, 0x2ad"), (0x435705, "ret", "")])


class Save150EmulationTests(SaveTableCases, unittest.TestCase, _Builds):
    LAYOUT = VV3


if __name__ == "__main__":
    unittest.main()
