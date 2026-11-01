"""scripts/export_game_mechanics_claims.py, A New Home (VV1): every line the Game Mechanics window renders from
the fixtures is in the claims file, and the file is written under its name with its statuses.  The shared checks
are in tests/game_mechanics_claims_cases.py."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import game_mechanics_claims_cases as cases  # noqa: E402


class Coverage(cases.ClaimsCases, unittest.TestCase):
    GAME = 1


if __name__ == "__main__":
    unittest.main()
