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
