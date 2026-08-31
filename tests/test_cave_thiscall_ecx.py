"""No patch cave may call a stock __thiscall function without loading ECX.

This is the VV5 Barrel of Babies crash generalised. `0x472BD0` is a member
function; it never loads ECX itself and forwards its own `this` to `0x4713F0`,
which dereferences it. All twelve stock call sites load ECX first. The barrel
cave did not, so buying Barrel of Babies access-violated.

The rule is derived from each stock binary rather than from a hand-kept list of
"functions that need ECX": for every `call 0x...` written in a generator, the
stock executable is asked how its own callers behave. A function whose stock
call sites essentially all load ECX first is a member function, and our cave
must load it too.

Auditing the AUTHORED assembly is deliberate. The first version of this check
scanned the rendered executable instead and reported a clean tree while the
known VV5 bug was still in it -- the cave lives in a page applied by the append
step, which `render_patched_bytes` does not perform, so there was no cave in the
image being scanned.
"""
from __future__ import annotations

import re
import struct
import unittest
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

ROOT = Path(__file__).resolve().parents[1]
STOCK_DIR = ROOT / "research" / "stock-executables"

GAMES = {
    "vv1": "Virtual Villagers - A New Home.exe",
    "vv2": "Virtual Villagers - The Lost Children.exe",
    "vv3": "Virtual Villagers - The Secret City.exe",
    "vv4": "Virtual Villagers - The Tree of Life.exe",
    "vv5": "Virtual Villagers - New Believers.exe",
}

# A function is treated as __thiscall when at least this share of its stock
# callers load ECX immediately before the call, over at least MIN_SITES sites.
THISCALL_RATIO = 0.9
MIN_SITES = 4

CALL = re.compile(r"^\s*call\s+0x([0-9A-Fa-f]{6,8})\s*$")
SETS_ECX = re.compile(
    r"^\s*(mov|lea|xor|pop|movzx|movsx|add|sub|or|and)\s+ecx\b", re.I
)
LABEL = re.compile(r"^\s*[A-Za-z_][A-Za-z0-9_]*:\s*$")

_md = Cs(CS_ARCH_X86, CS_MODE_32)
_md.detail = True


def _text_section(image: bytes):
    pe = struct.unpack_from("<I", image, 0x3C)[0]
    count = struct.unpack_from("<H", image, pe + 6)[0]
    opt = struct.unpack_from("<H", image, pe + 20)[0]
    base = struct.unpack_from("<I", image, pe + 24 + 28)[0]
    for i in range(count):
        off = pe + 24 + opt + i * 40
        if image[off : off + 8].rstrip(b"\0") == b".text":
            vsize, va, rsize, ptr = struct.unpack_from("<IIII", image, off + 8)
            return base + va, vsize, ptr, rsize
    raise AssertionError("no .text section")


def _writes_ecx(code: bytes, addr: int) -> bool:
    """Does the single instruction ending at `addr` write ECX?"""
    for size in range(1, 9):
        chunk = code[len(code) - size :]
        decoded = list(_md.disasm(chunk, addr - size))
        if len(decoded) == 1 and decoded[0].size == size:
            written = decoded[0].regs_access()[1]
            return "ecx" in {decoded[0].reg_name(r) for r in written}
    return False


class _Binary:
    def __init__(self, path: Path) -> None:
        self.image = path.read_bytes()
        self.tva, self.tvsize, self.tptr, self.trsize = _text_section(self.image)
        self._cache: dict[int, tuple] = {}

    def in_text(self, va: int) -> bool:
        return self.tva <= va < self.tva + self.tvsize

    def thiscall(self, target: int):
        """(ratio, sites, setters) for a stock function, or (None, n, 0)."""
        if target in self._cache:
            return self._cache[target]
        sites = []
        for i in range(self.trsize - 5):
            if self.image[self.tptr + i] != 0xE8:
                continue
            rel = struct.unpack_from("<i", self.image, self.tptr + i + 1)[0]
            va = self.tva + i
            if va + 5 + rel == target:
                sites.append((self.tptr + i, va))
        if len(sites) < MIN_SITES:
            self._cache[target] = (None, len(sites), 0)
        else:
            setters = sum(
                1 for off, va in sites if _writes_ecx(self.image[off - 8 : off], va)
            )
            self._cache[target] = (setters / len(sites), len(sites), setters)
        return self._cache[target]


def _cave_sets_ecx(lines: list[str], index: int) -> bool:
    """Walk back over authored assembly for an ECX write before the call.

    Stops at a label: control flow could reach the call from somewhere else, so
    an ECX write above a label proves nothing.
    """
    for back in range(1, 12):
        if index - back < 0:
            return False
        previous = lines[index - back]
        if LABEL.match(previous):
            return False
        if SETS_ECX.match(previous):
            return True
    return False


def _audit(game: str, binary: _Binary):
    findings, examined = [], 0
    for script in sorted((ROOT / "scripts").glob(f"build_{game}_*.py")):
        lines = script.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            match = CALL.match(line)
            if not match:
                continue
            target = int(match.group(1), 16)
            if not binary.in_text(target):
                continue
            ratio, sites, setters = binary.thiscall(target)
            if ratio is None or ratio < THISCALL_RATIO:
                continue
            examined += 1
            if not _cave_sets_ecx(lines, index):
                findings.append((script.name, index + 1, target, sites, setters))
    return findings, examined


@unittest.skipUnless(STOCK_DIR.is_dir(), "stock executables are not present")
class CaveThiscallTests(unittest.TestCase):
    def test_no_cave_calls_a_member_function_without_ecx(self) -> None:
        total_examined = 0
        for game, exe_name in GAMES.items():
            exe = STOCK_DIR / exe_name
            if not exe.is_file():
                self.skipTest(f"{exe_name} is not present")
            findings, examined = _audit(game, _Binary(exe))
            total_examined += examined
            with self.subTest(game=game):
                self.assertEqual(
                    findings,
                    [],
                    "\n".join(
                        f"{name}:{line} calls 0x{target:X} without loading ECX, "
                        f"but {setters} of {sites} stock callers load it first"
                        for name, line, target, sites, setters in findings
                    ),
                )
        # Without this the whole test would pass if the call regex stopped
        # matching, or if every target were classified as not-thiscall.
        self.assertGreater(
            total_examined,
            20,
            "the audit inspected almost nothing; the scan is probably broken "
            "rather than the caves being clean",
        )

    def test_the_known_barrel_gate_is_recognised_as_a_member_function(self) -> None:
        """Positive control for the classifier itself."""
        exe = STOCK_DIR / GAMES["vv5"]
        if not exe.is_file():
            self.skipTest("stock VV5 is not present")
        ratio, sites, setters = _Binary(exe).thiscall(0x472BD0)
        self.assertIsNotNone(ratio, "0x472BD0 should have plenty of stock callers")
        self.assertGreaterEqual(sites, 10)
        self.assertEqual(
            setters,
            sites,
            "every stock caller of the barrel capacity gate loads ECX",
        )

    def test_a_missing_ecx_load_is_actually_detected(self) -> None:
        """Positive control for the walk-back, so a clean run means something."""
        lines = ["    push ebx", "    call 0x472BD0"]
        self.assertFalse(_cave_sets_ecx(lines, 1))
        lines = ["    mov ecx, 0x554148", "    call 0x472BD0"]
        self.assertTrue(_cave_sets_ecx(lines, 1))
        # An ECX write on the far side of a label must not count.
        lines = ["    mov ecx, 0x554148", "target:", "    call 0x472BD0"]
        self.assertFalse(_cave_sets_ecx(lines, 2))


if __name__ == "__main__":
    unittest.main()
