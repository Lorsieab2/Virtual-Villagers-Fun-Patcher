"""Every game's Tech and Details menu shell must read exactly like VV2's.

VV2 is the reference implementation.  The visible shell -- dialog caption, row
labels, cost text, button text, the ESC hint and the Cancel control -- must be
identical everywhere.  Which upgrades exist, what they cost, and their icons
deliberately differ per game and are NOT compared.

scripts/audit_upgrade_menu_parity.py produces the comparison; this pins it.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts" / "audit_upgrade_menu_parity.py"


def _load_audit():
    spec = importlib.util.spec_from_file_location("upgrade_menu_parity", AUDIT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the upgrade-menu parity audit")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UpgradeMenuShellTextParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit = _load_audit()

    def test_shell_matches_vv2_everywhere(self) -> None:
        problems = self.audit.audit(verbose=False)
        self.assertEqual(problems, [], "\n".join(problems))

    def test_every_shared_row_uses_the_vv2_wording(self) -> None:
        """A game may omit an upgrade, but never reword one it has.

        VV1 has no Collections rows, so it is allowed to have fewer strings.
        Anything it does show must read exactly as VV2 shows it.
        """
        parsed = {
            game: self.audit.parse_dialogs(path)
            for game, path in self.audit.RESOURCES.items()
            if path.is_file()
        }
        self.assertIn("vv2", parsed, "the VV2 reference resource is required")

        for screen in ("tech", "details"):
            reference = {
                text
                for _, text in parsed["vv2"][
                    self.audit.DIALOGS["vv2"][screen]
                ]["strings"]
            }
            for game in parsed:
                if game == "vv2":
                    continue
                dialog = parsed[game].get(self.audit.DIALOGS[game][screen])
                self.assertIsNotNone(dialog, f"{game}/{screen} dialog missing")
                extra = sorted(
                    {text for _, text in dialog["strings"]} - reference
                )
                with self.subTest(game=game, screen=screen):
                    self.assertEqual(
                        extra,
                        [],
                        f"{game}/{screen} shows wording VV2 does not: {extra}",
                    )

    def test_only_the_doubler_rows_can_show_a_tech_checkmark(self) -> None:
        """Pins the answer to "what are the green checkmarks for?".

        Every game's exe builds the Tech state word with the same two
        "satisfied" bits -- 8 and 16, the Tech Point Doubler and Food Point
        Doubler ownership flags (VV1 accumulates them in EDI, the others in
        EAX).  No game sets a satisfied bit above 4, so those are the only two
        Tech rows whose checkmark can appear, and they are exactly the rows
        whose button also flips to "Remove".

        The other values seen alongside them -- 0x800 and 0x1000 -- are the
        "unavailable" markers for those same two rows under the `1 << (8 + row)`
        encoding, not additional satisfied bits.

        VV3/VV4/VV5 declare badge controls for all 14 Tech rows; the extra ones
        are inert.  That is recorded rather than "fixed", because removing them
        changes nothing a player can see.
        """
        self.assertEqual(self.audit.SATISFIED_BITS_SET_BY_EXE, {3, 4})

        # Scoped to the Tech state builder, NOT the whole generator: the
        # Details menu builds its own state word and also contains
        # `or edi, 8`, so a file-wide search would report Tech behaviour as
        # intact even after the Tech path stopped setting that bit.
        for game, path in self.audit.GENERATORS.items():
            if not path.is_file():
                continue
            with self.subTest(game=game):
                bits = self.audit.tech_state_bits(path)
                self.assertEqual(
                    bits,
                    {8, 16},
                    f"{game}'s Tech state builder sets {sorted(bits)}, not just "
                    f"the two doubler bits",
                )

        coverage = self.audit.badge_coverage()
        for (game, screen), (rows, badges) in coverage.items():
            with self.subTest(game=game, screen=screen):
                self.assertLessEqual(
                    badges,
                    rows,
                    "more badge controls than rows would leave orphans",
                )


if __name__ == "__main__":
    unittest.main()
