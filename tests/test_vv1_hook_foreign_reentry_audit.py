"""Fail if any VV1 hook gains an unreviewed "foreign re-entry" into stock code.

This guards the defect class that shipped twice (v1.34.10 and v1.34.11):

    hook spliced at S -> jumps to a cave -> the cave jumps BACK into stock
    code at some address T -> the stock code at T dereferences a register
    that was only guaranteed valid on the stock control-flow paths reaching
    T, not on the path arriving through S.

T == S + len(replaced bytes) is a plain resume and is always safe. Every
other target is a *foreign re-entry*: correctness there depends on a register
contract that must be checked by hand, because the stock code at T was
written assuming a different set of predecessors.

Rather than try to prove register liveness automatically (undecidable in
general here), this test pins the exact set of foreign re-entries that exist
today, each with the registers it dereferences and a note recording why it is
safe. Adding a hook, moving a splice point, or changing a cave's jump targets
makes the set drift and fails this test, forcing the new case to be reviewed
and recorded instead of silently shipped.

See also tests/test_vv1_birth_control_manual_pair_emulation.py, which proves
the birth-control manual-pair paths specifically by emulating them.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

try:
    import capstone
    import pefile

    HAVE_DEPS = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_DEPS = False

STOCK = ROOT / "inputs" / "vv1-stock-copy" / "Virtual Villagers - A New Home.exe"

GP = {"eax", "ebx", "ecx", "edx", "esi", "edi", "ebp"}

# (feature id, splice offset, stock re-entry target) -> why it is safe.
# Keep the reason specific: "which register, valid because what".
REVIEWED: dict[tuple[str, str, int], str] = {
    (
        "vv1_birth_control",
        "0x3DD03",
        0x43DD5E,
    ): "accept path. Derefs EBP (actor record), set once at 0x43DAE5 "
    "(lea ebp,[ecx+esi]) and never reassigned in the function.",
    (
        "vv1_birth_control",
        "0x3DD03",
        0x43DD9E,
    ): "reject path. Derefs ESI (this) and EBP (actor record), both stable, "
    "and EDI (candidate record) at 0x43DDE1/0x43DDF4/0x43DE06/0x43DE1A/"
    "0x43DE2E. EDI is stale at this splice point (it holds the RNG(3)+5 "
    "duration), which is exactly the v1.34.11 crash; the cave now rebuilds "
    "it as esi+ebx*0x3D8 before jumping here.",
    (
        "vv1_birth_control",
        "0x46E96",
        0x446EA2,
    ): "resume past the stock jl. Cave touches only EAX and flags, so EDX "
    "and ESI reach here exactly as the stock code left them.",
    (
        "vv1_birth_control",
        "0x46E96",
        0x447036,
    ): "reject. This is the stock's own jl target from 0x446E9C, and the "
    "cave preserves ESI (touches only EAX and flags).",
    (
        "vv1_birth_control",
        "0x47084",
        0x447090,
    ): "resume past the stock jl. Cave touches only ECX and flags, so ESI "
    "reaches here unchanged.",
    (
        "vv1_birth_control",
        "0x47084",
        0x44723D,
    ): "reject. Stock's own jl target from 0x44708A; no pointer reads.",
    (
        "vv1_birth_control",
        "0x477FA",
        0x447829,
    ): "reject. Stock's own jl target from 0x4477FD; no pointer reads.",
    (
        "vv1_birth_control",
        "0x39C83",
        0x439C9D,
    ): "chooser tail; both cave paths converge here. No pointer reads.",
    (
        "vv1_enable_origins_exclusive_features",
        "0x35ACA",
        0x435DCD,
    ): "Barrel close helper. Derefs ESI at 0x435DCD; the helper only reads "
    "ESI (never writes it) and the two calls it makes are callee-save, so "
    "ESI is the stock function's own value.",
    (
        "vv1_f6_clothing_change_cheat",
        "0x1FF2E",
        0x41FFB1,
    ): "no pointer reads at the target.",
    (
        "vv1_builder_action_fixes",
        "0x48336",
        0x44836F,
    ): "no pointer reads at the target.",
}


def _collect() -> dict[tuple[str, str, int], list[str]]:
    import vv_fun_patcher as patcher

    builds = {b.id: b for b in patcher.load_builds()}
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True

    found: dict[tuple[str, str, int], list[str]] = {}
    for feature in patcher.load_fun_patches():
        if feature.game_id != "vv1":
            continue
        edits = list(feature.raw.get("patches", []))
        for mode_edits in feature.raw.get("patch_mode_overrides", {}).values():
            edits.extend(mode_edits)
        jmp_edits = [
            e for e in edits if e.get("after") and bytes.fromhex(e["after"])[:1] == b"\xE9"
        ]
        if not jmp_edits:
            continue
        try:
            rendered, _ = patcher.render_patched_bytes(
                STOCK, builds["vv1"], "stock", [feature.id]
            )
        except Exception:  # mode-restricted or unavailable; covered elsewhere
            continue
        pe = pefile.PE(data=bytes(rendered), fast_load=True)
        pe.parse_data_directories()
        base = pe.OPTIONAL_HEADER.ImageBase
        img = pe.get_memory_mapped_image()
        text = next(s for s in pe.sections if s.Name.rstrip(b"\x00") == b".text")
        lo = base + text.VirtualAddress
        hi = lo + text.Misc_VirtualSize

        for edit in jmp_edits:
            after = bytes.fromhex(edit["after"])
            s_va = base + int(edit["offset"], 0)
            resume = s_va + len(after)
            cave = s_va + 5 + int.from_bytes(after[1:5], "little", signed=True)
            off = cave - base
            if not (0 <= off < len(img)):
                continue
            targets = set()
            for ins in md.disasm(img[off : off + 0x300], cave):
                if ins.bytes == b"\x00\x00":
                    break  # zero padding ends this hook's block
                if ins.mnemonic.startswith("j") and ins.op_str.startswith("0x"):
                    dst = int(ins.op_str, 16)
                    if lo <= dst < hi:
                        targets.add(dst)
                if ins.mnemonic == "ret":
                    break
            for dst in sorted(targets):
                if dst == resume:
                    continue
                derefs: list[str] = []
                written: set[str] = set()
                seen: set[str] = set()
                doff = dst - base
                for ins in md.disasm(img[doff : doff + 400], dst):
                    r, w = ins.regs_access()
                    rn = {ins.reg_name(x) for x in r} & GP
                    wn = {ins.reg_name(x) for x in w} & GP
                    for reg in sorted(rn - written):
                        if reg in seen:
                            continue
                        seen.add(reg)
                        body = ins.op_str.split("[", 1)[1] if "[" in ins.op_str else ""
                        if reg in body:
                            derefs.append(reg)
                    written |= wn
                    if ins.mnemonic == "ret":
                        break
                    if len(seen) >= 7:
                        break
                found[(feature.id, edit["offset"], dst)] = sorted(set(derefs))
    return found


@unittest.skipUnless(HAVE_DEPS, "requires capstone and pefile")
@unittest.skipUnless(STOCK.exists(), "requires the exact-build VV1 stock executable")
class VV1HookForeignReentryAuditTests(unittest.TestCase):
    def test_every_foreign_reentry_is_reviewed(self) -> None:
        found = _collect()
        unreviewed = {k: v for k, v in found.items() if k not in REVIEWED}
        self.assertEqual(
            unreviewed,
            {},
            "New/changed hook re-entry into stock code is not in REVIEWED. Each "
            "one must be checked: does the stock code at that address "
            "dereference a register the splice point does not guarantee? That "
            "is exactly how the v1.34.10 and v1.34.11 crashes shipped. "
            f"Unreviewed: { {f'{a}@{b}->{hex(c)}': d for (a, b, c), d in unreviewed.items()} }",
        )

    def test_no_reviewed_reentry_has_disappeared(self) -> None:
        found = _collect()
        missing = sorted(
            f"{a}@{b}->{hex(c)}" for (a, b, c) in REVIEWED if (a, b, c) not in found
        )
        self.assertEqual(
            missing,
            [],
            "REVIEWED lists re-entries that no longer exist; prune them so the "
            "audit keeps reflecting the real hooks.",
        )


if __name__ == "__main__":
    unittest.main()
