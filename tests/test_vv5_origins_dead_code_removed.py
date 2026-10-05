"""VV5 Origins carries no unreachable code, and every upgrade stays reachable.

The shipped VV5 Origins record is the Task9 one. Its Tech and Detail menus live
in the appended .vv5t9 page; the base .shr payload only keeps what live code
reaches: the two Upgrades-button constructors, the Tech/Detail handlers and
their absolute jumps into the page, the Barrel selector, the two doubler
wrappers and the "Upgrades" label.

Removed as unreachable in every public build:

* .shr: the legacy menus, their dialog, message and record helpers, and their
  strings and price tables;
* .text tail: the Cure/village-wide dispatch helper at 0x494EA0, its 0x494B32
  stub, the 0x494B37 preflight and the 640-byte village-wide extension at
  0x494C20;
* the Task9 page: resolve_manager, mask_load_once, the Time Warp row's own
  clock-only transaction (superseded by the companion), the nop padding after
  unconditional jumps, the unread page header and the strings only those
  read. Inside the page they are zeroed IN PLACE, so no live byte moves --
  the Expanded Time Warp overlay and the Story / Cheat Upgrades price sites
  name page addresses.

These tests render all three public modes, with Origins alone and with the
full public catalog, and run tests/origins_reachability.py over the result.
Every non-zero byte of the .shr payload, the .text-tail range and the Task9
page must be reached, and every Task9 action the menus offer must be reached.
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

STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
MODES = ("stock", "collection_progression", "immediate_fixed")
BASE_ID = "vv5_enable_origins_exclusive_features"
ROUTE_ID = "vv5_origins_village_wide_upgrades"

SHR = (0x7B2000, 0x7B3000)
SHR_CODE_END = 0x7B2D00                  # the .shr string area starts here
TEXT_TAIL = (0x494B32, 0x494FD0)         # where the removed caves lived
PAGE = (0x7C9000, 0x7D1000)
PAGE_CODE_END = 0x7D0000                 # the page's string area starts here
REGIONS = (SHR, TEXT_TAIL, PAGE)
CODE_RANGES = ((SHR[0], SHR_CODE_END), TEXT_TAIL, (PAGE[0], PAGE_CODE_END))

# Every action the two Task9 menus dispatch to, plus the entries themselves.
TASK9_ACTIONS = (
    "tech_entry", "detail_entry", "tech_menu", "detail_menu", "age",
    "time_warp", "mastery", "running", "heal", "island", "barrel",
    "appearance", "complete_collections", "reset_collections", "running_all",
    "mastery_all", "age18_all", "division_parenting", "division_no_parenting",
    "appearance_all", "barrel_close_arm",
)

_renders: dict[tuple[str, str], bytes] = {}
_analyses: dict[tuple[str, str], tuple] = {}
_builder = None


def task9_builder():
    global _builder
    if _builder is None:
        spec = importlib.util.spec_from_file_location(
            "vv5_task9_builder_reach", ROOT / "scripts" / "build_vv5_task9_native_actions.py"
        )
        _builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_builder)
    return _builder


def render(scope: str, mode: str) -> bytes:
    key = (scope, mode)
    if key not in _renders:
        build = next(b for b in vfp.load_builds() if b.id == "vv5")
        if scope == "alone":
            ids = [BASE_ID]
        else:
            public = [p.id for p in vfp.load_public_fun_patches() if p.game_id == "vv5"]
            ids = vfp.resolve_fun_patch_ids(public, game_id="vv5")
        image, _ = vfp.render_patched_bytes(STOCK, build, mode, ids)
        _renders[key] = bytes(image)
    return _renders[key]


def analyse(data: bytes):
    builder = task9_builder()
    # The bighead offset table is read by index, so it is one object.
    objects = {PAGE[0] + builder.OFF["bighead_offsets"]: builder.SIZES["bighead_offsets"]}
    return reach.reach(data, REGIONS, objects, CODE_RANGES)


def analysis(scope: str, mode: str):
    key = (scope, mode)
    if key not in _analyses:
        _analyses[key] = analyse(render(scope, mode))
    return _analyses[key]


def unreached(image, base, live, lo, hi) -> list[str]:
    return reach.unreached(image, base, live, lo, hi)


class VV5OriginsCarriesNoUnreachableCode(unittest.TestCase):
    def test_every_origins_byte_is_reached(self) -> None:
        for scope in ("alone", "full"):
            for mode in MODES:
                with self.subTest(scope=scope, mode=mode):
                    image, base, live = analysis(scope, mode)
                    self.assertEqual(unreached(image, base, live, *SHR), [], ".shr")
                    self.assertEqual(unreached(image, base, live, *TEXT_TAIL), [], ".text tail")
                    self.assertEqual(unreached(image, base, live, *PAGE), [], "Task9 page")

    def test_removed_regions_are_back_to_stock_zero(self) -> None:
        build = next(b for b in vfp.load_builds() if b.id == "vv5")
        for scope in ("alone", "full"):
            for mode in MODES:
                image = render(scope, mode)
                # The image with no patch selected: stock plus the automatic
                # layers (the safety layer's record guards use part of this
                # tail since v1.35.58, scripts/build_record_guards_vv345.py).
                # (With 256 Villagers in the selection, its rescaled rows.)
                table = ["vv5_population_256"] if scope == "full" and any(
                    p.id == "vv5_population_256" for p in vfp.load_public_fun_patches()) else []
                stock, _ = vfp.render_patched_bytes(STOCK, build, mode, table)
                for lo, hi, what in (
                    (0x94B32, 0x94BB0, "Cure stub and village-wide preflight"),
                    (0x94C20, 0x94EA0, "village-wide extension"),
                    (0x94EA0, 0x94FD0, "Cure/village-wide dispatch helper"),
                    (0xDB1C0, 0xDB2C0, "legacy dialog, message and record helpers"),
                    (0xDB2C7, 0xDB600, "legacy Tech menu body"),
                    (0xDB607, 0xDBA00, "legacy Detail menu body"),
                    (0xDBD09, 0xDC000, "legacy strings and price tables"),
                ):
                    with self.subTest(scope=scope, mode=mode, region=what):
                        self.assertEqual(image[lo:hi], stock[lo:hi])
                # Inside the Task9 page (raw 0xF2000 = page+0): zeroed in place.
                for lo, hi, what in (
                    (0x0000, 0x0040, "unread page header"),
                    (0x1147, 0x1218, "Time Warp's own clock-only transaction"),
                    (0x121F, 0x122D, "its cancelled/recheck messages"),
                    (0x123B, 0x1247, "its charge/clock-unknown messages"),
                    (0x6D00, 0x6D80, "mask_load_once"),
                    (0x7087, 0x7099, "SDL_GetWindowFlags"),
                    (0x7124, 0x7134, "ReadMaskSidecar"),
                    (0x7169, 0x71C3, "an unused permanent-change warning"),
                    (0x720B, 0x7261, "the old Time Warp prompt"),
                ):
                    with self.subTest(scope=scope, mode=mode, region=what):
                        self.assertEqual(image[0xF2000 + lo:0xF2000 + hi], bytes(hi - lo))

    def test_every_task9_upgrade_is_reached_from_the_live_hooks(self) -> None:
        builder = task9_builder()
        self.assertNotIn("resolve_manager", builder.OFF)
        for scope in ("alone", "full"):
            for mode in MODES:
                with self.subTest(scope=scope, mode=mode):
                    _, _, live = analysis(scope, mode)
                    missing = [
                        name for name in TASK9_ACTIONS
                        if PAGE[0] + builder.OFF[name] not in live
                    ]
                    self.assertEqual(missing, [])

    def test_the_old_cure_all_write_into_villager_record_0_is_gone(self) -> None:
        # The removed helper's Cure All loop ran `inc dword ptr [0x55490C]`
        # per cured villager: not People Cured (0x51D368) but villager record
        # 0 (0x554190) +0x77C, entry 21 field +0x44 of its action queue.
        bad = bytes.fromhex("FF050C495500")
        for relative in ("data/vv5_origins_feature.json", "data/vv5_task9_native_actions.json"):
            with self.subTest(manifest=relative):
                text = (ROOT / relative).read_text(encoding="utf-8").upper()
                self.assertNotIn(bad.hex().upper(), text)
        for scope in ("alone", "full"):
            for mode in MODES:
                with self.subTest(scope=scope, mode=mode):
                    self.assertNotIn(bad, render(scope, mode))

    def test_the_public_route_adds_nothing_and_removes_nothing(self) -> None:
        # The village-wide row is the player's route to the Origins upgrades;
        # with its dead extension gone it must render exactly as its base.
        route = json.loads((ROOT / "data" / f"{ROUTE_ID}.json").read_text(encoding="utf-8"))
        self.assertEqual(route["patches"], [])
        self.assertEqual(route["dependencies"], [BASE_ID])
        self.assertNotIn("extension_abi", route)
        public = {p.id for p in vfp.load_public_fun_patches() if p.game_id == "vv5"}
        self.assertIn(ROUTE_ID, public)
        build = next(b for b in vfp.load_builds() if b.id == "vv5")
        for mode in MODES:
            with self.subTest(mode=mode):
                with_route, _ = vfp.render_patched_bytes(
                    STOCK, build, mode, vfp.resolve_fun_patch_ids([ROUTE_ID], game_id="vv5")
                )
                self.assertEqual(bytes(with_route), render("alone", mode))


if __name__ == "__main__":
    unittest.main()
