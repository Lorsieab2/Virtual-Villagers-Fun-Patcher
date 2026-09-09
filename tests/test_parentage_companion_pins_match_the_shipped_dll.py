"""Every pinned parentage companion digest must match the DLL actually shipped.

The build is not reproducible: three compilations from byte-identical source
produce three different SHA-256s. So a rebuild always invalidates every pin,
and the only safe order is rebuild, then regenerate every manifest, in that
order and in one tree. Doing it in the other order -- or regenerating only the
manifests you happened to be editing -- leaves a pin naming a DLL that no
longer exists.

The failure is quiet in the wrong direction: the patcher refuses to apply the
feature on a hash mismatch, so the player sees a feature that does nothing
rather than an obviously broken build. It also surfaces in a confusing place,
because the pin is checked for every game: a stale VV2 pin fails VV1 tests.

Two nesting shapes exist and both must be walked. VV1, VV4 and VV5 carry a
top-level `companion_sha256` as well as the per-file digest inside
`companion_files`; VV2 carries only the latter. A check that reads only the top
level reports VV2 as missing a pin, which looks like a broken manifest and is
not -- that exact mistake was made and reported by a peer session.
"""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPANION = ROOT / "assets/parentage/VVFP Parentage Export.dll"
MANIFESTS = sorted(ROOT.glob("data/vv*_parentage_feature.json"))


def _pins(document) -> list[tuple[str, str]]:
    """Every companion digest in a manifest, as (where, digest) pairs."""
    found: list[tuple[str, str]] = []

    def walk(node, path):
        if isinstance(node, dict):
            top = node.get("companion_sha256")
            if isinstance(top, str):
                found.append((path + ".companion_sha256", top))
            for entry in node.get("companion_files") or []:
                if isinstance(entry, dict) and isinstance(entry.get("sha256"), str):
                    name = entry.get("destination") or entry.get("source") or "?"
                    found.append((path + ".companion_files[%s]" % name, entry["sha256"]))
            for key, value in node.items():
                if key != "companion_files":
                    walk(value, path + "." + key)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, path + "[%d]" % index)

    walk(document, "")
    return found


class ParentageCompanionPinsMatchShippedDllTests(unittest.TestCase):
    def test_the_companion_is_present(self):
        self.assertTrue(
            COMPANION.is_file(),
            "the parentage companion must ship in the repository, since every "
            "manifest pins its digest",
        )

    def test_every_pin_matches_the_shipped_companion(self):
        digest = hashlib.sha256(COMPANION.read_bytes()).hexdigest().upper()
        self.assertTrue(MANIFESTS, "no parentage manifests were found")
        checked = 0
        for manifest in MANIFESTS:
            document = json.loads(manifest.read_text(encoding="utf-8"))
            pins = _pins(document)
            with self.subTest(manifest=manifest.name):
                # A manifest that pins nothing is the silent case: nothing to
                # disagree, so nothing to catch, and the DLL could be anything.
                self.assertTrue(
                    pins, "%s pins no companion digest at all" % manifest.name
                )
                for where, pin in pins:
                    checked += 1
                    self.assertEqual(
                        pin.upper(),
                        digest,
                        "%s%s pins %s but the shipped DLL is %s -- rebuild, "
                        "THEN regenerate every parentage manifest, in one tree"
                        % (manifest.name, where, pin[:16], digest[:16]),
                    )
        self.assertGreater(checked, 0, "no companion pin was checked")

    def test_both_nesting_shapes_are_reached(self):
        """The walker must find nested digests, not only top-level ones.

        VV2 has no top-level `companion_sha256`, so a checker that reads only
        the top level would report it as unpinned. Assert that at least one
        manifest is carried entirely by the nested shape, which is what makes
        the walk necessary rather than incidental.
        """
        nested_only = []
        for manifest in MANIFESTS:
            document = json.loads(manifest.read_text(encoding="utf-8"))
            pins = _pins(document)
            if pins and not any(w.endswith("companion_sha256") for w, _ in pins):
                nested_only.append(manifest.name)
        self.assertTrue(
            nested_only,
            "expected at least one manifest pinned only inside companion_files; "
            "if that stopped being true, this walk is no longer load-bearing "
            "and the simpler top-level read would be safe",
        )


if __name__ == "__main__":
    unittest.main()
