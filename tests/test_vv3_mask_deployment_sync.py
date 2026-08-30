from __future__ import annotations

import hashlib
import re
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "candidates" / "VVFP VV3 Full Mastery Candidate.dll"
DEPLOYED = ROOT / "data" / "candidates" / "VVFP VV3 Safe Upgrades.dll"
MANIFEST = ROOT / "data" / "vv3_origins_feature.json"
BUILDER = ROOT / "scripts" / "build_vv3_safe_upgrade_resources.py"
COMPILE_SCRIPT = ROOT / "scripts" / "build_vv3_full_mastery_candidate_dll.ps1"
ORIGINS_BUILDER = ROOT / "scripts" / "build_vv3_origins_feature.py"


_C_SIMPLE_ESCAPES = {
    "a": 0x07,
    "b": 0x08,
    "f": 0x0C,
    "n": 0x0A,
    "r": 0x0D,
    "t": 0x09,
    "v": 0x0B,
    "\\": 0x5C,
    "'": 0x27,
    '"': 0x22,
    "?": 0x3F,
}


def _decode_c_string(literal: str) -> bytes:
    """Decode a C string-literal body into the BYTES the compiler stores.

    The compiled DLL holds the decoded byte for an escape such as ``\\"`` or
    ``\\n``, so comparing the raw source spelling would fail a companion that
    was in fact rebuilt correctly.

    This returns bytes rather than str on purpose.  A numeric escape may name a
    non-ASCII byte -- ``\\xE9`` or ``\\351`` -- and MSVC stores that byte
    verbatim.  Decoding to a Unicode character instead would make the later
    ASCII encode raise, rejecting a correctly rebuilt DLL for part of the very
    syntax this claims to support.
    """
    out = bytearray()
    index = 0
    while index < len(literal):
        char = literal[index]
        if char != "\\":
            encoded = char.encode("utf-8")
            out.extend(encoded)
            index += 1
            continue
        index += 1
        if index >= len(literal):
            raise AssertionError(f"dangling escape in C literal: {literal!r}")
        escape = literal[index]
        if escape == "x":
            index += 1
            digits = ""
            while index < len(literal) and literal[index] in "0123456789abcdefABCDEF":
                digits += literal[index]
                index += 1
            if not digits:
                raise AssertionError(f"empty hex escape in C literal: {literal!r}")
            value = int(digits, 16)
            if value > 0xFF:
                raise AssertionError(f"hex escape exceeds one byte: {literal!r}")
            out.append(value)
            continue
        if escape in "01234567":
            digits = ""
            while index < len(literal) and len(digits) < 3 and literal[index] in "01234567":
                digits += literal[index]
                index += 1
            value = int(digits, 8)
            if value > 0xFF:
                raise AssertionError(f"octal escape exceeds one byte: {literal!r}")
            out.append(value)
            continue
        if escape not in _C_SIMPLE_ESCAPES:
            raise AssertionError(f"unsupported C escape in {literal!r}")
        out.append(_C_SIMPLE_ESCAPES[escape])
        index += 1
    return bytes(out)


def _load_builder():
    spec = importlib.util.spec_from_file_location("vv3_safe_upgrade_sync", BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load VV3 companion synchronizer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VV3MaskDeploymentSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = _load_builder()

    def test_deployed_companion_is_byte_identical_to_canonical_build(self) -> None:
        canonical = SOURCE.read_bytes()
        deployed = DEPLOYED.read_bytes()
        self.assertEqual(deployed, canonical)
        # Assert against the synchronizer's own reviewed pin rather than a second
        # copy of the digest.  A duplicated literal here silently goes stale on
        # every legitimate DLL rebuild, which is exactly how it drifted before.
        self.assertEqual(
            hashlib.sha256(deployed).hexdigest().upper(),
            self.builder.SOURCE_SHA256,
        )
        self.assertEqual(len(deployed), self.builder.SOURCE_SIZE)

    def test_manifest_hash_is_the_canonical_deployed_hash(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        companion = manifest["companion_files"][0]
        self.assertEqual(companion["source"], "data/candidates/VVFP VV3 Safe Upgrades.dll")
        self.assertEqual(
            companion["sha256"],
            hashlib.sha256(SOURCE.read_bytes()).hexdigest().upper(),
        )

    def test_patcher_output_contains_the_village_mask_hook_and_append(self) -> None:
        stock = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
        if not stock.is_file():
            self.skipTest("stock VV3 executable fixture is unavailable")
        import sys
        sys.path.insert(0, str(ROOT / "src"))
        import vv_fun_patcher
        build = next(item for item in vv_fun_patcher.load_builds() if item.id == "vv3")
        rendered, _ = vv_fun_patcher.render_patched_bytes(
            stock, build, "collection_progression", ["vv3_enable_origins_exclusive_features"]
        )
        self.assertEqual(rendered[0x60C7F:0x60C84], bytes.fromhex("E87CE32700"))
        self.assertEqual(len(rendered), 0xCB000 + 0x2000)

    def test_canonical_build_contains_every_mask_export(self) -> None:
        exports = self.builder.export_names(SOURCE.read_bytes())
        self.assertTrue(self.builder.REQUIRED_MASK_EXPORTS <= exports)
        self.assertTrue(self.builder.REQUIRED_RUNNING_EXPORTS <= exports)
        self.assertIn("VV3RunningMaskBoundary", exports)
        self.assertEqual(len(exports), 32)

    def test_deployed_companion_carries_every_complete_result_message(self) -> None:
        """Every COMPLETE refusal message in the C source must be in the DLL.

        Editing a user-facing string without rebuilding leaves the source-only
        assertions passing while the game keeps showing the old text.  That
        happened once already: the source said "No active save slot is
        available yet" while the released companion still said "until this
        village has been saved at least once".

        This compares whole concatenated messages, not opening substrings, and
        it discovers them from the source rather than listing them here -- so a
        reworded tail, a changed deduction suffix, or a newly added branch is
        caught too, and the guard cannot silently fall behind the code.
        """
        source = (
            ROOT
            / "native"
            / "vv3_full_mastery_candidate"
            / "vv3_full_mastery_candidate.c"
        ).read_text(encoding="utf-8")

        block = source.split("if (affected == 0) {", 1)[1].split(
            "MessageBoxA(GetForegroundWindow(), why,", 1
        )[0]
        # Each branch is `why = "literal" "literal" ...;` across several lines,
        # so collect every assignment and concatenate its adjacent literals.
        # The literals are decoded first: the compiler stores the DECODED byte
        # for an escape such as \" or \n, so comparing the raw source spelling
        # would fail a correctly rebuilt companion.
        literal = r'"((?:[^"\\]|\\.)*)"'
        assignment_pattern = r"why\s*=\s*((?:\s*" + literal + r")+)\s*;"
        messages = []
        for match in re.finditer(assignment_pattern, block):
            parts = re.findall(literal, match.group(1))
            messages.append(b"".join(_decode_c_string(part) for part in parts))

        # persist-failed, the four VV3_CAF_MASK_* causes, and the default.
        self.assertEqual(
            len(messages),
            6,
            f"expected 6 refusal messages, found {len(messages)}: {messages}",
        )
        self.assertEqual(len(set(messages)), 6, "refusal messages are not distinct")

        deployed = DEPLOYED.read_bytes()
        for message in messages:
            with self.subTest(message=message[:48].decode("ascii", "replace")):
                self.assertIn(
                    message,
                    deployed,
                    "the deployed companion predates this source string; "
                    "rebuild the canonical DLL and re-pin it",
                )

        # Every distinct cause must actually be reachable in that chain.
        for cause in (
            "g_vv3_caf_mask_persist_failed",
            "VV3_CAF_MASK_NO_SLOT",
            "VV3_CAF_MASK_BAD_MODE",
            "VV3_CAF_MASK_AMBIGUOUS",
            "VV3_CAF_MASK_NO_ROOM",
        ):
            with self.subTest(cause=cause):
                self.assertIn(cause, block)

        # And the superseded wording must not still be shipping.
        self.assertNotIn(
            b"until this village has been saved at least once",
            deployed,
            "the deployed companion still carries the replaced message",
        )

    def test_c_string_decoder_matches_compiler_storage(self) -> None:
        """The decoder must produce what the compiler actually stores.

        Without it, a message containing a valid C escape would be compared
        against its raw source spelling and fail a companion that had in fact
        been rebuilt correctly.

        The result is BYTES.  A numeric escape may name a non-ASCII byte, which
        MSVC stores verbatim; decoding that to a Unicode character instead made
        the comparison raise on encode, rejecting a correctly rebuilt DLL for
        part of the very syntax this supports.
        """
        for literal, expected in (
            ("plain text", b"plain text"),
            (r"a\"b", b'a"b'),
            (r"a\\b", b"a\\b"),
            (r"l1\nl2", b"l1\nl2"),
            (r"tab\there", b"tab\there"),
            (r"hex\x41", b"hexA"),
            (r"oct\101", b"octA"),
            (r"\r\n", b"\r\n"),
            # Non-ASCII numeric escapes must survive as raw bytes.
            (r"hi\xE9", b"hi\xe9"),
            (r"hi\351", b"hi\xe9"),
            (r"\xff", b"\xff"),
        ):
            with self.subTest(literal=literal):
                self.assertEqual(_decode_c_string(literal), expected)
        for bad in ("dangling\\", r"empty\xZZ"):
            with self.subTest(invalid=bad):
                with self.assertRaises(AssertionError):
                    _decode_c_string(bad)

    def test_synchronize_repairs_a_stale_deployed_copy(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / DEPLOYED.name
            target.write_bytes(b"stale companion")
            with patch.object(self.builder, "OUTPUT", target):
                size, digest, exports = self.builder.synchronize()
            canonical = SOURCE.read_bytes()
            self.assertEqual(target.read_bytes(), canonical)
            self.assertEqual(size, len(canonical))
            self.assertEqual(digest, hashlib.sha256(canonical).hexdigest().upper())
            self.assertTrue(self.builder.REQUIRED_MASK_EXPORTS <= exports)
            self.assertTrue(self.builder.REQUIRED_RUNNING_EXPORTS <= exports)

    def test_compile_path_runs_synchronizer_after_native_build(self) -> None:
        script = COMPILE_SCRIPT.read_text(encoding="utf-8")
        invocation = '& python (Join-Path $projectRoot "scripts\\build_vv3_safe_upgrade_resources.py")'
        self.assertIn(invocation, script)
        self.assertIn('throw "VV3 Safe Upgrades companion synchronization failed."', script)

    def test_origins_builder_rejects_companion_drift(self) -> None:
        script = ORIGINS_BUILDER.read_text(encoding="utf-8")
        self.assertIn("CANONICAL_COMPANION", script)
        self.assertIn("COMPANION.read_bytes() != CANONICAL_COMPANION.read_bytes()", script)
        self.assertIn("VV3 deployed companion is stale", script)


if __name__ == "__main__":
    unittest.main()
