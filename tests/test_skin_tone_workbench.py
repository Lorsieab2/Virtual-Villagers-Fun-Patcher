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
        self.built, self.read, self.painted, self.fail_reads, self.jobs = [], [], {}, False, []

    def __call__(self, script, job):
        if script is sheets._GIMP_BUILD:
            for item in job["files"]:
                names = [layer["name"] for layer in item["layers"]]
                self.jobs.append(item["layers"])
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
        painted = Image.new("RGBA", (600, 25), (0, 0, 0, 0))     # tone 3's colour layer as the owner left it:
        painted.putpixel((152, 7), (90, 60, 40, 255))            # paint of any colour on two pixels,
        painted.putpixel((153, 7), (1, 2, 3, 9))                 # one of them faint, as a sprite's edge is
        self.gimp.painted["vv1_carrying.xcf"] = {"skin_03.png": painted}
        written, kept, unread = self.build()
        self.assertEqual((written, kept, unread), ([], ["carrying"], []))
        self.assertEqual(self.xcf.read_bytes(), theirs, "the owner's file, byte for byte")
        self.assertEqual(self.gimp.read, ["vv1_carrying.xcf"], "read as `import` reads it")
        self.assertEqual(self.gimp.built, ["vv1_carrying.xcf"], "built once, the first time only")
        kept_layer = self.folder / "edits" / "carrying" / "skin_03.png"
        self.assertTrue(kept_layer.is_file(), "its edit is kept in edits")
        mark = np.array(Image.open(kept_layer).convert("RGBA"))
        self.assertEqual({tuple(p) for p in mark.reshape(-1, 4)}, {(255, 255, 255, 255), (0, 0, 0, 0)},
                         "kept as where the skin is: no colour of the owner's paint, none of the art")
        self.assertEqual([(int(x), int(y)) for y, x in zip(*np.nonzero(mark[..., 3]))], [(152, 7), (153, 7)])
        art = sheets.Art("vv1", self.images, self.folder / "edits", shipped=False)
        self.assertEqual(int(art.tone_mask("carrying.png", 3).sum()), 2, "tone 3 has skin where they painted")
        self.assertEqual(int(art.tone_mask("carrying.png", 4).sum()), int(art.mask("carrying.png").sum()),
                         "and every other tone keeps the sheet's own mask")
        stock = art.stock("carrying.png")
        three = art.sheet("carrying.png", sheets.core.TONES[2])
        self.assertEqual({(int(x), int(y)) for y, x in zip(*np.nonzero((three != stock).any(-1)))}, {(152, 7), (153, 7)},
                         "the tone is made on exactly those pixels, shaded from the game's own art")
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

    def test_a_build_makes_each_tone_a_group_of_paint_under_shading(self):
        self.build()
        names = json.loads(self.xcf.read_bytes()[len(b"gimp xcf "):])
        want = [sheets.LAYER_GAME, sheets.LAYER_MASK]
        for number in range(1, len(sheets.core.TONES) + 1):
            want += [sheets.paint_layer_name(number), sheets.LAYER_SHADING]
        self.assertEqual(names, want + [sheets.LAYER_TOP])
        self.assertEqual(self.gimp.jobs[-1][3]["group"], sheets.tone_layer_name(1))
        self.assertEqual(self.gimp.jobs[-1][2]["group"], sheets.tone_layer_name(1))
        self.assertEqual([(layer["clip"], layer["lock"]) for layer in self.gimp.jobs[-1][2:4]],
                         [(False, False), (True, True)], "paint: free to edit; shading: locked, shown only on paint")
        record = json.loads((self.folder / ".generated.json").read_text(encoding="utf-8"))["carrying"]
        self.assertEqual(sorted(record), ["mask.png"] + [f"skin_{n:02d}.png" for n in range(1, 11)])

    def test_a_colour_layer_still_as_built_is_not_an_edit(self):
        self.build()
        self.xcf.write_bytes(self.xcf.read_bytes() + b" saved again, nothing painted")
        mask = sheets.Art("vv1", self.images, shipped=False).mask("carrying.png")
        layer = np.zeros(mask.shape + (4,), np.uint8)
        layer[mask] = (146, 98, 62, 255)
        self.gimp.painted["vv1_carrying.xcf"] = {"skin_07.png": Image.fromarray(layer)}
        self.build()
        self.assertFalse((self.folder / "edits" / "carrying" / "skin_07.png").exists())

    def test_starting_fresh_backs_every_file_up_first(self):
        self.build()
        self.xcf.write_bytes(self.xcf.read_bytes() + b" and the owner's painting")
        theirs = self.xcf.read_bytes()
        written, kept, unread = sheets.build_workbench("vv1", self.images, self.folder, fresh_backup="_before")
        self.assertEqual((len(written), kept, unread), (1, [], []))
        self.assertEqual((self.folder / "_before" / "vv1_carrying.xcf").read_bytes(), theirs, "their file is kept")
        self.assertNotEqual(self.xcf.read_bytes(), theirs, "and a fresh one is in its place")
        self.assertEqual(self.gimp.read, [], "nothing is read back")
        self.xcf.write_bytes(b"painted again")
        sheets.build_workbench("vv1", self.images, self.folder, fresh_backup="_before")
        self.assertEqual((self.folder / "_before" / "vv1_carrying.xcf").read_bytes(), theirs, "a backup is never overwritten")
        self.assertEqual((self.folder / "_before" / "vv1_carrying (2).xcf").read_bytes(), b"painted again")

    def test_publishing_ships_where_the_skin_is_and_nothing_else(self):
        """What goes into the patcher: white marks on the sprite's own pixels -- not the owner's paint colour,
        not a pixel of the game's art -- and the patcher's own maker tones exactly those pixels."""
        self.build()
        self.xcf.write_bytes(self.xcf.read_bytes() + b" and the owner's painting")
        painted = Image.new("RGBA", (600, 25), (0, 0, 0, 0))
        painted.putpixel((152, 7), (90, 60, 40, 255))            # on the baby's face
        painted.putpixel((130, 15), (90, 60, 40, 255))           # on the blanket: the owner says it is skin
        painted.putpixel((3, 3), (90, 60, 40, 255))              # off the sprite: nothing
        self.gimp.painted["vv1_carrying.xcf"] = {"skin_03.png": painted}
        self.build()
        edits, out = self.folder / "edits", self.folder.parent / "shipped"
        written = sheets.publish_edits(sheets.Art("vv1", self.images, edits, shipped=False), edits, out)
        self.assertEqual(written, ["vv1/carrying/skin_03.png"])
        mark = np.array(Image.open(out / "vv1" / "carrying" / "skin_03.png").convert("RGBA"))
        self.assertEqual({tuple(int(v) for v in p) for p in mark.reshape(-1, 4)}, {(255, 255, 255, 255), (0, 0, 0, 0)})
        self.assertEqual({(int(x), int(y)) for y, x in zip(*np.nonzero(mark[..., 3]))}, {(152, 7), (130, 15)})
        pins = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(list(pins), ["vv1/carrying/skin_03.png"])
        # The patcher's maker (Pillow only) and this tool make the same tone 3 from it.
        sys.path.insert(0, str(ROOT / "src"))
        import vv_skin_tone_art as maker
        maker.write_tone_sheets(1, self.images, self.folder.parent / "made", edits=[out / "vv1"], tones=[3])
        made = np.array(Image.open(self.folder.parent / "made" / maker.installed_name(3, "carrying.png")).convert("RGBA"))
        stock = np.array(Image.open(self.images / "carrying.png").convert("RGBA"))
        self.assertEqual({(int(x), int(y)) for y, x in zip(*np.nonzero((made != stock).any(-1)))}, {(152, 7), (130, 15)})

    def test_the_readme_says_so(self):
        self.assertIn("A file you have changed is never overwritten", sheets.README)
        self.assertNotIn("the .xcf files are replaced", sheets.README)
        self.assertIn(f'see "{sheets.TUTORIAL_NAME}" in this folder', sheets.README)

    def half_see_through(self, extra=None):
        """The sheet's own generated mask as GIMP hands it back when its layer was left at 50% opacity."""
        mask = sheets.Art("vv1", self.images, shipped=False).mask("carrying.png")
        layer = np.zeros(mask.shape + (4,), np.uint8)
        layer[mask] = (255, 255, 255, 128)
        if extra is not None:
            layer[extra[1], extra[0]] = (255, 255, 255, 128)
        return Image.fromarray(layer)

    def test_a_mask_left_at_half_opacity_is_read_whole(self):
        self.build()
        self.xcf.write_bytes(self.xcf.read_bytes() + b" the owner marked one more pixel, at 50% opacity")
        self.gimp.painted["vv1_carrying.xcf"] = {"mask.png": self.half_see_through(extra=(140, 3))}
        self.build()
        kept = Image.open(self.folder / "edits" / "carrying" / "mask.png").convert("RGBA")
        self.assertEqual(kept.getpixel((140, 3)), (255, 255, 255, 255), "the pixel the owner marked")
        self.assertEqual(kept.getpixel((152, 7)), (255, 255, 255, 255), "the skin that was already marked")
        self.assertEqual(set(kept.getdata()), {(255, 255, 255, 255), (0, 0, 0, 0)}, "kept clean: white or nothing")

    def test_a_mask_whose_opacity_alone_changed_is_not_an_edit(self):
        self.build()
        self.xcf.write_bytes(self.xcf.read_bytes() + b" saved again with the mask at 50%")
        self.gimp.painted["vv1_carrying.xcf"] = {"mask.png": self.half_see_through()}
        self.build()
        self.assertFalse((self.folder / "edits" / "carrying" / "mask.png").exists())


@unittest.skipUnless(HAVE, "numpy, scipy or Pillow is missing")
class Guides(unittest.TestCase):
    """README.txt and the GIMP tutorial in the workbench folder: written, brought up to date, never over
    the owner's own changes."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.bench = Path(tmp.name) / "bench"

    def test_written_then_up_to_date(self):
        self.assertEqual(sheets.write_guides(self.bench), {"README.txt": "written", sheets.TUTORIAL_NAME: "written"})
        self.assertEqual((self.bench / sheets.TUTORIAL_NAME).read_bytes(), sheets.TUTORIAL.read_bytes())
        self.assertEqual(set(sheets.write_guides(self.bench).values()), {"up to date"})

    def test_an_older_one_of_ours_is_brought_up_to_date(self):
        sheets.write_guides(self.bench)
        with mock.patch.object(sheets, "README", sheets.README + "one more line\n"):
            self.assertEqual(sheets.write_guides(self.bench)["README.txt"], "brought up to date")
            self.assertTrue((self.bench / "README.txt").read_text(encoding="utf-8").endswith("one more line\n"))

    def test_one_the_owner_changed_is_kept(self):
        sheets.write_guides(self.bench)
        for name in ("README.txt", sheets.TUTORIAL_NAME):
            (self.bench / name).write_text("my own notes", encoding="utf-8")
        with mock.patch.object(sheets, "README", sheets.README + "one more line\n"):
            done = sheets.write_guides(self.bench)
        self.assertEqual(set(done.values()), {"kept (changed by you)"})
        self.assertEqual((self.bench / "README.txt").read_text(encoding="utf-8"), "my own notes")
        self.assertEqual((self.bench / sheets.TUTORIAL_NAME).read_text(encoding="utf-8"), "my own notes")

    def test_one_with_no_record_is_kept(self):
        self.bench.mkdir(parents=True)
        (self.bench / sheets.TUTORIAL_NAME).write_text("put here by hand", encoding="utf-8")
        self.assertEqual(sheets.write_guides(self.bench)[sheets.TUTORIAL_NAME], "kept (changed by you)")
        self.assertEqual((self.bench / sheets.TUTORIAL_NAME).read_text(encoding="utf-8"), "put here by hand")

    def test_the_tutorial_names_the_layers_as_they_are_built(self):
        text = sheets.TUTORIAL.read_text(encoding="utf-8")
        lines = [line.strip() for line in text.splitlines()]
        top = lines.index(sheets.LAYER_TOP + "   (locked)")
        self.assertTrue(lines[top + 1].startswith(f"{sheets.tone_layer_name(len(sheets.core.TONES))} ... {sheets.tone_layer_name(1)}"))
        self.assertTrue(lines[top + 2].startswith(sheets.LAYER_MASK) and lines[top + 2].endswith("(hidden)"))
        self.assertTrue(lines[top + 3].startswith(sheets.LAYER_GAME) and lines[top + 3].endswith("(locked)"))
        self.assertIn("python scripts\\skin_tone_sheets.py import --game vv1", text)
        self.assertIn('"import" reads the mask\n   the same at any opacity', text)
        inside = lines.index(sheets.LAYER_SHADING.replace(" (locked)", "") + " (locked)              never paint this one")
        self.assertTrue(lines[inside + 1].startswith(sheets.paint_layer_name(len(sheets.core.TONES))))
        for words in ("Pencil tool [N]", "Eraser [Shift+E]", "skin_NN.png"):
            self.assertIn(words, text)


if __name__ == "__main__":
    unittest.main()
