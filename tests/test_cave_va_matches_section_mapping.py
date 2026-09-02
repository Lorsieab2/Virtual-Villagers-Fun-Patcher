"""Every declared cave VA must match where the PE actually maps its bytes.

Twice now a helper has been assembled at ``IMAGE_BASE + raw_file_offset`` in a
game whose section is not identity-mapped, so the code landed in the file
correctly while the call site jumped somewhere else entirely.  VV4's ``.shr``
maps raw ``0xCC000`` to VA ``0x728000``; a cave declared at
``IMAGE_BASE + 0xCCC20`` therefore pointed at ``0x4CCC20``, and v1.34.29 shipped
a Tech-screen crash whose dump faulted at ``0x004CCC21``.

Disassembling the cave does not catch this: the bytes are right, only the
address the rest of the build believes is wrong.  So this reads the section
table out of each generated executable and checks every
``<NAME>_FILE_OFFSET`` / ``<NAME>_VA`` pair the generator declares.
"""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GAMES = {
    "vv1": ROOT / "research/vv1-origins-apk/Virtual Villagers - A New Home - Origins Feature Research.exe",
    "vv2": ROOT / "research/vv2-origins/Virtual Villagers - The Lost Children - Origins Research.exe",
    "vv3": ROOT / "research/vv3-origins/Virtual Villagers - The Secret City - Origins Research.exe",
    "vv4": ROOT / "research/vv4-origins/Virtual Villagers - The Tree of Life - Origins Research.exe",
    "vv5": ROOT / "research/vv5-origins/Virtual Villagers - New Believers - Origins Research.exe",
}

# Deliberate `NAME_VA = OTHER_VA` aliases, which say nothing about where
# NAME_FILE_OFFSET maps.  The Cure/village-wide stubs use this: the offset is a
# five-byte jump slot and the VA names the helper it redirects TO.
ALIAS = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*_VA$")


def sections(data: bytes):
    pe = int.from_bytes(data[0x3C:0x40], "little")
    count = int.from_bytes(data[pe + 6 : pe + 8], "little")
    opt = int.from_bytes(data[pe + 20 : pe + 22], "little")
    base = int.from_bytes(data[pe + 24 + 28 : pe + 24 + 32], "little")
    table = pe + 24 + opt
    out = []
    for index in range(count):
        entry = table + index * 40
        out.append((
            data[entry : entry + 8].rstrip(b"\0").decode("ascii", "replace"),
            base + int.from_bytes(data[entry + 12 : entry + 16], "little"),
            int.from_bytes(data[entry + 20 : entry + 24], "little"),
            int.from_bytes(data[entry + 16 : entry + 20], "little"),
        ))
    return out


def va_for(secs, offset: int):
    for name, va, raw, raw_size in secs:
        if raw <= offset < raw + raw_size:
            return name, va + (offset - raw)
    return None, None


def constants(source: str) -> tuple[dict[str, int], dict[str, str]]:
    """Every module-level integer constant, with the text it was written as.

    Parsed with `ast` rather than matched line by line.  A line-based regex
    stops at the first newline, so a parenthesized multiline declaration --
    which is exactly how VV1 and VV2 write theirs:

        PENDING_ROWS_VA = IMAGE_BASE + SHR_RVA + (
            PENDING_ROWS_FILE_OFFSET - SHR_FILE_OFFSET
        )

    -- failed to evaluate and was dropped without a word.  That silently
    excluded 31 VV1 and 11 VV2 pairs while the aggregate count still passed on
    the other games, so the check protected far less than it claimed to.
    """
    found: dict[str, int] = {}
    exprs: dict[str, str] = {}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return found, exprs
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            value = eval(                                   # noqa: S307
                compile(ast.Expression(node.value), "<const>", "eval"),
                {"__builtins__": {}},
                dict(found),
            )
        except Exception:
            continue
        if isinstance(value, int) and not isinstance(value, bool):
            found[target.id] = value
            exprs[target.id] = ast.unparse(node.value).strip()
    return found, exprs


class CaveVaMatchesSectionMappingTests(unittest.TestCase):
    def test_declared_cave_vas_match_the_pe_section_mapping(self) -> None:
        # research/ is not committed, so on a clean checkout none of these
        # executables exist. Skip like the other fixture-dependent tests rather
        # than failing the whole suite on a machine that simply does not have
        # the private builds.
        available = [g for g, p in GAMES.items() if p.is_file()]
        if not available:
            self.skipTest("no generated executables present (research/ is not committed)")
        checked = 0
        pairs_seen: set[str] = set()
        for game, exe_path in GAMES.items():
            script = ROOT / f"scripts/build_{game}_origins_feature.py"
            if not script.is_file() or not exe_path.is_file():
                continue
            values, exprs = constants(script.read_text(encoding="utf-8"))
            secs = sections(exe_path.read_bytes())
            for key, offset in sorted(values.items()):
                if not key.endswith("_FILE_OFFSET"):
                    continue
                va_name = key[: -len("_FILE_OFFSET")] + "_VA"
                va = values.get(va_name)
                if va is None or ALIAS.match(exprs.get(va_name, "")):
                    continue
                section, expected = va_for(secs, offset)
                if expected is None:
                    continue          # data outside any raw section
                pairs_seen.add(f"{game}:{key}")
                with self.subTest(game=game, cave=key):
                    self.assertEqual(
                        va, expected,
                        f"{game} {key}={offset:#x} sits in {section} at {expected:#x}, "
                        f"but the generator declares its VA as {va:#x}. A call to "
                        f"{va:#x} would execute whatever happens to live there.",
                    )
                checked += 1
        self.assertGreater(checked, 10, "no cave VA pairs were checked")
        # Per game, not just in aggregate: a parsing regression that dropped
        # every VV1 pair would otherwise still pass on the strength of the
        # other four, which is how the multiline declarations went unchecked.
        for game in available:
            with self.subTest(game=game):
                self.assertTrue(
                    any(k.startswith(f"{game}:") for k in pairs_seen),
                    f"{game} contributed no cave VA pairs at all",
                )
        # Named explicitly so a parsing regression cannot quietly drop the very
        # pair that shipped a crash.
        if "vv4" in available:
            self.assertIn("vv4:PENDING_ROWS_FILE_OFFSET", pairs_seen)


if __name__ == "__main__":
    unittest.main()
