"""Build the VV5 "Clickable Tips" overlay.

Clicking the curled vine below the on-screen "Puzzles" button spawns a random
in-game tip into the fixed gray message bar (with the engine's own auto-hide
timer) and plays the ``hou.ogg`` chime.  The patch is a self-contained native
hook that touches only unused regions, so it layers on top of any certified
VV5 build:

  * a code cave at .text VA ``0x494890`` (currently zero padding),
  * an 8-byte hook (a jump and three int3) over the village scene's own
    mouse-down path at ``0x4463AD``,
  * a random tip index each click from ``rdtsc`` (CPU timestamp counter) — no
    external RNG, no writable scratch needed.

Where the hook sits decides where the vine answers.  ``0x4463AD`` is the
mouse-down case of theMainScene's input slot ``0x446370`` (vtable ``0x49A2F4``
slot 1, its only reference ``0x49A2F8``), the code that hands the click to the
village's own mouse-down ``0x445A60``.  The game's event queue (``0x4DACCC``,
dispatch ``0x402160``) calls a screen's slot only while that screen is shown:
showing a widget registers it (``0x40C8D0`` with 1 -> ``0x402280``) and hiding
it unregisters it (``0x40C8D0`` with 0 -> ``0x402020``).  The village's
buttons hide the village scene before their screen opens (Menu ``0x443683``,
Detail ``0x443837``, Tech ``0x44386D``, Map ``0x4438DD``, Collections
``0x44395D``, Trophies ``0x4439CD``, Puzzles ``0x443A3D``), and a pop-up in
front that takes the click stops it there.  So the vine answers only on the
village screen, exactly when the village's own buttons would.  (The first
version hooked the global event loop ``0x404A5C``, which runs for every screen:
a click on the same spot of the Menu, Tech, Collections, Puzzles or Detail
screen also picked a tip and played the chime.)

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

The default input is the stock New Believers exe in research/stock-executables
(not committed); with that exact parent the result is byte-for-byte
reproducible (see the known-good pins below).  data/builds.json carries the
same two edits with their before-guards.
"""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

import pefile
from keystone import KS_ARCH_X86, KS_MODE_32, Ks

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"

# --- addresses (image base 0x400000) -------------------------------------
# theMainScene's input slot 0x446370, mouse-down (event 2) case:
#   0x4463AD  mov edx,[esp+0x10]   ; y
#   0x4463B1  mov eax,[esp+0xC]    ; x
#   0x4463B5  push edx / push eax / call 0x445A60 (the village's mouse-down)
HOOK_VA = 0x4463AD
HOOK_PREIMAGE = bytes.fromhex("8B5424108B44240C")   # the two loads, replayed in the cave
HOOK_RETURN = 0x4463B5
CODE_VA = 0x494890          # .text cave for the handler (free of every VV5 feature cave)
CAVE_LO, CAVE_HI = 0x494610, 0x4948F8  # cave span kept zero apart from the handler
BAR_THIS = 0x520F68         # bar object (Bar::SetText `this`)
BAR_SETTEXT = 0x44EF60      # Bar::SetText(stringId, param); ret 8
SND_MGR = 0x51F440          # SoundMgr singleton
SND_PLAY = 0x44C440         # SoundMgr::PlaySound(id); ret 4
SND_ID = 0x61               # play id -> hou.ogg (naive manifest id 0x62 minus one)

TIP_ID_BASE = 0x461         # eRandomTip1 string id
TIP_COUNT = 50              # eRandomTip1..50 -> ids 0x461..0x492

# vine hit-test rectangle, just below the stock Puzzles button (button 7 at x 105, y 690,
# 0x4449EB..0x444A05).  In the cave eax = x and edx = y, the pair the event loop queued
# from SDL_GetMouseState(&x, &y) (0x404A4F..0x404A61) as (2, x, y).
VINE_X_LO, VINE_X_HI = 164, 194
VINE_Y_LO, VINE_Y_HI = 729, 757

# known-good reproducibility pins (informational; enforced only on a match)
KNOWN_PARENT_SHA256 = "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D"
KNOWN_RESULT_SHA256 = "577F5745D5653EE7075FFBE61CA02463E4A1A0915E7DEF2532D4630372F11886"


def _handler_bytes() -> bytes:
    asm = f"""
        mov edx,dword ptr [esp+0x10]
        mov eax,dword ptr [esp+0xC]
        pushad
        cmp eax,{VINE_X_LO}
        jl done
        cmp eax,{VINE_X_HI}
        jg done
        cmp edx,{VINE_Y_LO}
        jl done
        cmp edx,{VINE_Y_HI}
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
        popad
        jmp {HOOK_RETURN}
    """
    code, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(asm, CODE_VA)
    return bytes(code)


def _hook_bytes() -> bytes:
    rel = CODE_VA - (HOOK_VA + 5)
    return b"\xE9" + struct.pack("<i", rel) + b"\xCC" * (len(HOOK_PREIMAGE) - 5)


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
    hook = v2f_text(HOOK_VA)
    if raw[hook:hook + len(HOOK_PREIMAGE)] != HOOK_PREIMAGE:
        raise ValueError("hook preimage mismatch at 0x4463AD; parent is not a supported VV5 build")
    if any(raw[v2f_text(a)] for a in range(CAVE_LO, CAVE_HI)):
        raise ValueError("code cave 0x494610..0x4948F8 is not free")

    # apply: write handler, install hook, fix checksum
    code = _handler_bytes()
    if CODE_VA + len(code) > CAVE_HI:
        raise ValueError("handler does not fit the cave")
    raw[v2f_text(CODE_VA):v2f_text(CODE_VA) + len(code)] = code
    raw[hook:hook + len(HOOK_PREIMAGE)] = _hook_bytes()

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
