"""The README save-switch section must match the executables users receive.

The section originally said all five games behave the same way for doubler
ownership and claimed flatly that a queued event no longer follows you into
another save. Both overstated what ships:

* Doubler ownership is CLEARED, not restored. VV3/VV4/VV5 keep it in a process
  global that is not in the .ldw save, so there is nothing to reload. Returning
  to the village that paid for it finds it unowned -- genuinely different from
  VV1/VV2, where the flag rides the village object.
* Queued events are cleared in THREE games, not five. VV1, VV2 and VV5 clear
  theirs. VV3 slot cave clears only its ownership global, and VV4 out-of-line
  reset helper does the same, so a Barrel queued there can still cross a slot
  change.

This reads the RENDERED executables, not the generator sources. Review called
that out and was right: the release applies generated JSON manifests through
src/vv_fun_patcher.py and never executes the builders, so a builder edited
without regenerating its manifest would let a source-reading test document
behaviour absent from the shipped binary -- the exact trap of verifying the
source instead of the artifact.

Two further review points are enforced below. A game counts as clearing only
when it clears EVERY global its queued state uses, so dropping one of VV1 three
(or VV2 cue counter) is caught rather than masked by the others. And VV4 reset
is followed through the call to its out-of-line helper, because the slot cave is
space-constrained and that helper is where a queued-event clear would naturally
be added.
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

TITLES = {
    "vv1": "A New Home",
    "vv2": "The Lost Children",
    "vv3": "The Secret City",
    "vv4": "The Tree of Life",
    "vv5": "New Believers",
}

STOCK = {
    "vv1": "inputs/vv1-stock-copy/Virtual Villagers - A New Home.exe",
    "vv2": "inputs/vv2-stock-copy/Virtual Villagers - The Lost Children.exe",
    "vv3": "inputs/vv3-stock-copy/Virtual Villagers - The Secret City.exe",
    "vv4": "inputs/vv4-stock-copy/Virtual Villagers - The Tree of Life.exe",
    "vv5": "inputs/vv5-stock-copy/Virtual Villagers - New Believers.exe",
}

# EVERY global each game queued-event state uses, as (address, width). A game is
# only credited with clearing when ALL of its globals are cleared: review noted
# that accepting a single matching store lets a builder drop VV1 delay counter
# or VV2 cue counter while the detector still reports the game safe.
QUEUED_GLOBALS = {
    "vv1": {
        "BARREL_PENDING": (0x48D700, 1),
        "BARREL_DELAY_COUNTER": (0x48D704, 4),
        "BARREL_UPGRADE_FLAG": (0x48D708, 1),
    },
    "vv2": {
        "BARREL_PENDING": (0x49C700, 1),
        "BARREL_UPGRADE_FLAG": (0x49C704, 1),
        "BARREL_CUE_COUNTER": (0x49C708, 4),
    },
    "vv3": {
        # Only the pending flag. BARREL_DUE (0x6E004C) is never zeroed anywhere
        # in the rendered image -- scanning for its clear encoding returns no
        # matches -- so requiring it would demand a store that does not exist.
        "BARREL_PENDING_FLAG": (0x4B3C75, 1),
    },
    "vv4": {
        "BARREL_UPGRADE_FLAG": (0x728B00, 1),
        "BARREL_ARMED": (0x728B04, 1),
    },
    # VV5 carries its pending token as bits of the ownership word, so clearing
    # that word is what clears the queued state. Handled separately below.
    "vv5": {},
}

VV5_OWNERSHIP_WORD = 0x51D388

# The FILE-OFFSET window that holds each game slot-change code, so a clear is
# credited only when it sits on the slot path. Searching the whole image is
# wrong and was caught doing it: VV3 and VV4 both zero their barrel globals on
# the normal DELIVERY path (VV4 at 0xCCB25 and 0xCCB69, far from its slot cave
# at 0xCCFD0 and its reset helper at 0xCCE00), which would report them as
# clearing on a switch when they do not.
SLOT_PATH_WINDOWS = {
    # Measured from the rendered images, not guessed. Each game slot-change
    # clears sit in one contiguous run, well away from its delivery-path
    # clears: VV1 delivers at 0x8B773/0x8B77A/0x8B930/0x8B975 and switches at
    # 0x8E876..0x8E887; VV2 delivers at 0x9A503/0x9A7B6 and switches at
    # 0xB23F6..0xB2404; VV4 delivers at 0xCCB25/0xCCB69, nowhere near its slot
    # cave (0xCCFD0) or its out-of-line reset helper (0xCCE00).
    "vv1": [(0x8E800, 0x8E900)],
    "vv2": [(0xB2380, 0xB2440)],
    "vv3": [(0xCB100, 0xCB180)],
    "vv4": [(0xCCE00, 0xCCE40), (0xCCFD0, 0xCD000)],
    "vv5": [(0xF8F00, 0xF8F80)],
}

# VV4 out-of-line reset helper, and the file window that holds it.
VV4_RESET_VA = 0x728E00
VV4_RESET_FILE_OFFSET = 0xCCE00


def _clear_bytes(address, width):
    """Encode `mov byte/dword ptr [address], 0`."""
    if width == 1:
        return b"\xC6\x05" + struct.pack("<I", address) + b"\x00"
    return b"\xC7\x05" + struct.pack("<I", address) + b"\x00\x00\x00\x00"


class ReadmeSaveSwitchScopeTests(unittest.TestCase):
    """Capstone is required by exactly ONE test here (the VV4 helper
    disassembly). Skipping the whole class on its absence also skipped the
    README wording checks, which need no disassembler at all -- so a machine
    without capstone silently stopped verifying the documentation this file
    exists to police. The skip now sits on the single test that needs it.
    """

    @classmethod
    def setUpClass(cls):
        builds = {b.id: b for b in load_builds()}
        catalog = [p.id for p in load_fun_patches()]
        cls.images = {}
        for game, stock in STOCK.items():
            path = ROOT / stock
            if not path.is_file():
                continue
            ids = [i for i in catalog if i.startswith(game)]
            cls.images[game], _ = render_patched_bytes(
                path, builds[game], "collection_progression", ids
            )

    def _image(self, game):
        """The rendered image, or a skip that says exactly what is missing.

        The stock executables are the player's own game files and cannot be
        committed, so a clean checkout genuinely cannot render them and a skip
        is the honest outcome. What matters is that the skip NAMES the input,
        so an absent artifact check is visible as a missing prerequisite rather
        than looking like a test that simply chose not to run.
        """
        if game not in self.images:
            self.skipTest(
                f"{game}: {STOCK[game]} is absent, so the rendered-image "
                "checks cannot run. Supply your own copy of the game to "
                "exercise them."
            )
        return self.images[game]

    def _clears_every_queued_global(self, game):
        """True only when EVERY queued global for the game is cleared."""
        if game == "vv5":
            return any(
                _clear_bytes(VV5_OWNERSHIP_WORD, 4) in region
                for region in self._slot_regions(game)
            )
        wanted = QUEUED_GLOBALS[game]
        if not wanted:
            return False
        regions = self._slot_regions(game)
        return all(
            any(_clear_bytes(address, width) in region for region in regions)
            for address, width in wanted.values()
        )

    def _slot_regions(self, game):
        """The slot-change code windows of the rendered image."""
        image = self._image(game)
        return [image[start:end] for start, end in SLOT_PATH_WINDOWS[game]]

    def _clearing_games(self):
        return {g for g in TITLES if self._clears_every_queued_global(g)}

    # The section is found by a stable prefix, NOT by its full summary
    # sentence. Anchoring on the whole sentence made the lookup depend on the
    # very wording this file also polices: rephrasing the summary broke section
    # lookup and failed every test at once, which hides the real signal.
    SECTION_ANCHOR = "**Switching save files"

    def _section(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        start = text.index(self.SECTION_ANCHOR)
        return text[start : text.index("Both menus close with", start)]

    def _queued_bullet(self):
        """Just the queued-event bullet.

        Review pointed out that checking the whole section is toothless here:
        every clearing game title already appears in the doubler-ownership
        bullet above, so a queued-event bullet that dropped or mislabelled a
        game would still satisfy an assertIn against the section.
        """
        section = self._section()
        start = section.index("- **A queued Island Event")
        end = section.find("\n\nSaving does not trigger", start)
        bullet = section[start : end if end > start else len(section)]
        # Titles wrap across lines and carry markdown emphasis, so a raw
        # substring test misses "The Tree of Life" when a "**" and a newline
        # land inside it. Normalise whitespace and emphasis before matching.
        return " ".join(bullet.replace("*", " ").split())

    def test_the_section_and_bullet_still_exist(self):
        """Guard the guard -- every assertion below reads these."""
        self.assertIn("Doubler ownership", self._section())
        self.assertIn("queued Island Event", self._queued_bullet())

    def test_the_detector_agrees_with_the_shipped_images(self):
        """Positive control, pinned against the RENDERED executables.

        Without this a detector that quietly stops matching shrinks the scope
        the README is checked against instead of failing.
        """
        for game in TITLES:
            with self.subTest(game=game, expected="clears"):
                self.assertTrue(
                    self._clears_every_queued_global(game),
                    f"{game} no longer clears every queued-event global on a "
                    "slot change; the owner asked for all five games to be "
                    "protected against upgrades reading Unavailable after a "
                    "save switch",
                )

    def test_a_partial_clear_does_not_count(self):
        """Dropping one global must not still read as clearing.

        VV1 needs all three of pending, delay counter and upgrade flag. This
        pins the all-of rule directly, so a future single-store shortcut is
        caught rather than masked by its siblings.
        """
        regions = self._slot_regions("vv1")
        present = [
            name
            for name, (address, width) in QUEUED_GLOBALS["vv1"].items()
            if any(_clear_bytes(address, width) in region for region in regions)
        ]
        self.assertEqual(
            sorted(present),
            sorted(QUEUED_GLOBALS["vv1"]),
            "VV1 no longer clears every queued-event global it uses",
        )

    @unittest.skipIf(capstone is None, "requires capstone")
    def test_vv4_reset_helper_is_followed_through_the_call(self):
        """VV4 reset is out of line; read the helper, not just the cave.

        The slot cave has 2 bytes of headroom, so a queued-event clear would
        naturally be added to the called helper. Decoding it here means the
        README cannot go stale if that happens.
        """
        image = self._image("vv4")
        helper = image[VV4_RESET_FILE_OFFSET : VV4_RESET_FILE_OFFSET + 0x40]
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        body = []
        for insn in md.disasm(helper, VV4_RESET_VA):
            body.append((insn.mnemonic, insn.op_str))
            if insn.mnemonic == "ret":
                break
        self.assertIn(
            "ret",
            [m for m, _ in body],
            "VV4 reset helper never returns",
        )
        touched = sorted(
            name
            for name, (address, _) in QUEUED_GLOBALS["vv4"].items()
            if any(f"{address:#x}" in ops for _, ops in body)
        )
        self.assertEqual(
            touched,
            sorted(QUEUED_GLOBALS["vv4"]),
            "VV4 out-of-line reset helper must clear BOTH barrel flags as well "
            f"as doubler ownership; it currently touches {touched}. The cave "
            "that calls it has 2 bytes of headroom, so the helper is where "
            "these clears belong.",
        )

    def test_the_queued_bullet_names_every_clearing_game(self):
        bullet = self._queued_bullet()
        for game in self._clearing_games():
            with self.subTest(game=game):
                self.assertIn(
                    TITLES[game],
                    bullet,
                    f"{TITLES[game]} clears its queued-event state but the "
                    "README queued-event bullet never names it",
                )

    def test_the_bullet_states_no_exception_while_none_exists(self):
        """No game is exempt now, so the bullet must not claim one is.

        This is the mirror of the check it replaces. While VV3 and VV4 did not
        clear, the bullet had to name them; now that every game clears, a
        leftover exception sentence would understate the protection. Either way
        the bullet is pinned to what the images actually do.
        """
        bullet = self._queued_bullet()
        self.assertEqual(
            self._clearing_games(),
            set(TITLES),
            "not every game clears; this test assumes they all do",
        )
        self.assertNotIn(
            "do not clear theirs",
            bullet,
            "every game now clears queued-event state on a slot change, so "
            "the bullet must not carry a VV3/VV4 exception",
        )

    def test_the_summary_matches_whether_any_game_is_exempt(self):
        """The lead-in must track the images, in BOTH directions.

        Review's original objection was that an absolute summary contradicted
        the bullet while VV3 and VV4 did not clear. #240 made them clear, so
        that sentence is now TRUE -- but banning it forever would leave the
        README permanently understating the protection, and permitting it
        forever would let the contradiction return unnoticed the moment a game
        stops clearing.

        So the ban is tied to the detector rather than fixed: the unqualified
        claim is allowed only while every game really clears, and forbidden the
        moment one does not. Review's point survives as a live check instead of
        a frozen string.
        """
        lead = self._section()
        lead = lead[: lead.index("- **Doubler ownership")]
        absolute = "does not carry upgrade state between villages" in lead
        exempt = set(TITLES) - self._clearing_games()
        if exempt:
            self.assertFalse(
                absolute,
                "the summary states an unqualified rule, but "
                f"{sorted(TITLES[g] for g in exempt)} do not clear queued-event "
                "state; a reader who stops at the lead-in is told something "
                "the bullet below then contradicts",
            )

    def test_readme_does_not_claim_uniform_doubler_behaviour(self):
        self.assertNotIn(
            "All five now behave the same way",
            self._section(),
            "VV3/VV4/VV5 clear ownership rather than restoring it",
        )

    def test_readme_says_ownership_is_not_restored_on_return(self):
        section = self._section()
        self.assertTrue(
            "buy it again" in section,
            # `"buy it again" or "nothing to reload"` accepted text that says
            # the opposite: a README claiming ownership IS restored could still
            # contain "nothing to reload" in some other clause and pass. The
            # affirmative statement that the player must re-buy is the claim
            # under test, so require it specifically.
            "the README does not state that a returning player must buy the "
            "doubler again -- in VV3/VV4/VV5 ownership is CLEARED rather than "
            "restored, and the section has to say so plainly",
        )


if __name__ == "__main__":
    unittest.main()
