"""VV1's Barrel row must ask the same population gate the purchase path uses.

The Tech-menu row counted occupied villager records and compared the total
against a hardcoded ``0x57`` (87). That is the **stock** ceiling. The patcher
ships population modes that raise it -- Collection Progression and Immediate
Fixed both replace the game's cap check, so the real cap becomes 256 -- and
from 88 occupied records onward the row therefore read "no room" while the
purchase path would have sold the barrel. The menu contradicted the buy logic
in every expanded mode.

The repair keeps the occupied-record scan and delegates the varying bound to
``POPULATION_FINAL_TIER_VA``, the helper the purchase path already calls. Two
checks, because neither subsumes the other:

* the **occupied-record scan** counts records that are occupied, including dead
  and unburied villagers and pregnancies -- which hold a record while the living
  population counter skips them, so a village can look small with almost no
  free slots;
* the **tier helper** reads the cap-check opcode to tell stock (87) from
  expanded (253) apart.

These tests assert the *wiring*, not merely that the right instructions appear
somewhere. Presence checks are what a broken build passes: an ``inc edx`` that
no longer sits inside the occupancy branch, a ``call`` whose result nothing
tests, or a helper invoked with the wrong register all leave a presence-only
assertion green while the row misreports capacity.

They read the **tracked manifest** -- the bytes the patcher installs -- rather
than the builder source, because a source edit whose generator did not run
leaves the shipped payload carrying the old literal. That is exactly what
happened while this fix was being written, with a fully green suite.

They deliberately do NOT read the research executable under ``research/``: that
directory is gitignored with nothing tracked, so a clean checkout has no copy
and every test here would skip while looking like coverage. The builder also
writes that executable *before* the manifest, so such a test cannot catch a
generator run that left the manifest stale.

They also do NOT import the builder. Its module scope imports Keystone from the
gitignored ``.tools`` tree, so ``exec_module`` raises ``ModuleNotFoundError``
wherever Keystone is absent -- which skips nothing and executes nothing. The
handful of constants needed are parsed out of the builder text instead.
"""

import json
import pathlib
import re
import unittest

try:
    import capstone
except ImportError:  # pragma: no cover - exercised only without capstone
    capstone = None

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_vv1_origins_feature.py"
MANIFEST = ROOT / "data" / "vv1_origins_feature.json"

# The stock-only ceiling the row used to hardcode.
STOCK_LITERAL = 0x57
# The villager-record stride and array length the scan walks.
RECORD_STRIDE = 0x3D8
RECORD_COUNT = 0x100
# The state bit that marks the Barrel row unavailable.
NO_ROOM_BIT = 0x1000000


def _constant(name):
    """One integer constant from the builder, read as TEXT.

    Importing the builder is not an option: its module scope imports Keystone
    from the gitignored .tools tree, so exec_module raises ModuleNotFoundError
    wherever Keystone is absent and the whole class executes zero tests.
    """
    text = BUILDER.read_text(encoding="utf-8")
    match = re.search(r"^%s\s*=\s*(0x[0-9A-Fa-f]+)\s*$" % name, text, re.M)
    if match is None:
        raise AssertionError("%s is not a plain literal in the builder" % name)
    return int(match.group(1), 16)


def _addresses():
    """The two virtual addresses this test needs, derived the builder's way."""
    image_base = _constant("IMAGE_BASE")
    shr_rva = _constant("SHR_RVA")
    shr_file = _constant("SHR_FILE_OFFSET")
    rows_file = _constant("PENDING_ROWS_FILE_OFFSET")
    tier_file = _constant("POPULATION_FINAL_TIER_FILE_OFFSET")
    return {
        "rows_file": rows_file,
        "rows_va": image_base + shr_rva + (rows_file - shr_file),
        "tier_va": image_base + shr_rva + (tier_file - shr_file),
    }


def _row_gate_instructions():
    """Decode the pending-rows routine out of the TRACKED manifest.

    The builder emits it as one patch at PENDING_ROWS_FILE_OFFSET, assembled
    for PENDING_ROWS_VA, so the patch body disassembles at that virtual address
    with no PE section walk and no untracked artifact.
    """
    where = _addresses()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    start = where["rows_file"]
    for patch in manifest.get("patches", []):
        body = patch.get("after")
        if not body:
            continue
        offset = int(patch["offset"], 0)
        blob = bytes.fromhex(body)
        if not offset <= start < offset + len(blob):
            continue
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        return where, list(md.disasm(blob[start - offset:], where["rows_va"]))
    raise AssertionError(
        "no VV1 patch carries file offset %#x, so the pending-rows routine is "
        "not in the shipped manifest at all" % start
    )


def _direct_target(instruction):
    """Absolute target of a DIRECT call, or None.

    Indirect forms such as ``call dword ptr [0x457010]`` are not calls to a
    known address. Passing one to int() raises, which made an earlier revision
    CRASH on the unfixed build instead of reporting it -- and a crash reads as
    a broken tool rather than a detected defect.
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
        cls.where, cls.instructions = _row_gate_instructions()

    def _text(self):
        return " ; ".join(
            "%s %s" % (i.mnemonic, i.op_str) for i in self.instructions
        )

    def test_the_stock_only_ceiling_is_gone(self):
        """The exact regression, pinned by its encoding.

        ``cmp edx, 0x57`` is the stock ceiling. Its return means the row
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

    def test_the_scan_counts_occupied_records_across_the_whole_array(self):
        """The scan must be a real loop, gated on occupancy.

        Asserting only that an ``inc edx`` exists proves nothing: making the
        increment unconditional, or shrinking the loop to one record, leaves
        such a check green while the row computes a meaningless count. So this
        pins the three parts that make it a scan -- the occupancy test, the
        conditional that skips the increment, and the walk over the full
        256-record array at the correct stride.
        """
        text = self._text()
        by_addr = {i.address: n for n, i in enumerate(self.instructions)}

        increments = [
            i for i in self.instructions
            if i.mnemonic == "inc" and i.op_str.strip() == "edx"
        ]
        self.assertTrue(
            increments,
            "nothing counts occupied villager records any more, so a village "
            "full of unburied remains can buy a barrel with nowhere to put "
            "its children: %s" % text,
        )

        # The increment must be reached only when a record reads as occupied:
        # a `cmp byte ptr [reg], 0` AND a conditional that skips the increment.
        #
        # Requiring only the `cmp` is not enough, and mutation testing proved
        # it: NOPing the `je` leaves the compare in place, so the increment
        # becomes unconditional and every slot is counted -- while a
        # cmp-only assertion stays green. Both halves are needed, and the
        # branch must actually jump PAST the increment.
        gated = False
        for inc in increments:
            index = by_addr[inc.address]
            window = self.instructions[max(0, index - 3):index]
            has_cmp = any(
                i.mnemonic == "cmp"
                and i.op_str.startswith("byte ptr [")
                and i.op_str.endswith(", 0")
                for i in window
            )
            skips = False
            for i in window:
                if i.mnemonic not in ("je", "jz", "jne", "jnz"):
                    continue
                try:
                    target = int(i.op_str, 16)
                except ValueError:
                    continue
                if target > inc.address:
                    skips = True
            if has_cmp and skips:
                gated = True
        self.assertTrue(
            gated,
            "the record counter is incremented without testing whether the "
            "record is occupied, so it counts every slot and the row reports "
            "no room in an empty village: %s" % text,
        )

        self.assertTrue(
            any(
                i.mnemonic == "add" and i.op_str.endswith("%#x" % RECORD_STRIDE)
                for i in self.instructions
            ),
            "the scan does not advance by the villager-record stride %#x, so "
            "it is not walking the record array: %s" % (RECORD_STRIDE, text),
        )
        self.assertTrue(
            any(
                i.mnemonic == "mov" and i.op_str.endswith("%#x" % RECORD_COUNT)
                for i in self.instructions
            ),
            "the scan no longer covers all %d records; occupied records are "
            "not packed to the front, so a shorter walk misses skeletons "
            "living above the bound: %s" % (RECORD_COUNT, text),
        )

    def test_the_helper_receives_the_count_and_its_answer_gates_the_row(self):
        """The call must be wired, not merely present.

        Three separate ways a present call still misreports capacity, each of
        which a target-only assertion misses:

          * the helper's ABI wants the occupied count in EAX. Drop the
            ``mov eax, edx`` and it reads a stale pointer and normally says
            "no room", disabling the row.
          * nothing testing EAX afterwards means the answer is discarded.
          * the no-room bit must be written only when the helper says no; if
            the branch is removed or inverted the row is marked unavailable
            regardless of the installed mode.
        """
        tier = self.where["tier_va"]
        text = self._text()
        by_addr = {i.address: n for n, i in enumerate(self.instructions)}

        calls = [i for i in self.instructions if _direct_target(i) == tier]
        self.assertTrue(
            calls,
            "the VV1 Barrel row does not call the population tier helper at "
            "%#x, so its ceiling is not mode-aware and can disagree with the "
            "purchase path: %s" % (tier, text),
        )

        wired = []
        for call in calls:
            index = by_addr[call.address]
            before = self.instructions[max(0, index - 3):index]
            after = self.instructions[index + 1:index + 5]

            passes_count = any(
                i.mnemonic == "mov" and i.op_str.replace(" ", "") == "eax,edx"
                for i in before
            )
            tests_result = any(
                i.mnemonic == "test"
                and i.op_str.replace(" ", "") == "eax,eax"
                for i in after
            )
            # The helper returns 1 for "room". After `test eax, eax` that sets
            # ZF only when the answer was 0, so the branch that skips the
            # no-room write must be JNE/JNZ -- "not zero" means room.
            #
            # Polarity has to be asserted explicitly, not inferred from finding
            # a suitable branch: inverting `jne` to `je` simply makes a
            # search-for-jne find nothing, which is indistinguishable from
            # "this call site was not the interesting one". Mutation testing
            # caught exactly that. So a wrong-polarity branch over the same
            # no-room write is recorded as a POSITIVE fault rather than an
            # absence.
            skips_no_room = False
            inverted = False
            for branch in after:
                if branch.mnemonic not in ("jne", "jnz", "je", "jz"):
                    continue
                try:
                    target = int(branch.op_str, 16)
                except ValueError:
                    continue
                jumps_over_no_room = any(
                    i.mnemonic == "or"
                    and "%#x" % NO_ROOM_BIT in i.op_str
                    and call.address < i.address < target
                    for i in self.instructions
                )
                if not jumps_over_no_room:
                    continue
                if branch.mnemonic in ("jne", "jnz"):
                    skips_no_room = True
                else:
                    inverted = True
            self.assertFalse(
                inverted,
                "the branch after the tier helper skips the no-room bit on "
                "ZERO, but the helper returns 1 for room -- so the row is "
                "marked unavailable exactly when there IS room, and available "
                "when there is not: %s" % text,
            )
            wired.append((passes_count, tests_result, skips_no_room))

        self.assertTrue(
            any(w[0] for w in wired),
            "the occupied count is never moved into EAX before the tier "
            "helper call, so the helper reads an unrelated value and normally "
            "reports no room -- disabling the Barrel row even though the scan "
            "and the call are both present: %s" % text,
        )
        self.assertTrue(
            any(w[1] for w in wired),
            "nothing tests the tier helper's result, so its answer is "
            "discarded and the row's availability does not follow the "
            "installed population mode: %s" % text,
        )
        self.assertTrue(
            any(w[2] for w in wired),
            "a 'room available' answer does not branch past the no-room bit, "
            "so the Barrel row is marked unavailable regardless of what the "
            "tier helper said: %s" % text,
        )


if __name__ == "__main__":
    unittest.main()
