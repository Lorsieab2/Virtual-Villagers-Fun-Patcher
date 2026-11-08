"""Generate the two sickness patches (the owner, 2026-11-08: "bruh I'm playing on hard mode vv4 and vv5 and its still too
easy"):

  * data/vv<N>_sickness_multiplier_feature.json (all five games): "2-10x Sickness", a slider (2 to 10, 2 unless moved)
    that makes villagers fall sick N times as often; it stacks with every other patch ("sliders should stack with
    patches too!").  Its sites are written when a build is published (vv_fun_patcher.apply_sickness_multiplier), to
    the stock routine or to "Sickness works like VV1-3"'s, whichever the build has.
  * data/vv4_sickness_like_vv3_feature.json, data/vv5_sickness_like_vv3_feature.json: "Sickness works like VV1-3",
    The Secret City's rule in The Tree of Life and New Believers, with Medicine kept ("the vv4/vv5 sickness patch should
    take into account Medicine technology") and the fire's protection kept ("keep fire pit benefits for tech point
    research gain and sickness protection").  Asked, the owner chose The Secret City without Aromatherapy (which these
    games do not have), the slider multiplying the old villagers' roll too, both off by default, Owner's Defaults
    ticking both, and the second in Classic VV Difficulty.

THE STOCK ROLL (research/stock-executables, capstone, 2026-11-08): one routine per game, its only caller the life tick
(once per age unit for each villager, live and while catching up): Easy -> 50 in 100 "not sick" at once (that also
ends a sickness: Easy cures); already sick -> stays sick; then by Medicine rand(n) <= k:
  A New Home 0x42E590      rand(2400) <= 3, rand(4800) <= 3, rand(10000) <= 2 (aged 14 or more; never the Golden Child)
  The Lost Children 0x43B2B0, The Secret City 0x455C00:  rand(1440) <= 3m, rand(2460) <= 3m, rand(5400) <= 2m
  The Tree of Life 0x45E930, New Believers 0x465F50:      the same with m = 1 always
then, for a villager past 42 + 8 x Medicine years, rand(1000) <= 14.  m in The Secret City: 1 when the fire burns
(0x4337A0) or Aromatherapy (puzzle 11) is solved, else 2; on Hard 1 more unless both (0x455C25..0x455C7A).  The Lost
Children: 1 with the fire burning, else 2.

"SICKNESS WORKS LIKE VV1-3": the whole routine rewritten in place (VV4 0x45E930..0x45E9EF, VV5 0x465F50..0x46600F: the
stock 177 bytes and their int3 padding), the stock steps in the stock order, with m = 1 + (the fire is out) + (Hard),
The Secret City's rule with no Aromatherapy.  The fire test is each game's own (VV4 the Fire Pit 0x4D867C / 0x432600,
VV5 0x51DE80 / 0x438EC0, the ones the health regain reads).  Medicine's three rolls, its old-age years and Easy are
the stock ones.

"2-10x SICKNESS": each roll's modulus n (its push imm32, the four rolls of each routine) becomes round(n / N): within
0.2% of N times as likely; the smallest is 100 (the old villagers' 1,000 at x10: 15 in 100), and the game's rand takes
1 to 32,767.  Run after any change and re-run tests/test_sickness_patches.py.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

import pefile
from keystone import KS_ARCH_X86, KS_MODE_32, Ks

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables"
NAMES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}
DEFAULT = 2
MODULI = (1440, 2460, 5400, 1000)          # Medicine 1, 2, 3, the old villagers (VV2-VV5)
STOCK_SITES = {                             # the push imm32 instruction of each roll: (VA, modulus)
    1: [(0x42E61B, 2400), (0x42E5FF, 4800), (0x42E5E3, 10000), (0x42E643, 1000)],
    2: [(0x43B33E, 1440), (0x43B31D, 2460), (0x43B2FC, 5400), (0x43B380, 1000)],
    3: [(0x455CD2, 1440), (0x455CB6, 2460), (0x455C9A, 5400), (0x455CFD, 1000)],
    4: [(0x45E9AA, 1440), (0x45E991, 2460), (0x45E978, 5400), (0x45E9CB, 1000)],
    5: [(0x465FCA, 1440), (0x465FB1, 2460), (0x465F98, 5400), (0x465FEB, 1000)],
}
LIKE_VV3 = {
    4: dict(start=0x45E930, end=0x45E9F0, MGR=0x41FE70, DIFF=0x170F4, RAND=0x4036D0, TECHOBJ=0x4D6F5C,
            TECH=0x41E1C0, ELDER=0x465EB0, FIREOBJ=0x4D867C, FIRE=0x432600),
    5: dict(start=0x465F50, end=0x466010, MGR=0x425950, DIFF=0x17D54, RAND=0x403660, TECHOBJ=0x51D5CC,
            TECH=0x423600, ELDER=0x46F790, FIREOBJ=0x51DE80, FIRE=0x438EC0),
}
ASM = """
 push esi
 push edi
 mov esi, ecx
 call {MGR}
 mov edi, dword ptr [eax + {DIFF}]
 test edi, edi
 jne notEasy
 push 0x64
 call {RAND}
 pop ecx
 cmp eax, 0x32
 jl ret0
notEasy:
 cmp byte ptr [esi + 0x1c48], 0
 jne ret1
 xor eax, eax
 cmp edi, 2
 sete al
 lea edi, [eax + 1]
 mov ecx, {FIREOBJ}
 call {FIRE}
 test al, al
 jne lit
 inc edi
lit:
 push 1
 mov ecx, {TECHOBJ}
 call {TECH}
 dec eax
 je med1
 dec eax
 je med2
 dec eax
 jne elder
 add edi, edi
 push 0x1518
 jmp roll
med2:
 lea edi, [edi + edi*2]
 push 0x99c
 jmp roll
med1:
 lea edi, [edi + edi*2]
 push 0x5a0
roll:
 call {RAND}
 pop ecx
 cmp eax, edi
 jle ret1
elder:
 lea ecx, [esi + 0x1b8c]
 call {ELDER}
 test al, al
 je ret0
 push 0x3e8
 call {RAND}
 pop ecx
 cmp eax, 0xe
 jle ret1
ret0:
 xor eax, eax
 jmp out
ret1:
 xor eax, eax
 inc eax
out:
 pop edi
 pop esi
 ret
"""


def exe(game: int) -> tuple[pefile.PE, bytes]:
    path = STOCK / f"Virtual Villagers - {NAMES[game]}.exe"
    return pefile.PE(str(path), fast_load=True), path.read_bytes()


def off(pe: pefile.PE, va: int) -> int:
    return pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase)


def like_vv3_code(game: int) -> tuple[bytes, bytes, list[tuple[int, int]]]:
    """(stock bytes, new bytes, the new routine's (push VA, modulus) sites)."""
    c = LIKE_VV3[game]
    code = bytes(Ks(KS_ARCH_X86, KS_MODE_32).asm(ASM.format(**{k: hex(v) for k, v in c.items()}), c["start"])[0])
    room = c["end"] - c["start"]
    assert len(code) <= room
    pe, data = exe(game)
    stock = data[off(pe, c["start"]):off(pe, c["start"]) + room]
    assert stock[0xB1:] == b"\xCC" * (room - 0xB1), stock.hex()
    new = code + b"\xCC" * (room - len(code))
    sites = []
    for n in MODULI:
        at = new.find(b"\x68" + struct.pack("<I", n))
        assert at >= 0 and new.count(b"\x68" + struct.pack("<I", n)) == 1, n
        sites.append((c["start"] + at, n))
    return stock, new, sites


def multiplier_feature(game: int) -> dict:
    pe, data = exe(game)

    def rows(sites):
        out = []
        for va, n in sites:
            at = off(pe, va)
            out.append({"offset": "0x%X" % (at + 1), "modulus": n, "push": "0x%X" % va})
        return out

    for va, n in STOCK_SITES[game]:
        at = off(pe, va)
        assert data[at:at + 5] == b"\x68" + struct.pack("<I", n), (game, hex(va))
    sites = {"stock": rows(STOCK_SITES[game])}
    if game in LIKE_VV3:
        sites[f"vv{game}_sickness_like_vv3"] = rows(like_vv3_code(game)[2])
    return {
        "id": f"vv{game}_sickness_multiplier",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": "2-10x Sickness",
        "description": (
            "**Needs no other patch.** Makes the game harder; off by default. Villagers fall sick 2 to 10 times as "
            "often as they would: you choose how many times with the 2-10x Sickness slider in the patcher window (a "
            "whole number, 2 unless you move it). Every natural chance of falling sick is multiplied, at every Medicine "
            "level and difficulty, the old villagers' extra chance included, and it stacks with the other patches"
            + (" (with Sickness works like VV1-3 it multiplies that rule's chances)" if game in LIKE_VV3 else "")
            + ". Medicine, the fire, Easy's cures, healers, island events and everything that cures are unchanged."),
        "output_tag": "Sickness",
        "behavior_changes": [
            "The natural sickness roll's four moduli (Medicine 1, 2, 3 and the old villagers' roll) become "
            "round(stock / N), N the slider (2 to 10): each chance about N times as large.",
        ],
        "explicit_non_changes": [
            "The roll's thresholds, Medicine, the fire, the difficulty, Easy's cures, healers, events, the Hospital and "
            "every other health rule are unchanged; four immediates in place, written when the build is published.",
        ],
        "evidence_status": ("implemented from exact-build disassembly; every multiplier on every site, stock and with "
                            "Sickness works like VV1-3, is checked in tests/test_sickness_patches.py; runtime/player "
                            "confirmation pending"),
        "sickness_multiplier": {"default": DEFAULT, "minimum": 2, "maximum": 10, "sites": sites},
        "companion_files": [],
        "patches": [],
    }


def like_vv3_feature(game: int) -> dict:
    pe, _ = exe(game)
    stock, new, _ = like_vv3_code(game)
    start = LIKE_VV3[game]["start"]
    fire = "the Fire Pit" if game == 4 else "the fire"
    return {
        "id": f"vv{game}_sickness_like_vv3",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": "Sickness works like VV1-3",
        "description": (
            "**Needs no other patch.** Makes the game harder; off by default. Villagers fall sick as in The Secret "
            f"City: twice as often while {fire} is out, and on Hard one step more (twice as often with {fire} "
            "burning, three times with it out). With the fire burning on Easy or Medium nothing changes. Medicine's "
            "levels keep their own chances (the higher the level, the rarer), old villagers keep their extra chance, "
            "and Easy still lets a sickness end by itself. The Secret City's Aromatherapy, which cancels the fire's "
            "part there, does not exist in this game. 2-10x Sickness multiplies these chances too."),
        "output_tag": "Sickness like VV3",
        "behavior_changes": [
            f"The natural sickness roll 0x{start:X} (its only caller the life tick) rewritten in place: m = 1 + "
            "(the fire is out) + (Hard), and by Medicine rand(1440) <= 3m, rand(2460) <= 3m, rand(5400) <= 2m, as "
            "The Secret City 0x455C00 without Aromatherapy; Easy, an existing sickness and the old villagers' roll as "
            "stock.",
        ],
        "explicit_non_changes": [
            "Medicine's other effects, the fire's research bonus and health regain, healers, the Hospital, stews, "
            "island events, god powers, Faith and Heathens are unchanged.",
            "One guarded edit of the routine's own bytes and its int3 padding; nothing else is claimed.",
        ],
        "evidence_status": ("implemented from exact-build disassembly; every Medicine level, difficulty and fire "
                            "state, Easy's cure, an existing sickness and the old villagers' roll are emulated against "
                            "The Secret City's table in tests/test_sickness_patches.py; runtime/player confirmation "
                            "pending"),
        "companion_files": [],
        "patches": [{"offset": "0x%X" % off(pe, start), "before": stock.hex().upper(), "after": new.hex().upper(),
                     "purpose": f"the natural sickness roll (0x{start:X}): The Secret City's rule, the fire and Hard "
                                "raising the chance, Medicine kept"}],
    }


def main() -> None:
    for game in NAMES:
        out = ROOT / "data" / f"vv{game}_sickness_multiplier_feature.json"
        out.write_text(json.dumps(multiplier_feature(game), indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote", out.relative_to(ROOT))
    for game in LIKE_VV3:
        out = ROOT / "data" / f"vv{game}_sickness_like_vv3_feature.json"
        out.write_text(json.dumps(like_vv3_feature(game), indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
