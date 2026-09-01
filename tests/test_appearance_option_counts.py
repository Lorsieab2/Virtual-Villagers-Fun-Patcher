"""Every game's appearance chooser must offer all the options that game has.

The counts are not a shared constant and must not be "harmonised": each game
hands out its own range at villager creation, and the choosers have to match
whichever range their game actually uses.

  * VV2 creates bodies with `rand(30)` -> 30 options
  * VV3 creates bodies with `rand(30)` -> 30 options
  * VV4 creates bodies with `rand(29)` -> 29 options
  * VV5 creates bodies with `rand(29)` -> 29 options

VV3 shipped 29 and so could never reach body 29, an index its own creation code
assigns. It was tempting to read VV4/VV5's 29 as the "right" number and leave
VV3 alone; the stock binaries say otherwise, which is why this test derives the
range from each executable instead of restating a number here.

Head counts come from the atlases -- `male_heads`/`female_heads` are 1950px tall
in 65px rows, i.e. 30 -- and VV1 is the exception on both axes, using per-sex
RNG ranges of 19 (male) and 20 (female).
"""
from __future__ import annotations

import re
import struct
import unittest
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables"

# game -> (exe, body record offset, source file, count macro)
GAMES = {
    "vv2": (
        "Virtual Villagers - The Lost Children.exe", 0x54C,
        "native/vv2_origins_icons/vv2_origins_icons.c", "VV2_APPEARANCE_COUNT",
    ),
    "vv3": (
        "Virtual Villagers - The Secret City.exe", 0xDF4,
        "native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c", "VV3_BODY_COUNT",
    ),
    "vv4": (
        "Virtual Villagers - The Tree of Life.exe", 0x1BBC,
        "native/vv4_origins_icons/vv4_origins_icons.c", "VV_BODY_COUNT",
    ),
    "vv5": (
        "Virtual Villagers - New Believers.exe", 0x1BBC,
        "native/vv5_task9_origins/vv5_task9_origins.c", "APPEARANCE_BODY_COUNT",
    ),
}

# What each game's creation code actually rolls. Asserted against the binary
# below, so a wrong entry here fails rather than silently defining the answer.
EXPECTED_CREATION_RANGE = {"vv2": 30, "vv3": 30, "vv4": 29, "vv5": 29}


def _text(image: bytes):
    pe = struct.unpack_from("<I", image, 0x3C)[0]
    count = struct.unpack_from("<H", image, pe + 6)[0]
    opt = struct.unpack_from("<H", image, pe + 20)[0]
    base = struct.unpack_from("<I", image, pe + 24 + 28)[0]
    for i in range(count):
        off = pe + 24 + opt + i * 40
        if image[off : off + 8].rstrip(b"\0") == b".text":
            vsize, va, rsize, ptr = struct.unpack_from("<IIII", image, off + 8)
            return base + va, ptr, rsize
    raise AssertionError("no .text")


def _creation_ranges(image: bytes, body_offset: int) -> set[int]:
    """Immediates pushed to the RNG just before a store into the body field."""
    text_va, ptr, size = _text(image)
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    needle = struct.pack("<I", body_offset)
    found: set[int] = set()
    position = ptr - 1
    while True:
        position = image.find(needle, position + 1, ptr + size)
        if position < 0:
            return found
        # Walk back to a real instruction boundary for the store itself.
        for back in range(2, 9):
            start = position - back
            decoded = list(md.disasm(image[start : start + 12], text_va + (start - ptr)))
            if not decoded:
                continue
            first = decoded[0]
            if f"0x{body_offset:x}]" not in first.op_str or first.size < back + 4:
                continue
            if not (first.mnemonic == "mov" and first.op_str.endswith(", eax")):
                break  # a read, not the creation store
            # The RNG bound is the last `push imm8` in the preceding window.
            window_start = max(ptr, start - 48)
            pushes = [
                ins for ins in md.disasm(
                    image[window_start:start], text_va + (window_start - ptr))
                if ins.mnemonic == "push" and ins.op_str.startswith("0x")
            ]
            if pushes:
                try:
                    found.add(int(pushes[-1].op_str, 16))
                except ValueError:
                    pass
            break


class AppearanceOptionCountTests(unittest.TestCase):
    def _declared(self, source: str, macro: str) -> int:
        text = (ROOT / source).read_text(encoding="utf-8")
        match = re.search(rf"^#define {re.escape(macro)} (\d+)$", text, re.M)
        self.assertIsNotNone(match, f"{macro} not found in {source}")
        return int(match.group(1))

    def test_the_binaries_roll_the_ranges_this_file_claims(self) -> None:
        """Anti-vacuity: the expected table is checked against the exes."""
        for game, (exe_name, body_offset, _src, _macro) in GAMES.items():
            exe = STOCK / exe_name
            if not exe.is_file():
                self.skipTest(f"{exe_name} is not present")
            with self.subTest(game=game):
                ranges = _creation_ranges(exe.read_bytes(), body_offset)
                self.assertIn(
                    EXPECTED_CREATION_RANGE[game], ranges,
                    f"{game} creation does not roll "
                    f"rand({EXPECTED_CREATION_RANGE[game]}) into its body field; "
                    f"observed pushes: {sorted(ranges)}",
                )

    def test_each_chooser_offers_its_own_game_s_full_body_range(self) -> None:
        """Reads only committed sources, so it runs in a clean checkout.

        This used to skip on the first absent stock executable, which aborted
        the whole method and left the advertised cross-game guard checking
        nothing wherever those untracked fixtures are missing. The binaries are
        needed to VERIFY the expected ranges, which is a separate test.
        """
        for game, (_exe_name, _off, source, macro) in GAMES.items():
            with self.subTest(game=game):
                self.assertEqual(
                    self._declared(source, macro),
                    EXPECTED_CREATION_RANGE[game],
                    f"{game}'s chooser offers a different number of bodies than "
                    f"the game itself assigns, so some villagers wear an "
                    f"appearance the player cannot select",
                )

    def test_vv3_is_not_harmonised_with_vv4_and_vv5(self) -> None:
        """The specific mistake this guards: making the three 'consistent'."""
        vv3 = self._declared(*GAMES["vv3"][2:])
        vv4 = self._declared(*GAMES["vv4"][2:])
        self.assertEqual(vv3, 30)
        self.assertEqual(vv4, 29)
        self.assertNotEqual(
            vv3, vv4,
            "VV3 and VV4 genuinely differ -- rand(30) against rand(29) -- so "
            "equalising them breaks one of the two",
        )


if __name__ == "__main__":
    unittest.main()
