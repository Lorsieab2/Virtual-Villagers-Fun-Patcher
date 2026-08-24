"""Static regression tests for the VV4 Heathen-mask overlay (SDL-blit design).

A render hook can only be *proven* in-game, but the pieces that feed it are
statically checkable and easy to break silently. The mask overlay is fully
cosmetic and NON-INVASIVE:

* Storage/logic live in the companion DLL: an index-keyed side-table, a
  per-frame clear-on-death sweep keyed on the game's own free-slot flag
  (record+0x1CC4), and a gender+name fingerprint backstop. NO villager-record
  bytes are written, and NO game atlas/row is altered.
* The exe carries only three tiny caves in the free RWX .shr tail (resolve /
  present-surface-cache / head-draw) plus the call-site redirects. It must not
  touch any other upgrade, menu, or patch: no head-atlas row-count bumps, no
  atlas swaps, and the detail-portrait draw is left unhooked for now.
* The render atlas (Images/vvfp_mask_atlas.png) ships as an added file; stock
  atlases are untouched.

None of this needs the game executable.
"""
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLL_SOURCE = ROOT / "native" / "vv4_origins_icons" / "vv4_origins_icons.c"
DLL_DEF = ROOT / "native" / "vv4_origins_icons" / "vv4_origins_icons.def"
IMAGE_BASE = 0x400000

# Cave VAs (mirror scripts/build_vv4_origins_feature.py).
MASK_RESOLVE_VA = 0x728D90
MASK_PRESENT_VA = 0x728DE0
MASK_HEAD_VA = 0x728E10
MASK_PRESENT_SITE = 0x409458
MASK_PRESENT_CALLEE = 0x4046F0
MASK_DRAW_THUNK_VA = 0x409A70
MASK_HEAD_CALL_SITES = (0x45F702, 0x45F9CA)


def _rel_target(after_hex: str, site_va: int) -> int:
    b = bytes.fromhex(after_hex)
    rel = int.from_bytes(b[1:5], "little", signed=True)
    return site_va + 5 + rel


class DllStorageContractTests(unittest.TestCase):
    """The DLL owns the mask state; it must key by index, sweep on the free-slot
    flag, fingerprint on STABLE fields only, and never write a record byte."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.c = DLL_SOURCE.read_text(encoding="utf-8", errors="replace")

    def test_side_table_is_index_keyed_with_the_confirmed_layout(self) -> None:
        # Base is the game's own accessor result FUN_00466040(0x50E568)=0x50E5AC,
        # NOT 0x5101EC (that older value mis-keyed every record -> no masks).
        self.assertIn("#define VV_REC_ARRAY_BASE 0x50E5ACu", self.c)
        self.assertIn("#define VV_REC_STRIDE     0x2E3Cu", self.c)
        self.assertIn("g_mask_by_index[VV_MAX_VILLAGERS]", self.c)

    def test_clear_on_death_sweep_uses_the_free_slot_flag(self) -> None:
        # record+0x1CC4 is the game's own occupied flag (0 = free/dead), from
        # the villager-creation routine FUN_00466270.
        self.assertIn("#define VV_OCCUPIED_OFFSET 0x1CC4", self.c)
        self.assertIn("static void vv_mask_sweep(void)", self.c)
        self.assertIn("rec[VV_OCCUPIED_OFFSET] != 0", self.c)
        # A "seen alive" latch distinguishes a death (clear the mask) from a
        # not-yet-populated slot (menu / village not loaded) so a mask restored
        # from the sidecar before its villager exists is not wiped.
        self.assertIn("g_slot_seen_alive", self.c)
        # The sweep runs once per frame from the present-path surface cache.
        cache = self.c.split("Vv4MaskCacheSurface(void *surface)", 1)[1].split("\n}", 1)[0]
        self.assertIn("vv_mask_sweep();", cache)

    def test_sidecar_persistence_is_save_safe_and_onedrive_aware(self) -> None:
        # Persisted next to the saves via CSIDL_PERSONAL (follows OneDrive
        # redirection), in a SEPARATE file -- never inside the .ldw.
        self.assertIn("SHGetSpecialFolderPathA", self.c)
        self.assertIn("CSIDL_PERSONAL", self.c)
        self.assertIn("vvfp_masks.dat", self.c)
        self.assertIn("\\\\LDW", self.c)               # Documents\LDW\<basename>\
        # Written on chooser OK, read once lazily on the first present frame.
        self.assertIn("vv_write_mask_sidecar();", self.c)
        self.assertIn("vv_read_mask_sidecar();", self.c)
        self.assertIn('WriteFile(h, "VVMK", 4', self.c)   # magic + versioned header
        # Read validates magic + version + count before trusting the file.
        read = self.c.split("vv_read_mask_sidecar(void)", 1)[1].split("\n}", 1)[0]
        self.assertIn("VV_SIDECAR_VERSION", read)
        self.assertIn("VV_MAX_VILLAGERS", read)

    def test_fingerprint_uses_stable_fields_only(self) -> None:
        fp = self.c.split("vv_fingerprint(", 1)[1].split("}", 1)[0]
        self.assertIn("VV_SEX_OFFSET", fp)     # gender (stable)
        self.assertIn("VV_NAME_OFFSET", fp)    # name (stable)
        # Mutable fields must NOT be in the fingerprint (they'd false-invalidate
        # a living villager's mask when they change via upgrades/aging).
        self.assertNotIn("LIKES", fp)
        self.assertNotIn("DISLIKE", fp)
        self.assertNotIn("HEAD_OFFSET", fp)
        self.assertNotIn("BODY_OFFSET", fp)

    def test_no_villager_record_byte_is_written_for_the_mask(self) -> None:
        # The abandoned design stored the mask in the record at +0x1BC4 (which
        # is actually name char #4). Ensure no such write survives.
        self.assertNotIn("0x1BC4", self.c)
        self.assertNotIn("VV_MASK_OFFSET", self.c)

    def test_mask_table_is_none_plus_five(self) -> None:
        self.assertIn("#define VV_MASK_COUNT 6", self.c)
        table = self.c.split("g_mask_names[VV_MASK_COUNT] = {", 1)[1].split("};", 1)[0]
        self.assertEqual(table.count('"') // 2, 6)
        for label in ("(None)", "Blue Mask", "Orange Mask",
                      "Red Mask", "Purple Mask", "Tribal Chief Mask"):
            self.assertIn(label, table)

    def test_render_exports_are_declared(self) -> None:
        d = DLL_DEF.read_text(encoding="utf-8", errors="replace")
        self.assertIn("Vv4MaskCacheSurface=_Vv4MaskCacheSurface@4 @110", d)
        self.assertIn("Vv4MaskDrawRecord=_Vv4MaskDrawRecord@20 @112", d)


class OriginsManifestIntegrationTests(unittest.TestCase):
    """The mask render side must be wired into the shipped origins feature via
    the three .shr caves and the call-site redirects -- and NOTHING else."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.m = json.loads((ROOT / "data" / "vv4_origins_feature.json").read_text("utf-8"))
        cls.by_off = {int(p["offset"], 0): p for p in cls.m["patches"]}

    def test_present_site_is_redirected_to_the_surface_cache_cave(self) -> None:
        p = self.by_off[MASK_PRESENT_SITE - IMAGE_BASE]
        # was `call 0x4046f0`, still a call, now into the present cave.
        self.assertEqual(_rel_target(p["before"], MASK_PRESENT_SITE), MASK_PRESENT_CALLEE)
        self.assertTrue(p["after"].upper().startswith("E8"))
        self.assertEqual(_rel_target(p["after"], MASK_PRESENT_SITE), MASK_PRESENT_VA)

    def test_both_head_twins_are_redirected_to_the_head_cave(self) -> None:
        for site in MASK_HEAD_CALL_SITES:
            p = self.by_off[site - IMAGE_BASE]
            # was `call 0x409a70` (the head-draw thunk), still a call.
            self.assertEqual(_rel_target(p["before"], site), MASK_DRAW_THUNK_VA)
            self.assertTrue(p["after"].upper().startswith("E8"))
            self.assertEqual(_rel_target(p["after"], site), MASK_HEAD_VA)

    def test_three_caves_live_in_zeroed_shr_space(self) -> None:
        for off in (0xCCD90, 0xCCDE0, 0xCCE10):   # resolve / present / head
            cave = self.by_off[off]
            self.assertEqual(set(cave["before"]), {"0"})   # was zero-filled .shr
            self.assertGreater(len(bytes.fromhex(cave["after"])), 0)

    def test_non_invasive_no_row_bumps_and_portrait_unhooked(self) -> None:
        # No head-atlas row-count bumps (male/female/bigheads) -- the old
        # append-rows approach is gone.
        for off in (0xC3C24, 0xC3B94, 0xC3CB4):
            self.assertNotIn(off, self.by_off, f"row-count field {off:#x} must not be patched")
        # Detail-portrait head-draw call site stays unhooked (follow-up).
        self.assertNotIn(0x3D040, self.by_off)

    def test_render_atlas_ships_as_an_added_file(self) -> None:
        cf = self.m["companion_files"]
        self.assertEqual(cf[0]["destination"], "VVFP VV4 Origins Icons.dll")
        atlas = next((e for e in cf if e["destination"] == "Images/vvfp_mask_atlas00.png"), None)
        self.assertIsNotNone(atlas, "render atlas companion missing")
        self.assertEqual(
            hashlib.sha256((ROOT / atlas["source"]).read_bytes()).hexdigest().upper(),
            atlas["sha256"])
        # Added file -> no atlas SWAP fields (we do not overwrite a stock atlas).
        self.assertNotIn("restore_source", atlas)
        self.assertNotIn("preimage_sha256", atlas)

    def test_no_stock_head_atlas_is_swapped(self) -> None:
        for e in self.m["companion_files"]:
            self.assertNotIn("heads", e["destination"],
                             f"must not swap a stock head atlas: {e['destination']}")

    def test_isolated_mask_sheet_ships_for_the_chooser_preview(self) -> None:
        cf = self.m["companion_files"]
        sheet = next((e for e in cf if e["destination"] == "Images/vvfp_mask_preview.png"), None)
        self.assertIsNotNone(sheet, "chooser preview sheet missing")
        self.assertEqual(
            hashlib.sha256((ROOT / sheet["source"]).read_bytes()).hexdigest().upper(),
            sheet["sha256"])


class ChangeAppearanceForAllTests(unittest.TestCase):
    """The Tech-screen 'Change Appearance for All' (450k) upgrade: a self-
    contained DLL dialog + apply engine + export, wired to a 14th menu row
    entirely in the DLL (no payload/exe change)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.c = DLL_SOURCE.read_text(encoding="utf-8", errors="replace")
        cls.rc = (ROOT / "native" / "vv4_origins_icons" / "vv4_origins_icons.rc").read_text(
            encoding="utf-8", errors="replace")
        cls.d = DLL_DEF.read_text(encoding="utf-8", errors="replace")

    def test_export_declared(self) -> None:
        self.assertIn("ShowVv4AppearanceForAll=_ShowVv4AppearanceForAll@0 @113", self.d)

    def test_dialog_214_matches_mockup(self) -> None:
        self.assertIn("214 DIALOGEX", self.rc)
        for cap in ("Male Villagers", "Female Villagers",
                    "Mask Distribution (all villagers)",
                    "Village-wide Single Mask Color",
                    "Off - use the per-sex Mask selectors above",
                    "VV5-style", "Random", "Equal Colors",
                    "None (remove all masks)", "Blue", "Orange", "Red",
                    "Purple", "Chief",
                    "OK deducts 450,000 tech points"):
            self.assertIn(cap, self.rc, cap)

    def test_menu_row_13_is_wired_in_dll_only(self) -> None:
        # 14th tech row present in dialog 201 (Buy id 1013) + name/cost tables.
        self.assertIn('PUSHBUTTON  "Buy", 1013', self.rc)
        self.assertIn('"Change Appearance for All"', self.c)
        self.assertIn('"450,000"', self.c)
        self.assertIn("ID_BUY_LAST = 1013", self.c)
        # Row 13 handled inside the menu (self-contained), not via payload.
        self.assertIn("ShowVv4AppearanceForAll();", self.c)
        self.assertIn("#define ID_FORALL_ROW 13", self.c)

    def test_apply_engine_covers_all_modes(self) -> None:
        eng = self.c.split("vv4_apply_for_all(void)", 1)[1].split("\n}", 1)[0]
        # per-sex head/body writes + mask via the safe side-table
        self.assertIn("VV_HEAD_OFFSET", eng)
        self.assertIn("VV_CLOTHING_OFFSET", eng)
        self.assertIn("vv_set_mask", eng)
        # distribution modes
        self.assertIn("FA_MODE_OFF", eng)
        self.assertIn("FA_MODE_VV5", eng)
        self.assertIn("FA_MODE_RANDOM", eng)
        self.assertIn("FA_MODE_EQUAL", eng)
        # skips empty slots + persists
        self.assertIn("VV_OCCUPIED_OFFSET", eng)
        self.assertIn("vv_write_mask_sidecar", eng)

    def test_charge_uses_confirmed_tech_abi(self) -> None:
        # affordability check + charge via the same ABI the payload rows use.
        self.assertIn("0x4D6F88", self.c)
        self.assertIn("450000", self.c)
        self.assertIn("0x41E300", self.c)


if __name__ == "__main__":
    unittest.main()
