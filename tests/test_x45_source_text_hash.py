from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from scripts.source_text_hash import (
    SourceTextHashError,
    authenticated_file_sha256,
    canonical_source_text_bytes,
    raw_file_sha256,
    source_text_sha256_bytes,
)


class X45SourceTextHashTests(unittest.TestCase):
    def test_lf_crlf_cr_and_bom_are_identical(self) -> None:
        expected = hashlib.sha256(b"alpha\nbeta\n").hexdigest().upper()
        variants = (
            b"alpha\nbeta\n",
            b"alpha\r\nbeta\r\n",
            b"alpha\rbeta\r",
            b"\xef\xbb\xbfalpha\r\nbeta\r\n",
        )
        self.assertEqual({source_text_sha256_bytes(item) for item in variants}, {expected})

    def test_mixed_newlines_normalize_in_required_order(self) -> None:
        self.assertEqual(
            canonical_source_text_bytes(b"one\r\ntwo\rthree\n"),
            b"one\ntwo\nthree\n",
        )

    def test_invalid_utf8_fails_closed(self) -> None:
        with self.assertRaisesRegex(SourceTextHashError, "not valid UTF-8"):
            source_text_sha256_bytes(b"valid\n\xff")

    def test_text_extensions_use_canonical_hash_and_binary_stays_raw(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text = root / "contract.json"
            binary = root / "artifact.bin"
            payload = b"line1\r\nline2\r\n"
            text.write_bytes(payload)
            binary.write_bytes(payload)
            self.assertEqual(
                authenticated_file_sha256(text),
                source_text_sha256_bytes(payload),
            )
            self.assertEqual(authenticated_file_sha256(binary), raw_file_sha256(binary))
            self.assertNotEqual(authenticated_file_sha256(text), authenticated_file_sha256(binary))

    def test_tracked_x45_text_is_portable_from_clean_archive_bytes(self) -> None:
        payload = b'{\r\n  "status": false\r\n}\r\n'
        clean_archive_payload = payload.replace(b"\r\n", b"\n")
        self.assertEqual(
            source_text_sha256_bytes(payload),
            source_text_sha256_bytes(clean_archive_payload),
        )


if __name__ == "__main__":
    unittest.main()
