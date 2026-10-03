"""The transparency document counts every edit 256 Villagers makes.

256 Villagers is applied by its own routine (_apply_population_256), not
through `patches`. The generator counted only its `rows` -- "Guarded
executable edits: 570" for The Secret City -- while the same render also
replaces the automatic safety and population-mode rows with its own,
rewrites references inside other selected patches' code, rewrites three PE
header regions and appends a code section (Codex, #509 review). A count that
omits those reads as complete and is not.

The numbers here come from real renders of the exact stock executables, by
owner and kind of record, never from the generator: a test that reused the
code under test could not disagree with it.
"""
from __future__ import annotations

import collections
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as vfp  # noqa: E402

STOCK = ROOT / "research" / "stock-executables"
MODES = ("stock", "collection_progression", "immediate_fixed")
GAMES = ("vv3", "vv4", "vv5")


def _section(feature_id: str) -> str:
    text = (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8")
    for chunk in text.split("\n#### ")[1:]:
        match = re.match(r"[^\n]*?\(`([^`]+)`\)", chunk)
        if match and match.group(1) == feature_id:
            return chunk
    raise AssertionError(f"{feature_id} is not in the transparency document")


def _render(game: str, mode: str, ids: list[str]):
    build = next(b for b in vfp.load_builds() if b.id == game)
    stock = STOCK / build.input_name
    if not stock.exists():
        raise unittest.SkipTest(f"stock executable missing: {stock}")
    ids = vfp.resolve_fun_patch_ids(ids, game_id=game)
    _, applied = vfp.render_patched_bytes(stock, build, mode, ids)
    return applied


def _kinds(applied, owner: str) -> collections.Counter:
    kinds = collections.Counter()
    for record in applied:
        if record.get("owner") != owner:
            continue
        if record.get("virtual_address") is None:
            kinds["header"] += 1
        elif record.get("before") == "":
            kinds["append"] += 1
            kinds["append_bytes"] += len(record["after"]) // 2
        else:
            kinds["code"] += 1
    return kinds


class TransparencyCountsEvery256Edit(unittest.TestCase):
    def test_every_kind_of_256_edit_is_in_the_document(self) -> None:
        for game in GAMES:
            feature = f"{game}_population_256"
            owner = f"feature:{feature}"
            body = json.loads(
                (ROOT / "data" / f"{feature}_feature.json").read_text(encoding="utf-8")
            )["population_256"]
            doc = _section(feature)
            rows = len(body["rows"])
            with self.subTest(game=game):
                self.assertIn(f"- Guarded executable edits: {rows};", doc)
            mode_counts = []
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    applied = _render(game, mode, [feature])
                    kinds = _kinds(applied, owner)
                    self.assertEqual(kinds["code"], rows)
                    self.assertEqual(kinds["header"], 3)
                    self.assertEqual(kinds["append"], 1)
                    self.assertIn("rewrites 3 guarded regions of the PE headers", doc)
                    self.assertIn(f"Appends {kinds['append_bytes']} bytes of code", doc)
                    safety = sum(1 for r in applied if r.get("owner") == "automatic:safety")
                    self.assertIn(
                        f"replaced, in every population mode, by its own {safety} "
                        "guarded safety edits",
                        doc,
                    )
                    mode_counts.append(
                        f"{mode}={sum(1 for r in applied if r.get('owner') == 'automatic:population')}"
                    )
            with self.subTest(game=game, part="modes"):
                self.assertIn(
                    "- Population-mode edits: replaced by its own guarded rows, "
                    + ", ".join(mode_counts),
                    doc,
                )
            # Each composition, rendered with just that patch beside 256: the
            # extra records 256 writes are that patch's rewrites, plus any of
            # 256's own rows that stood aside for it.
            for other in body["compositions"]:
                with self.subTest(game=game, composition=other):
                    applied = _render(game, "stock", [feature, other])
                    kinds = _kinds(applied, owner)
                    yielded = sum(
                        1 for r in body["rows"]
                        if (r.get("yield_to") or {}).get("feature") == other
                    )
                    rewrites = kinds["code"] - (rows - yielded)
                    self.assertGreater(rewrites, 0)
                    self.assertRegex(doc, rf"\(`{re.escape(other)}`\) {rewrites}[,;]")
                    if yielded:
                        self.assertRegex(
                            doc,
                            rf"{yielded} stands? aside when [^`]*\(`{re.escape(other)}`\)",
                        )


if __name__ == "__main__":
    unittest.main()
