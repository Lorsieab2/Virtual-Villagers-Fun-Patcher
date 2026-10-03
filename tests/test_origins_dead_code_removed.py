"""A New Home, The Lost Children, The Secret City and The Tree of Life carry no
unreachable Origins code.

Every cave the game's Origins base or village-wide row writes (a row whose
preimage is all zero, including appended sections) is run through
tests/origins_reachability.py in all three public modes, with the
village-wide route alone and with the full public catalog: every non-zero
byte must be reached from the game's own hooks. (New Believers has its own,
stricter test: tests/test_vv5_origins_dead_code_removed.py.)

Removed after the same proof:

* A New Home and The Lost Children: the 5-byte "Cure/village-wide dispatch
  stub" at .shr+0x004 nothing calls (every caller calls the Cure entry);
* The Lost Children: the village-wide preflight at raw 0x9A009 nothing calls,
  the `do_village_wide` branch nothing jumps to (zeroed in place), and the
  village-wide ABI header only that preflight read (zeroed);
* The Tree of Life: the status-popup copy at PAYLOAD+0x200 (both menus call
  the copy in the pinned result-helper cave) and the "Upgrades" label the
  native image buttons replaced (zeroed in place).
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
import vv_fun_patcher as vfp  # noqa: E402
import origins_reachability as reach  # noqa: E402

STOCK = ROOT / "research" / "stock-executables"
MODES = ("stock", "collection_progression", "immediate_fixed")
GAMES = ("vv1", "vv2", "vv3", "vv4")

_story = None
_cache: dict[tuple[str, str, str], tuple] = {}


def price_tables(game: str) -> dict[int, int]:
    """The Origins price tables, read by index, are whole data objects."""
    global _story
    if _story is None:
        spec = importlib.util.spec_from_file_location(
            "story_tables_reach", ROOT / "scripts" / "build_story_cheat_upgrades_features.py"
        )
        _story = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_story)
    return {va: 4 * count for va, count in _story.PRICE_TABLES.get(game, [])}


def analysed(game: str, scope: str, mode: str):
    key = (game, scope, mode)
    if key not in _cache:
        build = next(b for b in vfp.load_builds() if b.id == game)
        if scope == "alone":
            ids = vfp.resolve_fun_patch_ids([f"{game}_origins_village_wide_upgrades"], game_id=game)
        else:
            public = [p.id for p in vfp.load_public_fun_patches() if p.game_id == game]
            ids = vfp.resolve_fun_patch_ids(public, game_id=game)
        data, applied = vfp.render_patched_bytes(STOCK / build.input_name, build, mode, ids)
        caves = reach.owned_caves(
            applied,
            {f"feature:{game}_enable_origins_exclusive_features", f"feature:{game}_origins_village_wide_upgrades"},
        )
        image, base, live = reach.reach(bytes(data), caves, price_tables(game), caves)
        _cache[key] = (bytes(data), caves, image, base, live)
    return _cache[key]


def manifest(name: str) -> dict:
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


class OriginsCarriesNoUnreachableCode(unittest.TestCase):
    def test_every_origins_cave_byte_is_reached(self) -> None:
        for game in GAMES:
            for scope in ("alone", "full"):
                for mode in MODES:
                    with self.subTest(game=game, scope=scope, mode=mode):
                        _, caves, image, base, live = analysed(game, scope, mode)
                        self.assertTrue(caves)
                        dead = [run for lo, hi in caves for run in reach.unreached(image, base, live, lo, hi)]
                        self.assertEqual(dead, [])

    def test_the_removed_rows_and_bytes_stay_removed(self) -> None:
        offsets = {
            game: {p["offset"] for p in manifest(f"{game}_origins_feature.json")["patches"]}
            for game in GAMES
        }
        self.assertNotIn("0x8B004", offsets["vv1"])          # dispatch stub
        self.assertNotIn("0x9A004", offsets["vv2"])          # dispatch stub
        self.assertNotIn("0x9A009", offsets["vv2"])          # village-wide preflight
        vv2_wide = manifest("vv2_origins_village_wide_upgrades.json")
        self.assertEqual(bytes.fromhex(vv2_wide["patches"][0]["after"])[:0x20], bytes(0x20))
        self.assertIsNone(vv2_wide["extension_abi"]["signature"])
        for mode in MODES:
            with self.subTest(mode=mode):
                vv2 = analysed("vv2", "full", mode)[0]
                self.assertEqual(vv2[0x94811:0x94818], bytes(7))      # do_village_wide
                vv4 = analysed("vv4", "full", mode)[0]
                self.assertEqual(vv4[0x89573:0x895A5], bytes(0x32))   # popup copy
                self.assertEqual(vv4[0x89D73:0x89D7C], bytes(9))      # "Upgrades"


if __name__ == "__main__":
    unittest.main()
