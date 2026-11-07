"""Generate data/vv{1..5}_preferred_job_graves_feature.json: "Checked Skill Preferences are listed as Jobs on Graves".

The owner: "Checked Skill Preferences are listed as Jobs on Graves: self-explanatory, except when a title overrides
it. (etc "Retired Chief, Golden Child, Tribal Chief etc)".  Default off; Owner's Defaults ticks it.

WHAT THE GAMES DO.  A grave keeps the job and the skill value the burial writer gives it, and the grave dialog
draws the Job line from those two numbers (and the age) every time it is shown.  Every game's burial writer asks
the shared best-skill routine for the villager's HIGHEST skill.  Each game's Villager Detail screen already shows
the checked skill preference as the villager's job (A New Home 0x41FB4B, The Lost Children 0x429B8C, The Secret
City 0x468DE9, The Tree of Life 0x4402F5, New Believers 0x442E96): with a preference checked it shows that skill
and its value, otherwise the highest.  This row makes the grave do the same.

  game              preference (record)            values            burial writer, best-skill call
  A New Home        +0x3D0  0 none, 1 Farming 2 Parenting 3 Research 4 Building 5 Healing      (= grave job ids)
                    loop 0x448F8D..0x448FFE, call 0x43B520 (value +0xA338, job +0xA33C, age +0xA340)
  The Lost Children +0x7F8  0 none, 1 Farming 2 Parenting 3 Healing 4 Research 5 Building      (= grave job ids)
                    loop 0x465063..0x4650D9, call 0x44B4D0 (value +0x2EB78, job +0x2EB7C, age +0x2EB80);
                    the epitaph's own inline best skill 0x465172..0x4651BD
  The Secret City   +0xEC0  -1 none, 0..4 = the skill index = the grave job id
                    Roster writer 0x45504E..0x4550AC, calls 0x462460 at 0x455063 and 0x4550A7 (gravestone)
  The Tree of Life  +0x1C70 -1 none, 0..4 (floats; the value is the float cut to a whole number)
                    Roster writer 0x45D4C5..0x45D531, call 0x46AC20 at 0x45D4EF
  New Believers     +0x1C74 -1 none, 0..5 (5 Devotion, the Devotee)
                    Roster writer 0x464CC5..0x464D31, call 0x4755C0 at 0x464CEF

The shared best-skill routines have many callers (the Nursery lesson among them), so they are never touched: each
burial writer's block is recoded IN PLACE, same length, every other write it makes kept, and after the stock call
it reads the preference: in range, the job is the preference and the value that skill's (A New Home and The Lost
Children through a 3-bit-per-entry table in an immediate; The Tree of Life and New Believers cut the float with
cvttss2si, as the game's own _ftol does); out of range (none), the stock result stands.  No executable space is
claimed.  Code that was squeezed to make room is listed per game in its explicit_non_changes.

THE EPITAPH FOLLOWS (the owner chose "Follow the preference").  The Secret City, The Tree of Life and New Believers
pick the epitaph from the job the writer just stored, so it follows by itself.  The Lost Children works the
highest skill out again for the epitaph (0x465172): that is recoded to read the grave's job (0 -> Parenting, as
the stock inline gives every skill 0).  A New Home has no epitaph of its own; the Cause of Death companion picks
it from the grave's job and value, so it follows too.

TITLES STILL WIN.  No game ever shows a title in place of the Job line: the titles are epitaphs, chosen before the
job is looked at, and are unchanged -- The Lost Children "Esteemed Elder" (a villager whose totem stands); The
Secret City "Wise and Beloved Chief" (the Tribal Chief) and "Esteemed Elder"; The Tree of Life "Scholar"; New
Believers "Esteemed Elder" and "Retired Chief"; and every game's children's epitaphs.  A New Home's Golden Child
has no grave title in the game.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pefile
from keystone import KS_ARCH_X86, KS_MODE_32, Ks

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables"
EXE = {1: "Virtual Villagers - A New Home.exe", 2: "Virtual Villagers - The Lost Children.exe",
       3: "Virtual Villagers - The Secret City.exe", 4: "Virtual Villagers - The Tree of Life.exe",
       5: "Virtual Villagers - New Believers.exe"}
GAME_NAME = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life",
             5: "New Believers"}
KS = Ks(KS_ARCH_X86, KS_MODE_32)
NAME = "Checked Skill Preferences are listed as Jobs on Graves"
OUTPUT_TAG = "Preferred Job Graves"


def row_id(game: int) -> str:
    return f"vv{game}_preferred_job_graves"


def asm(src: str, va: int) -> bytes:
    return bytes(KS.asm(src, va)[0])


_exes: dict[int, tuple] = {}


def stock(game: int, va: int, n: int) -> bytes:
    if game not in _exes:
        path = STOCK / EXE[game]
        _exes[game] = (pefile.PE(str(path), fast_load=True), path.read_bytes())
    pe, data = _exes[game]
    off = pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase)
    return data[off:off + n]


def patch(game: int, va: int, after: bytes, purpose: str) -> dict:
    before = stock(game, va, len(after))
    return {"offset": "0x%X" % (va - 0x400000), "before": before.hex().upper(), "after": after.hex().upper(),
            "purpose": purpose}


def fill(code: bytes, lo: int, hi: int) -> bytes:
    assert len(code) <= hi - lo, (hex(lo), len(code), hi - lo)
    return code + b"\x90" * (hi - lo - len(code))


# The skill a preference names, as an index from the first skill dword (A New Home +0x3BC, The Lost Children
# +0x7E4: Parenting, Building, Farming, Healing, Research), for preferences 1..5.  Packed 3 bits each.
PREF_SKILL = {1: (2, 0, 4, 1, 3),       # 1 Farming 0x3C4, 2 Parenting 0x3BC, 3 Research 0x3CC, 4 Building 0x3C0, 5 Healing 0x3C8
              2: (2, 0, 3, 4, 1)}       # 1 Farming 0x7EC, 2 Parenting 0x7E4, 3 Healing 0x7F0, 4 Research 0x7F4, 5 Building 0x7E8


def packed(game: int) -> int:
    return sum(k << (3 * i) for i, k in enumerate(PREF_SKILL[game]))


# ---- the blocks -----------------------------------------------------------------------------------------------

def vv1_block() -> tuple[int, int, bytes]:
    """A New Home's burial loop body, after the free-place test (eax = &grave.age, edi the village, ebp the
    place * 0x2C), up to the name copy's call at 0x448FF1, which stays where it is (Fix Vanilla Bugs aims it at
    strcpy); its arguments are pushed as stock and the 8 bytes after it (add esp,8 / mov ebx,0x33) are stock."""
    lo, hi = 0x448F8D, NAME_CALL[1]
    code = asm(f"""
        mov edx, dword ptr [esi-0x2ec]
        imul ecx, edx, 0x3d8
        push ecx
        mov ecx, dword ptr [ecx+edi+0x348]
        mov dword ptr [eax], ecx
        push eax
        lea ecx, [eax-4]
        push ecx
        push edx
        mov ecx, edi
        call 0x43b520
        pop ecx
        pop edx
        add edx, edi
        mov dword ptr [ecx-8], eax
        mov eax, dword ptr [edx+0x3d0]
        lea ebx, [eax-1]
        cmp ebx, 4
        ja name
        push ecx
        lea ecx, [ebx+ebx*2]
        mov ebx, {packed(1):#x}
        shr ebx, cl
        and ebx, 7
        pop ecx
        mov ebx, dword ptr [edx+ebx*4+0x3bc]
        mov dword ptr [ecx-8], ebx
        mov dword ptr [ecx-4], eax
    name:
        lea eax, [edx+0x370]
        lea ebx, [ecx-0x24]
        push eax
        push ebx
        """, lo)
    return lo, hi, fill(code, lo, hi)


# The name copy's call in the burial loop, left where it is (Fix Vanilla Bugs retargets it to strcpy).
NAME_CALL = {1: 0x448FF1, 2: 0x4650BA}
VV2_FIX = 0x46518A          # the preference fix-up, in the tail the recoded epitaph pick leaves free


def vv2_block() -> list[tuple[int, int, bytes]]:
    """The Lost Children's burial loop body, after the free-place test (eax = &grave.age, esi the world, edi the
    burier, [edi+0x60] the body's record, ebp the place * 0x7C): age, the best-skill call 0x44B4D0 (job), value,
    the preference fix-up, the name copy (its call at 0x4650BA stays, Fix Vanilla Bugs aims it at strcpy), then
    ecx = the record and the age compared with 360, as stock.  ebx is kept (the child and elder epitaphs skip its
    restore at 0x465321)."""
    lo, call = 0x465063, NAME_CALL[2]
    head = asm(f"""
        push ebx
        mov edx, dword ptr [edi+0x60]
        imul ebx, edx, 0xe48c
        add ebx, esi
        mov ecx, dword ptr [ebx+0x530]
        mov dword ptr [eax], ecx
        push eax
        lea ecx, [eax-4]
        push ecx
        push edx
        mov ecx, esi
        call 0x44b4d0
        mov ecx, dword ptr [esp]
        mov dword ptr [ecx-8], eax
        call {VV2_FIX:#x}
        lea eax, [ebx+0x564]
        push eax
        sub ecx, 0x74
        push ecx
        """, lo)
    tail_lo, tail_hi = call + 5, 0x4650D9
    tail = asm("""
        add esp, 8
        pop ecx
        mov ecx, ebx
        pop ebx
        mov eax, dword ptr [ecx+0x530]
        cmp eax, 0x168
        """, tail_lo)
    return [(lo, call, fill(head, lo, call)), (tail_lo, tail_hi, fill(tail, tail_lo, tail_hi))]


def vv2_epitaph() -> tuple[int, int, bytes]:
    """The Lost Children's adult epitaph: the job to pick the pair from is the grave's own (just written), not the
    highest skill worked out again; job 0 (every skill 0) is Parenting's pair, as the stock inline gives.  The
    tail it leaves free holds the burial's preference fix-up (ebx the record, ecx &grave.age; keeps ecx)."""
    lo, hi = 0x465172, 0x4651BD
    code = asm("""
        mov edx, dword ptr [esi+0xe574d4]
        mov edx, dword ptr [edx+ebp+0x2eb7c]
        test edx, edx
        jne done
        mov dl, 2
    done:
        jmp 0x4651bd
        """, lo)
    code = fill(code, lo, VV2_FIX)
    code += asm(f"""
        mov eax, dword ptr [ebx+0x7f8]
        lea edx, [eax-1]
        cmp edx, 4
        ja keep
        push ecx
        lea ecx, [edx+edx*2]
        mov edx, {packed(2):#x}
        shr edx, cl
        and edx, 7
        pop ecx
        mov edx, dword ptr [ebx+edx*4+0x7e4]
        mov dword ptr [ecx-8], edx
        mov dword ptr [ecx-4], eax
    keep:
        ret
        """, VV2_FIX)
    return lo, hi, fill(code, lo, hi)


def vv3_block() -> tuple[int, int, bytes]:
    """The Secret City's Roster writer from the age copy to the gravestone's best skill (esi the roster entry,
    ebp the record, edi the place).  The first best-skill call gets no pointer (the value is its edx), the
    gravestone's is the roster entry's value (stock: the same call again)."""
    lo, hi = 0x45504E, 0x4550AC
    code = asm("""
        mov edx, dword ptr [ebp+0xdc4]
        mov dword ptr [esi+0x1c], edx
        lea ebx, [ebp+0xeac]
        push 0
        mov ecx, ebx
        call 0x462460
        mov ecx, dword ptr [ebx+0x14]
        cmp ecx, 4
        ja keep
        mov eax, ecx
        mov edx, dword ptr [ebx+ecx*4]
    keep:
        mov dword ptr [esi+0x24], edx
        mov dword ptr [esi+0x20], eax
        mov ecx, ebx
        call 0x462570
        mov byte ptr [esi+0x29], al
        mov cl, byte ptr [ebx-0x2c]
        mov byte ptr [esi+0x28], cl
        mov edx, dword ptr [ebx-0x30]
        mov dword ptr [esi+0x2c], edx
        cmp edi, 0x32
        jge 0x4551d7
        imul eax, edi, 0x2c
        add eax, dword ptr [esp+0x10]
        mov dword ptr [esp+0x18], eax
        mov dword ptr [eax], edi
        mov ecx, dword ptr [esi+0x24]
        mov dword ptr [eax+4], ecx
        """, lo)
    return lo, hi, fill(code, lo, hi)


# The Tree of Life and New Believers: (block, best-skill routine, Scholar / elder routine, the last preference).
V45 = {4: (0x45D4C5, 0x45D531, 0x46AC20, 0x46AC70, 4, 0x14),
       5: (0x464CC5, 0x464D31, 0x4755C0, 0x475610, 5, 0x18)}


def v45_block(game: int) -> tuple[int, int, bytes]:
    """The Roster writer from the age copy to the epitaph's age test (esi the roster entry, edi the record, ebp
    the place).  The child byte is set right after the age; the best-skill call's pointer is the strncpy
    argument slot about to be dropped (push esp, before the add esp,0xC): the value is its edx."""
    lo, hi, best, elder, last, pref = V45[game]
    code = asm(f"""
        mov ecx, dword ptr [edi+0x1b8c]
        mov dword ptr [esi+0x1c], ecx
        cmp ecx, 0x118
        setl byte ptr [esi+0x32]
        mov edx, dword ptr [edi+0x1bb8]
        mov dword ptr [esi+0x20], edx
        mov eax, dword ptr [edi+0x1bbc]
        mov dword ptr [esi+0x24], eax
        lea ebx, [edi+0x1c5c]
        push esp
        mov ecx, ebx
        call {best:#x}
        add esp, 0xc
        mov ecx, dword ptr [ebx+{pref:#x}]
        cmp ecx, {last}
        ja keep
        xchg eax, ecx
        cvttss2si edx, dword ptr [ebx+eax*4]
    keep:
        mov dword ptr [esi+0x2c], edx
        mov dword ptr [esi+0x28], eax
        mov ecx, ebx
        call {elder:#x}
        mov byte ptr [esi+0x31], al
        cmp dword ptr [edi+0x1b90], 0
        sete byte ptr [esi+0x33]
        mov edx, dword ptr [ebx-0x18]
        mov dword ptr [esi+0x34], edx
        cmp dword ptr [esi+0x1c], 0x168
        """, lo)
    return lo, hi, fill(code, lo, hi)


def blocks(game: int) -> list[tuple[int, int, bytes, str]]:
    if game == 1:
        lo, hi, code = vv1_block()
        return [(lo, hi, code, "the burial loop's grave write: age, the best-skill call 0x43B520 (unchanged), then "
                 "with a preference (+0x3D0 = 1..5) job = the preference and value = that skill; the name copy's "
                 f"arguments (its call at 0x{NAME_CALL[1]:X} and what follows are left as they are)")]
    if game == 2:
        (lo, hi, code), (tlo, thi, tail) = vv2_block()
        elo, ehi, ecode = vv2_epitaph()
        return [(lo, hi, code, "the burial loop's grave write: age, the best-skill call 0x44B4D0 (unchanged), "
                 f"value, then the preference fix-up at 0x{VV2_FIX:X}; the name copy's arguments (its call at "
                 f"0x{NAME_CALL[2]:X} is left as it is)"),
                (tlo, thi, tail, "after the name copy: ecx = the record and the age against 360, as stock"),
                (elo, ehi, ecode, "the adult epitaph's job: the grave's job (0 -> Parenting's pair, as stock) "
                 "instead of the highest skill worked out again; then the burial's preference fix-up: with "
                 "+0x7F8 = 1..5, job = the preference and value = that skill")]
    if game == 3:
        lo, hi, code = vv3_block()
        return [(lo, hi, code, "the Roster writer: age, the best-skill call 0x462460 (unchanged), then with a "
                 "preference (+0xEC0 = 0..4) job = the preference and value = that skill; the elder, chief and "
                 "cause bytes; the gravestone's place and its value = the roster's")]
    lo, hi, code = v45_block(game)
    pref = 0x1C5C + V45[game][5]
    return [(lo, hi, code, f"the Roster writer: age (and the child byte), head, body, the best-skill call "
             f"0x{V45[game][2]:X} (unchanged), then with a preference (+0x{pref:X} = 0..{V45[game][4]}) job = the "
             "preference and value = that skill cut to a whole number; the elder, sex and cause; the age against "
             "360, as stock")]


SQUEEZED = {
    1: "The age is read and the record found once, the grave's fields reached from the age's address (value -8, "
       "job -4, name -0x24). The name copy's call at 0x448FF1 (which Fix Vanilla Bugs aims at strcpy) and the "
       "loop's end are untouched.",
    2: "The record is found once and kept in ebx (saved and put back) across the name copy, whose call at 0x4650BA "
       "(which Fix Vanilla Bugs aims at strcpy) is untouched; ecx and eax leave as stock (the record, the age). The "
       "preference fix-up lives in the bytes the recoded epitaph pick no longer needs.",
    3: "The first best-skill call is given no pointer (the routine returns the value in edx too); the gravestone's "
       "value is copied from the roster entry instead of a second identical call; the chief and cause are read "
       "through ebx (the same addresses).",
    4: "The child byte is set from the age as soon as it is read, setl / sete write their bytes directly, the cause "
       "is read through ebx (the same address), the best-skill call's pointer is the strncpy argument slot about "
       "to be dropped, and the last age test reads the roster entry's age (the same value).",
}
SQUEEZED[5] = SQUEEZED[4]


DESCRIPTION = (
    "A grave's Job line names the skill the villager had checked as their skill preference on the Villager Details "
    "screen (the one the game itself shows as their job there), with that skill's rank: \"Untrained\" below 20, "
    "else \"Trainee\", \"Adept\" or \"Master\" by the game's own values (and \"Apprentice\" for a child under 14 "
    "where Children's Graves Say Apprentice or the game does it). With no preference checked the grave shows the "
    "highest skill, as before. {epitaph}Titles still win: {titles}. Only graves made from now on change; for older "
    "graves, Repair Saves & Logs rewrites the grave and its Deaths log lines where the save still holds the "
    "villager's preference at death. **Needs no other patch.**")
EPITAPH = {1: "With Show Cause of Death and Age at Death on Graves, the epitaph it gives follows the same job. ",
           2: "The epitaph follows the same job. ", 3: "The epitaph follows the same job. ",
           4: "The epitaph follows the same job. ", 5: "The epitaph follows the same job. "}
TITLES = {
    1: "the game shows no title on a grave",
    2: "a villager whose Esteemed Elder totem stands still gets \"Esteemed Elder\", and a child the children's "
       "epitaphs",
    3: "the Tribal Chief still gets \"Wise and Beloved Chief\", an Esteemed Elder \"Esteemed Elder\", and a child "
       "the children's epitaphs",
    4: "a Scholar still gets \"Scholar\", and a child the children's epitaphs",
    5: "an Esteemed Elder still gets \"Esteemed Elder\", the Retired Chief \"Retired Chief\", and a child the "
       "children's epitaphs",
}


def feature(game: int) -> dict:
    parts = blocks(game)
    name = GAME_NAME[game]
    return {
        "id": row_id(game),
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": NAME,
        "description": DESCRIPTION.format(epitaph=EPITAPH[game], titles=TITLES[game]),
        "output_tag": OUTPUT_TAG,
        "behavior_changes": [
            f"{name}'s burial writer gives a villager with a skill preference checked the grave job of that "
            "preference and that skill's value (the grave dialog draws the rank, or Apprentice, from it as for any "
            "grave); without one the best-skill routine's job and value, as stock.",
            ("The epitaph is picked from that job." if game != 1 else
             "The Cause of Death companion's epitaph and Deaths log Grave line read the grave, so they follow it."),
        ],
        "explicit_non_changes": [
            "The shared best-skill routine is not touched (its other callers, the Nursery lesson among them, are "
            "unchanged); only the burial writer's block is recoded in place, same length, no executable space "
            "claimed.",
            SQUEEZED[game],
            "Titles and the children's epitaphs are chosen before the job as stock; a grave already made is never "
            "changed by the exe (Repair Saves & Logs does it where the preference at death is known).",
        ],
        "companion_files": [],
        "patches": [patch(game, lo, code, purpose) for lo, hi, code, purpose in parts],
    }


def main() -> int:
    for game in range(1, 6):
        path = ROOT / "data" / f"vv{game}_preferred_job_graves_feature.json"
        path.write_text(json.dumps(feature(game), indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
                        newline="\n")
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
