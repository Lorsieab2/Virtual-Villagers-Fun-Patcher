"""scripts/export_game_mechanics_claims.py, New Believers (VV5): every line the Game Mechanics window renders from
the fixtures is in the claims file, and the file is written under its name with its statuses (the owner's own
confirmations among them).  The shared checks are in tests/game_mechanics_claims_cases.py."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import game_mechanics_claims_cases as cases  # noqa: E402


class Coverage(cases.ClaimsCases, unittest.TestCase):
    GAME = 5

    def check_claims_file(self, text: str) -> None:
        super().check_claims_file(text)
        self.assertIn("Status: CONFIRMED BY OWNER", text)


if __name__ == "__main__":
    unittest.main()
