"""The owner's GIMP workbench is never overwritten (scripts/skin_tone_sheets.py build_workbench).

The owner's rule: nothing may destroy their data.  A rebuild makes again only the .xcf files that are still
exactly what the tool wrote (each is pinned by SHA-256 in the workbench's .generated.json).  A file that
differs is the owner's: it is read first, as `import` reads it, so its edits are in "edits", and then it is
left byte for byte as it is; if it cannot be read it is left as it is too, and said so.

GIMP is stood in for (it writes and reads the .xcf files in the real tool); the sheets are a small made-up
"game" of one picture, so nothing here needs a game's art.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import numpy as np
    from PIL import Image

    import skin_tone_sheets as sheets

    HAVE = True
except ImportError:  # pragma: no cover - the tool needs numpy and scipy, which the patcher itself does not
    HAVE = False


class FakeGimp:
    """Writes an .xcf for a build job; for an export job, the layers the test says the owner painted."""

    def __init__(self):
        self.built, self.read, self.painted, self.fail_reads = [], [], {}, False

    def __call__(self, script, job):
        if script is sheets._GIMP_BUILD:
            for item in job["files"]:
                names = [layer["name"] for layer in item["layers"]]
                Path(item["xcf"]).write_bytes(b"gimp xcf " + json.dumps(names).encode())
                self.built.append(Path(item["xcf"]).name)
            return ""
        if self.fail_reads:
            raise SystemExit("GIMP did not finish every file")
        for item in job["files"]:
            # GIMP hands the wanted layers back as one picture, one under the other, and their names in order.
            self.read.append(Path(item["xcf"]).name)
            Path(item["out"]).mkdir(parents=True, exist_ok=True)
            layers = self.painted.get(Path(item["xcf"]).name, {})
            if layers:
                width, height = next(iter(layers.values())).size
                tall = Image.new("RGBA", (width, height * len(layers)), (0, 0, 0, 0))
                for k, image in enumerate(layers.values()):
                    tall.paste(image, (0, k * height))
                tall.save(Path(item["out"]) / "layers.png")
            (Path(item["out"]) / "layers.json").write_text(json.dumps(list(layers)), encoding="utf-8")
        return ""


@unittest.skipUnless(HAVE, "numpy, scipy or Pillow is missing")
class Rebuild(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.images, self.folder = root / "Images", root / "bench" / "vv1"
        self.images.mkdir()
        # One sheet: the carried-things picture, with a held baby's face in its cell (warm, lit pixels).
        art = np.zeros((25, 600, 4), np.uint8)
        art[5:12, 150:158] = (240, 190, 140, 255)
        art[12:20, 125:150] = (220, 230, 250, 255)
        Image.fromarray(art).save(self.images / "carrying.png")
        self.gimp = FakeGimp()
        patch = mock.patch.object(sheets, "run_gimp", self.gimp)
        patch.start()
        self.addCleanup(patch.stop)
        self.xcf = self.folder / "vv1_carrying.xcf"

    def build(self):
        return sheets.build_workbench("vv1", self.images, self.folder)

    def test_a_first_build_writes_and_pins_the_file(self):
        written, kept, unread = self.build()
        self.assertEqual(([Path(p).name for p in written], kept, unread), (["vv1_carrying.xcf"], [], []))
        pins = json.loads((self.folder / ".generated.json").read_text(encoding="utf-8"))[sheets.XCF_PINS]
        self.assertEqual(pins, {"carrying": sheets._file_sha(self.xcf)})
        self.assertEqual(sheets.changed_by_the_owner("vv1", self.folder, ["carrying"]), [])

    def test_an_untouched_file_is_made_again(self):
        self.build()
        written, kept, unread = self.build()
        self.assertEqual((len(written), kept, unread), (1, [], []))
        self.assertEqual(self.gimp.built, ["vv1_carrying.xcf"] * 2)
        self.assertEqual(self.gimp.read, [], "nothing to read: nothing was changed")

    def test_a_file_the_owner_changed_is_read_and_never_replaced(self):
        self.build()
        self.xcf.write_bytes(self.xcf.read_bytes() + b" and the owner's painting")
        theirs = self.xcf.read_bytes()
        painted = Image.new("RGBA", (600, 25), (0, 0, 0, 0))
        painted.putpixel((152, 7), (90, 60, 40, 255))
        self.gimp.painted["vv1_carrying.xcf"] = {"tone_03.png": painted}
        written, kept, unread = self.build()
        self.assertEqual((written, kept, unread), ([], ["carrying"], []))
        self.assertEqual(self.xcf.read_bytes(), theirs, "the owner's file, byte for byte")
        self.assertEqual(self.gimp.read, ["vv1_carrying.xcf"], "read as `import` reads it")
        self.assertEqual(self.gimp.built, ["vv1_carrying.xcf"], "built once, the first time only")
        kept_layer = self.folder / "edits" / "carrying" / "tone_03.png"
        self.assertTrue(kept_layer.is_file(), "its edit is kept in edits")
        self.assertEqual(Image.open(kept_layer).convert("RGBA").getpixel((152, 7)), (90, 60, 40, 255))
        # ... and again, however often: still theirs.
        self.build()
        self.assertEqual(self.xcf.read_bytes(), theirs)

    def test_a_changed_file_that_cannot_be_read_is_left_alone(self):
        self.build()
        self.xcf.write_bytes(b"not something GIMP can open, but the owner's")
        self.gimp.fail_reads = True
        written, kept, unread = self.build()
        self.assertEqual((written, kept, unread), ([], [], ["carrying"]))
        self.assertEqual(self.xcf.read_bytes(), b"not something GIMP can open, but the owner's")
        self.assertFalse((self.folder / "edits").exists())

    def test_a_file_with_no_record_is_taken_for_the_owners(self):
        """A workbench built before the files were pinned, or a file the owner put there."""
        self.folder.mkdir(parents=True)
        self.xcf.write_bytes(b"who knows")
        written, kept, unread = self.build()
        self.assertEqual((written, kept), ([], ["carrying"]))
        self.assertEqual(self.xcf.read_bytes(), b"who knows")

    def test_pinning_an_older_workbench_skips_files_changed_since(self):
        self.build()
        manifest = self.folder / ".generated.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        del data[sheets.XCF_PINS]
        manifest.write_text(json.dumps(data), encoding="utf-8")
        built_at = self.xcf.stat().st_mtime
        self.assertEqual(sheets.pin_as_written("vv1", self.folder, built_at - 10), [], "changed after: the owner's")
        self.assertEqual(sheets.changed_by_the_owner("vv1", self.folder, ["carrying"]), ["carrying"])
        self.assertEqual(sheets.pin_as_written("vv1", self.folder, built_at + 1), ["carrying"])
        self.assertEqual(sheets.changed_by_the_owner("vv1", self.folder, ["carrying"]), [])

    def test_the_readme_says_so(self):
        self.assertIn("A file you have changed is never overwritten", sheets.README)
        self.assertNotIn("the .xcf files are replaced", sheets.README)


if __name__ == "__main__":
    unittest.main()
