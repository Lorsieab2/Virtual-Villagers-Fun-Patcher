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
    def test_restore_can_grant_ownership_but_never_revoke_it(self) -> None:
        """A stale sidecar must not undo what the save already records.

        Now that the flags live inside the serialised save, the save is the
        authority and the sidecar is a migration aid. The two can disagree: the
        .ldw write can succeed after a purchase while Vv1DoublerSave fails, and
        every one of its failure paths deliberately leaves the PREVIOUS .dat in
        place. An unconditional assignment in Restore would then copy the older
        sidecar over the newly saved flag and silently undo the purchase, or
        bring a removed doubler back.

        So Restore must raise a flag to 1 and never lower it. This asserts the
        direction of the write, which is the part that differs between the bug
        and the fix -- both versions apply the sidecar, so presence alone
        cannot tell them apart.
        """
        restore = self._function("Restore")
        for field in ("*tech", "*food"):
            self.assertNotRegex(
                restore,
                re.escape(field) + r"\s*=\s*\(?\s*payload",
                "%s must not be assigned straight from the sidecar: a stale "
                "file would revoke ownership the save already holds" % field,
            )
            self.assertRegex(
                restore,
                re.escape(field) + r"\s*=\s*1u\s*;",
                "%s must be raised to 1, so the sidecar can only grant" % field,
            )
        # And the grant must be conditional on the sidecar actually claiming
        # ownership, rather than unconditionally setting both flags.
        self.assertRegex(
            restore,
            r"if\s*\(\s*payload\[1\]\s*!=\s*0\s*\)",
            "the tech grant must be gated on the sidecar claiming tech",
        )
        self.assertRegex(
            restore,
            r"if\s*\(\s*payload\[2\]\s*!=\s*0\s*\)",
            "the food grant must be gated on the sidecar claiming food",
        )

    def test_a_migrated_save_ignores_the_sidecar_entirely(self) -> None:
        """Once the save carries the flags, a 0 in it means a real removal.

        Grant-only alone left `save 0 + sidecar 1` ambiguous: that shape is
        BOTH the legacy migration and a persisted removal whose sidecar write
        failed, and OR-ing always picks "restore", so removing a doubler could
        be undone on the next load. The village tag does not help, because the
        stale file belongs to the same village.

        The marker disambiguates them. Restore must therefore return BEFORE
        reading the sidecar when it is set, and Save must stamp it, so the
        migration happens at most once per village.
        """
        restore = self._function("Restore")
        save = self._function("Save")

        migrated = self._macro("VV_DOUBLER_MIGRATED_OFFSET")
        payload_end = PAYLOAD_STATE_BASE + 0xABDC
        self.assertGreaterEqual(migrated, PAYLOAD_STATE_BASE)
        self.assertLess(
            migrated + 4,
            payload_end,
            "the marker must round-trip through the save like the flags",
        )
        for other in ("VV_DOUBLER_TECH_OFFSET", "VV_DOUBLER_FOOD_OFFSET",
                      "VV_DOUBLER_VILLAGE_TAG_OFFSET"):
            self.assertNotEqual(
                migrated,
                self._macro(other),
                "the marker must not overlap %s" % other,
            )

        # Restore bails out on the marker, and does so before opening the file.
        self.assertRegex(
            restore,
            r"if\s*\(\s*\*migrated\s*==\s*VV_DOUBLER_MIGRATED_VALUE\s*\)",
            "Restore must ignore the sidecar once the save is authoritative",
        )
        guard = restore.index("*migrated == VV_DOUBLER_MIGRATED_VALUE")
        opened = restore.index("CreateFileA")
        self.assertLess(
            guard,
            opened,
            "the marker check must come before the sidecar is opened",
        )

        # The stamp belongs on the LOAD path, not in Save.
        #
        # The save hook is spliced at 0x41BF68, one instruction past the writer
        # call at 0x41BF63, so anything Save sets reaches memory only after the
        # .ldw is serialised and would not be on disk until the FOLLOWING save.
        # A removal in that window would still be undone by a stale sidecar,
        # which is the ambiguity the marker exists to remove.
        self.assertNotRegex(
            save,
            r"\*migrated\s*=\s*VV_DOUBLER_MIGRATED_VALUE\s*;",
            "Save must not stamp the marker: its hook runs after the write, so "
            "the marker would miss the save that triggered it",
        )
        self.assertRegex(
            restore,
            r"\*migrated\s*=\s*VV_DOUBLER_MIGRATED_VALUE\s*;",
            "Restore must stamp the marker, where it is in memory before any "
            "save serialises",
        )
        # It must NOT be stamped before the sidecar is examined.
        #
        # Consuming the migration up front also consumes it when the file
        # exists but could not be read this time -- an unresolvable Documents
        # folder, a sharing violation, a failed read. Restore then returns
        # without granting, the next save persists the marker, and every later
        # load skips a still-valid sidecar, losing a doubler the player bought.
        #
        # "Confirmed absent" and "could not look" are different answers, so the
        # stamp has to sit on the paths that actually learned something.
        stamp = restore.index("*migrated = VV_DOUBLER_MIGRATED_VALUE")
        self.assertGreater(
            stamp,
            restore.index("CreateFileA"),
            "the migration must not be consumed before the sidecar is even "
            "opened: a transient failure would strand a real sidecar",
        )
        # A genuinely missing file is settled, and is told apart from other
        # open failures by the error code rather than lumped in with them.
        self.assertIn(
            "ERROR_FILE_NOT_FOUND",
            restore,
            "a missing sidecar must be distinguished from an unreadable one",
        )
        self.assertIn(
            "ERROR_PATH_NOT_FOUND",
            restore,
            "a missing folder must be distinguished from an unreadable one",
        )
        # A short read must not count as an answer.
        self.assertRegex(
            restore,
            r"if\s*\(\s*got\s*==\s*sizeof\(payload\)\s*\)",
            "only a complete read may settle the migration",
        )
        # And the sidecar must survive long enough to BE retried.
        #
        # Leaving the marker clear is useless on its own: Save runs on every
        # save and would republish the file from in-memory flags that are still
        # zero precisely because the restore could not read them, destroying
        # the only record of a purchase before the retry happens. So Save must
        # decline to publish while the migration is unresolved.
        self.assertRegex(
            save,
            r"if\s*\(\s*\*migrated\s*!=\s*VV_DOUBLER_MIGRATED_VALUE\s*\)",
            "Save must not republish the sidecar while migration is pending, "
            "or a transient restore failure loses the purchase on the next save",
        )
        decline = save.index("*migrated != VV_DOUBLER_MIGRATED_VALUE")
        self.assertLess(
            decline,
            save.index("CreateFileA"),
            "the refusal must come before the file is created, not after",
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
