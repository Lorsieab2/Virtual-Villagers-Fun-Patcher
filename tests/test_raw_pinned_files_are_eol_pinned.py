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
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CRLF = bytes((13, 10))
LF = bytes((10,))
CR = bytes((13,))
BOM = bytes((0xEF, 0xBB, 0xBF))

# Where a raw whole-file hash can be written down. Not just Python: two of the
# CRLF-pinned files below are pinned inside SIBLING JSON MANIFESTS, which is
# why every sweep restricted to scripts/ and src/ missed them.
PIN_GLOBS = ("scripts/**/*.py", "src/**/*.py", "tests/**/*.py", "data/**/*.json")

# Files whose pin is recorded against their CRLF bytes, where a `text eol=lf`
# rule would force LF and break the pin permanently.
#
# EMPTY, and that is the point. Four files were listed here:
#
#   data/candidates/vv2_individual_grant_running_binding.json
#   data/candidates/vv4_full_mastery_all_candidate.json
#   data/native_evidence/vv1_vv2_native_query_manifest.json
#   data/native_evidence_queries.json
#
# Their pins were minted on a Windows autocrlf=true clone, so the committed LF
# blobs never satisfied them and `validate_authorized_analyzer_workflow.py`
# failed its sha256 assertions on every LF checkout. All four have been
# repinned against their LF bytes and given rules, so the exception is gone.
#
# The set stays as a mechanism rather than being deleted: a future pin minted
# on a CRLF clone lands here, with the same requirement that it be repinned
# rather than silently exempted. The expiry test below refuses an entry that no
# longer exhibits the defect, so this cannot quietly become a dumping ground.
KNOWN_UNPINNED_CRLF_DEFECTS: set[str] = set()


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


def _pin_corpus() -> dict[str, str]:
    """Every file that could record a pin, keyed by repo-relative path.

    Keyed rather than concatenated so a file's own digest -- which trivially
    appears in itself for a self-describing manifest -- can be excluded.
    """
    corpus = {}
    for pattern in PIN_GLOBS:
        for path in ROOT.glob(pattern):
            try:
                corpus[path.relative_to(ROOT).as_posix()] = path.read_text(
                    encoding="utf-8", errors="ignore"
                )
            except OSError:
                continue
    return corpus


def _code_text() -> str:
    return "".join(_pin_corpus().values())


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
    return sorted(pinned_digests_by_path())


def pinned_digests_by_path() -> dict[str, set[str]]:
    """Each raw-pinned file mapped to the digests recorded FOR IT.

    Keeping the pin-to-path relationship is the whole point, and its absence
    was a real hole Codex found on #247: a check that asks only "do these bytes
    appear as some pin?" passes for a file holding a DIFFERENT pinned file's
    contents. Reproduced by copying
    `data/candidates/vv2_full_mastery_all_candidate.json` over
    `data/native_evidence_queries.json` -- all five tests passed while the
    latter no longer matched its own E6154939 pin.

    A file's allowed digests are those of its committed blob, in either
    encoding, that some other file records. Both encodings still matter: a pin
    minted on a Windows clone is written against CRLF bytes, which is exactly
    how `vv1_vv2_native_query_manifest.json` escaped two manual sweeps.
    """
    corpus = _pin_corpus()
    pinned: dict[str, set[str]] = {}
    for relative in _tracked_json():
        as_lf = _blob_lf(relative)
        if as_lf is None:
            continue
        others = [text for name, text in corpus.items() if name != relative]
        allowed = {
            digest
            for digest in (
                hashlib.sha256(candidate).hexdigest().upper()
                for candidate in (as_lf, as_lf.replace(LF, CRLF))
            )
            if any(digest in text for text in others)
        }
        if allowed:
            pinned[relative] = allowed
    return pinned


def _blob_lf(relative: str) -> bytes | None:
    """The committed blob, normalised to LF. None when unavailable.

    Reading the blob rather than the worktree is what makes this identical on
    every clone. A disk-based version reported different sets on an
    autocrlf=false clone and an autocrlf=true one, which is the same defect
    these rules exist to prevent -- in the guard itself.
    """
    result = subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout:
        return None
    return result.stdout.replace(CRLF, LF)


def _authenticated_digests() -> dict[str, str]:
    """Path -> source-text digest, from the repository's own registry.

    `data/source-text-authentication.json` exists precisely to bind a path to
    the digest of its canonicalised text, and documents the canonicalisation it
    uses. It is the reference that NAMES the file, so unlike a corpus search it
    stays correct when the file's contents change -- which is exactly when a
    digest match stops being evidence of anything.

    This addresses the hole Codex found on #247: with only the corpus search, a
    file committed with ANOTHER pinned file's exact bytes inherited the
    aggressor's digest and passed.

    Deliberately this registry, and not any "path"/"sha256" pair found in the
    tree. Several records legitimately name a live path with a DELIBERATELY
    historical digest -- two candidate maps do so for
    data/vv5_origins_feature.json, and
    ...fullscreen_owner_transition_evidence_gate.json names the fullscreen
    candidate under "status": "disabled-static-oracle-only". Treating those as
    live pins reports correct files as broken, which is worse than the hole it
    would close.

    Covers 18 of the 28 raw-pinned files today. It is a floor, not a ceiling:
    the assertion below is exact for what the registry names, and the corpus
    search still covers the rest.
    """
    registry = ROOT / "data" / "source-text-authentication.json"
    try:
        record = json.loads(registry.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError):
        return {}
    return {
        entry["path"].replace(chr(92), "/"): entry["sha256"].upper()
        for entry in record.get("artifacts", [])
        if isinstance(entry, dict)
        and isinstance(entry.get("path"), str)
        and isinstance(entry.get("sha256"), str)
    }


def eol_pinned_files() -> list[str]:
    """Tracked JSON carrying an explicit `text eol=lf` rule, by PATH.

    Deliberately independent of any digest. `raw_pinned_files()` identifies a
    file by its current hash matching a pin, which means a file that DRIFTS
    from its pin stops being recognised as pinned and silently leaves its own
    guard -- Codex found this on #247, and it reproduces: committing a change
    to `data/native_evidence_queries.json` without repinning leaves every
    assertion in this file green while the pin is broken.

    A rule, once written, records the relationship permanently, so drift
    cannot erase it.
    """
    return sorted(
        relative
        for relative in _tracked_json()
        if eol_attribute(relative) == "lf"
    )


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

    def test_worktree_bytes_actually_satisfy_their_pins(self):
        """The rules are a means; matching bytes are the end.

        Asserting only that a `text eol=lf` rule exists is not enough, and
        Codex found the gap on #247: an EXISTING core.autocrlf=true checkout
        that pulls the rules keeps its stale CRLF copies, because git does not
        rewrite files whose content did not change. In that state all four
        repinned files carried their old CRLF digests, `git status` was clean,
        and this file's other assertions all passed -- the rules were present,
        so nothing complained, while the pins were broken.

        `git checkout --force -- .` does NOT repair it; git still considers the
        files unchanged. The migration that works, applied to ONLY the paths
        this test names, is:

            git rm --cached -- <path>
            git checkout HEAD -- <path>

        Deliberately per-path. The whole-worktree form
        (`git rm --cached -r . && git reset --hard`) also repairs it, but
        `--hard` silently discards every uncommitted change in the checkout --
        reproduced by appending a line to README.md and running it, which
        removed the line with no warning. A migration note is read by someone
        whose pins are already failing, which is a bad moment to hand them a
        command that eats their work.

        This asserts the outcome instead of the mechanism, so the breakage is
        loud and the message says how to fix it.
        """
        corpus = _pin_corpus()
        allowed_by_path = pinned_digests_by_path()
        stale = []
        # Union, not the digest-derived set alone: the rule-derived set
        # survives content drift, while the digest-derived set catches a
        # raw-pinned file that has no rule yet (reported by the test above).
        candidates = set(allowed_by_path) | set(eol_pinned_files())
        # A file in the exception set is pinned to its CRLF bytes ON PURPOSE,
        # so hashing its LF worktree copy here would report it stale and make
        # the suite unpassable with any entry present -- which would render the
        # documented mechanism unusable in exactly the window it exists for.
        candidates -= KNOWN_UNPINNED_CRLF_DEFECTS
        for relative in sorted(candidates):
            path = ROOT / relative
            if not path.is_file():
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
            allowed = allowed_by_path.get(relative)
            if allowed is None:
                # Rule-derived only: no pin recorded anywhere for this path, so
                # fall back to asking whether the bytes are pinned at all.
                others = [t for name, t in corpus.items() if name != relative]
                if not any(digest in text for text in others):
                    stale.append(relative)
            elif digest not in allowed:
                stale.append(relative)
        self.assertEqual(
            stale,
            [],
            "these files are pinned by a raw sha256, but the bytes ON DISK do "
            "not match any pinned digest. Either the file drifted from its pin "
            "without being repinned, or -- more often on Windows -- an existing "
            "checkout kept stale CRLF copies when the eol rules arrived, which "
            "`git checkout --force` will NOT repair. Re-materialise ONLY these "
            "paths, so unrelated local work is untouched: for each, "
            "`git rm --cached -- <path>` then `git checkout HEAD -- <path>` "
            "-- but COMMIT OR STASH FIRST if you have edited any of these "
            "files, because that checkout overwrites the worktree copy and "
            "your edit goes with it. Do NOT use "
            "`git rm --cached -r . && git reset --hard`; the --hard resets the "
            "whole worktree and silently discards every uncommitted change: "
            f"{stale}",
        )

    def test_registered_artifacts_match_their_own_recorded_digest(self):
        """Path-anchored, so contents cannot vote on their own identity.

        The other worktree assertion asks whether a file's bytes appear as SOME
        pin, which Codex showed is weaker than it reads: commit one pinned
        file's exact bytes over another and the victim inherits the aggressor's
        digest and passes.

        data/source-text-authentication.json binds each path to the digest of
        its canonicalised text, so it can answer "does THIS file still match
        ITS pin" rather than "are these bytes pinned anywhere".
        """
        registered = _authenticated_digests()
        self.assertGreater(
            len(registered),
            10,
            "the source-text authentication registry looks empty or moved; "
            "this assertion would pass vacuously",
        )
        wrong = []
        for relative, expected in sorted(registered.items()):
            path = ROOT / relative
            if not path.is_file():
                continue
            raw = path.read_bytes()
            if raw.startswith(BOM):
                raw = raw[len(BOM):]
            canonical = raw.replace(CRLF, LF).replace(CR, LF)
            actual = hashlib.sha256(canonical).hexdigest().upper()
            if actual != expected:
                wrong.append(
                    f"{relative} is {actual[:12]}, registered as {expected[:12]}"
                )
        self.assertEqual(
            wrong,
            [],
            "these files no longer match the digest recorded for them BY NAME "
            "in data/source-text-authentication.json. Either the file changed "
            "without the registry being updated, or it now holds content that "
            f"belongs to a different file: {wrong}",
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
