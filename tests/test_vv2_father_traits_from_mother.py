"""VV2 alone recovers the father's head and body from the mother's record.

Every other game finds the father by scanning for his name, and that scan can
legitimately fail: he can die between conception and delivery, and two living
villagers can share a name, in which case the scan refuses to guess. VV2 does
not depend on it for two of the three numbers, because the game copies the
father's head and body onto the MOTHER at conception, by value.

The evidence is in the stock executable, and this test reads it there rather
than trusting the comment in the C file. In sub_44B980 the mother is in esi and
the routine stores its stack arguments onto her::

    0044BA24  mov [esi + 0x5DC], eax     ; eax <- [esp + 0x24]
    0044BA43  mov [esi + 0x5E0], ecx     ; ecx <- [esp + 0x20]

and the caller at 0x421FE7 pushes the father's own fields into those slots::

    00421FE7  mov edx, [eax + 0x54C]     ; father body
    00421FEE  mov edx, [eax + 0x548]     ; father head
    00421FF5  lea edx, [eax + 0x564]     ; father name

Since +0x548 is head and +0x54C is body on a VV2 villager -- the same offsets
the descriptor already uses for the mother -- mother+0x5E0 holds the father's
head and mother+0x5DC holds his body.

Two traps this test exists to hold shut:

  * +0x5E4 sits between them and looks like a third trait. It is written from a
    hardcoded 1 at 0x44BA10, so it is a pregnancy flag; reading it as an age
    would print 1 for every father who ever lived. The father's age is NOT
    copied by any game, which is why only two fields are recovered here.
  * the descriptor is a POSITIONAL initialiser. Adding a field without adding a
    value to all five games shifts every later value up a slot, and the
    compiler does not warn. So this checks all five, not just VV2.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "native" / "parentage_export" / "parentage_export.c"
STOCK = ROOT / "research" / "stock-executables"
VV2_EXE = STOCK / "Virtual Villagers - The Lost Children.exe"

VV2_FATHER_HEAD_COPY = 0x5E0
VV2_FATHER_BODY_COPY = 0x5DC

# The whole chain, register-exact, as encoded bytes in the stock executable.
#
# Checking only the store's destination offset would be too weak: it would pass
# just as happily if some unrelated value were written to mother+0x5DC. What
# makes these the FATHER's numbers is where the stored register was loaded from,
# so each link is pinned end to end.
#
# The register pairing is visible in the ModRM byte and is not interchangeable:
# 0x8986 is `mov [esi+disp32], eax` and 0x898E is `mov [esi+disp32], ecx`, so a
# mixed-up pair would fail here rather than silently swap head for body.
VV2_CHAIN = (
    # (address, expected bytes, what this link establishes)
    (
        0x0044BA16,
        "8B442424",
        "callee loads eax from [esp+0x24], the caller's last-but-one push",
    ),
    (
        0x0044BA24,
        "8986DC050000",
        "callee stores eax to mother+0x5DC -- the father's BODY",
    ),
    (
        0x0044BA30,
        "8B4C2420",
        "callee loads ecx from [esp+0x20]",
    ),
    (
        0x0044BA43,
        "898EE0050000",
        "callee stores ecx to mother+0x5E0 -- the father's HEAD",
    ),
    (
        0x00421FE7,
        "8B904C050000",
        "caller reads [father+0x54C], body, and pushes it into [esp+0x24]",
    ),
    (
        0x00421FEE,
        "8B9048050000",
        "caller reads [father+0x548], head, and pushes it into [esp+0x20]",
    ),
    (
        0x00421FF5,
        "8D9064050000",
        "caller takes [father+0x564], his name, proving the base is the father",
    ),
)

VV2_LOG_NAME = "Virtual Villagers 2 Parentage Log"

# The copy pair is the line after the FATHER_* line and before no_villager.
COPY_PAIR = (
    r"FATHER_(?:BY_NAME|BY_ID|NOT_RECORDED),[^\n]*\n\s*"
    r"(0x[0-9A-Fa-f]+|0),\s*(0x[0-9A-Fa-f]+|0),"
)


def _descriptor_rows() -> list[tuple[str, str]]:
    """Each game's descriptor body, keyed by the log name that ends it."""
    text = SOURCE.read_text(encoding="utf-8")
    pattern = r"\{(.*?)L\"(Virtual Villagers \d+ Parentage Log)\""
    return [(m.group(2), m.group(1)) for m in re.finditer(pattern, text, re.S)]


class VV2FatherTraitsAreCopiedOntoTheMotherTests(unittest.TestCase):
    def test_every_game_supplies_both_copy_fields(self) -> None:
        """A positional initialiser must not be short for any game."""
        rows = _descriptor_rows()
        self.assertEqual(len(rows), 5, "expected one descriptor per game")
        for name, row in rows:
            with self.subTest(game=name):
                self.assertRegex(
                    row,
                    COPY_PAIR,
                    f"{name} is missing the father_head_copy/father_body_copy pair",
                )

    def test_only_vv2_claims_to_copy_anything(self) -> None:
        for name, row in _descriptor_rows():
            with self.subTest(game=name):
                pair = re.search(COPY_PAIR, row)
                self.assertIsNotNone(pair, f"{name} has no copy pair")
                head, body = (int(value, 0) for value in pair.groups())
                if name == VV2_LOG_NAME:
                    self.assertEqual(head, VV2_FATHER_HEAD_COPY)
                    self.assertEqual(body, VV2_FATHER_BODY_COPY)
                else:
                    self.assertEqual(
                        (head, body),
                        (0, 0),
                        f"{name} claims copied traits it has not been shown to have",
                    )

    def test_the_values_really_come_from_the_father(self) -> None:
        """The whole chain must be what the stock executable actually encodes.

        Without this the suite would only prove the C file agrees with itself.
        Checking the store alone would be nearly as weak: it would pass if some
        unrelated value were written to the offsets the descriptor names, which
        is exactly how a log ends up carrying plausible but wrong parentage. So
        every link is pinned -- the caller's read off the father, the push, the
        callee's load, and the store -- with the registers named by their ModRM
        bytes rather than merely implied.
        """
        if not VV2_EXE.is_file():
            self.skipTest(f"stock executable not available: {VV2_EXE.name}")

        import pefile

        pe = pefile.PE(str(VV2_EXE))
        image = VV2_EXE.read_bytes()
        base = pe.OPTIONAL_HEADER.ImageBase
        sections = [
            (s.VirtualAddress + base, s.Misc_VirtualSize, s.PointerToRawData)
            for s in pe.sections
        ]

        def read(va: int, count: int) -> bytes:
            for start, size, raw in sections:
                if start <= va < start + size:
                    offset = raw + (va - start)
                    return image[offset : offset + count]
            raise AssertionError(f"VA {va:#x} is not in any section")

        for va, expected, establishes in VV2_CHAIN:
            with self.subTest(address=f"{va:#x}"):
                wanted = bytes.fromhex(expected)
                found = read(va, len(wanted))
                self.assertEqual(
                    found.hex().upper(),
                    wanted.hex().upper(),
                    f"at {va:#x} the game no longer {establishes}",
                )

    def test_the_flag_between_them_is_not_read_as_a_trait(self) -> None:
        """+0x5E4 is written from a constant, so it carries no father data."""
        source = SOURCE.read_text(encoding="utf-8")
        offsets = re.findall(r"0x5E0, 0x5DC|0x5E4,", source)
        self.assertNotIn(
            "0x5E4,",
            offsets,
            "0x5E4 is a pregnancy flag set to a hardcoded 1, not an inherited trait",
        )


if __name__ == "__main__":
    unittest.main()
