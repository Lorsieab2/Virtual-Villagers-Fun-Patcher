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

These tests assert the two *properties*, not one particular encoding of them.
The physical bound in particular is left to the implementation: the tier helper
already caps expanded mode at 253 (the 256-record array minus the barrel's
three children), so a separate ``cmp edx, 0xFD`` before the call is redundant
and a correct gate may omit it. An earlier revision of this file required that
literal and would therefore have failed a working row gate.

These tests read the **tracked manifest** -- the bytes the patcher installs --
rather than the builder source, because a source edit whose generator did not
run leaves the shipped payload carrying the old literal. That is exactly what
happened while this fix was being written, with a fully green suite.

They deliberately do NOT read the research executable under ``research/``.
That directory is gitignored and nothing in it is tracked, so a clean checkout
has no copy and every test here would skip -- protecting nothing in CI. It
would also miss a generator run that wrote the executable and left the manifest
stale, since the builder writes the executable first.
"""

import importlib.util
import json
import pathlib
import sys
import unittest

try:
    import capstone
except ImportError:  # pragma: no cover - exercised only without capstone
    capstone = None

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_vv1_origins_feature.py"
# The TRACKED manifest, which is what the patcher installs. An earlier version
# of this file read the research executable under research/, but that directory
# is gitignored and nothing there is tracked -- so in a clean checkout every
# test below skipped, and the suite protected nothing. It also could not catch a
# generator run that wrote the research exe and left the manifest stale, because
# the builder writes the executable first.
MANIFEST = ROOT / "data" / "vv1_origins_feature.json"

# The stock-only ceiling the row used to hardcode.
STOCK_LITERAL = 0x57


def _builder():
    spec = importlib.util.spec_from_file_location("vv1_builder", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row_gate_instructions():
    """Decode the pending-rows routine out of the TRACKED manifest.

    The builder emits this routine as one patch whose file offset is
    ``PENDING_ROWS_FILE_OFFSET`` and whose code is assembled for
    ``PENDING_ROWS_VA``, so the patch body can be disassembled at that virtual
    address directly -- no PE section walk, and no dependency on an untracked
    build artifact.

    Both addresses are read from the builder rather than hardcoded, so moving
    the routine surfaces as a failure here instead of silently checking the
    wrong bytes.
    """
    builder = _builder()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    start = builder.PENDING_ROWS_FILE_OFFSET
    for patch in manifest.get("patches", []):
        body = patch.get("after")
        if not body:
            continue
        offset = int(patch["offset"], 0)
        blob = bytes.fromhex(body)
        if not offset <= start < offset + len(blob):
            continue
        inside = start - offset
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        return builder, list(
            md.disasm(blob[inside:], builder.PENDING_ROWS_VA)
        )
    raise AssertionError(
        "no VV1 patch carries file offset %#x, so the pending-rows routine "
        "is not in the shipped manifest at all" % start
    )


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
        cls.builder, cls.instructions = _row_gate_instructions()

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

    def test_the_occupied_record_scan_still_runs(self):
        """The scan must survive, because it sees what the cap cannot.

        It counts records that are *occupied*, including dead and unburied
        villagers and pregnancies -- which hold a record while the living
        population counter skips them, so a village can look small with almost
        no free slots. Deleting the scan and keeping only the population gate
        would drop that case entirely.

        This asserts the SCAN, not any particular bound. An earlier revision
        required a literal ``cmp edx, 0xFD`` before the helper call, which is a
        statement about one implementation rather than about the property: the
        tier helper already caps expanded mode at 253, so that pre-check is
        redundant and a correct gate may omit it. Pinning it would have failed a
        working row gate.
        """
        walks = [
            i for i in self.instructions
            if i.mnemonic == "inc" and i.op_str.strip() == "edx"
        ]
        self.assertTrue(
            walks,
            "the VV1 Barrel row no longer counts occupied villager records, so "
            "a village full of unburied remains can buy a barrel that has "
            "nowhere to put its children -- the population cap does not see "
            "those records, which is why the scan exists",
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
