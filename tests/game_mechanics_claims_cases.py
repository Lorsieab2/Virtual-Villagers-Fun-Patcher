"""Shared checks for the Game Mechanics claims files (scripts/export_game_mechanics_claims.py): one claims file per
game that covers every line the Game Mechanics window can render, each with its status, evidence and patches.

Not a test file itself.  Each game has its own test file (tests/test_export_game_mechanics_claims_vv<N>.py), so
CI's shards (scripts/ci_test_shard.py, which deal out whole files) can run the five games' slow claims side by
side instead of one shard building all five in a row."""
from __future__ import annotations

import gzip
import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_game_mechanics as gm  # noqa: E402
import vv_tribe_rename  # noqa: E402

spec = importlib.util.spec_from_file_location("export_claims", ROOT / "scripts" / "export_game_mechanics_claims.py")
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)

_CLAIMS: dict[int, dict] = {}
MOMENTS = (1_785_000_000.0, 1_791_000_000.0, 1_850_000_000.0)


def claims(game: int) -> dict:
    """export.claims(game), built once per process."""
    if game not in _CLAIMS:
        _CLAIMS[game] = export.claims(game)
    return _CLAIMS[game]


class ClaimsCases:
    """Mixed into one unittest.TestCase per game; GAME is the game it covers."""

    GAME: int = 0

    def page(self, game: int, data: bytes, now: float, features=None) -> list[gm.Fact]:
        base = next(item.base for item in vv_tribe_rename.GAMES if item.number == game)
        root = Path(tempfile.mkdtemp(prefix="gmc"))
        self.addCleanup(shutil.rmtree, root, True)
        folder = root / base
        folder.mkdir()
        (folder / f"{base}1.ldw").write_bytes(data)
        games = []
        if features is not None:
            game_folder = root / "g" / base
            (game_folder / "Virtual Villagers Fun Patcher Files").mkdir(parents=True)
            (game_folder / f"{base}.exe").write_bytes(b"MZ")
            (game_folder / "Virtual Villagers Fun Patcher Files" / "VVFP Transparency Log.txt").write_text(
                export.HASH_LINE.format(name=base) + "".join(f"- Optional feature: x [{fid}]\n" for fid in features),
                encoding="utf-8")
            games = [game_folder]
        return gm.read(folder, game, 1, games, now=now)

    def assert_covered(self, game: int, facts: list[gm.Fact]) -> None:
        known = claims(game)
        for fact in facts:
            if fact.group == gm.SOURCES:
                continue
            self.assertIn(export.template(fact.text), known.get(fact.group, {}), f"{fact.group}: {fact.text}")

    def test_every_fixture_line_at_another_moment(self) -> None:
        saves = export.fixture_saves(self.GAME)
        self.assertTrue(saves, f"no fixture saves for game {self.GAME}")
        for path in saves:
            with self.subTest(save=path.name):
                data = gzip.decompress(path.read_bytes())
                for now in MOMENTS:
                    self.assert_covered(self.GAME, self.page(self.GAME, data, now))

    def check_claims_file(self, text: str) -> None:
        """This game's own checks of its claims file; every game's file names a status for its lines."""
        self.assertIn("    Status: ", text)

    def test_files_name_status_and_evidence(self) -> None:
        """The exporter writes the five games' files under their names; this game's file is its real claims.
        The other games' claims are each built and checked by their own game's test file."""
        out = Path(tempfile.mkdtemp(prefix="gmo"))
        self.addCleanup(shutil.rmtree, out, True)
        real = claims(self.GAME)
        built = []

        def only_this_game(game: int) -> dict:
            built.append(game)
            return real if game == self.GAME else {group: {} for group in gm.GROUPS}

        with mock.patch.object(export, "claims", only_this_game):
            self.assertEqual(export.main([str(out)]), 0)
            expected = export.render(self.GAME)
        self.assertEqual(sorted(set(built)), [1, 2, 3, 4, 5])
        names = sorted(p.name for p in out.iterdir())
        self.assertEqual(names, sorted(export.file_name(n) for n in range(1, 6)))
        text = (out / export.file_name(self.GAME)).read_text(encoding="utf-8")
        self.assertEqual(text, expected)
        self.check_claims_file(text)
