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
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CRLF = bytes((13, 10))
LF = bytes((10,))
CR = bytes((13,))
BOM = bytes((0xEF, 0xBB, 0xBF))

# The path->digest registry. Excluded when looking for corroboration, because
# the registry agreeing with itself proves nothing about the pin the patcher
# actually enforces.
REGISTRY_PATH = "data/source-text-authentication.json"

# Artifacts the registry is the SOLE record for. Verified with `git grep`: no
# other file in the repository holds their digest, so there is nothing for the
# registry to agree with and demanding corroboration would condemn correct
# files. Kept as an explicit, checked list rather than a silent skip -- the
# expiry assertion below fails if one of these gains a second record, so the
# exemption cannot outlive its reason.
REGISTRY_IS_SOLE_PIN = {
    "data/candidates/vv3_running_candidate_map.json",
    "data/candidates/vv4_full_heal_cure_all_candidate.json",
    "data/candidates/vv4_full_heal_cure_all_candidate_map.json",
}

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


def _recorded_digests_for(relative: str, corpus: dict[str, str]) -> set[str]:
    """Digests some OTHER file records for this path, independent of its bytes.

    Reads the DECLARED binding, never a derived one. Earlier revisions looked
    for the path in another file and took the digests written near it -- the
    enclosing JSON object, or the enclosing blank-line-delimited statement
    group in Python. Both are layout heuristics, and layout is not a binding:

      * `src/vv_fun_patcher.py` mentions `builds.json` at line 36 inside a
        block with no blank line until line 314, so the "bounded" window spans
        282 lines and captures 44 unrelated SHA-256 values. Measured on
        4bba6b0b -- that is a global search wearing a smaller hat, and it is
        what made `data/builds.json` look pinned when its digest is recorded
        nowhere (Codex P2, this PR).
      * The same file keeps the VV2 candidate path in one constant and its
        digest in another, so the object-scoped form found nothing at all --
        28 of 36 artifacts returned empty (Codex P1, this PR).

    The repository already maintains the binding this predicate needs, in
    `data/source-text-authentication.json`: one row per path, naming its
    digest. Reading it removes the inference entirely. A path the registry does
    not name has no recorded digest, which is the correct answer rather than a
    guess assembled from whatever happened to sit nearby.

    `corpus` is retained in the signature because callers pass it and the
    return contract is unchanged; the answer no longer depends on it.
    """
    del corpus  # answer comes from the declared registry, not a text search
    declared = _authenticated_digests().get(relative)
    return {declared} if declared else set()


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
    registry = ROOT / REGISTRY_PATH
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


def _committed_registry_paths() -> set[str]:
    """Paths the registry names at HEAD, independent of the working tree.

    Deliberately read from the committed blob. A guard whose inventory comes
    from the working tree can be switched off by editing the working tree,
    which is the shape of every erasure Codex found on this PR.
    """
    blob = _git("show", f"HEAD:{REGISTRY_PATH}")
    if not blob.strip():
        return set()
    try:
        record = json.loads(blob)
    except ValueError:
        return set()
    return {
        entry["path"].replace(chr(92), "/")
        for entry in record.get("artifacts", [])
        if isinstance(entry, dict) and isinstance(entry.get("path"), str)
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
        declared_by_path = _authenticated_digests()
        stale = []
        uncorroborated = []
        # Union, not the digest-derived set alone: the rule-derived set
        # survives content drift, while the digest-derived set catches a
        # raw-pinned file that has no rule yet (reported by the test above).
        # Digest-pinned paths only. Including every file with an eol=lf rule
        # made an ordinary line-ending rule imply a SHA-256 pin: adding
        # `/data/builds.json text eol=lf` for plain cross-platform text
        # normalisation reported that file as stale, because nothing
        # authenticates it and nothing should have to. Codex found that on
        # #258, and it would have blocked using eol=lf for its actual purpose.
        #
        # The rule-derived set is still unioned in, but restricted to files
        # something actually pins -- that is what keeps a file inside its own
        # guard after it drifts, which was the reason for adding it.
        # "Something pins it" must include what pinned it BEFORE this commit.
        # Testing only the current bytes and the current registry lets a single
        # commit that drifts the file AND deletes its registry row drop the
        # path from the set entirely -- both signals vanish together, and the
        # guard cannot report a file it is no longer looking at. Codex
        # reproduced that on #258 by appending whitespace and removing the row.
        #
        # The committed blob's own digests survive both edits, so they answer
        # "was this path ever authenticated" independently of what the working
        # tree currently says.
        # A digest recorded BESIDE the path is the evidence that survives both
        # edits: the file's bytes change and its registry row disappears, but
        # data/authorized_analyzer_workflow.json still binds this path to the
        # old digest, and scripts/validate_authorized_analyzer_workflow.py
        # still enforces it. Asking "was this path ever authenticated" has to
        # read that binding, not the file's own current or committed bytes --
        # both of which the drift replaces.
        # The candidate inventory is the COMMITTED registry, not the working
        # tree's. Every input the previous form intersected -- current bytes
        # (`raw_pinned_files`), the live registry row (`_authenticated_digests`),
        # and a proximity search (`historically_pinned`) -- is mutable by the
        # very commit the guard exists to catch: drift the file and delete its
        # row and all three signals vanish together, so the path leaves the set
        # and nothing reports it. Codex reproduced that twice on this PR, on
        # data/native_evidence_queries.json and on the VV2 candidate.
        #
        # HEAD's copy of the registry is not editable by the working tree, so a
        # row deleted in the index is still named here and the path stays under
        # guard. A row deleted in a COMMIT is caught by the coverage assertion
        # below, which requires the registry to name every eol-pinned path.
        committed = _committed_registry_paths()
        candidates = set(allowed_by_path) | (
            set(eol_pinned_files())
            & (
                set(_authenticated_digests())
                | set(raw_pinned_files())
                | committed
            )
        )
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
            # PATH-OWNED first, and for a raw-pinned file that is the only
            # answer accepted. The registry now names all 36 of them, so the
            # global corpus fallback below is reachable only for a file that
            # carries an eol rule without being raw-pinned at all.
            #
            # The fallback is what let a substitution pass: it asks whether the
            # bytes are pinned ANYWHERE, so a file committed with another
            # pinned file's content inherited the aggressor's digest. Codex
            # reproduced that on this PR twice, before and after the registry
            # was introduced, because the registry then covered only 18 of 36.
            registered = declared_by_path.get(relative)
            if registered is not None:
                if digest != registered:
                    stale.append(relative)
                    continue
                # The registry says the file is intact. Require the CONSUMER
                # to agree, or the registry can mask a broken production pin:
                # change a pinned file, update only its registry digest, and
                # every assertion here passes while the pin the patcher
                # actually enforces still names the old bytes. Codex
                # reproduced exactly that on 0ecbf576 by appending whitespace
                # to data/native_evidence_queries.json.
                #
                # Corroboration is deliberately sought OUTSIDE both the
                # artifact and the registry: a self-describing manifest
                # trivially contains its own digest, and the registry agreeing
                # with itself proves nothing.
                # Only files the corpus ALSO pins need to agree with it. Three
                # of the originally registered artifacts -- vv3_running_candidate_map,
                # vv4_full_heal_cure_all_candidate and its map -- are recorded
                # nowhere else, so for them the registry is the sole pin rather
                # than a second opinion, and demanding corroboration would
                # condemn correct files.
                #
                # What must not happen is the registry DISAGREEING with a pin
                # that exists: that is the masking case, where a file is
                # changed, the registry updated, and the consumer left naming
                # the old bytes.
                # Does ANY consumer hold this digest?
                #
                # Not "is it recorded near the path" -- proximity does not
                # survive the way pins are actually written. src/vv_fun_patcher.py
                # keeps data/candidates/vv2_full_mastery_all_candidate.json in
                # VV2_FULL_MASTERY_CANDIDATE_PATHS and its digest in a separate
                # VV2_FULL_MASTERY_MANIFEST_SHA256 constant, so a scan scoped to
                # the enclosing structure finds nothing. Codex measured the
                # damage: 28 of 36 registered artifacts had no digest found that
                # way, leaving the check inert for most of them.
                #
                # Presence is the property that actually matters. A registry-only
                # repin invents a digest NO consumer holds, so requiring the
                # registry value to appear somewhere outside the artifact and the
                # registry catches it without needing to know which constant
                # belongs to which path.
                # Corroboration must come from a consumer that NAMES this
                # path, not from any file that happens to hold the digest.
                #
                # Digest uniqueness in the registry is not enough, because the
                # registry is mutable: swap two artifacts' contents AND swap
                # their registry digests, and each digest still has exactly one
                # registry owner while each is found in the OTHER artifact's
                # consumer. Codex reproduced that on 5ed8196 -- 12 tests green
                # on a tree where two files had exchanged identities, with
                # VV2_FULL_MASTERY_MANIFEST_SHA256 and QUERY_PLAN_SHA still
                # authenticating the original mappings.
                #
                # A consumer that enforces a path's digest refers to that path,
                # so requiring the holder to mention the artifact by name binds
                # the corroboration to the path instead of to the value. This
                # is file-level, NOT the line-proximity rule rejected earlier:
                # proximity failed because layout is arbitrary, while "this
                # file talks about this artifact" is a property of the file.
                #
                # The sibling `<artifact>_map.json` counts as naming its
                # artifact. That pairing is a declared convention in this repo,
                # and it is how data/candidates/vv4_full_mastery_all_candidate
                # .json is legitimately corroborated -- its map records the
                # value as `feature_manifest_sha256` without spelling the
                # basename, and rejecting that would condemn a correct file.
                #
                # KNOWN LIMIT, stated rather than left to read as full cover.
                # That sibling map is itself unregistered and unpinned -- no
                # file in the tree records its digest -- so the one artifact
                # relying on this rule is corroborated more weakly than the
                # other 32, which are named by a consumer that enforces the
                # digest in code. Substituting it would take a two-file edit:
                # change the artifact and its registry row, and edit the map
                # to hold the new digest. Uniqueness would not object, because
                # the invented digest is still registered to exactly one path.
                #
                # Not closed here on purpose. The durable fix is to register
                # the map, or to have consumers read their digest from the
                # registry so there is one pin per path by construction. Both
                # are schema changes and belong in their own PR with the
                # owner's go-ahead, exactly like the limit already recorded in
                # this PR's description. Claiming the guard is tighter than it
                # is would repeat the mistake these findings were about.
                basename = relative.rsplit("/", 1)[-1]
                stem = basename[: -len(".json")] if basename.endswith(
                    ".json"
                ) else basename
                elsewhere = [
                    text
                    for name, text in corpus.items()
                    if name not in (relative, REGISTRY_PATH)
                    and (
                        basename in text
                        or name.rsplit("/", 1)[-1] == f"{stem}_map.json"
                    )
                ]
                # A digest ANOTHER registered path owns cannot also be this
                # path's. That is the substitution case in its final form:
                # copy one pinned file over another and repin the victim's
                # registry row to the aggressor's digest, and a presence check
                # is satisfied because a consumer really does hold that value
                # -- for the aggressor. Codex reproduced it on #258.
                #
                # Registered paths are distinct artifacts by construction, so a
                # shared digest means two paths claim the same bytes, which is
                # exactly what substitution produces.
                owners = [
                    other
                    for other, digest_of in declared_by_path.items()
                    if other != relative and digest_of == registered
                ]
                if owners:
                    uncorroborated.append(
                        f"{relative} (digest also registered to {owners[0]})"
                    )
                    continue
                if relative in REGISTRY_IS_SOLE_PIN:
                    continue
                # Presence, plus the ownership test above. Codex asked for
                # corroboration to establish that the external pin belongs to
                # `relative` rather than occurring anywhere, and the reachable
                # form of that is the `owners` check: registered paths are
                # distinct artifacts, so a digest naming two of them is
                # substitution and is rejected before reaching here.
                #
                # A basename-proximity rule was tried and REJECTED as a false
                # positive: data/candidates/vv4_full_mastery_all_candidate.json
                # is corroborated by its own map file, which records the digest
                # as `feature_manifest_sha256` without spelling the basename
                # nearby. Requiring the name to sit beside the digest would
                # condemn that correct file, so ownership is established from
                # the registry's one-row-per-path structure rather than from
                # the layout of the corroborating file.
                if not any(registered in text for text in elsewhere):
                    uncorroborated.append(relative)
                continue
            allowed = allowed_by_path.get(relative)
            if allowed is None:
                others = [t for name, t in corpus.items() if name != relative]
                if not any(digest in text for text in others):
                    stale.append(relative)
            elif digest not in allowed:
                stale.append(relative)
        self.assertEqual(
            uncorroborated,
            [],
            "the registry records a digest for these files that NO other pin "
            "in the repository agrees with. Either the file was changed and "
            "only data/source-text-authentication.json was updated -- leaving "
            "the pin the patcher enforces naming the old bytes -- or the "
            "consumer was repinned and the registry was not. Update both, so "
            f"the registry records a pin rather than replacing one: {uncorroborated}",
        )
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
        # COVERAGE, not size. A count-only guard cannot see a deletion: remove
        # one row and the file drops back to the global-digest fallback, where
        # a substitution passes again. Codex reproduced that on 86927c75 by
        # deleting the row for data/native_evidence_queries.json and replacing
        # the file with another pinned JSON.
        #
        # Anchored to the COMMITTED registry as well as to current bytes.
        # `raw_pinned_files()` is computed from what the files contain now, so
        # a commit that drifts a file AND drops its row removes it from both
        # sides of this subtraction and the deletion becomes invisible -- the
        # erasure Codex reproduced on this PR. HEAD's row list cannot be edited
        # by the working tree, so the path stays in the minuend and a deleted
        # row is reported instead of vanishing.
        uncovered = sorted(
            (
                set(raw_pinned_files())
                | (_committed_registry_paths() & set(eol_pinned_files()))
            )
            - set(registered)
            - KNOWN_UNPINNED_CRLF_DEFECTS
        )
        self.assertEqual(
            uncovered,
            [],
            "these files are pinned by a raw sha256 but are not named in "
            f"{REGISTRY_PATH}, so nothing owns their path and a file committed "
            "with another pinned file's bytes inherits that file's digest. Add "
            f"a row for each: {uncovered}",
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

    def test_the_sole_pin_exemptions_are_still_sole(self):
        """An exemption must not outlive the reason for it.

        REGISTRY_IS_SOLE_PIN exists because no other file records those
        artifacts' digests, so the corroboration check has nothing to compare
        against. If one later gains a second record, the exemption becomes a
        hole that silently skips a file the check should now cover -- the same
        failure mode KNOWN_UNPINNED_CRLF_DEFECTS guards against above.
        """
        corpus = _pin_corpus()
        registered = _authenticated_digests()
        no_longer_sole = []
        # A missing row is a FAILURE, not a skip. These artifacts are pinned by
        # the registry and by nothing else, so deleting the row deletes their
        # only authentication -- and because they have no second record, the
        # deletion also removes them from every other check here. Skipping on
        # `None` meant the one case that destroys the pin was the one case that
        # reported nothing. Codex reproduced it by committing the deletion of
        # the vv3_running_candidate_map row: all 12 tests stayed green.
        missing_row = sorted(
            relative
            for relative in REGISTRY_IS_SOLE_PIN
            if registered.get(relative) is None
        )
        self.assertEqual(
            missing_row,
            [],
            "these paths are exempt from corroboration BECAUSE the registry is "
            "their sole pin, but the registry no longer names them -- so they "
            "now have no pin at all. Restore the row, or drop the path from "
            f"REGISTRY_IS_SOLE_PIN if it is genuinely gone: {missing_row}",
        )
        for relative in sorted(REGISTRY_IS_SOLE_PIN):
            digest = registered[relative]
            elsewhere = [
                text
                for name, text in corpus.items()
                if name not in (relative, REGISTRY_PATH)
            ]
            if any(digest in text for text in elsewhere):
                no_longer_sole.append(relative)
        self.assertEqual(
            no_longer_sole,
            [],
            "these files now have a second record of their digest, so the "
            "registry is no longer their sole pin and the exemption is a hole: "
            f"drop them from REGISTRY_IS_SOLE_PIN: {no_longer_sole}",
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
