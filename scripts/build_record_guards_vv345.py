"""Generate The Secret City's, The Tree of Life's and New Believers' villager-record guards
(data/builds.json, the automatic safety layer, every population mode).

The three games' creators are bounded (they return -1 with every record
taken), but what the callers did with that -1 lost villagers and spent things
(the v1.35.58 Golden Child audit, approved by the owner for every mode):

  * a delivery whose creator got -1 cleared the pregnancy anyway -- the baby
    never existed and Babies Made stayed counted.  A delivery now waits, the
    pregnancy kept, until its whole litter fits in the free records;
  * the room predicate every conception, island event and barrel child asks
    (VV3 0x45FE30, VV4 0x468350, VV5 0x472BD0) counted the living (VV5 stock:
    the believers) against the cap.  Corpses, ghosts, Heathens and the babies
    still owed hold records too, so with the cap at the table size (the
    raising modes, the 256 builds) or enough of them (stock) it promised
    records that did not exist.  It now also answers "no room" while the
    records' demand -- every occupied record plus every baby still owed --
    has no record left;
  * New Believers' Reanimate (0x42341A) made its stand-in with no record
    check and crashed on a NULL record with every record taken: it is now
    refused, nothing spent, like a cast with no free spell slot, and says
    why in the gray message bar ("There's no room in your village to revive
    this person.") as the game's own god-power refusals say theirs;
  * The Secret City's Mysterious Vial (two copies) and Crystal of
    Reflections (one) asked for no record at all, and the Crystal changed
    the villager's likes before a clone that could fail: both are offered
    only with room for their copies, and the Crystal checks before it
    changes anything;
  * The Secret City's twin and triplet guards and its Canoe and Barrel
    guards counted occupied records but not the babies still owed.

Every room question counts the records the allocators themselves test
(corpses included).  The 256 builds rescale each row
(scripts/build_vv{3,4,5}_population_256_feature.py read RESCALE_256 here).
tests/test_slot_guards_count_records.py runs every guard in an emulator.

Code space: VV5 has room at the end of .text.  VV3's and VV4's .text tails are
full, so their code goes in a page the loader already maps: VV3's .shr page
(made executable here, exactly as Everyone Tries On The Robe makes it -- the
two identical header writes are allowed together), VV4's .rdata tail (made
executable here, exactly as Origins makes it).
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

from keystone import KS_ARCH_X86, KS_MODE_32, Ks

ROOT = Path(__file__).resolve().parents[1]
BUILDS = ROOT / "data" / "builds.json"
STOCK = ROOT / "research" / "stock-executables"
EXE = {"vv3": "Virtual Villagers - The Secret City.exe", "vv4": "Virtual Villagers - The Tree of Life.exe",
       "vv5": "Virtual Villagers - New Believers.exe"}
KS = Ks(KS_ARCH_X86, KS_MODE_32)


def asm(source: str | bytes, va: int) -> bytes:
    """Assemble `source` at `va`; bytes (a block's text) are placed as they are."""
    if isinstance(source, bytes):
        return source
    encoding, _ = KS.asm(source, va)
    return bytes(encoding)


def h32(v: int) -> str:
    return struct.pack("<I", v).hex().upper()


# ---- per game -----------------------------------------------------------------
# file_of: VA -> file offset for the cave's section.
GAMES = {
    "vv3": dict(slots=0x96, base=0x59E124, stride=0x1F8C, active=0xF10, pregnant=0xE8C, litter=0xE90,
                cave_va=0x6C8300, cave_file=0xB4300, headers=[(0x280, "04000000", "00100000"),
                                                             (0x29C, "400000D0", "600000F0")],
                base_256=0x800014),
    "vv4": dict(slots=0x96, base=0x50E5AC, stride=0x2E3C, active=0x1CC4, pregnant=0x1C4C, litter=0x1C50,
                cave_va=0x4B7500, cave_file=0xB7500, headers=[(0x244, "40000040", "40000060")],
                base_256=0x800044),
    "vv5": dict(slots=0x96, base=0x554190, stride=0x2F44, active=0x1CD4, pregnant=0x1C4C, litter=0x1C50,
                cave_va=0x494BE0, cave_file=0x94BE0, headers=[],
                base_256=0x800048),
}
# New Believers' gray message bar, where every god-power refusal is said:
# Bar::SetText(stringId, param) @ 0x44EF60 (`this` = 0x520F68) looks the id up
# in Assets/sm.xml and, for a string with no format and param -1, does
# strncpy(bar, text, 0xFF), then [bar + 0x100] = the game clock (0x425950 ->
# 0x4036E0) + 5: the bar's five-second display.  sm.xml has no string for
# Reanimate's refusal and the patcher never changes the game's assets, so the
# guard runs that same tail with its own text.
VV5_BAR = 0x520F68
VV5_STRNCPY, VV5_CLOCK, VV5_SECONDS = 0x47D7C0, 0x425950, 0x4036E0
REANIMATE_NO_ROOM = "There's no room in your village to revive this person."

HEADER_PURPOSE = {
    "vv3": ["map the whole .shr page, where the record guards live (the same write Everyone Tries On The "
            "Robe makes)",
            "mark the .shr page executable for the record guards (the same write Everyone Tries On The Robe "
            "makes)"],
    "vv4": ["mark .rdata executable: the record guards live in its tail (the same write Origins makes)"],
}


def occupied(g) -> str:
    """eax = the occupied records (the active byte; corpses included); ecx, edx kept."""
    return f"""
        push ecx
        push edx
        xor eax, eax
        mov edx, {g['base']:#x}
        mov ecx, {g['slots']:#x}
    top:
        cmp byte ptr [edx + {g['active']:#x}], 0
        je next
        inc eax
    next:
        add edx, {g['stride']:#x}
        dec ecx
        jnz top
        pop edx
        pop ecx
        ret
    """


def demand(g) -> str:
    """eax = the occupied records plus every baby still owed; ecx, edx kept."""
    return f"""
        push ecx
        push edx
        xor eax, eax
        mov edx, {g['base']:#x}
        mov ecx, {g['slots']:#x}
    top:
        cmp byte ptr [edx + {g['active']:#x}], 0
        je next
        inc eax
        cmp dword ptr [edx + {g['pregnant']:#x}], 0
        je next
        add eax, dword ptr [edx + {g['litter']:#x}]
    next:
        add edx, {g['stride']:#x}
        dec ecx
        jnz top
        pop edx
        pop ecx
        ret
    """


def room_wrapper(g, population: int, demand_va: int) -> str:
    """The room predicate's population count, or 0x7FFF (no room at any cap) while the
    records' demand has no record left."""
    return f"""
        call {population:#x}
        push eax
        call {demand_va:#x}
        cmp eax, {g['slots']:#x}
        pop eax
        jb ok
        mov eax, 0x7FFF
    ok:
        ret
    """


def delivery(g, pregnant_rel: int, litter_rel: int, occupied_va: int) -> str:
    """ZF set: no delivery now (not pregnant, or the litter does not fit: the
    pregnancy waits); ZF clear: deliver, eax = the pregnancy field as before."""
    return f"""
        mov eax, dword ptr [esi + {pregnant_rel:#x}]
        test eax, eax
        jz out
        push eax
        push edx
        mov edx, dword ptr [esi + {litter_rel:#x}]
        test edx, edx
        jnz have
        inc edx
    have:
        call {occupied_va:#x}
        add eax, edx
        pop edx
        cmp eax, {g['slots'] + 1:#x}
        pop eax
        jb fits
        cmp eax, eax
        ret
    fits:
        test eax, eax
    out:
        ret
    """


def layout(game: str):
    """[(va, name, source)] in the cave, and the site rows."""
    g = GAMES[game]
    va = g["cave_va"]
    blocks = []
    names = {}

    def place(name, source_fn, align=16):
        nonlocal va
        va = (va + align - 1) & ~(align - 1)
        names[name] = va
        code = asm(source_fn(), va)
        blocks.append((va, name, source_fn, len(code)))
        va += len(code)

    if game == "vv3":
        place("demand", lambda: demand(g))
        place("room", lambda: room_wrapper(g, 0x45E8F0, names["demand"]))
        place("delivery", lambda: delivery(g, 0xC0, 0xC4, 0x47B318))
        place("vial", lambda: f"""
            test eax, eax
            jz no
            call {names['demand']:#x}
            cmp eax, {g['slots'] - 1:#x}
            setb al
            jmp done
        no:
            xor eax, eax
        done:
            pop esi
            ret
        """)
        place("crystal", lambda: f"""
            cmp eax, 2
            jge no
            call {names['demand']:#x}
            cmp eax, {g['slots']:#x}
            setb al
            ret
        no:
            xor eax, eax
            ret
        """)
        place("crystal_keep", lambda: f"""
            call {names['demand']:#x}
            cmp eax, {g['slots']:#x}
            jb ok
            pop eax
            mov dword ptr [esi + 0xC], 0
            pop esi
            ret 4
        ok:
            pop eax
            push edi
            mov edi, dword ptr [esi + 4]
            push 0x2B
            jmp eax
        """)
        sites = [
            (0x5FE37, "E8B4EAFFFF", lambda: f"call {names['room']:#x}",
             "the room predicate 0x45FE30 answers no room while the records' demand (occupied records, "
             "corpses included, plus every baby still owed) has no record left"),
            (0x60341, "8B86C000000085C00F84C3010000", lambda: f"call {names['delivery']:#x}; je 0x460512; nop; nop; nop",
             "a delivery waits, the pregnancy kept, until its whole litter fits in the free records (the "
             "stock code cleared the pregnancy when the creator found no record)"),
            (0x178DA, "894604" "85C00F95C05EC3", lambda: f"mov dword ptr [esi + 4], eax; jmp {names['vial']:#x}; nop; nop",
             "The Mysterious Vial is offered only with room for its two copies"),
            (0x1580C, "33C983F8020F9CC18AC1C3", lambda: f"jmp {names['crystal']:#x}; nop; nop; nop; nop; nop; nop",
             "The Crystal of Reflections is offered only with room for its reflection"),
            (0x191EF, "578B7E046A2B", lambda: f"call {names['crystal_keep']:#x}; nop",
             "The Crystal of Reflections' keep checks for a record before it changes the villager's likes"),
        ]
        existing = {
            0x7B260: lambda: f"""
                call {names['demand']:#x}
                cmp eax, {g['slots'] - 2:#x}
                jg 0x455bdd
                mov dword ptr [esi + 0xe90], 3
                jmp 0x455bc9
            """,
            0x7B280: lambda: f"""
                call {names['demand']:#x}
                cmp eax, {g['slots'] - 1:#x}
                jg 0x455bed
                mov dword ptr [esi + 0xe90], 2
                jmp 0x455be7
            """,
        }
        retarget = {0x7B2E0: names["demand"], 0x7B300: names["demand"]}
    elif game == "vv4":
        place("occupied", lambda: occupied(g))
        place("room", lambda: room_wrapper(g, 0x467610, 0x4890F0))
        place("delivery", lambda: delivery(g, 0x10, 0x14, names["occupied"]))
        sites = [
            (0x68357, "E8B4F2FFFF", lambda: f"call {names['room']:#x}",
             "the room predicate 0x468350 answers no room while the records' demand (occupied records, "
             "corpses and ghosts included, plus every baby still owed) has no record left"),
            (0x687E4, "8B461085C00F842B020000", lambda: f"call {names['delivery']:#x}; je 0x468a1a",
             "a delivery waits, the pregnancy kept, until its whole litter fits in the free records (the "
             "stock code cleared the pregnancy when the creator found no record)"),
        ]
        existing, retarget = {}, {}
    else:
        place("occupied", lambda: occupied(g))
        place("room", lambda: room_wrapper(g, 0x4713F0, 0x4944C0))
        place("delivery", lambda: delivery(g, 0x10, 0x14, names["occupied"]))
        place("reanimate_text", lambda: REANIMATE_NO_ROOM.encode("ascii") + b"\0")
        place("reanimate", lambda: f"""
            call 0x4944C0
            cmp eax, {g['slots']:#x}
            jb ok
            push 0xFF
            push {names['reanimate_text']:#x}
            push {VV5_BAR:#x}
            call {VV5_STRNCPY:#x}
            add esp, 0xC
            call {VV5_CLOCK:#x}
            mov ecx, eax
            call {VV5_SECONDS:#x}
            add eax, 5
            mov ecx, {VV5_BAR:#x}
            mov dword ptr [ecx + 0x100], eax
            or eax, -1
            ret 4
        ok:
            mov ecx, ebx
            jmp 0x4206F0
        """)
        sites = [
            (0x72BD7, "E814E8FFFF", lambda: f"call {names['room']:#x}",
             "the room predicate 0x472BD0 answers no room while the records' demand (every occupied record "
             "-- Heathens, corpses and stand-ins included -- plus every baby still owed) has no record left"),
            (0x730AF, "8B461085C00F8427020000", lambda: f"call {names['delivery']:#x}; je 0x4732e1",
             "a delivery waits, the pregnancy kept, until its whole litter fits in the free records (the "
             "stock code cleared the pregnancy when the creator found no record)"),
            (0x2341A, "8BCBE8CFD2FFFF", lambda: f"call {names['reanimate']:#x}; nop; nop",
             "Reanimate is refused, nothing spent, while no record is free for its stand-in (the stock "
             "spell wrote through a NULL record and crashed): answered as a cast with no free spell slot, "
             "the gray message bar saying why"),
        ]
        existing, retarget = {}, {}
    return blocks, names, sites, existing, retarget


PURPOSE = {
    "demand": "count the records' demand: every occupied record (the active byte; corpses included) plus "
              "the babies each pregnant mother still owes",
    "occupied": "count the occupied records (the active byte; corpses included)",
    "room": "the room predicate's count, or no room at any cap while the records' demand has no record left",
    "delivery": "a delivery only when its whole litter fits in the free records, else it waits with the "
                "pregnancy kept",
    "vial": "The Mysterious Vial: offered only with room for two copies",
    "crystal": "The Crystal of Reflections: offered only with room for its reflection",
    "crystal_keep": "The Crystal of Reflections' keep: a record checked before the likes change",
    "reanimate": "Reanimate: refused while no record is free for its stand-in, saying \"There's no room "
                 "in your village to revive this person.\" in the gray message bar (the bar's own strncpy "
                 "and five-second clock, as Bar::SetText 0x44EF60 shows the game's refusals)",
    "reanimate_text": "Reanimate's refusal text for the gray message bar",
}

def rescale_256(game: str) -> dict[str, list[tuple[str, str]]]:
    """What the 256 builds change in each of this file's rows: [(old hex, new hex)] by
    row offset (scripts/build_vv{3,4,5}_population_256_feature.py)."""
    return rows(game)[1]


def rows(game: str) -> tuple[list[dict], dict[str, list[tuple[str, str]]]]:
    g = GAMES[game]
    blocks, names, sites, existing, retarget = layout(game)
    stock = (STOCK / EXE[game]).read_bytes()
    out, rescale = [], {}
    for (offset, before, after), purpose in zip(g["headers"], HEADER_PURPOSE.get(game, [])):
        assert stock[offset:offset + 4].hex().upper() == before, (game, hex(offset))
        out.append({"offset": f"0x{offset:X}", "before": before, "after": after, "purpose": purpose})
    for va, name, source_fn, _ in blocks:
        code = asm(source_fn(), va)
        file_off = g["cave_file"] + (va - g["cave_va"])
        assert stock[file_off:file_off + len(code)] == bytes(len(code)), (game, name)
        off = f"0x{file_off:X}"
        out.append({"offset": off, "before": "00" * len(code), "after": code.hex().upper(),
                    "purpose": PURPOSE[name]})
        edits = []
        if name in ("demand", "occupied"):
            edits = [("BA" + h32(g["base"]), "BA" + h32(g["base_256"])), ("B9" + h32(0x96), "B9" + h32(0x100))]
        elif name == "room":
            edits = [("3D" + h32(0x96), "3D" + h32(0x100))]
        elif name == "delivery":
            edits = [("3D" + h32(0x97), "3D" + h32(0x101))]
        elif name == "vial":
            edits = [("3D" + h32(0x95), "3D" + h32(0xFF))]
        elif name in ("crystal", "crystal_keep", "reanimate"):
            edits = [("3D" + h32(0x96), "3D" + h32(0x100))]
        for old, _ in edits:
            assert code.hex().upper().count(old) == 1, (game, name, old)
        rescale[off] = edits
    for offset, before, source_fn, purpose in sites:
        b = bytes.fromhex(before)
        assert stock[offset:offset + len(b)] == b, (game, hex(offset), stock[offset:offset + len(b)].hex())
        code = asm(source_fn(), offset + 0x400000)
        assert len(code) == len(b), (game, hex(offset), len(code), len(b))
        out.append({"offset": f"0x{offset:X}", "before": before, "after": code.hex().upper(), "purpose": purpose})
    return out, rescale, existing, retarget


def main() -> None:
    data = json.loads(BUILDS.read_text(encoding="utf-8"))
    for game in ("vv3", "vv4", "vv5"):
        new, rescale, existing, retarget = rows(game)
        entry = next(x for x in data["games"] if x["id"] == game)
        owned = {r["offset"] for r in new}
        kept = []
        for p in entry["safety_patches"]:
            if p["offset"] in owned:
                continue
            off = int(p["offset"], 16)
            if off in existing:
                code = asm(existing[off](), off + 0x400000)
                size = len(p["after"]) // 2
                assert len(code) <= size, (game, p["offset"])
                p["after"] = (code + bytes(size - len(code))).hex().upper()
            if off in retarget:
                after = bytearray.fromhex(p["after"])
                assert after[0] == 0xE8, (game, p["offset"])
                after[1:5] = struct.pack("<i", retarget[off] - (off + 0x400000 + 5))
                p["after"] = after.hex().upper()
            kept.append(p)
        entry["safety_patches"] = kept + new
        for r in new:
            print(game, r["offset"], len(r["after"]) // 2, r["purpose"][:70])
    BUILDS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\r\n")


if __name__ == "__main__":
    main()
