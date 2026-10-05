"""Generate A New Home's and The Lost Children's villager-slot guards (data/builds.json).

Both games keep 256 villager records and their creators take the first record
whose occupied byte is 0 with no bound of their own (A New Home 0x43C374 and
0x43C860; The Lost Children's three scans stop at record 255 and reuse it).
A corpse keeps its record until the game removes it, so "the population is
below 256" never meant "a record is free": the living, the babies still owed
and the corpses together can fill all 256 records.  Every guard here decides
from the occupied records themselves, counted by a bounded sweep.

What went wrong before this file (v1.35.58):
  * A New Home's twin and triplet guards compared [world+0x9E24] -- Babies
    Made, a lifetime total -- with 256: once a village had made 256 babies it
    never had twins or triplets again.  Its event guard read [array+0x9E24],
    a field of record 41.  The Lost Children's guards read the population
    counter 0x425860, which leaves the corpses out.
  * A New Home's Golden Child puzzle (the drop handler 0x424150, 0x4242F8)
    and the Mysterious Face's newcomer (0x41974A) called the creator with no
    guard, and its delivery's twin and triplet copies (0x42F021, 0x42F06D)
    likewise: with every record occupied the puzzle's child went to the
    257th record no loop reads -- the owner's vanished Golden Child -- while
    the mother's pregnancy was spent.
  * The births' guards called the creator from the cave, so the creator's
    return address was the cave's, not the delivery's: Cause of Death's
    birth markers (cod_arrival_sites.inc) never matched in a patched build.
    Every guard now leaves the stock return address in place.

Run after changing anything here; tests/test_slot_guards_count_records.py
emulates every guard.
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
# The record count: the existing bounded sweep (unchanged), ecx = the villager
# array, preserved; eax = how many of the 256 records are occupied (corpses
# included); edx clobbered.
V1_COUNT = 0x456860
V1_CREATE = 0x43C350          # fresh creator: thiscall (array), 5 args, ret 0x14
V1_COPY = 0x43C840            # copy creator: thiscall (array), 1 arg, ret 4
V1_ROOM = 0x43A1A0            # the game's room predicate: thiscall (array), al

V1_GOLDEN_EXTRA = 0x456580    # the golden-child mother's extra child (two records)
V1_GOLDEN_PUZZLE = 0x45659A   # the Golden Child puzzle
V1_COPY_GUARD = 0x4565B0      # the delivery's twin and triplet copies
V1_SINGLE = 0x4565C8          # a delivery's first child
V1_LITTER = 0x4565E0          # twins/triplets at conception
V1_EVENT = 0x456680           # island events' children (Barrel, crate), the Face
V1_FACE_ROOM = 0x456840       # the Mysterious Face's room question

VV1_CODE = {
    V1_GOLDEN_EXTRA: f"""
        call {V1_COUNT:#x}
        cmp eax, 0xFF
        jae full
        jmp {V1_CREATE:#x}
    full:
        pop eax
        add esp, 0x14
        jmp 0x42EF9B
    """,
    V1_GOLDEN_PUZZLE: f"""
        call {V1_COUNT:#x}
        test ah, ah
        jnz done
        mov dword ptr [ecx + edi + 0x394], 0xC7
    done:
        ret
    """,
    V1_COPY_GUARD: f"""
        call {V1_COUNT:#x}
        test ah, ah
        jnz full
        pop eax
        inc eax
        push ebx
        push eax
        jmp {V1_COPY:#x}
    full:
        pop eax
        jmp 0x42F0A9
    """,
    V1_SINGLE: f"""
        call {V1_COUNT:#x}
        test ah, ah
        jnz full
        jmp {V1_CREATE:#x}
    full:
        pop eax
        add esp, 0x14
        jmp 0x42F0A9
    """,
    V1_LITTER: f"""
        mov ecx, edi
        call {V1_COUNT:#x}
        mov edx, dword ptr [esp + 4]
        add eax, edx
        cmp eax, 0x101
        jae done
        mov dword ptr [esi + 0x35C], edx
    done:
        ret 4
    """,
    V1_EVENT: f"""
        call {V1_COUNT:#x}
        test ah, ah
        jnz full
        jmp {V1_CREATE:#x}
    full:
        or eax, -1
        ret 0x14
    """,
    V1_FACE_ROOM: f"""
        push ecx
        call {V1_ROOM:#x}
        pop ecx
        test al, al
        jz done
        call {V1_COUNT:#x}
        test ah, ah
        sete al
    done:
        ret
    """,
}

VV1_CAVE_PURPOSE = {
    V1_GOLDEN_EXTRA: (47, "the golden-child mother's extra child (0x42EF5F) only when two records are free, "
                          "else the delivery's other child alone (0x42EF9B); the creator returns to 0x42EF64 as "
                          "in the stock game. Then the Golden Child puzzle's check: the record count, and the "
                          "puzzle's first write (the mother's +0x394 = 0xC7) only when a record is free -- ZF "
                          "tells the drop handler which"),
    V1_COPY_GUARD: (47, "a delivery's twin or triplet copy only when a record is free (else the rest of the "
                        "litter is skipped, 0x42F0A9), returning to the delivery's own next instruction "
                        "(0x42F026 / 0x42F072); then a delivery's first child only when a record is free, the "
                        "creator returning to 0x42EFD5 as in the stock game"),
    V1_LITTER: (29, "twins or triplets at conception only when the occupied records plus the litter fit in "
                    "256 (the litter is the call's argument); otherwise CF clear and the conception's own "
                    "singleton or twins branch is taken"),
    V1_EVENT: (20, "an island event's child only when a record is free: the creator with the caller's own "
                   "return address, else -1 (the callers ignore the index)"),
    V1_FACE_ROOM: (22, "the Mysterious Face's newcomer: the game's room predicate, and a free record"),
}

VV1_SITES = [
    # (file offset, stock bytes, assembly at the site, purpose)
    (0x2EF5F, "E8ECD30000", f"call {V1_GOLDEN_EXTRA:#x}",
     "the golden-child mother's extra child: through the record guard, the creator returning here"),
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
    (0x2F020, "53E81AD80000", f"call {V1_COPY_GUARD:#x}; nop",
     "the delivery's twin copy through the record guard"),
    (0x2F06C, "53E8CED70000", f"call {V1_COPY_GUARD:#x}; nop",
     "the delivery's triplet copy through the record guard"),
    (0x19700, "E89B0A0200", f"call {V1_FACE_ROOM:#x}",
     "the Mysterious Face asks for a free record too before its newcomer (0x41974A, which the Story "
     "companion detours at run time, is left as it is)"),
]

# ---- The Lost Children ------------------------------------------------------
V2_CREATE_EVENT = 0x44F580    # the event wrapper: thiscall (array), 5 args, ret 0x14
V2_COPY = 0x44CEC0            # copy creator: thiscall (array), 1 arg, ret 4
V2_ROOM = 0x44B310            # the game's room predicate: thiscall (array), al
V2_ARRAY_OF_WORLD = 0x305A4   # world -> villager array
V2_WORLD_OF_ARRAY = 0xE574D4  # villager array -> world

V2_COUNT = 0x473C40           # the record count (new)
V2_LITTER = 0x473C70
V2_EVENT = 0x473D00
V2_DELIVERY = 0x473F20
V2_COPY_GUARD = 0x473F44
V2_MIRROR_ROOM = 0x473F64
V2_STRANGER = 0x473F84

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
    V2_LITTER: f"""
        mov ecx, dword ptr [edi + {V2_WORLD_OF_ARRAY:#x}]
        call {V2_COUNT:#x}
        mov edx, dword ptr [esp + 4]
        add eax, edx
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
        call {V2_COUNT:#x}
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
        test ah, ah
        popal
        jnz full
        call 0x44F5C0
        jmp 0x43BE93
    full:
        add esp, 0x2C
        jmp 0x43BF8C
    """,
    V2_COPY_GUARD: f"""
        push ecx
        mov ecx, dword ptr [esi]
        call {V2_COUNT:#x}
        pop ecx
        test ah, ah
        jnz full
        pop eax
        inc eax
        push ebx
        push eax
        jmp {V2_COPY:#x}
    full:
        pop eax
        jmp 0x43BF67
    """,
    V2_MIRROR_ROOM: f"""
        push ecx
        call {V2_ROOM:#x}
        pop ecx
        test al, al
        jz done
        push ecx
        mov ecx, dword ptr [ecx + {V2_WORLD_OF_ARRAY:#x}]
        call {V2_COUNT:#x}
        pop ecx
        test ah, ah
        sete al
    done:
        ret
    """,
    V2_STRANGER: f"""
        mov ecx, dword ptr [esi + 0x50AC]
        call {V2_COUNT:#x}
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
    V2_EVENT: (48, "an island event's villager only when a record is free: the event wrapper with the "
                   "caller's own return address, else -1"),
    V2_DELIVERY: (36, "defer a delivery (the pregnancy is kept) while every record is occupied"),
    V2_COPY_GUARD: (32, "a delivery's twin or triplet copy only when a record is free (else the rest of the "
                        "litter is skipped, 0x43BF67), returning to the delivery's own next instruction"),
    V2_MIRROR_ROOM: (32, "the game's room predicate, and a free record (The Silver Mirror's copy, The "
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
     "a delivery's first child only when a record is free"),
    (0x3BEDE, "53E8DC0F0100", f"call {V2_COPY_GUARD:#x}; nop",
     "the delivery's twin copy through the record guard"),
    (0x3BF2A, "53E8900F0100", f"call {V2_COPY_GUARD:#x}; nop",
     "the delivery's triplet copy through the record guard"),
    (0x217DF, "E82C9B0200", f"call {V2_MIRROR_ROOM:#x}",
     "The Silver Mirror asks for a free record too before its copy (0x4217F9)"),
    (0x1F604, "E807BD0200", f"call {V2_MIRROR_ROOM:#x}",
     "The Savage Child (event 4) is offered only with room and a free record for its newcomer "
     "(0x4209A4; its answer pays 500 food first)"),
    (0x1F6D4, "94F64100", None,
     "The Strange Request (event 3), always offered in the stock game, through the free-record check"),
]


def cave_entries(code: dict[int, str], purpose: dict[int, tuple[int, str]]) -> list[dict]:
    """Each claimed block: its routines packed from its start, zero-padded to its size."""
    out = []
    starts = sorted(code)
    for start, (size, text) in sorted(purpose.items()):
        body = b""
        members = [s for s in starts if start <= s < start + size]
        for s in members:
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


def site_entries(game: str, sites) -> list[dict]:
    stock = (STOCK / EXE[game]).read_bytes()
    out = []
    for offset, before, source, purpose in sites:
        b = bytes.fromhex(before)
        if stock[offset:offset + len(b)] != b:
            raise SystemExit(f"{game} {offset:#x}: stock bytes differ")
        code = asm(source, offset + BASE) if source is not None else struct.pack("<I", V2_STRANGER)
        if len(code) != len(b):
            raise SystemExit(f"{game} {offset:#x}: {len(code)} bytes for {len(b)}")
        out.append({"offset": f"0x{offset:X}", "before": before, "after": code.hex().upper(),
                    "purpose": purpose})
    return out


# Entries this file owns, by file offset (replaced on every run).
OWNED = {
    "vv1": {0x2EF5F, 0x2EFD0, 0x3BC4E, 0x3BC8C, 0x56580, 0x565B0, 0x565E0, 0x56680, 0x56840,
            0x2427B, 0x2F020, 0x2F06C, 0x19700},
    "vv2": {0x3BE8E, 0x73F20, 0x4BA82, 0x73C40, 0x4BAB6, 0x73C70, 0x73D00, 0x3BEDE, 0x3BF2A, 0x217DF,
            0x73F44, 0x73F64, 0x1F604, 0x1F6D4, 0x73F84},
}


def main() -> None:
    data = json.loads(BUILDS.read_text(encoding="utf-8"))
    new = {
        "vv1": site_entries("vv1", VV1_SITES) + cave_entries(VV1_CODE, VV1_CAVE_PURPOSE),
        "vv2": site_entries("vv2", VV2_SITES) + cave_entries(VV2_CODE, VV2_CAVE_PURPOSE),
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
