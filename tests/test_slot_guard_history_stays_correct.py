"""The "nothing writes 0x4D6DE8" claim must not come back anywhere.

That claim is false, and it has been written down three separate times:

* `docs/vv4-slot-guards-are-inert.md` (twice -- reintroduced after a fix),
* the docstring of `tests/test_slot_guard_population_source.py`, whose own
  COUNTING_GAMES note simultaneously had it right,
* a comment in `tests/test_patcher.py`.

The address IS written, by `add dword ptr [0x4d6de8], ecx` at `0x45E91C`. The
false version comes from decoding one byte late -- `01 0D E8 6D 4D 00` becomes
`0D E8 6D 4D 00`, `or eax, 0x4D6DE8` -- and both readings resynchronise at
`0x45E922`, which is why it keeps looking plausible.

It matters because the two readings imply opposite failure modes. "Nothing
writes it" means the guards never fire and VV4 has no slot protection. The
truth is that they read a lifetime conception total, so they eventually fire
*permanently* and suppress children in a village with free records -- which is a
live hypothesis for VV4's reported symptom rather than a ruled-out one.

A repo-wide assertion rather than a per-file one, because the error spread by
copying between files.
"""

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Every tracked text file, not a hand-picked set of subdirectories. An earlier
# version scanned only docs/tests/scripts/src and only .md/.py, which left the
# top-level README.md -- where the population-safety behaviour is actually
# documented for users -- and How to Use.txt outside a check that called itself
# repo-wide. Verified: appending the false claim to README.md passed.
SUFFIXES = {".md", ".py", ".txt"}

# Phrasings that assert the address is unwritten. Deliberately narrow: the
# files legitimately DISCUSS the false claim while correcting it, so this
# matches the assertion, not the mention.
FALSE_CLAIMS = (
    re.compile(r"Nothing ever wrote `?0x4D6DE8", re.I),
    re.compile(r"0x4D6DE8 that nothing ever wrote", re.I),
    re.compile(r"nothing (?:ever )?writes `?0x4D6DE8", re.I),
)

# Files allowed to quote the false claim, because they exist to refute it.
QUOTING_ALLOWED = {
    "test_slot_guard_history_stays_correct.py",
    "test_vv4_slot_guards_use_a_real_counter.py",
}


def _repo_files():
    """Tracked text files, asked of git rather than guessed at.

    Using `git ls-files` means a new documentation file is covered the moment
    it is tracked, instead of only when someone remembers to widen a list.
    """
    listing = subprocess.run(
        ["git", "ls-files", "--full-name"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if listing.returncode != 0:  # pragma: no cover - not a git checkout
        raise unittest.SkipTest("not a git checkout")
    for name in listing.stdout.splitlines():
        path = ROOT / name
        if path.suffix.lower() in SUFFIXES and path.is_file():
            yield path


class SlotGuardHistoryTests(unittest.TestCase):
    def test_no_file_claims_the_address_is_unwritten(self):
        offenders = []
        for path in _repo_files():
            if path.name in QUOTING_ALLOWED:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern in FALSE_CLAIMS:
                if pattern.search(text):
                    offenders.append(f"{path.relative_to(ROOT)}: {pattern.pattern}")
        self.assertEqual(
            offenders,
            [],
            "0x4D6DE8 IS written by `add [0x4d6de8], ecx` at 0x45E91C; these "
            "files assert otherwise, which inverts the failure mode: "
            + "; ".join(offenders),
        )

    def test_the_writer_is_documented_where_the_guards_are_explained(self):
        """The correction has to be findable, not merely absent."""
        doc = (ROOT / "docs" / "vv4-slot-guards-are-inert.md").read_text(
            encoding="utf-8"
        )
        lowered = doc.lower()
        self.assertIn("add dword ptr [0x4d6de8], ecx", lowered)
        self.assertIn("0045e91c", lowered.replace("0x45e91c", "0045e91c"))

    def test_the_scan_actually_covers_files(self):
        """Guard the guard: an empty sweep would pass vacuously."""
        names = {p.name for p in _repo_files()}
        self.assertIn("test_slot_guard_population_source.py", names)
        self.assertIn("vv4-slot-guards-are-inert.md", names)
        # The root-level user documentation specifically: these sat outside an
        # earlier version of this scan while it claimed to be repo-wide.
        self.assertIn("README.md", names)
        self.assertIn("How to Use.txt", names)
        self.assertGreater(len(names), 50)


if __name__ == "__main__":
    unittest.main()
