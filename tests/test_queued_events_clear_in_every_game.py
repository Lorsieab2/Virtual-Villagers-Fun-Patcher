"""A queued event must not follow the player into another save, in ANY game.

Reported: "make sure all 5 games have protection against upgrades being
unavailable even when you switch save files and other related bugs".

Barrel of Babies and Island Event grey their row out while the event is
pending, and that pending state lives in the EXECUTABLE, not in the `.ldw`
save. So a Barrel bought in village A and not yet delivered followed the player
into village B: B's row read "Unavailable" for an event another save paid for,
and the armed event could be delivered into a village that never bought it.

VV1, VV2 and VV5 clear their queued-event state on a slot change. VV3 and VV4
did not -- their slot-change reset cleared the doubler-ownership word and
nothing else.

That gap is invisible to a whole-image search, which is the trap this file
exists to close: every one of these globals IS cleared somewhere in the image,
because the purchase and delivery paths clear them too. Only the reset block
itself answers the question, so each game is checked by decoding its own reset
and looking at what that block writes.

Everything here is read from the RENDERED executable and translated through the
PE section table -- an appended section does not map at `VA - 0x400000`, and
the naive subtraction reads empty bytes that look exactly like a missing fix.
"""

import struct
import sys
import unittest
from pathlib import Path

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

STOCK = {
    "vv1": "inputs/vv1-stock-copy/Virtual Villagers - A New Home.exe",
    "vv2": "inputs/vv2-stock-copy/Virtual Villagers - The Lost Children.exe",
    "vv3": "inputs/vv3-stock-copy/Virtual Villagers - The Secret City.exe",
    "vv4": "inputs/vv4-stock-copy/Virtual Villagers - The Tree of Life.exe",
}

# Where each game's slot-change reset begins, and the queued-event globals that
# block must clear. VV1/VV2 reach their reset through a detour that has to be
# followed; VV3 likewise; VV4's is an out-of-line helper at a fixed address.
#
# VV5 is deliberately absent: it keeps its queued-event bits in the same word as
# doubler ownership (0x51D388, bits 2 and 3) and zeroes the whole word, so it is
# covered by test_save_switch_ownership_reset.py rather than by a separate
# clear here. Asserting a separate store for VV5 would fail on correct code.
RESETS = {
    "vv1": {
        "detour_at": 0x402ED0,
        "globals": {
            0x48D700: "Barrel pending flag",
            0x48D704: "Barrel delay counter",
            0x48D708: "three-child one-shot",
        },
    },
    "vv2": {
        "detour_at": 0x403160,
        "globals": {
            0x49C700: "Barrel pending flag",
            0x49C704: "three-child one-shot",
            0x49C708: "Barrel cue counter",
        },
    },
    "vv3": {
        "detour_at": 0x403290,
        "globals": {
            0x4B3C75: "Barrel pending flag",
        },
    },
    "vv4": {
        "helper_at": 0x728E00,
        "globals": {
            0x728B00: "purchased-Barrel flag",
            0x728B04: "Barrel armed flag",
        },
    },
}

FEATURES = {
    game: [f"{game}_enable_origins_exclusive_features",
           f"{game}_origins_village_wide_upgrades"]
    for game in STOCK
}


def _sections(image):
    pe = struct.unpack_from("<I", image, 0x3C)[0]
    count = struct.unpack_from("<H", image, pe + 6)[0]
    optional = struct.unpack_from("<H", image, pe + 20)[0]
    base = struct.unpack_from("<I", image, pe + 52)[0]
    out = []
    for index in range(count):
        entry = pe + 24 + optional + index * 40
        out.append((
            base + struct.unpack_from("<I", image, entry + 12)[0],
            struct.unpack_from("<I", image, entry + 8)[0],
            struct.unpack_from("<I", image, entry + 20)[0],
            struct.unpack_from("<I", image, entry + 16)[0],
        ))
    return out


@unittest.skipIf(capstone is None, "requires capstone")
class QueuedEventsClearInEveryGameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builds = {b.id: b for b in load_builds()}
        cls.catalog = {p.id for p in load_fun_patches()}
        cls.images = {}
        cls.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

    def _image(self, game):
        if game not in self.images:
            source = ROOT / STOCK[game]
            if not source.is_file():
                self.skipTest(f"{game} stock executable not present")
            selected = [f for f in FEATURES[game] if f in self.catalog]
            self.assertEqual(
                len(selected), len(FEATURES[game]),
                f"{game}: the Origins patches this suite needs are not in the "
                "catalog, so it would otherwise pass vacuously")
            rendered, _ = render_patched_bytes(
                source, self.builds[game], "immediate_fixed", selected)
            self.images[game] = bytes(rendered)
        return self.images[game]

    def _offset(self, image, va):
        for start, vsize, raw, rsize in _sections(image):
            if start <= va < start + max(vsize, rsize):
                return raw + (va - start)
        return None

    def _reset_block(self, game):
        """Decode the game's slot-change reset, stopping at its own end.

        Read to the END of the block rather than a fixed number of bytes: a
        fixed window reports a present clear as missing the moment anything is
        inserted ahead of it, which is a failure that looks exactly like a
        regression.
        """
        image = self._image(game)
        spec = RESETS[game]
        if "helper_at" in spec:
            start = spec["helper_at"]
        else:
            detour = spec["detour_at"]
            offset = self._offset(image, detour)
            self.assertIsNotNone(offset, f"{game}: {detour:#x} is not mapped")
            self.assertEqual(
                image[offset], 0xE9,
                f"{game}: {detour:#x} is not a jmp; the save-builder detour "
                "has moved and this suite is reading the wrong bytes")
            start = detour + 5 + struct.unpack_from("<i", image, offset + 1)[0]
        offset = self._offset(image, start)
        self.assertIsNotNone(offset, f"{game}: {start:#x} is not mapped")
        block = []
        for instruction in self.md.disasm(image[offset:offset + 0x80], start):
            block.append(instruction)
            if instruction.mnemonic in ("ret", "jmp"):
                break
        self.assertTrue(block, f"{game}: the reset block decodes to nothing")
        return block

    def _written(self, block):
        """Absolute addresses this block stores an immediate zero into."""
        written = set()
        for instruction in block:
            if instruction.mnemonic != "mov":
                continue
            destination, _, source = instruction.op_str.partition(", ")
            if source.strip() != "0":
                continue
            destination = destination.strip()
            if "ptr [0x" not in destination:
                continue
            written.add(int(destination.split("[")[1].rstrip("]"), 16))
        return written

    def test_every_queued_event_global_is_cleared_on_a_slot_change(self):
        for game, spec in RESETS.items():
            with self.subTest(game=game):
                written = self._written(self._reset_block(game))
                for address, name in spec["globals"].items():
                    with self.subTest(state=name):
                        self.assertIn(
                            address, written,
                            f"{game}: the {name} at {address:#010x} is not "
                            "cleared when the player changes save slot, so an "
                            "event bought in one village leaves the next "
                            "village's row reading Unavailable and can be "
                            "delivered into a save that never paid for it")

    def test_the_clears_are_gated_on_a_real_slot_change(self):
        """Unconditional would discard a pending event on every autosave.

        The stock save-path builder runs for saves as well as loads, so an
        ungated clear is a different bug in the same place.

        This asserts the clear sits BEHIND the gate, not merely that a compare
        exists somewhere in the block. Mutation-checked: moving VV3's clear
        past `save_slot_keep_previous:` makes it unconditional while leaving
        the slot compare untouched, and an "is there a cmp?" check passes on
        that. The clear has to be on the branch's not-taken path -- the one
        reached only when the slot actually changed.
        """
        for game, spec in RESETS.items():
            with self.subTest(game=game):
                block = self._reset_block(game)
                addresses = set(spec["globals"])

                skips = [
                    instruction for instruction in block
                    if instruction.mnemonic.startswith("j")
                    and instruction.mnemonic != "jmp"
                    and instruction.op_str.startswith("0x")
                ]
                if not skips:
                    # VV4's reset is out of line, so its gate lives at the call
                    # site. Require it to be a callee that RETURNS -- fallen
                    # into code would not.
                    self.assertEqual(
                        block[-1].mnemonic, "ret",
                        f"{game} clears queued-event state with no preceding "
                        "compare and does not return, so it is neither gated "
                        "here nor a callee gated by its caller; a pending "
                        "event would be discarded on every autosave")
                    continue

                # Every clear must lie strictly between the LAST skip branch
                # and that branch's destination: the region the branch jumps
                # over, which runs only on a real slot change.
                gate = skips[-1]
                destination = int(gate.op_str, 16)
                for instruction in block:
                    if instruction.mnemonic != "mov":
                        continue
                    written = self._written([instruction]) & addresses
                    if not written:
                        continue
                    address = sorted(written)[0]
                    self.assertTrue(
                        gate.address < instruction.address < destination,
                        f"{game}: the clear of {address:#010x} at "
                        f"{instruction.address:#x} is not inside the region "
                        f"`{gate.mnemonic} {gate.op_str}` at "
                        f"{gate.address:#x} jumps over, so it runs on every "
                        "save and would discard a legitimately pending event "
                        "on each autosave")


if __name__ == "__main__":
    unittest.main()
