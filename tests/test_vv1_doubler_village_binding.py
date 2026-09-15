from __future__ import annotations

import re
import struct
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

SOURCE = ROOT / "native" / "vv1_origins_icons" / "vv1_origins_icons.c"
DLL = ROOT / "assets" / "origins" / "VVFP VV1 Origins Icons.dll"

# The village identity tag, in the SAVED FILE's address space.  Measured across
# 38 of the owner's VV1 saves covering 22 distinct villages: constant at all 90
# villager record slots within a village, distinct across every village.
TAG_FILE_OFFSET = 0x188

# The exe's own numbers, from the save/load pair in "A New Home":
#   0x41BEDB  lea edi, [ebx+8]      the saver copies the staged buffer to state+8
#   0x41BF58  lea eax, [esi+8]      the loader reads into state+8
#   0x4031E6  fwrite(hdr, 0xC, 1)   a 12-byte header precedes the payload
# so  file = (state - 8) + 0xC = state + 4.
PAYLOAD_STATE_BASE = 0x8
SAVE_HEADER_BYTES = 0xC
TAG_STATE_OFFSET = TAG_FILE_OFFSET - SAVE_HEADER_BYTES + PAYLOAD_STATE_BASE

SIDECAR_MAGIC = 0x32304456  # 'VD02'
SUPERSEDED_MAGIC = 0x31304456  # 'VD01', the untagged 12-byte record


class VillageTagBindingTest(unittest.TestCase):
    """The doubler sidecar must be bound to the village that earned it.

    Save slots are reused.  Without a binding, starting a new village in a slot
    that still holds an old village's sidecar grants doublers that village
    never earned, on any reload before its first save.
    """

    def setUp(self) -> None:
        self.text = SOURCE.read_text(encoding="utf-8")

    def _macro(self, name: str) -> int:
        match = re.search(
            r"^#define\s+%s\s+(0x[0-9A-Fa-f]+)u?" % re.escape(name),
            self.text,
            re.MULTILINE,
        )
        self.assertIsNotNone(match, "%s is not defined in %s" % (name, SOURCE.name))
        return int(match.group(1), 16)

    def _function(self, name: str) -> str:
        start = self.text.index("Vv1Doubler%s(void *state) {" % name)
        depth = 0
        for index in range(start, len(self.text)):
            if self.text[index] == "{":
                depth += 1
            elif self.text[index] == "}":
                depth -= 1
                if depth == 0:
                    return self.text[start:index + 1]
        self.fail("unterminated Vv1Doubler%s" % name)

    def test_tag_offset_matches_the_measured_save_layout(self) -> None:
        """The in-memory offset must be the file offset carried through the
        exe's own base adjustment -- not the file offset used directly.

        This is the check that would have caught +0x17C (file - 0xC, forgetting
        the state+8 payload base) or +0x188 (the file offset used raw, ignoring
        the header entirely).
        """
        self.assertEqual(TAG_STATE_OFFSET, 0x184)
        self.assertEqual(
            self._macro("VV_DOUBLER_VILLAGE_TAG_OFFSET"),
            TAG_STATE_OFFSET,
            "the tag offset must be the file offset 0x%X mapped through "
            "file = state + 4" % TAG_FILE_OFFSET,
        )

    def test_tag_is_inside_the_serialised_payload(self) -> None:
        """The tag must be a field the save actually round-trips.

        The doubler flags themselves sit at +0xAD48/+0xAD4C, PAST the 0xABDC
        the game serialises, which is the whole reason this sidecar exists.  A
        tag with that problem would read as garbage on the restore path.
        """
        payload_end = PAYLOAD_STATE_BASE + 0xABDC
        offset = self._macro("VV_DOUBLER_VILLAGE_TAG_OFFSET")
        self.assertGreaterEqual(offset, PAYLOAD_STATE_BASE)
        self.assertLess(
            offset + 4,
            payload_end,
            "the tag must round-trip through the save, unlike the doubler "
            "flags at +0xAD48/+0xAD4C which do not",
        )
        for flag in ("VV_DOUBLER_TECH_OFFSET", "VV_DOUBLER_FOOD_OFFSET"):
            self.assertGreater(
                self._macro(flag),
                payload_end,
                "%s is expected to sit past the serialised extent" % flag,
            )

    def test_save_stamps_the_tag(self) -> None:
        save = self._function("Save")
        self.assertIn("VV_DOUBLER_VILLAGE_TAG_OFFSET", save)
        self.assertRegex(
            save,
            r"payload\[3\]\s*=\s*\*tag\s*;",
            "Vv1DoublerSave must stamp the live village tag into the sidecar",
        )
        self.assertIn("unsigned int payload[4]", save)

    def test_restore_rejects_a_foreign_tag(self) -> None:
        """The guard this whole change exists for."""
        restore = self._function("Restore")
        self.assertIn("unsigned int payload[4]", restore)
        self.assertRegex(
            restore,
            r"payload\[0\]\s*==\s*VV_DOUBLER_SIDECAR_MAGIC\s*\n\s*"
            r"&&\s*payload\[3\]\s*==\s*\*tag",
            "Vv1DoublerRestore must require the village tag to match, not "
            "accept a sidecar on magic alone",
        )

    def test_restore_falls_back_rather_than_granting(self) -> None:
        """A rejected sidecar must leave the flags as the game set them."""
        restore = self._function("Restore")
        applied = restore.index("*tech =")
        guard = restore.index("payload[3] == *tag")
        self.assertLess(
            guard,
            applied,
            "the tag check must gate the writes, not follow them",
        )

    def test_magic_was_bumped_for_the_longer_record(self) -> None:
        """A 12-byte 'VD01' file must not be readable as a 16-byte record."""
        self.assertEqual(self._macro("VV_DOUBLER_SIDECAR_MAGIC"), SIDECAR_MAGIC)
        self.assertNotEqual(SIDECAR_MAGIC, SUPERSEDED_MAGIC)

    def test_shipped_dll_carries_the_binding(self) -> None:
        """CODE PRESENT != CODE RUNNING: check the built artifact too."""
        self.assertTrue(DLL.is_file(), "%s is not built" % DLL)
        blob = DLL.read_bytes()
        self.assertIn(
            struct.pack("<I", SIDECAR_MAGIC),
            blob,
            "the shipped DLL does not carry the 'VD02' magic",
        )
        self.assertNotIn(
            struct.pack("<I", SUPERSEDED_MAGIC),
            blob,
            "the shipped DLL still carries the untagged 'VD01' magic, so it "
            "was not rebuilt from the current source",
        )
        self.assertIn(
            struct.pack("<I", TAG_STATE_OFFSET),
            blob,
            "the shipped DLL does not reference the village tag offset",
        )


if __name__ == "__main__":
    unittest.main()
