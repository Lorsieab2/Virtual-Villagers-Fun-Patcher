"""Generate A New Home's and The Lost Children's villager-record guards (data/builds.json).

Both games keep 256 villager records and their creators take the first record
whose occupied byte is 0 with no bound of their own (A New Home 0x43C374 and
0x43C860 walk off the end of the table; The Lost Children's three scans are
stopped at record 255 by an older safety patch and take it over).  A corpse
keeps its record until the game removes it, so "the population is below the
cap" never meant "a record is free": the living, the babies still owed and the
corpses together can fill all 256 records.  Every guard here decides from the
occupied records themselves, counted by a bounded sweep, and nothing is spent
when there is no record: the creation waits, or does not happen at all.

What went wrong before this file (v1.35.58):
  * A New Home's twin and triplet guards compared [world+0x9E24] -- Babies
    Made, a lifetime total -- with 256: once a village had made 256 babies it
    never had twins or triplets again.  Its event guard read [array+0x9E24],
    a field of record 41.  The Lost Children's guards read the population
    counter 0x425860, which leaves the corpses out.
  * A New Home's Golden Child puzzle (the drop handler 0x424150, 0x4242F8)
    and the Mysterious Face's newcomer (0x41974A) called the creator with no
    guard: with every record occupied the puzzle's child went to the 257th
    record, which no loop reads -- the owner's vanished Golden Child -- while
    the mother's pregnancy was spent.  The Lost Children's Strange Request
    (always offered) handed its stranger record 255 -- a villager, whom both
    answers then take away.
  * A delivery with no free record made what it could and cleared the
    pregnancy, losing the rest of the litter; it now waits, pregnancy kept,
    until the whole litter fits (a corpse is removed in time).  That also
    makes the twin and triplet copies always find their record.
  * The births' guards called the creator from the cave, so the creator's
    return address was the cave's, not the delivery's: Cause of Death's
    birth markers (cod_arrival_sites.inc) never matched in a patched build.
    Every guard now leaves the stock return address in place.

Run after changing anything here; tests/test_slot_guards_count_records.py
runs every guard in an emulator.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

from keystone import KS_ARCH_X86, KS_MODE_32, Ks

ROOT = Path(__file__).resolve().parents[1]
BUILDS = ROOT / "data" / "builds.json"
STOCK = ROOT / "research" / "stock-executables"
EXE = {"vv1": "Virtual Villagers - A New Home.exe", "vv2": "Virtual Villagers - The Lost Children.exe"}
BASE = 0x400000

KS = Ks(KS_ARCH_X86, KS_MODE_32)


def asm(source: str, va: int) -> bytes:
    encoding, _ = KS.asm(source, va)
    return bytes(encoding)


# ---- A New Home -------------------------------------------------------------
# The record count, a bounded sweep: ecx = the villager array, preserved;
# eax = how many of the 256 records are occupied (corpses included); edx = the
# babies still owed (Codex, #543; the owner: "pending babies count toward
# population"): every living (+0x344 above 0) occupied record carrying
# (+0x358) is owed her litter (+0x35C: 0 one baby, 2 twins, 3 triplets) -- a
# dead mother's babies are never born: the tick skips her (0x42EC86).  A
# delivery adds only its own mother's extra babies to eax; a newcomer, a
# litter or the puzzle adds edx (V1_OWED_FULL).  It replaces the
# occupied-only sweep that was at 0x456860: A New Home's .text has no other
# unclaimed cave (every render's claimed ranges were measured), so the Golden
# Child puzzle's check moves into the 8 free bytes before it and the sweep
# follows it.
V1_COUNT = 0x45684B
V1_CREATE = 0x43C350          # fresh creator: thiscall (array), 5 args, ret 0x14
V1_ROOM = 0x43A1A0            # the game's room predicate: thiscall (array), al

V1_DEMAND = 0x456580          # the occupied records plus the delivery's extra babies
V1_GOLDEN_EXTRA = 0x456594    # the golden-child mother's delivery (two records and the litter)
V1_DEFER = 0x4565A6           # wait: the delivery's arguments dropped, the tick goes on (0x42F0CE)
V1_SINGLE = 0x4565B0          # any other delivery (one record and the litter)
V1_FACE_ROOM = 0x4565C4       # the Mysterious Face's room question
V1_LITTER = 0x4565E0          # twins/triplets at conception
V1_EVENT = 0x456680           # island events' children (Barrel, crate)
V1_GOLDEN_PUZZLE = 0x456838   # the Golden Child puzzle
V1_OWED_FULL = 0x456692       # every record taken or owed: ZF clear when none is free

VV1_CODE = {
    V1_COUNT: """
        push ecx
        push esi
        lea esi, [ecx + 0x358]
        xor ecx, ecx
        mul ecx
        inc ch
    top:
        cmp byte ptr [esi - 0x330], 0
        je next
        inc eax
        cmp dword ptr [esi - 0x14], 0
        jle next
        cmp dword ptr [esi], 0
        je next
        cmp dword ptr [esi + 4], 1
        adc edx, dword ptr [esi + 4]
    next:
        add esi, 0x3D8
        loop top
        pop esi
        pop ecx
        ret
    """,
    V1_DEMAND: f"""
        call {V1_COUNT:#x}
        mov edx, dword ptr [ecx + edi + 0x35C]
        test edx, edx
        jz single
        dec edx
    single:
        add eax, edx
        ret
    """,
    V1_GOLDEN_EXTRA: f"""
        call {V1_DEMAND:#x}
        cmp eax, 0xFE
        ja {V1_DEFER:#x}
        jmp {V1_CREATE:#x}
    """,
    V1_DEFER: """
        pop eax
        add esp, 0x14
        jmp 0x42F0CE
    """,
    V1_SINGLE: f"""
        call {V1_DEMAND:#x}
        cmp eax, 0xFF
        ja {V1_DEFER:#x}
        jmp {V1_CREATE:#x}
    """,
    V1_FACE_ROOM: f"""
        push ecx
        call {V1_ROOM:#x}
        pop ecx
        test al, al
        jz done
        call {V1_OWED_FULL:#x}
        sete al
    done:
        ret
    """,
    V1_LITTER: f"""
        mov ecx, edi
        call {V1_COUNT:#x}
        add eax, edx
        mov edx, dword ptr [esp + 4]
        add eax, edx
        cmp eax, 0x102
        jae done
        mov dword ptr [esi + 0x35C], edx
    done:
        ret 4
    """,
    V1_EVENT: f"""
        call {V1_OWED_FULL:#x}
        jnz full
        jmp {V1_CREATE:#x}
    full:
        or eax, -1
        ret 0x14
    """,
    V1_OWED_FULL: f"""
        call {V1_COUNT:#x}
        add eax, edx
        test ah, ah
        ret
    """,
    V1_GOLDEN_PUZZLE: f"""
        call {V1_OWED_FULL:#x}
        jnz done
        mov dword ptr [ecx + edi + 0x394], 0xC7
    done:
        ret
    """,
}

# Each claimed block of the cave (start: size, purpose); its routines are
# packed from VVx_CODE at their own addresses.
VV1_CAVE_PURPOSE = {
    0x456580: (48, "a delivery's record demand: the occupied records plus the extra babies of the "
                   "mother's litter (+0x35C: 2 twins, 3 triplets); the golden-child mother's delivery "
                   "only when her two children and the litter fit, else it waits with the pregnancy kept "
                   "(the arguments dropped, the tick goes on at 0x42F0CE); the creator returns to "
                   "0x42EF64 as in the stock game"),
    0x4565B0: (48, "any other delivery only when its child and the litter fit, else it waits; the creator "
                   "returns to 0x42EFD5 as in the stock game. Then the Mysterious Face's room question: "
                   "the game's room predicate, and a free record"),
    0x4565E0: (32, "twins or triplets at conception only when the occupied records and the babies still "
                   "owed (her own one baby already counted) plus the rest of the litter fit in 256 (the "
                   "litter is the call's argument); otherwise CF clear and the conception's own branch is "
                   "taken"),
    0x456680: (28, "an island event's child only when a record is free after the babies still owed: the "
                   "creator with the caller's own return address, else -1 (the callers ignore the index); "
                   "then the records taken or owed, with ZF clear when none is free (the event's, the "
                   "Mysterious Face's and the puzzle's own question)"),
    0x456838: (19, "the Golden Child puzzle's check: a record free after the babies still owed, and the "
                   "puzzle's first write (the mother's +0x394 = 0xC7) only then -- ZF tells the drop handler "
                   "which"),
    0x45684B: (53, "the record count: the occupied records (the +0x28 byte; corpses included) in eax and "
                   "the babies still owed in edx -- every living occupied record carrying (+0x358) her "
                   "litter (+0x35C, one baby at least) -- across the 256 records, ecx preserved "
                   "(Codex, #543)"),
}

VV1_SITES = [
    # (file offset, stock bytes, assembly at the site, purpose)
    (0x2EF5F, "E8ECD30000", f"call {V1_GOLDEN_EXTRA:#x}",
     "the golden-child mother's delivery: through the record guard, the creator returning here"),
    (0x2EFD0, "E87BD30000", f"call {V1_SINGLE:#x}",
     "a delivery's first child: through the record guard, the creator returning here"),
    (0x3BC4E, "C7865C03000002000000", f"push 2; call {V1_LITTER:#x}; jae 0x43BC4C; nop",
     "twins at conception only when the records fit them; otherwise back to the twins roll's own "
     "branch (0x43BC4C), whatever that branch is composed to"),
    (0x3BC8C, "C7865C03000003000000", f"push 3; call {V1_LITTER:#x}; jae 0x43BC8A; nop",
     "triplets at conception only when the records fit them; otherwise back to the triplets roll's own "
     "branch (0x43BC8A)"),
    (0x2427B, "C7843994030000C7000000", f"call {V1_GOLDEN_PUZZLE:#x}; jnz 0x4243AC",
     "the Golden Child puzzle fires only when a record is free: otherwise the drop is answered as when "
     "the puzzle is not ready (0x4243AC), and nothing is spent -- the latch, the hour and the pregnancy "
     "are kept"),
    (0x19700, "E89B0A0200", f"call {V1_FACE_ROOM:#x}",
     "the Mysterious Face asks for a free record too before its newcomer (0x41974A, which the Story "
     "companion detours at run time, is left as it is)"),
]

# ---- The Lost Children ------------------------------------------------------
V2_CREATE_EVENT = 0x44F580    # the event wrapper: thiscall (array), 5 args, ret 0x14
V2_ROOM = 0x44B310            # the game's room predicate: thiscall (array), al
V2_ARRAY_OF_WORLD = 0x305A4   # world -> villager array
V2_WORLD_OF_ARRAY = 0xE574D4  # villager array -> world

V2_COUNT = 0x473C40           # the record count (new): ecx = world, preserved
V2_LITTER = 0x473C70
V2_EVENT = 0x473D00
V2_DELIVERY = 0x473F20
V2_ROOM_AND_RECORD = 0x473F64
V2_STRANGER = 0x473F84
V2_OWED = 0x473F9C            # the occupied records plus every baby still owed (new; a free run every render leaves, 0x473F99-0x473FED)

VV2_CODE = {
    V2_COUNT: f"""
        push ecx
        mov ecx, dword ptr [ecx + {V2_ARRAY_OF_WORLD:#x}]
        xor eax, eax
        lea edx, [ecx + 0x30]
        mov ecx, 0x100
    top:
        cmp byte ptr [edx], 0
        je next
        inc eax
    next:
        add edx, 0xE48C
        dec ecx
        jnz top
        pop ecx
        ret
    """,
    # The babies still owed (Codex, #543): every living villager carrying
    # (+0x540) is owed her litter (+0x544, one baby at least).  ecx = the
    # world, preserved; eax = the records taken or owed; edx clobbered.
    V2_OWED: f"""
        push esi
        push edi
        call {V2_COUNT:#x}
        mov esi, dword ptr [ecx + {V2_ARRAY_OF_WORLD:#x}]
        mov edi, 0x100
    top:
        cmp byte ptr [esi + 0x30], 0
        je next
        cmp dword ptr [esi + 0x52C], 0
        jle next
        cmp dword ptr [esi + 0x540], 0
        je next
        mov edx, dword ptr [esi + 0x544]
        test edx, edx
        jnz litter
        inc edx
    litter:
        add eax, edx
    next:
        add esi, 0xE48C
        dec edi
        jnz top
        pop edi
        pop esi
        ret
    """,
    V2_LITTER: f"""
        mov ecx, dword ptr [edi + {V2_WORLD_OF_ARRAY:#x}]
        call {V2_OWED:#x}
        mov edx, dword ptr [esp + 4]
        lea eax, [eax + edx - 1]
        cmp eax, 0x101
        jae done
        mov dword ptr [esi + 0x544], edx
    done:
        ret 4
    """,
    V2_EVENT: f"""
        push ecx
        mov ecx, dword ptr [ebp + 0x50A4]
        test ecx, ecx
        je refuse
        cmp dword ptr [ecx + {V2_ARRAY_OF_WORLD:#x}], 0
        je refuse
        call {V2_OWED:#x}
        pop ecx
        test ah, ah
        jnz full
        jmp {V2_CREATE_EVENT:#x}
    refuse:
        pop ecx
    full:
        or eax, -1
        ret 0x14
    """,
    V2_DELIVERY: f"""
        pushal
        mov ecx, dword ptr [esi]
        call {V2_COUNT:#x}
        mov edx, dword ptr [esi + 4]
        mov edx, dword ptr [edx + edi + 0x544]
        test edx, edx
        jz single
        dec edx
    single:
        add eax, edx
        cmp eax, 0xFF
        popal
        ja wait
        call 0x44F5C0
        jmp 0x43BE93
    wait:
        add esp, 0x2C
        jmp 0x43BF8C
    """,
    V2_ROOM_AND_RECORD: f"""
        push ecx
        call {V2_ROOM:#x}
        pop ecx
        test al, al
        jz done
        push ecx
        mov ecx, dword ptr [ecx + {V2_WORLD_OF_ARRAY:#x}]
        call {V2_OWED:#x}
        pop ecx
        test ah, ah
        sete al
    done:
        ret
    """,
    V2_STRANGER: f"""
        mov ecx, dword ptr [esi + 0x50AC]
        call {V2_OWED:#x}
        test ah, ah
        sete bl
        jmp 0x41F696
    """,
}

VV2_CAVE_PURPOSE = {
    V2_COUNT: (48, "boundedly count the occupied records (the +0x30 byte; corpses included) across the "
                   "256-record pool from the world argument, preserving ecx"),
    V2_LITTER: (48, "twins or triplets at conception only when the occupied records plus the litter fit in "
                    "256 (the litter is the call's argument); otherwise CF clear and the conception's own "
                    "branch is taken"),
    V2_EVENT: (48, "an island event's villager only when a record is free after the babies still owed: "
                   "the event wrapper with the caller's own return address, else -1"),
    V2_OWED: (68, "the records taken or owed: the occupied records (corpses included) plus, for every "
                  "living villager carrying, her litter (one baby at least) -- the newcomers' and the "
                  "litters' own check (Codex, #543)"),
    V2_DELIVERY: (68, "a delivery only when its child and the litter's extra babies (+0x544) fit in the "
                      "records, else it waits with the pregnancy kept (the twin and triplet copies then "
                      "always find their record)"),
    V2_ROOM_AND_RECORD: (32, "the game's room predicate, and a free record (The Silver Mirror's copy, The "
                             "Savage Child's newcomer)"),
    V2_STRANGER: (24, "The Strange Request is offered only with a free record for its stranger (stock: "
                      "always offered; with every record occupied the bounded scan handed it record 255, "
                      "a villager, whom both answers then take away)"),
}

VV2_SITES = [
    (0x4BA82, "C7864405000002000000", f"push 2; call {V2_LITTER:#x}; jae 0x44BA80; nop",
     "twins at conception only when the records fit them; otherwise back to the twins roll's own branch"),
    (0x4BAB6, "C7864405000003000000", f"push 3; call {V2_LITTER:#x}; jae 0x44BAB4; nop",
     "triplets at conception only when the records fit them; otherwise back to the triplets roll's own "
     "branch"),
    (0x3BE8E, "E82D370100", f"jmp {V2_DELIVERY:#x}",
     "a delivery only when its whole litter fits in the records"),
    (0x217DF, "E82C9B0200", f"call {V2_ROOM_AND_RECORD:#x}",
     "The Silver Mirror asks for a free record too before its copy (0x4217F9)"),
    (0x1F604, "E807BD0200", f"call {V2_ROOM_AND_RECORD:#x}",
     "The Savage Child (event 4) is offered only with room and a free record for its newcomer "
     "(0x4209A4; its answer pays 500 food first)"),
    (0x1F6D4, "94F64100", None,
     "The Strange Request (event 3), always offered in the stock game, through the free-record check"),
]
VV2_TABLE_ENTRY = {0x1F6D4: V2_STRANGER}


def cave_entries(code: dict[int, str], purpose: dict[int, tuple[int, str]]) -> list[dict]:
    """Each claimed block: its routines packed at their own addresses, zero-padded."""
    out = []
    starts = sorted(code)
    for start, (size, text) in sorted(purpose.items()):
        body = b""
        for s in [s for s in starts if start <= s < start + size]:
            if len(body) > s - start:
                raise SystemExit(f"{s:#x} overlaps the routine before it")
            body = body.ljust(s - start, b"\x00")
            body += asm(code[s], s)
        if len(body) > size:
            raise SystemExit(f"{start:#x}: {len(body)} bytes do not fit in {size}")
        out.append({
            "offset": f"0x{start - BASE:X}",
            "before": "00" * len(body),
            "after": body.hex().upper(),
            "purpose": text,
        })
    return out


def site_entries(game: str, sites, table=None) -> list[dict]:
    stock = (STOCK / EXE[game]).read_bytes()
    out = []
    for offset, before, source, purpose in sites:
        b = bytes.fromhex(before)
        if stock[offset:offset + len(b)] != b:
            raise SystemExit(f"{game} {offset:#x}: stock bytes differ")
        code = asm(source, offset + BASE) if source is not None else struct.pack("<I", table[offset])
        if len(code) != len(b):
            raise SystemExit(f"{game} {offset:#x}: {len(code)} bytes for {len(b)}")
        out.append({"offset": f"0x{offset:X}", "before": before, "after": code.hex().upper(),
                    "purpose": purpose})
    return out


# Entries this file owns, by file offset (replaced on every run; an owned
# offset that is no longer generated is removed).
OWNED = {
    "vv1": {0x2EF5F, 0x2EFD0, 0x3BC4E, 0x3BC8C, 0x56580, 0x565B0, 0x565E0, 0x56680, 0x56840,
            0x2427B, 0x2F020, 0x2F06C, 0x19700, 0x56838, 0x5684B, 0x5684F, 0x56860},
    "vv2": {0x3BE8E, 0x73F20, 0x4BA82, 0x73C40, 0x4BAB6, 0x73C70, 0x73D00, 0x3BEDE, 0x3BF2A, 0x217DF,
            0x73F44, 0x73F64, 0x1F604, 0x1F6D4, 0x73F84, 0x73F9C},
}


def main() -> None:
    data = json.loads(BUILDS.read_text(encoding="utf-8"))
    new = {
        "vv1": site_entries("vv1", VV1_SITES) + cave_entries(VV1_CODE, VV1_CAVE_PURPOSE),
        "vv2": site_entries("vv2", VV2_SITES, VV2_TABLE_ENTRY) + cave_entries(VV2_CODE, VV2_CAVE_PURPOSE),
    }
    for game in data["games"]:
        if game["id"] not in new:
            continue
        kept = [p for p in game["safety_patches"] if int(p["offset"], 16) not in OWNED[game["id"]]]
        game["safety_patches"] = new[game["id"]] + kept
        for p in new[game["id"]]:
            print(game["id"], p["offset"], len(p["after"]) // 2, p["after"])
    # builds.json is stored with CRLF line ends (-text): keep them.
    BUILDS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\r\n")


if __name__ == "__main__":
    main()
