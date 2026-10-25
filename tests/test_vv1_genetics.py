"""Genetics (A New Home): a newborn's head from its parents ("VVFP VV1 Genetics.dll", native/vv1_genetics;
the owner, 2026-10-25).

Everything here runs the game's own code in an emulator, the stock executable with the DLL installed, the
game's rand(bound) answered by the test so every value it can return is tried:

* the creator 0x43C350 as the pregnancy tick calls it for a birth's first child (returning to 0x42EFD5):
  for every rand answer the head is the rule's -- (father + mother) / 2 + rand(3) - 1, the rolled head on
  rand(100) < 5 -- clamped to the baby's sex (a boy 0..18, never 19; a girl 0..19);
* the father is Show Parents' (Vv1ParentageQueryExpectedFather); unknown (-1), out of range, or no
  Show Parents: the mother's head alone;
* the distribution over every rand answer: 95% within one of the base, 5% the rolled head;
* twins and triplets: 0x43C840 copies the first child's head;
* every other caller of the creator, and the stock executable without the DLL, keep the rolled head;
* all or nothing: one changed byte anywhere it checks and nothing is written.

The live effect in a running game is NOT verified here.
"""
from __future__ import annotations

import functools
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402

try:
    import pefile  # noqa: F401
    from story_emulator import HEAP, STACK_TOP, Process

    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False
    HEAP = STACK_TOP = 0

DLL = ROOT / "assets" / "genetics" / "VVFP VV1 Genetics.dll"
CREATOR, TWIN, RAND = 0x43C350, 0x43C840, 0x402F10
SITE, RESUME, BIRTH = 0x43C647, 0x43C64D, 0x42EFD5
STRIDE = 0x3D8
FAKE_PARENTAGE = 0x7E000000


@functools.lru_cache(maxsize=None)
def _build():
    return {b.id: b for b in patcher.load_builds()}["vv1"]


def stock_path() -> Path:
    return ROOT / "inputs" / "vv1-stock-copy" / _build().input_name


@functools.lru_cache(maxsize=None)
def stock_exe() -> bytes:
    return stock_path().read_bytes()


def have() -> bool:
    return HAVE_EMULATOR and stock_path().is_file() and DLL.is_file()


class Village:
    """The records in the emulator and the head store at 0x43C647 run as the creator reaches it."""

    def __init__(self, dll: bool = True, exe: bytes | None = None, father: int | None = None):
        self.p = Process(exe if exe is not None else stock_exe(), DLL if dll else None)
        self.father = father
        if father is not None:
            self.p.api_handlers["GetModuleHandleA"] = lambda p: (FAKE_PARENTAGE, 4)
            query = self.p.alloc(0x10)
            self.p.write(query, b"\xC3")
            self.p.stub(query, self._query)
            self.p.api_handlers["GetProcAddress"] = lambda p, q=query: (
                q if p.cstring(p.arg(1)) == "Vv1ParentageQueryExpectedFather" else 0, 8)
        if dll:
            self.p.export("VvfpStartup", 1, 0)
        self.records = self.p.alloc(256 * STRIDE)
        self.answers: list[int] = []
        self.bounds: list[int] = []
        self.p.stub(RAND, self._rand)
        self.asked: list[int] = []

    def _query(self, p):
        index, out = p.arg(0), p.arg(1)
        self.asked.append(index)
        p.put32(out, self.father & 0xFFFFFFFF)
        p.put32(out + 4, 0)
        return 1, 16

    def _rand(self, p):
        bound = p.arg(0)
        self.bounds.append(bound)
        value = self.answers.pop(0) if self.answers else 0
        assert 0 <= value < max(bound, 1), (value, bound)
        return value, 0

    def head_store(self, *, mother: int, sex: int, rolled: int, ret: int = BIRTH, mother_index: int = 3,
                   answers=()) -> int:
        """The head stored for a child of `sex` whose mother (record `mother_index`) has head `mother`."""
        child = 7
        self.p.put32(self.records + mother_index * STRIDE + 0x360, mother)
        self.p.put32(self.records + child * STRIDE + 0x350, sex)
        esp = STACK_TOP - 0x4000
        self.p.put32(esp + 4, mother_index * STRIDE)          # the caller's EDI, saved by the creator
        self.p.put32(esp + 0x44, ret)                          # the creator's return address
        self.p.set_reg("esp", esp)
        self.p.set_reg("eax", rolled)
        self.p.set_reg("esi", self.records + child * STRIDE)
        self.p.set_reg("ebx", self.records)
        self.answers = list(answers)
        self.bounds = []
        self.p.run(SITE, RESUME)
        return self.p.u32(self.records + child * STRIDE + 0x360)


def rule(base: int, top: int, r100: int, r3: int, rolled: int) -> int:
    if r100 < 5:
        return rolled
    return max(0, min(top, base + r3 - 1))


def _skip():
    return unittest.skipUnless(have(), "unicorn/pefile, the stock A New Home or the DLL is missing")


@_skip()
class TheHead(unittest.TestCase):
    def test_installs_and_writes_one_detour(self):
        v = Village()
        self.assertEqual(v.p.export("VvfpGeneticsInstalled"), 1)
        self.assertEqual(v.p.read(SITE, 1), b"\xE9")
        self.assertEqual(v.p.read(SITE + 5, 1), b"\x90")

    def test_every_answer_with_a_known_father(self):
        for father, mother in ((0, 0), (3, 9), (18, 19), (19, 19), (10, 11), (0, 19)):
            for sex, top in ((1, 18), (2, 19)):
                v = Village(father=father)
                base = (father + mother) // 2
                for r100 in (0, 4, 5, 50, 99):
                    for r3 in range(3):
                        rolled = 7
                        got = v.head_store(mother=mother, sex=sex, rolled=rolled, answers=[r100, r3])
                        with self.subTest(father=father, mother=mother, sex=sex, r100=r100, r3=r3):
                            self.assertEqual(got, rule(base, top, r100, r3, rolled))
                            self.assertEqual(v.bounds[0], 100)
                            if r100 >= 5:
                                self.assertEqual(v.bounds, [100, 3])
                self.assertTrue(set(v.asked) == {3})       # asked about the mother's own record

    def test_a_boy_is_never_given_19(self):
        for father, mother in ((19, 19), (18, 19), (19, 18)):
            v = Village(father=father)
            for r100 in range(100):
                for r3 in range(3):
                    got = v.head_store(mother=mother, sex=1, rolled=18, answers=[r100, r3])
                    self.assertLessEqual(got, 18)
            for r3 in range(3):                             # a girl can be
                self.assertEqual(Village(father=19).head_store(mother=19, sex=2, rolled=0, answers=[50, r3]),
                                 min(19, 19 + r3 - 1))

    def test_an_unknown_father_means_the_mothers_head_alone(self):
        for father in (-1, 20, 99, None):
            for mother in (0, 5, 19):
                for r3 in range(3):
                    v = Village(father=father)
                    got = v.head_store(mother=mother, sex=2, rolled=4, answers=[50, r3])
                    with self.subTest(father=father, mother=mother, r3=r3):
                        self.assertEqual(got, max(0, min(19, mother + r3 - 1)))

    def test_the_distribution_over_every_answer(self):
        v = Village(father=6)                               # base (6 + 12) / 2 = 9
        counts: dict[int, int] = {}
        for r100 in range(100):
            for r3 in range(3):
                got = v.head_store(mother=12, sex=2, rolled=15, answers=[r100, r3])
                counts[got] = counts.get(got, 0) + 1
        self.assertEqual(counts, {8: 95, 9: 95, 10: 95, 15: 15})     # 5 in 100 keep the rolled head

    def test_other_callers_and_a_bad_mother_keep_the_rolled_head(self):
        v = Village(father=4)
        for ret in (0x42EF64, 0x4242FD, 0x41C50E, 0x42C3F4):
            self.assertEqual(v.head_store(mother=10, sex=2, rolled=13, ret=ret, answers=[50, 0]), 13)
            self.assertEqual(v.bounds, [])                  # nothing rolled for them
        self.assertEqual(v.head_store(mother=25, sex=2, rolled=13, answers=[50, 0]), 13)
        self.assertEqual(v.head_store(mother=-1, sex=2, rolled=13, answers=[50, 0]), 13)

    def test_without_the_dll_the_head_is_the_rolled_one(self):
        v = Village(dll=False)
        self.assertEqual(v.head_store(mother=10, sex=1, rolled=13, answers=[50, 0]), 13)


@_skip()
class TwinsAndInstall(unittest.TestCase):
    def test_a_twin_copies_the_first_childs_head(self):
        """The twin and triplet creator 0x43C840 (0x42F021, 0x42F06D: the first child's index, then the
        twin's) copies the sex, body and head of the child it is given (0x43C9C1..0x43C9DF): run here on
        an inherited head, the twin gets it."""
        v = Village(father=6)
        first = v.records + 7 * STRIDE
        head = v.head_store(mother=12, sex=2, rolled=15, answers=[50, 2])
        self.assertEqual(head, 10)
        twin = v.records + 9 * STRIDE
        v.p.set_reg("ebp", first)
        v.p.set_reg("esi", twin)
        v.p.run(0x43C9C1, 0x43C9E5)
        self.assertEqual(v.p.u32(twin + 0x360), 10)
        self.assertEqual(v.p.u32(twin + 0x350), 2)

    def test_all_or_nothing(self):
        exe = bytearray(stock_exe())
        pe = __import__("pefile").PE(data=bytes(exe))
        base = pe.OPTIONAL_HEADER.ImageBase
        for va in (0x43C616, 0x43C632, 0x43C64B, 0x402F14):
            changed = bytearray(exe)
            off = pe.get_offset_from_rva(va - base)
            changed[off] ^= 0xFF
            v = Village(exe=bytes(changed))
            with self.subTest(va=hex(va)):
                self.assertEqual(v.p.export("VvfpGeneticsInstalled"), 0)
                self.assertEqual(v.p.read(SITE, 6), bytes(changed[off - (va - SITE):off - (va - SITE) + 6]) if SITE <= va < SITE + 6 else bytes.fromhex("898660030000"))
        # Another companion's rand target, and Fix Vanilla Bugs' name bound, still install.
        changed = bytearray(exe)
        changed[pe.get_offset_from_rva(0x43C646 - base)] = 0x65
        changed[pe.get_offset_from_rva(0x43C63A - base)] ^= 0x10
        self.assertEqual(Village(exe=bytes(changed)).p.export("VvfpGeneticsInstalled"), 1)


if __name__ == "__main__":
    unittest.main()
