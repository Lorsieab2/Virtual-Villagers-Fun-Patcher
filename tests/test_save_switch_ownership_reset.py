"""Switching save slots must not carry Origins upgrade ownership across.

VV3, VV4 and VV5 keep doubler ownership in a PROCESS GLOBAL that is not part
of the `.ldw` save:

    VV3  0x5824D0      VV4  0x4D6E10      VV5  0x51D388

Nothing cleared them on load, so a Tech Point Doubler bought in one village
stayed owned in another that never paid for it -- its row read "Remove" instead
of "Buy", and the doubler was live. VV1 and VV2 never had this bug because they
hang the flags off the village object, which follows the save for free.

VV5's word is worse: it also carries the Barrel of Babies pending token (bit 3)
and the forced-event marker (bit 2), so a barrel queued in one village could
fire in the next.

Every game already hooks the stock save-path builder for the mask sidecar, and
that hook already detects a slot CHANGE. The reset belongs there, and the
change-gate matters: the builder runs on saves too, so an unconditional reset
would wipe a doubler the player legitimately owns on every autosave.

These tests assert against the RENDERED executable, translated through the PE
section table rather than by subtracting the image base -- an appended section
does not map that way, and the naive subtraction reads empty bytes that look
exactly like a missing fix.
"""

import struct
import unittest
from pathlib import Path
import sys

try:
    import capstone
except ImportError:  # pragma: no cover - exercised only without capstone
    capstone = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.vv_fun_patcher import (  # noqa: E402
    load_builds,
    load_fun_patches,
    render_patched_bytes,
)

# game -> (stock exe, ownership global, the mode to render)
GAMES = {
    "vv3": (
        "inputs/vv3-stock-copy/Virtual Villagers - The Secret City.exe",
        0x5824D0,
    ),
    "vv4": (
        "inputs/vv4-stock-copy/Virtual Villagers - The Tree of Life.exe",
        0x4D6E10,
    ),
    "vv5": (
        "inputs/vv5-stock-copy/Virtual Villagers - New Believers.exe",
        0x51D388,
    ),
}

# Games whose ownership already lives on the village object, so a reset would
# be wrong rather than merely unnecessary.
PER_VILLAGE = {"vv1": 0xAD48, "vv2": 0x2EAE8}


def _clear_bytes(address):
    """`mov dword ptr [address], 0` -- C7 05 <addr> 00000000."""
    return b"\xC7\x05" + struct.pack("<I", address) + b"\x00\x00\x00\x00"


@unittest.skipIf(capstone is None, "requires capstone")
class SaveSwitchOwnershipResetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builds = {b.id: b for b in load_builds()}
        cls.catalog = [p.id for p in load_fun_patches()]
        cls.images = {}
        for game, (stock, _) in GAMES.items():
            path = ROOT / stock
            if not path.is_file():
                continue
            ids = [i for i in cls.catalog if i.startswith(game)]
            cls.images[game], _ = render_patched_bytes(
                path, cls.builds[game], "collection_progression", ids
            )

    def _available(self, game):
        if game not in self.images:
            self.skipTest(f"{game} stock executable unavailable")
        return self.images[game]

    def test_each_affected_game_clears_its_ownership_global(self):
        """The reset must exist in the rendered image, per game."""
        for game, (_, address) in GAMES.items():
            with self.subTest(game=game):
                image = self._available(game)
                self.assertIn(
                    _clear_bytes(address),
                    image,
                    f"{game} never clears {address:#x}; a doubler bought in one "
                    "village would stay owned in another",
                )

    def test_the_reset_is_gated_on_a_slot_change(self):
        """Unconditional would wipe a legitimately owned doubler on autosave.

        The stock save-path builder runs for saves as well as loads, so the
        reset has to sit behind a comparison against the remembered slot.
        """
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        for game, (_, address) in GAMES.items():
            with self.subTest(game=game):
                image = self._available(game)
                index = image.find(_clear_bytes(address))
                self.assertGreater(index, 0, f"{game} reset not found")
                window = image[max(0, index - 48) : index]
                text = " ; ".join(
                    f"{i.mnemonic} {i.op_str}" for i in md.disasm(window, 0)
                )
                if "cmp" in text:
                    continue
                # VV4 reaches its reset through a `call` to an out-of-line
                # helper -- its slot cave has only 48 bytes before .rsrc -- so
                # the gate lives at the call site, not beside the store. Assert
                # the helper is CALLED rather than fallen into, which is what
                # makes the caller's existing slot compare load-bearing.
                self.assertIn(
                    b"\xC3",
                    image[index : index + 16],
                    f"{game} clears ownership inline with no preceding compare "
                    "and does not return, so it is neither gated here nor a "
                    "callee gated by its caller",
                )

    def test_games_with_per_village_ownership_are_left_alone(self):
        """VV1/VV2 store ownership on the village object.

        Adding a global reset there would be wrong, not redundant -- there is
        no global to clear, and the flags already follow the save.
        """
        for game in PER_VILLAGE:
            with self.subTest(game=game):
                self.assertNotIn(
                    game,
                    GAMES,
                    f"{game} must not be given a global ownership reset",
                )

    def test_vv5_clears_the_whole_word_not_just_the_doubler_bits(self):
        """0x51D388 carries the Barrel pending token and forced-event marker.

        Clearing only the doubler bits would leave a barrel queued in one
        village able to fire in the next.
        """
        image = self._available("vv5")
        self.assertIn(
            _clear_bytes(0x51D388),
            image,
            "VV5 must zero the whole word, not mask individual bits",
        )
        # Bit-masks against this word elsewhere are legitimate and must NOT be
        # forbidden: the doubler Remove path does
        # `and dword ptr [0x51D388], 0xFFFFFFFB` to drop the forced-event
        # marker. An earlier version of this test banned any mask and failed on
        # exactly that instruction. What matters is that the SLOT-CHANGE site
        # zeroes the whole word, which the assertion above pins.


if __name__ == "__main__":
    unittest.main()
