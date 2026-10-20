"""VV5 Statue Drops: Normal Action or Honoring, RUN from the rendered executable.

Stock New Believers dispatches a villager dropped on a COMPLETED statue with
`push 0x9D` (Polishing the Statue) at two sites, 0x46BF9A and 0x4796EB; an
upgradeable statue is dispatched with `push 0xA0` (Honoring) at 0x46C45D and
0x46CDED.  The row replaces each completed-statue push with a call through a
trampoline to the selector (0x494840, which jumps to 0x494D30) that calls the
game's own RNG(2) and leaves 0x9D or 0xA0 on the stack exactly where the push
would have.

Each site is executed in an emulator from the patched call, with only the C
runtime's rand() replaced by controlled values (the game's own RNG wrapper at
0x403660 still reduces each modulo its argument).  The site must resume at the
byte after the original five-byte push with ESP four bytes lower and the
registers the following code reads (ECX, EBX, ESI, EDI, EBP) unchanged.  EAX
and EDX are clobbered, which is harmless: the next thing either site reaches
is the dispatcher 0x465580, which loads both from its own arguments before
reading them -- pinned here from the stock bytes.

The owner (2026-10-20): the game's own (autonomous) choices follow the 14%
rule for both statue actions; the player's own drop never does.  At the task
continuation's site (0x46BF9A: a villager carrying a statue job on by
themselves; ECX is that villager's record) the 50/50 pick is kept for a
villager checked on its skill -- Honoring on Devotion (+0x1C74 = 5),
Polishing on Building (4) -- and for anyone else only when a second RNG(100)
is below 14.  Otherwise the villager does neither: the continuation 0x46BCF0
returns "nothing started" (al = 0) through its own epilogue shape, so the
scheduler goes on to its own next choice.  The player's drop (0x4796EB) is the
plain 50/50 for anyone.
"""
from __future__ import annotations

import random
import struct
import sys
import unittest
from pathlib import Path

import capstone
import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI, UC_X86_REG_EIP,
    UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_fun_patcher as vfp  # noqa: E402

EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
STOCK_ABSENT = "the stock executables (research/stock-executables) are gitignored and absent"
FEATURE = "vv5_statue_polishing_or_honoring"
SITES = (0x46BF9A, 0x4796EB)
CONTINUATION, DROP = SITES
POLISHING, HONORING = 0x9D, 0xA0
NEITHER = "neither"
DEVOTION, BUILDING = 5, 4
PREFERENCE = 0x1C74             # the job checkmark: 5 Devotion, 4 Building, -1 none
RNG = 0x403660                  # the game's RNG(n) wrapper: rand() % n
SCRATCH = 0x0F000000
RAND_VALUE = SCRATCH
RECORD = 0x0F100000
FRAME_RET = 0x0F200000          # 0x46BCF0's caller, for the "neither" return
STACK_TOP = 0x10800000
CS = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
KEPT = dict(ecx=UC_X86_REG_ECX, ebx=UC_X86_REG_EBX, esi=UC_X86_REG_ESI,
            edi=UC_X86_REG_EDI, ebp=UC_X86_REG_EBP)


def _render(with_row: bool) -> bytes:
    build = next(b for b in vfp.load_builds() if b.id == "vv5")
    rendered, applied = vfp.render_patched_bytes(EXE, build, "immediate_fixed", [FEATURE] if with_row else [])
    assert (f"feature:{FEATURE}" in {r["owner"] for r in applied}) == with_row
    return bytes(rendered)


def _crt_rand(image: bytes) -> int:
    """The C runtime rand() the RNG wrapper calls, decoded from the image."""
    pe = pefile.PE(data=image, fast_load=True)
    o = pe.get_offset_from_rva(RNG - 0x400000)
    calls = [i for i in CS.disasm(image[o:o + 0x20], RNG) if i.mnemonic == "call"]
    return int(calls[0].op_str, 16)


_MACHINES: dict = {}


def _machine(image: bytes):
    key = id(image)
    if key not in _MACHINES:
        pe = pefile.PE(data=image)
        mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(0x400000, (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF)
        mu.mem_write(0x400000, image[:pe.OPTIONAL_HEADER.SizeOfHeaders])
        for section in pe.sections:
            mu.mem_write(0x400000 + section.VirtualAddress, section.get_data())
        mu.mem_map(SCRATCH, 0x1000)
        mu.mem_map(RECORD, 0x10000)
        mu.mem_map(FRAME_RET, 0x1000)
        mu.mem_write(FRAME_RET, b"\xF4")
        mu.mem_map(STACK_TOP - 0x10000, 0x10000)
        state = {"values": [], "rng_args": []}
        rand = _crt_rand(image)
        # mov eax, [RAND_VALUE] ; ret -- RAND_VALUE is refilled before each call
        mu.mem_write(rand, b"\xA1" + struct.pack("<I", RAND_VALUE) + b"\xC3")

        def hook(uc, address, size, _):
            if address == RNG:
                esp = uc.reg_read(UC_X86_REG_ESP)
                state["rng_args"].append(struct.unpack("<i", uc.mem_read(esp + 4, 4))[0])
            elif address == rand:
                value = state["values"].pop(0) if state["values"] else 0
                uc.mem_write(RAND_VALUE, struct.pack("<I", value))
            elif address == FRAME_RET:
                uc.emu_stop()

        mu.hook_add(UC_HOOK_CODE, hook)
        _MACHINES[key] = (mu, state)
    return _MACHINES[key]


SAVED = (0x44444444, 0x22222222, 0x33333333, 0x55555555)   # edi, ebx, esi, ebp as 0x46BCF0 saved them


def _run(image: bytes, site: int, rand_values, preference=None) -> dict:
    """rand_values: the C runtime rand() results in call order.  preference:
    the villager's job checkmark at RECORD + 0x1C74, with ECX = RECORD (None:
    ECX is a sentinel no code may read through).  The stack is 0x46BCF0's
    frame at the site: the pushed argument, its four saved registers, its
    0x2C locals, its return address (FRAME_RET)."""
    mu, state = _machine(image)
    state["values"] = list(rand_values) if isinstance(rand_values, (list, tuple)) else [rand_values]
    state["rng_args"] = rng_args = []
    esp = STACK_TOP - 0x200
    frame = struct.pack("<I", 0xCAFEF00D) + struct.pack("<4I", *SAVED) + bytes(0x2C) + struct.pack("<I", FRAME_RET)
    mu.mem_write(esp, frame)
    mu.reg_write(UC_X86_REG_ESP, esp)
    sentinels = dict(ecx=0x11111111, ebx=0x99999999, esi=0x88888888, edi=0x77777777, ebp=0x66666666)
    if preference is not None:
        sentinels["ecx"] = RECORD
        mu.mem_write(RECORD + PREFERENCE, struct.pack("<i", preference))
    for name, value in sentinels.items():
        mu.reg_write(KEPT[name], value)
    mu.emu_start(site, site + 5, count=4000)
    eip = mu.reg_read(UC_X86_REG_EIP)
    end = mu.reg_read(UC_X86_REG_ESP)
    if eip == FRAME_RET:
        return dict(pushed=NEITHER, al=mu.reg_read(UC_X86_REG_EAX) & 0xFF, esp_delta=esp - end,
                    restored=(mu.reg_read(UC_X86_REG_EDI), mu.reg_read(UC_X86_REG_EBX),
                              mu.reg_read(UC_X86_REG_ESI), mu.reg_read(UC_X86_REG_EBP)),
                    rng_args=rng_args)
    return dict(
        eip=eip,
        esp_delta=esp - end,
        pushed=struct.unpack("<I", mu.mem_read(end, 4))[0],
        below=struct.unpack("<I", mu.mem_read(end + 4, 4))[0],
        kept={name: mu.reg_read(reg) for name, reg in KEPT.items()} == sentinels,
        rng_args=rng_args,
    )


@unittest.skipUnless(EXE.is_file(), STOCK_ABSENT)
class StatueSelectorExecutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stock = _render(False)
        cls.patched = _render(True)
        cls.honor = 0 if _run(cls.patched, DROP, 0)["pushed"] == HONORING else 1

    def test_stock_pushes_polishing_for_a_completed_statue_and_honoring_for_an_upgradeable_one(self):
        pe = pefile.PE(data=self.stock, fast_load=True)
        for va, action in ((0x46BF9A, POLISHING), (0x4796EB, POLISHING),
                           (0x46C45D, HONORING), (0x46CDED, HONORING)):
            o = pe.get_offset_from_rva(va - 0x400000)
            self.assertEqual(self.stock[o:o + 5], b"\x68" + struct.pack("<I", action), hex(va))
        # The dispatcher both sites reach next loads EDX and EAX from its own
        # arguments before any read, so the selector clobbering them is dead.
        o = pe.get_offset_from_rva(0x465580 - 0x400000)
        self.assertEqual(self.stock[o:o + 8], bytes.fromhex("8B5424088B442404"))
        # The continuation's own epilogue -- the shape "neither" returns through.
        o = pe.get_offset_from_rva(0x46BFA4 - 0x400000)
        self.assertEqual(self.stock[o:o + 10], bytes.fromhex("5F5B5EB0015D83C42CC3"))

    def test_stock_sites_always_push_polishing(self):
        for site in SITES:
            for rand_value in (4660, 4661):
                with self.subTest(site=hex(site), rand=rand_value):
                    r = _run(self.stock, site, rand_value)
                    self.assertEqual((r["pushed"], r["esp_delta"], r["rng_args"]), (POLISHING, 4, []))

    def _resumes(self, r, site):
        self.assertEqual(r["eip"], site + 5, "resumes after the replaced push")
        self.assertEqual(r["esp_delta"], 4, "nets exactly one pushed dword, like the push")
        self.assertEqual(r["below"], 0xCAFEF00D, "the caller's stack is untouched")
        self.assertTrue(r["kept"], "ECX/EBX/ESI/EDI/EBP must survive")

    def test_the_players_drop_is_the_plain_50_50_for_anyone(self):
        for preference in (None, -1, 0, 1, 2, 3, BUILDING, DEVOTION):
            by_roll = {0: set(), 1: set()}
            for rand_value in (0, 2, 4660, 0x7FFE, 1, 3, 4661, 0x7FFF):
                with self.subTest(preference=preference, rand=rand_value):
                    r = _run(self.patched, DROP, [rand_value, 0], preference)
                    self.assertEqual(r["rng_args"], [2], "exactly one RNG(2) roll, no 14% roll")
                    self._resumes(r, DROP)
                    by_roll[rand_value % 2].add(r["pushed"])
            with self.subTest(preference=preference):
                self.assertEqual(len(by_roll[0]), 1)
                self.assertEqual(len(by_roll[1]), 1)
                self.assertEqual(by_roll[0] | by_roll[1], {POLISHING, HONORING})

    def test_the_continuation_keeps_each_pick_for_a_villager_checked_on_its_skill(self):
        for pick, checked, action in ((self.honor, DEVOTION, HONORING), (1 - self.honor, BUILDING, POLISHING)):
            with self.subTest(action=hex(action)):
                r = _run(self.patched, CONTINUATION, [pick, 99], checked)
                self.assertEqual((r["pushed"], r["rng_args"]), (action, [2]))
                self._resumes(r, CONTINUATION)

    def test_the_continuation_gates_each_pick_at_14_in_100_for_anyone_else(self):
        for pick, action, checked in ((self.honor, HONORING, DEVOTION), (1 - self.honor, POLISHING, BUILDING)):
            for preference in (-1, 0, 1, 2, 3, BUILDING, DEVOTION):
                if preference == checked:
                    continue
                with self.subTest(action=hex(action), preference=preference, second=13):
                    r = _run(self.patched, CONTINUATION, [pick, 13], preference)
                    self.assertEqual((r["pushed"], r["rng_args"]), (action, [2, 100]))
                    self._resumes(r, CONTINUATION)
                with self.subTest(action=hex(action), preference=preference, second=14):
                    # Neither statue action: 0x46BCF0 returns "nothing started"
                    # through its own frame, every saved register restored.
                    r = _run(self.patched, CONTINUATION, [pick, 14], preference)
                    self.assertEqual(r["pushed"], NEITHER)
                    self.assertEqual(r["al"], 0)
                    self.assertEqual(r["restored"], SAVED)
                    self.assertEqual(r["esp_delta"], -(4 + 16 + 0x2C + 4))
                    self.assertEqual(r["rng_args"], [2, 100])

    def test_measured_shares(self):
        # The C runtime's rand() as a uniform 0..0x7FFF stream, 4000 decisions per case.
        rng = random.Random(20261020)
        n = 4000
        cases = {
            ("continuation", "checked on Devotion"): (CONTINUATION, DEVOTION, (0.50, 0.07, 0.43)),
            ("continuation", "checked on Building"): (CONTINUATION, BUILDING, (0.07, 0.50, 0.43)),
            ("continuation", "checked on another job"): (CONTINUATION, 1, (0.07, 0.07, 0.86)),
            ("continuation", "no checkmark"): (CONTINUATION, -1, (0.07, 0.07, 0.86)),
            ("player's drop", "no checkmark"): (DROP, -1, (0.50, 0.50, 0.0)),
            ("player's drop", "checked on another job"): (DROP, 1, (0.50, 0.50, 0.0)),
        }
        for name, (site, preference, expected) in cases.items():
            with self.subTest(case=name):
                counts = {HONORING: 0, POLISHING: 0, NEITHER: 0}
                for _ in range(n):
                    r = _run(self.patched, site, [rng.randrange(0x8000), rng.randrange(0x8000)], preference)
                    counts[r["pushed"]] += 1
                shares = tuple(counts[k] / n for k in (HONORING, POLISHING, NEITHER))
                print(f"statue {name[0]}, {name[1]}: Honoring {shares[0]:.3f}, Polishing {shares[1]:.3f}, "
                      f"neither {shares[2]:.3f}")
                for got, want in zip(shares, expected):
                    self.assertAlmostEqual(got, want, delta=0.035)


if __name__ == "__main__":
    unittest.main()
