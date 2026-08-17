"""Build the VV5 "Clickable Tips" overlay.

Clicking the curled vine below the on-screen "Puzzles" button spawns a random
in-game tip into the fixed gray message bar (with the engine's own auto-hide
timer) and plays the ``hou.ogg`` chime.  The patch is a self-contained native
hook that touches only unused regions, so it layers on top of any certified
VV5 build:

  * a code cave at .text VA ``0x494900`` (currently zero padding),
  * a 5-byte hook over the click-dispatch site at ``0x404A5C``,
  * a random tip index each click from ``rdtsc`` (CPU timestamp counter) — no
    external RNG, no writable scratch needed.

Everything the handler calls is native engine code:

  * ``Bar::SetText(stringId, param)`` @ ``0x44EF60`` (``this`` = bar object
    ``0x520F68``) resolves a string id to text and starts the bar's auto-hide
    timer.  The 50 ``eRandomTip`` strings occupy contiguous ids ``0x461..0x492``.
  * ``SoundMgr::PlaySound(id)`` @ ``0x44C440`` (``this`` = sound manager
    ``0x51F440``) plays a preloaded sound.  Because the manifest name/id fields
    are staggered, the *play id* is one below the naive manifest id: play id
    ``0x61`` resolves to ``hou.ogg`` (see ``[0x4CDB90 + id*0x10]``).

Usage::

    python scripts/build_vv5_clickable_tips.py --input <parent.exe> --output <patched.exe>

The default input is the certified VV5 "heal-fix" build the feature was
playtested against; when that exact parent is supplied the result is byte-for-
byte reproducible (see the known-good pins below).
"""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

import pefile
from keystone import KS_ARCH_X86, KS_MODE_32, Ks

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = (
    ROOT
    / "outputs"
    / "heal-fix"
    / "Virtual Villagers - New Believers - Modded"
    / "Virtual Villagers - New Believers - Modded.exe"
)

# --- addresses (image base 0x400000) -------------------------------------
HOOK_VA = 0x404A5C          # click-dispatch site; displaced bytes below
HOOK_PREIMAGE = bytes.fromhex("83C4085152")   # add esp,8 ; push ecx ; push edx
CODE_VA = 0x494890          # .text cave for the handler (free of every VV5 feature cave)
CAVE_LO, CAVE_HI = 0x494610, 0x4948F8  # cave span kept zero apart from the handler
BAR_THIS = 0x520F68         # bar object (Bar::SetText `this`)
BAR_SETTEXT = 0x44EF60      # Bar::SetText(stringId, param); ret 8
SND_MGR = 0x51F440          # SoundMgr singleton
SND_PLAY = 0x44C440         # SoundMgr::PlaySound(id); ret 4
SND_ID = 0x61               # play id -> hou.ogg (naive manifest id 0x62 minus one)

TIP_ID_BASE = 0x461         # eRandomTip1 string id
TIP_COUNT = 50              # eRandomTip1..50 -> ids 0x461..0x492

# vine hit-test rectangle (x = ecx, y = edx at the hook site)
VINE_X_LO, VINE_X_HI = 729, 757
VINE_Y_LO, VINE_Y_HI = 164, 194

# known-good reproducibility pins (informational; enforced only on a match)
KNOWN_PARENT_SHA256 = "869C5CBA8CC051B4623B159F0BB3DC60462FE4D9CBA0A013755A893F0D2EECFB"
KNOWN_RESULT_SHA256 = "CA6A1E9A8A9E0D5927AD263F199E1C5FF4EEF38583F05BF25807DC5DAA299DC2"


def _handler_bytes() -> bytes:
    asm = f"""
        pushad
        pushfd
        cmp edx,{VINE_Y_LO}
        jl done
        cmp edx,{VINE_Y_HI}
        jg done
        cmp ecx,{VINE_X_LO}
        jl done
        cmp ecx,{VINE_X_HI}
        jg done
        rdtsc
        xor edx,edx
        mov ebx,{TIP_COUNT}
        div ebx
        add edx,{TIP_ID_BASE}
        push -1
        push edx
        mov ecx,{BAR_THIS}
        call {BAR_SETTEXT}
        mov ecx,{SND_MGR}
        push {SND_ID}
        call {SND_PLAY}
    done:
        popfd
        popad
        add esp,8
        push ecx
        push edx
        jmp {HOOK_VA + 5}
    """
    code, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(asm, CODE_VA)
    return bytes(code)


def build(parent: bytes) -> bytes:
    raw = bytearray(parent)
    pe = pefile.PE(data=bytes(raw), fast_load=True)
    ib = pe.OPTIONAL_HEADER.ImageBase

    def sect(name: bytes):
        return next(s for s in pe.sections if s.Name.rstrip(b"\x00") == name)

    text = sect(b".text")

    def v2f_text(va: int) -> int:
        return text.PointerToRawData + (va - (ib + text.VirtualAddress))

    # preconditions
    if raw[v2f_text(HOOK_VA):v2f_text(HOOK_VA) + 5] != HOOK_PREIMAGE:
        raise ValueError("hook preimage mismatch at 0x404A5C; parent is not a supported VV5 build")
    if any(raw[v2f_text(a)] for a in range(CAVE_LO, CAVE_HI)):
        raise ValueError("code cave 0x494610..0x4949B0 is not free")

    # apply: zero cave, write handler, install hook, fix checksum
    for a in range(CAVE_LO, CAVE_HI):
        raw[v2f_text(a)] = 0
    code = _handler_bytes()
    raw[v2f_text(CODE_VA):v2f_text(CODE_VA) + len(code)] = code
    rel = CODE_VA - (HOOK_VA + 5)
    raw[v2f_text(HOOK_VA):v2f_text(HOOK_VA) + 5] = b"\xE9" + struct.pack("<i", rel)

    out = pefile.PE(data=bytes(raw))
    out.OPTIONAL_HEADER.CheckSum = out.generate_checksum()
    return out.write()


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the VV5 Clickable Tips overlay.")
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="parent VV5 exe")
    ap.add_argument("--output", type=Path, required=True, help="patched exe path")
    args = ap.parse_args()

    parent = args.input.read_bytes()
    parent_sha = hashlib.sha256(parent).hexdigest().upper()
    result = build(parent)
    result_sha = hashlib.sha256(result).hexdigest().upper()

    if parent_sha == KNOWN_PARENT_SHA256 and result_sha != KNOWN_RESULT_SHA256:
        raise SystemExit(
            f"reproducibility check FAILED: certified parent produced {result_sha}, "
            f"expected {KNOWN_RESULT_SHA256}"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result)
    tag = " (matches known-good pin)" if result_sha == KNOWN_RESULT_SHA256 else ""
    print(f"parent  sha256={parent_sha}")
    print(f"result  sha256={result_sha}{tag}")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
