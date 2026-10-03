"""A New Home, The Lost Children, The Secret City and The Tree of Life carry no
unreachable Origins code.

Every cave the game's Origins base or village-wide row writes (a row whose
preimage is all zero, including appended sections) is run through
tests/origins_reachability.py in all three public modes, with the
village-wide route alone and with the full public catalog: every non-zero
byte must be reached from the game's own hooks, and no conditional jump may
have a side the code's own earlier tests already ruled out -- a check that
can never fail is dead code too. (New Believers has its own test:
tests/test_vv5_origins_dead_code_removed.py.)

The analysis is path-sensitive. Codex (#506 review) found the first version
followed both sides of every branch, so it passed while The Lost Children's
Tech menu still ended in a Cure call no row could reach: every row from 0 to
5 had been handled and rows 6 and up had gone to the companion before it.
test_the_analysis_sees_through_a_decided_dispatch puts those bytes back and
requires the analysis to report them.

Removed after the same proof:

* A New Home and The Lost Children: the 5-byte "Cure/village-wide dispatch
  stub" at .shr+0x004 nothing calls (every caller calls the Cure entry);
* The Lost Children: the village-wide preflight at raw 0x9A009 nothing calls,
  the `do_village_wide` branch nothing jumps to (zeroed in place), and the
  village-wide ABI header only that preflight read (zeroed);
* The Tree of Life: the status-popup copy at PAYLOAD+0x200 (both menus call
  the copy in the pinned result-helper cave) and the "Upgrades" label the
  native image buttons replaced (zeroed in place).

Removed after the path-sensitive proof (#506 review), all zeroed in place so
no live byte moves:

* every game's Tech menu: the legacy-row tail -- a Cure call after the last
  row test, reached by no row -- and the row tests whose outcome was already
  decided (A New Home and The Tree of Life `cmp ebx, 8; ja`, The Lost
  Children's two row-2 tests);
* the Cure helper's below-row-5 arm (A New Home, The Secret City, The Tree
  of Life) and, in The Lost Children, its whole rows 6-8 dispatch: the menu
  calls Cure directly;
* the village-wide entry's invalid-command return (A New Home, The Secret
  City, The Tree of Life): every caller passes row 6, 7 or 8;
* The Lost Children's whole 1,312-byte village-wide payload -- only that
  rows 6-8 arm called it -- so its public row is now route-only, like New
  Believers'; and the strings only dead code read (A New Home's five
  "Images/mN.png" paths, The Tree of Life's "Full Heal/Cure All Villagers",
  eight of The Lost Children's).
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
import pefile  # noqa: E402

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
        edges: dict = {}
        image, base, live = reach.reach(bytes(data), caves, price_tables(game), caves, edges=edges)
        _cache[key] = (bytes(data), caves, image, base, live, edges)
    return _cache[key]


def manifest(name: str) -> dict:
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


class OriginsCarriesNoUnreachableCode(unittest.TestCase):
    def test_every_origins_cave_byte_is_reached(self) -> None:
        for game in GAMES:
            for scope in ("alone", "full"):
                for mode in MODES:
                    with self.subTest(game=game, scope=scope, mode=mode):
                        _, caves, image, base, live, _ = analysed(game, scope, mode)
                        self.assertTrue(caves)
                        dead = [run for lo, hi in caves for run in reach.unreached(image, base, live, lo, hi)]
                        self.assertEqual(dead, [])

    def test_no_check_has_a_side_that_can_never_happen(self) -> None:
        for game in GAMES:
            for scope in ("alone", "full"):
                for mode in MODES:
                    with self.subTest(game=game, scope=scope, mode=mode):
                        *_, edges = analysed(game, scope, mode)
                        self.assertTrue(edges)
                        decided = {
                            f"{va:#x}": "never taken" if not taken else "always taken"
                            for va, (taken, falls) in edges.items()
                            if not (taken and falls)
                        }
                        self.assertEqual(decided, {})

    def test_the_analysis_sees_through_a_decided_dispatch(self) -> None:
        # The Lost Children's Tech menu as it shipped before #506's review:
        # row 5 to Cure, then rows 1-4 charged and dispatched -- testing for
        # row 2 twice although preflight had already taken it -- and a
        # fallback Cure call that no row could reach. Put back over the
        # current render, the analysis must report exactly that.
        data, caves, *_ = analysed("vv2", "full", "stock")
        image = bytearray(data)
        old_menu = bytes.fromhex(
            "83fb050f84ac0000008b049d904f490083fb0274423987dcea02000f82d00000"
            "002987dcea020083fb010f849300000083fb02742283fb030f849900000083fb"
            "040f849900000083fb057469e88a7d000090e990000000"
        )
        offset = pefile.PE(data=data, fast_load=True).get_offset_from_rva(0x494755 - 0x400000)
        image[offset: offset + len(old_menu)] = old_menu
        edges: dict = {}
        shown, base, live = reach.reach(bytes(image), caves, price_tables("vv2"), caves, edges=edges)
        # The row-5 test after the last row and the Cure call: never run.
        # (A few of their bytes can read as live where a stray 32-bit value
        # elsewhere in the image happens to point at them.)
        dead = {va for va in range(0x494755, 0x4947AC) if shown[va - base] and va not in live}
        self.assertTrue(dead)
        self.assertTrue(dead <= set(range(0x49479C, 0x4947AC)))
        self.assertIn(0x4947A1, dead)                  # call Cure
        # The two row-2 tests can never jump; the row-4 test always does.
        decided = {va: flags for va, flags in edges.items() if not all(flags)}
        self.assertEqual(
            decided, {0x494768: [False, True], 0x494788: [False, True], 0x494796: [True, False]}
        )

    def test_the_removed_rows_and_bytes_stay_removed(self) -> None:
        offsets = {
            game: {p["offset"] for p in manifest(f"{game}_origins_feature.json")["patches"]}
            for game in GAMES
        }
        self.assertNotIn("0x8B004", offsets["vv1"])          # dispatch stub
        self.assertNotIn("0x9A004", offsets["vv2"])          # dispatch stub
        self.assertNotIn("0x9A009", offsets["vv2"])          # village-wide preflight
        # The Lost Children's village-wide row is a route: no bytes, no ABI.
        vv2_wide = manifest("vv2_origins_village_wide_upgrades.json")
        self.assertEqual(vv2_wide["patches"], [])
        self.assertNotIn("extension_abi", vv2_wide)
        self.assertEqual(vv2_wide["dependencies"], ["vv2_enable_origins_exclusive_features"])
        stock = {
            game: reach._load(
                (STOCK / next(b for b in vfp.load_builds() if b.id == game).input_name).read_bytes()
            )[0]
            for game in GAMES
        }
        # (game, VA, length, what) -- zero in every render, and a zero cave
        # in the stock game, so the row that covers it writes zero there.
        zeroed = (
            ("vv1", 0x456ABF, 7, "Tech menu `cmp ebx, 8; ja` (after its short jump)"),
            ("vv1", 0x456B2D, 14, "Tech menu legacy tail"),
            ("vv1", 0x485F70, 0x50, '"Images/mN.png" strings'),
            ("vv1", 0x48D53B, 14, "Cure helper below-row-5 arm"),
            ("vv1", 0x48D1B3, 14, "village-wide invalid-command return"),
            ("vv2", 0x494767, 3, "Tech menu first row-2 test"),
            ("vv2", 0x494787, 3, "Tech menu second row-2 test"),
            ("vv2", 0x494798, 20, "Tech menu legacy tail"),
            ("vv2", 0x494811, 7, "do_village_wide"),
            ("vv2", 0x494DB4, 20, '"Purchased." and "Removed."'),
            ("vv2", 0x494FB8, 0x14, "unread skill-code table"),
            ("vv2", 0x49C530, 0x9D, "Cure helper dispatch and rows 6-8 arm"),
            ("vv2", 0x49C800, 0x520, "village-wide payload"),
            ("vv3", 0x47B66B, 11, "Cure helper below-row-5 arm"),
            ("vv3", 0x4A3672, 14, "Tech menu legacy tail"),
            ("vv3", 0x47B853, 14, "village-wide invalid-command return"),
            ("vv4", 0x48968A, 7, "Tech menu `cmp ebx, 8; ja` (after its short jump)"),
            ("vv4", 0x48978E, 11, "Tech menu legacy tail"),
            ("vv4", 0x489E96, 29, '"Full Heal/Cure All Villagers"'),
            ("vv4", 0x72800B, 11, "Cure helper below-row-5 arm"),
            ("vv4", 0x728253, 14, "village-wide invalid-command return"),
        )
        for mode in MODES:
            for scope in ("alone", "full"):
                images = {game: analysed(game, scope, mode)[2] for game in GAMES}
                for game, va, length, what in zeroed:
                    with self.subTest(mode=mode, scope=scope, game=game, what=what):
                        at = va - 0x400000
                        self.assertEqual(bytes(images[game][at: at + length]), bytes(length))
                        self.assertEqual(bytes(stock[game][at: at + length]), bytes(length))
            with self.subTest(mode=mode):
                vv4 = analysed("vv4", "full", mode)[0]
                self.assertEqual(vv4[0x89573:0x895A5], bytes(0x32))   # popup copy
                self.assertEqual(vv4[0x89D73:0x89D7C], bytes(9))      # "Upgrades"


if __name__ == "__main__":
    unittest.main()
