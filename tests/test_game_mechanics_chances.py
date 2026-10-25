"""Game Mechanics' Chances groups (src/vv_game_mechanics_chances.py and each game's table,
src/vv_game_mechanics_chances_vv<N>.py): every roll's constants are the stock exe's, and the game's own code gives the
chance shown.

For every Check of every game:
  * the instruction at its address is a call of that game's rand(n); the n pushed for it is the one in the table;
  * the compare that reads the result and the jump after it are the ones in the table;
  * the call, its compare and its jump are run in the stock exe's own code (unicorn), with the C library rand()
    replaced by each value in turn: a sample of values for every check, and all 32,768 for one check of each game, and
    the outcome comes out exactly as the table's count says.
The game's rand(n) itself is run for every value of rand() for several n, which proves the 32,768-value rule.
"""
from __future__ import annotations

import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_chances as ch  # noqa: E402

STOCK = ROOT / "research" / "stock-executables"
EXES = {1: "Virtual Villagers - A New Home.exe", 2: "Virtual Villagers - The Lost Children.exe",
        3: "Virtual Villagers - The Secret City.exe", 4: "Virtual Villagers - The Tree of Life.exe",
        5: "Virtual Villagers - New Believers.exe"}
try:
    import capstone
    import pefile
    import unicorn
    from unicorn import x86_const as X
    HAVE_DEPS = True
except ImportError:  # pragma: no cover
    HAVE_DEPS = False

CELL = 0x00F00000            # the value the replaced rand() returns
STACK = 0x00E00000
SCRATCH = 0x00100000         # every register points here; reads and writes land in mapped zeros
JUMPS = {"jl", "jle", "jg", "jge", "jb", "jbe", "ja", "jae", "je", "jne"}


def _image(game: int):
    pe = pefile.PE(str(STOCK / EXES[game]))
    return pe.OPTIONAL_HEADER.ImageBase, pe.get_memory_mapped_image()


class _Exe:
    def __init__(self, game: int):
        self.game = game
        self.base, self.mem = _image(game)
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        self.md.detail = True
        self._uc = None

    def at(self, va: int, count: int):
        out = []
        for insn in self.md.disasm(self.mem[va - self.base: va - self.base + 16 * count], va):
            out.append(insn)
            if len(out) >= count:
                break
        return out

    def before(self, va: int, count: int = 6):
        """The `count` instructions that end exactly at `va` (decoding from each start in turn until one lands)."""
        for start in range(va - 48, va):
            insns = []
            for insn in self.md.disasm(self.mem[start - self.base: va - self.base], start):
                insns.append(insn)
            if insns and insns[-1].address + insns[-1].size == va and len(insns) >= count:
                return insns[-count:]
        return []

    def emulator(self):
        if self._uc is None:
            uc = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
            size = (len(self.mem) + 0xFFF) & ~0xFFF
            uc.mem_map(self.base, size)
            uc.mem_write(self.base, bytes(self.mem))
            uc.mem_map(0, 0x00400000)                     # below the image: the registers' scratch
            uc.mem_map(STACK - 0x10000, 0x20000)
            uc.mem_map(CELL, 0x1000)
            # rand() becomes "mov eax, [CELL]; ret"
            uc.mem_write(ch.RAW_RAND[self.game], b"\xA1" + struct.pack("<I", CELL) + b"\xC3")

            def unmapped(uc_, access, address, size_, value, data):
                uc_.mem_map(address & ~0xFFF, 0x1000)
                return True
            uc.hook_add(unicorn.UC_HOOK_MEM_UNMAPPED, unmapped)
            self._uc = uc
        return self._uc

    def branch(self, check: ch.Check, value: int, jump_at: int, target: int) -> bool:
        """Run the call and its compare in the game's code with rand() = value; True when the jump is taken."""
        uc = self.emulator()
        uc.mem_write(CELL, struct.pack("<I", value))
        for reg in (X.UC_X86_REG_EAX, X.UC_X86_REG_EBX, X.UC_X86_REG_ECX, X.UC_X86_REG_EDX, X.UC_X86_REG_ESI,
                    X.UC_X86_REG_EDI, X.UC_X86_REG_EBP):
            uc.reg_write(reg, SCRATCH)
        esp = STACK - 0x100
        uc.mem_write(esp, struct.pack("<I", check.n))
        uc.reg_write(X.UC_X86_REG_ESP, esp)
        uc.emu_start(check.site, jump_at, count=200)
        uc.emu_start(jump_at, 0, count=1)
        return uc.reg_read(X.UC_X86_REG_EIP) == target

    def rng(self, n: int, value: int) -> int:
        uc = self.emulator()
        uc.mem_write(CELL, struct.pack("<I", value))
        esp = STACK - 0x100
        stop = STACK - 0x80
        uc.mem_write(esp, struct.pack("<II", stop, n))
        uc.reg_write(X.UC_X86_REG_ESP, esp)
        uc.emu_start(ch.RNG[self.game], stop, count=100)
        return uc.reg_read(X.UC_X86_REG_EAX)


def _compare(exe: _Exe, site: int):
    """(the compare's constant or None for a register, the jump, its address, its target) after the call at site."""
    after = exe.at(site, 8)
    for k, insn in enumerate(after[1:], 1):
        if insn.mnemonic == "cmp" and insn.op_str.startswith("eax, "):
            nxt = after[k + 1]
            imm = insn.op_str.split(", ", 1)[1]
            value = int(imm, 16) if re.fullmatch(r"-?0x[0-9a-f]+|-?\d+", imm) else None
            if value is not None and value < 0:
                value &= 0xFFFFFFFF
            target = int(nxt.op_str, 16) if nxt.mnemonic in JUMPS else None
            return value, nxt.mnemonic, nxt.address, target
    return None, None, None, None


def _sample(check: ch.Check):
    """Values of rand() around every boundary of the compare, and a spread."""
    values = set(range(0, 32768, 1021))
    if check.cmp is not None and check.n:
        for base in (0, check.n, 7 * check.n, 32768 - 32768 % check.n - check.n):
            for d in (-2, -1, 0, 1, 2):
                v = base + check.cmp + d
                if 0 <= v < 32768:
                    values.add(v)
        values.update(range(min(check.n, 64)))
    return sorted(values)


@unittest.skipUnless(HAVE_DEPS and STOCK.is_dir() and all((STOCK / e).is_file() for e in EXES.values()),
                     "requires the stock executables and capstone/unicorn/pefile")
class ChancesMatchTheExe(unittest.TestCase):
    exes: dict[int, _Exe] = {}

    def exe(self, game: int) -> _Exe:
        if game not in self.exes:
            self.exes[game] = _Exe(game)
        return self.exes[game]

    def test_rng_is_rand_mod_n(self) -> None:
        """Each game's rand(n) is rand() % n: run in the game's code for every rand() value at several n."""
        for game in range(1, 6):
            exe = self.exe(game)
            first = exe.at(ch.RNG[game], 12)
            self.assertIn(f"call {hex(ch.RAW_RAND[game])}", [f"{i.mnemonic} {i.op_str}" for i in first], game)
            for n in (2, 100, 120, 300, 6000):
                with self.subTest(game=game, n=n):
                    for v in list(range(0, 32768, 97)) + [32767, n - 1, n, 2 * n - 1]:
                        self.assertEqual(exe.rng(n, v), v % n)

    def test_every_check_is_in_the_exe(self) -> None:
        for game in range(1, 6):
            exe = self.exe(game)
            for roll in ch.rolls(game):
                for check in roll.checks:
                    with self.subTest(game=game, site=hex(check.site), roll=roll.text[:50]):
                        call = exe.at(check.site, 1)[0]
                        self.assertEqual(call.mnemonic, "call")
                        self.assertIn(int(call.op_str, 16), (ch.RNG[game], ch.RAW_RAND[game]))
                        if check.n is not None and check.push is not None:
                            push = exe.at(check.push, 1)[0]
                            self.assertEqual(f"{push.mnemonic} {push.op_str}",
                                             f"push {hex(check.n) if check.n > 9 else check.n}")
                        elif check.n is not None:
                            pushes = [i for i in exe.before(check.site, 6) if i.mnemonic == "push"]
                            self.assertTrue(pushes, "no push before the call")
                            self.assertEqual(pushes[-1].op_str, hex(check.n) if check.n > 9 else str(check.n))
                        if check.jump is not None:
                            value, jump, _at, _target = _compare(exe, check.site)
                            self.assertEqual(jump, check.jump)
                            self.assertEqual(value, check.cmp)

    def test_the_games_code_gives_the_chance_shown(self) -> None:
        for game in range(1, 6):
            exe = self.exe(game)
            full_done = False
            for roll in ch.rolls(game):
                for check in roll.checks:
                    if check.count is None:
                        continue
                    _value, _jump, at, target = _compare(exe, check.site)
                    values = range(32768) if not full_done else _sample(check)
                    with self.subTest(game=game, site=hex(check.site)):
                        hits = 0
                        for v in values:
                            taken = exe.branch(check, v, at, target)
                            expected = ch._holds(v % check.n, ch._JUMPS[check.jump], check.cmp)
                            self.assertEqual(taken, expected, f"rand() = {v}")
                            hits += taken == check.take
                        if not full_done:
                            self.assertEqual(hits, check.count)
                            full_done = True


class ChancesWords(unittest.TestCase):
    def test_exact_words(self) -> None:
        self.assertEqual(ch.chance(16400), "50.05%")
        self.assertEqual(ch.chance(56), "0.171% (1 in 585)")
        self.assertEqual(ch.chance(32768), "100%")
        self.assertEqual(ch.below(100, 50), 16400)
        self.assertEqual(ch.Check(0, 6000, 2, "jle").count, 18)

    def test_every_game_has_rolls_and_no_bare_units(self) -> None:
        """The owner (2026-10-24): every time says real-life or per age unit; no vague words."""
        for game in range(1, 6):
            rolls = ch.rolls(game)
            with self.subTest(game=game):
                self.assertTrue(rolls)
                self.assertTrue(any(r.group == ch.BIRTHS for r in rolls))
                for roll in rolls:
                    for text in (roll.text,) + roll.subs + ((roll.patched,) if roll.feature else ()):
                        words = roll.words(text)
                        self.assertNotRegex(words, r"(^|[ (])\?([ .,;)]|$)", words)   # a chance worked out at run time
                        self.assertNotIn("{", words)
                        self.assertNotRegex(words.lower(), r"not (yet )?worked out|some effect|\betc\b|probabl|"
                                                           r"(?<!equally )likely|perhaps|relic")
                        if text != roll.patched:      # the Golden Mushroom is named only with its patch in the game
                            self.assertNotRegex(words.lower(), r"secret|golden mushroom|1,000,000")
                        # Every length of time says real-life time or the game's own clock (the owner, 2026-10-24).
                        for m in re.finditer(r"\b\d[\d,.]* (seconds?|minutes?|hours?)\b", words):
                            self.assertRegex(words[max(0, m.start() - 40):m.end() + 40],
                                             r"real-life|in-game|of play", words)
                    if roll.feature:
                        self.assertNotEqual(gm.feature_name(roll.feature), roll.feature, roll.feature)
                        self.assertTrue(roll.patched)

    def test_patch_words_only_with_the_patch(self) -> None:
        for game in range(1, 6):
            for roll in ch.rolls(game):
                if not roll.feature:
                    continue
                with self.subTest(game=game, feature=roll.feature):
                    off = gm.Village(Path("."), game, 1, Path("x"), b"", frozenset(), 0.0)
                    on = gm.Village(Path("."), game, 1, Path("x"), b"", frozenset({roll.feature}), 0.0)
                    name = gm.feature_name(roll.feature)
                    self.assertFalse(any(name in f.text for f in ch.facts(off)))
                    self.assertTrue(any(f.text.startswith(f"With the patcher's \"{name}\" (in this game): ")
                                        for f in ch.facts(on)))


if __name__ == "__main__":
    unittest.main()
