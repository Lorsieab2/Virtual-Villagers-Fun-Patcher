"""VV1's Barrel row must ask the same population gate the purchase path uses.

The Tech-menu row counted occupied villager records and compared the total
against a hardcoded ``0x57`` (87). That is the **stock** ceiling. The patcher
ships population modes that raise it -- Collection Progression and Immediate
Fixed both replace the game's cap check, so the real cap becomes 256 -- and
from 88 occupied records onward the row therefore read "no room" while the
purchase path would have sold the barrel. The menu contradicted the buy logic
in every expanded mode.

VV2 was repaired the same way on PR #248: keep the occupied-record scan, and
delegate the varying bound to the gate the purchase path already calls. VV1
already had the helper -- ``POPULATION_FINAL_TIER_VA`` reads the cap-check
opcode to tell stock (87) from expanded (253) apart, and the purchase path
calls it -- the row gate simply never did.

Two checks are required and neither subsumes the other:

* the **occupied-record scan** catches dead and unburied villagers, and
  pregnancies, which hold a record while the living-population counter skips
  them, so a village can look small with almost no free slots;
* the **tier helper** catches the mode-dependent population ceiling.

The scan's own bound stays at ``0xFD`` -- the 256-record array minus the three
children a barrel brings. That is a statement about physical storage and does
not vary by mode, so deriving it from the cap would be wrong in both
directions: too strict wherever the cap is below 253, and meaningless at 256.

These tests read the **emitted** research executable rather than the builder
source, because a source edit whose generator did not run leaves the shipped
payload carrying the old literal -- which is exactly what happened while this
fix was being written, with a fully green suite.
"""

import importlib.util
import pathlib
import sys
import unittest

try:
    import capstone
except ImportError:  # pragma: no cover - exercised only without capstone
    capstone = None

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_vv1_origins_feature.py"
RESEARCH = (
    ROOT / "research" / "vv1-origins-apk"
    / "Virtual Villagers - A New Home - Origins Feature Research.exe"
)

# 256-record array minus the three children a barrel brings.
PHYSICAL_BOUND = 0xFD
# The stock-only ceiling the row used to hardcode.
STOCK_LITERAL = 0x57


def _builder():
    spec = importlib.util.spec_from_file_location("vv1_builder", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _section_lookup(image):
    pe = image.find(b"PE\0\0")
    count = int.from_bytes(image[pe + 6:pe + 8], "little")
    opt = int.from_bytes(image[pe + 20:pe + 22], "little")
    table = pe + 24 + opt
    base = int.from_bytes(image[pe + 24 + 28:pe + 24 + 32], "little")

    def raw(va):
        rva = va - base
        for index in range(count):
            entry = table + index * 40
            start = int.from_bytes(image[entry + 12:entry + 16], "little")
            size = int.from_bytes(image[entry + 8:entry + 12], "little")
            ptr = int.from_bytes(image[entry + 20:entry + 24], "little")
            if start <= rva < start + max(size, 1):
                return ptr + (rva - start)
        return None

    return raw


def _direct_target(instruction):
    """Absolute target of a DIRECT call, or None.

    Indirect forms such as ``call dword ptr [0x457010]`` are not calls to a
    known address. Passing one to int() raises, which made an earlier version
    of this check CRASH on the unfixed build instead of reporting it -- and a
    crash reads as a broken tool rather than a detected defect.
    """
    if instruction.mnemonic != "call":
        return None
    try:
        return int(instruction.op_str, 16)
    except ValueError:
        return None


@unittest.skipIf(capstone is None, "requires capstone")
class VV1RowGateFollowsPopulationModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not RESEARCH.is_file():
            raise unittest.SkipTest(
                "VV1 research executable not built in this clone"
            )
        cls.builder = _builder()
        image = RESEARCH.read_bytes()
        raw = _section_lookup(image)
        offset = raw(cls.builder.PENDING_ROWS_VA)
        if offset is None:
            raise unittest.SkipTest("pending-rows routine not mapped")
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        cls.instructions = list(
            md.disasm(image[offset:offset + 0x140], cls.builder.PENDING_ROWS_VA)
        )

    def test_the_stock_only_ceiling_is_gone(self):
        """The exact regression, pinned by its encoding.

        ``cmp edx, 0x57`` is the stock ceiling. Its presence means the row
        refuses from 88 occupied records in every mode, including the ones
        where the purchase path allows up to 256.
        """
        offenders = [
            hex(i.address)
            for i in self.instructions
            if i.mnemonic == "cmp"
            and i.op_str.replace(" ", "") == "edx,%#x" % STOCK_LITERAL
        ]
        self.assertFalse(
            offenders,
            "the VV1 Barrel row compares occupied records against the stock "
            "ceiling 87 again, so it reports 'no room' from 88 records while "
            "the purchase path would allow the barrel: %s" % offenders,
        )

    def test_the_physical_bound_is_still_checked(self):
        """The array bound must survive, separately from the cap.

        It catches skeletons and pregnancies, which hold a record while the
        living-population counter skips them. Replacing it with the cap check
        would drop that case entirely.
        """
        self.assertTrue(
            any(
                i.mnemonic == "cmp"
                and i.op_str.replace(" ", "") == "edx,%#x" % PHYSICAL_BOUND
                for i in self.instructions
            ),
            "the occupied-record bound (256 records minus 3 children) is no "
            "longer checked, so a village full of unburied remains can buy a "
            "barrel that has nowhere to put its children",
        )

    def test_the_row_asks_the_same_gate_as_the_purchase_path(self):
        """The varying bound must be delegated, not duplicated.

        POPULATION_FINAL_TIER_VA reads the cap-check opcode to tell stock from
        expanded apart. The purchase path calls it; the row must call the same
        helper, or the two can disagree again the next time a mode is added.
        """
        tier = self.builder.POPULATION_FINAL_TIER_VA
        self.assertTrue(
            any(_direct_target(i) == tier for i in self.instructions),
            "the VV1 Barrel row does not call the population tier helper at "
            "%#x, so its ceiling is not mode-aware and can disagree with the "
            "purchase path" % tier,
        )


if __name__ == "__main__":
    unittest.main()
