"""The README's save-switch section must name the games that actually clear.

The section originally said all five games "behave the same way" for doubler
ownership and made a blanket claim that a queued event "no longer follows you
into another save". Both overstated what ships, and review caught it:

* **Doubler ownership is cleared, not restored.** VV3/VV4/VV5 keep it in a
  process global that is not in the `.ldw` save, so there is nothing to reload.
  Returning to the village that paid for it finds it unowned -- genuinely
  different from VV1/VV2, where the flag rides the village object.
* **Queued events are cleared in three games, not five.** VV1, VV2 and VV5 do
  clear theirs. VV3's slot cave clears only its ownership global, and VV4's
  out-of-line reset helper does the same, so a Barrel queued there can still
  cross a slot change.

This test reads the shipped builders to decide which games clear what, then
requires the README to be consistent with them. It is deliberately anchored on
the source of truth rather than on fixed prose, so if a later change teaches
VV3 or VV4 to clear its queued state, this test fails and asks for the README
to be updated with it -- rather than silently permitting a stale sentence.
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"

# Human-facing titles, as the README refers to them.
TITLES = {
    "vv1": "A New Home",
    "vv2": "The Lost Children",
    "vv3": "The Secret City",
    "vv4": "The Tree of Life",
    "vv5": "New Believers",
}

# Where each game's slot-change reset actually lives.
SLOT_RESET_SOURCES = {
    "vv1": ["scripts/build_vv1_origins_feature.py"],
    "vv2": ["scripts/build_vv2_mask_stage2.py"],
    "vv3": ["scripts/build_vv3_origins_feature.py"],
    "vv4": ["scripts/build_vv4_origins_feature.py"],
    "vv5": ["scripts/build_vv5_task9_native_actions.py"],
}

# A queued-event clear only counts when it sits INSIDE the slot-change path.
# Searching the whole builder is wrong: VV3 and VV4 both zero their barrel
# globals during normal delivery, which made an earlier version of this
# detector report all five games as clearing and rendered the scope check
# vacuous -- caught by the guard-the-guard test below.
# Substrings that identify a queued-event global, matched against the slot
# path. Deliberately NOT a regex: the builders spell these three different ways
# ([{NAME:#x}] in VV1, [0x{NAME:X}] in VV2), and an earlier regex attempt
# matched none of them while still letting the suite pass -- it reported only
# VV5, which is found by literal text. A missed game here would understate the
# README's required scope, so the detector is kept blunt and verified by
# test_the_detector_sees_every_game_that_really_clears below.
QUEUED_GLOBAL_TOKENS = ("BARREL_PENDING", "BARREL_DELAY", "BARREL_ARMED",
                        "BARREL_CUE", "BARREL_UPGRADE")


def _clears_a_queued_global(region):
    """True when the region writes 0 to one of the queued-event globals."""
    for line in region.splitlines():
        # Strip trailing comments only. Splitting on a bare "#" is wrong: VV1
        # writes [{BARREL_PENDING_VA:#x}], where the "#" is a format spec, and
        # cutting there discarded the ", 0" and hid all three of VV1's clears.
        text = line.split("/*")[0]
        marker = text.find("# ")
        if marker >= 0:
            text = text[:marker]
        if "mov" not in text or not text.rstrip().endswith("0"):
            continue
        if any(token in text for token in QUEUED_GLOBAL_TOKENS):
            return True
    return False


# The assembly block that runs on a genuine slot CHANGE, per game. Each is the
# region between the slot-compare that gates the reset and the label control
# rejoins, which is the only place a clear affects a village switch.
SLOT_PATH_BOUNDS = {
    "vv1": ("save_slot_capture_code = assemble(", "save_slot_done:"),
    "vv2": ("slot_asm = f\"\"\"", "slot_done:"),
    "vv3": ("save_slot_capture_cave = assemble(", "save_slot_keep_previous:"),
    "vv4": ("def mask_save_slot_cave", "mss_keep_previous:"),
    "vv5": ('put(page, page_va, "slot_capture"', "sc_skip:"),
}


def _slot_path(game):
    """Just the slot-change region, or the whole file if unbounded."""
    text = _sources(game)
    start_marker, end_marker = SLOT_PATH_BOUNDS[game]
    start = text.find(start_marker)
    if start < 0:
        raise AssertionError(
            f"{game}: slot-path start marker {start_marker!r} no longer exists; "
            "the detector would silently report this game as not clearing")
    end = text.find(end_marker, start)
    if end <= start:
        raise AssertionError(
            f"{game}: slot-path end marker {end_marker!r} not found after the "
            "start marker; the region would run to end of file")
    return text[start:end]


def _sources(game):
    return "\n".join(
        (ROOT / rel).read_text(encoding="utf-8") for rel in SLOT_RESET_SOURCES[game]
    )


def games_clearing_queued_events():
    """Games whose slot-change path zeroes queued-event state."""
    clearing = set()
    for game in TITLES:
        if _clears_a_queued_global(_slot_path(game)):
            clearing.add(game)
    # VV5 stores the pending token as bits of the ownership word, so the
    # generic barrel-global pattern above cannot see it. Its slot_capture
    # zeroes the whole word, which is what clears the queued token.
    if "mov dword ptr [0x51D388], 0" in _slot_path("vv5"):
        clearing.add("vv5")
    return clearing


def readme_section():
    text = README.read_text(encoding="utf-8")
    start = text.index("**Switching save files does not carry upgrade state")
    end = text.index("Both menus close with", start)
    return text[start:end]


class ReadmeSaveSwitchScopeTests(unittest.TestCase):
    def test_the_section_still_exists(self):
        """Guard the guard -- every assertion below reads this section."""
        self.assertIn("Doubler ownership", readme_section())

    def test_queued_event_clearing_is_detected_for_a_known_subset(self):
        """If the detector matched nothing or everything it would be inert."""
        clearing = games_clearing_queued_events()
        self.assertTrue(clearing, "no game detected as clearing queued events")
        self.assertNotEqual(
            clearing,
            set(TITLES),
            "every game detected as clearing; the scope check would be vacuous",
        )

    def test_the_detector_sees_every_game_that_really_clears(self):
        """Positive control, from the source rather than from the detector.

        VV1, VV2 and VV5 demonstrably zero queued-event state on a slot change
        (VV5 by zeroing the word that carries the pending token). Pinning that
        here means a detector that quietly stops matching -- as an earlier
        regex version did, reporting only VV5 -- fails instead of silently
        shrinking the scope the README is checked against.
        """
        self.assertEqual(
            games_clearing_queued_events(),
            {"vv1", "vv2", "vv5"},
            "the queued-event detector no longer agrees with the builders")

    def test_readme_names_the_games_that_clear_queued_events(self):
        section = readme_section()
        for game in games_clearing_queued_events():
            with self.subTest(game=game):
                self.assertIn(
                    TITLES[game],
                    section,
                    f"{TITLES[game]} clears its queued-event state on a slot "
                    "change but the README's save-switch section never names it",
                )

    def test_readme_does_not_claim_all_five_clear_queued_events(self):
        """The blanket claim review rejected, in the form it was written."""
        section = readme_section()
        self.assertNotIn(
            "A pending event no longer follows you into another save",
            section,
            "the README makes an unqualified queued-event claim, but VV3 and "
            "VV4 do not clear theirs on a slot change",
        )

    def test_readme_does_not_claim_uniform_doubler_behaviour(self):
        section = readme_section()
        self.assertNotIn(
            "All five now behave the same way",
            section,
            "VV3/VV4/VV5 clear ownership rather than restoring it, so they do "
            "not behave the same way as VV1/VV2",
        )

    def test_readme_says_ownership_is_not_restored_on_return(self):
        """The correction review actually asked for.

        Clearing is not the same as restoring: the paying village finds the
        doubler unowned when you come back to it, and the README has to say so
        rather than implying paid upgrades persist per village everywhere.
        """
        section = readme_section()
        self.assertTrue(
            "buy it again" in section or "nothing to reload" in section,
            "the README does not explain that in VV3/VV4/VV5 a doubler is "
            "cleared rather than restored, so a returning player must re-buy it",
        )


if __name__ == "__main__":
    unittest.main()
