"""Build the VV2 Villagers Died counter.

The requirements ask for Villagers Died in all five games. The Secret City,
The Tree of Life and New Believers ship it through the statistics feature's
``death_hooks``; A New Home and The Lost Children omit the row entirely,
because that emitter writes every wrapper into a fixed-size cave and VV2's
cave has six free bytes of 208 against the ~1,700 this needs.

So this is a separate append-based feature. Everything it rests on is
recorded in docs/village-statistics-export-research.md, measured rather than
assumed, and several of those measurements were wrong the first time:

  * 22 hook sites -- 21 damage plus the old-age store at 0x43BDEE. An earlier
    count of 22 damage sites included 0x44B448, which only READS the field;
    a fixed +7 offset decoded a byte read as a phantom ``dec`` because that
    site uses the six-byte ``lea`` form.
  * spans 7-23 bytes, each derived by decoding the ``lea``'s ModRM and
    walking whole instructions to the field write. A fixed span splices
    mid-instruction.
  * nine spans carry ``e8 <rel32>``. Copying those bytes to the appended page
    would send 0x463638 to 0x45404A, which is not a function entry -- a crash
    rather than a wrong number, and invisible to a manifest check.

The trampoline uses MEMORY scratch rather than the stack. A push before the
mutation shifts esp, and the 23-byte spans contain ``mov edi,[esp+0x1C]``.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / (
    "Virtual Villagers - The Lost Children.exe"
)
ORIGINS = ROOT / "data" / "vv2_origins_feature.json"
OUTPUT = ROOT / "data" / "vv2_villagers_died_feature.json"

# Counter slot. Unreferenced by stock code -- the same scan returns 4 hits for
# +0x2E520 (Special Stews Found), so zero is a real absence -- and at 189,916
# it sits inside the 197,488-byte serialised extent with 7,572 bytes to spare.
# The doubler persistence defect was a field 352 bytes PAST that boundary, so
# "unreferenced" alone is not sufficient.
COUNTER_OFFSET = 0x2E5DC

# The manager is reached through a base register the surrounding code sets up;
# 0xE574D4 is not an address, it sits above the 0x4B5000 image end. Ten sites
# have such a register live and twelve do not, so the pointer is cached at its
# single point of publication instead.
MANAGER_STORE_VA = 0x44C1E5
MANAGER_STORE_STOCK = bytes.fromhex("8986d474e500")

# Spans, derived. See the research document for the per-site decode.
SPANS = {
    0x420E16: 10, 0x421013: 10, 0x433367: 9, 0x4375E7: 9, 0x43909F: 16,
    0x4392CC: 16, 0x4393DC: 16, 0x4394EC: 16, 0x43BAEB: 10, 0x43BB7E: 9,
    0x43BC43: 10, 0x44EE21: 12, 0x462990: 15, 0x462C05: 14, 0x462D3C: 14,
    0x462E78: 14, 0x462F8A: 14, 0x463638: 23, 0x4638DA: 21, 0x46403E: 21,
    0x4641A7: 23, 0x43BDEE: 7,
}

REG = {0: "eax", 1: "ecx", 2: "edx", 3: "ebx", 5: "ebp", 6: "esi", 7: "edi"}


def _geometry() -> tuple[int, int, int]:
    """Image geometry read from the PE, never written down.

    A hardcoded copy of these three numbers is what put an earlier VV2
    feature's file offsets 3 KB from their intended sites.
    """
    import pefile

    pe = pefile.PE(str(STOCK), fast_load=True)
    text = next(s for s in pe.sections if s.Name.rstrip(b"\0") == b".text")
    return (
        pe.OPTIONAL_HEADER.ImageBase,
        text.VirtualAddress,
        text.PointerToRawData,
    )


def _v2f(va: int) -> int:
    base, text_va, text_raw = _geometry()
    return va - base - text_va + text_raw


def _append_layout() -> tuple[int, int]:
    manifest = json.loads(ORIGINS.read_text(encoding="utf-8"))
    layout = manifest["pe_append_transaction"]["layouts"]["collection_progression"]
    return (
        int(str(layout["append_offset"]), 0),
        int(str(layout["virtual_address"]), 0),
    )


def _appended_f2v(fo: int) -> int:
    """File offset to VA inside the Origins page.

    ``virtual_address`` in the layout is already absolute (0x4B3000), so the
    image base must NOT be added again -- doing so put an earlier trampoline
    0x400000 high, and the build still succeeded because nothing checks that
    a jump target contains code.
    """
    append_offset, virtual_address = _append_layout()
    return fo - append_offset + virtual_address


# The payload sits after the parentage payload (0xB241A + 0xBE) in the
# executable .vvmk half of the appended page. The first 0x1000 bytes are
# .mtab, which is writable and cannot hold code -- the layout names the pair
# ".mtab/.vvmk" in one string, which is what invited reading them as one page.
PAYLOAD_FILE = 0xB24D8
PAGE_END_FILE = 0xB3000

SLOT_MGR = 0
SLOT_PRE = 4
SLOT_SAVE = 8
CODE_OFFSET = 12


def assemble(source: str, address: int) -> bytes:
    from keystone import KS_ARCH_X86, KS_MODE_32, Ks

    encoding, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoding)


def _raw(data: bytes) -> str:
    return "\n".join(".byte 0x%02X" % b for b in data)


def _lea_len(text: bytes, site: int, base: int) -> int:
    """Decoded from the ModRM, never assumed.

    Six or seven bytes depending on whether a SIB follows. Exactly one site
    of the twenty-two uses the short form, which is why assuming seven
    produced a phantom instruction at that one site and nowhere else.
    """
    o = site - base
    if text[o] != 0x8D:
        return 0
    return 7 if (text[o + 1] & 7) == 4 else 6


def _ptr_reg(text: bytes, site: int, base: int) -> str | None:
    o = site - base
    if text[o] != 0x8D:
        return None
    return REG[(text[o + 1] >> 3) & 7]


def _retarget(chunk: bytes, old_va: int, new_va: int) -> bytes:
    """Re-encode every rel32 branch for a new address.

    A replay is only verbatim when the bytes carry no relative displacement.
    Nine of the twenty-two spans call 0x4031A0 through an ``e8``; copying
    them unchanged is a crash the manifest cannot see.
    """
    out = bytearray(chunk)
    i = 0
    while i < len(out) - 4:
        if out[i] in (0xE8, 0xE9):
            rel = struct.unpack_from("<i", out, i + 1)[0]
            target = old_va + i + 5 + rel
            struct.pack_into("<i", out, i + 1, target - (new_va + i + 5))
            i += 5
            continue
        i += 1
    return bytes(out)


def _prefix_len(reg: str, slots: dict[str, int]) -> int:
    probe = (
        "mov dword ptr [%d], eax\n"
        "mov eax, dword ptr [%s]\n"
        "mov dword ptr [%d], eax\n"
        "mov eax, dword ptr [%d]\n"
        % (slots["save"], reg, slots["pre"], slots["save"])
    )
    return len(assemble(probe, 0))


def _trampoline(text: bytes, base: int, site: int, tramp_va: int,
                slots: dict[str, int]) -> bytes:
    """One trampoline. Same shape for every site, parameterised by pointer.

    The pre-value is read THROUGH the pointer rather than captured from a
    register, which is what collapses eight mutation shapes to one: the lea
    always produces the pointer before the mutation runs.
    """
    span = SPANS[site]
    stolen = text[site - base:site - base + span]
    n = _lea_len(text, site, base)
    reg = _ptr_reg(text, site, base)
    ret = site + span

    if reg is None:
        # 0x43BDEE stores a literal zero with no lea, so the pointer is the
        # record base the instruction itself uses.
        head = (
            "mov dword ptr [%d], eax\n"
            "mov eax, dword ptr [ebx + 0x52C]\n"
            "mov dword ptr [%d], eax\n"
            "mov eax, dword ptr [%d]\n" % (slots["save"], slots["pre"], slots["save"])
        )
        post = "dword ptr [ebx + 0x52C]"
        body = _raw(stolen)
    else:
        rest_va = tramp_va + n + _prefix_len(reg, slots)
        head = (
            _raw(stolen[:n]) + "\n"
            "mov dword ptr [%d], eax\n"
            "mov eax, dword ptr [%s]\n"
            "mov dword ptr [%d], eax\n"
            "mov eax, dword ptr [%d]\n"
            % (slots["save"], reg, slots["pre"], slots["save"])
        )
        post = "dword ptr [%s]" % reg
        body = _raw(_retarget(stolen[n:], site + n, rest_va))

    # eax is saved to MEMORY on both halves. Pushing it would shift esp before
    # the replay, and the 23-byte spans read [esp+0x1C].
    #
    # mov does not affect flags, so the flags the mutation produced survive to
    # the pushfd and are restored before the return jump -- which 0x44EE21
    # needs, since it resumes at a jns reading its own add ecx,-0x5A.
    source = (
        head + body + "\n"
        "mov dword ptr [%d], eax\n"
        "pushfd\n"
        "mov eax, dword ptr [%d]\n"
        "cmp eax, 0\n"
        "jle restore\n"
        "cmp %s, 0\n"
        "jg restore\n"
        "mov eax, dword ptr [%d]\n"
        "test eax, eax\n"
        "jz restore\n"
        "inc dword ptr [eax + 0x%X]\n"
        "restore:\n"
        "popfd\n"
        "mov eax, dword ptr [%d]\n"
        "jmp 0x%X\n"
        % (slots["save"], slots["pre"], post, slots["mgr"],
           COUNTER_OFFSET, slots["save"], ret)
    )
    return assemble(source, tramp_va)


def build() -> dict:
    source = STOCK.read_bytes()
    base, text_va, text_raw = _geometry()
    text_base = base + text_va
    text = source[text_raw:]

    if PAYLOAD_FILE < len(source):
        raise RuntimeError(
            f"payload at {PAYLOAD_FILE:#x} is inside the stock file; it was "
            "meant to sit in the appended page"
        )

    slots = {
        "mgr": _appended_f2v(PAYLOAD_FILE + SLOT_MGR),
        "pre": _appended_f2v(PAYLOAD_FILE + SLOT_PRE),
        "save": _appended_f2v(PAYLOAD_FILE + SLOT_SAVE),
    }

    # Every hook's stock bytes are asserted before anything is emitted.
    for site, span in SPANS.items():
        off = _v2f(site)
        if len(source[off:off + span]) != span:
            raise RuntimeError(f"site {site:#x} runs past the stock image")

    store_off = _v2f(MANAGER_STORE_VA)
    if source[store_off:store_off + 6] != MANAGER_STORE_STOCK:
        raise RuntimeError(
            f"the manager store at {MANAGER_STORE_VA:#x} is not the expected "
            "mov [esi+0xE574D4], eax"
        )

    va = _appended_f2v(PAYLOAD_FILE + CODE_OFFSET)
    emitted: dict[int, tuple[int, bytes]] = {}
    for site in sorted(SPANS):
        code = _trampoline(text, text_base, site, va, slots)
        emitted[site] = (va, code)
        va += len(code)

    used = va - _appended_f2v(PAYLOAD_FILE)
    room = PAGE_END_FILE - PAYLOAD_FILE
    if used > room:
        raise RuntimeError(f"payload needs {used} bytes, page has {room}")

    return {
        "slots": {k: hex(v) for k, v in slots.items()},
        "bytes_used": used,
        "bytes_available": room,
        "trampolines": {
            hex(s): {"va": hex(a), "size": len(c)} for s, (a, c) in emitted.items()
        },
    }


def main() -> None:
    result = build()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
