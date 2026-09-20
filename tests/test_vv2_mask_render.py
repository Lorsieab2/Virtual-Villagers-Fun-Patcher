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
    # pushad, then `mov eax,[SWEEP_FN]` -- the cave loads the cached
    # Vv2MaskSweep pointer and forwards ECX. It used to begin with the
    # SWEEP_CLEARED store, which moved into the DLL along with the loop.
    0x45B50: "60A124",
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
    """One snapshot per pass, and only when something was actually cleared.

    The ordering moved into the DLL with the loop, but the contract is
    unchanged: reset the flag, walk the records, clear a dead villager's mask
    and mark the flag, then persist once at the end if anything was marked.
    Persisting unconditionally would rewrite the sidecar on every frame.
    """
    assert 'SAVE_STR = b"Vv2MaskSaveSidecar\\x00"' in STAGE2
    assert "SAVE_FN     = MASK_TABLE_VA + 0xF1C" in STAGE2

    source = (ROOT / "native" / "vv2_origins_icons"
              / "vv2_origins_icons.c").read_text(encoding="utf-8")
    body = source[source.index("__stdcall Vv2MaskSweep("):]
    body = body[:body.index("\n}\n") + 3]

    reset = body.index("*VV2_SWEEP_CLEARED = 0;")
    loop = body.index("for (i = 0;")
    clear = body.index("VV2_MASK_TABLE[i] = 0;")
    mark = body.index("*VV2_SWEEP_CLEARED = 1;")
    check = body.index("if (*VV2_SWEEP_CLEARED)")
    save = body.index("vv2_mask_sidecar_save();")
    assert reset < loop < clear < mark < check < save, (
        "the persist-once ordering is broken; the sidecar would be rewritten "
        "on every frame or not at all")


def test_the_record_base_cannot_be_clobbered_before_it_is_captured() -> None:
    """The contract for the VV2 startup AV at generated RVA 0xB437C.

    The sidecar restore is allowed to clobber volatile ECX. The old cave dealt
    with that by reloading EDX from the pushad frame AFTER the restore call.
    The base is now forwarded as the call argument before any call runs, so it
    cannot be clobbered in between -- the hazard is structural rather than
    worked around.

    The DLL's own null check is the other half: a base that never arrives makes
    the sweep do nothing rather than dereference it.
    """
    gate = STAGE2[STAGE2.index('sweep_asm = f"""'):]
    gate = gate[:gate.index('"""', 20)]
    assert gate.index("push ecx") < gate.index("call eax"), (
        "the base is captured after a call, so it could already be clobbered")
    assert "mov  edx, [esp+0x18]" not in gate, (
        "the pushad-frame reload is back; the base should arrive as an "
        "argument instead")

    source = (ROOT / "native" / "vv2_origins_icons"
              / "vv2_origins_icons.c").read_text(encoding="utf-8")
    body = source[source.index("__stdcall Vv2MaskSweep("):]
    body = body[:body.index("\n}\n") + 3]
    assert "if (base == 0" in body, (
        "the sweep no longer refuses a null base, so a hook firing with no "
        "village would dereference it")


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
        # The record walk moved into the DLL, so the page no longer contains
        # it. What the page must still contain is the hook that forwards the
        # compositor receiver: `push ecx; call eax`, with ECX pushed before any
        # call can clobber it. Reloading it from the pushad frame afterwards --
        # `mov edx,[esp+0x18]` -- was the old workaround for the startup AV at
        # RVA 0xB437C, and must not come back.
        assert bytes.fromhex("51FFD0") in mode_append, (
            "the cave does not forward ECX to Vv2MaskSweep")
        assert bytes.fromhex("8B542418") not in mode_append, (
            "the pushad-frame reload is back in the appended page")
        assert bytes.fromhex("89CA31F6807A3000") not in mode_append
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


def test_the_sweep_lives_in_the_dll_and_the_cave_only_forwards_ecx() -> None:
    """The appended page is shared, so the loop belongs in the companion.

    .vvmk is claimed by three features: the mask stubs, the parentage cave at
    0x41A..0x4D8, and the villagers-died payload from 0x4D8. The per-frame
    sweep is logic rather than a hook, so it lives in the DLL; the executable
    keeps only the detour, the argument and the replayed prologue.

    ECX must be forwarded BEFORE any call, while it still holds the
    compositor's receiver. An earlier restore call clobbered ECX and caused a
    first-frame AV at RVA 0xB437C; passing it up front removes that hazard.
    """
    source = STAGE2
    assert "Vv2MaskSweep" in source, (
        "the cave no longer resolves the sweep export, so no village-change "
        "reload and no death sweep would run at all")
    gate = source[source.index('sweep_asm = f"""'):]
    gate = gate[:gate.index('"""', 20)]
    assert "push ecx" in gate, "the record[0] base is not forwarded to the DLL"
    assert gate.index("push ecx") < gate.index("call eax"), (
        "ECX is forwarded after the call, so a clobbered ECX would be passed")
    # The loop must NOT have come back into the page.
    for gone in ("sweep_loop", "slot_alive", "SEEN_ALIVE_VA"):
        assert gone not in gate, (
            f"{gone} is back in the appended page; the loop belongs in the DLL")


def test_the_dll_sweep_still_reloads_on_a_village_change() -> None:
    """The bleed returns silently if the sweep stops asking.

    Byte guards cannot see this: the cave would still call the export, the
    export would still sweep the dead, and a same-slot Start Over would simply
    keep the previous village's masks. So pin the call itself.
    """
    source = (ROOT / "native" / "vv2_origins_icons"
              / "vv2_origins_icons.c").read_text(encoding="utf-8")
    body = source[source.index("__stdcall Vv2MaskSweep("):]
    body = body[:body.index("\n}\n") + 3]
    assert "Vv2MaskSyncVillage(base);" in body, (
        "Vv2MaskSweep no longer performs the village-change reload, so a "
        "Start Over in the same slot keeps the dead village's masks")
    assert body.index("Vv2MaskSyncVillage(base);") < body.index("for ("), (
        "the village reload must precede the death sweep, so the sweep "
        "reconciles the freshly loaded table against the live records")


def test_the_mask_code_clears_both_reserved_ranges() -> None:
    """The appended page is shared, and both neighbours must stay untouched.

    build_vv2_parentage_feature.py overlays its cave at .vvmk 0x41A..0x4D8, and
    build_vv2_villagers_died_feature.py places its payload from 0x4D8. An
    earlier revision walked into the first, and the next attempt landed exactly
    on the second, so this measures the rendered page rather than trusting the
    layout arithmetic.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_vv2_feat", ROOT / "scripts" / "build_vv2_origins_feature.py")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except SystemExit:
        pass
    stock = module.STOCK.read_bytes()
    append = module.build_vv2_mask_stage2_output(stock)[len(stock):]
    vvmk = append[0x1000:]

    parentage = sum(1 for byte in vvmk[0x41A:0x4D8] if byte)
    villagers_died = sum(1 for byte in vvmk[0x4D8:] if byte)
    assert parentage == 0, (
        f"{parentage} mask byte(s) land inside the parentage cave "
        "(.vvmk 0x41A..0x4D8)")
    assert villagers_died == 0, (
        f"{villagers_died} mask byte(s) land inside the villagers-died payload "
        "(.vvmk from 0x4D8)")


def test_the_sidecar_is_bound_to_the_village_that_wrote_it() -> None:
    """Detecting a village change is useless if the reload restores the old file.

    The first attempt shipped exactly that: the sweep noticed the change, the
    restore reloaded vv2_masks_<slot>.dat -- keyed only by slot -- and the
    table was refilled with the DEAD village's masks. The record therefore
    carries a per-slot snapshot of the living roster, and the load applies it
    only when that snapshot shares at least one living villager with the
    village on screen. Removing that check leaves every other test green.
    """
    source = (ROOT / "native" / "vv2_origins_icons"
              / "vv2_origins_icons.c").read_text(encoding="utf-8")

    # 'VM04': the record grew (snapshot, not a single tag), so an older file
    # fails the magic and is ignored rather than misread.
    assert "0x34304D56u" in source, (
        "the sidecar magic is not 'VM04'; an older file could be misread")

    load = source[source.index("static void vv2_mask_sidecar_load("):]
    load = load[:load.index(chr(10) + "}" + chr(10)) + 3]
    assert "vv2_roster_same(filesnap, live)" in load, (
        "the mask sidecar is applied without checking that its roster shares "
        "a living villager with the village on screen, so a Start Over in the "
        "same slot restores the dead village's masks")

    save = source[source.index("static void vv2_mask_sidecar_save("):]
    save = save[:save.index(chr(10) + "}" + chr(10)) + 3]
    assert "WriteFile(f, g_vv2_roster, sizeof(g_vv2_roster), &w, NULL);" in save, (
        "the sidecar is written without its roster snapshot, so it can never "
        "be matched against the village that wrote it")
    assert "if (!g_vv2_have_roster) return;" in save, (
        "an unidentified village must not write a file at all")


def test_a_birth_or_death_does_not_count_as_a_new_village() -> None:
    """The exact-hash version failed exactly here.

    An exact hash of the active records changes on every birth and death. The
    sync read that as a replacement, cleared the table, rejected the sidecar
    (which carried the old hash), and the next death persisted the emptied
    table -- an ordinary population change removed every surviving villager's
    mask. Codex caught it before it shipped.

    The rule is overlap: the same village across a birth or a death still
    shares almost all of its villagers, while a reused slot shares none. So a
    changed roster that still OVERLAPS must be adopted, not reloaded, and the
    reload must be reachable only when the overlap is zero.
    """
    source = (ROOT / "native" / "vv2_origins_icons"
              / "vv2_origins_icons.c").read_text(encoding="utf-8")
    sync = source[source.index("__stdcall Vv2MaskSyncVillage("):]
    sync = sync[:sync.index(chr(10) + "}" + chr(10)) + 3]

    overlap = sync.index("vv2_roster_same(g_vv2_roster, cur)")
    reload = sync.index("vv2_mask_sidecar_load(cur);")
    assert overlap < reload, (
        "the reload is not gated behind the overlap check")
    same_village_return = sync.index("return;", overlap)
    assert same_village_return < reload, (
        "an overlapping roster must return WITHOUT reloading; otherwise a "
        "birth or a death wipes every surviving villager's mask")
    # And the overlapping-but-changed case must adopt the new snapshot rather
    # than keep comparing against a stale one forever.
    adopt = sync.index("memcpy(g_vv2_roster, cur, sizeof(cur));")
    assert overlap < adopt < same_village_return, (
        "a changed-but-overlapping roster is not adopted as the same village")
    # The exact-hash export must not come back.
    assert "Vv2VillageTag" not in source, (
        "the exact-hash village tag is back; it reads births and deaths as a "
        "village replacement")


def test_one_shared_slot_name_is_not_a_village_identity() -> None:
    """The fourth finding on #386, and the one the majority rule exists for.

    "Two villages never share villagers" is true of whole rosters, not of one
    slot: founders fill slots 0..6 in order from a finite name pool, so a
    recreated village landing the same name in the same slot as its
    predecessor is roughly one-in-pool-size per slot. With `overlap > 0` a
    single coincidence kept the dead village's masks and wrote them under the
    new one.

    The predicate must therefore demand a MAJORITY of the smaller roster. A
    single death leaves prev-1 >= ceil((prev-1)/2) always; births keep every
    previous villager; a fresh 7-villager start needs four independent
    coincidences to pass. Restoring `overlap > 0` must fail here.
    """
    source = (ROOT / "native" / "vv2_origins_icons"
              / "vv2_origins_icons.c").read_text(encoding="utf-8")
    same = source[source.index("static int vv2_roster_same("):]
    same = same[:same.index(chr(10) + "}" + chr(10)) + 3]

    assert "need = (need + 1) / 2;" in same, (
        "the match no longer requires a majority of the smaller roster")
    assert "vv2_roster_overlap(a, b) >= need" in same, (
        "the overlap is not compared against the majority threshold")
    assert "return vv2_roster_overlap(a, b) > 0" not in same, (
        "one shared slot-name is being treated as a village identity again")
    # And an empty roster must match nothing, so a load frame with no
    # villagers cannot pass by vacuous majority.
    assert "if (need == 0)" in same and "return 0;" in same, (
        "an empty roster must never match")
