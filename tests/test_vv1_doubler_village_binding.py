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
        """The tag must be a field the save actually round-trips."""
        payload_end = PAYLOAD_STATE_BASE + 0xABDC
        offset = self._macro("VV_DOUBLER_VILLAGE_TAG_OFFSET")
        self.assertGreaterEqual(offset, PAYLOAD_STATE_BASE)
        self.assertLess(
            offset + 4,
            payload_end,
            "the tag must round-trip through the save",
        )

    def test_doubler_flags_are_inside_the_serialised_payload(self) -> None:
        """The flags must live where the game actually saves them.

        This is the persistence fix.  The flags used to sit at +0xAD48/+0xAD4C,
        356 and 360 bytes PAST the 0xABDC the serialiser copies from state+8,
        so the game set them correctly and then never wrote them to disk and a
        purchased doubler vanished on reload.  They now sit inside the extent,
        which is why VV2-VV5 keep their equivalents without any sidecar.

        Asserting the containment directly means a future edit that moves
        either flag back outside the window fails here rather than silently
        reintroducing the original bug.
        """
        payload_end = PAYLOAD_STATE_BASE + 0xABDC
        for flag in ("VV_DOUBLER_TECH_OFFSET", "VV_DOUBLER_FOOD_OFFSET"):
            offset = self._macro(flag)
            self.assertGreaterEqual(
                offset,
                PAYLOAD_STATE_BASE,
                "%s must not sit before the serialised payload" % flag,
            )
            self.assertLess(
                offset + 4,
                payload_end,
                "%s must round-trip through the save, or a purchased doubler "
                "is lost on reload" % flag,
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


class HookDirectionTest(unittest.TestCase):
    """The save hook must be on the save function and the restore hook on the
    load function.

    An earlier revision had them the other way round.  Every splice verified,
    every guard matched, and the feature was still completely inert: the save
    export ran on load (before the read, so it sampled the previous village)
    and the restore export ran at the end of a save (where nothing needs
    restoring and nothing is re-serialised).

    The file primitives are what settle the direction, so this test asserts
    against those rather than against the function names:

        sub_402FD0  fopen("rb") + fread + 'ldwg' magic   -> the READER
        sub_403160  fopen("wb") + fwrite                 -> the WRITER
    """

    GENERATOR = ROOT / "scripts" / "build_vv1_origins_feature.py"

    # sub_41BF10 calls the WRITER at 0x41BF63, so it saves.  0x41BF68 is its
    # epilogue: the write has returned and ESI holds the state.
    SAVE_HOOK_VA = 0x41BF68
    SAVE_HOOK_GUARD = "5F5EC20400"

    # sub_41BE00 calls the READER at 0x41BEC4 and installs the result with the
    # rep movsd at 0x41BEDB.  0x41BEFD is past both, and EBX holds the state.
    LOAD_HOOK_VA = 0x41BEFD
    LOAD_HOOK_GUARD = "E84EC50200"

    # Before the read, and before the rep movsd -- where the save hook used to
    # be.  Nothing may be spliced here.
    PRE_READ_VA = 0x41BEAE

    def setUp(self) -> None:
        self.text = self.GENERATOR.read_text(encoding="utf-8")

    def _const(self, name: str) -> str:
        match = re.search(
            r"^%s\s*=\s*(.+)$" % re.escape(name), self.text, re.MULTILINE
        )
        self.assertIsNotNone(match, "%s is not defined" % name)
        return match.group(1).strip()

    def test_save_hook_is_on_the_save_function(self) -> None:
        self.assertEqual(
            int(self._const("DOUBLER_SAVE_HOOK_VA"), 16),
            self.SAVE_HOOK_VA,
            "Vv1DoublerSave must be spliced at the SAVE function's epilogue "
            "(sub_41BF10, which calls the writer sub_403160), not on the load "
            "function",
        )
        self.assertIn(self.SAVE_HOOK_GUARD, self._const("DOUBLER_SAVE_HOOK_GUARD"))

    def test_restore_hook_is_on_the_load_function_after_the_state_lands(self) -> None:
        self.assertEqual(
            int(self._const("DOUBLER_LOAD_HOOK_VA"), 16),
            self.LOAD_HOOK_VA,
            "Vv1DoublerRestore must be spliced on the LOAD function "
            "(sub_41BE00) AFTER the rep movsd at 0x41BEDB installs the state",
        )
        self.assertIn(self.LOAD_HOOK_GUARD, self._const("DOUBLER_LOAD_HOOK_GUARD"))

    def test_nothing_is_spliced_before_the_read(self) -> None:
        """0x41BEAE runs before the read, so a hook there sees the previous
        village's flags.  That is where the save hook used to sit."""
        for name in ("DOUBLER_SAVE_HOOK_VA", "DOUBLER_LOAD_HOOK_VA"):
            self.assertNotEqual(
                int(self._const(name), 16),
                self.PRE_READ_VA,
                "%s is at 0x41BEAE, which runs BEFORE the read at 0x41BEC4" % name,
            )

    def test_each_stub_pushes_the_register_its_site_actually_holds(self) -> None:
        """EBX on the load path, ESI at the save epilogue.  Pushing the wrong
        one hands the DLL a pointer that is not the game state."""
        save = self.text[self.text.index("doubler_save_call:"):]
        save = save[:save.index("doubler_save_ret:")]
        self.assertIn("push esi", save, "the save epilogue holds the state in ESI")

        restore = self.text[self.text.index("doubler_restore_call:"):]
        restore = restore[:restore.index("doubler_restore_ret:")]
        self.assertIn("push ebx", restore, "the load path holds the state in EBX")


if __name__ == "__main__":
    unittest.main()
