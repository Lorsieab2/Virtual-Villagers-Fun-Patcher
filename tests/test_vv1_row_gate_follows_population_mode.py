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


def _branch_target(instruction):
    """Absolute target of a direct jump, or None for indirect forms."""
    if not instruction.mnemonic.startswith("j"):
        return None
    try:
        return int(instruction.op_str, 16)
    except ValueError:
        return None


def _writes_eax(instruction):
    """True when the instruction's destination operand is EAX."""
    first = instruction.op_str.split(",")[0].strip()
    return first == "eax"


@unittest.skipIf(capstone is None, "requires capstone")
class VV1RowGateFollowsPopulationModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.where, cls.instructions = _row_gate_instructions()

    def _text(self):
        return " ; ".join(
            "%s %s" % (i.mnemonic, i.op_str) for i in self.instructions
        )

    def test_the_tech_menu_actually_calls_this_routine(self):
        """A validated routine nothing calls protects nothing.

        Removing the Tech-menu ``call PENDING_ROWS_VA`` while leaving the cave
        in place makes every other assertion here vacuous -- the routine is
        still perfect and never runs. The caller must therefore be asserted
        too, and it has to live OUTSIDE the routine: the cave's own internal
        call to the tier helper is not a caller of the cave.
        """
        rows_va = self.where["rows_va"]
        rows_file = self.where["rows_file"]
        inside = {i.address for i in self.instructions}
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

        callers = []
        for patch in manifest.get("patches", []):
            body = patch.get("after")
            if not body:
                continue
            offset = int(patch["offset"], 0)
            blob = bytes.fromhex(body)
            # Every patch body in this feature is assembled for the .shr page,
            # so its virtual base is the routine's VA shifted by the file-offset
            # difference. That makes each body's addresses directly comparable.
            base = rows_va - (rows_file - offset)
            for ins in md.disasm(blob, base):
                if ins.address in inside:
                    continue
                if _direct_target(ins) == rows_va:
                    callers.append("%s+%#x" % (patch["offset"], ins.address - base))

        self.assertTrue(
            callers,
            "nothing outside the routine calls the pending-rows cave at %#x, "
            "so the entire gate is unreachable and every other assertion in "
            "this file passes against a build where the row is never checked"
            % rows_va,
        )

    def test_the_stock_only_ceiling_is_gone(self):
        """The exact regression, in ANY register.

        ``cmp edx, 0x57`` was the original. Recognising the literal only when
        the compare uses EDX lets ``mov eax, edx / cmp eax, 0x57 / ja`` put the
        stock-only gate back in front of the mode-aware helper while this test
        stays green, so the literal is rejected whatever register carries the
        count.
        """
        pattern = re.compile(
            r"^(?:e[abcd]x|e[sd]i|ebp)\s*,\s*(?:%#x|%d)$"
            % (STOCK_LITERAL, STOCK_LITERAL)
        )
        offenders = [
            "%#x: %s %s" % (i.address, i.mnemonic, i.op_str)
            for i in self.instructions
            if i.mnemonic == "cmp" and pattern.match(i.op_str.strip())
        ]
        self.assertFalse(
            offenders,
            "the VV1 Barrel row compares a record count against the stock "
            "ceiling 87 again, so it reports 'no room' from 88 records while "
            "the purchase path would allow the barrel: %s" % offenders,
        )

    def test_the_scan_counts_occupied_records_across_the_whole_array(self):
        """The scan must be a real loop, correctly polarised, over all records.

        Each part is asserted because each breaks alone:

        * the occupancy compare, and a branch that skips the increment when the
          record reads ZERO. Inverting that ``je`` to ``jne`` counts the EMPTY
          slots instead -- the count inverts and the row reports no room in an
          empty village.
        * the record stride, so it walks records rather than bytes.
        * the bound **and a backedge that uses it**. Deleting the loop's ``jnz``
          leaves bound, stride, compare and increment all in place while
          exactly one record is inspected.
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
            "full of unburied remains can buy a barrel with nowhere to put its "
            "children: %s" % text,
        )

        gated = False
        for inc in increments:
            index = by_addr[inc.address]
            window = self.instructions[max(0, index - 3):index]
            compares_zero = any(
                i.mnemonic == "cmp"
                and i.op_str.startswith("byte ptr [")
                and i.op_str.endswith(", 0")
                for i in window
            )
            # `cmp X, 0` sets ZF when the record is EMPTY, so the branch that
            # jumps past the increment must be JE/JZ. JNE skips on occupied,
            # which counts empty slots instead.
            skips_on_zero = any(
                i.mnemonic in ("je", "jz")
                and (_branch_target(i) or 0) > inc.address
                for i in window
            )
            counts_empty = any(
                i.mnemonic in ("jne", "jnz")
                and (_branch_target(i) or 0) > inc.address
                for i in window
            )
            self.assertFalse(
                counts_empty,
                "the branch guarding the record counter skips on NON-zero, so "
                "it counts EMPTY records: the count is inverted and the row "
                "reports no room in an empty village: %s" % text,
            )
            if compares_zero and skips_on_zero:
                gated = True
        self.assertTrue(
            gated,
            "the record counter is not guarded by an occupancy test that skips "
            "empty slots, so its value is meaningless: %s" % text,
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

        backedges = [
            i for i in self.instructions
            if i.mnemonic in ("jne", "jnz", "loop", "ja", "jg")
            and (_branch_target(i) or (i.address + 1)) <= i.address
        ]
        self.assertTrue(
            backedges,
            "the record loop has no backedge, so the bound is loaded and then "
            "exactly one record is inspected -- the scan degenerates to a "
            "single sample: %s" % text,
        )

    def test_the_helper_receives_the_count_and_its_answer_gates_the_row(self):
        """The call must be wired, not merely present.

        Four ways a present call still misreports capacity, each demonstrated
        to slip past a looser assertion:

        * ``mov eax, edx`` must be the **last** write to EAX before the call.
          ``mov eax, edx / xor eax, eax / call`` passes a search-in-a-window
          while the helper receives zero.
        * ``test eax, eax`` must sit **immediately** after the call, or the
          branch below consumes some other instruction's flags.
        * the skipped write must be exactly ``or edi, 0x1000000``. ``or eax,
          0x1000000`` writes a scratch register and marks no row.
        * polarity: the helper returns 1 for room, so the branch past the
          no-room write is JNE/JNZ.
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

            passes_count = False
            for earlier in reversed(self.instructions[max(0, index - 8):index]):
                if not _writes_eax(earlier):
                    continue
                passes_count = (
                    earlier.mnemonic == "mov"
                    and earlier.op_str.replace(" ", "") == "eax,edx"
                )
                break

            after = self.instructions[index + 1:index + 3]
            tests_result = bool(
                after
                and after[0].mnemonic == "test"
                and after[0].op_str.replace(" ", "") == "eax,eax"
            )

            skips_no_room = False
            inverted = False
            if tests_result and len(after) > 1:
                branch = after[1]
                target = _branch_target(branch)
                if target is not None:
                    jumps_over = any(
                        i.mnemonic == "or"
                        and i.op_str.replace(" ", "") == "edi,%#x" % NO_ROOM_BIT
                        and call.address < i.address < target
                        for i in self.instructions
                    )
                    if jumps_over and branch.mnemonic in ("jne", "jnz"):
                        skips_no_room = True
                    elif jumps_over:
                        inverted = True

            self.assertFalse(
                inverted,
                "the branch after the tier helper skips the no-room bit on "
                "ZERO, but the helper returns 1 for room -- so the row is "
                "marked unavailable exactly when there IS room: %s" % text,
            )
            wired.append((passes_count, tests_result, skips_no_room))

        self.assertTrue(
            any(w[0] for w in wired),
            "the occupied count is not the last value written to EAX before "
            "the tier helper call, so the helper reads something else and "
            "normally reports no room -- disabling the Barrel row while the "
            "scan and the call are both present: %s" % text,
        )
        self.assertTrue(
            any(w[1] for w in wired),
            "the tier helper's result is not tested immediately after the "
            "call, so the branch below consumes unrelated flags and row "
            "availability does not follow the population mode: %s" % text,
        )
        self.assertTrue(
            any(w[2] for w in wired),
            "a 'room available' answer does not branch past `or edi, %#x`, so "
            "the Barrel row's unavailable bit is written regardless of what "
            "the tier helper said: %s" % (NO_ROOM_BIT, text),
        )


if __name__ == "__main__":
    unittest.main()
