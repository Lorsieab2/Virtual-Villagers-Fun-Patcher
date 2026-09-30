"""sub_43BBC0 reads all four of its arguments, so none may carry the father.

The VV1 parentage feature once routed the six calls into the conception
routine through stubs that overwrote its second argument with the father's
record pointer, on the belief that the routine never read it. It does: the
routine's reads at 0x43BBD0 and 0x43BC00 share the displacement [esp+0x10] but
a `push esi` sits between them, so the first is arg3 and the second is arg2 --
which 0x43BC04 stores into the mother's +0x394, a field delivery compares with
0xC7 at 0x42EF39. The overwrite therefore changed what the game did at birth,
and the same miscounting of the routine's pushes made the twins tail read a
return address instead of the father.

Both mistakes came from reading displacements by eye. These guards derive the
stack depth at every instruction of the routine by walking its control flow
from the stock bytes, and hold the feature to what that walk finds:

  * every one of the four arguments is read, so there is no dead slot;
  * the +0x394 store is fed from arg2;
  * every place the feature's trampolines are entered from is exactly two
    pushes deep, which is the depth the shared log body assumes when it finds
    the routine's entry esp;
  * nothing the feature emits stores to the stack or to any other memory, and
    no call site is patched.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

FEATURE = ROOT / "data" / "vv1_parentage_feature.json"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"

CONCEPTION_VA = 0x43BBC0
CONCEPTION_END = 0x43BCCB  # the five-byte nop pad after `ret 0x10`

# Where the feature's code is entered from inside the routine: the two
# diverted tails, and the two retargeted singleton branches (whose stock
# target is the epilogue 0x43BCC6).
TAILS = (0x43BCA2, 0x43BCBA)
SINGLE_BRANCHES = (0x43BC39, 0x43BC4C)


def _walk_stock_routine():
    """{address: (instruction, bytes pushed since entry)} over sub_43BBC0.

    A worklist over real control flow, not a linear sweep: the twins tail at
    0x43BCBA follows a `ret 0x10` and is reached only by jumps, so a linear
    sweep would assign it the depth after the pops -- the exact error that
    shipped.
    """
    import capstone

    blob = STOCK.read_bytes()
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True

    def decode(va):
        at = va - 0x400000
        return next(md.disasm(blob[at : at + 16], va))

    seen: dict[int, tuple[object, int]] = {}
    work = [(CONCEPTION_VA, 0)]
    while work:
        va, depth = work.pop()
        if va in seen:
            if seen[va][1] != depth:
                raise AssertionError(
                    "%#x reached at two stack depths (%d and %d)"
                    % (va, seen[va][1], depth))
            continue
        if not CONCEPTION_VA <= va < CONCEPTION_END:
            raise AssertionError("control left the routine at %#x" % va)
        insn = decode(va)
        seen[va] = (insn, depth)
        after = depth
        if insn.mnemonic == "push":
            after += 4
        elif insn.mnemonic == "pop":
            after -= 4
        elif insn.mnemonic == "add" and insn.op_str.startswith("esp, "):
            after -= int(insn.op_str.split(", ")[1], 0)
        elif insn.mnemonic == "sub" and insn.op_str.startswith("esp, "):
            after += int(insn.op_str.split(", ")[1], 0)
        if insn.mnemonic == "ret":
            continue
        if insn.mnemonic.startswith("j"):
            target = int(insn.op_str, 16)
            work.append((target, after))
            if insn.mnemonic == "jmp":
                continue
        work.append((va + insn.size, after))
    return seen


def _argument_reads(seen):
    """{argument number: [reading addresses]} for every [esp+disp] read."""
    reads: dict[int, list[int]] = {}
    for va, (insn, depth) in seen.items():
        match = re.search(r"\[esp \+ (0x[0-9a-f]+|\d+)\]", insn.op_str)
        if not match or insn.mnemonic == "lea":
            continue
        entry_relative = int(match.group(1), 0) - depth
        if entry_relative <= 0:
            continue
        self_arg = entry_relative // 4
        reads.setdefault(self_arg, []).append(va)
    return reads


@unittest.skipUnless(STOCK.is_file(), "the exact-build VV1 executable is not available")
class ConceptionRoutineArgumentTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import capstone  # noqa: F401
        except ImportError:  # pragma: no cover - optional dependency
            self.skipTest("capstone is not installed")
        self.seen = _walk_stock_routine()

    def test_all_four_arguments_are_read(self) -> None:
        """There is no dead argument to carry anything in."""
        reads = _argument_reads(self.seen)
        self.assertEqual(sorted(reads), [1, 2, 3, 4], reads)

    def test_the_mothers_394_is_fed_from_the_second_argument(self) -> None:
        """0x43BC00 loads arg2 and 0x43BC04 stores it into the mother."""
        load, depth = self.seen[0x43BC00]
        self.assertEqual(load.mnemonic, "mov")
        self.assertEqual(load.op_str, "edx, dword ptr [esp + 0x10]")
        self.assertEqual(depth, 8, "0x43BC00 runs after both pushes")
        self.assertEqual((0x10 - depth) // 4, 2)
        store, _ = self.seen[0x43BC04]
        self.assertEqual(store.op_str, "dword ptr [esi + 0x394], edx")
        self.assertIn(0x43BC00, _argument_reads(self.seen)[2])

    def test_every_hook_entry_is_two_pushes_deep(self) -> None:
        """The depth the shared log body assumes when it locates E.

        LOG_ENTRY_TO_E is the body's own return address, the trampoline's
        pushad, and this depth. The twins tail once assumed zero here.
        """
        import build_vv1_parentage_feature as generator

        assumed = generator.LOG_ENTRY_TO_E - 0x04 - 0x20
        for va in TAILS + SINGLE_BRANCHES:
            with self.subTest(entry=hex(va)):
                self.assertIn(va, self.seen, "not reachable in the routine")
                self.assertEqual(self.seen[va][1], 8)
                self.assertEqual(
                    assumed, self.seen[va][1],
                    "the log body assumes %d bytes pushed at %#x, the routine "
                    "has pushed %d" % (assumed, va, self.seen[va][1]))

    def test_the_twins_tail_is_reached_only_before_the_pops(self) -> None:
        """0x43BCBA sits after `ret 0x10`, so it is never a fallthrough."""
        previous = max(va for va in self.seen if va < 0x43BCBA)
        self.assertEqual(self.seen[previous][0].mnemonic, "ret")


class NothingTheFeatureEmitsWritesMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import capstone  # noqa: F401
        except ImportError:  # pragma: no cover - optional dependency
            self.skipTest("capstone is not installed")

    def _layouts(self):
        feature = json.loads(FEATURE.read_text(encoding="utf-8"))["features"][0]
        yield "standalone", feature["patches"], 0x456900
        yield "composed", feature["composition_patches"][
            "vv1_enable_origins_exclusive_features"], 0x490E00

    def test_no_call_site_or_argument_is_touched(self) -> None:
        """The six calls run stock bytes with stock arguments."""
        call_sites = (0x43DD33, 0x43DD54, 0x43DD7B, 0x43DD94, 0x447031, 0x447238)
        for label, patches, _cave in self._layouts():
            for patch in patches:
                start = int(patch["offset"], 16)
                end = start + len(bytes.fromhex(patch["after"]))
                for site in call_sites:
                    at = site - 0x400000
                    with self.subTest(layout=label, site=hex(site)):
                        self.assertFalse(
                            start < at + 5 and at < end,
                            "a patch at %#x rewrites the call at %#x"
                            % (start, site))

    def test_the_cave_code_stores_nowhere(self) -> None:
        """Only pushes and calls touch memory; no mov/add/... destination."""
        import capstone
        from capstone import x86

        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        md.detail = True
        for label, patches, cave in self._layouts():
            payload = next(bytes.fromhex(p["after"]) for p in patches
                           if len(p["after"]) // 2 == 0x200)
            code = payload[:0x120]  # trampolines and the log body
            for insn in md.disasm(code, cave):
                if insn.mnemonic in ("push", "call", "cmp", "test"):
                    continue
                if insn.mnemonic == "add" and insn.op_str == "byte ptr [eax], al":
                    continue  # zero padding between blocks
                if insn.operands and insn.operands[0].type == x86.X86_OP_MEM:
                    with self.subTest(layout=label, at=hex(insn.address)):
                        self.fail("%s %s writes memory" % (insn.mnemonic, insn.op_str))


if __name__ == "__main__":
    unittest.main()
