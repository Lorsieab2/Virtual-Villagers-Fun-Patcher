"""Static and application guards for the VV2 mask overlay contract."""

import hashlib
import importlib.util
import json
import struct
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from source_text_hash import source_text_sha256, source_text_sha256_bytes  # noqa: E402

STAGE2 = (ROOT / "scripts" / "build_vv2_mask_stage2.py").read_text(encoding="utf-8")
ORIGINS_BUILDER = (ROOT / "scripts" / "build_vv2_origins_feature.py").read_text(encoding="utf-8")
DLL = (ROOT / "native" / "vv2_origins_icons" / "vv2_origins_icons.c").read_text(encoding="utf-8")
MANIFEST = json.loads((ROOT / "data" / "vv2_origins_feature.json").read_text(encoding="utf-8"))
STATUS = (ROOT / "docs" / "vv5-mask-parity-status.md").read_text(encoding="utf-8")

REQUIRED_MASK_HOOKS = {
    0x3160: "8B4424048B11",
    0x95B0: "8B09E989F3FFFF",
    0x9600: "8B09E9E9F6FFFF",
    0x45B50: "5355568BF1",
    0x4C5E6: "8986D874E500",
}

# Semantic entry signatures for the five authoritative stage-2 routines.  The
# detour destinations may move when a preceding routine grows; these probes
# prove each published JMP still lands at the intended instruction boundary.
MASK_HOOK_ENTRY_PREFIXES = {
    0x3160: "508B442408",
    0x95B0: "508B4424043D505B4400",
    0x9600: "508B4424043D40554400",
    0x45B50: "60C605",
    0x4C5E6: "8986D874E50060",
}


def _rel32_jump_target(file_offset: int, encoded: bytes) -> int:
    assert len(encoded) >= 5 and encoded[0] == 0xE9
    return 0x400000 + file_offset + 5 + int.from_bytes(
        encoded[1:5], "little", signed=True
    )


def test_stage2_uses_the_current_atlas_geometry_in_its_contract() -> None:
    assert "(520x725)" in STAGE2
    assert "cell 65x145" in STAGE2
    assert "ATLAS_COLS, ATLAS_ROWS = 8, 5" in STAGE2


def test_vv2_atlas_migration_replaces_only_exact_bundled_legacy_art() -> None:
    """The startup migration must not treat arbitrary 320x440 art as legacy."""
    assert "#define VV2_LEGACY_ATLAS_WIDTH  320" in DLL
    assert "#define VV2_LEGACY_ATLAS_HEIGHT 440" in DLL
    for size in ("64965", "64852", "78917", "79105"):
        assert size in DLL
    assert "GetFileSizeEx(file, &file_size)" in DLL
    assert "CryptHashData(hash, header, sizeof(header), 0)" in DLL
    for digest in (
        "CAE2F56C58D504EB26AD8AA9772A92F616D8CD26B546EE1091D889A19F616FB4",
        "10819268622323D4B289CB27A35BFA4B1398AC149A55399AE627AA4CBB4EA57C",
        "1D2CC1CB3230E59A66D847DAB2EF482075DA538357CCBCAF97A121705CC09E81",
        "3CE015BA025BF847C65FB0389016658E7D624AFA2038A3AAD7C1530367FE8AC7",
    ):
        assert digest in DLL
    assert "if (!vv2_legacy_atlas_identity(path)) return;  /* preserve current/custom art */" in DLL
    assert "if (replace_legacy && !vv2_legacy_atlas_identity(path))" in DLL
    assert "MOVEFILE_REPLACE_EXISTING" in DLL
    assert "if (GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES) return;" not in DLL


def test_dead_slot_clears_are_persisted_once_after_the_sweep() -> None:
    assert 'SAVE_STR = b"Vv2MaskSaveSidecar\\x00"' in STAGE2
    assert "SAVE_FN     = MASK_TABLE_VA + 0xF1C" in STAGE2
    assert "mov  dword ptr [0x{SAVE_FN:X}], eax" in STAGE2

    sweep = STAGE2[STAGE2.index("sweep_asm = f\"\"\""):]
    reset = sweep.index("mov  byte ptr [0x{SWEEP_CLEARED_VA:X}], 0")
    clear = sweep.index("mov  byte ptr [esi+0x{MASK_TABLE_VA:X}], 0")
    mark = sweep.index("mov  byte ptr [0x{SWEEP_CLEARED_VA:X}], 1")
    save_check = sweep.index("cmp  byte ptr [0x{SWEEP_CLEARED_VA:X}], 0")
    save_call = sweep.index("call eax                             /* Vv2MaskSaveSidecar() */")
    loop = sweep.index("sweep_loop:")
    assert reset < loop < clear < mark < save_check < save_call


def test_dll_exports_the_sidecar_save_used_by_the_sweep() -> None:
    assert "Vv2MaskSaveSidecar=_Vv2MaskSaveSidecar@0" in (
        ROOT / "native" / "vv2_origins_icons" / "vv2_origins_icons.def"
    ).read_text(encoding="utf-8")
    assert "__declspec(dllexport) void __stdcall Vv2MaskSaveSidecar(void)" in DLL
    assert "vv2_mask_sidecar_save();" in DLL


def test_sidecar_path_rejects_invalid_slots_before_formatting() -> None:
    # Slot zero remains available only to the explicit legacy migration read;
    # arbitrary save-path arguments must not reach the decimal formatter.
    assert "if (slot < 0 || slot > 5) return 0;" in DLL
    assert "sizeof(\"\\\\vv2_masks_00.dat\")" in DLL


def test_sidecar_load_normalizes_every_mask_byte_before_publish() -> None:
    # Sidecars are external/user-writable. Invalid rows must never reach the
    # native atlas draw, even if the file has the right magic and length.
    assert "if (buf[i] >= VV2_MASK_COUNT) buf[i] = 0;" in DLL
    assert DLL.index("if (buf[i] >= VV2_MASK_COUNT) buf[i] = 0;") < DLL.index(
        "memcpy(VV2_MASK_TABLE, buf, sizeof(buf));"
    )


def test_render_consumers_fail_closed_on_invalid_table_rows() -> None:
    # Both the in-world adult and scaled (child/details) consumers re-check
    # the byte before subtracting one for an atlas row.
    assert "cmp  edx, {MASK_ROW_COUNT}" in STAGE2
    assert "cmp  eax, {MASK_ROW_COUNT}" in STAGE2
    assert "jae  aorig" in STAGE2
    assert "jae  corig" in STAGE2
    assert "jae  adone" in STAGE2
    assert "jae  cdone" in STAGE2


def _vv2_caf_applicable(
    sexes: list[int],
    *,
    head: tuple[int, int] = (-1, -1),
    body: tuple[int, int] = (-1, -1),
    mask: tuple[int, int] = (-1, -1),
    mask_dist: int = 0,
    village_mask: int = -1,
    head_mode: int = 0,
    body_mode: int = 0,
    mask_ok: bool = True,
) -> int:
    """Reference the VV2 preflight contract for focused no-charge cases."""
    return sum(
        int(
            head_mode != 0
            or body_mode != 0
            or head[sex] >= 0
            or body[sex] >= 0
            or (mask_ok and (mask[sex] >= 0 or mask_dist != 0 or village_mask >= 0))
        )
        for sex in sexes
    )


def _vv2_caf_record_needs_change(
    *,
    sex: int,
    current_head: tuple[int, int] = (0, 0),
    current_body: tuple[int, int] = (0, 0),
    current_mask: tuple[int, int] = (0, 0),
    head: tuple[int, int] = (-1, -1),
    body: tuple[int, int] = (-1, -1),
    mask: tuple[int, int] = (-1, -1),
    mask_dist: int = 0,
    village_mask: int = -1,
    head_mode: int = 0,
    body_mode: int = 0,
    mask_ok: bool = True,
) -> bool:
    """Reference one VV2 record's changed-value preflight decision."""
    if head[sex] >= 0 and current_head[sex] != head[sex]:
        return True
    if body[sex] >= 0 and current_body[sex] != body[sex]:
        return True
    if mask_ok and mask[sex] >= 0 and current_mask[sex] != mask[sex]:
        return True
    return bool(
        head_mode != 0
        or body_mode != 0
        or (mask_ok and (mask_dist != 0 or village_mask >= 0))
    )


def test_vv2_for_all_preflight_covers_absent_matching_and_global_cases() -> None:
    # VV2 uses active +0x30 as its established population predicate.  A
    # selector for an absent sex must be a no-op, while a matching selector and
    # each global mode must count the affected record exactly once.
    assert _vv2_caf_applicable([0], head=(-1, 7)) == 0
    assert _vv2_caf_applicable([0], head=(7, -1)) == 1
    assert _vv2_caf_applicable([0, 1], body_mode=1) == 2
    assert _vv2_caf_applicable([0, 1], body=(-1, -1), mask_dist=3) == 2
    assert _vv2_caf_applicable([], head=(7, -1)) == 0
    assert _vv2_caf_applicable([0], mask_dist=2, mask_ok=False) == 0

    engine = DLL[DLL.index("static int caf_plan_head"):DLL.index("#define VV2_CAF_COST")]
    assert "int n = 0, affected = 0, mask_ok, mask_requested, i;" in engine
    assert "mask_requested = (caf_mask[0] >= 0 || caf_mask[1] >= 0 ||" in engine
    assert "if (rec[VV2_ACTIVE_OFFSET] == 0) continue;" in engine
    assert "vv2_caf_record_needs_change(rec, idx[i], sexof[i], mask_ok)" in engine
    assert "caf_head[s] >= 0" in engine
    assert "caf_body[s] >= 0" in engine
    assert "mask_ok && caf_mask[s] >= 0" in engine
    assert "if (affected == 0)" in engine
    assert engine.index("if (affected == 0)") < engine.index("*(int *)(rec + VV2_HEAD_OFFSET)")
    assert "return affected;" in engine
    assert "return n;" not in engine


def test_vv2_for_all_preflight_counts_only_real_fixed_value_changes() -> None:
    # A selected fixed head/body/mask that already matches is a true no-op.
    assert not _vv2_caf_record_needs_change(
        sex=0, current_head=(7, 0), head=(7, -1)
    )
    assert not _vv2_caf_record_needs_change(
        sex=0, current_body=(12, 0), body=(12, -1)
    )
    assert not _vv2_caf_record_needs_change(
        sex=0, current_mask=(3, 0), mask=(3, -1)
    )
    assert not _vv2_caf_record_needs_change(
        sex=0,
        current_head=(7, 0),
        current_body=(12, 0),
        current_mask=(3, 0),
        head=(7, -1),
        body=(12, -1),
        mask=(3, -1),
    )

    # Each changed fixed field, and a mixed selection with one changed field,
    # counts exactly once for that record.
    assert _vv2_caf_record_needs_change(
        sex=0, current_head=(6, 0), head=(7, -1)
    )
    assert _vv2_caf_record_needs_change(
        sex=0, current_body=(11, 0), body=(12, -1)
    )
    assert _vv2_caf_record_needs_change(
        sex=0, current_mask=(2, 0), mask=(3, -1)
    )
    assert _vv2_caf_record_needs_change(
        sex=0,
        current_head=(7, 0),
        current_body=(11, 0),
        current_mask=(3, 0),
        head=(7, -1),
        body=(12, -1),
        mask=(3, -1),
    )

    # Sex selection remains record-local, while missing mask storage remains
    # fail-closed and cannot turn a mask-only no-op into a charged action.
    assert not _vv2_caf_record_needs_change(
        sex=1, current_head=(7, 9), head=(7, -1)
    )
    assert not _vv2_caf_record_needs_change(
        sex=0, current_mask=(3, 0), mask=(3, -1), mask_ok=False
    )
    assert _vv2_caf_record_needs_change(
        sex=0, current_head=(7, 0), head=(7, -1), body_mode=1
    )


def test_vv2_for_all_dynamic_modes_compare_the_materialized_plan() -> None:
    # Random selectors are planned before preflight.  A one-record village can
    # therefore be a true no-op when the planned random output equals storage.
    def planned_needs_change(
        current: tuple[int, int, int],
        planned: tuple[int, int, int],
        *,
        mask_ok: bool = True,
    ) -> bool:
        return (
            current[0] != planned[0]
            or current[1] != planned[1]
            or (mask_ok and current[2] != planned[2])
        )

    assert not planned_needs_change((7, 12, 3), (7, 12, 3))
    assert planned_needs_change((7, 12, 3), (8, 12, 3))
    assert planned_needs_change((7, 12, 3), (7, 13, 3))
    assert planned_needs_change((7, 12, 3), (7, 12, 4))
    assert not planned_needs_change((7, 12, 3), (7, 12, 4), mask_ok=False)

    engine = DLL[DLL.index("static int caf_plan_head"):DLL.index("#define VV2_CAF_COST")]
    assert "static void vv2_caf_build_plan" in engine
    assert "caf_plan_head[idx[i]] = h;" in engine
    assert "caf_plan_body[idx[i]] =" in engine
    assert "caf_plan_mask[idx[i]] = (int)(caf_rand() % 6u);" in engine
    assert "caf_plan_mask[order[k]] = (k % 5) + 1;" in engine
    assert "caf_plan_head[index]" in engine
    assert "caf_plan_body[index]" in engine
    assert "caf_plan_mask[index]" in engine
    assert "vv2_caf_build_plan(base, mask_ok, idx, sexof, &n);" in engine


def test_vv2_for_all_zero_count_precedes_charge_and_sidecar_save() -> None:
    entry = DLL[DLL.index("ShowVV2AppearanceForAll(void *player)"):]
    apply_at = entry.index("if (vv2_apply_caf(base) == 0)")
    charge_at = entry.index("*tech -= VV2_CAF_COST", apply_at)
    save_at = entry.index("vv2_mask_sidecar_save();", charge_at)
    assert apply_at < charge_at < save_at
    assert "No active villagers matched the selected appearance options." in entry[apply_at:charge_at]
    assert "No tech points were deducted." in entry[apply_at:charge_at]


def test_vv2_for_all_noop_defect_is_recorded_in_the_status_ledger() -> None:
    assert "20. VV2's Change Appearance for All apply pass previously returned" in STATUS
    assert "matching-sex field" in STATUS
    assert "deduct no 450,000 points" in STATUS


def test_origins_builder_composes_the_authoritative_mask_stage() -> None:
    assert "build_vv2_mask_stage2_output(original)" in ORIGINS_BUILDER
    assert "VV2_MASK_STAGE2_PATCH_SPECS" in ORIGINS_BUILDER
    assert "mask_stage2_output[offset : offset + len(before)]" in ORIGINS_BUILDER
    assert "mask_append.hex().upper()" in ORIGINS_BUILDER
    assert "append_bytes" in MANIFEST["pe_append_transaction"]["layouts"]["collection_progression"]


def test_manifest_publishes_all_mask_hooks_and_exact_append_pages() -> None:
    patches = {item["offset"]: item for item in MANIFEST["patches"]}
    layout = MANIFEST["pe_append_transaction"]["layouts"]["collection_progression"]
    append_bytes = bytes.fromhex(layout["append_bytes"])
    append_va = int(layout["virtual_address"], 0)
    for offset, before in REQUIRED_MASK_HOOKS.items():
        patch = patches[f"0x{offset:X}"]
        assert patch["before"] == before
        after = bytes.fromhex(patch["after"])
        assert len(after) == len(bytes.fromhex(before))
        target = _rel32_jump_target(offset, after)
        target_offset = target - append_va
        prefix = bytes.fromhex(MASK_HOOK_ENTRY_PREFIXES[offset])
        assert 0 <= target_offset <= len(append_bytes) - len(prefix)
        assert append_bytes[target_offset : target_offset + len(prefix)] == prefix

    tx = MANIFEST["pe_append_transaction"]
    builder_path = ROOT / "scripts" / "build_vv2_mask_stage2.py"
    assert tx["builder_sha256"] == source_text_sha256(builder_path)
    builder_lf = builder_path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    assert tx["builder_sha256"] == source_text_sha256_bytes(
        builder_lf.replace(b"\n", b"\r\n")
    )
    assert tx["append_length"] == 0x2000
    assert "append_source" not in tx
    assert tx["source_sha256"] == "46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677"
    for mode in ("collection_progression", "immediate_fixed"):
        layout = tx["layouts"][mode]
        mode_append = bytes.fromhex(layout["append_bytes"])
        assert len(mode_append) == layout["append_length"] == 0x2000
        assert hashlib.sha256(mode_append).hexdigest().upper() == layout["page_sha256"]
        assert layout["page_sha256"] == tx["page_sha256"]
        for header in layout["header_patches"]:
            before = bytes.fromhex(header["before"])
            after = bytes.fromhex(header["after"])
            assert len(before) == len(after)


def _stock_shape() -> bytearray:
    """Small exact-size PE-shaped input for generic append install tests."""
    data = bytearray(0xB1000)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0xF0)
    data[0xF0:0xF4] = b"PE\0\0"
    struct.pack_into("<H", data, 0xF6, 5)
    struct.pack_into("<H", data, 0x104, 0xE0)
    struct.pack_into("<H", data, 0x108, 0x10B)
    struct.pack_into("<I", data, 0x140, 0xB3000)
    data[0xF6:0xF8] = bytes.fromhex("0500")
    data[0x140:0x144] = bytes.fromhex("00300B00")
    return data


def test_generic_mask_append_installs_and_removes_cleanly_for_all_public_modes() -> None:
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from vv_fun_patcher import FunPatch, _apply_pe_append_transactions, _remove_feature_bytes, pe_checksum

    append_only_manifest = json.loads(json.dumps(MANIFEST))
    append_only_manifest["patches"] = []
    feature = FunPatch(append_only_manifest)
    for mode in ("stock", "collection_progression", "immediate_fixed"):
        original = _stock_shape()
        checksum_offset = 0x148
        struct.pack_into("<I", original, checksum_offset, 0)
        struct.pack_into("<I", original, checksum_offset, pe_checksum(original))
        installed = bytearray(original)
        applied = _apply_pe_append_transactions(installed, [feature], mode)
        assert len(installed) == 0xB3000
        assert len(applied) == 5
        assert bytes(installed[0xB1000:]) == bytes.fromhex(
            MANIFEST["pe_append_transaction"]["layouts"]["collection_progression"]["append_bytes"]
        )
        assert installed[0xF6:0xF8] == bytes.fromhex("0700")
        removed = _remove_feature_bytes(installed, feature, mode)
        assert len(removed) == 1
        assert installed == original


@pytest.mark.parametrize("mode", ("collection_progression", "immediate_fixed"))
def test_real_stock_install_remove_roundtrip_if_local_fixture_is_present(mode: str) -> None:
    stock = ROOT / "inputs" / "vv2-stock-copy" / "Virtual Villagers - The Lost Children.exe"
    if not stock.is_file():
        pytest.skip("local VV2 stock fixture is not present in this checkout")
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from vv_fun_patcher import FunPatch, _apply_pe_append_transactions, _remove_feature_bytes, pe_checksum

    original = bytearray(stock.read_bytes())
    assert len(original) == 0xB1000
    # The generic transaction owns PE checksum repair.  Compare against the
    # stock bytes in that canonical form so a stock fixture with a stale or
    # zero checksum still has an exact roundtrip expectation.
    struct.pack_into("<I", original, 0x148, 0)
    struct.pack_into("<I", original, 0x148, pe_checksum(original))
    # This roundtrip isolates the delivery transaction itself.  The five
    # fixed detours are covered by the manifest assertions above; the generic
    # append/remove path must be proven against the real stock PE without
    # pretending the unrelated Origins rows were applied first.
    append_only_manifest = json.loads(json.dumps(MANIFEST))
    append_only_manifest["patches"] = []
    feature = FunPatch(append_only_manifest)
    installed = bytearray(original)
    _apply_pe_append_transactions(installed, [feature], mode)
    assert len(installed) == 0xB3000
    _remove_feature_bytes(installed, feature, mode)
    assert installed == original


def test_release_manifest_keeps_vv2_mask_delivery_self_contained() -> None:
    release_source = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
    assert '"data/vv2_origins_feature.json"' in release_source
    assert '"src/vv_fun_patcher.py"' in release_source
    # The installed patcher consumes the literal page in the manifest; it does
    # not need to ship Keystone or the development-only stage-2 builder.
    assert '"scripts/build_vv2_mask_stage2.py"' not in release_source


def test_release_zip_carries_the_literal_vv2_mask_transaction(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "vv2_release_manifest", ROOT / "scripts" / "build_release.py"
    )
    assert spec is not None and spec.loader is not None
    release = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release)

    archive_path = tmp_path / release.NAME
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in release.FILES:
            archive.write(ROOT / relative, relative)

    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        names = set(archive.namelist())
        assert "data/vv2_origins_feature.json" in names
        assert "src/vv_fun_patcher.py" in names
        assert "scripts/build_vv2_mask_stage2.py" not in names
        bundled_manifest = json.loads(
            archive.read("data/vv2_origins_feature.json")
        )
        transaction = bundled_manifest["pe_append_transaction"]
        for mode in ("collection_progression", "immediate_fixed"):
            layout = transaction["layouts"][mode]
            payload = bytes.fromhex(layout["append_bytes"])
            assert len(payload) == 0x2000
            assert hashlib.sha256(payload).hexdigest().upper() == layout["page_sha256"]
            assert "append_source" not in layout
