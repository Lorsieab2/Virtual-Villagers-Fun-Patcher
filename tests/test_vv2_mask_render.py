"""Static guards for the VV2 mask overlay's persistence and render contract."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE2 = (ROOT / "scripts" / "build_vv2_mask_stage2.py").read_text(encoding="utf-8")
DLL = (ROOT / "native" / "vv2_origins_icons" / "vv2_origins_icons.c").read_text(encoding="utf-8")


def test_stage2_uses_the_current_atlas_geometry_in_its_contract() -> None:
    assert "(520x725)" in STAGE2
    assert "cell 65x145" in STAGE2
    assert "ATLAS_COLS, ATLAS_ROWS = 8, 5" in STAGE2


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
