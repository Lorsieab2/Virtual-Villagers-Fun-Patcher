"""The village header is written once, at the top, and never again.

The parentage log is append-only. Its header names the village so a player with
several villages per game can tell which log is which, and the code's own
comment says writing it per record "would interleave it between records".

It did exactly that. Every guard asked `ftell(file) == 0` immediately after
`_wfopen(path, L"a")`, believing that reported the end of the file. It does
not: on a freshly opened append stream this CRT reports 0 however long the file
is, and resolves the position only at the first write. Compiled with the
project's own toolchain and the /MT runtime the shipped DLL uses:

    ftell after fopen("a") on a NON-empty file: 0
    ftell after the first write:                20

So the guard held for every record. Measured in the owner's own logs after he
Time Warped his villages: 10 headers inside VV3's file, 10 in VV5's, 2 in
VV2's, one before each record written once the village became known.

Two properties are pinned here, because fixing only the first would let the bug
return in a new spelling:

  1. No header guard may use ftell.
  2. The file must be measured BEFORE it is opened. Opening with "a" creates
     the file, so a measurement taken afterwards always reports empty -- which
     is the original bug with a different expression in it.
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "native", "parentage_export", "parentage_export.c")

APPEND_OPEN = 'file = _wfopen(path, L"a");'
MEASURE = "had_content = log_file_has_content(path);"


def source():
    with open(SOURCE, encoding="utf-8", newline="") as handle:
        return handle.read()


def without_comments(text):
    return re.sub(r"/\*.*?\*/", " ", text, flags=re.S)


class LogHeaderWrittenOnce(unittest.TestCase):
    def setUp(self):
        self.c = source()
        self.code = without_comments(self.c)

    def test_no_header_guard_uses_ftell(self):
        """ftell cannot answer "is this file new" on an append stream."""
        self.assertNotIn(
            "ftell", self.code,
            "a header guard still uses ftell. On a freshly opened append "
            "stream it reports 0 however long the file is, so the guard holds "
            "for every record and the header is written into the middle of "
            "the log.",
        )

    def test_every_append_open_measures_the_file_first(self):
        """Opening with "a" creates the file, so measuring after it is useless.

        Each writer must capture the answer before its own open. Checked by
        position: the measurement has to appear between the previous open and
        this one.
        """
        # Two writers open the log: append_record, which both record kinds
        # share (a record may be held until the village's first save and
        # written later, so the write lives in one place), and
        # EnsureParentageLog. Each still measures before it opens.
        opens = [m.start() for m in re.finditer(re.escape(APPEND_OPEN), self.code)]
        self.assertEqual(len(opens), 2,
                         "expected two append-mode opens, found %d" % len(opens))

        measures = [m.start() for m in re.finditer(re.escape(MEASURE), self.code)]
        self.assertEqual(len(measures), 2,
                         "expected two measurements, found %d" % len(measures))

        previous = 0
        for index, open_at in enumerate(opens):
            between = [m for m in measures if previous < m < open_at]
            self.assertEqual(
                len(between), 1,
                "append-mode open #%d has %d measurement(s) before it and "
                "after the previous open; each open needs exactly one, or it "
                "is measuring a file it has already created."
                % (index + 1, len(between)),
            )
            previous = open_at

    def test_the_measurement_asks_the_filesystem(self):
        """Not the stream: the size on disk, before anything is opened."""
        self.assertIn("static int log_file_has_content(const wchar_t *path) {",
                      self.c, "the helper was renamed or removed")
        body = self.c.split(
            "static int log_file_has_content(const wchar_t *path) {", 1)[1]
        body = body.split("\n}", 1)[0]
        self.assertIn("GetFileAttributesExW", body,
                      "the helper no longer measures the file on disk")
        self.assertNotIn("ftell", body)
        self.assertNotIn("_wfopen", body,
                         "the helper must not open the file it is measuring")

    def test_the_header_is_guarded_by_that_measurement(self):
        """Each village header write sits under !had_content."""
        writes = re.findall(r'fprintf\(file, "%s", village\)', self.code)
        self.assertEqual(len(writes), 2,
                         "expected two header writes, found %d" % len(writes))
        self.assertEqual(
            self.code.count("if (!had_content"), 2,
            "every header write must be guarded by the pre-open measurement")


if __name__ == "__main__":
    unittest.main()
