"""Every VV2 write to the health field, classified by what it actually does.

A Villagers Died counter for The Lost Children has to hook the sites that
damage a villager to death, and only those. The obvious way to build that hook
set -- take the addresses somebody wrote down while reading the death arbiter --
is wrong in both directions, and this test pins the measurement so neither
mistake can be made quietly.

**Missed damage.** Four sites damage the health field and are followed by a test
for death, and none of them is inside the arbiter `sub_43B690` that every
earlier survey worked from:

    0x420E16  add [eax], -0x14   then 0x420E39  cmp [eax], ebx ; jge
    0x421013  add [eax], -0xA    then 0x421036  cmp [eax], ebx ; jge
    0x433367  sub [eax], ebp     then 0x43337D  test ecx, ecx  ; jge
    0x4375E7  sub [eax], ebp     then 0x4375FD  test ecx, ecx  ; jge

A hook set drawn from the arbiter alone undercounts by four paths, silently.

**Counted healing.** Two sites increment, two clamp, and all four look like the
damage sites at a glance because they share the `lea` + store shape:

    0x43BBD7, 0x43BD02   inc          heals
    0x43BC59             floor clamp  only ever RAISES health to ebx
    0x43BD0F             ceiling clamp

Hooking by address list rather than by classification counts healing as death.

**And one that is harmless only by accident.** `0x46116C` decrements and stores,
but floors at *three* rather than zero:

    0x46116C  lea ; dec ecx ; cmp ecx, 3 ; mov [eax], ecx ; jge ; mov [eax], 3

A `pre > 0 && post <= 0` transition gate never fires there, so it is safe to
leave unhooked -- but only because of that constant. This test names it so the
reasoning is recorded rather than rediscovered.

## Method, and the two ways it was wrong first

Sites are found by byte-searching for the displacement and decoding each hit
individually, never by a linear disassembly sweep. A linear sweep desynchronises
on this executable and both invents instructions that do not exist and skips
real ones -- there are several `mov esp, 0x52c30` artifacts in the raw output
that are not instructions at all.

Classification then walks each site to the end of its **basic block**, not to a
fixed byte distance. A byte window is wrong in both directions and cannot be
tuned out of it: at 0x28 bytes the death checks for `0x420E16` and `0x421013`
fall outside and those sites are missed; widen it to 0x40 and `0x43BB7E` picks
up a `cmp` belonging to the next villager's check and is misclassified as
floored. A test after a branch is on a different path and says nothing about
this one.
"""

from __future__ import annotations

import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

STOCK = ROOT / "research/stock-executables/Virtual Villagers - The Lost Children.exe"

HEALTH_DISPLACEMENT = 0x52C

# The damage set is DERIVED from the binary below, never listed. An earlier
# draft listed it, and a mutation that deleted one real damage site from the
# list left the suite green -- the list was a restatement of the answer rather
# than a check of it. What is kept here is only the set that must be a SUBSET
# of what the derivation finds, so a site going missing fails loudly.
DOCUMENTED_DAMAGE = {
    0x420E16,   # add [eax], -0x14   outside sub_43B690
    0x421013,   # add [eax], -0xA    outside sub_43B690
    0x433367,   # sub [eax], ebp     outside sub_43B690
    0x4375E7,   # sub [eax], ebp     outside sub_43B690
    0x43BAEB,   # dec ecx ; mov [eax], ecx
    0x43BB7E,   # dec [eax] in place -- no register holds the pre-value
    0x43BC43,   # dec ecx ; mov [eax], ecx
}

# Sites that raise health or hold it up. Hooking any of these counts healing
# as a death.
NOT_DAMAGE = {
    0x43BBD7,   # inc, heal
    0x43BD02,   # inc, heal
    0x43BC59,   # floor clamp: only fires when health is BELOW ebx
    0x43BD0F,   # ceiling clamp at 0x64
    0x46107B,   # inc toward a 0x64 ceiling
}

# Decrements that cannot reach a death state because they floor above zero.
FLOORED_ABOVE_ZERO = {0x46116C: 3}

# Bytes a hook must steal at each damage site: whole instructions up to and
# including the write. Pinned because the two ten-byte entries are the ones a
# fixed instruction count gets wrong -- 0x43BAEB and 0x43BC43 need THREE
# instructions (`lea ; dec ecx ; mov [eax], ecx`), and taking two covers only
# eight bytes, leaving the store outside the splice.
EXPECTED_SPANS = {
    0x420E16: 10,
    0x421013: 10,
    0x433367: 9,
    0x4375E7: 9,
    0x43BAEB: 10,
    0x43BB7E: 9,
    0x43BC43: 10,
}


def _text_section(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, pe + 6)[0]
    opt = struct.unpack_from("<H", data, pe + 0x14)[0]
    base = struct.unpack_from("<I", data, pe + 0x34)[0]
    for index in range(count):
        entry = pe + 0x18 + opt + index * 0x28
        name = data[entry:entry + 8].rstrip(b"\0").decode("latin1")
        vsize, rva, rsize, raw = struct.unpack_from("<IIII", data, entry + 8)
        if name == ".text":
            return base + rva, raw, rsize
    raise AssertionError(".text not found")


class Vv2HealthMutationSitesAreClassified(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not STOCK.is_file():
            raise unittest.SkipTest(
                "requires a local game file that is gitignored and absent: "
                + STOCK.name
            )
        try:
            import capstone
        except ImportError:  # pragma: no cover - environment without capstone
            raise unittest.SkipTest("capstone is required to decode instructions")
        cls.data = STOCK.read_bytes()
        cls.va, cls.raw, cls.rsize = _text_section(cls.data)
        cls.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        # Required for the EFLAGS model the liveness check reads. Without it
        # every `instruction.eflags` access raises CS_ERR_DETAIL rather than
        # returning zero, so the failure is loud -- but the ad-hoc scripts that
        # first derived these results set it and this class did not, which is
        # its own small lesson about analysis and test drifting apart.
        cls.md.detail = True
        cls.chains = cls._collect(cls)

    def _collect(self):
        """Every instruction whose disp32 is the health displacement.

        Byte-search then decode backwards into the instruction, rather than
        sweeping forward: a linear pass over this .text desynchronises and
        reports instructions that are not there.
        """
        blob = self.data[self.raw:self.raw + self.rsize]
        needle = struct.pack("<I", HEALTH_DISPLACEMENT)
        chains = {}
        for match in re.finditer(re.escape(needle), blob):
            offset = match.start()
            for back in range(2, 10):
                start = self.va + offset - back
                window = self.data[
                    self.raw + offset - back:self.raw + offset - back + 28
                ]
                decoded = list(self.md.disasm(window, start))
                if not decoded or decoded[0].size <= back:
                    continue
                if "0x52c" not in decoded[0].op_str.lower():
                    continue
                chains.setdefault(decoded[0].address, decoded[:6])
                break
        return chains

    def _block_at(self, address, limit=0x60):
        """Decode from `address` to the end of its basic block.

        See the module docstring: bounding by control flow rather than by a byte
        window is what makes the classification stable. Any fixed window is
        wrong in one direction or the other.
        """
        out = []
        start = self.raw + (address - self.va)
        for instruction in self.md.disasm(self.data[start:start + limit], address):
            out.append(instruction)
            if instruction.mnemonic.startswith("j") or instruction.mnemonic in (
                "call",
                "ret",
            ):
                break
        return out

    def _reduces_health(self, block):
        head = block[0]
        if head.mnemonic in ("add", "sub") and head.op_str.startswith("dword ptr ["):
            return head.mnemonic == "sub" or "-0x" in head.op_str
        if head.mnemonic != "lea":
            return False
        for follow in block[1:4]:
            if follow.mnemonic == "dec":
                return True
            if follow.mnemonic in ("add", "sub") and follow.op_str.startswith(
                "dword ptr [eax]"
            ):
                return follow.mnemonic == "sub" or "-0x" in follow.op_str
        return False

    def _floors_above_zero(self, block):
        """A compare against a positive literal inside the same block."""
        for instruction in block:
            match = re.match(r"^(e\w\w),\s*(\d+)$", instruction.op_str or "")
            if instruction.mnemonic == "cmp" and match and int(match.group(2)) > 0:
                return int(match.group(2))
        return None

    def _derived_damage(self):
        """Sites that reduce health without flooring above zero.

        Derived from the instructions rather than restated, so a site dropped
        from DOCUMENTED_DAMAGE still appears here and the subset check fails.
        """
        damage = set()
        for address in self.chains:
            block = self._block_at(address)
            if not block or not self._reduces_health(block):
                continue
            if self._floors_above_zero(block):
                continue
            damage.add(address)
        return damage

    def test_the_search_finds_a_known_present_site(self):
        """Positive control: the method must find sites everyone agrees exist.

        An absence result from this scan is only meaningful if the scan is
        shown to find known-present cases first. 0x43BAEB and 0x43BB7E are the
        two damage sites documented in the research notes.
        """
        self.assertIn(0x43BAEB, self.chains, "the scan must find the documented dec")
        self.assertIn(0x43BB7E, self.chains, "the scan must find the in-place dec")
        self.assertGreater(
            len(self.chains), 100, "the scan must see the whole section"
        )

    def test_the_documented_damage_set_equals_what_the_binary_yields(self):
        """The documented set must EQUAL the derived one, not contain it.

        Two earlier drafts of this assertion could not fail. The first listed
        the damage sites and compared nothing, so deleting one left the suite
        green. The second checked `DOCUMENTED_DAMAGE <= derived`, which is worse
        than useless in the direction that matters: removing an element from a
        subset makes the check *more* likely to pass, so the exact mutation the
        test exists to catch -- a real damage site quietly dropped -- still
        passed.

        Equality is the only form that fails in both directions: a dropped site
        leaves the derivation finding one the list does not have, and an
        invented site leaves the list holding one the derivation does not.
        """
        derived = self._derived_damage()
        self.assertEqual(
            sorted(hex(address) for address in DOCUMENTED_DAMAGE),
            sorted(hex(address) for address in derived),
            "the documented damage sites and the derived ones must agree "
            "exactly -- a difference in either direction is a defect",
        )
        for address in (0x420E16, 0x421013, 0x433367, 0x4375E7):
            with self.subTest(site=hex(address)):
                self.assertIn(
                    address,
                    derived,
                    f"{address:#010x} damages health outside sub_43B690 "
                    "and an arbiter-only survey misses it",
                )

    def test_the_derivation_excludes_heals_and_clamps(self):
        """Nothing that raises or floors health may appear as damage."""
        derived = self._derived_damage()
        for address in sorted(NOT_DAMAGE | set(FLOORED_ABOVE_ZERO)):
            with self.subTest(site=hex(address)):
                self.assertNotIn(
                    address,
                    derived,
                    f"{address:#010x} raises or floors health and is not damage",
                )

    def test_the_floored_decrement_cannot_reach_zero(self):
        """0x46116C decrements but floors at three, so it can never kill.

        Recorded rather than merely omitted, because it is safe only by virtue
        of that constant. If the floor ever changes, the site becomes a real
        damage path and this fails rather than the counter silently going wrong.
        """
        for address, floor in FLOORED_ABOVE_ZERO.items():
            with self.subTest(site=hex(address)):
                block = self._block_at(address)
                self.assertTrue(block, f"{address:#010x} must decode")
                observed = self._floors_above_zero(block)
                self.assertEqual(
                    observed,
                    floor,
                    f"{address:#010x} must still floor at {floor}",
                )
                self.assertGreater(
                    floor, 0, "a floor at or below zero would be a death path"
                )

    def _branch_targets(self):
        """Every branch target in .text, by byte-decoding branch opcodes.

        Byte-level rather than by walking a disassembly, for the same reason
        the site scan is: a linear pass desynchronises and would report an
        address as having no incoming branch, which is the worst possible wrong
        answer before stealing bytes for a hook.
        """
        blob = self.data[self.raw:self.raw + self.rsize]
        short = {0x70 | code for code in range(16)} | {0xEB}
        targets = {}
        for offset in range(len(blob) - 6):
            opcode = blob[offset]
            if opcode in short:
                delta = struct.unpack_from("<b", blob, offset + 1)[0]
                target = self.va + offset + 2 + delta
            elif opcode == 0x0F and 0x80 <= blob[offset + 1] <= 0x8F:
                delta = struct.unpack_from("<i", blob, offset + 2)[0]
                target = self.va + offset + 6 + delta
            elif opcode == 0xE9:
                delta = struct.unpack_from("<i", blob, offset + 1)[0]
                target = self.va + offset + 5 + delta
            else:
                continue
            targets.setdefault(target, []).append(self.va + offset)
        return targets

    def _stolen_span(self, address):
        """Whole instructions from `address` until the field has been written.

        Derived, never a fixed count. Two instructions is right at five of the
        seven damage sites and WRONG at 0x43BAEB and 0x43BC43, which need three
        (`lea ; dec ecx ; mov [eax], ecx`) -- taking two there covers 8 bytes
        and leaves the store outside the splice. A fixed instruction count is
        the same error as a fixed byte window, one level up.
        """
        start = self.raw + (address - self.va)
        span = 0
        for instruction in self.md.disasm(self.data[start:start + 24], address):
            span += instruction.size
            operands = instruction.op_str
            if instruction.mnemonic in ("dec", "add", "sub") and operands.startswith(
                "dword ptr [eax]"
            ):
                return span
            if instruction.mnemonic == "mov" and operands.startswith(
                "dword ptr [eax],"
            ):
                return span
        return 0

    def test_the_branch_scan_finds_known_targets(self):
        """Positive control for the two-entry check below.

        The clean result there is an EMPTY list, and an empty list is what a
        broken scan also produces -- three separate weakenings of that test
        (blinding the decoder to rel32 conditionals, dropping the minimum span,
        pinning the span to a fixed instruction count) all left it green,
        because nothing it looks for exists. So the scan has to be shown to
        find targets that are known to be there before its silence means
        anything.

        0x43BAF7 and 0x43BC4D are real branch targets just past two of the
        damage sites, each reached from several branches. They are also the
        reason this whole check is worth having: they land on the far side of
        the stolen span, where they are harmless, and the difference between
        that and landing inside it is the entire question.
        """
        targets = self._branch_targets()
        for target, sources in ((0x43BAF7, (0x43BAC1, 0x43BAD0)),
                                (0x43BC4D, (0x43BBEB, 0x43BC1B, 0x43BC37))):
            with self.subTest(target=hex(target)):
                self.assertIn(
                    target,
                    targets,
                    f"the scan must see the branch target at {target:#010x}",
                )
                for source in sources:
                    self.assertIn(
                        source,
                        targets[target],
                        f"{source:#010x} branches to {target:#010x}",
                    )
        # One control per branch ENCODING. The two targets above are reached by
        # rel8 branches only, so they cannot detect a decoder blind to rel32
        # conditionals -- blinding it left this test green until the pair below
        # was added. 0x43B961 is reached by four rel32 `jcc`s inside the death
        # arbiter itself.
        self.assertIn(
            0x43B961,
            targets,
            "the scan must see rel32 conditional branches, not only rel8",
        )
        for source in (0x43B7E9, 0x43B7F7, 0x43B805, 0x43B813):
            self.assertIn(
                source,
                targets[0x43B961],
                f"{source:#010x} is a rel32 jcc to 0x0043B961",
            )
        # And the third encoding: an unconditional rel32 `jmp`. Blinding the
        # decoder to 0xE9 left every other assertion here green, so each of the
        # three encodings the scan handles needs its own known-present case.
        self.assertIn(
            0x467B8D,
            targets,
            "the scan must see unconditional rel32 jmps",
        )
        self.assertGreaterEqual(
            len(targets[0x467B8D]),
            100,
            "0x00467B8D is a shared epilogue reached by many rel32 jmps",
        )
        self.assertGreater(
            len(targets), 5000, "the scan must cover the whole section"
        )

    def test_no_branch_lands_inside_a_stolen_span(self):
        """A hook may only steal bytes no branch can jump into.

        This is the hazard that bit a sibling investigation on a different
        feature: a block with two entries, where a branch bypasses the
        instruction being hooked and the counter silently misses cases. Here
        the answer is clean at all seven sites -- but it has to be measured,
        because two sites DO have branches landing just past them (0x43BAF7 and
        0x43BC4D) and that reads alarming until you check which side of the
        span they fall on. Those skip the damage entirely, so a hook that does
        not fire is correct.

        The empty expected result is why the test above exists: read this one
        together with it, never alone.
        """
        targets = self._branch_targets()
        for address in sorted(DOCUMENTED_DAMAGE):
            with self.subTest(site=hex(address)):
                span = self._stolen_span(address)
                self.assertEqual(
                    span,
                    EXPECTED_SPANS[address],
                    f"{address:#010x} stolen span changed; a span derived by a "
                    "fixed instruction count is 8 here rather than 10 at the "
                    "three-instruction sites, which leaves the store outside "
                    "the splice",
                )
                # Derived from the jmp encoding rather than written as a
                # literal, so lowering a constant cannot make a too-short site
                # pass. A rel32 jmp is one opcode byte plus a four-byte
                # displacement; anything shorter cannot be spliced at all.
                self.assertGreaterEqual(
                    span,
                    len(b"\xe9") + 4,
                    f"{address:#010x} must have room for a 5-byte jmp",
                )
                landing = [
                    target
                    for target in range(address + 1, address + span)
                    if target in targets
                ]
                self.assertEqual(
                    [],
                    [hex(target) for target in landing],
                    f"{address:#010x} would be spliced across a branch target",
                )

    def test_every_damage_site_opens_with_the_same_pointer_lea(self):
        """All seven sites compute the health pointer into eax the same way.

        This is what collapses the guard shapes into one wrapper: the site
        differences are in which registers feed the `lea`, not in what the
        wrapper has to do afterwards. If a future site broke this shape the
        single-wrapper design would silently stop being valid, so it is
        asserted rather than assumed.
        """
        for address in sorted(DOCUMENTED_DAMAGE):
            with self.subTest(site=hex(address)):
                block = self._block_at(address, 0x10)
                self.assertTrue(block, f"{address:#010x} must decode")
                head = block[0]
                self.assertEqual(
                    head.mnemonic,
                    "lea",
                    f"{address:#010x} must open with the pointer computation",
                )
                self.assertEqual(
                    head.size, 7, "the lea must be 7 bytes so a jmp fits inside"
                )
                self.assertTrue(
                    head.op_str.startswith("eax, ["),
                    "the pointer must land in eax for the shared wrapper",
                )
                self.assertIn(
                    hex(HEALTH_DISPLACEMENT),
                    head.op_str,
                    "the lea must address the health field",
                )

    def _flag_writes(self, instruction):
        """Flags this instruction leaves DEFINED, by any means.

        Counting only capstone's MODIFY class is wrong and produced a false
        alarm: `test ecx, ecx` is MODIFY on PF/ZF/SF but RESET on CF/OF,
        because the SDM has TEST *clear* those rather than leave them stale.
        Reading MODIFY alone made OF look live at two sites and nearly produced
        a "your analysis is wrong" message to a peer whose analysis was right.
        """
        import capstone

        defined = set()
        for flag in ("CF", "PF", "AF", "ZF", "SF", "OF"):
            for kind in ("MODIFY", "RESET", "SET", "UNDEFINED"):
                mask = getattr(capstone.x86, f"X86_EFLAGS_{kind}_{flag}", 0)
                if mask & instruction.eflags:
                    defined.add(flag)
        return defined

    def _flag_reads(self, instruction):
        import capstone

        return {
            flag
            for flag in ("CF", "PF", "AF", "ZF", "SF", "OF")
            if getattr(capstone.x86, f"X86_EFLAGS_TEST_{flag}", 0)
            & instruction.eflags
        }

    def test_no_site_resumes_with_live_flags(self):
        """Nothing downstream may read a flag the mutation set.

        A wrapper spliced in here restores registers but not flags unless it
        says so, and a corrupted flag produces a WRONG NUMBER rather than a
        crash -- the class that never generates a bug report. So whether the
        mutation's flags are still live at the resume point decides whether the
        wrapper must carry a `pushfd`/`popfd` pair.

        The answer is that they are dead at all seven sites. Establishing that
        took three attempts, in both wrong directions:

          1. walking to the first flag READER and stopping -- reports dead
             whenever a reader is far away, regardless of intervening writes;
          2. tracking writes but counting only capstone's MODIFY class --
             reported OF live at 0x433367 and 0x4375E7, because the `test`
             between the resume point and the `jge` RESETs OF rather than
             MODIFYing it;
          3. counting MODIFY, RESET, SET and UNDEFINED as writes -- dead
             everywhere, which the SDM confirms.

        The shipped wrapper carries `pushfd`/`popfd` anyway, so this property
        is not load-bearing. It is asserted because a future site added without
        it would otherwise silently depend on a fact nobody re-derived, and
        because the analysis above is worth keeping next to the addresses it
        describes.
        """
        for address in sorted(DOCUMENTED_DAMAGE):
            with self.subTest(site=hex(address)):
                span = self._stolen_span(address)
                resume = address + span
                live = {"CF", "PF", "AF", "ZF", "SF", "OF"}
                start = self.raw + (resume - self.va)
                verdict = None
                for instruction in self.md.disasm(
                    self.data[start:start + 48], resume
                ):
                    read = self._flag_reads(instruction) & live
                    if read:
                        verdict = (
                            f"{instruction.address:#010x} "
                            f"{instruction.mnemonic} {instruction.op_str} "
                            f"reads {sorted(read)} left by the mutation"
                        )
                        break
                    live -= self._flag_writes(instruction)
                    if not live:
                        break
                    if instruction.mnemonic in ("call", "ret"):
                        verdict = "flags still live across a call boundary"
                        break
                self.assertIsNone(
                    verdict,
                    f"{address:#010x} resumes with live flags: {verdict}",
                )

    def test_the_flag_model_counts_reset_as_a_write(self):
        """Positive control for the liveness check above.

        The check's clean answer is "nothing live", which is also what a model
        that thinks every instruction rewrites everything would report. This
        pins the specific modelling detail that got it wrong: `test` must be
        seen to define CF and OF, not merely PF/ZF/SF.
        """
        import capstone

        decoded = list(self.md.disasm(b"\x85\xc9", 0))
        self.assertEqual(len(decoded), 1)
        self.assertEqual(decoded[0].mnemonic, "test")
        defined = self._flag_writes(decoded[0])
        self.assertEqual(
            defined,
            {"CF", "PF", "AF", "ZF", "SF", "OF"},
            "TEST defines every arithmetic flag -- SF/ZF/PF from the result, "
            "CF/OF cleared, AF undefined -- and a model that misses the "
            "cleared ones reports stale flags that are actually zero",
        )
        # And the converse: a `mov` must define nothing, or the liveness walk
        # would clear flags that really are still live.
        moved = list(self.md.disasm(b"\x8b\x46\x04", 0))
        self.assertEqual(
            self._flag_writes(moved[0]),
            set(),
            "a plain mov must not be treated as defining flags",
        )

    def test_the_old_age_store_is_a_store_not_a_decrement(self):
        """0x43BDEE zeroes health directly; no decrement reaches it.

        It is a death, but it needs a different wrapper from the damage sites
        because there is no pre-value to compare against -- the transition gate
        used elsewhere has nothing to read.
        """
        chain = self.chains.get(0x43BDEE)
        self.assertIsNotNone(chain, "the old-age store must decode")
        head = chain[0]
        self.assertEqual(head.mnemonic, "mov")
        self.assertTrue(
            head.op_str.endswith(", 0"),
            "the old-age path stores zero rather than decrementing",
        )


if __name__ == "__main__":
    unittest.main()
