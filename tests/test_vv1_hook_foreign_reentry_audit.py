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

Proving register liveness automatically is not tractable here, so instead the
exact set of foreign re-entries is pinned, each with the registers it
dereferences and a recorded reason it is safe. Three things can invalidate a
recorded review, and all three fail this test:

  1. a NEW re-entry appears                  -> REVIEWED has no entry
  2. a reviewed re-entry disappears          -> stale entry, prune it
  3. the CAVE ITSELF changes                 -> fingerprint mismatch

(3) matters because a review is a statement about the cave's register
behaviour, not merely about which address it jumps to. Editing a cave so it
clobbers a register while still jumping to the same target would otherwise
keep the same key and silently pass -- which is precisely another way to
reintroduce the crash class this audit exists to prevent.

Cave traversal follows reachable control flow (conditional and unconditional
branches, plus calls that land inside the cave) rather than decoding a fixed
prefix, so a helper or re-entry further into a large cave is still found.

See also tests/test_vv1_birth_control_manual_pair_emulation.py, which proves
the birth-control manual-pair paths specifically by emulating them.
"""
from __future__ import annotations

import hashlib
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

# VV1 features that legitimately cannot be rendered in "stock" mode. Anything
# else failing to render is a real problem and fails the audit rather than
# silently dropping that feature's hooks from consideration.
EXPECTED_UNRENDERABLE: dict[str, str] = {}

# (feature id, splice offset) -> sha256 of the reachable cave block.
# Regenerate deliberately (and re-review the reasons below) whenever a cave's
# code genuinely changes.
#
# Static review record for the integrated VV1 mask branch (commit 8217950,
# fixture SHA-256 1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D):
#
#   The four Details portrait head sites are CALL detours, not JMP caves, so
#       they are outside this foreign-reentry walker. Their complete seven-arg
#       replay and ABI contract are pinned in test_vv1_mask_render_contract.py.
#   0x37798                         confirmed.  Exact cave bytes decode to
#       `mov eax,[esi+edi*4+0x3DBDC]; mov [0x4911B4],eax; jmp 0x43779F`.
#       The resume first reuses EAX in `imul` and then consumes ESI/EDI; the
#       cave defines EAX identically, leaves ESI/EDI and ESP unchanged, and
#       neither displaced mov nor the added store changes flags.
#   0x38900                         confirmed.  Exact cave bytes decode to
#       `mov eax,[ebp]; mov [0x4911B4],eax; imul eax,eax,0x3D8; jmp 0x438909`.
#       The resume consumes EAX/ESI/EBX; the cave defines EAX and preserves
#       ESI/EBX/EBP/ESP.  Its final imul reproduces the displaced flag result.
#   0x377B8 -> 0x4388CE             confirmed.  The cave begins with the exact
#       displaced `jne 0x4388CE` (`0F85C884FAFF`), before any register write.
#       The foreign target is `inc edi; cmp edi,0x100; jl ...`, which consumes
#       only EDI and flags.  The taken path therefore has the stock EDI and
#       flags; the fall-through path saves/restores EBX and resumes at
#       0x4377BE, whose first cmp redefines flags and whose next instructions
#       reload ECX/EDX from the EAX record.
#   0x9410 -> 0x408AF0               confirmed.  The pass block pops the saved
#       EDX/EAX/ECX, exactly replays stock `8B09`, and jumps with the original
#       ESP and seven arguments.  0x408AF0 starts `sub esp,0x10` (redefines
#       flags), reads its argument frame, and consumes the restored renderer
#       via `mov esi,ecx`; no incoming flag is live.  The masked path builds
#       two complete seven-argument calls and ends `ret 0x1C`, also returning
#       with the original ESP and callee-saved registers.
#   0x93E0/0x93C0                    confirmed.  The exact entry bytes store
#       0x408840/0x408740 in the draw-function slot, then jump to the shared
#       body.  The pass block restores ECX/EAX/EDX and stack, replays `8B09`,
#       and indirect-jumps to the selected stock five-argument draw.  Those
#       targets begin with `sub esp,0x10`; the shared masked path's calls end
#       `ret 0x14`, so stack and callee-saved state match the native thunks.
#   0x24103                         confirmed.  The cave decodes to the exact
#       displaced `mov ecx,[esi+8]; push 0`, plus a data-only counter reset,
#       then jumps 0x424108.  The resume immediately calls native code and
#       later consumes ESI; ECX/ESP are exactly defined and no flags are changed.
#   0x913C                          confirmed.  The cave optionally calls the
#       pushad/popad restore stub, then calls the pushad/popad Vv1MaskTick
#       resolver/caller before reproducing `mov ecx,[esi+0x30]; push ecx; mov
#       ecx,esi` and jumping 0x409142. Both calls preserve every GP register
#       and ESP. The resume stores EAX through ESI, and its first mov does not
#       consume flags.
#   0x2ED0                          re-confirmed after the save-slot fix.
#       `pushfd`+`pushad` now bracket all scratch writes and `popad`+`popfd`
#       restore every GP register, ESP, AND the flags, so the contract is
#       strictly stronger than the previous pushad-only form (the resume still
#       starts with `sub esp,0x100`, which redefines flags anyway).  The
#       argument is read at [esp+0x28] to account for the pushed flags, and the
#       cave still replays `mov eax,[esp+4]; mov edx,[ecx]` and jumps 0x402ED6.
#       Only numbered village slots 1..5 are published: slot 0 (the meta file)
#       and out-of-range values now branch straight to the popad/popfd tail
#       without touching the capture or the mask tables.
#   0x35AB0                         re-confirmed after the duplicate-purchase
#       guard.  The Tech menu it reaches now calls a small .shr helper while
#       building its state word, so this block's bytes change.  The helper
#       runs in the menu's own frame on purpose: it reads the game context
#       from [esi+0x0C] and ORs the Island-Event/Barrel pending bits straight
#       into EDI, the accumulator the menu is building.  It brackets its own
#       scratch use with push/pop EAX and ends in a balanced `ret`, so ESP and
#       every register except the intended EDI are preserved.  It leaves flags
#       undefined, which is safe here: the next instruction is `push edi`.
#       Reaching it is a `call`, not a jmp, so it adds no stock re-entry.
#   0x35AB0/0x4A700                  confirmed.  The 0x35AB0 fall-through
#       repeats the displaced `cmp [esp+4],8` immediately before 0x435AB5;
#       the 0x4A700 fall-through repeats `mov eax,[esp+4]; push ebx`
#       immediately before 0x44A705.  Each resume's first flag-setting
#       instruction (`jne` after the saved compare / `xor bl,bl`) redefines
#       flags.  The handled paths use balanced `ret 8`; helper calls preserve
#       nonvolatiles.
#   0x3C393                         confirmed.  Exact stock sub_43C350 selects
#       the first free record, sets its occupied/faction bytes at this
#       boundary, and keeps the selected record index in [esp+0x10]. The cave
#       replays those two stores, pushad/popad-brackets a bounds-checked clear
#       of the patch-owned mask nibble for that exact index, and resumes at
#       0x43C39B. No villager-record bytes or incoming flags are consumed by
#       the clear path.
#   No entry in this review was unsafe or unknown. The hashes below are the
#   post-review generated cave bytes.
CAVE_FINGERPRINTS: dict[tuple[str, str], str] = {
    ("vv1_birth_control", "0x39C83"): "D3E8E252393FE028178409449C81F4C69C69B8E259387B249D71E4CEE6322AE6",
    ("vv1_birth_control", "0x3DD03"): "F4AF5EE81A11110F6F37F8AD2411C0D7F4DA616E3B8EB820C519C5E2734E8614",
    ("vv1_birth_control", "0x46E96"): "5C9F87C9FA92B6B7BCB38A902E9E81009F206F636B8A09A0BA7FA86040BF358F",
    ("vv1_birth_control", "0x47084"): "669F80876E7C754473CDDD2EAACAB28978542C24DDAAF46090C1A29A00B0DC93",
    ("vv1_birth_control", "0x477FA"): "EAD1E07AA649935AF986B7F2BD5C3583AD72A10DF90DEACE461393D9002CB89B",
    ("vv1_builder_action_fixes", "0x48336"): "8901998FCDDD8EB745F1666B550B4C384919536E546CA4B1EAAF3BDB90176485",
    ("vv1_enable_origins_exclusive_features", "0x1D120"): "99B923C87F4D69AB38EA63F758E2712656DC93418797460FD5B5C68C62C8F0D4",
    ("vv1_enable_origins_exclusive_features", "0x1D140"): "504ACC56E0C6FB7BC92BC58CD2D2425ABE41FAB98247EC859F17D02B2F03B02A",
    ("vv1_enable_origins_exclusive_features", "0x2403F"): "63CB33A95A00E194547370F24644869943BE36AB894A6653134BC4CD8E8D1D88",
    ("vv1_enable_origins_exclusive_features", "0x28470"): "F739955B349CB69FC3FDBBC591C5461D5F5395D91D3421D3005F37AC85DAC504",
    ("vv1_enable_origins_exclusive_features", "0x358DC"): "6BBFAD8D3A7A8414759CFD64840F17AB0336E0F5237596247C101162DFE1AB01",
    ("vv1_enable_origins_exclusive_features", "0x35AB0"): "EAE6A3945D1E3FABF46BA31975ED9DA0F740773771271340BB1C2A551DE26FF8",
    ("vv1_enable_origins_exclusive_features", "0x35ACA"): "3176E4468842A999A9A9E1AFCDFE6639F52ED68FCC40767F8E6D155BA5061113",
    ("vv1_enable_origins_exclusive_features", "0x4A5FA"): "1615B6A0F8C8D7B6D292E404DE7AEEAD8B1017D33ADAD8EC55D89EBB03884C85",
    ("vv1_enable_origins_exclusive_features", "0x4A700"): "7BEEF2CB03944B6556253B41D90584B95F51DB8A177FAB1DFA8D3540490B1CD3",
    ("vv1_enable_origins_exclusive_features", "0x8B004"): "E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855",
    ("vv1_enable_origins_exclusive_features", "0x24103"): "003BBF1143C6AC2F7AD6DD0D0A70346447E500F851CD3ABD7EDE134A87AEC848",
    ("vv1_enable_origins_exclusive_features", "0x377B8"): "3EC4BE5669CAA10DB6414592D5C6FDE19C02942709AA65B8EE3A849F488DE5C0",
    ("vv1_enable_origins_exclusive_features", "0x913C"): "7809AB50B236818750AC418BD5080C6053BE2B5852AAFA37AD58DFCCC5102824",
    # The three newer detours below are part of the same integrated mask
    # branch. Their cave contracts are pinned separately in the review notes:
    # 0x9410 restores the original thunk pass path; 0x93E0/0x93C0 select the
    # original 5-argument draw function before entering the shared body.
    ("vv1_enable_origins_exclusive_features", "0x9410"): "12B2B1E9D3FB03A3613D36E8C38AE1AAD724B7AB9ED92D188E7573F204E9BDCD",
    ("vv1_enable_origins_exclusive_features", "0x93E0"): "737AA82521DC44FB571462B9B8C3BB432316C88DE977634C2D6C388ED44A1586",
    ("vv1_enable_origins_exclusive_features", "0x93C0"): "28E4B105A8C0D9E9ED8F0AA2973CB2B9919F342E9D87697A9DB9EB742324FBE9",
    ("vv1_enable_origins_exclusive_features", "0x2ED0"): "05441D52DA5CA09EE2A426FE393B21D074C929A990A190E5E0CF1CFBD73FA8ED",
    ("vv1_enable_origins_exclusive_features", "0x3C393"): "323F30C734F89D8ABAF15C4C864AC78A0320AE634B5D4D99EA826801C35F8044",
    # Village all-pose mask identity stash (Stage 1): two per-loop caves that
    # reproduce the villager index load, stash it to .data, and re-enter stock
    # at the NATURAL resume (0x43779F=splice+7, 0x438909=splice+9), so no
    # foreign re-entry -- fingerprints pin the cave bytes only. Inert until the
    # shared-draw hook reads the slot.
    ("vv1_enable_origins_exclusive_features", "0x37798"): "6D0E444DACFA185CA3D13C076829A25DAF3B84696BFC31153416B622D836650D",
    ("vv1_enable_origins_exclusive_features", "0x38900"): "E8D8456C4E183D69B796D6D26005EA39B1E96E01266DACAA859A569C5499EC21",
    ("vv1_f6_clothing_change_cheat", "0x1FF2E"): "A00945F8D66A35B8BDB078E933690DDE5B048C60287B716EED0276AC20A07F3E",
    ("vv1_magic_fruit_alters_mortality", "0x2EEAA"): "81719DCFD4BC20C6F136E88308A12EDFA14447AF58E3B8B6DC239BBF4053BF10",
    ("vv1_magic_fruit_alters_mortality", "0x4892D"): "FCB1B3DE15F5892465BFC27A589B488D0A213C8C9FF82CEB081D754C9A51221E",
    ("vv1_school_lessons_grant_skill", "0x3A230"): "846EAF1C3E8A0897824E1607D8568B3050F240A670A857D88D59F3479E24089A",
    ("vv1_school_lessons_grant_skill", "0x44B28"): "E695CAD15B97EF9EC985AC6A3EB1C2045C0BE465D922AD6F57F3FAC975EF43E9",
}

# The co-selected Origins composition relocates the Birth Control page to the
# reserved .vv1mc tail. Its reachable cave bytes have different rel32
# displacements even though the register/stack review is the same, so keep a
# separate fingerprint namespace rather than silently accepting standalone
# bytes for the combined output.
COMPOSED_CAVE_FINGERPRINTS: dict[tuple[str, str], str] = {
    ("vv1_birth_control+origins", "0x39C83"): "6A12741A0766E134FF174B1F38A2D60AE54DFDC3419E225DE63C099B8C8A00E3",
    ("vv1_birth_control+origins", "0x3DD03"): "B14149577146F1A2C72E7A79B65F5BAA32AEEF8B3EC10D429FD71223C3EF2B04",
    ("vv1_birth_control+origins", "0x46E96"): "BC63138974420681617BB3D5652C236C19879C83218C73E8AEB79339AF389ACC",
    ("vv1_birth_control+origins", "0x47084"): "926796ACA098A27162CE31B86F9A1DD23EC740CA7E0FDA70C70177BE34B10703",
    ("vv1_birth_control+origins", "0x477FA"): "95D1ABBD9B240B08828F67C39DEBCA8099F3C9CD96DD4861D3B2988904E8F58E",
}

# (feature id, splice offset, stock re-entry target) -> why it is safe.
REVIEWED: dict[tuple[str, str, int], str] = {
    # Accept path re-enters at 0x43DD0A, which is the natural resume point
    # (splice 0x43DD03 + 7 patched bytes), so the audit auto-excludes it as a
    # plain stock resume -- it is not a foreign re-entry and needs no review.
    # This is deliberate: the cave does no net push/pop, so ESP at 0x43DD0A
    # equals the splice-entry ESP, exactly matching stock, and stock's own
    # `push 0x64; jne 0x43DD5E` at 0x43DD0A then supplies both the stack push
    # and the branch. The earlier cave re-entered at 0x43DD5E instead, which
    # stock only reaches AFTER that `push 0x64`; skipping the push while stock's
    # `add esp,4` still ran left ESP 4 bytes high and FUN_0043DAD0 later `ret`ed
    # into the villager-index arg -- the full-heap-dump crash to EIP=0x22.
    (
        "vv1_birth_control",
        "0x3DD03",
        0x43DD9E,
    ): "reject path. Derefs ESI (this) and EBP (actor record), both stable, "
    "and EDI (candidate record) at 0x43DDE1/0x43DDF4/0x43DE06/0x43DE1A/"
    "0x43DE2E. EDI is stale at this splice point (it holds the RNG(3)+5 "
    "duration), which is exactly the v1.34.11 crash; the cave rebuilds it as "
    "esi+ebx*0x3D8 before jumping here.",
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
        "vv1_enable_origins_exclusive_features",
        "0x377B8",
        0x4388CE,
    ): "Heathen-mask stash hook. This IS the displaced native branch: the "
    "splice replaces sub_437790's own 'jnz 0x4388CE' (the not-occupied skip) "
    "and the hook's first instruction reproduces it byte-for-byte with the "
    "same flags and the same target, so this path is the stock control flow "
    "unchanged. 0x4388CE is the loop back-edge (inc edi / cmp edi,0x100) and "
    "dereferences nothing. The hook reaches it before touching any register.",
    (
        "vv1_enable_origins_exclusive_features",
        "0x9410",
        0x408AF0,
    ): "shared scaled-draw pass path. The cave first pushes ECX/EAX/EDX, "
    "then the pass block pops them in reverse order, restoring the original "
    "ESP and all three volatile values, reproduces stock `mov ecx,[ecx]`, "
    "and jumps to 0x408AF0. The original thunk bytes are exactly "
    "8B09 E9D9F6FFFF. At 0x408AF0, `sub esp,0x10` is the first instruction "
    "and overwrites flags; its argument reads use the untouched 7-argument "
    "frame, while `mov esi,ecx` consumes the restored renderer. Therefore "
    "the foreign entry has the stock ECX/ESP/argument contract and no "
    "incoming-flag dependency.",
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

MAX_CAVE_INSNS = 4000


class RenderFailure(RuntimeError):
    pass


def _walk_cave(md, img, base, entry, text_lo, text_hi):
    """Follow reachable control flow inside a cave.

    Returns (reentry_targets, fingerprint). Traverses conditional and
    unconditional branches and calls that land inside the cave, so helpers
    beyond any fixed prefix are still covered. Stops at rets and at the zero
    padding that separates cave blocks.
    """
    reentries: set[int] = set()
    body: dict[int, bytes] = {}
    work = [entry]
    seen_starts: set[int] = set()

    def in_cave(addr: int) -> bool:
        return 0 <= addr - base < len(img) and not (text_lo <= addr < text_hi)

    while work:
        if len(body) > MAX_CAVE_INSNS:
            break
        start = work.pop()
        if start in seen_starts or not in_cave(start):
            continue
        seen_starts.add(start)
        off = start - base
        for ins in md.disasm(img[off : off + 0x400], start):
            if ins.address in body:
                break  # already decoded from another path
            if ins.bytes == b"\x00\x00":
                break  # zero padding: end of this block
            body[ins.address] = ins.bytes
            mnem = ins.mnemonic
            if mnem.startswith("j") or mnem == "call":
                if ins.op_str.startswith("0x"):
                    dst = int(ins.op_str, 16)
                    if text_lo <= dst < text_hi:
                        # A jmp into stock code is a re-entry. A call is an
                        # ordinary invocation that returns, not a re-entry.
                        if mnem != "call":
                            reentries.add(dst)
                    elif in_cave(dst):
                        work.append(dst)
            if mnem == "jmp" or mnem == "ret":
                break  # unconditional transfer ends this straight-line run
        # conditional branches fall through, which the linear decode above
        # already covered.

    digest = hashlib.sha256()
    for addr in sorted(body):
        digest.update(addr.to_bytes(4, "little"))
        digest.update(body[addr])
    return reentries, digest.hexdigest().upper()


def _derefs(md, img, base, dst) -> list[str]:
    out: list[str] = []
    written: set[str] = set()
    seen: set[str] = set()
    off = dst - base
    for ins in md.disasm(img[off : off + 400], dst):
        r, w = ins.regs_access()
        rn = {ins.reg_name(x) for x in r} & GP
        wn = {ins.reg_name(x) for x in w} & GP
        for reg in sorted(rn - written):
            if reg in seen:
                continue
            seen.add(reg)
            body = ins.op_str.split("[", 1)[1] if "[" in ins.op_str else ""
            if reg in body:
                out.append(reg)
        written |= wn
        if ins.mnemonic == "ret" or len(seen) >= 7:
            break
    return sorted(set(out))


def _collect():
    """Returns (reentries, fingerprints, skipped)."""
    import vv_fun_patcher as patcher

    builds = {b.id: b for b in patcher.load_builds()}
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True

    reentries: dict[tuple[str, str, int], list[str]] = {}
    fingerprints: dict[tuple[str, str], str] = {}
    skipped: dict[str, str] = {}

    for feature in patcher.load_fun_patches():
        if feature.game_id != "vv1":
            continue
        edits = list(feature.raw.get("patches", []))
        for mode_edits in feature.raw.get("patch_mode_overrides", {}).values():
            edits.extend(mode_edits)
        jmp_edits = [
            e
            for e in edits
            if e.get("after") and bytes.fromhex(e["after"])[:1] == b"\xE9"
        ]
        if not jmp_edits:
            continue
        audit_variants = [(feature.id, [feature.id])]
        if feature.id == "vv1_birth_control":
            audit_variants.append(
                (
                    "vv1_birth_control+origins",
                    [
                        "vv1_birth_control",
                        "vv1_enable_origins_exclusive_features",
                    ],
                )
            )
        for fingerprint_feature_id, audit_ids in audit_variants:
            try:
                rendered, _ = patcher.render_patched_bytes(
                    STOCK, builds["vv1"], "stock", audit_ids
                )
            except Exception as exc:  # noqa: BLE001 - recorded, then asserted on
                skipped[f"{feature.id}:{fingerprint_feature_id}"] = (
                    f"{type(exc).__name__}: {exc}"
                )
                continue

            pe = pefile.PE(data=bytes(rendered), fast_load=True)
            pe.parse_data_directories()
            base = pe.OPTIONAL_HEADER.ImageBase
            img = pe.get_memory_mapped_image()
            text = next(s for s in pe.sections if s.Name.rstrip(b"\x00") == b".text")
            lo = base + text.VirtualAddress
            hi = lo + text.Misc_VirtualSize

            for edit in jmp_edits:
                # Use the rendered bytes, because the composed Birth Control
                # page's hook displacements are generated for 0x490C00.
                after_len = len(bytes.fromhex(edit["after"]))
                after = bytes(
                    rendered[
                        int(edit["offset"], 0) : int(edit["offset"], 0) + after_len
                    ]
                )
                s_va = base + int(edit["offset"], 0)
                resume = s_va + len(after)
                cave = s_va + 5 + int.from_bytes(after[1:5], "little", signed=True)
                if not (0 <= cave - base < len(img)):
                    continue
                targets, fingerprint = _walk_cave(md, img, base, cave, lo, hi)
                fingerprints[(fingerprint_feature_id, edit["offset"])] = fingerprint
                for dst in sorted(targets):
                    if dst == resume:
                        continue
                    reentries[(fingerprint_feature_id, edit["offset"], dst)] = _derefs(
                        md, img, base, dst
                    )
    return reentries, fingerprints, skipped


@unittest.skipUnless(HAVE_DEPS, "requires capstone and pefile")
@unittest.skipUnless(STOCK.exists(), "requires the exact-build VV1 stock executable")
class VV1HookForeignReentryAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.reentries, cls.fingerprints, cls.skipped = _collect()

    def test_no_feature_silently_dropped_from_the_audit(self) -> None:
        # A feature that fails to render contributes no hooks, so a new
        # foreign re-entry inside it would pass unnoticed.
        unexpected = {
            fid: why
            for fid, why in self.skipped.items()
            if fid not in EXPECTED_UNRENDERABLE
        }
        self.assertEqual(
            unexpected,
            {},
            "VV1 feature(s) failed to render, so their hooks were not audited. "
            "Fix the rendering or record the feature in EXPECTED_UNRENDERABLE "
            f"with a reason: {unexpected}",
        )

    def test_every_foreign_reentry_is_reviewed(self) -> None:
        def review_key(key):
            feature_id, splice, target = key
            if feature_id == "vv1_birth_control+origins":
                feature_id = "vv1_birth_control"
            return feature_id, splice, target

        unreviewed = {
            k: v for k, v in self.reentries.items() if review_key(k) not in REVIEWED
        }
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
        missing = sorted(
            f"{a}@{b}->{hex(c)}"
            for (a, b, c) in REVIEWED
            if not any(
                (a, b, c)
                == (
                    "vv1_birth_control" if fid == "vv1_birth_control+origins" else fid,
                    splice,
                    target,
                )
                for fid, splice, target in self.reentries
            )
        )
        self.assertEqual(
            missing,
            [],
            "REVIEWED lists re-entries that no longer exist; prune them so the "
            "audit keeps reflecting the real hooks.",
        )

    def test_reviewed_caves_have_not_changed(self) -> None:
        # A review is a statement about the cave's register behaviour, not
        # just about which address it jumps to. If the cave's code changed,
        # the recorded reasoning must be re-checked even when every jump
        # target stayed identical.
        drifted = {
            f"{fid}@{splice}": {
                "recorded": COMPOSED_CAVE_FINGERPRINTS.get(
                    (fid, splice), CAVE_FINGERPRINTS.get((fid, splice))
                ),
                "actual": actual,
            }
            for (fid, splice), actual in self.fingerprints.items()
            if (
                COMPOSED_CAVE_FINGERPRINTS.get(
                    (fid, splice), CAVE_FINGERPRINTS.get((fid, splice))
                )
                != actual
            )
        }
        self.assertEqual(
            drifted,
            {},
            "Cave code changed. Re-verify the register contract recorded in "
            "REVIEWED for these hooks, then update CAVE_FINGERPRINTS: "
            f"{drifted}",
        )

    def test_composed_birth_control_reentries_match_standalone_contract(self) -> None:
        standalone = {
            (splice, target): derefs
            for (feature_id, splice, target), derefs in self.reentries.items()
            if feature_id == "vv1_birth_control"
        }
        composed = {
            (splice, target): derefs
            for (feature_id, splice, target), derefs in self.reentries.items()
            if feature_id == "vv1_birth_control+origins"
        }
        self.assertEqual(composed, standalone)


if __name__ == "__main__":
    unittest.main()
