"""The deferred Barrel of Babies must recheck capacity when it is delivered.

Capacity is checked when the row is bought, but VV1 then waits
`BARREL_DELAY_TICKS` before dispatching.  A pregnancy or another event can take
a slot inside that window, and the stock per-child allocation then stops after
one or two children while the player has paid the full 75,000.

The fix reruns the purchase-time ladder against the live village at delivery.
The village needs no captured pointer: the enclosing main-village update owner
holds it, and the helper already recovers that register.

These tests pin the two things that can silently rot:

* the delivery ladder and the purchase ladder must stay identical -- same
  population tiers, same housing flags -- because two copies of one rule drift;
* "no room" must HOLD the paid event rather than consume it, so the barrel
  arrives when a slot frees instead of being spent on a short count.
"""

import json
import re
import unittest
from pathlib import Path

try:
    import capstone
except ImportError:  # pragma: no cover - exercised only without capstone
    capstone = None

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "vv1_origins_feature.json"
GENERATOR = ROOT / "scripts" / "build_vv1_origins_feature.py"

ROOM_CHECK_OFFSET = "0x8EB00"
ROOM_CHECK_VA = 0x490B00
MAIN_HELPER_OFFSET = "0x8B710"
MAIN_HELPER_VA = 0x48D710
POPULATION_GETTER = 0x41CF90
POPULATION_FINAL_TIER = 0x48DD00
BARREL_UPGRADE_FLAG = 0x48D708
# The gap from BARREL_MAIN_HELPER_FILE_OFFSET to EQUAL_DIVISION_CORE_FILE_OFFSET.
MAIN_HELPER_RESERVATION = 0x80
# The .vv1mc slot reserved for the room check, ending exactly where
# vv1_birth_control's composition overlay begins (0x8EC00).
ROOM_CHECK_RESERVATION = 0x100


def _patches():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    found = {}
    stack = [data]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            offset = item.get("offset")
            after = item.get("after")
            if isinstance(offset, str) and isinstance(after, str):
                found.setdefault(offset, item)
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return found


def _disasm(blob: str, va: int):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    return list(md.disasm(bytes.fromhex(blob), va))


@unittest.skipIf(capstone is None, "requires capstone")
class BarrelDeliveryCapacityTests(unittest.TestCase):
    def setUp(self):
        self.patches = _patches()
        self.assertIn(ROOM_CHECK_OFFSET, self.patches, "room check is not emitted")
        self.assertIn(MAIN_HELPER_OFFSET, self.patches, "main helper is not emitted")
        self.room = _disasm(self.patches[ROOM_CHECK_OFFSET]["after"], ROOM_CHECK_VA)
        self.main = _disasm(self.patches[MAIN_HELPER_OFFSET]["after"], MAIN_HELPER_VA)

    # -- placement ---------------------------------------------------------

    def test_both_caves_fit_their_reservations(self):
        room = len(self.patches[ROOM_CHECK_OFFSET]["after"]) // 2
        main = len(self.patches[MAIN_HELPER_OFFSET]["after"]) // 2
        self.assertLessEqual(room, ROOM_CHECK_RESERVATION)
        self.assertLessEqual(
            main,
            MAIN_HELPER_RESERVATION,
            "the main helper would run into EQUAL_DIVISION_CORE",
        )

    def test_room_check_lives_in_the_owned_section_not_a_shared_cave(self):
        """.vv1mc is patch-owned; .shr is shared with Cure/Equal-Division."""
        self.assertGreaterEqual(int(ROOM_CHECK_OFFSET, 0), 0x8E000)
        self.assertLess(int(ROOM_CHECK_OFFSET, 0), 0x8EC00)

    # -- the ladder --------------------------------------------------------

    def _delivery_ladder(self):
        tiers, flags = [], []
        for insn in self.room:
            if insn.mnemonic == "cmp" and insn.op_str.startswith("eax, "):
                tiers.append(int(insn.op_str.split(", ")[1], 0))
            if insn.mnemonic == "cmp" and "ecx +" in insn.op_str:
                flags.append(int(re.search(r"ecx \+ (0x[0-9a-f]+)", insn.op_str)[1], 16))
        return tiers, flags

    def _purchase_ladder(self):
        """The same ladder as written in the menu handler's source."""
        text = GENERATOR.read_text(encoding="utf-8")
        block = text[text.index("cmp eax, 12") : text.index("POPULATION_FINAL_TIER_VA:X}")]
        tiers = [int(m, 0) for m in re.findall(r"cmp eax, (\d+)", block)]
        flags = [int(m, 16) for m in re.findall(r"edi \+ (0x[0-9A-Fa-f]+)\]", block)]
        return tiers, flags

    def test_delivery_ladder_matches_the_purchase_ladder(self):
        """Two copies of one capacity rule drift; assert they cannot."""
        self.assertEqual(self._delivery_ladder(), self._purchase_ladder())

    def test_delivery_ladder_uses_the_shared_final_tier_helper(self):
        """The installed population cap must not be re-hardcoded here."""
        targets = [int(i.op_str, 16) for i in self.room if i.mnemonic == "call"]
        self.assertIn(POPULATION_GETTER, targets)
        self.assertIn(POPULATION_FINAL_TIER, targets)

    def test_room_check_preserves_the_registers_the_dispatch_still_needs(self):
        """esi/ebx/edi must survive: the caller uses esi after this returns."""
        written = set()
        for insn in self.room:
            if insn.mnemonic in {"mov", "xor", "pop", "inc", "dec", "add", "sub"}:
                dest = insn.op_str.split(",")[0].strip()
                if dest in {"esi", "ebx", "edi", "ebp"}:
                    written.add(dest)
        self.assertEqual(written, set())

    # -- the caller --------------------------------------------------------

    def test_main_helper_rechecks_before_it_constructs_the_event(self):
        order = [
            index
            for index, insn in enumerate(self.main)
            if insn.mnemonic == "call"
            and int(insn.op_str, 16) in {ROOM_CHECK_VA, 0x4286B0}
        ]
        self.assertEqual(len(order), 2, "expected the room check and the constructor")
        first = int(self.main[order[0]].op_str, 16)
        self.assertEqual(
            first,
            ROOM_CHECK_VA,
            "capacity must be rechecked before the event object is built",
        )

    def test_main_helper_reads_the_village_from_the_live_frame(self):
        """[esi+0x10], recovered from the enclosing update owner -- not a
        pointer captured at purchase, which could go stale across a load."""
        text = " ; ".join(f"{i.mnemonic} {i.op_str}" for i in self.main)
        self.assertIn("mov esi, dword ptr [esp + 4]", text)
        self.assertIn("mov ecx, dword ptr [esi + 0x10]", text)

    def test_no_room_holds_the_paid_event_instead_of_consuming_it(self):
        """The refusal path must not reach the token clear.

        If it did, the player would be charged and get nothing at all, which is
        worse than the short count this fixes.
        """
        addresses = [i.address for i in self.main]
        room_call = next(
            i for i in self.main if i.mnemonic == "call" and i.op_str == hex(ROOM_CHECK_VA)
        )
        refusal = next(
            i
            for i in self.main
            if i.address > room_call.address and i.mnemonic in {"je", "jz"}
        )
        target = int(refusal.op_str, 16)
        self.assertIn(target, addresses)
        tail = [i for i in self.main if i.address >= target]
        self.assertEqual(
            tail[0].mnemonic,
            "popal",
            "the no-room branch must land on the shared restore, not mid-dispatch",
        )
        # Nothing after the branch target clears the pending token, so the
        # barrel stays queued and the next tick retries.
        cleared = [
            i
            for i in tail
            if i.mnemonic == "mov" and "0x48d700" in i.op_str.lower()
        ]
        self.assertEqual(cleared, [])

    def test_three_child_override_is_armed_only_on_the_dispatch_path(self):
        """A natural barrel must not consume the one-shot while ours waits."""
        main_arms = [
            i
            for i in self.main
            if i.mnemonic == "mov" and hex(BARREL_UPGRADE_FLAG) in i.op_str.lower()
        ]
        self.assertEqual(
            main_arms,
            [],
            "the flag must be armed inside the room check, past the refusal",
        )
        room_arms = [
            i
            for i in self.room
            if i.mnemonic == "mov" and hex(BARREL_UPGRADE_FLAG) in i.op_str.lower()
        ]
        self.assertEqual(len(room_arms), 1)
        returns = [i.address for i in self.room if i.mnemonic == "ret"]
        self.assertTrue(
            any(address > room_arms[0].address for address in returns),
            "arming must be followed by a return, not fall into the refusal",
        )


if __name__ == "__main__":
    unittest.main()
