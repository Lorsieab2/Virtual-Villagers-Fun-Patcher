"""No shipped C string may contain an invalid escape.

MSVC warns (C4129) and then DROPS the backslash. A literal written with one
backslash before an ordinary letter loses it entirely in the binary: the path
`"%ls" BS "Village History 1.txt"` becomes `"%lsVillage History 1.txt"`, which
can never match anything on disk. The build still succeeds, and every test
that reads the SOURCE still passes, because the source reads correctly at a
glance -- only the shipped binary is wrong.

That is not hypothetical. It shipped in the Village History migration: the
upgrade probe targeted a concatenated nonsense path, always missed, and every
player upgrading had their permanent timeline silently split in two. Review
found it by reading the DLL, not the source. The same slip was introduced four
separate times while editing these files in one session.

Comments are blanked out first. A backslash in a comment is prose -- a header
drawing a path for a reader -- and flagging those buries the real findings.
"""
from __future__ import annotations

import pathlib
import re
import unittest

NL = chr(10)
BS = chr(92)
QUOTE = chr(34)

# Escapes C actually defines; octal digits and \x../\u.... handled separately.
VALID = set("abfnrtv'" + QUOTE + "?" + BS)
LITERAL = re.compile(r'"(?:[^"\\\n]|\\.)*"')

ROOT_NATIVE = pathlib.Path(__file__).resolve().parents[1] / "native"


def strip_comments(text: str) -> str:
    """Blank out comments, preserving line numbers and line breaks."""
    out: list[str] = []
    i = 0
    n = len(text)
    in_block = in_line = in_str = in_chr = False
    while i < n:
        c = text[i]
        two = text[i : i + 2]
        if in_block:
            out.append(NL if c == NL else " ")
            if two == "*/":
                out.append(" ")
                i += 2
                in_block = False
                continue
            i += 1
            continue
        if in_line:
            if c == NL:
                out.append(NL)
                in_line = False
            else:
                out.append(" ")
            i += 1
            continue
        if in_str or in_chr:
            out.append(c)
            if c == BS and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if (in_str and c == QUOTE) or (in_chr and c == "'"):
                in_str = in_chr = False
            i += 1
            continue
        if two == "/*":
            out.append("  ")
            i += 2
            in_block = True
            continue
        if two == "//":
            out.append("  ")
            i += 2
            in_line = True
            continue
        if c == QUOTE:
            in_str = True
        elif c == "'":
            in_chr = True
        out.append(c)
        i += 1
    return "".join(out)


def bad_escapes_in(literal: str) -> list[str]:
    """Every escape in `literal` that C does not define."""
    found: list[str] = []
    index = 0
    while index < len(literal):
        if literal[index] != BS:
            index += 1
            continue
        if index + 1 >= len(literal):
            break
        nxt = literal[index + 1]
        if not (nxt in VALID or nxt.isdigit() or nxt in "xu"):
            found.append(nxt)
        index += 2
    return found


def invalid_escapes() -> list[tuple[str, int, str, str]]:
    findings: list[tuple[str, int, str, str]] = []
    for path in sorted(ROOT_NATIVE.rglob("*.c")):
        raw = path.read_text(encoding="utf-8", errors="replace")
        raw_lines = raw.splitlines()
        for number, line in enumerate(strip_comments(raw).splitlines(), 1):
            for literal in LITERAL.findall(line):
                for char in bad_escapes_in(literal):
                    findings.append(
                        (
                            path.name,
                            number,
                            char,
                            raw_lines[number - 1].strip()[:110]
                            if number - 1 < len(raw_lines)
                            else "",
                        )
                    )
    return findings


class NoInvalidCEscapesTests(unittest.TestCase):
    def test_the_scanner_sees_the_sources(self) -> None:
        """Guard the guard: an empty sweep would pass vacuously."""
        self.assertGreater(
            len(list(ROOT_NATIVE.rglob("*.c"))), 10, "native sources not found"
        )

    def test_the_scanner_strips_comments(self) -> None:
        """A path drawn in a comment is prose, not an escape."""
        sample = "/* <docs>" + BS + "LDW" + BS + "x */" + NL + 'char *p = "ok";' + NL
        stripped = strip_comments(sample)
        self.assertNotIn("LDW", stripped)
        self.assertIn('"ok"', stripped)
        self.assertEqual(sample.count(NL), stripped.count(NL))

    def test_the_scanner_catches_a_dropped_separator(self) -> None:
        """The exact shape that shipped: one backslash before a letter."""
        sample = 'x(L"%ls' + BS + 'Village History 1.txt");'
        literal = LITERAL.findall(sample)[0]
        self.assertEqual(bad_escapes_in(literal), ["V"])

    def test_a_correct_separator_is_not_flagged(self) -> None:
        """And the fixed form must be accepted, or the guard is useless."""
        sample = 'x(L"%ls' + BS + BS + 'Village History 1.txt");'
        literal = LITERAL.findall(sample)[0]
        self.assertEqual(bad_escapes_in(literal), [])

    def test_the_shipped_population_dll_has_its_separators(self) -> None:
        """Read the BINARY, which is how review found this in the first place.

        The source guard above would have caught it, but it did not exist
        when the defect shipped -- and the companions ship prebuilt, so a
        corrected .c file proves nothing until the DLL is rebuilt.
        """
        dll = (
            pathlib.Path(__file__).resolve().parents[1]
            / "assets" / "population" / "VVFP Population Export.dll"
        )
        self.assertTrue(dll.is_file(), dll)
        data = dll.read_bytes()
        wanted = "%ls" + BS + "Village History 1.txt"
        broken = "%lsVillage History 1.txt"
        self.assertIn(
            wanted.encode("utf-16-le"),
            data,
            "the shipped DLL has no separator in the history migration path",
        )
        self.assertNotIn(
            broken.encode("utf-16-le"),
            data,
            "the shipped DLL still holds the concatenated path, so every "
            "upgrade probe misses and the timeline splits",
        )

    def test_no_shipped_source_has_an_invalid_escape(self) -> None:
        findings = invalid_escapes()
        detail = "; ".join(
            f"{name}:{line} {BS}{char}" for name, line, char, _ in findings
        )
        self.assertEqual(
            findings,
            [],
            "MSVC drops these backslashes, so the shipped binary holds a path "
            "that can never match: " + detail,
        )


if __name__ == "__main__":
    unittest.main()
