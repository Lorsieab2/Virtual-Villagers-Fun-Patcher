"""The standalone badge audit must validate the generators, not just print.

`scripts/audit_upgrade_menu_parity.py` prints "only rows 3 and 4 can show" for
every game's Tech menu.  That is a claim about the generators' Tech state
builders, and for a while it was only a claim: `audit_badges()` printed the
constant and returned an empty problem list, so running the audit on its own
still exited 0 after a generator dropped or gained a satisfied bit.  The
validation lived solely in `test_upgrade_menu_shell_text_parity.py`, which is
no help to anyone running the script.

These tests pin the audit's own behaviour, in both directions.

The two damage tests rewrite a generator in place, so they read and restore it
as BYTES.  Reading text and writing it back with newline="\n" would normalise a
CRLF working copy and leave the tree dirty on Windows even though the content
is unchanged.
"""

import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts" / "audit_upgrade_menu_parity.py"


def _load():
    spec = importlib.util.spec_from_file_location("audit_upgrade_menu_parity", AUDIT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BadgeAuditValidatesGeneratorsTests(unittest.TestCase):
    def setUp(self):
        self.audit = _load()

    def test_clean_tree_reports_no_badge_problems(self):
        self.assertEqual(self.audit.audit_badges(verbose=False), [])

    def test_every_present_generator_is_actually_read(self):
        """A generator the audit skips must be absent, not silently unchecked."""
        present = [g for g, p in self.audit.GENERATORS.items() if p.is_file()]
        self.assertTrue(present, "no generators found to audit")
        expected = {1 << row for row in self.audit.SATISFIED_BITS_SET_BY_EXE}
        for game in present:
            with self.subTest(game=game):
                bits = self.audit.tech_state_bits(self.audit.GENERATORS[game])
                self.assertEqual(bits, expected)

    def _tech_block(self, original):
        """Bound the Tech state block exactly the way `tech_state_bits` does."""
        call = self.audit.TECH_DIALOG_CALL.search(original)
        self.assertIsNotNone(call, "no Tech dialog invocation found")
        register = call.group("reg")
        zero = re.compile(rf"xor\s+{register},\s*{register}\b")
        starts = [
            m.start() for m in zero.finditer(original) if m.start() < call.start()
        ]
        self.assertTrue(starts, "the Tech state accumulator is never cleared")
        return register, zero, starts[-1], call.end()

    def test_dropping_a_tech_satisfied_bit_is_reported(self):
        """The regression the audit exists to catch must actually fail it.

        The edit is scoped to the Tech state block, so this cannot pass by
        mutating the Details menu's own `or edi, 8` instead.
        """
        generator = self.audit.GENERATORS["vv3"]
        if not generator.is_file():
            self.skipTest("vv3 generator not present")
        raw = generator.read_bytes()
        original = raw.decode("utf-8")
        register, _zero, start, end = self._tech_block(original)
        block = original[start:end]
        damaged = re.sub(
            rf"or\s+{register},\s*16\b", f"or {register}, 0", block, count=1
        )
        self.assertNotEqual(damaged, block, "no doubler bit found to drop")
        try:
            generator.write_bytes(
                (original[:start] + damaged + original[end:]).encode("utf-8")
            )
            problems = self.audit.audit_badges(verbose=False)
        finally:
            generator.write_bytes(raw)
        self.assertTrue(
            problems,
            "dropping a Tech satisfied bit left the standalone audit reporting OK",
        )
        self.assertIn("vv3", problems[0])

    def test_an_unreadable_tech_block_is_a_problem_not_a_skip(self):
        """A generator whose Tech block cannot be bounded must not pass quietly."""
        generator = self.audit.GENERATORS["vv3"]
        if not generator.is_file():
            self.skipTest("vv3 generator not present")
        raw = generator.read_bytes()
        original = raw.decode("utf-8")
        register, zero, _start, _end = self._tech_block(original)
        try:
            generator.write_bytes(
                zero.sub(f"mov {register}, 0", original).encode("utf-8")
            )
            problems = self.audit.audit_badges(verbose=False)
        finally:
            generator.write_bytes(raw)
        self.assertTrue(problems, "an unbounded Tech state block was not reported")


if __name__ == "__main__":
    unittest.main()
