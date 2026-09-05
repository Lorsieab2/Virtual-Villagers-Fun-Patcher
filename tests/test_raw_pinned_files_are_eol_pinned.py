"""A file pinned by its raw sha256 must also be pinned to LF line endings.

Several generators authenticate a data file by hashing its **whole bytes** and
comparing against a constant in `scripts/` or `src/` -- `ACTIVE_SHA256` in
`scripts/build_vv5_task9_native_actions.py` is the clearest example. A raw hash
covers line endings, so without a `text eol=lf` attribute the file's identity
follows whatever `core.autocrlf` the contributor happens to have.

That is not hypothetical. `data/vv5_origins_feature.json` carries exactly this
rule today, and `.gitattributes` records why in its own comment: a Windows
checkout and an LF checkout "settle to different chains and the generator's
identity check fails on whichever one did not produce the pin". Measured on the
committed blob:

    LF   sha256 6726AFB4...  == ACTIVE_SHA256   -> the build proceeds
    CRLF sha256 1983C284...  != ACTIVE_SHA256   -> "pinned active VV5 Origins
                                                    source drift", build stops

The failure is nastier than a line-ending complaint: it presents as a plausible
identity mismatch, which invites someone to "correct" the pin to the CRLF value
and bake the corruption in permanently.

The protection was applied to one file at a time as each was discovered, so 25
of the 28 raw-pinned files were still exposed. This test closes the class: the
set is derived mechanically rather than listed by hand, so a newly added pin is
covered the moment it appears instead of waiting to be found the painful way.
"""

import hashlib
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CRLF = bytes((13, 10))
LF = bytes((10,))

# Where a raw whole-file hash would be written down.
CODE_DIRECTORIES = ("scripts", "src")

# Two files are pinned against their CRLF bytes, so a `text eol=lf` rule would
# force them to LF and break those pins permanently. Both are pre-existing
# defects, NOT things this rule set fixes, and both feed the same validator:
#
#   data/native_evidence/vv1_vv2_native_query_manifest.json
#       Its CRLF digest A53C6D01... is pinned in TWO places --
#       `MANIFEST_SHA` in scripts/validate_authorized_analyzer_workflow.py and
#       data/authorized_analyzer_workflow.json. The committed blob is LF and
#       hashes to B79E1613..., which is pinned nowhere, so that validator
#       already fails on any LF checkout -- reproduced by running it directly,
#       where it raises AssertionError at the sha256 comparison. Nothing in the
#       suite executes it, which is why the failure has gone unnoticed.
#       Repinning it against LF is a separate change with its own verification;
#       folding a content change into a line-endings rule set would bury it.
#
#   data/native_evidence_queries.json
#       Same defect, same validator. Its CRLF digest FED6AE17... is pinned as
#       `QUERY_PLAN_SHA` and appears three times in
#       data/authorized_analyzer_workflow.json as the `query_plan` sha256. The
#       LF form E6154939... is pinned nowhere.
#
# A sweep of every tracked JSON found exactly these two pinned only under CRLF.
#
# The exception is the standing record of what is still broken. Removing this
# path without repinning the file re-breaks it, which the expiry test below
# guards against.
KNOWN_UNPINNED_CRLF_DEFECTS = {
    "data/native_evidence/vv1_vv2_native_query_manifest.json",
    "data/native_evidence_queries.json",
}


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout


def _tracked_json() -> list[str]:
    return [
        line
        for line in _git("ls-files").splitlines()
        if line.endswith(".json")
    ]


def _code_text() -> str:
    parts = []
    for directory in CODE_DIRECTORIES:
        for path in (ROOT / directory).rglob("*.py"):
            parts.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "".join(parts)


def raw_pinned_files() -> list[str]:
    """Tracked JSON whose sha256 -- as LF or as CRLF -- appears in code.

    Both encodings are checked, and that matters. Hashing only the worktree
    copy makes the result depend on the reader's `core.autocrlf`: the other
    session's CRLF clone flagged a file this one did not, purely because the
    on-disk bytes differed. Hashing only the LF form misses a pin that was
    minted on a Windows clone -- which is exactly how
    `vv1_vv2_native_query_manifest.json` escaped two manual sweeps.

    Testing both makes the set identical on every clone, and catches a file
    whose pin was recorded against either encoding.
    """
    code = _code_text()
    found = []
    for relative in _tracked_json():
        path = ROOT / relative
        if not path.is_file():
            continue
        raw = path.read_bytes()
        as_lf = raw.replace(CRLF, LF)
        for candidate in (as_lf, as_lf.replace(LF, CRLF)):
            if hashlib.sha256(candidate).hexdigest().upper() in code:
                found.append(relative)
                break
    return sorted(found)


def eol_attribute(relative: str) -> str:
    """The `eol` attribute git reports for a path."""
    out = _git("check-attr", "eol", "--", relative)
    # "<path>: eol: lf"
    return out.strip().rsplit(":", 1)[-1].strip() if out.strip() else "unspecified"


class RawPinnedFilesAreEolPinnedTests(unittest.TestCase):
    def test_the_detector_finds_the_known_pinned_files(self):
        """Guard the guard.

        If the search stopped matching -- a renamed constant, a moved
        directory -- every assertion below would pass vacuously against an
        empty set. Pin a file known to be raw-hashed.
        """
        pinned = raw_pinned_files()
        self.assertIn(
            "data/vv5_origins_feature.json",
            pinned,
            "the raw-hash detector no longer finds the VV5 Origins payload, "
            "whose ACTIVE_SHA256 pin is the reason this test exists",
        )
        self.assertGreater(
            len(pinned), 1, "only one raw-pinned file found; the search looks broken"
        )

    def test_every_raw_pinned_file_is_pinned_to_lf(self):
        """The invariant: raw hash implies an explicit LF rule.

        A file whose identity is its exact bytes cannot be allowed to change
        bytes on checkout. `.gitattributes` is the only thing that makes that
        independent of the contributor's `core.autocrlf`.
        """
        missing = [
            relative
            for relative in raw_pinned_files()
            if eol_attribute(relative) != "lf"
            and relative not in KNOWN_UNPINNED_CRLF_DEFECTS
        ]
        self.assertEqual(
            missing,
            [],
            "these files are pinned by a raw sha256 but carry no `text eol=lf` "
            "rule, so their identity depends on the contributor's "
            f"core.autocrlf setting: {missing}",
        )

    def test_the_known_defects_are_still_defects(self):
        """An exception must not outlive the problem it excuses.

        `KNOWN_UNPINNED_CRLF_DEFECTS` exists because those files are pinned to
        their CRLF bytes, so an `eol=lf` rule would break them. If someone
        repins one against LF, the exception becomes a hole that silently
        exempts a file the rule should now cover -- so require each entry to
        still exhibit the defect, and fail asking for it to be removed.
        """
        code = _code_text()
        for relative in sorted(KNOWN_UNPINNED_CRLF_DEFECTS):
            path = ROOT / relative
            if not path.is_file():
                continue
            with self.subTest(path=relative):
                raw = path.read_bytes()
                as_lf = hashlib.sha256(
                    raw.replace(CRLF, LF)
                ).hexdigest().upper()
                # assertFalse on a membership test, not assertNotIn: the
                # latter prints the entire concatenated source corpus on
                # failure, which buries the message in megabytes of output.
                self.assertFalse(
                    as_lf in code,
                    f"{relative} now matches a pin on its LF bytes ({as_lf}), "
                    "so the reason for excepting it is gone: give it a "
                    "`text eol=lf` rule and drop it from "
                    "KNOWN_UNPINNED_CRLF_DEFECTS",
                )

    def test_a_crlf_checkout_would_break_a_pinned_hash(self):
        """Anti-vacuity: prove the rule is load-bearing, not decorative.

        If line endings did not affect these hashes the assertion above would
        be busywork. Re-encoding the VV5 payload as CRLF must change its digest
        away from the pinned value.
        """
        path = ROOT / "data/vv5_origins_feature.json"
        if not path.is_file():
            self.skipTest("VV5 Origins payload unavailable")
        raw = path.read_bytes()
        if b"\r\n" in raw:
            self.skipTest("worktree copy is already CRLF; eol rule not applied")
        as_lf = hashlib.sha256(raw).hexdigest().upper()
        as_crlf = hashlib.sha256(raw.replace(b"\n", b"\r\n")).hexdigest().upper()
        self.assertNotEqual(
            as_lf,
            as_crlf,
            "line endings do not affect this file's hash, so the eol rules "
            "protect nothing and this test is inert",
        )
        self.assertIn(
            as_lf,
            _code_text(),
            "the LF digest is no longer the value pinned in code; either the "
            "payload changed without repinning, or the worktree copy is not LF",
        )


if __name__ == "__main__":
    unittest.main()
