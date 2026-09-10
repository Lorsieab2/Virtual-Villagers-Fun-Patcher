"""VV3 has no Tribal Chiefs Robed lifetime total, and cannot be given one here.

`docs/village-statistics-requirements.md` asks for a "Tribal Chiefs Robed"
row in The Secret City. It is not blocked on finding the right storage: the
game does not maintain the quantity at all, and the reason is structural
rather than an absence somebody failed to search hard enough for.

Robing a chief is **puzzle id 1** in the story-puzzle system, and every
puzzle is a saturating progress value behind a one-way latch:

    sub_435990  AdvancePuzzle(id)
        0x435999  call 0x4358D0        ; IsComplete(id)
        0x43599E  test al, al
        0x4359A0  jne  0x4359D0        ; ALREADY COMPLETE -> return, no write
        0x4359A2  mov  edx, [edi+esi*8]
        0x4359A5  inc  edx
        0x4359A6  mov  [edi+esi*8], edx

Puzzle 1's threshold is 1, so the single advance at 0x431B7E takes progress
from 0 to 1, which equals the threshold and marks it complete. Every later
robing reaches the `jne` and returns without touching the counter. The stored
value is therefore a boolean by construction: it is not a count that happens
to stop at one, it is a latch that cannot represent two.

The routine that advances it is the robe fitting itself, sub_431A40, whose
`cmp eax, 0x1F ; jne 0x431B96` is the fit test -- the two branches are the
game's own "The robe fits!" and "The robe does not fit" outcomes.

## Why this is worth a test rather than a note

Three separate investigations have now approached this row from the string
side, found that "The robe fits! The chosen one has been found." at 0x4926BD
has zero .text references, and stopped. That is a true observation about
resource-table-by-id lookup and says nothing about whether a counter exists,
which is exactly the shape of absence result this project has been bitten by
before. This test pins the positive finding instead: the mechanism was
located, and the mechanism is incapable of holding the requested quantity.

Anyone who later wants the row must ADD storage rather than read the game's,
and that is a different decision needing the owner rather than more research.

The addresses are decoded with capstone rather than compared as bytes, so a
mis-stated address fails loudly instead of silently matching nothing.
"""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

STOCK = ROOT / "research/stock-executables/Virtual Villagers - The Secret City.exe"

# Established addresses. Each is asserted below, never merely asserted about.
ADVANCE_PUZZLE = 0x435990
IS_COMPLETE = 0x4358D0
ROBE_FITTING = 0x431A40
ADVANCE_CALL_SITE = 0x431B88          # the call inside the robe fitting
THRESHOLDS = 0x49D230                 # indexed as [reg*4 + 0x49D230]
HAS_CHIEF = 0x415030                  # the game's own boolean accessor
LATCH_EARLY_OUT = 0x4359D0            # AdvancePuzzle's epilogue
CHIEF_PUZZLE_ID = 1


def _sections(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, pe + 6)[0]
    opt = struct.unpack_from("<H", data, pe + 0x14)[0]
    base = struct.unpack_from("<I", data, pe + 0x34)[0]
    out = []
    for index in range(count):
        entry = pe + 0x18 + opt + index * 0x28
        name = data[entry:entry + 8].rstrip(b"\0").decode("latin1")
        vsize, rva, rsize, raw = struct.unpack_from("<IIII", data, entry + 8)
        out.append((name, base + rva, vsize, raw, rsize))
    return out


def _to_file_offset(sections, va):
    for _name, start, vsize, raw, rsize in sections:
        if start <= va < start + max(vsize, rsize):
            return raw + (va - start)
    return None


class Vv3ChiefPuzzleIsAOneShotLatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not STOCK.is_file():
            raise unittest.SkipTest(
                "requires a local game file that is gitignored and absent: "
                + STOCK.name
            )
        cls.data = STOCK.read_bytes()
        cls.sections = _sections(cls.data)
        try:
            import capstone
        except ImportError:  # pragma: no cover - environment without capstone
            raise unittest.SkipTest("capstone is required to decode instructions")
        cls.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

    def _disasm(self, va, length):
        offset = _to_file_offset(self.sections, va)
        self.assertIsNotNone(offset, "%#010x is not in a mapped section" % va)
        return list(self.md.disasm(self.data[offset:offset + length], va))

    def test_the_game_reads_the_chief_as_a_boolean(self):
        """The game's own HasChief predicate returns a flag, not a count.

        sub_415030 is the whole accessor:

            push 1 ; mov ecx, <puzzle manager> ; call IsComplete
            test al, al ; setne al ; ret

        `setne` collapses whatever is stored into 0 or 1. Two of its callers
        then pair it with a population check (`cmp [0x5945E0], 0xA`), which is
        the tribe-size influence rule the game's own tips describe. Nothing
        anywhere reads a chief quantity, because there is nothing to read.

        This is the load-bearing assertion. An earlier draft of this test
        derived the chief's puzzle id from its index in the table of handler
        initialisers at 0x49D298 -- which is wrong, because no instruction
        indexes that table by puzzle id, and it holds 25 entries against the
        26 the indexed tables hold. The id below comes only from tables the
        code actually subscripts.
        """
        decoded = self._disasm(HAS_CHIEF, 0x14)
        rendered = [(i.mnemonic, i.op_str) for i in decoded]

        self.assertIn(
            ("push", "1"),
            rendered,
            "HasChief must ask about puzzle 1",
        )
        self.assertIn(
            ("call", hex(IS_COMPLETE)),
            rendered,
            "HasChief must reach the completion test",
        )
        self.assertIn(
            ("setne", "al"),
            rendered,
            "setne is what makes the answer a boolean rather than a count",
        )

    def test_the_chief_puzzle_threshold_is_one(self):
        """Puzzle 1's threshold makes a single advance saturate it.

        The threshold table is one the code subscripts directly -- five
        instructions in the puzzle accessors use `[reg*4 + 0x49D230]` -- so
        reading entry 1 out of it is reading what the game reads.
        """
        thresholds = _to_file_offset(self.sections, THRESHOLDS)
        self.assertIsNotNone(thresholds)
        threshold = struct.unpack_from(
            "<I", self.data, thresholds + 4 * CHIEF_PUZZLE_ID
        )[0]
        self.assertEqual(
            threshold,
            1,
            "a threshold of 1 is what makes the stored value a boolean",
        )

    def test_advance_returns_early_once_the_puzzle_is_complete(self):
        """The latch: AdvancePuzzle checks IsComplete and returns before writing.

        This is the whole finding. The increment at [edi+esi*8] is reachable
        only when IsComplete said no, so a puzzle at its threshold can never be
        advanced again -- and puzzle 1's threshold is 1.
        """
        decoded = [
            (i.address, i.mnemonic, i.op_str)
            for i in self._disasm(ADVANCE_PUZZLE, 0x48)
        ]

        checks = [
            addr for addr, mn, ops in decoded
            if mn == "call" and ops == hex(IS_COMPLETE)
        ]
        self.assertTrue(
            checks,
            "AdvancePuzzle must consult IsComplete before doing anything else",
        )

        increments = [addr for addr, mn, _ in decoded if mn == "inc"]
        self.assertTrue(increments, "AdvancePuzzle must contain the increment")

        guards = [
            (addr, ops) for addr, mn, ops in decoded
            if mn == "jne" and addr > checks[0]
        ]
        self.assertTrue(guards, "the early-out branch must follow the IsComplete call")
        guard_address, guard_target = guards[0]
        self.assertLess(
            guard_address,
            increments[0],
            "the early-out must precede the increment, or the latch does not hold",
        )

        # Ordering alone is not the latch. A `jne` before the `inc` that jumped
        # BACKWARD, or straight AT the increment, would satisfy the ordering
        # check while leaving completed puzzles advanceable -- which is the
        # whole property this file exists to establish. So the destination is
        # checked, and it must land past the last write in the routine.
        target = int(guard_target, 16)
        self.assertGreater(
            target,
            increments[0],
            "the early-out must jump PAST the increment, not before or at it",
        )
        writes = [
            addr for addr, mn, ops in decoded
            if mn == "mov" and ops.startswith("dword ptr [")
        ]
        self.assertTrue(writes, "the routine must contain the progress store")
        self.assertGreater(
            target,
            max(writes),
            "the early-out must skip every write the counting path performs",
        )
        landing = [entry for entry in decoded if entry[0] == target]
        self.assertTrue(
            landing,
            f"the branch target {target:#010x} must be an instruction "
            "boundary inside this routine",
        )
        # Pinned to the exact address rather than to "some epilogue-looking
        # mnemonic past the writes". A relative assertion drifts silently if
        # the routine is ever reordered; an exact one fails loudly and makes
        # somebody re-derive the latch. The relative checks above stay, because
        # together they say WHY this address is the right one -- the constant
        # alone would be unexplained.
        self.assertEqual(
            target,
            LATCH_EARLY_OUT,
            "the early-out must reach the routine's epilogue at "
            f"{LATCH_EARLY_OUT:#010x}",
        )
        self.assertEqual(
            landing[0][1],
            "pop",
            "the early-out must land on the epilogue's first pop, which is "
            "what makes it a return rather than a re-entry",
        )

    def test_the_robe_fitting_advances_puzzle_one(self):
        """The only advance of puzzle 1 lives in the robe-fitting routine.

        `push 1` sits ten bytes before the call with an unrelated `mov` between
        them, which is why a narrow backward window reports no such call site.
        That false absence is the reason this assertion decodes the routine
        forward from its entry instead of pattern-matching near the call.
        """
        decoded = self._disasm(ROBE_FITTING, 0x180)
        by_address = dict((i.address, i) for i in decoded)

        call = by_address.get(ADVANCE_CALL_SITE)
        self.assertIsNotNone(
            call, "no instruction decodes at %#010x" % ADVANCE_CALL_SITE
        )
        self.assertEqual(call.mnemonic, "call")
        self.assertEqual(call.op_str, hex(ADVANCE_PUZZLE))

        pushes = [
            i for i in decoded
            if i.mnemonic == "push" and i.address < ADVANCE_CALL_SITE
        ]
        self.assertTrue(pushes, "the id must be pushed before the call")
        self.assertEqual(
            pushes[-1].op_str,
            "1",
            "the last push before the call is the puzzle id, and it is the chief",
        )

    def _entry_before(self, address, limit=0x400):
        """Nearest preceding address whose decode chain reaches `address`.

        Candidate starts are restricted to addresses immediately after padding
        (`nop`/`int3`), which is where MSVC begins a function, and a candidate
        is accepted only if decoding forward from it lands EXACTLY on
        `address`. That is a validated instruction-boundary chain rather than a
        guess at one.
        """
        text = next(s for s in self.sections if s[0] == ".text")
        _name, start, _vsize, raw, _rsize = text
        for candidate in range(address - 1, max(start, address - limit) - 1, -1):
            index = raw + (candidate - start)
            if self.data[index - 1] not in (0x90, 0xCC):
                continue
            for instruction in self.md.disasm(
                self.data[index:index + (address - candidate) + 16], candidate
            ):
                if instruction.address == address:
                    return candidate
                if instruction.address > address:
                    break
        return None

    def test_no_other_site_advances_the_chief_puzzle(self):
        """A second advance would not change the latch, but would change the story.

        Scanned across the whole of .text rather than near any known address,
        so this is a statement about the image and not about a window in it.

        Each candidate is decoded from a validated instruction boundary rather
        than from `call - 0x18`. That fixed offset is not safe: x86 is
        variable-length, and measured against this image **three of the
        twenty-seven** call sites to `AdvancePuzzle` desynchronise from it --
        the decode never reaches the call at all, so its argument is never
        read. Any of those three could have carried a second `push 1` and this
        assertion would still have passed. A site whose boundary cannot be
        established is reported rather than skipped, because "could not decode"
        and "does not push 1" must not look alike.

        **Honest limit of the anchoring change.** Swapping the anchoring back
        to `call - 0x18` does *not* make this test fail today, because none of
        the three desynchronising sites happens to carry a `push 1`. The change
        is therefore defensive rather than currently load-bearing: it removes a
        way this assertion could be wrong in future without announcing it, and
        that is stated here rather than left to look like a mutation-tested
        property when it is not. The desync count above is the measurement that
        justifies it.
        """
        _name, start, _vsize, raw, rsize = next(
            s for s in self.sections if s[0] == ".text"
        )
        blob = self.data[raw:raw + rsize]

        sites = []
        unresolved = []
        for offset in range(len(blob) - 5):
            if blob[offset] != 0xE8:
                continue
            disp = struct.unpack_from("<i", blob, offset + 1)[0]
            call_site = start + offset
            if call_site + 5 + disp != ADVANCE_PUZZLE:
                continue
            entry = self._entry_before(call_site)
            if entry is None:
                unresolved.append(call_site)
                continue
            window = list(
                self.md.disasm(
                    self.data[
                        raw + (entry - start):raw + (entry - start)
                        + (call_site - entry)
                    ],
                    entry,
                )
            )
            pushes = [i for i in window if i.mnemonic == "push"]
            if pushes and pushes[-1].op_str == "1":
                sites.append(call_site)

        self.assertEqual(
            [],
            [hex(address) for address in unresolved],
            "every call site must be decodable from a validated boundary; an "
            "undecodable one hides its argument",
        )
        self.assertEqual(
            [hex(address) for address in sites],
            [hex(ADVANCE_CALL_SITE)],
            "the robe fitting must be the only route that advances puzzle 1",
        )


if __name__ == "__main__":
    unittest.main()
