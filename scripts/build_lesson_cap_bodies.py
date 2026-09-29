"""Re-assemble the VV1 and VV2 lesson-award callback bodies with the 50 cap.

The owner: "going to school (A New Home) / attending lessons (The Lost
Children) limits skill gain to exactly 50", and, for a skill already at 50,
option (b): pick only among the skills still below 50, so no lesson is wasted
on a skill that can no longer gain.  The Tree of Life's and New Believers'
Nursery Schools already skip any skill at 50 or above.

Both callbacks keep their shape -- 7 to 9 points to one skill, chosen with
equal odds, through the games' own RNG -- and change only what "one skill"
ranges over and where the award stops:

  * the five skills below 50 are counted; none -> the lesson awards nothing;
  * RNG(count) picks one of them with equal odds;
  * RNG(3)+7 is added and the result is clamped to 50.

A skill already at or above 50 (a Master trained by work) is never touched,
so nothing is ever lowered.

VV1: the School Lessons callback 127 body, cave 0x4566E0 (file 0x566E0), the
detour from the callback dispatcher at 0x43A230 (which stays as it is).
VV2: the shared private-callback dispatcher, cave 0x473D80 (file 0x73D80),
which also carries the Hospital Recovery callback 126 (unchanged here).

Writes the two entries into data/builds.json in place.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import keystone

ROOT = Path(__file__).resolve().parents[1]
BUILDS = ROOT / "data" / "builds.json"

CAP = 50
SKILLS = 5

# game: (cave VA, file offset, room, RNG, stride, skills offset, stock resume)
# The bodies moved when they grew.  Measured against EVERY claim -- the
# games' safety_patches, fun_patch_support, every fun patch and every
# manifest under data/ (statistics, parentage, origins...) -- and confirmed by
# the patcher's own overlap guard, the free runs in the .text slack are:
#   VV1: 0x566C1-0x56730 (111 bytes; Write Village Statistics' wrapper
#        starts at 0x56730), so the body is encoded to fit it;
#   VV2: 0x73F42-0x73FED (Statistics' skeleton wrapper starts at 0x73FED).
# Nothing else in either file is both free and executable.
VV1 = dict(va=0x4566C1, file=0x566C1, room=0x6F, rng=0x402F10, stride=0x3D8,
           skills=0x3BC, resume=0x43A235, hook_file=0x3A230, hook_va=0x43A230,
           old_file=0x566E0)
VV2 = dict(va=0x473F50, file=0x73F50, room=0x9D, rng=0x4031A0, stride=0xE48C,
           skills=0x7E4, resume=0x461B15, health=0x52C, hook_file=0x61B10,
           hook_va=0x461B10, old_file=0x73D80)


def assemble(source: str, address: int) -> bytes:
    engine = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    encoding, _ = engine.asm(source, address)
    return bytes(encoding)


def award_body(g: dict) -> str:
    """Callback 127: the award.  Entered after `pushad` (ecx = the villager
    array, [esp+4] = the villager's index, so [esp+0x24] after pushad)."""
    return f"""
        imul eax, dword ptr [esp + 0x24], 0x{g['stride']:X}
        lea ebx, [eax + ecx + 0x{g['skills']:X}]
        xor ecx, ecx
        xor edx, edx
    count_loop:
        cmp dword ptr [ebx + edx*4], {CAP}
        jge count_next
        inc ecx
    count_next:
        inc edx
        cmp edx, {SKILLS}
        jl count_loop
        jecxz done
        push ecx
        call 0x{g['rng']:X}
        pop ecx
        xor edx, edx
    walk_loop:
        cmp dword ptr [ebx + edx*4], {CAP}
        jge walk_next
        dec eax
        js found
    walk_next:
        inc edx
        cmp edx, {SKILLS}
        jl walk_loop
        jmp done
    found:
        lea edi, [ebx + edx*4]
        push 3
        call 0x{g['rng']:X}
        pop ecx
        add eax, 7
        add dword ptr [edi], eax
        cmp dword ptr [edi], {CAP}
        jle done
        mov dword ptr [edi], {CAP}
    done:
        popad
        ret 8
    """


def vv1_source() -> str:
    g = VV1
    return f"""
        cmp dword ptr [esp + 8], 0x7F
        jne stock
        pushad
        {award_body(g)}
    stock:
        mov eax, dword ptr [esp + 8]
        dec eax
        jmp 0x{g['resume']:X}
    """


def vv2_source() -> str:
    g = VV2
    return f"""
        cmp dword ptr [esp + 8], 0x7F
        jne check_126
        pushad
        {award_body(g)}
    check_126:
        cmp dword ptr [esp + 8], 0x7E
        je heal
        push ecx
        mov eax, dword ptr [esp + 0xC]
        jmp 0x{g['resume']:X}
    heal:
        pushad
        mov eax, dword ptr [esp + 0x24]
        imul eax, eax, 0x{g['stride']:X}
        lea ebx, [eax + ecx + 0x{g['health']:X}]
        cmp dword ptr [ebx], 100
        jge healed
        inc dword ptr [ebx]
    healed:
        popad
        ret 8
    """


def bodies() -> dict[str, bytes]:
    out = {}
    for name, g, src in (("vv1", VV1, vv1_source()), ("vv2", VV2, vv2_source())):
        code = assemble(src, g["va"])
        if len(code) > g["room"]:
            raise RuntimeError(f"{name} body is {len(code):#x} bytes, room is {g['room']:#x}")
        out[name] = code
    return out


def _replace_hook(text: str, g: dict) -> str:
    """Point the 5-byte dispatcher detour at the (re)located body."""
    rel = (g["va"] - (g["hook_va"] + 5)) & 0xFFFFFFFF
    after = (bytes([0xE9]) + rel.to_bytes(4, "little")).hex().upper()
    pattern = re.compile(r'("offset": "0x%X",\s*"before": "[0-9A-F]+",\s*"after": ")([0-9A-F]{10})(")' % g["hook_file"])
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(f"expected one hook entry at {g['hook_file']:#x}, found {len(matches)}")
    m = matches[0]
    return text[: m.start()] + m.group(1) + after + m.group(3) + text[m.end():]


def _replace_entry(text: str, offset: str, purpose_fragment: str, code: bytes, purpose: str, new_offset: str) -> str:
    pattern = re.compile(
        r'(\{\s*"offset": "' + re.escape(offset) + r'",\s*"before": ")([0-9A-F]*)(",\s*"after": ")([0-9A-F]*)(",\s*"purpose": ")([^"]*)(")',
    )
    matches = [m for m in pattern.finditer(text) if purpose_fragment in m.group(6)]
    if len(matches) != 1:
        raise RuntimeError(f"expected one entry at {offset} mentioning {purpose_fragment!r}, found {len(matches)}")
    m = matches[0]
    zeros = "00" * len(code)
    head = m.group(1).replace(f'"offset": "{offset}"', f'"offset": "{new_offset}"')
    return text[: m.start()] + head + zeros + m.group(3) + code.hex().upper() + m.group(5) + purpose + m.group(7) + text[m.end():]


def main() -> None:
    code = bodies()
    raw = BUILDS.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    text = _replace_hook(text, VV1)
    text = _replace_hook(text, VV2)
    text = _replace_entry(
        text, "0x566E0", "callback 127", code["vv1"],
        "award 7 to 9 points, stopping at 50, to one uniformly selected child skill still below 50 "
        "(nothing when all five are at 50) only when callback 127 executes",
        f"0x{VV1['file']:X}",
    )
    text = _replace_entry(
        text, "0x73D80", "callback 127", code["vv2"],
        "award callback 127's 7 to 9 points, stopping at 50, to one uniformly selected child skill "
        "still below 50 (nothing when all five are at 50), or callback 126's capped one health point, "
        "while preserving every stock callback",
        f"0x{VV2['file']:X}",
    )
    json.loads(text)
    BUILDS.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    for name, c in code.items():
        print(name, f"{len(c):#x} bytes", c.hex().upper())


if __name__ == "__main__":
    main()
