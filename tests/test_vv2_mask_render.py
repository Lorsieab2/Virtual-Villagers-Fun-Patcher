"""Static and application guards for the VV2 mask overlay contract."""

import hashlib
import importlib.util
import json
import struct
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STAGE2 = (ROOT / "scripts" / "build_vv2_mask_stage2.py").read_text(encoding="utf-8")
ORIGINS_BUILDER = (ROOT / "scripts" / "build_vv2_origins_feature.py").read_text(encoding="utf-8")
DLL = (ROOT / "native" / "vv2_origins_icons" / "vv2_origins_icons.c").read_text(encoding="utf-8")
MANIFEST = json.loads((ROOT / "data" / "vv2_origins_feature.json").read_text(encoding="utf-8"))

REQUIRED_MASK_HOOKS = {
    "0x3160": ("8B4424048B11", "E95A120B0090"),
    "0x95B0": ("8B09E989F3FFFF", "E997AA0A009090"),
    "0x9600": ("8B09E9E9F6FFFF", "E920AB0A009090"),
    "0x45B50": ("5355568BF1", "E9E8E70600"),
    "0x4C5E6": ("8986D874E500", "E9BD7C060090"),
}


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


def test_origins_builder_composes_the_authoritative_mask_stage() -> None:
    assert "build_vv2_mask_stage2_output(original)" in ORIGINS_BUILDER
    assert "mask_append.hex().upper()" in ORIGINS_BUILDER
    assert "append_bytes" in MANIFEST["pe_append_transaction"]["layouts"]["collection_progression"]


def test_manifest_publishes_all_mask_hooks_and_exact_append_pages() -> None:
    patches = {item["offset"]: item for item in MANIFEST["patches"]}
    for offset, (before, after) in REQUIRED_MASK_HOOKS.items():
        assert patches[offset]["before"] == before
        assert patches[offset]["after"] == after

    tx = MANIFEST["pe_append_transaction"]
    assert tx["append_length"] == 0x2000
    assert "append_source" not in tx
    assert tx["source_sha256"] == "46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677"
    for mode in ("collection_progression", "immediate_fixed"):
        layout = tx["layouts"][mode]
        append_bytes = bytes.fromhex(layout["append_bytes"])
        assert len(append_bytes) == layout["append_length"] == 0x2000
        assert hashlib.sha256(append_bytes).hexdigest().upper() == layout["page_sha256"]
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
