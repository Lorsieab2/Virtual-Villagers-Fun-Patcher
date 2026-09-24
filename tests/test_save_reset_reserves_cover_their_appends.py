"""Every reserve in save_reset.c must cover what its call site then appends.

`wsprintfA`/`wsprintfW` take no destination bound, so a reserve shorter than
the tail that follows it is a stack overrun of a MAX_PATH buffer, not a
truncation. The reserve is the only thing standing between a long Documents
path -- redirected to OneDrive, a network share, a deeply nested profile --
and memory corruption during Start Over.

This checks the arithmetic against the strings actually in the source, so it
cannot drift when a name is edited. It was written after a review flagged a
suspected overrun here; the arithmetic held, but nothing was proving it, and
"I read it carefully" is not a guard.

How the reserve composes:

  * `vv_save_folder_w(out, reserve)` refuses unless
    `len(Documents) + 5 + len(exe stem) + reserve < MAX_PATH`, so `reserve`
    must cover everything the caller appends after the save folder.
  * `vv_save_subfolder_w(out, sub, reserve)` adds `wcslen(sub) + 1` itself,
    so its `reserve` covers only the caller's own append -- not `sub`.
  * `legacy_subfolder_w(out, sub)` does the same with a fixed 64.
"""
from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "native" / "shared" / "save_reset.c"
FOLDER_SOURCE = ROOT / "native" / "shared" / "save_folder.c"

MAX_PATH = 260
MAX_LOG_FILES = 4096
# The widest slot and roll-over numbers that can be formatted into a name.
WIDEST_SLOT = len("5")
WIDEST_LOG_NUMBER = len(str(MAX_LOG_FILES))


def source() -> str:
    return SOURCE.read_text(encoding="utf-8")


class SaveResetReservesCoverTheirAppendsTests(unittest.TestCase):
    def test_the_sources_are_present(self) -> None:
        """Guard the guard: a moved file would pass everything vacuously."""
        self.assertTrue(SOURCE.is_file(), SOURCE)
        self.assertTrue(FOLDER_SOURCE.is_file(), FOLDER_SOURCE)

    def test_the_folder_helper_actually_enforces_its_reserve(self) -> None:
        """The whole argument rests on this refusal existing."""
        text = FOLDER_SOURCE.read_text(encoding="utf-8")
        self.assertIn(
            "docs_len + 5 + base_len + reserve >= MAX_PATH",
            text,
            "vv_save_folder_w no longer refuses when the reserve does not fit, "
            "so every reserve below is decorative",
        )
        self.assertIn(
            "vv_save_folder_w(folder, (int)wcslen(sub) + 1 + reserve)",
            text,
            "vv_save_subfolder_w no longer adds the subfolder length itself, "
            "so its callers' reserves are now short by len(sub) + 1",
        )

    def test_the_narrow_sidecar_reserve_covers_the_longest_name(self) -> None:
        """The sidecars are formatted straight onto the save folder."""
        text = source()
        names = re.findall(r'"%s(\\\\[^"]*?)"', text)
        self.assertTrue(names, "no sidecar formats found -- the pattern moved")
        longest = max(names, key=len).replace("\\\\", "\\")
        # "%d" is replaced by a single-digit slot.
        tail = len(longest.replace("%d", "5")) + 1  # + NUL

        # The reserve is written as a sizeof over the two literal halves.
        reserve_literals = re.search(
            r"vv_save_folder\(folder, \(int\)sizeof\(\s*"
            r'"([^"]*)"\s*"([^"]*)"\s*\)\)',
            text,
        )
        self.assertIsNotNone(
            reserve_literals, "the sidecar reserve is no longer a sizeof pair"
        )
        assert reserve_literals is not None
        reserve = (
            len(
                (reserve_literals.group(1) + reserve_literals.group(2)).replace(
                    "\\\\", "\\"
                )
            )
            + 1  # sizeof includes the NUL
        )
        self.assertGreaterEqual(
            reserve,
            tail,
            f"the sidecar reserve is {reserve} but the longest name appends "
            f"{tail}: {longest!r}",
        )

    def test_every_subfolder_reserve_covers_its_own_append(self) -> None:
        """`reserve` here covers only what the CALLER appends after `sub`."""
        text = source()
        # Pair each vv_save_subfolder_w(..., reserve) with the wsprintfW that
        # formats into the buffer it filled, on a following line.
        lines = text.splitlines()
        checked = 0
        for index, line in enumerate(lines):
            call = re.search(
                r"vv_save_subfolder_w\(\s*(\w+)\s*,\s*(?:L\"[^\"]*\"|\w+(?:\[\w+\])?)"
                r"\s*,\s*(\d+)\s*\)",
                line,
            )
            if call is None:
                continue
            buf, reserve = call.group(1), int(call.group(2))
            appended = None
            for follow in lines[index + 1 : index + 16]:
                fmt = re.search(
                    r"wsprintfW\(\s*\w+\s*,\s*L\"%ls(.*?)\"\s*,\s*" + buf, follow
                )
                if fmt is not None:
                    appended = fmt.group(1)
                    break
            self.assertIsNotNone(
                appended,
                f"line {index + 1}: nothing formats into {buf} after this call",
            )
            assert appended is not None
            tail = appended.replace("\\\\", "\\")
            # Widest substitutions: %d is a slot or a roll-over number, %ls is
            # the longest log stem in the file.
            stems = re.findall(r'L"(Virtual Villagers \d [^"]*?)"', text)
            widest_stem = max((len(s) for s in stems), default=0)
            size = (
                len(re.sub(r"%d|%ls", "", tail))
                + tail.count("%d") * WIDEST_LOG_NUMBER
                + tail.count("%ls") * widest_stem
                + 1  # NUL
            )
            with self.subTest(line=index + 1, tail=tail):
                self.assertGreaterEqual(
                    reserve,
                    size,
                    f"reserve {reserve} does not cover an append of {size}: "
                    f"{tail!r} (widest stem {widest_stem})",
                )
            checked += 1
        self.assertGreaterEqual(
            checked, 3, "found fewer subfolder call sites than expected"
        )

    def test_the_legacy_helper_reserves_for_its_callers(self) -> None:
        text = source()
        self.assertIn(
            "vv_save_folder_w(root, (int)wcslen(sub) + 1 + 64)",
            text,
            "legacy_subfolder_w no longer reserves for its caller's append",
        )
        # Its callers append the same tails the current-folder calls do.
        for tail in (
            "\\Village Statistics - Save %d.txt",
            "\\Village Population %d.txt",
        ):
            size = len(tail.replace("%d", "5")) + 1
            with self.subTest(tail=tail):
                self.assertGreaterEqual(64, size, f"{tail!r} needs {size}")


if __name__ == "__main__":
    unittest.main()
