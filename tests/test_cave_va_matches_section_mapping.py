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

# Any module-level integer constant, so a VA expression may reference whatever
# it likes.  Collecting only the _FILE_OFFSET/_VA names silently skipped every
# VA written as `IMAGE_BASE + ...` -- which is exactly the broken form, so the
# check passed straight over the one case it exists to catch.
ASSIGNMENT = re.compile(r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<expr>[^\n#]+)", re.M)


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
    found: dict[str, int] = {}
    exprs: dict[str, str] = {}
    for match in ASSIGNMENT.finditer(source):
        expr = match.group("expr").strip()
        try:
            value = eval(expr, {"__builtins__": {}}, dict(found))
        except Exception:
            continue
        if isinstance(value, int) and not isinstance(value, bool):
            found[match.group("name")] = value
            exprs[match.group("name")] = expr
    return found, exprs


# `NAME_VA = OTHER_VA` is an alias, not a claim about where NAME_FILE_OFFSET
# maps.  The Cure/village-wide stubs do this deliberately: HEAL_CAVE_FILE_OFFSET
# is a five-byte jump slot whose HEAL_CAVE_VA names the certified helper it
# redirects TO.  Pairing them by name would report three healthy builds as
# broken.
ALIAS = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*_VA$")


class CaveVaMatchesSectionMappingTests(unittest.TestCase):
    def test_declared_cave_vas_match_the_pe_section_mapping(self) -> None:
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
        # Named explicitly so a parsing regression cannot quietly drop the very
        # pair that shipped a crash.
        self.assertIn("vv4:PENDING_ROWS_FILE_OFFSET", pairs_seen)


if __name__ == "__main__":
    unittest.main()
