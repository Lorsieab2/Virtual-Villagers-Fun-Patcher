"""Static regression tests for the VV4 Heathen-mask overlay (SDL-blit design).

A render hook can only be *proven* in-game, but the pieces that feed it are
statically checkable and easy to break silently. The mask overlay is fully
cosmetic and NON-INVASIVE:

* Storage/logic live in the companion DLL: an index-keyed side-table, a
  per-frame clear-on-death sweep keyed on the game's own free-slot flag
  (record+0x1CC4), and a gender+name fingerprint backstop. NO villager-record
  bytes are written, and NO game atlas/row is altered.
* The exe carries four tiny caves (the reclaimed Details head gap plus resolve /
  present-surface-cache / world-draw caves) plus the call-site redirects. It
  must not touch any other upgrade, menu, or patch: no head-atlas row-count
  bumps, no atlas swaps, and the proven-wrong 0x45F965 route is absent.
* Separate village (8-facing) and VV5-identical Details (3-facing) mask atlases
  ship as added files; stock atlases are untouched.

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
MASK_HEAD_VA = 0x7287A1
MASK_HEAD_FILE_OFFSET = 0xCC7A1
MASK_PRESENT_SITE = 0x409458
MASK_PRESENT_CALLEE = 0x4046F0
MASK_DRAW_THUNK_VA = 0x409A70
MASK_DRAW_REAL_VA = 0x408C40
MASK_HEAD_CALL_SITES = (0x45F702,)
MASK_SAVE_SLOT_SITE = 0x403670
MASK_SAVE_SLOT_FILE_OFFSET = 0x3670
MASK_SAVE_SLOT_SCRATCH = 0xCCFCC
MASK_SAVE_SLOT_CAVE = 0xCCFD0
MASK_WORLD_SITE = 0x468263
MASK_WORLD_CAVE_FILE_OFFSET = 0xCCEB0
MASK_DY_FILE_OFFSET = 0xCCFC4
MASK_DETAILS_TABLE_FILE_OFFSET = 0xCCA40
DETAIL_FALSE_SITE = 0x45F965
DETAIL_FALSE_OLD_SCRATCH_OFFSETS = (0xCCA28, 0xCCA30, 0xCCA34)


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
        # The stock answer is 0x50E5AC (the manager 0x50E568 + 0x44); with 256
        # Villagers it is read from the executable (vv4_villager_table.h).
        self.assertIn("#define VV_REC_ARRAY_BASE vv_rec_base()", self.c)
        self.assertIn("g_vv_rec_base = 0x400000u + rva + 0x44u;", self.c)
        locator = (DLL_SOURCE.parent.parent / "shared" / "vv4_villager_table.h").read_text(encoding="utf-8")
        self.assertIn("#define VV4_STOCK_MANAGER_RVA 0x10E568u", locator)
        self.assertIn("#define VV_REC_STRIDE     0x2E3Cu", self.c)
        self.assertIn("g_mask_by_index[VV_MAX_VILLAGERS]", self.c)
        # Every walk over records stops at the executable's slot count.
        sweep = self.c.split("static int vv_mask_sweep(void) {", 1)[1].split("\n}", 1)[0]
        self.assertIn("int slots = vv_slots();", sweep)
        self.assertIn("for (idx = 0; idx < slots; idx++) {", sweep)

    def test_clear_on_death_sweep_uses_the_free_slot_flag(self) -> None:
        # record+0x1CC4 is the game's own occupied flag (0 = free/dead), from
        # the villager-creation routine FUN_00466270.
        self.assertIn("#define VV_OCCUPIED_OFFSET 0x1CC4", self.c)
        self.assertIn("static int vv_mask_sweep(void)", self.c)
        self.assertIn("rec[VV_OCCUPIED_OFFSET] != 0", self.c)
        # A "seen alive" latch distinguishes a death (clear the mask) from a
        # not-yet-populated slot (menu / village not loaded) so a mask restored
        # from the sidecar before its villager exists is not wiped.
        self.assertIn("g_slot_seen_alive", self.c)
        self.assertIn("g_slot_identity_ready", self.c)
        # The sweep runs once per frame from the present-path surface cache.
        cache = self.c.split("Vv4MaskCacheSurface(void *surface)", 1)[1].split("\n}", 1)[0]
        self.assertIn("vv_mask_sweep();", cache)

    def test_sidecar_persistence_is_save_safe_and_onedrive_aware(self) -> None:
        # Persisted next to the saves via CSIDL_PERSONAL (follows OneDrive
        # redirection), in a SEPARATE file -- never inside the .ldw.
        self.assertIn("SHGetSpecialFolderPathA", self.c)
        self.assertIn("CSIDL_PERSONAL", self.c)
        self.assertIn("Village Masks - Save ", self.c)
        self.assertIn(".dat", self.c)
        self.assertNotIn('"\\\\vvfp_masks.dat"', self.c)
        self.assertIn("\\\\LDW", self.c)               # Documents\LDW\<basename>\
        # Written on chooser OK, read once lazily on the first present frame.
        self.assertIn("vv_write_mask_sidecar();", self.c)
        # The reader now REPORTS whether the load settled, so the caller
        # latches only a settled one; a bare call would discard that.
        # assertIn would print the whole 137KB source on failure and bury
        # the finding; assert on a boolean instead.
        self.assertTrue(
            "g_sidecar_loaded = vv_read_mask_sidecar();" in self.c,
            "the latch is set without regard to whether the load settled",
        )
        self.assertIn('parts[0] = "VVMK";            sizes[0] = 4;', self.c)   # magic + versioned header
        # Read validates magic + version + count before trusting the file.
        read = self.c.split("static int vv_read_mask_sidecar(void) {", 1)[1].split("\n}", 1)[0]
        # A REFUSED PATH LEAVES THE LOAD PENDING. The builder refuses when
        # a legacy sidecar exists and will not move, so the masks are still
        # on disk under the old name. Latching there left an empty table
        # marked loaded, and the next write migrated the real file and
        # overwrote it. Found in review.
        refusal = read.split("vv_build_sidecar_path(path, g_current_slot))", 1)
        self.assertEqual(len(refusal), 2, "the path guard moved")
        refused = refusal[1][:refusal[1].index("\n    }")]
        self.assertIn("vv_sidecar_gate_block(&g_mask_gate);", refused)
        self.assertIn("return 0;", refused)
        # The magic/version/count check is the validator vv_sidecar_load runs.
        self.assertIn("vv_mask_sidecar_valid, NULL);", read)
        valid = self.c.split("static int vv_mask_sidecar_valid(", 1)[1].split("\n}", 1)[0]
        self.assertIn("VV_SIDECAR_VERSION", valid)
        # The count is the writing build's slot count: 150, or 256 from the
        # 256 Villagers build; either is read.
        self.assertIn("vv_mask_sidecar_count_ok(vv_sidecar_u32(data + 8))", valid)
        self.assertIn("return count == 150u || count == 256u;", self.c)
        self.assertIn("data[0] == 'V' && data[1] == 'V' && data[2] == 'M' && data[3] == 'K'", valid)

    def test_save_slot_namespaces_and_resets_sidecar_state(self) -> None:
        self.assertIn("#define VV4_MASK_SAVE_SLOT_VA 0x728FCCu", self.c)
        self.assertIn("g_current_slot", self.c)
        self.assertIn("g_sidecar_loaded", self.c)
        self.assertIn("vv_sync_save_slot();", self.c)
        sync = self.c.split("static void vv_sync_save_slot(void)", 1)[1].split("\n}", 1)[0]
        self.assertIn("vv_clear_mask_state();", sync)
        self.assertIn("g_sidecar_loaded = (slot == 0) ? 1 : 0;", sync)
        self.assertIn("slot < 1 || slot > 5", self.c)
        self.assertIn("name[sizeof(\"Village Masks - Save \") - 1] = (char)('0' + slot);", self.c)

    def test_sidecar_write_is_transactional_with_exact_four_writes(self) -> None:
        write = self.c.split("static void vv_write_mask_sidecar(void) {", 1)[1].split(
            "static int vv_read_mask_sidecar(void) {", 1
        )[0]
        # The temp-file / checked-write / flush / replace sequence now lives in
        # native/shared/sidecar_io.h, shared by all five games and exercised
        # against real files by tests/test_mask_sidecar_durability.py.  Here:
        # the format remains magic, header, mask table, fingerprint table --
        # four parts, published in one atomic call.
        for expected in (
            'parts[0] = "VVMK";            sizes[0] = 4;',
            "parts[1] = header;            sizes[1] = sizeof(header);",
            "header[1] = (unsigned int)vv_slots();",
            "parts[2] = g_mask_by_index;   sizes[2] = header[1];",
            "parts[3] = g_mask_fp;         sizes[3] = header[1] * (DWORD)sizeof(unsigned int);",
            "vv_sidecar_publish(&g_mask_gate, path, parts, sizes, g_fp_version == 2u ? 4 : 5);",
            "parts[4] = g_mask_roster;     sizes[4] = header[1] * (DWORD)sizeof(unsigned int);",
        ):
            self.assertIn(expected, write)
        for raw in ("CreateFileA", "WriteFile(", "MoveFileExA", "DeleteFileA(path);"):
            self.assertNotIn(raw, write)
        # Never before this slot's load settled.
        self.assertLess(write.index("vv_sidecar_gate_ready(&g_mask_gate, g_current_slot)"),
                        write.index("vv_build_sidecar_path(path, g_current_slot)"))
        header = (DLL_SOURCE.parent.parent / "shared" / "sidecar_io.h").read_text(encoding="utf-8")
        publish = header[header.index("static int vv_sidecar_publish("):]
        self.assertIn('lstrcatA(tmp, ".tmp");', publish)
        self.assertIn("|| wrote != sizes[i]) {", publish)
        self.assertLess(publish.index("FlushFileBuffers(h)"), publish.index("MoveFileExA(tmp, path,"))
        self.assertIn("MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH", publish)

    def test_sidecar_path_checks_the_complete_max_path_budget_before_appending(self) -> None:
        builder = self.c.split("static int vv_build_sidecar_path(char *out, int slot)", 1)[1].split(
            "\n}", 1
        )[0]
        guard = 'lstrlenA(out) + (int)(sizeof("\\\\LDW\\\\") - 1) + lstrlenA(base) +'
        # The caller bounds the loose path in the Data folder; whether the
        # masks' own folder (and the set-aside reserve) still fits is
        # vv_data_file_path's to decide (native/shared/data_subfolder.h).
        suffix = '(int)sizeof("\\\\" VV_DATA_FOLDER "\\\\Village Masks - Save 0.dat") > MAX_PATH'
        self.assertIn("vv_data_file_path(out, MAX_PATH, VV_DATA_SUB_MASKS, name, VV_DATA_RESERVE)", builder)
        self.assertIn(guard, builder)
        self.assertIn(suffix, builder)
        # sizeof(suffix) includes the NUL. The guard must precede every
        # unbounded append, including the otherwise-vulnerable first "\\LDW".
        self.assertLess(builder.index(guard), builder.index('lstrcatA(out, "\\\\LDW");'))
        # The length repair must not broaden or rename the existing slot files.
        self.assertIn("slot < 1 || slot > 5", builder)
        self.assertIn("name[sizeof(\"Village Masks - Save \") - 1] = (char)('0' + slot);", builder)
        self.assertIn('lstrcpyA(name, "Village Masks - Save 0.dat");', builder)
        self.assertIn("vv_data_file_path(out, MAX_PATH, VV_DATA_SUB_MASKS, name,", builder)

    def test_details_has_a_dedicated_vv5_style_three_facing_atlas(self) -> None:
        loader = self.c.split("static void vv_ensure_bighead_atlas(void)", 1)[1].split(
            "/* Head-draw caves call this", 1
        )[0]
        self.assertIn('atlas_name[] = "vvfp_bighead_mask_atlas"', loader)
        self.assertIn("push 5", loader)  # five mask-colour rows
        self.assertIn("push 3", loader)  # right/front/left columns
        self.assertIn("VV_BIGHEAD_ATLAS_SLOT_VA", loader)
        getter = self.c.split("Vv4MaskGetForRecord(unsigned char *villager)", 1)[1].split(
            "\n}", 1
        )[0]
        self.assertIn("vv_ensure_bighead_atlas();", getter)

    def test_sweep_persists_confirmed_free_slot_clears(self) -> None:
        cache = self.c.split("Vv4MaskCacheSurface(void *surface)", 1)[1].split("\n}", 1)[0]
        self.assertIn("cleared = vv_mask_sweep();", cache)
        self.assertIn("if (cleared && g_current_slot > 0)", cache)
        self.assertIn("vv_write_mask_sidecar();", cache)

    def test_every_mask_entrypoint_prepares_before_table_access(self) -> None:
        for signature, table_token in (
            ("static int vv_get_mask(", "g_mask_by_index[idx]"),
            ("static void vv_set_mask(", "g_mask_by_index[idx]"),
        ):
            body = self.c.split(signature, 1)[1].split("\n}", 1)[0]
            self.assertIn("vv_prepare_mask_state();", body, signature)
            self.assertLess(
                body.index("vv_prepare_mask_state();"),
                body.index(table_token),
                signature,
            )
        cache = self.c.split("Vv4MaskCacheSurface(void *surface)", 1)[1].split("\n}", 1)[0]
        self.assertIn("vv_prepare_mask_state();", cache)
        self.assertLess(cache.index("vv_prepare_mask_state();"), cache.index("vv_mask_sweep();"))
        write = self.c.split("static void vv_write_mask_sidecar(void) {", 1)[1].split("\n}", 1)[0]
        self.assertIn("vv_prepare_mask_state();", write)
        self.assertIn("vv_build_sidecar_path(path, g_current_slot)", write)

    def test_fingerprint_uses_stable_fields_only(self) -> None:
        v2 = self.c.split("static unsigned int vv_fingerprint_v2(const unsigned char *villager) {", 1)[1]
        v2 = v2.split("\n}", 1)[0]
        v3 = self.c.split("static unsigned int vv_fingerprint(const unsigned char *villager) {", 1)[1]
        v3 = v3.split("\n}", 1)[0]
        # Version 2 (still read): gender and name.  Version 3 (written): the
        # same plus the parents' names, so a mask that follows its villager
        # through a reload cannot move to a living namesake of a dead one.
        self.assertIn("VV_SEX_OFFSET", v2)     # gender (stable)
        self.assertIn("VV_NAME_OFFSET", v2)    # name (stable)
        self.assertIn("vv_fingerprint_v2(villager)", v3)
        self.assertIn("VV_FATHER_NAME_OFFSET", v3)
        self.assertIn("VV_MOTHER_NAME_OFFSET", v3)
        self.assertIn("#define VV_FATHER_NAME_OFFSET 0x1BC0u", self.c)
        self.assertIn("#define VV_MOTHER_NAME_OFFSET 0x1BD9u", self.c)
        # Mutable fields must NOT be in either (they'd false-invalidate
        # a living villager's mask when they change via upgrades/aging).
        for fp in (v2, v3):
            self.assertNotIn("LIKES", fp)
            self.assertNotIn("DISLIKE", fp)
            self.assertNotIn("HEAD_OFFSET", fp)
            self.assertNotIn("BODY_OFFSET", fp)

    def test_lookup_rejects_and_persists_reused_slot_identity_mismatch(self) -> None:
        lookup = self.c.split("static int vv_get_mask(", 1)[1].split(
            "static void vv_set_mask(", 1
        )[0]
        # The present sweep can see an old and replacement villager as occupied
        # on adjacent callbacks.  The lookup must therefore validate the live
        # stable fingerprint before returning an index-keyed mask.
        self.assertIn("fp = vv_identity(villager);", lookup)
        self.assertIn("if (g_mask_fp[idx] != fp)", lookup)
        # A mismatch is NOT cleared here any more: after a reload the mask's
        # villager is in another record, and the sweep's follow moves it there
        # -- or drops it, and persists that, once nobody carries its identity
        # (a reused record).  Clearing in the lookup lost the masks of
        # everyone behind a death.
        mismatch = lookup.split("if (g_mask_fp[idx] != fp)", 1)[1].split("} else {", 1)[0]
        self.assertNotIn("g_mask_by_index[idx] = 0;", mismatch)
        self.assertNotIn("vv_write_mask_sidecar();", mismatch)
        self.assertIn("return 0;", mismatch)
        follow = self.c.split("static int vv_mask_follow_table(void) {", 1)[1].split("\n}", 1)[0]
        self.assertIn("if (!g_slot_identity_ready[idx]) {", follow)
        self.assertIn("vv_mask_follow(slots, g_mask_by_index, g_mask_fp,\n"
                      "                             g_mask_roster_known ? g_mask_roster : NULL, live, 0, moved_mask, moved_fp);",
                      follow)
        sweep_body = self.c.split("static int vv_mask_sweep(void) {", 1)[1].split("\n}", 1)[0]
        self.assertIn("changed |= vv_mask_follow_table();", sweep_body)
        # Codex (#516): after a reload in the same process the seen-alive
        # latches describe the old layout, so the follow must run BEFORE the
        # clear of vacated records, or those masks are erased first.
        self.assertLess(sweep_body.index("changed |= vv_mask_follow_table();"),
                        sweep_body.index("g_mask_by_index[idx] = 0;                /* was alive, now freed"))
        cache = self.c.split("Vv4MaskCacheSurface(void *surface)", 1)[1].split("\n}", 1)[0]
        self.assertIn("vv_write_mask_sidecar();", cache)
        sweep = self.c.split("static int vv_mask_sweep(void)", 1)[1].split(
            "static unsigned int vv_fingerprint", 1
        )[0]
        # The first sweep only records that the slot is occupied.  A later
        # completed sweep promotes it to identity-ready, preventing a
        # partially initialized first-load name from being persisted as stale.
        self.assertLess(
            sweep.index("if (g_slot_seen_alive[idx])"),
            sweep.index("g_slot_identity_ready[idx] = 1;"),
        )
        self.assertLess(
            sweep.index("g_slot_identity_ready[idx] = 1;"),
            sweep.index("g_slot_seen_alive[idx] = 1;"),
        )
        # A mismatch must be decided before the successful value is returned.
        self.assertLess(lookup.index("if (g_mask_fp[idx] != fp)"), lookup.rindex("return 0;"))
        self.assertLess(lookup.index("if (g_mask_fp[idx] != fp)"), lookup.index("return (int)m;"))

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

    def test_only_the_resolved_mask_exports_are_declared(self) -> None:
        d = DLL_DEF.read_text(encoding="utf-8", errors="replace")
        self.assertIn("Vv4MaskCacheSurface=_Vv4MaskCacheSurface@4 @110", d)
        self.assertIn("Vv4MaskGetForRecord=_Vv4MaskGetForRecord@4 @114", d)
        # The SDL blit exports (@111 Vv4MaskDraw, @112 Vv4MaskDrawRecord) were
        # never resolved: the masks are drawn through the game's ldwImageGrid.
        self.assertNotIn("Vv4MaskDraw=", d)
        self.assertNotIn("Vv4MaskDrawRecord=", d)


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

    def test_save_builder_slot_capture_uses_exact_preimage_and_owned_cave(self) -> None:
        p = self.by_off[MASK_SAVE_SLOT_FILE_OFFSET]
        self.assertEqual(p["before"], "81EC04010000")
        self.assertTrue(p["after"].upper().startswith("E9"))
        target = _rel_target(p["after"], MASK_SAVE_SLOT_SITE)
        self.assertEqual(target, 0x728FD0)
        scratch = self.by_off[MASK_SAVE_SLOT_SCRATCH]
        self.assertEqual(scratch["before"], "00000000")
        self.assertEqual(scratch["after"], "00000000")
        cave = self.by_off[MASK_SAVE_SLOT_CAVE]
        self.assertEqual(set(cave["before"]), {"0"})
        self.assertIn("capture save-builder slot", cave["purpose"])
        cave_bytes = bytes.fromhex(cave["after"])
        self.assertIn(bytes.fromhex("83F801"), cave_bytes)
        self.assertIn(bytes.fromhex("83F805"), cave_bytes)
        self.assertIn(bytes.fromhex("A3CC8F7200"), cave_bytes)

    def test_save_slot_capture_is_before_untouched_stock_body(self) -> None:
        p = self.by_off[MASK_SAVE_SLOT_FILE_OFFSET]
        self.assertEqual(len(bytes.fromhex(p["before"])), 6)
        self.assertEqual(len(bytes.fromhex(p["after"])), 6)
        self.assertEqual(p["before"], "81EC04010000")
        # The cave returns to VA 0x403676, immediately after the six-byte
        # prologue; no later save-builder bytes are replaced.
        cave = bytes.fromhex(self.by_off[MASK_SAVE_SLOT_CAVE]["after"])
        targets = []
        for i, value in enumerate(cave[:-4]):
            if value == 0xE9:
                rel = int.from_bytes(cave[i + 1:i + 5], "little", signed=True)
                targets.append(0x728FD0 + i + 5 + rel)
        self.assertIn(0x403676, targets)

    def test_approved_render_hook_and_cave_bytes_are_unchanged(self) -> None:
        # These are the player-approved VV4 world/render bytes from the Details
        # repair. Slot scoping must not silently retune geometry or routes.
        world = self.by_off[MASK_WORLD_SITE - IMAGE_BASE]
        self.assertEqual(world["before"], "E82845FEFF")
        self.assertEqual(world["after"], "E8480C2C00")
        self.assertEqual(
            hashlib.sha256(bytes.fromhex(self.by_off[MASK_WORLD_CAVE_FILE_OFFSET]["after"])).hexdigest().upper(),
            "E15812FD6F264E329F1B174B00945F7D602435DD604A78DA79329BDD0DB46F62",
        )
        self.assertEqual(self.by_off[MASK_DY_FILE_OFFSET]["after"], "2222222222")
        self.assertEqual(
            hashlib.sha256(bytes.fromhex(self.by_off[MASK_HEAD_FILE_OFFSET]["after"])).hexdigest().upper(),
            # Re-pinned when MASK_DETAILS_ROW/COL moved off the Barrel/Island requeue
            # code (0x728A50/54 -> 0x728D48/4C): the only changed bytes are those six
            # absolute operands; geometry and routes are byte-identical.
            "F7BFA0280E880ADC7E3A07FFF29BC178E1D3CAC009BD0CE6D35B3A38C4D9AA98",
        )

    def test_confirmed_details_head_is_redirected_to_the_head_cave(self) -> None:
        for site in MASK_HEAD_CALL_SITES:
            p = self.by_off[site - IMAGE_BASE]
            # was `call 0x409a70` (the head-draw thunk), still a call.
            self.assertEqual(_rel_target(p["before"], site), MASK_DRAW_THUNK_VA)
            self.assertTrue(p["after"].upper().startswith("E8"))
            self.assertEqual(_rel_target(p["after"], site), MASK_HEAD_VA)

    def test_details_uses_confirmed_full_body_head_draw(self) -> None:
        # Exact stock trace: Details vtable entry 6 (0x48EFFC) -> 0x447D30 ->
        # 0x460BF0(record, 0) -> 0x45F550; its head draw is 0x45F702 using
        # record+0x1BB8.  The 0x45F965 route belongs to another renderer and
        # must never be emitted by this feature.
        self.assertNotIn(DETAIL_FALSE_SITE - IMAGE_BASE, self.by_off)
        self.assertIn(MASK_HEAD_FILE_OFFSET, self.by_off)
        for off in DETAIL_FALSE_OLD_SCRATCH_OFFSETS:
            self.assertNotIn(off, self.by_off)
        self.assertEqual(
            _rel_target(self.by_off[0x45F702 - IMAGE_BASE]["after"], 0x45F702),
            MASK_HEAD_VA,
        )
        self.assertNotIn(0x45F9CA - IMAGE_BASE, self.by_off)

    def test_head_replay_ports_the_vv5_details_tuple_contract(self) -> None:
        # VV4 0x45F550 is the structural counterpart of VV5 0x466C40. Keep the
        # exact native x/y tuple, use the portrait-only turn field (+0x2E38 mod
        # 3), and draw through the native wrapper with a dedicated atlas.
        source = (ROOT / "scripts" / "build_vv4_origins_feature.py").read_text("utf-8")
        head_source = source.split("def mask_head_cave", 1)[1].split(
            "def mask_world_cave", 1)[0]
        self.assertIn("mov ecx, dword ptr [{MASK_S_ECX}]", head_source)
        self.assertIn("call 0x{MASK_DRAW_THUNK_VA:X}", head_source)
        self.assertIn("mov eax, dword ptr [eax + {MASK_DETAILS_FACING_OFFSET}]", head_source)
        self.assertIn("mov ecx, 3", head_source)
        self.assertIn("idiv ecx", head_source)
        self.assertIn("movzx ecx, byte ptr [edx + {MASK_DETAILS_OFFSETS}]", head_source)
        self.assertNotIn("[esi+0x1CD4]", head_source)  # +0x1CD4 is active, not facing
        self.assertNotIn("mov eax, [esp+0x14]", head_source)
        self.assertIn("mov edx, dword ptr [{MASK_SLOT_BIGHEAD_ATLAS}]", head_source)
        self.assertIn("imul ecx, ecx, {MASK_DETAILS_SCALE_MUL}", head_source)
        self.assertIn("shr ecx, {MASK_DETAILS_SCALE_SHIFT}", head_source)
        self.assertIn("sub eax, {MASK_DETAILS_LIFT}", head_source)
        self.assertNotIn("fmul dword ptr [{MASK_S_TRANSFORM}]", head_source)
        for row in (1, 3, 4):
            self.assertIn(f"cmp ecx, {row}", head_source)
        self.assertIn("sub dword ptr [{MASK_S_X}], 2", head_source)
        self.assertIn("add dword ptr [{MASK_S_Y}], 3", head_source)
        world_source = source.split("def mask_world_cave", 1)[1].split(
            "def add_c_string", 1)[0]
        self.assertIn("fild dword ptr [esp]", world_source)
        self.assertIn("fmul dword ptr [{MASK_W_A6}]", world_source)
        cave = bytes.fromhex(self.by_off[MASK_HEAD_FILE_OFFSET]["after"])
        call_targets = []
        for i, value in enumerate(cave[:-4]):
            if value == 0xE8:
                rel = int.from_bytes(cave[i + 1:i + 5], "little", signed=True)
                call_targets.append(MASK_HEAD_VA + i + 5 + rel)
        self.assertIn(MASK_DRAW_THUNK_VA, call_targets)
        self.assertNotIn(MASK_DRAW_REAL_VA, call_targets)
        # Generated bytes pin the VV4 portrait field, modulo-3 operation, exact
        # x1.5 integer scale, and the dedicated atlas slot.
        self.assertIn(bytes.fromhex("8B80382E000099B903000000F7F9"), cave)
        self.assertIn(bytes.fromhex("8B0D888D72006BC903D1E9"), cave)
        self.assertGreaterEqual(cave.count(bytes.fromhex("8B153C8A7200")), 2)
        table = self.by_off[MASK_DETAILS_TABLE_FILE_OFFSET]
        self.assertEqual(table["before"], "00" * 16)
        self.assertEqual(table["after"], "00010200000000001303F00002000200")
        # The separate world cave retains its 0x44C790 float-scale contract.
        world_cave = bytes.fromhex(self.by_off[0xCCEB0]["after"])
        self.assertIn(bytes.fromhex("DB0424"), world_cave)  # fild [esp]
        self.assertIn(bytes.fromhex("D80DB88F7200"), world_cave)  # fmul scale
        self.assertLessEqual(MASK_HEAD_VA + len(cave), 0x728A3C)

    def test_mask_caves_live_in_zeroed_shr_space(self) -> None:
        for off in (0xCCD90, 0xCCDE0, MASK_HEAD_FILE_OFFSET, 0xCCEB0):
            cave = self.by_off[off]
            self.assertEqual(set(cave["before"]), {"0"})   # was zero-filled .shr
            self.assertGreater(len(bytes.fromhex(cave["after"])), 0)
        self.assertNotIn(0xCCE10, self.by_off)  # old head cave was not reused

    def test_non_invasive_no_row_bumps_and_portrait_unhooked(self) -> None:
        # No head-atlas row-count bumps (male/female/bigheads) -- the old
        # append-rows approach is gone.
        for off in (0xC3C24, 0xC3B94, 0xC3CB4):
            self.assertNotIn(off, self.by_off, f"row-count field {off:#x} must not be patched")
        # The old dead site and the proven-wrong 0x45F965 Details route stay
        # byte-identical; no obsolete portrait cave is emitted.
        self.assertNotIn(0x3D040, self.by_off)
        self.assertNotIn(DETAIL_FALSE_SITE - IMAGE_BASE, self.by_off)
        self.assertNotIn(0x45F9CA - IMAGE_BASE, self.by_off)
        for off in DETAIL_FALSE_OLD_SCRATCH_OFFSETS:
            self.assertNotIn(off, self.by_off)

    def test_render_atlas_ships_as_an_added_file(self) -> None:
        cf = self.m["companion_files"]
        self.assertEqual(cf[0]["destination"], "VVFP VV4 Origins Icons.dll")
        self.assertEqual(
            hashlib.sha256((ROOT / cf[0]["source"]).read_bytes()).hexdigest().upper(),
            cf[0]["sha256"],
        )
        # Ships as vvfp_mask_atlas00.png: the DLL builds the atlas via the game's
        # MULTI-FILE ldwImageGrid ctor FUN_0040ABA0, whose sprintf "%s%d%d%s"
        # yields "<name>00.png". The multi-file ctor is required so the surface
        # array at obj[0xc] is populated (the draw reads the surface there).
        atlas = next((e for e in cf if e["destination"] == "Images/vvfp_mask_atlas00.png"), None)
        self.assertIsNotNone(atlas, "render atlas companion missing")
        self.assertEqual(
            hashlib.sha256((ROOT / atlas["source"]).read_bytes()).hexdigest().upper(),
            atlas["sha256"])
        # Added file -> no atlas SWAP fields (we do not overwrite a stock atlas).
        self.assertNotIn("restore_source", atlas)
        self.assertNotIn("preimage_sha256", atlas)

        details = next(
            (e for e in cf
             if e["destination"] == "Images/vvfp_bighead_mask_atlas00.png"),
            None,
        )
        self.assertIsNotNone(details, "VV5-style Details atlas companion missing")
        details_bytes = (ROOT / details["source"]).read_bytes()
        self.assertEqual(hashlib.sha256(details_bytes).hexdigest().upper(), details["sha256"])
        self.assertEqual(
            details_bytes,
            (ROOT / "assets/vv5_bighead_masks/bigheads_masks.png").read_bytes(),
            "VV4 Details must retain VV5's approved frames and geometry exactly",
        )
        self.assertNotIn("restore_source", details)
        self.assertNotIn("preimage_sha256", details)

    def test_rebuilt_dll_imports_transactional_sidecar_apis(self) -> None:
        import pefile

        pe = pefile.PE(str(ROOT / self.m["companion_files"][0]["source"]))
        imports = {
            item.name.decode(errors="replace")
            for dll in pe.DIRECTORY_ENTRY_IMPORT
            for item in dll.imports
            if item.name is not None
        }
        self.assertTrue({"WriteFile", "FlushFileBuffers", "CloseHandle", "MoveFileExA"} <= imports)

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

    def test_chooser_is_internal_not_exported(self) -> None:
        # Only the Tech dialog's row 13, inside the DLL, opens the chooser; the
        # executable never resolved ordinal 113, so it is no longer exported.
        self.assertNotIn("ShowVv4AppearanceForAll", self.d)
        self.assertIn("static int __stdcall ShowVv4AppearanceForAll(void) {", self.c)

    def test_dialog_214_matches_mockup(self) -> None:
        self.assertIn("214 DIALOGEX", self.rc)
        for cap in ("Male Villagers", "Female Villagers",
                    "Mask Distribution (all villagers)",
                    "Village-wide Single Mask Color",
                    "Off (use Mask selectors above)",
                    "VV5-style", "Random (All 5 + No Mask)", "Random (All 5)",
                    "Equal Colors (All 5 colors; balanced M/F)",
                    "None (remove all masks)", "Blue", "Orange", "Red",
                    "Purple", "Chief",
                    # Village-wide Heads + Bodies groups (VV2 parity wording).
                    "Village-wide Heads", "Village-wide Bodies",
                    "Off (use Head selectors above)",
                    "Off (use Body selectors above)",
                    "Random (by gender)",
                    "All Black Hair", "All Brown Hair", "All Red / Ginger Hair",
                    "All Blonde Hair", "All Other Hair / Styles",
                    "OK deducts 450,000 tech points"):
            self.assertIn(cap, self.rc, cap)

    def test_dialog_214_is_wide_layout(self) -> None:
        # Wide 620x340 (VV2 parity) clears the fullscreen-centering height cap.
        self.assertIn("214 DIALOGEX 0, 0, 620, 340", self.rc)

    def test_head_body_forall_wired(self) -> None:
        # The two new village-wide groups drive fa_head_mode/fa_body_mode and
        # override the per-sex cyclers at apply time; the hair buckets exist.
        for token in ("FA_HEAD_RADIO_FIRST 3220", "FA_BODY_RADIO_FIRST 3240",
                      "head_mode", "body_mode", "fa_pick_head",
                      "fa_buckets", "fa_sync_enable"):
            self.assertIn(token, self.c, token)
        # Heads override writes the head field; Bodies override the body field.
        self.assertIn("head_mode != FA_HEAD_OFF", self.c)
        self.assertIn("body_mode != FA_BODY_OFF", self.c)

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

    def test_charge_requires_an_applicable_occupied_record(self) -> None:
        self.assertIn("static int vv4_apply_for_all(void)", self.c)
        engine = self.c.split("static int vv4_apply_for_all(void)", 1)[1].split(
            "\n}", 1
        )[0]
        self.assertIn("int affected = 0", engine)
        self.assertIn("forall_state.male_mask != FA_NOCHANGE", engine)
        self.assertIn("forall_state.female_mask != FA_NOCHANGE", engine)
        self.assertIn("if (affected == 0)", engine)
        self.assertIn("return affected;", engine)

        entry = self.c.split("ShowVv4AppearanceForAll(void) {", 1)[1].split("\n}", 1)[0]
        apply_at = entry.index("affected = vv4_apply_for_all()")
        guard_at = entry.index("if (affected == 0)", apply_at)
        charge_at = entry.index("push delta", guard_at)
        self.assertLess(apply_at, guard_at)
        self.assertLess(guard_at, charge_at)
        self.assertIn("No occupied villagers matched", entry)
        self.assertIn("No tech points have been deducted", entry)

    def test_for_all_dialog_and_messages_reuse_captured_game_owner(self) -> None:
        entry = self.c.split(
            "ShowVv4AppearanceForAll(void) {", 1
        )[1].split("\n}", 1)[0]
        owner_capture = "HWND owner = GetForegroundWindow();"
        self.assertIn(owner_capture, entry)
        self.assertLess(entry.index(owner_capture), entry.index("vv4_prep_fullscreen();"))
        self.assertIn(
            "DialogBoxParamA(module_instance, MAKEINTRESOURCEA(214), owner,",
            entry,
        )
        self.assertNotIn("MessageBoxA(NULL", entry)
        self.assertEqual(entry.count("MessageBoxA(owner"), 6)

    def test_successful_cure_result_is_foreground_information_popup(self) -> None:
        cure = self.c.split(
            "ShowOriginsCureResult(", 1
        )[1].split("/* ---- Complete / Reset All Collections", 1)[0]
        self.assertIn(
            'MessageBoxA(GetForegroundWindow(), text, "Origins Upgrades",\n'
            "                MB_OK | MB_ICONINFORMATION | VV_MB_FRONT);",
            cure,
        )
        self.assertEqual(cure.count("MB_OK | MB_ICONINFORMATION | VV_MB_FRONT"), 2)

    def test_apply_preflights_actual_final_values_before_mutation(self) -> None:
        engine = self.c.split("static int vv4_apply_for_all(void)", 1)[1].split(
            "\n}", 1
        )[0]
        # Dynamic modes are materialized into a plan, allowing coincidental
        # random matches to be treated as a genuine no-op too.
        for token in ("current_head", "current_body", "current_mask",
                      "plan_head", "plan_body", "plan_mask",
                      "head_selected", "body_selected", "mask_selected",
                      "raw_mask", "raw_mask_fp", "fingerprint-checked lookup",
                      "vv4_mask_plan_changes"):
            self.assertIn(token, engine, token)
        preflight = engine.index("Preflight compares the final planned values")
        zero_gate = engine.index("if (affected == 0) return 0;", preflight)
        mutation = engine.index("Exactly one mutation pass", zero_gate)
        self.assertLess(preflight, zero_gate)
        self.assertLess(zero_gate, mutation)
        self.assertIn("plan_head[i] != current_head[i]", engine)
        self.assertIn("plan_body[i] != current_body[i]", engine)
        self.assertIn("plan_mask[i], current_mask[i], raw_mask[i], raw_mask_fp[i]", engine)
        # A no-op must not persist the mask table; only a changed mask does.
        self.assertIn("if (mask_changed) vv_write_mask_sidecar();", engine)

    def test_explicit_none_clears_stale_or_malformed_mask_slot(self) -> None:
        helper = self.c.split("static int vv4_mask_plan_changes", 1)[1].split(
            "\n}", 1
        )[0]
        # vv_peek_mask maps stale/malformed state to logical None, so explicit
        # None must additionally inspect the exact raw mask/fingerprint bytes.
        self.assertIn("if (desired == 0)", helper)
        self.assertIn("raw_mask != 0 || raw_fp != 0", helper)
        self.assertIn("return desired != current", helper)
        engine = self.c.split("static int vv4_apply_for_all(void)", 1)[1].split(
            "\n}", 1
        )[0]
        self.assertIn("raw_mask[nact] = g_mask_by_index[idx]", engine)
        self.assertIn("raw_mask_fp[nact] = g_mask_fp[idx]", engine)
        self.assertIn("plan_mask[i], current_mask[i], raw_mask[i], raw_mask_fp[i]", engine)
        # The same decision controls the actual setter and the persisted-save
        # flag, preventing a stale slot from being reported as a no-op.
        mutation = engine.index("Exactly one mutation pass")
        self.assertIn("vv_set_mask(rec, plan_mask[i]);", engine[mutation:])
        self.assertIn("mask_changed = 1;", engine[mutation:])


if __name__ == "__main__":
    unittest.main()


class Vv4RenameAndRosterTests(unittest.TestCase):
    """Codex (#516, round 2): a renamed villager keeps the mask (the follow
    recognises the rename by gender and parents and moves the identity
    with it), and any roster change is written while there are masks --
    a stale roster would read as a repack on the next load."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.c = (Path(__file__).resolve().parents[1] / "native" / "vv4_origins_icons"
                 / "vv4_origins_icons.c").read_text(encoding="utf-8")
        cls.follow = cls.c.split("static int vv_mask_follow_table(void) {", 1)[1].split("\n}", 1)[0]

    def test_a_rename_is_carried_before_the_follow(self) -> None:
        renamed = self.follow.index("int renamed = vv_roster_renamed(slots, g_mask_roster, g_mask_stable, live, live_stable);")
        self.assertLess(renamed, self.follow.index("changed = vv_mask_follow("))
        block = self.follow[renamed:self.follow.index("changed = vv_mask_follow(")]
        self.assertIn("g_mask_fp[renamed] = live[renamed];", block)
        self.assertIn("g_mask_roster[renamed] = live[renamed];", block)
        self.assertIn("roster_delta = 1;", block)
        stable = self.c.split("static unsigned int vv_stable_identity(const unsigned char *villager) {", 1)[1].split("\n}", 1)[0]
        self.assertNotIn("VV_NAME_OFFSET", stable)
        self.assertIn("VV_FATHER_NAME_OFFSET", stable)

    def test_every_roster_change_is_written_while_masks_exist(self) -> None:
        self.assertIn("if (roster_delta && any_mask) {\n        changed = 1;", self.follow)
        self.assertNotIn("changed |= !g_mask_roster_known || g_mask_by_index[idx] != 0;", self.follow)

    def test_the_stable_fields_are_unknown_after_a_load_or_reset(self) -> None:
        self.assertEqual(self.c.count("g_mask_stable_known = 0;"), 2)
