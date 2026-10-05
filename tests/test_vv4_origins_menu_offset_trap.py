"""Keep VV4's wrong-layout menu function gone.

`native/vv4_origins_icons/vv4_origins_icons.c` began as a copy of the VV1
companion source with only some offsets corrected.  One function was missed:
`ShowOriginsUpgradeMenu` read villager fields at **VV1's** offsets -- age
`+0x348`, skills `+0x3BC..0x3CC`, likes `+0x398`, dislikes `+0x3A8` -- against
VV4's layout, where the verified fields live at `+0x1B8C`, `+0x1C5C`, `+0x1E60`
and `+0x1E6C`.

No player could reach it: the shipped VV4 patch resolves a *different* export,
`ShowOriginsUpgradeMenuState`, which takes the dialog state from its caller and
reads no villager fields.  v1.35.58 removed the unreachable export together
with the VV1-valued macros only it used.  These tests keep it that way: the
function and the macros must not come back, no VV4 generator may resolve that
name, and the export VV4 does call must stay free of record reads.

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
        r"^int\s+__stdcall\s+" + re.escape(name)
        + r"\s*\([^)]*\)\s*\{",
        text,
        re.M,
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

    def test_the_wrong_layout_function_and_its_vv1_macros_are_gone(self) -> None:
        """Nothing in VV4 called them, so they were removed; keep them out."""
        self.assertIsNone(
            re.search(r"__stdcall\s+" + re.escape(QUARANTINED_EXPORT) + r"\s*\(", self.source),
            f"{QUARANTINED_EXPORT} is back in the VV4 companion; it read VV1 offsets. "
            "Use VV4's verified layout: "
            + ", ".join(f"{k} +0x{v:X}" for k, v in VV4_VERIFIED.items()),
        )
        for macro in VV1_VALUED_MACROS:
            with self.subTest(macro=macro):
                self.assertIsNone(re.search(r"\b" + macro + r"\b", self.source))

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
