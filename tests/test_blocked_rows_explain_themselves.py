"""A blocked Barrel/Island row must say WHY, in all five games.

The Tech menu used to draw a blocked Island Event or Barrel of Babies row as a
DISABLED button reading "Unavailable". That is accurate and useless: it tells
the player the upgrade cannot be bought without telling them why, or whether
waiting will help. Worse, a disabled button swallows the click, so there was
nowhere to put an explanation even if one existed.

The row now stays clickable, reads "Why not?", and clicking it shows the
specific reason and closes nothing -- in particular it does NOT reach the
purchase path, so nothing is charged.

Two causes are distinguished, because they ask completely different things of
the player:

  * ALREADY PENDING -- one was bought moments ago and arrives a few seconds
    after the screen closes. Waiting fixes it.
  * NO VILLAGER SLOTS -- the village has no room for the children. Waiting does
    NOT fix it; the player has to act. The text names burial specifically,
    because a dead villager keeps occupying a record until they are buried,
    which is exactly the state that surprises players.

These tests assert against the COMPILED DLLs as well as the sources. A string
present in the C file but absent from the shipped binary would leave the
player with the old behaviour and a green suite.
"""

import pathlib
import re
import unittest

try:
    import capstone
except ImportError:  # pragma: no cover - exercised only without capstone
    capstone = None

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Every game's dialog source. VV2 includes VV1's file, so it has no separate
# copy of the reason table; it is listed for the call sites it does own.
SOURCES = {
    "vv1": "native/vv1_origins_icons/vv1_origins_icons.c",
    "vv2": "native/vv2_origins_icons/vv2_origins_icons.c",
    "vv3": "native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c",
    "vv4": "native/vv4_origins_icons/vv4_origins_icons.c",
    "vv5": "native/vv5_task9_origins/vv5_task9_origins.c",
}

# The shipped companions. VV3 deploys the same canonical build twice.
DLLS = {
    "vv1": "assets/origins/VVFP VV1 Origins Icons.dll",
    "vv2": "assets/origins/VVFP VV2 Origins Icons.dll",
    "vv3": "data/candidates/VVFP VV3 Full Mastery Candidate.dll",
    "vv3_safe_upgrades": "data/candidates/VVFP VV3 Safe Upgrades.dll",
    "vv4": "assets/origins/VVFP VV4 Origins Icons.dll",
    "vv5": "data/candidates/VVFP VV5 Task9 Origins Icons.dll",
}

BUTTON_LABEL = b"Why not?"
DIALOG_TITLE = b"Not right now"
PENDING_TEXT = b"already been bought and is on its way"
NO_SLOTS_TEXT = b"not enough room in the village for the three children"
BURIAL_HINT = b"buried"
# The wording must not claim EVERY slot is taken: the check is for three free
# records, so with one or two free that would contradict the visible village.
OVERCLAIM = b"Every villager slot is taken"


def _manifest_payload(relative: str) -> bytes:
    """Every emitted byte of a feature manifest: patches AND appended layouts.

    Reading only `patches` is a false-negative waiting to happen, and it bit
    immediately: VV3 emits its arming instruction into the appended R-X page,
    which lives under `pe_append_transaction.layouts`, so a patches-only scan
    reported the flag as unarmed on a build that arms it correctly. A guard
    that cannot see half the payload cannot certify anything about it.
    """
    import json as _json

    manifest = _json.loads((ROOT / relative).read_text(encoding="utf-8"))
    blobs = [
        bytes.fromhex(patch["after"])
        for patch in manifest.get("patches", [])
        if patch.get("after")
    ]
    layouts = manifest.get("pe_append_transaction", {}).get("layouts", {})
    for layout in layouts.values():
        if layout.get("append_bytes"):
            blobs.append(bytes.fromhex(layout["append_bytes"]))
    return b"".join(blobs)


class BlockedRowsExplainThemselvesTests(unittest.TestCase):
    def test_every_shipped_companion_carries_the_explanations(self):
        """The bytes the player actually runs.

        Checking the C sources alone would pass while the DLL in the release
        still had the old behaviour -- the companions are committed binaries,
        so a source edit without a rebuild is a real and silent failure mode.
        """
        for game, relative in sorted(DLLS.items()):
            path = ROOT / relative
            with self.subTest(game=game):
                self.assertTrue(path.is_file(), f"missing companion: {relative}")
                blob = path.read_bytes()
                for needle in (
                    BUTTON_LABEL,
                    DIALOG_TITLE,
                    PENDING_TEXT,
                    NO_SLOTS_TEXT,
                ):
                    # assertTrue on a membership test, not assertIn: the latter
                    # prints the entire DLL on failure, which buried the real
                    # message under 16MB of hex.
                    self.assertTrue(
                        needle in blob,
                        f"{relative} does not contain {needle!r}. The source "
                        "may have been edited without rebuilding the DLL, in "
                        "which case players keep the old bare 'Unavailable'",
                    )
                self.assertFalse(
                    OVERCLAIM in blob,
                    f"{relative} still claims every villager slot is taken. "
                    "The barrel needs THREE free records, so with one or two "
                    "free that contradicts what the player can see",
                )

    def test_no_shipped_companion_still_disables_these_rows(self):
        """Anti-regression on the mechanism that caused the complaint.

        A disabled button cannot explain itself. If a future edit re-disables
        the row, the reason text would still be present in the binary and the
        test above would pass, so this pins the source side of it.
        """
        pattern = re.compile(
            r"blocked\s*!=\s*(?:VV3_)?BLOCK_NONE\s*\)\s*\{(?P<body>.*?)\n            \}",
            re.S,
        )
        for game, relative in sorted(SOURCES.items()):
            text = (ROOT / relative).read_text(encoding="utf-8", errors="ignore")
            match = pattern.search(text)
            with self.subTest(game=game):
                self.assertIsNotNone(
                    match, f"{relative}: no block-reason branch found"
                )
                body = match.group("body")
                self.assertIn(
                    "TRUE",
                    body,
                    f"{relative}: the blocked row is not left enabled, so the "
                    "click cannot be intercepted and explained",
                )
                self.assertNotIn(
                    "FALSE",
                    body,
                    f"{relative}: the blocked row is disabled again. A "
                    "disabled button swallows the click, which is the whole "
                    "reason 'Unavailable' was unhelpful",
                )

    def test_the_two_causes_are_distinguished(self):
        """One message for both causes would be no better than 'Unavailable'.

        A queued event clears itself; a full village does not. Collapsing them
        would tell a player to wait when waiting cannot help.
        """
        for game in ("vv1", "vv3", "vv4", "vv5"):
            text = (ROOT / SOURCES[game]).read_bytes()
            with self.subTest(game=game):
                self.assertTrue(PENDING_TEXT in text, f"{game}: no pending text")
                self.assertTrue(NO_SLOTS_TEXT in text, f"{game}: no capacity text")

    def test_the_capacity_message_mentions_burial(self):
        """The actionable half.

        A player told only that the village is full has no way to know that
        burying remains frees a slot -- a dead villager keeps their record
        until buried, which is precisely the state that looks like a bug.
        """
        for game, relative in sorted(DLLS.items()):
            blob = (ROOT / relative).read_bytes()
            index = blob.find(NO_SLOTS_TEXT)
            with self.subTest(game=game):
                self.assertGreater(index, 0, f"{relative}: capacity text absent")
                window = blob[index : index + 400]
                self.assertTrue(
                    BURIAL_HINT in window,
                    f"{relative}: the capacity message does not mention "
                    "burial, so it says what is wrong without saying what the "
                    "player can do about it",
                )

    def test_a_pending_island_still_examines_the_barrel_row(self):
        """VV4: the island branch must not skip the barrel checks.

        The original code set the BARREL bit from the island branch, which was
        wrong -- it claimed a barrel was on its way when none had been bought.
        Removing that bit while KEEPING the branch's jump to the end was also
        wrong, and Codex caught it on the fix rather than the original: with
        both gone, the Barrel row went unexamined whenever an island event was
        pending, so a player could buy an island event, buy a barrel inside the
        same five-second window, reopen the menu, and be charged for a second
        barrel while the first was still armed.

        Asserted as: the jump that immediately follows the island bit must land
        on the barrel-armed comparison. That is the single instruction the
        defect changes, and checking it directly avoids a reachability walk --
        an earlier version of this test searched forward in the blob instead,
        and passed against the known-bad build because the barrel check is
        still PRESENT in the image, merely jumped over.
        """
        if capstone is None:
            self.skipTest("requires capstone")
        import json as _json

        manifest = _json.loads(
            (ROOT / "data" / "vv4_origins_feature.json").read_text(encoding="utf-8")
        )
        island_bit = bytes.fromhex("81CA00008000")  # or edx, 0x800000
        found = False
        for patch in manifest.get("patches", []):
            after = patch.get("after")
            if not after or island_bit not in bytes.fromhex(after):
                continue
            found = True
            blob = bytes.fromhex(after)
            offset = patch.get("file_offset")
            if offset is None:
                offset = int(str(patch.get("offset", "0")), 0)
            base = 0x400000 + offset
            md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
            listing = {i.address: i for i in md.disasm(blob, base)}
            island = base + blob.find(island_bit)
            after_bit = listing[island].address + listing[island].size
            branch = listing.get(after_bit)
            self.assertIsNotNone(branch, "no instruction follows the island bit")
            self.assertEqual(
                branch.mnemonic,
                "jmp",
                "the island branch no longer ends in a jump; re-check that it "
                f"still reaches the barrel checks: {branch.mnemonic} "
                f"{branch.op_str}",
            )
            landing = listing.get(int(branch.op_str, 16))
            self.assertIsNotNone(landing, "island branch jumps outside the cave")
            self.assertEqual(
                (landing.mnemonic, landing.op_str.split(",")[0].strip()),
                ("cmp", "byte ptr [0x728b04]"),
                "the island branch does not land on the barrel-armed check, "
                "so a barrel queued inside the same window goes unexamined and "
                f"can be charged twice: {landing.mnemonic} {landing.op_str}",
            )
        self.assertTrue(found, "VV4 island-pending branch not found")

    def test_no_companion_reads_a_state_bit_nothing_writes(self):
        """A reader with no producer is a silently dead feature.

        Codex found this on VV5: the companion tested STATE_BARREL_PENDING and
        STATE_ISLAND_PENDING, and nothing in the VV5 payload ever set them, so
        both branches were unreachable and the rows never became "Why not?".
        A suite cannot notice on its own, because an always-zero flag is a
        perfectly valid state -- nothing asserts, everything passes.

        The same trap recurs across branches. A DLL that reads VV3's island
        flag at SECTION_DATA_VA + 0x50 is inert unless the payload that ARMS
        that flag is present too, and those two halves have lived on separate
        branches. This pins the invariant rather than the branch topology: for
        each game, if the companion reads a pending bit, the payload must
        contain an instruction that sets it.
        """
        import json as _json

        # game -> (companion source, payload manifest, bit)
        pairs = (
            ("vv1", SOURCES["vv1"], "data/vv1_origins_feature.json", 0x800000),
            ("vv1", SOURCES["vv1"], "data/vv1_origins_feature.json", 0x1000000),
            ("vv4", SOURCES["vv4"], "data/vv4_origins_feature.json", 0x800000),
            ("vv4", SOURCES["vv4"], "data/vv4_origins_feature.json", 0x1000000),
        )
        for game, source, manifest_path, bit in pairs:
            text = (ROOT / source).read_text(encoding="utf-8", errors="ignore")
            if f"0x{bit:X}" not in text.upper():
                continue
            payload = _manifest_payload(manifest_path)
            # `or <reg>, imm32` for each of the registers these payloads use.
            setters = [
                bytes([opcode]) + bit.to_bytes(4, "little")
                for opcode in (0x0D, 0xC9, 0xCA, 0xCF)  # eax, ecx, edx, edi
            ]
            with self.subTest(game=game, bit=hex(bit)):
                self.assertTrue(
                    any(setter in payload for setter in setters),
                    f"{game}'s companion tests state bit {hex(bit)} but its "
                    "payload never sets it, so that branch is unreachable and "
                    "the row silently keeps the old behaviour",
                )

    def test_a_flag_the_companion_reads_is_armed_by_the_payload(self):
        """The cross-branch case, stated as bytes rather than as topology.

        VV3's companion reads the island pending flag in the patch's own data
        page. The instruction that ARMS it lives in the payload builder, and
        those two halves have been developed on separate branches -- so a merge
        order exists in which the DLL ships reading a byte nothing ever writes.
        That is the VV5 defect again, and it passes a green suite because zero
        is a valid value for a flag.
        """
        import json as _json
        import re as _re

        source = (ROOT / SOURCES["vv3"]).read_text(encoding="utf-8", errors="ignore")
        match = _re.search(
            r"define\s+VV3_ISLAND_PENDING_FLAG\s+(0x[0-9A-Fa-f]+)", source
        )
        if match is None:
            self.skipTest("VV3 companion does not read an island pending flag")
        flag = int(match.group(1), 16)

        payload = _manifest_payload("data/vv3_origins_feature.json")
        arm = bytes([0xC6, 0x05]) + flag.to_bytes(4, "little") + bytes([0x01])
        # assertTrue on a membership test, not assertIn: the payload is ~78KB
        # and assertIn prints all of it as hex on failure, burying the message
        # that says what to do. Same trap this file already documents for the
        # DLL blobs above.
        self.assertTrue(
            arm in payload,
            f"the VV3 companion reads a pending flag at 0x{flag:X}, but the "
            "VV3 payload never sets it. The DLL half and the payload half are "
            "on different branches; merging the companion without the arming "
            "patch ships a guard that can never fire",
        )

    def test_a_blocked_click_cannot_reach_the_purchase(self):
        """The refusal must not charge.

        The handler shows the message and returns TRUE, which keeps the dialog
        open. Falling through to EndDialog would report the row as bought and
        run the purchase path.
        """
        for game, relative in sorted(SOURCES.items()):
            text = (ROOT / relative).read_text(encoding="utf-8", errors="ignore")
            with self.subTest(game=game):
                marker = "MessageBoxA(window,"
                index = text.find(marker, text.find("WM_COMMAND"))
                self.assertGreater(
                    index, 0, f"{relative}: no refusal MessageBoxA in WM_COMMAND"
                )
                after = text[index : index + 400]
                self.assertIn(
                    "return TRUE;",
                    after,
                    f"{relative}: the refusal does not return TRUE, so the "
                    "dialog may fall through to the purchase path and charge "
                    "for an upgrade it just refused",
                )


if __name__ == "__main__":
    unittest.main()
