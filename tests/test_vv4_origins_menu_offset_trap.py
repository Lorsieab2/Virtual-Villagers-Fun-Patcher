"""Keep VV4's wrong-layout menu function unreachable.

`native/vv4_origins_icons/vv4_origins_icons.c` is a copy of the VV1 companion
source with only some offsets corrected.  One function was missed:
`ShowOriginsUpgradeMenu` still reads villager fields at **VV1's** offsets --
age `+0x348`, skills `+0x3BC..0x3CC`, likes `+0x398`, dislikes `+0x3A8` --
against VV4's layout, where the verified fields live at `+0x1B8C`, `+0x1C5C`,
`+0x1E60` and `+0x1E6C`.  It also compares the skills against int `100`, where
VV4 stores Float32 and the companion's own `VV_MASTER_VALUE` is `0x42C80000`.

No player can reach it.  The shipped VV4 patch resolves a *different* export,
`ShowOriginsUpgradeMenuState`, which takes the dialog state from its caller and
reads no villager fields at all.  The wrong-layout function is exported at
ordinal 1 and nothing references it.

So this is a latent trap, not a live fault, and the working VV4 companion is
deliberately left alone rather than rebuilt to correct unreachable code.  These
tests make sure it stays that way: the moment anything wires that export up, or
lets those VV1-valued reads spread into a function VV4 actually calls, this
fails and the offsets have to be fixed first.

See docs/mask-identity-safeguard.md ("Fields deliberately not adopted").
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPANION = ROOT / "native" / "vv4_origins_icons" / "vv4_origins_icons.c"

# The export that must stay unwired, and the one VV4 legitimately calls.
QUARANTINED_EXPORT = "ShowOriginsUpgradeMenu"
WIRED_EXPORT = "ShowOriginsUpgradeMenuState"

# Macros holding VV1's values in the VV4 companion.
VV1_VALUED_MACROS = (
    "VV_AGE_OFFSET",
    "VV_SKILL_FARMING_OFFSET",
    "VV_SKILL_BUILDING_OFFSET",
    "VV_SKILL_RESEARCH_OFFSET",
    "VV_SKILL_HEALING_OFFSET",
    "VV_SKILL_PARENTING_OFFSET",
    "VV_LIKES_OFFSET",
    "VV_DISLIKES_OFFSET",
)

# VV4's verified offsets, for the message when this test fires.
VV4_VERIFIED = {
    "age": 0x1B8C,
    "skills": 0x1C5C,
    "likes": 0x1E60,
    "dislikes": 0x1E6C,
}

VV4_GENERATORS = (
    "build_vv4_origins_feature.py",
    "build_vv4_full_mastery_candidate.py",
)


def _function_body(text: str, name: str) -> str:
    """Return the brace-matched body of `name`'s definition."""
    match = re.search(
        r"__declspec\(dllexport\)\s+int\s+__stdcall\s+" + re.escape(name)
        + r"\s*\([^)]*\)\s*\{",
        text,
    )
    if match is None:
        raise AssertionError(f"{name} not found in the VV4 companion")
    start = match.end() - 1
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise AssertionError(f"unbalanced braces in {name}")


class VV4OriginsMenuOffsetTrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = COMPANION.read_text(encoding="utf-8", errors="replace")

    def test_the_wrong_layout_reads_are_confined_to_the_unwired_export(self) -> None:
        """Those VV1-valued reads may exist only where nothing calls them."""
        quarantined = _function_body(self.source, QUARANTINED_EXPORT)

        # Every read of the form `villager + <macro>` in the whole file.
        pattern = re.compile(
            r"\+\s*(" + "|".join(re.escape(m) for m in VV1_VALUED_MACROS) + r")\b"
        )
        all_reads = pattern.findall(self.source)
        quarantined_reads = pattern.findall(quarantined)

        self.assertTrue(all_reads, "the VV1-valued reads vanished; update this test")
        self.assertEqual(
            len(all_reads), len(quarantined_reads),
            "VV1-valued offset reads escaped ShowOriginsUpgradeMenu into code VV4 "
            "may actually call. Fix them to VV4's verified layout first: "
            + ", ".join(f"{k} +0x{v:X}" for k, v in VV4_VERIFIED.items()),
        )

    def test_the_wrong_layout_export_is_never_wired(self) -> None:
        """VV4 must keep resolving the State export, which reads no records."""
        for name in VV4_GENERATORS:
            path = ROOT / "scripts" / name
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            # The wired name has the quarantined one as a prefix, so match on
            # the terminating quote or NUL rather than a bare substring.
            hits = re.findall(
                re.escape(QUARANTINED_EXPORT) + r'(?:\\0)?["\']', text
            )
            with self.subTest(generator=name):
                self.assertEqual(
                    hits, [],
                    f"{name} resolves {QUARANTINED_EXPORT}, which reads villager "
                    f"fields at VV1 offsets. Correct those offsets before wiring it.",
                )

    def test_vv4_still_wires_the_record_free_state_export(self) -> None:
        """Guards the other direction: if VV4 stopped using the State export,
        the test above would pass for the wrong reason."""
        generator = ROOT / "scripts" / "build_vv4_origins_feature.py"
        text = generator.read_text(encoding="utf-8", errors="replace")
        self.assertIn(
            f'"{WIRED_EXPORT}"', text,
            "VV4 no longer wires the record-free State export; re-check which "
            "export now builds the Details dialog state",
        )

    def test_the_state_export_reads_no_villager_fields(self) -> None:
        """The reason the trap is only latent: this one takes the state in."""
        body = _function_body(self.source, WIRED_EXPORT)
        # `villager_menu` is an int flag, not a record, so the property to
        # assert is that nothing here DEREFERENCES a record.
        self.assertNotIn(
            "*(", body,
            f"{WIRED_EXPORT} now dereferences memory; it can no longer be "
            "assumed free of the VV1-offset problem",
        )
        for macro in VV1_VALUED_MACROS:
            with self.subTest(macro=macro):
                self.assertNotIn(macro, body)


if __name__ == "__main__":
    unittest.main()
