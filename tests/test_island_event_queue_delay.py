"""The purchased Island Event is queued, and the pending guard knows it is.

Two halves that MUST move together, which is the whole point of this file.

Half one: the purchase queues the event a few real seconds out instead of
making it due on the very next scheduler tick. Each game stamps ``now + delay``
read from its own scheduler clock. Those clocks all convert
GetSystemTimeAsFileTime through 0x989680 (10,000,000), so they return Unix
epoch SECONDS -- the same units the due stamp already holds and the same units
Time Warp subtracts in, which makes the delay real seconds at every game speed.

Half two: the duplicate-purchase guard reads that same field, and it used to
treat "queued" as "exactly zero", because queueing had always meant "due now".
A delayed stamp is not zero. Shipping half one without half two -- which is
exactly what #207 did, and #209 reverted -- made a freshly purchased Island
Event read as un-purchased: the row stayed enabled and could be bought again
inside the delay window and charged a second time.

So the guard now treats a stamp as queued when it is zero (the legacy trigger,
still used by some barrels) OR falls due within the delay window. A naturally
scheduled event sits far beyond that window and is still correctly ignored.

VV3 is deliberately absent: it owns a separate due stamp in its appended
.vv3md page plus its own pending flag, so it never depended on the zero
sentinel. Its equivalent is pinned in tests/test_vv3_barrel_event_table.py.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# game -> (generator, clock VA, due-stamp field, world register in the branch)
GAMES = {
    "vv1": ("scripts/build_vv1_origins_feature.py", "0x402F70", 0xA300, "edi"),
    "vv2": ("scripts/build_vv2_origins_feature.py", "0x403200", 0x2EAE0, "edi"),
    "vv4": ("scripts/build_vv4_origins_feature.py", "0x403750", 0x170E0, "ecx"),
}


def branch(text: str, label: str) -> str:
    start = text.find("        " + label + ":")
    if start == -1:
        return ""
    rest = text[start + len(label) + 9:]
    nxt = re.search(r"^\s{8}[a-z_0-9]+:\s*$", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def guard(text: str) -> str:
    start = text.find("pending_rows_code = assemble(")
    if start == -1:
        return ""
    return text[start : text.find("PENDING_ROWS_VA", start)]


class PurchaseIsQueuedTests(unittest.TestCase):
    def test_no_game_makes_the_island_event_due_immediately(self) -> None:
        for gid, (script, _c, field, reg) in GAMES.items():
            with self.subTest(game=gid):
                text = (ROOT / script).read_text(encoding="utf-8")
                body = branch(text, "do_island_event")
                self.assertTrue(body, gid + " has no do_island_event branch")
                self.assertNotIn(
                    "mov dword ptr [%s + 0x%X], 0" % (reg, field), body,
                    gid + " still makes the Island Event due on the next tick",
                )

    def test_every_game_stamps_the_delay_from_its_own_clock(self) -> None:
        for gid, (script, clock, field, reg) in GAMES.items():
            with self.subTest(game=gid):
                text = (ROOT / script).read_text(encoding="utf-8")
                body = branch(text, "do_island_event")
                self.assertIn("ISLAND_QUEUE_CLOCK_VA", body)
                self.assertIn("ISLAND_QUEUE_DELAY_SECONDS", body)
                self.assertIn("mov dword ptr [%s + 0x%X], eax" % (reg, field), body)
                self.assertIn("ISLAND_QUEUE_CLOCK_VA = " + clock, text)


class PendingGuardKnowsAboutTheDelayTests(unittest.TestCase):
    """The half whose absence shipped a double charge in #207."""

    def test_no_guard_still_treats_zero_as_the_only_queued_state(self) -> None:
        for gid, (script, _c, field, _r) in GAMES.items():
            with self.subTest(game=gid):
                text = (ROOT / script).read_text(encoding="utf-8")
                body = guard(text)
                self.assertTrue(body, gid + " has no pending_rows helper")
                self.assertNotRegex(
                    body,
                    r"cmp dword ptr \[e[a-z]{2} \+ 0x%X\], 0\s*\n\s*jne" % field,
                    gid + " guard reads queued as exactly zero, so a delayed "
                    "stamp looks un-purchased and the row can be bought twice",
                )

    def test_every_guard_tests_the_delay_window(self) -> None:
        for gid, (script, _c, _f, _r) in GAMES.items():
            with self.subTest(game=gid):
                body = guard((ROOT / script).read_text(encoding="utf-8"))
                self.assertIn("ISLAND_QUEUE_CLOCK_VA", body,
                              gid + " guard never reads the clock")
                self.assertIn("ISLAND_QUEUE_DELAY_SECONDS", body,
                              gid + " guard never compares against the window")
                self.assertRegex(body, r"sub ebx, eax",
                                 gid + " guard does not compute stamp - now")

    def test_zero_is_still_accepted_as_queued(self) -> None:
        """Some barrels still trigger by zeroing, so zero must remain pending.

        Asserted as an OUTCOME -- a zero slot reaches the island-pending label
        -- rather than by pinning `test ebx, ebx` immediately followed by `jz`.
        That encoding stopped being the only correct one when VV4 had to tell
        apart the two upgrades sharing its queue slot: do_barrel zeroes
        [world+0x170E0] to cue the game's own event check, so a zero there can
        belong to either, and VV4 now consults BARREL_ARMED_VA before deciding.
        Zero with no barrel armed still means the island is pending -- the
        property this test is named for. Only the branch shape changed, which
        is exactly the kind of change a mechanism-pinned assertion cannot
        survive.
        """
        for gid, (script, _c, _f, _r) in GAMES.items():
            with self.subTest(game=gid):
                text = guard((ROOT / script).read_text(encoding="utf-8"))
                self.assertIn(
                    "test ebx, ebx",
                    text,
                    f"{gid}: the guard no longer tests the queue slot for zero",
                )
                self.assertTrue(
                    "jz pending_rows_island" in text
                    or "jmp pending_rows_island" in text,
                    f"{gid}: no path from the zero test reaches the "
                    "island-pending label, so an event that signals itself by "
                    "zeroing the slot would read as not pending",
                )

    def test_the_guard_balances_every_push_it_makes(self) -> None:
        """Both exits pop what they pushed; an unbalanced path corrupts the caller.

        Only VV2 and VV4 save inside the guard. VV1 already brackets the whole
        pending_rows body with push/pop of EAX/ECX/EDX/EBX, so a second local
        save there would be dead weight -- its balance is asserted separately
        below rather than by pretending the three games look alike.
        """
        for gid in ("vv2", "vv4"):
            with self.subTest(game=gid):
                body = guard((ROOT / GAMES[gid][0]).read_text(encoding="utf-8"))
                window = body[body.find("push ebx") : body.find("pending_rows_barrel:")]
                self.assertEqual(
                    window.count("pop ecx"), 2,
                    gid + " guard must pop ecx on BOTH the queued and "
                    "not-queued exits",
                )
                self.assertEqual(window.count("pop ebx"), 2)

    def test_vv1_relies_on_its_existing_function_level_save(self) -> None:
        """VV1's guard may clobber EBX/ECX only because the helper already saves them."""
        body = guard((ROOT / GAMES["vv1"][0]).read_text(encoding="utf-8"))
        prologue = body[: body.find("mov ebx,")]
        for reg in ("eax", "ecx", "edx", "ebx"):
            self.assertIn("push " + reg, prologue,
                          "vv1 guard clobbers registers the helper no longer saves")
        for reg in ("eax", "ecx", "edx", "ebx"):
            self.assertIn("pop " + reg, body)


class ReasoningIsRecordedTests(unittest.TestCase):
    def test_each_generator_records_why_the_guard_must_move_too(self) -> None:
        """So a future edit cannot re-split the two halves."""
        for gid, (script, _c, _f, _r) in GAMES.items():
            with self.subTest(game=gid):
                text = (ROOT / script).read_text(encoding="utf-8")
                where = text.find("ISLAND_QUEUE_CLOCK_VA = ")
                comment = text[max(0, where - 1600):where]
                self.assertIn("0x989680", comment)
                self.assertIn("#207", comment)
                self.assertIn("#209", comment)


if __name__ == "__main__":
    unittest.main()
