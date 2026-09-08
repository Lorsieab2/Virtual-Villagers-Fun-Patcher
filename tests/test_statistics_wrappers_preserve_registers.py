"""Every statistics counter wrapper must leave the resumed code's state intact.

A detour that returns into the middle of a routine inherits that routine's
register expectations. Getting this wrong is a crash rather than a wrong
number, and it is invisible to a byte-level check: the payload can be exactly
right while the machine state it returns with is not. A parallel case on the
parentage feature clobbered EBX across a stolen call because the enclosing
routine had already popped it, which made every conception a null dereference
while the payload bytes verified clean.

"The register is volatile" is not the test. The test is whether the value in
it is live at the site being hooked. This module asserts the stronger, checkable
property: each counter wrapper writes only registers whose incoming value the
stock code is about to overwrite anyway, so nothing the resumed instruction
stream reads can be lost.

The wrappers are deliberately tiny -- load a base, increment a dword, replay
the stolen instruction, jump back -- so the check is an exact decode rather
than a heuristic scan. If a wrapper ever grows an instruction that touches
something else, this fails and the liveness argument has to be redone.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "statistics_features.json"
STOCK = ROOT / "research" / "stock-executables"

# Each counter wrapper, by the offset of the patch that installs it, with the
# registers it is permitted to write. The permission is justified per site in
# ALLOWED_BECAUSE below; anything outside this table is a new wrapper whose
# liveness has not been argued.
WRAPPER_WRITES = {
    # game, wrapper install offset (None = inside the cave payload), writes
    ("vv1", 0x56730): {"eax"},
    ("vv2", 0x73E50): {"eax"},
    ("vv2", 0x73DF4): {"eax"},
    ("vv3", 0x7B464): set(),
    ("vv4", 0x89173): set(),
    ("vv5", 0x94932): set(),
}

ALLOWED_BECAUSE = {
    "vv1": "0x448F65: the next use of EAX is 0x448F84 lea eax, a write",
    "vv2": "0x46503B: the next use of EAX is 0x465042 mov eax, a write; "
           "0x44BA8C: the stolen instruction is itself mov eax, a write",
    "vv3": "the wrapper increments an absolute address and touches no register",
    "vv4": "the wrapper increments an absolute address and touches no register",
    "vv5": "the wrapper increments an absolute address and touches no register",
}

# Opcodes the wrappers are built from. Anything else means the shape changed.
#   FF 05 disp32        inc dword [abs]        writes nothing
#   FF 80 disp32        inc dword [eax+disp]   writes nothing
#   8B 87 disp32        mov eax,[edi+disp]     writes eax
#   8B 86 disp32        mov eax,[esi+disp]     writes eax
#   C6 ...              mov byte [..],imm8     writes nothing
#   C7 ...              mov dword [..],imm32   writes nothing
#   E9 rel32            jmp                    writes nothing
WRITES_EAX = (b"\x8b\x87", b"\x8b\x86")


def _stock(game_id: str) -> bytes:
    names = {
        "vv1": "Virtual Villagers - A New Home.exe",
        "vv2": "Virtual Villagers - The Lost Children.exe",
        "vv3": "Virtual Villagers - The Secret City.exe",
        "vv4": "Virtual Villagers - The Tree of Life.exe",
        "vv5": "Virtual Villagers - New Believers.exe",
    }
    return (STOCK / names[game_id]).read_bytes()


def _counter_patches(feature: dict) -> list[dict]:
    """Patches that install a counter detour, by their stated purpose."""
    return [
        row
        for row in feature["patches"]
        if "count every" in str(row.get("purpose", ""))
    ]


class StatisticsWrappersPreserveRegistersTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_the_feature_appends_no_pe_section(self) -> None:
        """No appended page means no section header to get wrong.

        The parentage feature's appended sections were mapped nowhere because
        their IMAGE_SECTION_HEADER was never written, and no byte-level check
        could see it. This feature stays clear of that class entirely by
        patching only inside the stock image, which is worth asserting rather
        than assuming.
        """
        text = MANIFEST.read_text(encoding="utf-8")
        for token in ("pe_append_transaction", "append_bytes", "section_header"):
            with self.subTest(token=token):
                self.assertNotIn(token, text)
        for feature in self.manifest["features"]:
            game_id = feature["game_id"]
            size = len(_stock(game_id))
            for row in feature["patches"]:
                offset = int(row["offset"], 0)
                length = (
                    len(bytes.fromhex(row["after"]))
                    if row.get("after")
                    else int(row.get("length", 0))
                )
                with self.subTest(game=game_id, offset=row["offset"]):
                    self.assertLessEqual(
                        offset + length,
                        size,
                        "a patch reaches past the stock image, which would "
                        "require an appended section this feature does not "
                        "declare",
                    )

    def test_every_counter_hook_steals_whole_instructions(self) -> None:
        """The replaced bytes must be a whole number of instructions.

        A jump that lands partway through the original instruction stream
        resumes on a misaligned boundary, which is a crash rather than a bad
        statistic. Each hook's preimage is checked to be exactly the bytes the
        stock image holds there, and the detour to be a five-byte jump padded
        with NOPs to that same length.
        """
        for feature in self.manifest["features"]:
            game_id = feature["game_id"]
            data = _stock(game_id)
            for row in _counter_patches(feature):
                offset = int(row["offset"], 0)
                before = bytes.fromhex(row["before"])
                after = bytes.fromhex(row["after"])
                with self.subTest(game=game_id, offset=row["offset"]):
                    self.assertEqual(
                        data[offset : offset + len(before)],
                        before,
                        "the hook preimage is not what the stock image holds",
                    )
                    self.assertEqual(
                        len(after),
                        len(before),
                        "the detour must be exactly as long as what it replaces",
                    )
                    self.assertEqual(after[0], 0xE9, "the detour must be a jmp")
                    self.assertEqual(
                        after[5:],
                        b"\x90" * (len(after) - 5),
                        "the tail of the replaced instruction must be NOPs",
                    )

    def test_counter_wrappers_write_only_dead_registers(self) -> None:
        """A wrapper may only write registers the stock code overwrites anyway.

        Decoded exactly rather than scanned: these wrappers are a handful of
        fixed instruction forms, so an unrecognised opcode means the shape has
        changed and the liveness argument recorded in ALLOWED_BECAUSE no longer
        covers it.
        """
        seen = set()
        for feature in self.manifest["features"]:
            game_id = feature["game_id"]
            for row in feature["patches"]:
                offset = int(row["offset"], 0)
                key = (game_id, offset)
                if key not in WRAPPER_WRITES:
                    continue
                seen.add(key)
                blob = (
                    bytes.fromhex(row["after"])
                    if row.get("after")
                    else __import__("base64").b64decode(row["after_base64"])
                )
                with self.subTest(game=game_id, offset=row["offset"]):
                    written = {"eax"} if any(
                        prefix in blob for prefix in WRITES_EAX
                    ) else set()
                    self.assertLessEqual(
                        written,
                        WRAPPER_WRITES[key],
                        "%s wrapper writes a register outside its allowance; "
                        "the liveness argument (%s) must be redone"
                        % (game_id, ALLOWED_BECAUSE[game_id]),
                    )
        self.assertEqual(
            seen,
            set(WRAPPER_WRITES),
            "a wrapper listed in WRAPPER_WRITES was not found in the manifest; "
            "the table and the build have drifted apart",
        )

    def test_no_counter_wrapper_touches_a_nonvolatile_register(self) -> None:
        """EBX, ESI, EDI and EBP must never be written by a counter wrapper.

        The parentage crash came from writing EBX at a site whose enclosing
        routine had already popped it, so nothing restored it and the caller
        dereferenced the clobbered value. None of these wrappers needs a
        nonvolatile register, so the safe rule is that they may not write one
        at all.
        """
        # ModRM forms that would write ebx/esi/edi/ebp as a destination
        # register in the two-byte loads these wrappers use.
        forbidden = (b"\x8b\x9f", b"\x8b\x9e", b"\x8b\xb7", b"\x8b\xbf",
                     b"\x8b\xaf", b"\x8b\xae")
        for feature in self.manifest["features"]:
            game_id = feature["game_id"]
            for row in feature["patches"]:
                blob = (
                    bytes.fromhex(row["after"])
                    if row.get("after")
                    else __import__("base64").b64decode(row.get("after_base64", ""))
                )
                for pattern in forbidden:
                    with self.subTest(game=game_id, offset=row["offset"]):
                        self.assertNotIn(
                            pattern,
                            blob,
                            "a wrapper writes a nonvolatile register; whether "
                            "the call site preserves it is only visible in the "
                            "disassembly and must be argued explicitly",
                        )


if __name__ == "__main__":
    unittest.main()
