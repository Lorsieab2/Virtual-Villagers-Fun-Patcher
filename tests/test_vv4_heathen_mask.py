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
        self.assertIn("#define VV_REC_ARRAY_BASE 0x50E5ACu", self.c)
        self.assertIn("#define VV_REC_STRIDE     0x2E3Cu", self.c)
        self.assertIn("g_mask_by_index[VV_MAX_VILLAGERS]", self.c)

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
        self.assertIn("vvfp_masks_", self.c)
        self.assertIn(".dat", self.c)
        self.assertNotIn('"\\\\vvfp_masks.dat"', self.c)
        self.assertIn("\\\\LDW", self.c)               # Documents\LDW\<basename>\
        # Written on chooser OK, read once lazily on the first present frame.
        self.assertIn("vv_write_mask_sidecar();", self.c)
        self.assertIn("vv_read_mask_sidecar();", self.c)
        self.assertIn('WriteFile(h, "VVMK", 4', self.c)   # magic + versioned header
        # Read validates magic + version + count before trusting the file.
        read = self.c.split("static void vv_read_mask_sidecar(void) {", 1)[1].split("\n}", 1)[0]
        self.assertIn("VV_SIDECAR_VERSION", read)
        self.assertIn("VV_MAX_VILLAGERS", read)

    def test_save_slot_namespaces_and_resets_sidecar_state(self) -> None:
        self.assertIn("#define VV4_MASK_SAVE_SLOT_VA 0x728FCCu", self.c)
        self.assertIn("g_current_slot", self.c)
        self.assertIn("g_sidecar_loaded", self.c)
        self.assertIn("vv_sync_save_slot();", self.c)
        sync = self.c.split("static void vv_sync_save_slot(void)", 1)[1].split("\n}", 1)[0]
        self.assertIn("vv_clear_mask_state();", sync)
        self.assertIn("g_sidecar_loaded = (slot == 0) ? 1 : 0;", sync)
        self.assertIn("slot < 1 || slot > 5", self.c)
        self.assertIn("out[i] = (char)('0' + slot);", self.c)

    def test_sidecar_write_is_transactional_with_exact_four_writes(self) -> None:
        write = self.c.split("static void vv_write_mask_sidecar(void) {", 1)[1].split(
            "static void vv_read_mask_sidecar(void) {", 1
        )[0]
        # A near-limit final path remains usable for reads, but publication gets
        # its own bounded path budget for the fixed temporary suffix.
        self.assertIn("char tmp[MAX_PATH];", write)
        self.assertIn('lstrlenA(path) + (int)sizeof(".tmp") > MAX_PATH', write)
        self.assertIn("lstrcpyA(tmp, path);", write)
        self.assertIn('lstrcatA(tmp, ".tmp");', write)
        self.assertIn(
            "CreateFileA(tmp, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,", write
        )
        # The format remains magic, header, mask table, fingerprint table: four
        # complete writes, each checked for both API success and byte count.
        self.assertEqual(write.count("WriteFile("), 4)
        for expected in (
            'WriteFile(h, "VVMK", 4, &wr, NULL) || wr != 4',
            "WriteFile(h, header, sizeof(header), &wr, NULL) ||",
            "wr != sizeof(header)",
            "WriteFile(h, g_mask_by_index, VV_MAX_VILLAGERS, &wr, NULL) ||",
            "wr != VV_MAX_VILLAGERS)",
            "WriteFile(h, g_mask_fp,",
            "wr != VV_MAX_VILLAGERS * (DWORD)sizeof(unsigned int)",
        ):
            self.assertIn(expected, write)
        self.assertIn("FlushFileBuffers(h)", write)
        self.assertIn("if (!CloseHandle(h))", write)
        self.assertEqual(write.count("DeleteFileA(tmp);"), 2)
        self.assertNotIn("DeleteFileA(path);", write)

        # No final-name publication can occur before all writes, flush, and close.
        writes_done = write.rindex("WriteFile(h, g_mask_fp,")
        flush = write.index("FlushFileBuffers(h)")
        close = write.index("if (!CloseHandle(h))")
        publish = write.index("MoveFileExA(tmp, path,")
        self.assertLess(writes_done, flush)
        self.assertLess(flush, close)
        self.assertLess(close, publish)
        self.assertIn("MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH", write)

    def test_sidecar_path_checks_the_complete_max_path_budget_before_appending(self) -> None:
        builder = self.c.split("static int vv_build_sidecar_path(char *out, int slot)", 1)[1].split(
            "\n}", 1
        )[0]
        guard = 'lstrlenA(out) + (int)(sizeof("\\\\LDW\\\\") - 1) + lstrlenA(base) +'
        suffix = '(int)sizeof("\\\\vvfp_masks_0.dat") > MAX_PATH'
        self.assertIn(guard, builder)
        self.assertIn(suffix, builder)
        # sizeof(suffix) includes the NUL. The guard must precede every
        # unbounded append, including the otherwise-vulnerable first "\\LDW".
        self.assertLess(builder.index(guard), builder.index('lstrcatA(out, "\\\\LDW");'))
        # The length repair must not broaden or rename the existing slot files.
        self.assertIn("slot < 1 || slot > 5", builder)
        self.assertIn("out[i] = (char)('0' + slot);", builder)
        self.assertIn('lstrcatA(out, ".dat");', builder)

    def test_render_atlas_path_checks_complete_max_path_budget_before_appending(self) -> None:
        renderer = self.c.split("static void vv4_mask_render_init(void)", 1)[1].split(
            "\n}", 1
        )[0]
        guard = 'lstrlenA(path) + (int)sizeof("Images\\\\vvfp_mask_atlas.png") > MAX_PATH'
        self.assertIn(guard, renderer)
        self.assertLess(
            renderer.index(guard),
            renderer.index('lstrcatA(path, "Images\\\\vvfp_mask_atlas.png");'),
        )

    def test_sweep_persists_confirmed_free_slot_clears(self) -> None:
        cache = self.c.split("Vv4MaskCacheSurface(void *surface)", 1)[1].split("\n}", 1)[0]
        self.assertIn("cleared = vv_mask_sweep();", cache)
        self.assertIn("if (cleared && g_current_slot > 0)", cache)
        self.assertIn("vv_write_mask_sidecar();", cache)

    def test_every_mask_entrypoint_prepares_before_table_access(self) -> None:
        for signature, table_token in (
            ("static int vv_get_mask(", "g_mask_by_index[idx]"),
            ("static void vv_set_mask(", "g_mask_by_index[idx]"),
            ("Vv4MaskDraw(int index", "g_mask_by_index[index]"),
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
        fp = self.c.split("vv_fingerprint(", 1)[1].split("}", 1)[0]
        self.assertIn("VV_SEX_OFFSET", fp)     # gender (stable)
        self.assertIn("VV_NAME_OFFSET", fp)    # name (stable)
        # Mutable fields must NOT be in the fingerprint (they'd false-invalidate
        # a living villager's mask when they change via upgrades/aging).
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
        self.assertIn("fp = vv_fingerprint(villager);", lookup)
        self.assertIn("if (g_mask_fp[idx] != fp)", lookup)
        self.assertIn("g_mask_by_index[idx] = 0;", lookup)
        self.assertIn("g_mask_fp[idx] = 0;", lookup)
        self.assertIn("vv_write_mask_sidecar();", lookup)
        self.assertIn("g_slot_identity_ready[idx]", lookup)
        self.assertIn("g_current_slot == 0", lookup)
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
        self.assertIn("if (g_slot_identity_ready[idx] || !g_sidecar_loaded ||", lookup)
        # A mismatch must be decided before the successful value is returned;
        # the load-frame exception only defers invalidation until a prior
        # completed sweep has promoted the slot and cannot publish the stale
        # value.
        self.assertLess(lookup.index("if (g_mask_fp[idx] != fp)"), lookup.rindex("return 0;"))
        self.assertLess(lookup.index("g_mask_by_index[idx] = 0;"), lookup.index("return (int)m;"))

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
            "29CF62BED8C8A162AFF87BCA1BBE99058012BF091A1513DA272B713A398A2BA0",
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

    def test_head_replay_preserves_draw_context_and_uses_mask_arg1(self) -> None:
        # VV2/VV5 parity: 0x409A70 is retained for the draw-manager wrapper
        # (mov ecx,[ecx]); 0x408C40 is not called with the atlas as ECX. The
        # mask replay uses a clean record facing, not the age-adjusted native
        # animation frame passed as arg5 by the portrait renderer.
        source = (ROOT / "scripts" / "build_vv4_origins_feature.py").read_text("utf-8")
        head_source = source.split("def mask_head_cave", 1)[1].split(
            "def mask_world_cave", 1)[0]
        self.assertIn("mov ecx, dword ptr [{MASK_S_ECX}]", head_source)
        self.assertIn("call 0x{MASK_DRAW_THUNK_VA:X}", head_source)
        self.assertIn("mov eax, [esi+0x1CD4]", head_source)
        self.assertIn("and eax, 7", head_source)
        self.assertNotIn("mov eax, [esp+0x14]", head_source)
        self.assertIn("movsx eax, byte ptr [eax + {MASK_DY_TABLE}]", head_source)
        # Details arg6 is an integer percent, matching 0x408C40's fild / 100;
        # the head replay must not reinterpret it as an IEEE float.  +50 gives
        # nearest-integer seating for positive native scales.
        self.assertIn("imul eax, dword ptr [{MASK_S_TRANSFORM}]", head_source)
        self.assertIn("add eax, 50", head_source)
        self.assertIn("idiv ecx", head_source)
        self.assertNotIn("fmul dword ptr [{MASK_S_TRANSFORM}]", head_source)
        self.assertIn("sub ecx, dword ptr [{MASK_S_DY}]", head_source)
        self.assertEqual(
            head_source.count("mov dword ptr [{MASK_S_FACING}], eax"), 1,
            "clean facing must not be overwritten by lift arithmetic")
        self.assertNotIn("fistp dword ptr [{MASK_S_FACING}]", head_source)
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
        # The generated bytes include mov eax,[esi+0x1CD4]; and eax,7 before
        # storing the clean facing scratch used by the mask replay.
        self.assertIn(bytes.fromhex("8B86D41C000083E007"), cave)
        # Details arg6 is the native integer percent: imul dy*percent, round
        # with +50, then idiv 100.  This guards against the old IEEE-float bug.
        self.assertIn(
            bytes.fromhex("0FAF05888D720083C03231D2B964000000F7F9"), cave)
        # The separate world cave retains its 0x44C790 float-scale contract.
        world_cave = bytes.fromhex(self.by_off[0xCCEB0]["after"])
        self.assertIn(bytes.fromhex("DB0424"), world_cave)  # fild [esp]
        self.assertIn(bytes.fromhex("D80DB88F7200"), world_cave)  # fmul scale
        self.assertLessEqual(MASK_HEAD_VA + len(cave), 0x728B10)

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

    def test_export_declared(self) -> None:
        self.assertIn("ShowVv4AppearanceForAll=_ShowVv4AppearanceForAll@0 @113", self.d)

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
        charge_at = entry.index("push -450000", guard_at)
        self.assertLess(apply_at, guard_at)
        self.assertLess(guard_at, charge_at)
        self.assertIn("No occupied villagers matched", entry)
        self.assertIn("No tech points have been deducted", entry)

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
